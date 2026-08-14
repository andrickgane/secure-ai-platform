# Security Policy

Secure AI Platform is an engineering project focused on security-sensitive AI infrastructure.

## Reporting a Vulnerability

Please do not disclose security vulnerabilities through public GitHub issues.

For security-sensitive findings, contact the project maintainer privately through the contact information available on the maintainer's GitHub profile.

When reporting a vulnerability, include:

- affected component
- reproduction conditions
- potential impact
- relevant logs or evidence
- suggested mitigation, when available

## Security Scope

Security-sensitive areas include:

- authentication and authorization
- Kubernetes RBAC
- model ingestion
- model promotion
- artifact signing and verification
- registry access
- runtime orchestration
- secret handling
- network isolation

## Security Model

The platform assumes that AI models acquired from external sources are untrusted until they have passed through the controlled ingestion, validation and promotion workflow.

Inference environments should consume trusted, immutable and verified artifacts rather than retrieving models directly from public repositories.
