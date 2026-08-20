# Plateform AI Security

## Current Controls

- JWT authentication and validation
- Strict `platform_admin` authorization
- Least-privilege Control Plane RBAC
- Dedicated workload ServiceAccounts
- Workload ServiceAccount token automount disabled
- Fail-closed Kubernetes NetworkPolicy enforcement
- PostgreSQL network isolation
- Worker egress isolation
- Runtime isolation
- OCI model artifact validation
- Cosign trusted model verification
- Non-root containers
- Read-only root filesystems where applicable
- Linux capabilities dropped
- RuntimeDefault seccomp
- Repository pre-push security checks

## Workload Identities

- `model-ingestion`
- `model-promotion`
- `runtime-activation`
- `ai-runtime`

## Future Hardening

- Internal API route isolation
- NetworkPolicy startup convergence hardening
- Safe archive extraction
- Protection against path traversal and unsafe symlinks
- Prompt-injection trust boundaries
- Dependency locking
- SBOM generation
- Image signing
- Vulnerability policies
- Admission controls
- Production secret management

## Secret Policy

Real secrets, private keys, API tokens, audit exports and local backups must never be committed.
