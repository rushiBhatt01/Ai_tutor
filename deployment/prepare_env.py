"""Generate private runtime configuration without printing any secret values.

No provider calls, OCI calls, container startup or resource creation occurs.
"""

import argparse
import json
import os
from pathlib import Path
import secrets
import sys
from urllib.parse import quote


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reuse-local-provider-keys", action="store_true")
    args = parser.parse_args()
    import bcrypt
    from dotenv import dotenv_values
    root = Path(__file__).resolve().parents[1]
    target = root / ".local-secrets" / "runtime.env"
    target.parent.mkdir(mode=0o700, exist_ok=True)
    if target.exists():
        raise SystemExit("Private runtime file already exists; refusing overwrite")
    values = {}
    provider_names = ("CEREBRAS_API_KEY", "GEMINI_API_KEY", "PIXABAY_API_KEY", "PEXELS_API_KEY", "UNSPLASH_ACCESS_KEY")
    if args.reuse_local_provider_keys:
        local = dotenv_values(root / "backend" / ".env")
        for name in provider_names:
            value = os.getenv(name) or local.get(name)
            if value:
                values[name] = value
        if not values.get("CEREBRAS_API_KEY"):
            # Existing resolver reads local files only; it does not call providers.
            sys.path.insert(0, str(root / "backend"))
            from functions.cerebras_client import resolve_cerebras_api_key
            value = resolve_cerebras_api_key()
            if value:
                values["CEREBRAS_API_KEY"] = value
    password = secrets.token_urlsafe(32)
    mongo_root, mongo_app = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    values.update({
        "TARGET_PLATFORM": "linux/arm64", "SITE_ADDRESS": "localhost", "PUBLIC_BIND_IP": "127.0.0.1",
        "API_USERNAME": "tutor", "API_PASSWORD": password,
        "PROXY_PASSWORD_HASH": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
        "MONGO_ROOT_USER": "tutor_root", "MONGO_ROOT_PASSWORD": mongo_root,
        "MONGO_APP_USER": "tutor_app", "MONGO_APP_PASSWORD": mongo_app,
        "MONGO_URI": f"mongodb://tutor_app:{quote(mongo_app, safe='')}@mongo:27017/video_tutorials?authSource=video_tutorials",
        "ARTIFACT_BACKEND": "local", "OCI_STORAGE_APPROVED": "false",
    })
    # Single quotes prevent Compose expanding $ in hashes; generated values have
    # no quotes/newlines. Reject unexpected input rather than creating bad env.
    for value in values.values():
        if any(c in value for c in ("'", "\r", "\n")):
            raise SystemExit("Unsupported character in a configuration value; no file written")
    fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
        stream.write("# PRIVATE: generated locally; never print, commit, or include in Docker context.\n")
        for name, value in values.items():
            stream.write(f"{name}='{value}'\n")
    print("Created .local-secrets/runtime.env; generated credentials and provider values are not printed.")
    missing = [name for name in ("CEREBRAS_API_KEY",) if not values.get(name)]
    if missing:
        print("Still required: " + ", ".join(missing))


if __name__ == "__main__":
    main()
