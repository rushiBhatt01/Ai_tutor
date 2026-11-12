# Oracle Cloud Deployment Implementation Plan
## AI Tutor: CPU-First, GPU-Free, Provider-Portable Deployment

**Document type:** Implementation plan for an AI coding agent  
**Project:** Existing AI Tutor / AI Video Tutorial Generator  
**Target infrastructure:** Oracle Cloud Infrastructure (OCI) Always Free resources  
**Deployment approach:** Browser-based OCI Console access through Chrome MCP, with CLI/API access only where explicitly available and approved  
**Priority:** Reliable deployment, no accidental paid usage, portability beyond Oracle trial credits

---

## 1. Mission

Deploy the existing AI Tutor project to Oracle Cloud using eligible Always Free resources, while keeping the application portable so it can be moved to another cloud provider or self-hosted environment later.

The deployed system must support the existing lesson-generation workflow and CPU-based visual generation:

- FastAPI backend
- LangGraph orchestration
- Existing script-generation API integrations
- Scene/storyboard generation
- Web image retrieval and relevance checks, where already implemented or included in the approved project scope
- Manim technical animations
- Pillow image processing and fallback visuals
- FFmpeg video assembly
- Existing audio/TTS pipeline
- Existing avatar pipeline only if it is compatible with the target ARM64 environment and passes a measured performance test
- Persistent application data and generated lesson assets

**Explicit exclusion:** Do not implement, install, configure, provision, or call Wan, LTX, or any other text-to-video/image-to-video generative model. Do not provision GPU infrastructure. This deployment is CPU-only.

The agent must inspect the actual repository before making changes. Treat this document as the deployment target, not as permission to rewrite working application components.

---

## 2. Non-negotiable constraints

1. **Always Free first:** Use only resources explicitly identified as Always Free and currently eligible in the user's OCI tenancy.
2. **No Pay As You Go upgrade:** Do not upgrade the account or accept any paid-account conversion.
3. **No paid resources:** Do not create paid compute, GPU, load balancer, NAT gateway, database, storage, logging, monitoring, or networking resources.
4. **No GPU:** Do not search for, provision, or configure GPU instances.
5. **No trial-credit consumption:** Do not use the $300 trial credits as part of this deployment plan. The objective is a long-lived Always Free deployment.
6. **Approval gates:** Stop and ask the user before any action that may create a charge, upgrade the tenancy, change account billing, delete existing resources, expose a service publicly, or overwrite production data.
7. **No secrets in chat or source control:** Never print, commit, or store OCI credentials, API keys, SSH private keys, database passwords, or access tokens in logs, screenshots, repository files, or generated documentation.
8. **Least privilege:** Use the minimum OCI permissions and network exposure required.
9. **Portable architecture:** Keep cloud-specific operations behind adapters/configuration. Do not couple business logic to OCI SDKs.
10. **Backups before destructive changes:** Export or back up relevant configuration and data before migrations, replacement, or cleanup.
11. **Do not assume capacity:** Check actual Always Free availability, service limits, region restrictions, and tenancy eligibility in the OCI Console.
12. **No false success claims:** Verify each resource and deployment from OCI and from application health checks before marking a task complete.

If the OCI Console indicates a resource is not Always Free, shows a price, requires a paid upgrade, or displays ambiguous billing terms, stop and ask the user.

---

## 3. Target architecture

### 3.1 Always Free application host

Use an eligible OCI Ampere A1 Flex VM, if available in the user's home region and tenancy:

- Architecture: ARM64 / aarch64
- Allocation target: up to 2 OCPUs and 12 GB RAM, subject to current Always Free entitlement and availability
- Operating system: a currently supported Ubuntu ARM64 image
- Persistent boot volume: remain within the Always Free storage allowance
- Public access: expose only required HTTP/HTTPS endpoints
- SSH: restrict to the user's IP where practical; do not expose database or Redis ports

Do not create a second VM unless the user explicitly approves and it is verified as Always Free.

### 3.2 Services on the VM

Start with a single-host deployment to conserve resources:

| Service | Role | Deployment |
|---|---|---|
| Nginx or Caddy | Reverse proxy and TLS termination | Docker or host package |
| FastAPI | Application API | Docker |
| LangGraph | Lesson workflow orchestration | Within backend initially, or separate process if repository requires it |
| Redis | Background job queue / coordination | Private Docker service |
| PostgreSQL | Application persistence | Existing managed/external DB if already configured; otherwise local container only after resource and backup review |
| CPU worker | Manim, Pillow, FFmpeg, image processing | Separate worker process/container |
| Scheduler | Retry, cleanup, health and job maintenance | Lightweight process or existing queue scheduler |
| OCI Object Storage | Persistent generated assets | OCI adapter behind generic storage interface |

Do not deploy multiple copies of the same service. Inspect the current project and reuse its existing job system, database, and checkpointing mechanisms if they are already functional.

### 3.3 CPU-only visual pipeline

Supported visual engines:

- Manim for technical and mathematical animations
- Pillow for static layouts, labels, and fallback visuals
- FFmpeg for transitions, image pan/zoom, audio/video synchronization, and final assembly
- Web image retrieval from the project's configured providers, subject to provider terms, relevance checks, and reuse rights

Do not add generative video models or GPU inference.

### 3.4 Storage layout

Use OCI Object Storage only if the account's current Always Free allowance and selected region support the intended usage.

Suggested object key layout:

```text
ai-tutor/
  jobs/<job_id>/
    manifest.json
    script/
    storyboard/
    images/
    audio/
    scenes/
    avatar/
    final/
    logs/
```

Store job metadata and state in the database. Store large binary artifacts in Object Storage. Keep temporary render files on the VM and delete them after successful upload, subject to a configurable retention policy.

Do not assume that Object Storage requests, outbound data transfer, API operations, or additional storage are unlimited or free. Verify current quotas and pricing before enabling the integration.

---

## 4. Phase 0: Repository and tenancy discovery

### 4.1 Repository inspection

Before changing code:

1. Identify the repository root, active branch, and working tree status.
2. Inspect README, environment examples, Dockerfiles, compose files, requirements/lock files, and deployment scripts.
3. Map the existing pipeline from request to final MP4.
4. Identify the current database, queue, checkpoint, and storage implementations.
5. Identify all required environment variables and external API dependencies.
6. Identify any hard-coded local paths, localhost URLs, Windows paths, or assumptions about x86/CUDA.
7. Identify whether Wav2Lip or other avatar dependencies support ARM64 and CPU execution.
8. Run the existing tests and record the baseline before changing anything.

Create a deployment inventory with:
- Component
- Current implementation
- Runtime dependency
- CPU/ARM64 compatibility
- Required environment variables
- Persistent data location
- External API dependencies
- Deployment action
- Risk or unresolved question

Do not replace or refactor unrelated functionality.

### 4.2 OCI tenancy inspection through Chrome MCP

Using the user's already-authenticated OCI Console session:

1. Confirm the account is in the intended tenancy.
2. Identify the home region.
3. Inspect the Always Free eligibility and resource limits shown for the tenancy.
4. Inspect existing compute instances, VCNs, subnets, boot volumes, buckets, databases, and reserved public IPs.
5. Check available Ampere A1 capacity and service limits.
6. Check the current Always Free compute and storage allowances in official OCI documentation.
7. Identify any existing resources that could be reused.
8. Record screenshots or notes only if they do not reveal secrets, account identifiers, or sensitive information.

Do not create resources during discovery.

### Phase 0 exit criteria

- Repository deployment inventory completed.
- Existing application baseline tests recorded.
- OCI home region and Always Free eligibility confirmed.
- Existing resources and potential reuse documented.
- Any uncertainty about free eligibility raised to the user.

---

## 5. Phase 1: Prepare the application for portable deployment

### 5.1 Configuration

Create or update a production environment template, for example `.env.production.example`.

Requirements:

- No real secrets in the example file.
- All environment-specific URLs and paths configurable.
- No hard-coded OCI bucket names or endpoints in business logic.
- Separate development and production configuration.
- Validate required variables at startup.
- Never log secret values.

### 5.2 Storage abstraction

If the project currently writes directly to local disk, introduce or complete a minimal storage interface:

```python
class ArtifactStorage:
    def upload_file(self, local_path: str, object_key: str) -> str:
        raise NotImplementedError

    def download_file(self, object_key: str, local_path: str) -> None:
        raise NotImplementedError

    def delete_file(self, object_key: str) -> None:
        raise NotImplementedError
```

Implement:
- Local filesystem adapter for development
- OCI Object Storage adapter for deployment

Keep provider-specific SDK usage inside the OCI adapter. Do not make the rest of the application depend on OCI SDK types.

If a suitable abstraction already exists, extend it rather than creating a duplicate.

### 5.3 Job and artifact handling

Ensure each lesson job has:
- Unique job ID
- Explicit status
- Created/updated timestamps
- Scene-level status
- Retry count
- Artifact manifest
- Error summary without secrets
- Idempotent task handling

Recommended states:

```text
QUEUED
PLANNING
GENERATING_SCENES
VALIDATING
ASSEMBLING
UPLOADING
COMPLETED
FAILED
CANCELLED
```

A failed scene should not fail the whole lesson if the existing pipeline can safely use a fallback visual.

### 5.4 CPU resource controls

Add configurable limits:

- One heavy render job at a time initially.
- Bounded queue length.
- Per-job timeout.
- Maximum temporary disk usage.
- Maximum output resolution and FPS defaults.
- Cleanup of temporary files after confirmed upload.
- Memory-aware worker restart or task rejection if necessary.

Start with conservative settings, for example 720p at 30 FPS for video output, and benchmark before increasing quality or concurrency.

### Phase 1 exit criteria

- Application configuration is environment-driven.
- Storage can use local or OCI backend.
- Job processing is restart-safe.
- Heavy tasks are queued and bounded.
- Existing local development workflow still works.
- Existing tests pass.

---

## 6. Phase 2: Provision Always Free infrastructure

Only proceed after Phase 0 confirms eligibility and the user has authorized resource creation.

### 6.1 Create or reuse the VM

Preferred target:
- OCI Ampere A1 Flex
- ARM64 Ubuntu image
- Up to 2 OCPUs and 12 GB RAM, within current Always Free entitlement
- Smallest boot volume that safely supports the application and Docker images
- SSH key authentication

Before clicking Create:
- Verify the selected shape is marked Always Free.
- Verify boot volume size and performance settings are within free limits.
- Verify the estimated cost is zero.
- Verify no paid add-ons are selected.

If any price is shown, stop.

### 6.2 Networking

Reuse an existing eligible VCN/subnet where safe. Otherwise, create only the minimum networking resources necessary and verify their billing status.

Security rules:
- Allow inbound TCP 22 only from the user's known IP where practical.
- Allow inbound TCP 80 and 443 for public web traffic.
- Do not expose PostgreSQL (5432), Redis (6379), or internal worker ports.
- Do not create a paid NAT Gateway or Load Balancer.
- Prefer private service-to-service communication over public ports.
- Do not disable the VM firewall.

If a public IP or networking feature has a charge or unclear status, stop and ask.

### 6.3 SSH and host setup

- Use key-based SSH.
- Create a non-root deployment user.
- Apply security updates.
- Configure a host firewall.
- Install Docker Engine and Compose versions compatible with ARM64.
- Configure log rotation and disk monitoring.
- Do not place private keys on the VM unnecessarily.
- Do not paste private keys into the browser or terminal logs.

### Phase 2 exit criteria

- VM is running and verified Always Free.
- SSH works securely.
- Only required ports are exposed.
- Docker works on ARM64.
- No paid resource was created.

---

## 7. Phase 3: Deploy application services

### 7.1 Container architecture

Use ARM64-compatible images and pin versions. Do not assume an x86 image supports ARM.

Suggested compose services, adapted to the existing repository:

```yaml
services:
  api:
    build: ./backend
    restart: unless-stopped
    env_file:
      - .env.production
    depends_on:
      - redis
    # Do not publish internal application port directly.

  worker:
    build: ./backend
    command: ["python", "-m", "app.workers.cpu_worker"]
    restart: unless-stopped
    env_file:
      - .env.production
    depends_on:
      - redis

  redis:
    image: redis:<pinned-version>
    restart: unless-stopped
    # Internal network only.
    volumes:
      - redis_data:/data

  # Add PostgreSQL only if the repository needs it and its resource
  # footprint, persistence and backup strategy have been reviewed.

volumes:
  redis_data:
```

This is a structural example, not a drop-in compose file. Use the project's actual module names, commands, health checks, networks, volumes, and existing database setup. Do not add a duplicate database if one is already configured.

### 7.2 Reverse proxy and TLS

- Configure Nginx or Caddy as the only public application entry point.
- Use a domain if the user has one; otherwise document the temporary IP-based access limitations.
- Enable HTTPS using a supported certificate workflow.
- Set upload size and request timeouts appropriate for the application.
- Do not expose Swagger/OpenAPI docs publicly unless the user approves or authentication is enabled.

### 7.3 External APIs

Keep existing script-generation and TTS APIs external to the VM where appropriate.

- Validate API keys at startup without printing them.
- Implement timeouts and bounded retries.
- Handle provider rate limits.
- Do not introduce paid API dependencies without approval.
- Preserve existing provider fallback logic.

### Phase 3 exit criteria

- API health endpoint succeeds.
- Worker connects to the queue.
- Database connection succeeds if required.
- Reverse proxy serves the application over HTTPS.
- No secrets appear in logs.
- Services restart after VM reboot.

---

## 8. Phase 4: Deploy and benchmark CPU visual generation

### 8.1 Manim

- Install a compatible ARM64 Manim dependency set.
- Render a simple shape/text scene.
- Render a representative algorithm scene.
- Render a 10-second scene at 720p/30 FPS.
- Measure wall-clock time, peak RAM, CPU use, and temporary disk usage.
- Verify generated video plays correctly.

### 8.2 Pillow and FFmpeg

- Verify Pillow can load, resize, crop, annotate, and export supported formats.
- Verify FFmpeg supports the required codecs.
- Test image pan/zoom, transitions, audio muxing, and final MP4 assembly.
- Test a representative 30-second image-based video.
- Check audio/video synchronization.

### 8.3 Image retrieval

- Use only configured providers and respect their terms.
- Generate queries from scene narration and visual objectives.
- Validate semantic relevance, image dimensions, source and available license/attribution information.
- Reject keyword matches that depict the wrong subject.
- Cache only where the provider's terms permit it.
- Provide a Pillow fallback when no suitable asset is found.

### 8.4 Avatar stage

Treat the existing Wav2Lip/avatar stage as conditional:

1. Check ARM64 dependency compatibility.
2. Confirm CPU inference is supported.
3. Benchmark a 10-second representative clip.
4. Measure RAM, CPU and elapsed time.
5. Keep the stage optional if it is too slow or unstable.

Do not silently remove avatar functionality. Report the benchmark and propose options if it cannot run acceptably.

### Phase 4 exit criteria

- Manim sample renders successfully.
- Pillow and FFmpeg assembly tests pass.
- Image retrieval has relevance and reuse checks.
- Avatar compatibility is measured and documented.
- CPU resource limits are configured.

---

## 9. Phase 5: Persistent storage and data protection

### 9.1 Object Storage

Before creating a bucket:
- Confirm the bucket/storage allowance is Always Free.
- Confirm region compatibility.
- Confirm the intended storage volume is within the free allowance.
- Check request and data-transfer pricing.
- Stop if the console shows a charge or unclear billing status.

Configure:
- Private bucket by default.
- Least-privilege application access.
- Server-side encryption using supported defaults.
- Object naming by job ID and artifact type.
- Retention and cleanup policy.
- No public bucket access unless explicitly approved.

### 9.2 Database and checkpoints

- Persist job state and workflow checkpoints.
- Back up database data before schema migrations.
- Test restart recovery.
- Do not store large videos as database blobs.
- Store object keys and metadata in the database.
- Document backup and restore steps.

### 9.3 Storage portability

Keep the local filesystem and OCI Object Storage adapters available. Document how to switch storage providers through environment configuration without changing lesson-generation code.

### Phase 5 exit criteria

- Final videos and artifacts persist after worker restart.
- Database and checkpoint recovery are tested.
- Bucket permissions are private and minimal.
- Storage usage can be measured.
- Local storage fallback remains functional.

---

## 10. Phase 6: Security, monitoring and cost protection

### 10.1 Security checklist

- [ ] No secrets committed to Git.
- [ ] No credentials exposed in screenshots or logs.
- [ ] SSH key authentication only.
- [ ] SSH source IP restricted where practical.
- [ ] PostgreSQL and Redis not publicly accessible.
- [ ] HTTPS enabled for public application access.
- [ ] OCI credentials use least privilege.
- [ ] Object Storage bucket private by default.
- [ ] API endpoints have appropriate authentication and rate limiting.
- [ ] Debug mode disabled in production.
- [ ] Dependencies pinned and security updates documented.

### 10.2 Monitoring

Use lightweight, free/available host-level monitoring:
- CPU utilization
- Memory and swap
- Disk usage
- Docker container health
- Queue length
- Job duration
- Render duration
- Worker failures
- Object Storage usage

Avoid enabling paid OCI monitoring/logging services unless the user explicitly approves the cost.

### 10.3 Cost protection

- Do not upgrade to Pay As You Go.
- Do not create GPU instances.
- Do not create paid load balancers or NAT gateways.
- Verify Always Free labels and estimated cost before resource creation.
- Review the tenancy's usage and billing page after deployment.
- Keep a written inventory of all created resources and their billing classification.
- If a resource's free status is uncertain, stop and ask.

---

## 11. Phase 7: End-to-end acceptance testing

Run these tests on the deployed application:

| Test | Expected result |
|---|---|
| Backend health check | Healthy response |
| Frontend/API integration | Requests succeed over HTTPS |
| Script generation | Existing provider integration works |
| Storyboard generation | Scene plan is persisted |
| LangGraph workflow | Completes and records state |
| Manim technical scene | Correct video artifact generated |
| Image retrieval scene | Relevant image accepted or safe fallback used |
| Pillow fallback | Valid visual generated |
| FFmpeg assembly | Valid MP4 with synchronized audio |
| Worker restart | Queued jobs recover safely |
| VM reboot | Services return automatically |
| Object Storage | Artifacts persist and are retrievable |
| Failed scene | Bounded retry and fallback work |
| Resource pressure | Queue remains bounded; service does not exhaust memory |
| Portability | Local deployment still works with local storage adapter |

### Performance targets to measure, not assume

- One heavy render job at a time initially.
- No out-of-memory failure during the representative lesson test.
- No public exposure of internal service ports.
- No paid OCI resource created.
- Successful restart and recovery.
- Record actual time to render a 10-second Manim scene and a 30-second assembled clip.

Do not claim the system is production-scalable based only on a successful single-job test.

---

## 12. Portability and exit plan

The deployment must remain usable after trial credits expire and must not depend on Oracle-specific application logic.

Required portability measures:

1. Keep Dockerfiles and Compose configuration in the repository.
2. Keep application configuration in environment variables.
3. Use generic storage and database interfaces.
4. Keep OCI SDK calls inside the OCI storage adapter or deployment scripts.
5. Keep generated artifacts in a documented, exportable layout.
6. Document database export and restore.
7. Document how to run the full pipeline locally.
8. Document how to move the app to another VM or cloud provider.
9. Do not use Oracle trial credits for any mandatory runtime dependency.

The application should continue to run using the CPU-based Always Free host only while the account and resources remain eligible. Do not promise guaranteed lifetime availability or capacity.

---

## 13. Agent execution order and approval gates

The agent must execute in this order:

| Order | Work | Approval |
|---|---|---|
| 1 | Inspect repository and run baseline tests | No additional approval |
| 2 | Inspect OCI tenancy, home region, free limits and existing resources | No resource creation |
| 3 | Produce deployment inventory and proposed resource plan | User reviews |
| 4 | Create/reuse verified Always Free VM and minimum network resources | Explicit user approval |
| 5 | Configure host and deploy application | Within approved scope |
| 6 | Create/reuse Always Free storage only after verifying terms | Explicit approval if new resource |
| 7 | Run CPU visual benchmarks and acceptance tests | Within approved scope |
| 8 | Report costs, limitations, security and rollback plan | Final report |

### Stop and ask the user if:

- OCI asks to upgrade to Pay As You Go.
- A resource is not clearly marked Always Free.
- The console shows a non-zero estimated cost.
- The selected region has no eligible capacity.
- A paid networking or storage service appears necessary.
- Existing resources may be overwritten or deleted.
- A public IP, domain, firewall or access rule change could expose sensitive services.
- A migration could lose data.
- The repository requires a new paid third-party API.

Do not bypass a billing or security warning to complete the task.

---

## 14. Required final handoff

At completion, provide:

1. OCI region and VM shape created or reused.
2. Resource inventory with each resource's verified Always Free status.
3. Public application URL, if configured.
4. Deployed services and container status.
5. Environment variables required, by name only (never values).
6. Database and Object Storage configuration summary.
7. CPU benchmark results for Manim, FFmpeg, and avatar processing.
8. End-to-end test results.
9. Security checklist status.
10. Current storage and compute usage.
11. Any known limitations or incomplete work.
12. Exact steps to stop, restart, back up, restore, and redeploy.
13. Confirmation that no GPU or generative video model was provisioned.
14. Confirmation that no Pay As You Go upgrade or paid resource was created.

---

## 15. Definition of Done

- [ ] Existing project inspected before modification.
- [ ] Baseline tests recorded.
- [ ] OCI Always Free eligibility verified.
- [ ] No paid account upgrade performed.
- [ ] No GPU provisioned.
- [ ] ARM64-compatible application deployment completed.
- [ ] FastAPI and LangGraph operational.
- [ ] Background CPU worker operational.
- [ ] Manim, Pillow and FFmpeg tested.
- [ ] Image retrieval/fallback tested where supported.
- [ ] Existing audio pipeline tested.
- [ ] Avatar stage tested or explicitly documented as unsupported/too slow.
- [ ] Persistent data and artifacts verified.
- [ ] Security and cost controls checked.
- [ ] End-to-end lesson generation completed.
- [ ] Local development remains functional.
- [ ] Portability and rollback instructions delivered.

**Final principle:** Deploy the smallest useful Always Free footprint first. Measure the real application workload before adding services or increasing resource usage. Keep the project portable and do not make any paid resource a requirement for lesson generation.
