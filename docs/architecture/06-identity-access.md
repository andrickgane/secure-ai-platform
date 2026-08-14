# Identity and Access

Identity and access controls are separated between human users, platform services and runtime workloads.

## Human Identity

Platform users authenticate through the control plane.

Authorization decisions are based on platform roles and responsibilities.

Typical access domains include:

- platform administration
- model lifecycle management
- deployment operations
- audit visibility

## Workload Identity

Kubernetes workloads use dedicated ServiceAccounts.

Each ServiceAccount receives only the permissions required by its responsibility.

Examples include:

- control-plane orchestration
- model ingestion
- model promotion
- runtime activation

## Kubernetes RBAC

RBAC is used to restrict access to Kubernetes resources.

Permissions are scoped according to workload responsibilities and namespaces wherever possible.

The platform follows least-privilege principles and avoids unnecessary cluster-wide permissions.

## Secret Access

Secrets are provided only to components that require them.

Examples include:

- registry credentials
- callback tokens
- signing material
- runtime authentication credentials
- database credentials

Signing private keys and runtime verification keys are intentionally separated.

## Enterprise Integration

The identity model is designed to evolve toward enterprise identity federation and centralized authorization systems.
