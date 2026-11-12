# CPU-only deployment discovery inventory

Updated: 2026-11-07. Branch: `wave2lip-integration`.
Implementation tracker: `Oracle_Cloud_Deployment_Checklist.md`.

## Repository baseline

The working tree contains substantial pre-existing staged, unstaged and untracked changes. No reset, cleanup or commit was performed. Root tests: `python -m pytest tests -q` -> **123 passed in 6.25 seconds** on local Windows/Python 3.10. Backend baseline: `python -m pytest backend/tests -q --disable-warnings --tb=short` -> **7 failed, 96 passed, 2 warnings in 842.39 seconds**. These results do not establish Linux ARM64 compatibility.

Backend failures: three Manim tests (slide/Pillow expectation, generated template representation, failed scene fixture), three semantic image tests (two removed `Fetcher` mock targets and candidate manifest expectation), and one storyboard test (legacy Gemini mock does not intercept current Cerebras provider). Output confirms a real provider response in the last test. Future reruns must isolate actual provider calls first. Docker CLI exists but its Linux daemon is unavailable (`dockerDesktopLinuxEngine` pipe missing); container checks are blocked locally.

## Component inventory

| Component | Current implementation | Dependencies / environment variable names | Persistence | Deployment action / unresolved risk |
| --- | --- | --- | --- | --- |
| API | `backend/main.py`, FastAPI/Uvicorn; `/videoCreate` awaits generation | Python, `ENVIRONMENT`, `DEV_API_TOKEN` | Delegates to pipeline | Add health/readiness, startup validation, bounded asynchronous jobs and production authentication. Existing basic credentials are embedded in frontend/backend; developer token has a default. Do not expose current configuration publicly. |
| Frontend | Next.js/React in `frontend/topic2explanation` | Node/npm; version ranges in package manifest | Browser history and cached demo assets | Production build and same-origin proxy required. Generation currently targets `http://127.0.0.1:8000`; backend status is static. |
| Script/storyboard | `functions/langgraph_pipeline.py`, provider fallback and validated scene specifications | LangGraph/LangChain; `CEREBRAS_API_KEY`, `CEREBRAS_MODEL`, `GEMINI_API_KEY` / `GOOGLE_API_KEY`; legacy Cohere integration | Run artifacts, storyboard JSON | Preserve existing graphs and provider fallback. Verify existing API credentials privately and provider usage permissions; do not add paid providers. |
| Job/checkpoint state | `functions/checkpoint_manager.py`: UUID run IDs, timestamps, stages/chunks, retry/error state, JSON file replacement | Python filesystem | `backend/runs/<run_id>/checkpoint.json`, event logs and artifacts | Reuse state model. Existing boolean JSON execution lock is not an atomic multi-process queue or restart recovery mechanism. Validate user-supplied run IDs and isolate durable job ownership. |
| CPU rendering | Manim fixed templates, Pillow fallback, visual graph and acceptance checks | Manim, Cairo/Pango, FFmpeg; `VISUAL_RENDER_WORKERS`, `MANIM_PYTHON_PATH` | Run scene artifacts | POSIX resource launcher exists; verify sandbox support on target kernel/container. Current worker default is 2; target one heavy lesson job and bounded scene work. ARM64 rendering remains unmeasured. |
| Image retrieval | Configurable image provider broker and semantic relevance checks | `IMAGE_PROVIDERS`, `PIXABAY_API_KEY`, `PEXELS_API_KEY`, provider-specific access keys, `IMAGE_SEARCH_ENABLED`, relevance/size/retry settings | Images, manifests, optional `IMAGE_CACHE_DIR` | Preserve existing relevance/attribution checks; verify allowed caching and fallback with actual configured providers. Semantic model download size and ARM64 CPU memory remain unmeasured. |
| Audio | Edge TTS and local audio processing | `edge-tts`, librosa, soundfile, FFmpeg | Per-run audio | External connectivity required; real synthesis test exists. Measure on host; preserve bounded provider failure behavior. |
| Avatar | Wav2Lip subprocess using current Python, local portraits and model checkpoints | Torch, torchvision, OpenCV, Wav2Lip weights; explicit `cpu_mode` | Character assets/checkpoints, run avatar clips | Existing default selects CUDA device 0. Force CPU for this deployment. ARM64 dependency compatibility and 10-second performance are unverified; keep feature conditional pending benchmark. Do not install video generation models. |
| Assembly/media | FFmpeg/MoviePy and `backend/media_store.py` | FFmpeg, MoviePy, Motor/PyMongo; `ENVIRONMENT`, `CACHE_POST_DELAY` | Local final assets and MongoDB GridFS | Existing media storage is async GridFS, not a generic object adapter. Introduce adapters while preserving existing call contracts; avoid duplicated databases. |
| Database | `backend/db.py`, lazy Motor client, MongoDB cache/GridFS | `MONGO_URI` | Compose `mongo_data` volume | Reuse MongoDB; PostgreSQL is not required by current implementation. Verify ARM64 MongoDB image and backup/restore before changes. Database URI parsing and exception logging need production review. |
| Containers | Existing development Compose, Python 3.10 slim backend, MongoDB 6.0 | Docker/Compose | Bind mounts plus Mongo volume | Development frontend command/reload, published database port and broad build context are unsuitable for production. Add separate reviewed production configuration, pinned supported images, non-root services and private networking. No Docker daemon/ARM64 build verified yet. |

## Current request-to-video flow

Frontend cache lookup -> `/videoCreate` -> local cache or run initialization -> LangGraph script/storyboard -> TTS/images -> parallel avatar and visual graph -> FFmpeg assembly -> local/cache/GridFS result -> HTTP video stream. Recovery endpoints read checkpoint and DAG integrity state before resuming. Heavy generation currently remains tied to an HTTP request.

## Tenancy discovery and proposed footprint

Manual sign-in completed and confirmed by user. Home region verified from the console region menu: **India South (Hyderabad), `ap-hyderabad-1`**; only one subscribed region. Account banner states **Free Tier account / Free Trial**. No OCI resources have been created or changed.

Root compartment list pages show no instances, VCNs, boot volumes, block volumes or buckets. Object Storage reports approximately 0 bytes combined usage and displays a home-region free storage notice. These checks are not exhaustive across all compartments: compartment picker remained in a compiling state. Existing databases and reserved public IPs remain unchecked. The read-only Hyderabad Block Volume regional limit explicitly shows free-tier storage 200 GB total, 0 used, 200 remaining. See `deployment/OCI_ELIGIBILITY.md` for limits and billing caveats.

A1 regional service limits show 16 OCPUs and 96 GB memory with usage 0. AD limits are dynamic. These service limits must not be interpreted as the free allowance. Shape selector marks `VM.Standard.A1.Flex` Always Free eligible; current Oracle documentation gives a monthly allowance of 1,500 OCPU hours and 9,000 GB hours, equivalent to 2 OCPUs/12 GB. Account-wide consumption and host capacity have not been verified by launching an instance.

Unsubmitted console draft: `ai-tutor-cpu`, A1 Flex, **2 OCPUs / 12 GB**, **Canonical Ubuntu 24.04 Minimal aarch64**, build **2026.10.27-0**, home-region AD 1. User-requested checks reached final Review. Storage page explicitly displays **default boot volume size 46.6 GB**; custom size/performance switch is off, no additional block volumes are attached, customer-managed encryption key is off and in-transit encryption is on. No enlargement or performance upgrade was selected. Preserve the observed size rather than reporting an unverified exact 50 GB.

To reach Review, selected a new VCN/subnet within the unsubmitted draft only. No network was created. Final review shows Public IPv4 **No** and SSH keys **-**: secure SSH configuration and approved networking remain incomplete. Optional agent defaults include Custom Logs Monitoring and Cloud Guard Workload Protection enabled; these require cost/scope review before launch, and do not establish that any paid service has actually been enabled.

Subsequently, at the user's explicit request, downloaded the draft's SSH private/public pair and moved it out of Downloads to `C:\Users\Rushi\.ssh\oci-ai-tutor-20261107-151654\` (outside repository and OneDrive). Filenames: `ssh-key-2026-11-07.key` and `ssh-key-2026-11-07.key.pub`. Cryptographically verified that the public key matches the private key; restricted both ACLs to the current Windows user. Key contents were never printed or stored in project files. Downloading keys does not establish that a VM was launched or that SSH access works; verify the matching public key is configured before eventual launch.

The last read-only Estimate drawer showed **Boot volume $2.76/month; Estimated total $2.76/month**, and says tier unit pricing is not reflected. The selected subnet/public IPv4 were not configured in that draft, so it is not the requested final network itemization. Oracle's official VCN guide says public IPv4 addresses are not charged, and the VCN FAQ says creating/using a VCN is free; see `deployment/OCI_ELIGIBILITY.md`. No resource was created, no paid usage authorized, and no account upgrade accepted.

Latest user clarification: treat the $2.76 estimator as a standard estimate, not proof of billing, and qualify the final resources against the free allowance. The Always Free docs and Hyderabad volume limit support the proposed home-region A1/default boot volume. A final itemized estimate is still pending: the subnet/public IPv4 were absent in the old estimate. Chrome's page-list response unexpectedly contained the signed-in console URL with session credentials; no further OCI page content was inspected. User should revoke that session and sign in manually again before any read-only estimate review. The VM wizard's disabled public-IP control requires a subnet first; do not bypass it.

Provisional footprint, not approved for deployment: one eligible ARM64 Ubuntu A1 VM, 2 OCPUs/12 GB RAM; default boot volume 46.6 GB; one reverse proxy, frontend, API, one bounded CPU worker and MongoDB on the same VM. Object Storage remains disabled. No PostgreSQL, NAT/load balancer, GPU or extra host is proposed. Oracle's published statements confirm public IPs and VCN use have no charge; the last account-specific final estimate is still pending safe console reauthentication.

## Prepared repository implementation

- `compose.production.yaml`, `backend/Dockerfile.cpu`, and `deployment/Dockerfile.web` describe API, one bounded CPU worker, authenticated MongoDB, static Next.js/Caddy, internal networks and persistent volumes. No container was started.
- API supports production auth, secret-safe settings, health/readiness, durable SQLite jobs, idempotency, bounded retries and authenticated video delivery. Worker runs the existing pipeline in a bounded isolated subprocess and retains checkpoints/artifacts.
- Local filesystem is default artifact storage. The injected OCI adapter is opt-in and explicitly guarded; no bucket or SDK network calls occurred.
- Wav2Lip is excluded from production; its legacy requirements are not a supported CPython3.11 ARM64 set. Static Pillow/FFmpeg presenter mode is configured. Local Wav2Lip behavior is preserved.
- `deployment/ARM64_COMPATIBILITY.md` and PyPI audit JSON files record the all-image/dependency compatibility audit. Hashed Python ARM64 build/runtime locks and index digests are prepared, but native image build, sandbox/runtime behavior and performance remain untested because Docker Desktop was unavailable and host memory was low.
- MongoDB named-volume persistence and credential-safe `mongodump`/fresh-volume restore scripts are prepared; runtime backup/restore is not tested until a disposable ARM64 Mongo service is available.
- `deployment/transfer-runtime.ps1` uses SSH with host-key checking and installs runtime env root-only. It refuses the current OneDrive-synced `.local-secrets` path; move the env file first. The private SSH key remains on the operator's machine, with only its public half used by OCI.
- User-authorized project secret copies are ACL-restricted, excluded from Git/Docker. Names-only record: `deployment/SECRET_INVENTORY.md`; no values are in tracked files or output.
- See `deployment/README.md` for operations, backup/restore and validation gates.

## Official documentation check

Checked 2026-11-07: [Oracle Always Free resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm).

The live page currently lists A1 allowance as 1,500 OCPU-hours and 9,000 GB-hours monthly (2 OCPUs/12 GB), combined boot/block storage of 200 GB in the home region, and Object Storage request/storage allowances that vary with account state. Context7 returned an older conflicting 3,000/18,000-hour A1 excerpt. Use the live official page and actual tenancy console; do not provision against the older excerpt. Capacity and eligibility remain unverified.

## Resume and approval boundary

The user selected repository preparation only. Do not create OCI resources, expose the service, or upgrade the account. Before a separate future deployment approval, recheck all-compartment usage, public-IP and gateway pricing, optional Oracle agent services, capacity and the itemized estimate. Credential entry remains manual; do not inspect session secrets.
