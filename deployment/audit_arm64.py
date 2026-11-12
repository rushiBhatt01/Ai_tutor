"""Audit locked Python artifacts for CPython 3.11 on Linux ARM64.

This performs read-only requests to PyPI JSON. It never installs packages or
reads environment variables. Output is a tracked compatibility report.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import re
import argparse
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
PIN = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s\\]+)", re.I)
PY311_TAGS = {"cp311", "py3"}
GLIBC_MAX = (2, 36)  # Debian Bookworm


def parse_lock(lock: Path) -> dict[str, dict[str, object]]:
    packages: dict[str, dict[str, object]] = {}
    current = None
    for line in lock.read_text(encoding="utf-8").splitlines():
        match = PIN.match(line)
        if match:
            current = re.sub(r"[-_.]+", "-", match.group(1)).lower()
            packages[current] = {"name": match.group(1), "version": match.group(2), "hashes": set()}
        elif current and "--hash=sha256:" in line:
            packages[current]["hashes"].add(line.split("sha256:", 1)[1].split()[0].rstrip("\\"))
        elif line.startswith("# via") or not line.endswith("\\"):
            current = None
    return packages


def linux_arm64_wheel(filename: str) -> bool:
    if not filename.endswith(".whl"):
        return False
    parts = filename[:-4].split("-")
    if len(parts) < 5:
        return False
    python_tags, abi_tags, platform_tags = (part.split(".") for part in parts[-3:])
    python_ok = bool(PY311_TAGS.intersection(python_tags)) or (
        "abi3" in abi_tags and any(re.fullmatch(r"cp3\d+", tag) for tag in python_tags)
    )
    if not python_ok:
        return False
    for platform in platform_tags:
        if platform == "any":
            return True
        if platform.endswith("_aarch64") or platform == "linux_aarch64":
            found = re.search(r"manylinux_(\d+)_(\d+)_aarch64", platform)
            if found and tuple(map(int, found.groups())) <= GLIBC_MAX:
                return True
            if "manylinux2014_aarch64" in platform or "manylinux2010_aarch64" in platform or "manylinux1_aarch64" in platform:
                return True
    return False


def check_package(item: tuple[str, dict[str, object]]) -> dict[str, object]:
    normalized, spec = item
    name, version = str(spec["name"]), str(spec["version"])
    request = Request(
        f"https://pypi.org/pypi/{quote(name)}/{quote(version)}/json",
        headers={"User-Agent": "oracle-cpu-tutor-arm64-compat-audit/1.0"},
    )
    try:
        with urlopen(request, timeout=25) as response:
            data = json.load(response)
    except (HTTPError, URLError, TimeoutError) as exc:
        return {"name": name, "version": version, "status": "metadata-unavailable", "detail": type(exc).__name__}
    files = data.get("urls", [])
    wheels = [file for file in files if linux_arm64_wheel(file["filename"])]
    hashes = spec["hashes"]
    verified = [file for file in wheels if file["digests"]["sha256"] in hashes]
    sdist = next((file for file in files if file["packagetype"] == "sdist"), None)
    if verified:
        status = "hashed-arm64-wheel"
    elif sdist:
        status = "source-build-required"
    else:
        status = "blocked-no-arm64-artifact"
    selected = sorted(file["filename"] for file in verified)
    return {
        "name": name,
        "version": version,
        "status": status,
        "verified_wheels": selected[:4],
        "verified_wheel_count": len(selected),
        "sdist_available": bool(sdist),
        "lock_hashes_present": bool(hashes),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=ROOT / "backend" / "requirements.cpu.lock")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    lock = args.lock if args.lock.is_absolute() else ROOT / args.lock
    default_report = "arm64_python_audit.json" if lock.name == "requirements.cpu.lock" else "arm64_build_python_audit.json" if lock.name == "requirements.cpu-build.lock" else f"{lock.stem}_arm64_audit.json"
    report_path = args.report or ROOT / "deployment" / default_report
    if not report_path.is_absolute():
        report_path = ROOT / report_path
    packages = parse_lock(lock)
    results = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(check_package, item) for item in packages.items()]
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda row: str(row["name"]).lower())
    counts: dict[str, int] = {}
    for row in results:
        key = str(row["status"])
        counts[key] = counts.get(key, 0) + 1
    report = {
        "python": "CPython 3.11",
        "platform": "linux/arm64 (aarch64, glibc <= 2.36)",
        "lock": str(lock.relative_to(ROOT)).replace("\\", "/"),
        "lock_sha256": hashlib.sha256(lock.read_bytes()).hexdigest(),
        "pypi_source": "https://pypi.org/pypi/<package>/<version>/json",
        "packages_checked": len(results),
        "summary": counts,
        "packages": results,
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(report_path.relative_to(ROOT)), "packages_checked": len(results), "summary": counts}))
    return 1 if counts.get("blocked-no-arm64-artifact", 0) or counts.get("metadata-unavailable", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
