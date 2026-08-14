# ADR-003: Restrict External Connectivity from Inference Runtimes

## Status

Accepted

## Context

Production inference workloads should not depend on uncontrolled external model repositories.

Direct outbound connectivity increases supply-chain and data-exposure risks.

## Decision

Inference runtimes consume previously approved artifacts from trusted infrastructure rather than retrieving models directly from public repositories.

## Consequences

Benefits:

- reduced supply-chain exposure
- predictable model versions
- compatibility with disconnected infrastructure
- stronger operational control
- improved auditability

Trade-offs:

- models must pass through an ingestion and promotion workflow
- internal artifact storage capacity is required
