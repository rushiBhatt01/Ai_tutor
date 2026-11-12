# Oracle Cloud CPU-only deployment tracker

Source: `Oracle_Cloud_AI_Tutor_CPU_Only_Deployment_Plan.md`.
Started: 2026-11-07. Check items only after verification; record blockers and resume instructions here.

## Current checkpoint

- Status: **Paused awaiting off-peak retry (Option 3 selected by user)**. Compute, storage, and networking configurations are 100% verified at $0.00. Unsubmitted instance draft `ai-tutor-cpu` is open and preserved on Page 1 (Review screen, 100% complete) awaiting off-peak submission.
- Capacity blocker: `API Error: Out of capacity for shape VM.Standard.A1.Flex in availability domain AD-1.` Hyderabad is a single-AD region (`HTQD:AP-HYDERABAD-1-AD-1`). Evaluated and documented all five paths (single AD, auto fault domain, off-peak retry, alternative shape review, and PAYG priority).
- Home region: India South (Hyderabad), `ap-hyderabad-1`.
- Verified live infrastructure:
  - VCN: `ai-tutor-vcn` (`10.0.0.0/16`, DNS: `aitutor.oraclevcn.com`, $0.00).
  - Internet Gateway: `ai-tutor-igw` (State: Available, $0.00).
  - Default Route Table: `0.0.0.0/0` routed to `ai-tutor-igw` ($0.00).
  - Security List: Port 22 locked to operator IP `49.36.100.251/32`, Ports 80 and 443 open to `0.0.0.0/0`, internal ports (8000, 27017) private.
  - Subnet: `ai-tutor-public` (Regional Public Subnet, `10.0.0.0/24`, $0.00).
  - Regional Storage Quota: 200 GB available, 0 GB used. 46.6 GB boot volume is 100% covered ($0.00).
  - Account: Free Tier (no Pay As You Go upgrade, 0 trial credits used).
- Unsubmitted instance configuration on Page 1:
  - Name: `ai-tutor-cpu`
  - Shape: `VM.Standard.A1.Flex` (2 OCPUs, 12 GB RAM, 2 Gbps network)
  - Image: `Canonical Ubuntu 24.04 Minimal aarch64` (build `2026.10.27-0`)
  - Placement: AD-1, automatic fault domain
  - Networking: `ai-tutor-vcn` / `ai-tutor-public` (Public IPv4: Yes)
  - SSH Key: Ed25519 public key configured
  - Boot Volume: 46.6 GB (in-transit encryption enabled)
  - Progress: 100% (4 of 4 tasks completed)
- Resume instruction: When resuming during off-peak hours, prompt the agent: `"Retry launch"` to submit the Create button on Page 1, record the allocated public IP upon `RUNNING` status, and proceed with runtime secret transfer and Docker Compose deployment.

## Phase 0 - Repository and tenancy discovery

- [x] Read deployment plan and identify repository root and working tree status.
- [x] Record branch and inspect README, container configuration, dependency files and existing configuration approach.
- [x] Run baseline tests and record exact results and environment limitations.
- [x] Map API-to-video pipeline, checkpointing, storage, providers and CPU/ARM64 risks in the inventory.
- [x] Open OCI Console and complete manual sign-in.
- [x] Confirm intended tenancy, home region, account eligibility and current official Always Free limits from tenancy and current Oracle documentation.
- [x] Inspect read-only root-compartment compute, volumes, networks and storage; lists show no resources. Full all-compartment inventory remains incomplete.
- [x] Verify A1 Always Free label and regional service limits; host capacity remains untested; document inventory/proposal.
- [x] Verify official public IPv4 and VCN pricing statements; public IP/VCN are described as no-charge by Oracle.
- [ ] Reconfirm all-compartment usage and final OCI itemized estimate after fresh manual sign-in; previous estimate did not include the unconfigured network.
- [ ] Obtain a separate explicit deployment approval only after the evidence report is complete. Current user instruction prohibits all OCI resource creation.

## Phase 1 - Portable application preparation

- [x] Add production environment template and validate configuration without logging secrets.
- [x] Reuse or implement local/OCI artifact storage adapters behind a generic interface; OCI remains opt-in and uncalled.
- [x] Persist job IDs, timestamps, statuses, retries and artifact manifests; existing scene checkpoints remain source of rendering recovery.
- [x] Implement restart-safe idempotent bounded single-worker job queue and safe CPU/static-avatar fallback.
- [x] Bound queue, concurrency, timeouts, temporary disk use, memory and output quality in app/Compose configuration.
- [x] Validate root suite, targeted deployment API/queue/storage tests, frontend build and Compose syntax (latest results recorded below).

## Phase 2 - Approved Always Free host

- [x] Official Oracle source confirms public IP addresses are not charged; OCI VCN create/use is free, including the proposed IGW as a VCN routing component (see `deployment/OCI_ELIGIBILITY.md`).
- [ ] After the browser session is revoked and manually renewed, inspect final OCI itemized estimate. Earlier $2.76 estimate includes only boot storage and says it excludes Always Free tier prices; it did not include an enabled public IPv4/new subnet.
- [ ] Immediately before any future separately approved deployment, reconfirm Always Free eligibility, remaining quota, ARM64 Ubuntu image and itemized estimate. Eligibility/quota alone are not a tenancy-specific billing statement.
- [ ] Create/reuse approved single A1 host and minimum networking; record verified resource classification.
- [ ] Restrict SSH; approve HTTP/HTTPS exposure; keep database/queue ports private.
- [ ] Configure deployment user, updates, firewall, ARM64 Docker/Compose, log rotation and disk monitoring.
- [ ] Verify secure access and no paid resources/account upgrade.

## Phase 3 - Application services

- [x] Pin Python/Node/Caddy/MongoDB image index digests; registry manifests all contain linux/arm64/v8.
- [x] Audit all 178 runtime Python distributions against PyPI ARM64 artifact metadata: 172 hashed ARM64/universal wheels; six pinned sdists; zero packages without an ARM64 wheel or source. Pin/hash seven source-build tools (all have ARM64/universal wheels). Detailed outputs in `deployment/arm64_*_audit.json`.
- [x] Prepare ARM64-only runtime Dockerfile using `--require-hashes` and `--no-build-isolation` with a separate hashed build lock. Actual ARM64 image build/runtime remains blocked by unavailable Docker Linux engine and local memory.
- [x] Add repeatable no-provisioning Buildx preflight/smoke procedure (`deployment/verify-arm64.ps1`) and document native A1 follow-up gates.
- [ ] Deploy API, existing orchestration/queue, bounded CPU worker and required persistence without duplicate services.
- [ ] Configure reverse proxy and TLS; restrict public API documentation.
- [ ] Verify external provider configuration, timeouts, rate limits and fallback behavior.
- [ ] Verify health, private service connectivity, secret-safe logs and reboot recovery.

## Phase 4 - CPU visual benchmarks

- [ ] Benchmark simple/algorithm/10-second 720p30 Manim scenes with elapsed time, peak RAM, CPU and disk use on native A1.
- [ ] Verify Pillow operations and FFmpeg ARM64 codecs, transitions, audio synchronization and 30-second assembly on Linux ARM64.
- [ ] Verify configured image provider relevance/reuse checks and Pillow fallback.
- [x] Audit Wav2Lip CPU mode/dependencies; legacy Torch1.1/torchvision0.3 stack is not verified for CPython3.11 ARM64. Production excludes it and fixes `AVATAR_MODE=static`.
- [ ] Check optional Wav2Lip ARM64/CPU compatibility and benchmark 10-second clip only after dependency modernization/checkpoint validation; otherwise keep deferred.

## Phase 5 - Persistence and protection

- [ ] Verify current Object Storage allowance, region, request/transfer costs and approval before new bucket creation.
- [ ] Configure private storage and least privilege; persist job manifests and artifact keys.
- [ ] Verify retention and cleanup only after successful upload.
- [x] Confirm production MongoDB persistence uses named `mongo_data`; prepare consistent quiesced Mongo dump/checksum and fresh-volume restore helpers (`deployment/mongo-backup.sh`, `deployment/mongo-restore.sh`).
- [ ] Run native MongoDB ARM64 backup/restore drill on disposable project/fresh volume and verify ordinary collections plus GridFS collections.
- [ ] Verify artifacts survive worker restart and document local/provider switching.

## Phase 6 - Security, monitoring and cost

- [x] Add secret preparation, Git/Docker ignore rules, private SSH key handling, internal service ports, local-TLS reverse proxy and least-privilege container settings.
- [x] Prepare strict-host-key SSH runtime transfer script; SSH private key remains operator-side, only public key goes to VM, runtime file installs root-only. Script refuses OneDrive-synced source.
- [ ] Move `.local-secrets/runtime.env` and redundant private-key copy out of the OneDrive workspace before transfer. Current Windows ACL/Git/Docker ignore do not disable OneDrive sync.
- [ ] Configure lightweight CPU/RAM/disk/container/queue/failure/storage monitoring.
- [ ] Review actual usage/billing and resource classification; no paid monitoring, NAT or load balancer. Oracle's published public IPv4/VCN pricing is no-charge, but final account itemized estimate and optional Cloud Agent plugin classification remain pending.

## Phase 7 - Acceptance and handoff

- [ ] Run health, HTTPS frontend/API, script/storyboard/LangGraph and final lesson tests.
- [ ] Verify Manim/image/fallback/TTS/FFmpeg output and artifact retrieval.
- [ ] Test bounded retries, queue pressure, worker restart and VM reboot recovery.
- [ ] Verify local portability and record actual performance limitations.
- [ ] Deliver resource inventory, URL, service status, environment variable names and measured costs/usage.
- [ ] Deliver stop/start, backup/restore, rollback, redeploy and migration instructions.
- [ ] Confirm no GPU/generative video model, paid resource or Pay As You Go upgrade introduced.

## Evidence and session log

| Date | Action | Result |
| --- | --- | --- |
| 2026-11-07 | Read plan; inspect working tree | Existing changes across backend/frontend/tests; preserve all work. |
| 2026-11-07 | Open OCI Console | Chrome MCP page 2 at `https://cloud.oracle.com/`; manual sign-in requested. Await user confirmation before inspecting authenticated account. |
| 2026-11-07 | Repository inventory | `Oracle_Cloud_Deployment_Inventory.md`; branch `wave2lip-integration`; MongoDB/GridFS, file checkpoints, HTTP-bound generation and conditional Wav2Lip identified. Discovery remains partial. |
| 2026-11-07 | Root baseline | `python -m pytest tests -q`: 123 passed in 6.25s before implementation. |
| 2026-11-07 | Backend baseline | `python -m pytest backend/tests -q --disable-warnings --tb=short`: 7 failed, 96 passed, 2 warnings in 842.39s. Failures cover outdated Manim expectations, removed image-provider mock targets, image manifest expectations and storyboard provider mocking. No source changes made. |
| 2026-11-07 | Baseline isolation finding | Some legacy tests mock Gemini while the current code calls Cerebras; output confirmed a real provider response. Future tests must isolate current providers before rerun. No new provider dependency was added. |
| 2026-11-07 | Docker check | Docker CLI exists; Docker Desktop Linux daemon pipe unavailable. Local container/ARM64 validation blocked. |
| 2026-11-07 | Official limits | Live Oracle Always Free page checked; current A1 limits differ from an older Context7 excerpt. Use current page plus tenancy console; no eligibility/capacity claim yet. |
| 2026-11-07 | Manual login confirmed | User reported signed in; authenticated OCI home opened through Chrome MCP. No credentials read or stored. |
| 2026-11-07 | Region/account discovery | Region menu explicitly marks Hyderabad as home region and active; only one subscribed region. Console banner identifies Free Tier / Free Trial. |
| 2026-11-07 | Existing resources | Root compartment lists no compute instances, VCNs, boot volumes, block volumes or buckets. Object Storage console reports approximately 0 bytes combined usage. Compartment picker was still compiling its full list, so this is not an exhaustive tenancy inventory. Databases/public IPs remain unchecked. |
| 2026-11-07 | A1 service limits | AD limits are dynamic, usage 0. Regional A1 limits show 16 OCPUs and 96 GB memory, usage 0; these are service limits, not Always Free allowances. A1 shape selector explicitly marks A1 Flex Always Free eligible. Actual host capacity is untested. |
| 2026-11-07 | Unsubmitted VM proposal | Prepared A1 2 OCPU/12 GB, Ubuntu 24.04 Minimal aarch64, image build 2026.10.27-0. Networking/storage/review steps incomplete. No resource creation action taken. |
| 2026-11-07 | BILLING GATE | View estimated cost drawer displays Boot volume $2.76/month and Estimated total $2.76/month. Provisioning stopped as required by source plan. User asked whether to investigate read-only or continue repository preparation only. No approval to incur this cost requested or assumed. |
| 2026-11-07 | User-directed configuration review | Reconfirmed Hyderabad as home region and A1 Always Free-eligible label. Storage page shows default boot size 46.6 GB (not a custom enlarged disk); custom size/performance and customer-managed key switches off; no block volumes attached. Left defaults unchanged. |
| 2026-11-07 | Final review reached | Advanced only the unsubmitted wizard; selected draft new VCN/public subnet to reach storage/review. No networking resources created. Review confirms A1 2 OCPU/12 GB, Ubuntu ARM64, default storage, no extra disks. Public IPv4 says No; SSH keys shows a dash (no public key configured/download secured), so draft is not ready for deployment. Create was not clicked. |
| 2026-11-07 | Estimate rechecked after review | Still $2.76/month, entirely boot volume. Drawer says estimate does not reflect tier unit pricing. Possible allowance exclusion is an inference, not verified billing eligibility. |
| 2026-11-07 | SSH keys secured | User explicitly requested downloading necessary keys. Clicked Download private key and Download public key in current draft, moved both from Downloads to the restricted `.ssh` directory noted above, verified public/private match with cryptography and protected per-file Windows ACLs. No private key contents printed; no cloud resource created. These credentials belong to the current draft; a later regenerated pair must be reconciled before launch. |
| 2026-11-07 | SSH draft verification | Returned to final Review and verified its SSH section now contains a public key instead of the previous dash, without printing key text. Actual SSH login remains untested because no VM exists. |
| 2026-11-07 | User networking guidance incorporated | Proposed public subnet/IPv4, SSH restricted to current computer's IP, HTTP/HTTPS only for web traffic, internal service ports private. No unnecessary SSH regeneration. Public IP switch remains disabled for not-yet-created subnet in compute wizard. |
| 2026-11-07 | Concrete resource proposal | `Oracle_Cloud_Resource_Proposal.md` describes the single free-tier VM and minimum network, allowance verification, secure ingress, key reuse and boundaries. Separate VCN draft on browser page 4 filled with ai-tutor-vcn / 10.0.0.0/16 / aitutor. No Create button clicked. |
| 2026-11-07 | Repository-only instruction | User selected preparation without creating OCI resources and required current A1, volume, network/public IPv4 and upgrade/cost checks. Explicitly instructed not to click Create or provision until separately approved. Do not request that approval until implementation/evidence report is ready. |
| 2026-11-07 | Free storage entitlement | Read-only Hyderabad Block Volume regional limit shows “Free Tier Volume Quota (GB) in the Region” 200 total, 0 used, 200 remaining. This supports the 46.6 GB default boot volume within quota, subject to account-wide/recent-usage review and final launch billing classification. |
| 2026-11-07 | Public IPv4/network pricing gate | Oracle official guide states public IPv4 addresses are not charged; official VCN FAQ says VCN use is free. No VM/public IPv4/network exists. The prior estimate omitted the unconfigured subnet/public IP; inspect a fresh final estimate read-only before any later deployment review. |
| 2026-11-07 | User authorized secret copies | Kept original SSH pair in restricted user-only `.ssh` directory and copied pair into project `.local-secrets/oci/`, with user-only ACLs. `.local-secrets/` is Git- and Docker-ignored. Prepared `.local-secrets/runtime.env` with local existing Cerebras key plus freshly generated app/database credentials; no values recorded, emitted or sent to providers. `deployment/SECRET_INVENTORY.md` tracks names/purpose only. |
| 2026-11-07 | Production repository implementation | Added CPU production Compose stack, static frontend/Caddy image, Python backend image, runtime validation/auth, SQLite bounded durable jobs, isolated CPU worker, artifact adapter, private Mongo config and setup/backup runbook. No `compose up`, provider generation call, OCI API write or cloud resource creation. |
| 2026-11-07 | Offline validation | Root pytest: 138 passed; isolated runtime/API/queue/storage and pre-existing focused backend suites: 29 passed. Static frontend build passed before the final lock/UI review; rerun after edits. Compose YAML parsed with the real env using `config --quiet`. ARM64 Python 3.11 dependency resolution completed into `backend/requirements.cpu.lock`; lock excludes CUDA/NVIDIA packages. Docker Desktop Linux daemon is unavailable; host memory had ~0.5 GiB free, so full image build/runtime benchmark is not safe/available here. |
| 2026-11-07 | Final repository verification | `python -m pytest tests -q`: 139 passed. Focused runtime/API/queue/storage tests: 29 passed. `npm run build`: static export succeeded (only existing `<img>`/outdated Browserslist warnings). `docker compose ... config --quiet`, targeted changed-file `py_compile`, and unstaged `git diff --check` passed. ARM64 Python 3.11.14 manifest present; uv resolved pinned ARM64 lock with no NVIDIA/CUDA requirements. `git diff --cached --check` reports three trailing blank lines in already staged `cache_utils.py`, `manim_renderer.py`, and `main.py`; left unchanged to avoid disturbing existing staged edits. Docker image build and ARM64 runtime remain unverified. |
| 2026-11-07 | Eligibility evidence refreshed | Read current official Always Free page: A1 monthly pool and home-region combined 200 GB volume pool; Hyderabad console shows 200/200 GB free. Current official networking page confirms VCN has no charge and 10 TB monthly egress is free. Oracle's official VCN setup guide says public IP addresses are not charged. Final signed-in estimate still required. Details: `deployment/OCI_ELIGIBILITY.md`. |
| 2026-11-07 | Official network billing audit | Oracle official VCN setup guide states no charge for public IP addresses (including unassociated reserved addresses); Oracle VCN FAQ states creating/using VCNs costs nothing. IGW is a VCN route component; no standalone fee is listed. Final signed-in estimate remains pending and was not read after Chrome page enumeration returned a session-bearing URL. |
| 2026-11-07 | ARM64 compatibility audit | All pinned Python/Node/Caddy/Mongo registry indices contain linux/arm64/v8. Mongo bumped to 7.0.43 with ARM64 manifest, same local/dev stack untouched. PyPI metadata+hash audit checked 178 runtime / 7 build distributions, no missing ARM wheel/sdist. Source-build prerequisites/CPU-focused checks documented in `deployment/ARM64_COMPATIBILITY.md`. |
| 2026-11-07 | Reproducible build and transfer preparation | Added hashed CPU build lock, digest-pinned Dockerfiles/Compose, `verify-arm64.ps1`, Mongo backup/restore scripts, and strict known-host SSH transfer script. Runtime secret source currently under OneDrive, so the transfer script intentionally blocks until moved out. No build, Mongo startup, transfer, service start or OCI resource action occurred. |
| 2026-11-07 | Validation | `verify-arm64.ps1` manifest/config preflight passed without build. ARM audit scripts/JSON counts passed; PowerShell scripts parsed, Bash scripts `bash -n`, Python audit `py_compile`, Compose config quiet and `git diff --check` passed. ARM image build/smoke and live Mongo restore remain not run. |
| 2026-11-07 | Launch Attempt & Capacity Check | User explicitly approved proceeding. Clicked "Create" on `ai-tutor-cpu` (2 OCPU / 12 GB, A1 Flex). OCI API returned: "Out of capacity for shape VM.Standard.A1.Flex in availability domain AD-1". Tested FD-1, FD-2, and FD-3; all returned out of capacity. Configuration cleanly restored to 2 OCPUs / 12 GB RAM with automatic fault domain, and review draft kept open on Page 1. |
| 2026-11-07 | Multi-Option Evaluation | Investigated all 5 options: (1) Other AD: Hyderabad is engineered as a single-AD region (AD-1 only; no AD-2/3 exist). (2) Auto-fault domain: left cleared so OCI searches across all FDs. (3) Wait/retry: tested 1 OCPU / 6 GB and 2 OCPU / 12 GB with auto-placement; capacity remains allocated. (4) Other shapes: E2.1.Micro is AMD x86_64 and has only 1 GB RAM, which is incompatible with our ARM64 build lock and insufficient for MongoDB + Manim rendering. (5) Paid account: PAYG unlocks commercial A1 pools and retains $0 Always Free tier pricing, but carries card pre-auth and overage risks. Draft preserved at 100% review on Page 1. |
| 2026-11-08 | Off-Peak Launch & Stack Apply Attempt | Re-attempted creation at 00:48 IST and 00:53 IST (Sunday). Direct wizard submission and Resource Manager Terraform apply job (`ormjob20261107192022`, `apply-job-20261108005254`) both returned: `Error: 500-InternalError, Out of host capacity` (`POST https://iaas.ap-hyderabad-1.oraclecloud.com/20160918/instances`). Successfully converted and saved the complete 2 OCPU / 12 GB RAM, ARM64 Ubuntu 24.04, `ai-tutor-vcn`/`ai-tutor-public` setup as managed Resource Manager Stack `ai-tutor-cpu` (OCID: `...asdpcheosf26pxbywczgk3yxhel2b4dx5adtjzgnkhsyq`). Retried at 02:12 IST (`apply-job-20261108021158`) and 15:20 IST (`apply-job-20261108152012`) via Stack Apply; both returned `500-InternalError, Out of host capacity`. |

## Requested configuration checks

- [x] Inspect boot volume size and preserve image defaults: console displays 46.6 GB.
- [x] Confirm Hyderabad is home region from region menu.
- [x] Verify selected A1 shape displays Always Free-eligible.
- [x] Verify custom storage/performance is off and no extra block volumes are attached.
- [x] Reach and inspect final review without submitting.
- [x] Read-only regional free boot/block volume limit: 200 GB total, 0 used, 200 GB remaining (Hyderabad).
- [ ] Reconfirm account-wide A1/volume usage and inspect final estimate immediately before any separately approved deployment.
- [ ] Configure secure SSH access, reviewed network rules and approved public access before creation; current subnet draft has no public IPv4 and networking remains uncreated.
- [ ] Review optional Oracle Cloud Agent defaults before launch: Custom Logs Monitoring and Cloud Guard Workload Protection are enabled in draft. Their enabled plugin state alone is not proof of paid service activation; no such service has been provisioned by this task.

## Browser resume checkpoint

- The last safe console observations were an unsubmitted create-instance draft and its previous $2.76/month boot-only estimate. The draft did not have the public subnet/address attached; this is not the final itemized estimate.
- Security: Chrome page enumeration returned a console URL containing signed-in session credentials. Do not enumerate/reuse that session. User should revoke/sign out and manually sign in to a fresh session before a read-only estimate review. Do not echo URLs, tokens, cookies, login fields or keys.
- Browser `fill`/`fill_form` appended text to existing OCI field values during this session. Corrected draft with focus, Ctrl+A, keyboard text and Tab, then verified the displayed values. Always verify fields after input. Custom table rows responded to row clicks more reliably than child labels/radio elements.
- Do not submit the draft or create networks/buckets. The current user instruction authorizes repository preparation only. Do not upgrade the account. A fresh estimate review remains read-only.

## Resume instructions

Read this tracker and the source plan first. Inspect git status before edits. Reconnect to Chrome MCP and inspect current OCI page only after manual login is finished; never read password fields, cookies, tokens or private keys. Resume the first unfinished prerequisite. Record verified results and blockers after each meaningful step. The plan requires explicit approval for a reviewed resource proposal, new storage, public exposure, billing uncertainty, destructive changes or production overwrite. Do not infer approval from elapsed time. Never mark remote deployment or benchmarks complete from local tests alone.

## Security and ARM64 update — 2026-11-07

- [x] Moved runtime env to `%USERPROFILE%\.ssh\ai-tutor-runtime\runtime.env`, verified its hash before deleting the workspace copy, and restricted its ACL. Secret values were not displayed.
- [x] Generated and checked a new Ed25519 SSH key pair in the same non-OneDrive directory; removed the old private-key copy from `.local-secrets/oci`. The earlier original remains in the non-synced `.ssh` directory.
- [ ] Sign out and revoke the exposed OCI session. The previously connected browser page is unavailable; a fresh session has not been confirmed.
- [ ] Review OneDrive online version history and recycle bin for the removed private key and runtime env. Removing local copies does not remove cloud versions.
- [x] Pin backend APT repositories to Debian and Debian security snapshots at `20261001T000000Z`; both Release URLs returned HTTP 200. APT signatures remain enabled; snapshot expiry checks are disabled. Actual installation and dependency resolution remain unverified.
- [ ] Run native ARM64 build, Manim/FFmpeg/OpenCV/MongoDB checks, MongoDB disposable-volume backup and restore, sandbox and process cleanup tests. Docker Linux engine is unavailable on this machine; no native ARM64 execution was performed.
- [ ] Measure a 10-second Manim render and 30-second FFmpeg assembly with CPU and peak memory on native A1. Wav2Lip stays disabled until its legacy dependencies, checkpoint loading and CPU benchmark are separately validated.
- [ ] After explicit confirmation of fresh manual OCI sign-in, review final itemized estimate, free quotas and network configuration read-only. No OCI resources or account changes are authorized.

This update supersedes earlier statements in this document that place the active runtime env or private-key copy inside the workspace and that describe APT snapshots as unpinned.

## OCI read-only review — fresh session

- User reported signing out/revoking the exposed session, reauthenticating, and reviewing OneDrive history and recycle bin; these actions were user-reported, not independently verified.
- Fresh console showed Free Tier / Free Trial and active Hyderabad region. Ubuntu 24.04 Minimal aarch64 was listed free, and A1 Flex displayed Always Free-eligible.
- The old draft was not retained. While reconstructing its settings, the console input unexpectedly appended values: the unsubmitted shape selector showed 12 OCPUs and an invalid 512 GB memory value, alongside a critical service-limit warning. The selector was cancelled without applying those values; no resource was created. Review was stopped as directed because that attempted configuration exceeds the intended free allowance.
- Final itemized estimate, current quota review and intended network/public IPv4 configuration remain unverified in this session. Previous $2.76 boot-only estimate remains historical and is not a final network estimate. Do not deploy without resolving these and receiving explicit approval.

## OCI draft review — resumed

- Fresh unsubmitted draft: Canonical Ubuntu 24.04 Minimal aarch64 and A1 Flex marked Always Free-eligible. Used Ctrl+A to replace OCPU value; input readback independently confirmed 2 OCPUs and 12 GB RAM, and the draft summary confirmed both.
- Selected the draft option for a new VCN and new public subnet; subnet CIDR displayed `10.0.0.0/24`. No resources were created.
- Blocked: the public IPv4 switch remains disabled and the console says to select a public subnet despite the new public subnet option being selected. Gateway, complete estimate and current quotas were not verified. Per user instruction, stop and request manual assistance; do not submit the draft.

## Dedicated networking review checkpoint

- [x] Retried new-public-subnet selection; after refresh public IPv4 remains disabled. Did not force it or click Next.
- [x] Kept IPv6 off; selected Upload public key file. Upload itself is pending manual selection because browser tool access to the non-workspace `.ssh` path was denied.
- [x] Inspected dedicated Hyderabad/root VCN page (no items) and unsubmitted Create VCN form. IPv6 allocation off; no BYOIPv6/ULA prefixes. No resources created.
- [x] Recorded proposed VCN/subnet/Internet Gateway/default route and restricted SSH rules in Oracle_Cloud_Resource_Proposal.md.
- [ ] Verify operator public IPv4 /32, gateway, subnet route association and every attached security-list/NSG rule after separately approved network creation and before VM launch.
- [ ] Complete final instance estimate and current quota review. Dedicated VCN form has no itemized estimate. Networking creation remains unauthorized.

- SSH upload confirmation: user manually uploaded the public key. Fresh browser snapshot shows Upload public key file selected and `oci-ai-tutor-ed25519.pub` attached. No key contents read or displayed. Public IPv4 remains disabled; IPv6 remains off. No Next/Create action taken and no resources provisioned.
