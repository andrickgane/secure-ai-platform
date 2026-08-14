# Security Architecture

Security controls are integrated into the platform lifecycle rather than applied only at the infrastructure perimeter.

## Trust Boundaries

The platform separates:

1. external model sources
2. ingestion workloads
3. trusted artifact storage
4. control plane services
5. inference runtimes
6. platform users and administrators

## Kubernetes Security

Kubernetes workloads use:

- dedicated ServiceAccounts
- namespace-scoped RBAC
- NetworkPolicies
- isolated workload identities
- controlled secret access
- restricted service communication

## Model Supply Chain Security

Models cannot move directly from an external repository into an inference runtime.

The trusted lifecycle requires:

- controlled ingestion
- security validation
- explicit promotion
- immutable artifact creation
- cryptographic signing
- runtime-side verification

## Runtime Security

Inference environments are designed to operate without unrestricted access to external model repositories.

Runtime activation verifies trusted artifacts before model execution.

## Secrets

Sensitive configuration is separated from application manifests and source code.

Private signing material is isolated from runtime verification material.

## Auditability

Security-relevant lifecycle events are recorded by the platform control plane to provide operational traceability.
