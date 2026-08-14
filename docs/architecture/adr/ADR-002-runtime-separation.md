# ADR-002: Separate Control Plane and Inference Runtimes

## Status

Accepted

## Context

AI inference infrastructure may vary significantly depending on accelerator hardware, security requirements and deployment environment.

Coupling platform governance directly to a specific inference implementation would limit portability.

## Decision

The control plane and inference runtime layers are separated.

The control plane manages lifecycle and governance while runtime implementations are responsible for model execution.

## Consequences

Benefits:

- runtime portability
- heterogeneous accelerator support
- independent lifecycle management
- clearer security boundaries
- easier platform evolution

Trade-offs:

- runtime activation requires an orchestration interface
- runtime health must be synchronized with the control plane
