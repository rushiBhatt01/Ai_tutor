# CPU deployment preparation

**No OCI resource creation is authorized.** All configuration is prepared for review. Do not run `compose up`, host setup, resource creation, public binding or remote deployment until explicitly approved. Local checks below do not provision OCI.

## Layout and configuration

`compose.production.yaml` runs one Caddy/static Next.js frontend, a lightweight FastAPI API, one CPU worker and the existing MongoDB. API, worker and MongoDB have no published ports. MongoDB is authenticated on an internal network. SQLite stores only durable bounded queue metadata next to the existing file checkpoints, avoiding another Redis/database service. It is a **single-host queue** on a local Docker volume, not a shared-filesystem or multi-host service.

Four outstanding jobs maximum (including the running job), one render at a time, 30-minute total job timeout, two attempts maximum, 4 GiB combined run-directory budget and 720p30 final assembly are the initial defaults. Generation and artifact upload execute in an isolated process group; the supervisor kills that group on timeout or shutdown. OS and container limits bound CPU/RAM/processes. Queue admission and claim use SQLite write transactions; the worker additionally holds a lifetime POSIX file lock. On restart, interrupted jobs return to the queue within the attempt budget. A full or disk-constrained queue remains bounded; failed jobs require explicit retry.

The production image uses CPU Torch wheels from pinned, hashed Python 3.11.14 ARM64 runtime/build locks (`backend/requirements.cpu*.lock`), Manim/Cairo/Pango, Pillow and FFmpeg. Base image index digests are pinned. The PyPI metadata audit found ARM64/universal hashed wheels for 172/178 runtime packages; six require source builds, all recorded in `arm64_python_audit.json`. The clean ARM64 image build remains untested. No GPU runtime or generative video model is configured. Wav2Lip is **explicitly deferred**, not removed: `AVATAR_MODE=static` renders a portrait presenter with narration. The CPU image deliberately excludes Wav2Lip sources and weights; an ARM64 dependency modernization, checkpoint test and measured CPU benchmark are required before enabling it. Existing local Wav2Lip behavior is preserved.

The backend pipeline and graph implementations remain in use. Production `/videoCreate` returns HTTP 202 plus a job ID. The frontend polls `/api/jobs/{id}` and loads its authenticated video endpoint. Local development retains direct streaming. Production documentation and developer execution endpoints are disabled. Authentication protects production API routes, while `/healthz` and `/readyz` return minimal status on the internal port. Caddy additionally authenticates the site and forwards the browser's Basic credentials. Do not put credentials into frontend public build variables.

## Private configuration

The private `.local-secrets/runtime.env` was prepared at the user's request. Its generated credentials and reused Cerebras key are not tracked. For a future machine, use `.env.production.example` as a template, or generate a new private file after locally authorizing reuse of provider keys:

```powershell
python deployment/prepare_env.py --reuse-local-provider-keys
docker compose --env-file .local-secrets/runtime.env -f compose.production.yaml config --quiet
```

The helper refuses overwrite, generates distinct application/database passwords and a bcrypt proxy hash, and copies only existing configured provider keys. It does not call providers or OCI. `.local-secrets` is excluded from Git and Docker; inspect credentials directly in your local editor only when needed. Never paste runtime files into chat or run full `compose config` against real secrets; use `--quiet`.

The same password must be used for API authentication and the proxy's bcrypt hash. `MONGO_URI` uses the application database user, with URL-encoded credentials and `authSource=video_tutorials`. The Mongo initialization script applies only to a new empty volume. Do not erase an existing database or assume initialization updates existing users. Back up and review any existing database before migration.

Default `SITE_ADDRESS=localhost` and `PUBLIC_BIND_IP=127.0.0.1` allow a future SSH-tunnel preview with local-CA HTTPS. This is not publicly trusted TLS; the client must trust the local Caddy CA. Public deployment needs an approved hostname/DNS setup and `PUBLIC_BIND_IP=0.0.0.0`; Caddy can then obtain trusted HTTPS certificates. No domain has been supplied or TLS issuance verified. Never send Basic credentials over public plain HTTP.

## Storage and data protection

Named volumes preserve queue state, checkpoints/run assets, published artifacts, model cache, MongoDB and Caddy state. Local artifact storage is default. The generic adapter publishes all durable run assets under `ai-tutor/jobs/<job_id>/` and writes a SHA-256 manifest **after** successful uploads. Videos stream through the authenticated backend. No buckets, policies, public URLs or OCI resources are created by the adapter.

OCI Object Storage is disabled until its allowance, account-specific tier, request/transfer pricing and permissions are verified and separately approved. Enabling it requires `ARTIFACT_BACKEND=oci`, `OCI_STORAGE_APPROVED=true`, namespace/bucket names, and a least-privilege instance principal. No OCI SDK types escape the adapter. Database/queue metadata contains object keys, not video blobs. Existing development GridFS remains available.

Automatic destructive cleanup is intentionally not enabled. On-disk render artifacts remain available for inspection/recovery; when the 4 GiB budget is reached the worker stops claiming new jobs. A reviewed retention policy must remove only completed, confirmed-published run data. Do not delete pending/running jobs or their files to free space.

MongoDB's `/data/db` is the named `mongo_data` volume (default Compose project: `ai-tutor`). `docker compose stop/down` without `-v` preserves it. The init script creates the application user only on an empty database volume. Never use `down -v` or rerun initialization against existing data.

For a consistent standalone MongoDB backup, the helper briefly stops API and worker writers, streams `video_tutorials` to a mode-0600 compressed archive, writes a SHA-256 sidecar, and restarts the app services. The dump config is created under mode-0700 `/tmp` inside the Mongo container from its environment; the password is not placed in command arguments or logs:

```sh
bash deployment/mongo-backup.sh /secure/encrypted-backups/ai-tutor
```

Protect the backup directory and encrypt off-host copies. To validate recovery, restore to a distinct fresh Compose project name, which creates a separate Mongo volume. The restore helper checks the archive checksum and runs `mongorestore --dryRun` before importing without `--drop`:

```sh
bash deployment/mongo-restore.sh /secure/encrypted-backups/ai-tutor/video_tutorials-<timestamp>.archive.gz ai-tutor-restore-check
```

Inspect collection counts and both GridFS collections (`fs.files` and `fs.chunks`) in the isolated restored volume, then stop/remove only that explicitly named test project after review. The production stack must be quiesced for its own backup and no test restore may target its active project. No backup/restore was run because MongoDB has not been started.

The SSH private key stays on the operator's machine and is never copied to the VM. Only its public key belongs in OCI instance metadata. Runtime configuration can be sent over SSH using `deployment/transfer-runtime.ps1`; it checks file ACL, requires a non-OneDrive source, `StrictHostKeyChecking=yes`, and installs the file root-owned mode 0600 at `/etc/ai-tutor/runtime.env`. No browser automation is involved. **Current `.local-secrets` is under the OneDrive workspace path, so do not transfer it until it has been moved to a private local path outside OneDrive.** The transfer script intentionally refuses the current location.

## Validation gates

Before deployment, pass: root and targeted backend tests; frontend static build; Compose configuration validation; pinned image ARM64 manifest checks; CPU dependency resolution; Docker build and `pip check`; trusted Manim render and FFmpeg benchmark; authenticated API/queue integration with Mongo; timeout/process-tree termination and worker restart under Linux. Existing unrelated backend baseline failures are recorded in the tracker and must not be presented as passing.

Docker Desktop's local Linux engine was unavailable at discovery, and the host had about 0.5 GiB free memory. The Desktop instance started solely to check the engine was stopped again. Registry manifests, ARM64 dependency resolution and Compose parsing were checked without the engine. An ARM64 manifest and resolver success do not prove wheel installation, kernel sandbox behavior, native Cairo builds or runtime performance. If image/dependency checks fail, leave deployment blocked and record the failure.

See `OCI_ELIGIBILITY.md` for verified quota evidence, Oracle's public IPv4/VCN pricing statements and the pending fresh-console estimate review. See `ARM64_COMPATIBILITY.md` for image/dependency evidence, repeatable ARM64 build checks and unresolved runtime tests. Repository preparation does not authorize provisioning. `SECRET_INVENTORY.md` lists local secret filenames and names without values.

## Future approved operations

Commands below are a runbook only; none has been executed against OCI. Run on the approved host with a protected runtime env file and the same project directory/Compose project name.

```sh
# Build first; inspect build result before starting services.
docker compose --env-file /etc/ai-tutor/runtime.env -f compose.production.yaml build
# Start only after resource, host, networking and application approval.
docker compose --env-file /etc/ai-tutor/runtime.env -f compose.production.yaml up -d
docker compose --env-file /etc/ai-tutor/runtime.env -f compose.production.yaml ps
# Internal readiness check, without credentials in command arguments.
docker compose --env-file /etc/ai-tutor/runtime.env -f compose.production.yaml exec -T api python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/readyz').status)"
# Stop preserves named volumes; never append --volumes or use down -v.
docker compose --env-file /etc/ai-tutor/runtime.env -f compose.production.yaml stop
docker compose --env-file /etc/ai-tutor/runtime.env -f compose.production.yaml start
```

For an existing host, quiesce submissions and stop API/worker before a backup. Export MongoDB with `mongodump` using its container environment (never print the URI/password), then archive the state/runs/artifacts/model-cache volumes and Caddy data to an access-controlled location. For a live SQLite-only queue backup use `JobStore.backup(path)`; copying only `jobs.sqlite3` while WAL writes are active is unsafe. Verify checksums and perform restore into **fresh** volumes with services stopped. Restore Mongo with `mongorestore`, then queue/checkpoints/artifacts with ownership UID 10001, before starting services. A real backup/restore drill remains a deployment acceptance gate.

For rollback, stop services, restore the reviewed prior image tags/configuration and matching backed-up data into fresh volumes. Preserve original volumes until verification succeeds. Moving to another provider needs Docker/Compose, the private runtime configuration, exported volumes and storage-adapter configuration. No OCI SDK is required for local filesystem storage; download OCI objects before switching backends. Do not treat a backup copy of private keys as permission to publish them.
