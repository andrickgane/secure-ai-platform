# ADR-001: Distribute AI Models as OCI Artifacts

## Status

Accepted

## Context

Enterprise AI platforms require controlled distribution of large model artifacts.

Allowing inference runtimes to retrieve models directly from external repositories increases the attack surface and complicates provenance, auditing and offline operation.

## Decision

Approved models are distributed as immutable OCI artifacts through a trusted internal registry.

## Consequences

Benefits:

- content-addressable artifacts
- immutable model versions
- compatibility with registry infrastructure
- centralized distribution
- simplified provenance controls
- support for restricted environments

Trade-offs:

- additional storage requirements
- promotion workflows are required
- registry lifecycle management becomes part of the platform
