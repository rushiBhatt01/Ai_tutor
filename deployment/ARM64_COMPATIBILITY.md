# ARM64 compatibility audit and reproducible build

Audit date: 2026-11-07. Target: OCI VM.Standard.A1 (Ampere Altra, Linux ARM64/aarch64), Debian Bookworm, CPython 3.11.14. This is a compatibility audit and build recipe; it does not start containers or provision OCI resources.

## Container image audit

Docker Registry manifests were inspected with `docker buildx imagetools inspect`. All four pinned manifest lists contain `linux/arm64/v8`; the immutable index digests are pinned in the Dockerfiles/Compose file.

| Image | ARM64 result | Role |
| --- | --- | --- |
| `python:3.11.14-slim-bookworm` | Present; index `sha256:65a93d69fa75478d554f4ad27c85c1e69fa184956261b4301ebaf6dbb0a3543d` | Backend and worker |
| `node:22.22.0-bookworm-slim` | Present; index `sha256:dd9d21971ec4395903fa6143c2b9267d048ae01ca6d3ea96f16cb30df6187d94` | Next static export build stage |
| `caddy:2.10.2-alpine` | Present; index `sha256:4c6e91c6ed0e2fa03efd5b44747b625fec79bc9cd06ac5235a779726618e530d` | Static web/reverse proxy |
| `mongo:7.0.43-jammy` | Present; index `sha256:f71f6d0913c945096cd058557cbadf4ad435007f378d84b3c4c636c928735e72` | MongoDB and bundled Database Tools |

The Mongo tag was advanced from 7.0.16 to 7.0.43 (latest 7.0 patch found in the official image source at audit time); production Compose volume is new and this does not touch the local development MongoDB. MongoDB documents ARM64 support from ARMv8.2-A; OCI A1 uses Ampere Altra, which is ARMv8.2+. This establishes ISA compatibility. A native MongoDB runtime/backup drill remains pending.

## Python artifact audit

`backend/requirements.cpu.lock` pins 178 runtime distributions for CPython 3.11/aarch64 manylinux and contains hashes. The PyPI JSON audit verified a matching ARM64 or universal wheel and matching lock hash for **172** distributions. Six have no compatible wheel and require locked-source builds: `glcontext`, `manimpango`, `moderngl`, `moviepy`, `pycairo`, `srt`. None lacks both an ARM64 wheel and source distribution. `backend/requirements.cpu-build.lock` pins and hashes its 7 build tools; all 7 have verified ARM64/universal wheels. Full per-package evidence and lock hashes are in `arm64_python_audit.json` and `arm64_build_python_audit.json`.

Important native artifacts checked:

- **PyTorch 2.6.0 / torchvision 0.21.0:** hashed `manylinux_2_28_aarch64` wheels are present. There are no NVIDIA/CUDA distributions in the resolved runtime lock. Docker hides CUDA and the smoke procedure asserts the CPU wheel (`torch.version.cuda is None`). ARM package import and inference still need a real A1 run.
- **OpenCV 4.11.0.86:** a hashed `manylinux2014_aarch64` headless wheel is present. Headless avoids Qt/X11; image installs `libglib2.0-0` and `libgl1` for runtime shared libraries. Test import, `cv2.getBuildInformation()`, image read/write, and `ldd` on the built ARM image.
- **NumPy 2.2.6 / SciPy 1.15.3, Pillow 12, PyAV 13.1, lxml, orjson, pydantic-core, cryptography, bcrypt, and tokenizers:** hashed ARM64 wheels are present. Check native imports and shared libraries after build.
- **Manim 0.19:** Python package is architecture-neutral. `manimpango` and `pycairo` build from the pinned sdists against `libpango1.0-dev`, `libcairo2-dev`, `pkg-config`, Python headers, Cython, Meson/Ninja, and GCC. Cairo renderer is used; OpenGL is not required for the deployment's configured renderer. A 720p30 scene render is a runtime gate.
- **FFmpeg:** Debian's official Bookworm package index lists `ffmpeg` for ARM64, and the corresponding ARM64 `libavcodec59` package depends on ARM64 `libx264-164` ([ffmpeg package search](https://packages.debian.org/search?arch=arm64&keywords=ffmpeg&suite=bookworm), [libavcodec59](https://packages.debian.org/bookworm/arm64/libavcodec59), [libx264-164](https://packages.debian.org/bookworm/libx264-164)). The backend image installs Debian Bookworm's ARM64 `ffmpeg` package. Test `ffmpeg -version`, encoder presence (`libx264`, AAC), a short 720p30 encode and audio mux on ARM64. Package availability is verified; the actual codec run was not executed on ARM hardware here.
- **MongoDB:** official ARM64 image and `mongodump`/`mongorestore` binaries are included in the pinned official image. Named volume persistence and a no-drop recovery procedure are documented in `README.md`; perform the native drill before deployment.
- **Wav2Lip:** deliberately excluded from production Docker image and `AVATAR_MODE=static` is fixed in Compose. Local Wav2Lip requirements pin Torch 1.1, torchvision 0.3, NumPy 1.17, OpenCV 4.1, librosa 0.7 and Numba 0.48, which do not form a supported CPython 3.11 ARM64 wheel set. The local inference script can select CPU when CUDA is absent and the wrapper hides CUDA for CPU mode, but that alone does not validate this legacy stack/checkpoint on A1. Wav2Lip stays unavailable in production until dependencies are separately modernized, ARM64 checkpoint loading is tested and a 10-second CPU benchmark is measured.

The Next 14.2.31 package lock is tracked and contains ARM64 optional packages for Next SWC and esbuild. `npm ci` and `next build` run inside the pinned Node ARM64 build stage. A successful Windows frontend build is not proof of the Linux ARM64 native package path.

## Repeatable ARM64 procedure

On a Linux ARM64 builder (recommended) or Buildx/QEMU-enabled host with at least 8 GB free build memory and ~15 GB free disk:

1. Check source state and ensure `.local-secrets`, env files, SSH keys and model weights remain absent from the Docker context. Do not run a full Compose config that prints interpolated secrets.
2. Re-run `python deployment/audit_arm64.py` and `python deployment/audit_arm64.py --lock backend/requirements.cpu-build.lock`; compare package counts and lock SHA-256 values with the checked-in reports.
3. Run `docker buildx imagetools inspect` for the four pinned images and verify `linux/arm64/v8`. Run `docker compose --env-file .local-secrets/runtime.env -f compose.production.yaml config --quiet` only when the ignored env file exists.
4. Run `powershell -ExecutionPolicy Bypass -File deployment/verify-arm64.ps1 -Build`. This runs Buildx Dockerfile checks and builds the backend and web images without `compose up` and without pushing. To run the smoke checks on an ARM64 builder, add `-Smoke`.
5. In the backend image, verify `pip check`, imports (`torch`, `cv2`, `manim`, `cairo`, `manimpango`, `av`, NumPy/SciPy), and `torch.version.cuda is None`. Check `ldd` for missing libraries on `cv2`, torch, Cairo/Pango and PyAV extensions.
6. Verify FFmpeg codecs and one short video/audio encode, a simple Manim scene, Pillow image operations, and a Mongo `mongod --version`/`mongodump --version` smoke test. Do not start the production stack as part of the image preflight.
7. Run the authenticated API + Mongo integration and `deployment/mongo-backup.sh` / restore test only on an isolated disposable test Compose project and fresh volume. Never restore over the production data volume.
8. Repeat runtime/performance tests on a native A1 host. QEMU confirms basic cross-platform execution but is not valid evidence for Manim/Wav2Lip speed, signal handling, `flock`, `prctl`, cgroups, memory or disk budgets.

`verify-arm64.ps1` has no `up`, `push`, or resource-creation action. Its `-Build` switch only creates local images. The present machine's Docker daemon was unavailable and memory was low, so the actual Docker build and all Linux runtime steps remain **not run**.

## Reproducibility limits

Python runtime and build artifacts are version-pinned and SHA-256 hashed. Base image index digests are pinned. The frontend uses a tracked npm lock and a digest-pinned Node image. Debian packages are currently installed by package name after `apt-get update`; Debian mirror package versions are not snapshot-pinned, so the build is repeatable at the Python/container dependency level but is not yet bit-for-bit reproducible. Capture `dpkg-query -W` after a successful ARM64 build, then pin a Debian snapshot and exact APT versions before claiming hermetic/bit-identical builds. Digest bumps should be reviewed and audited for security updates.

## Open risks

- Native ARM64 build/import/render, FFmpeg codec run and Mongo persistence/restore drill have not run.
- The `bubblewrap` renderer sandbox, `flock`, `prctl` subreaper and cgroup/process-tree cleanup need native Linux integration tests.
- Manim source build and Cairo/Pango linkage need confirmation from a clean ARM64 build.
- A1 performance for Manim, image model inference, audio generation and job throughput is not benchmarked; Wav2Lip is disabled.
- APT package versions are not yet frozen to a Debian snapshot.
- Current OCI account's final itemized estimate awaits a fresh authenticated console session after revoking the session URL returned by Chrome page listing.
- `.local-secrets` currently resides below the OneDrive workspace path. Git/Docker ignore rules and current-user ACLs do not prevent OneDrive synchronization. Keep the original SSH private key in the user's non-synced `.ssh` directory; relocate the runtime env to a private non-OneDrive path before any future transfer. `transfer-runtime.ps1` refuses runtime files under OneDrive and requires strict known-host SSH validation.

Update 2026-11-07: The backend Dockerfile now uses fixed Debian and Debian security snapshots `20261001T000000Z`. Both Release endpoints returned HTTP 200. The ARM64 build and package resolution remain untested; signature checks remain enabled, while expired snapshot metadata is accepted. The active runtime env is now `%USERPROFILE%\.ssh\ai-tutor-runtime\runtime.env`; pass that path to tooling where needed. Earlier statements about unpinned APT and the active env location are superseded.
