# Networking Architecture

The platform uses network segmentation to enforce explicit communication paths between control-plane services, model supply-chain workloads and inference infrastructure.

## Network Principles

- deny unnecessary east-west communication
- restrict outbound connectivity
- separate model acquisition from model execution
- allow only required service-to-service flows
- keep inference runtimes independent from public model repositories

## Control Plane Connectivity

The control plane communicates with:

- PostgreSQL for platform state
- Kubernetes API for orchestration
- trusted registry services
- runtime orchestration endpoints
- internal authentication and audit services

## Model Ingestion Connectivity

Model ingestion workloads are the primary components allowed to reach external model sources.

Their network access should be limited to:

- approved model repositories
- internal registry endpoints
- required security services
- control-plane callbacks

## Trusted Registry Connectivity

The trusted registry is accessible only from components that require artifact publication or artifact consumption.

Typical consumers include:

- promotion workloads
- runtime activation components
- platform verification services

## Runtime Connectivity

Inference runtimes are designed with restricted outbound connectivity.

Required flows may include:

- trusted registry access
- control-plane callbacks
- internal API exposure
- observability endpoints

Direct access to public model repositories is not required.

## Kubernetes Enforcement

NetworkPolicies are used to define allowed ingress and egress paths between platform components.

The objective is to make connectivity explicit rather than relying on unrestricted namespace communication.
