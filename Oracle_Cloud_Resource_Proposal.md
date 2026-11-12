# OCI resource proposal for review

Status: **deferred; the user selected repository preparation only and explicitly prohibited OCI resource creation**. This document is a proposal, not an approval request.
Updated: 2026-11-07. No cloud resources created by this task.

## Verified configuration and allowance evidence

- Home region: India South (Hyderabad), `ap-hyderabad-1`, explicitly identified as home in the OCI region menu.
- Account banner: Free Tier / Free Trial. No account upgrade is proposed.
- Compute: `VM.Standard.A1.Flex`, **Always Free-eligible** label, **2 OCPUs / 12 GB RAM**.
- OS: Canonical Ubuntu 24.04 Minimal aarch64, build 2026.10.27-0; image selector price Free.
- Boot storage: image default displayed as **46.6 GB**; custom sizing/performance off, in-transit encryption on, Oracle-managed encryption key, no extra disks.
- Official documentation confirms a 200 GB combined home-region boot/block storage allowance and A1 2 OCPUs/12 GB equivalent monthly allowance: https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- Root compartment resource lists are empty for compute, VCNs and volumes; these lists were not exhaustive across all compartments. Read-only Hyderabad Block Volume limits now show free-tier regional storage 200 GB total, 0 used, 200 remaining. Regional A1 service limits (16 OCPUs / 96 GB) are not the free allowance.
- Estimator displays boot volume and total **$2.76/month**, with an explicit statement that tier unit pricing is not reflected. User clarified that this is a standard estimate, not proof of charges. Do not treat the estimate alone as proof of paid usage or as proof of zero billing. Approval must remain limited to resources verified within free allowances; no trial credits or actual charges are authorized.

## Proposed network

| Resource / setting | Proposed configuration |
| --- | --- |
| VCN | `ai-tutor-vcn`, IPv4 `10.0.0.0/16`, private DNS label `aitutor` |
| Subnet | `ai-tutor-public`, regional public subnet `10.0.0.0/24` |
| Internet route | One internet gateway and `0.0.0.0/0` route for public access |
| Public IPv4 | One address for VM SSH/web access only if final account-specific cost/eligibility review confirms no paid resource is required |
| SSH ingress | Stateful TCP destination 22, current deployment computer public IPv4 `/32` only; re-detect before rule creation |
| HTTP/HTTPS ingress | Stateful TCP destinations 80 and 443 from `0.0.0.0/0` |
| Internal services | No public rules for 8000, 3000, 27017, 5432, 6379 or worker ports |
| Default SSH rule | Replace/remove unrestricted default TCP 22 rule **before** attaching a publicly addressed VM; an NSG restriction alone cannot cancel a broad security-list allow rule |
| Other networking | No NAT gateway, load balancer, paid firewall, flow logs or additional VM |

The current compute wizard disables public IPv4 assignment while its new subnet is uncreated. A separate unsubmitted VCN form on Chrome MCP page 4 has the proposed name, CIDR and DNS label filled. Creating the VCN first enables configuring restricted rules before selecting the existing subnet in the VM draft. The generic VCN creation form does not itself create the proposed subnet/gateway or finish those access rules.

## VM and key handling

- VM name: `ai-tutor-cpu`; one VM only, home-region AD 1, normal on-demand capacity. Capacity has not been tested by launch.
- Use the existing freshly downloaded matching SSH pair; do not regenerate unnecessarily. Private/public files are stored under `C:\Users\Rushi\.ssh\oci-ai-tutor-20261107-151654\`, outside repository/OneDrive and restricted to the current Windows user. Key contents are not recorded in this document.
- Before launch, verify the draft still contains the matching saved public key, review optional agent plugins, and disable unnecessary cloud log collection/workload integrations for the smallest deployment scope.
- Configure host firewall to match approved ingress, then install ARM64-compatible runtime and deploy only after repository preparation/validation is ready.

## Approval boundary

The source deployment plan section 13 requires **explicit user approval** before creating/reusing the VM and minimum networking; section 2 requires approval before public exposure. The current instruction is repository preparation only, so this document does not request those actions. Public IPv4 and internet-gateway charges remain uncertain; see `deployment/OCI_ELIGIBILITY.md`. Any future review must be limited to resources verified within Always Free entitlements and cannot authorize paid resources, trial credit spending, account conversion, deletion, production data overwrite, new storage buckets or exposed application internals.

After approval, check resource eligibility and remaining allowances immediately before creation; create network first, secure rules, then finalize the single VM. Stop for genuine paid billing terms, unavailable free capacity or any configuration outside this proposal. Preserve all existing application work. Record actual created resources and costs separately from this proposal.

## Dedicated VCN inspection (latest review)

The Hyderabad root-compartment VCN list showed no items. Opened the dedicated Create VCN form only; it has IPv4 CIDR, DNS and IPv6 options, but no gateway/subnet/security-rule configuration at this stage. IPv6 allocation is off; BYOIPv6 and ULA prefixes are empty. Nothing submitted.

Proposed configuration for later separately approved creation:
- VCN `ai-tutor-vcn`: `10.0.0.0/16`, DNS label `aitutor`, IPv6 disabled.
- Regional public subnet `ai-tutor-public`: `10.0.0.0/24`, IPv6 disabled.
- One enabled Internet Gateway `ai-tutor-igw`; subnet route table `ai-tutor-public-rt`: destination `0.0.0.0/0`, target type Internet Gateway, target `ai-tutor-igw`.
- Stateful ingress: TCP destination 22 from the operator's verified current public IPv4 `/32`; TCP 80 and 443 from `0.0.0.0/0`. Source ports unrestricted. No public database/API/worker rules.
- Remove any broad default SSH allow rule from every attached security list; a restrictive NSG does not override an existing allow rule. Confirm the operator IP before adding the SSH rule; no IP was guessed.
- Allow outbound traffic needed for package installation and HTTPS providers; review egress and traffic allowance before deployment.
- No NAT gateway, service gateway, DRG, load balancer, paid firewall, flow logs or IPv6 resources proposed.

Oracle VCN FAQ describes VCN creation/use as free; the existing eligibility report records public-IP pricing evidence. Traffic allowances still apply. The dedicated VCN form displays no itemized cost estimate, so this inspection does not establish final account billing or quotas.

The public-subnet retry in the compute wizard left public IPv4 disabled; it was not forced. Upload public key file is selected. Browser upload was denied because the public key is outside the tool's allowed workspace roots. Manually choose `C:\Users\Rushi\.ssh\ai-tutor-runtime\oci-ai-tutor-ed25519.pub`. Do not upload its private companion. This fresh key supersedes the historical key path above.
