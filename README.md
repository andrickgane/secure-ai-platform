# Plateform AI

**Enterprise AI / LLMOps / GPU Infrastructure Platform**

Plateform AI is an engineering platform for operating, securing and orchestrating AI workloads across Kubernetes and heterogeneous inference runtimes.

## Current V2 Capabilities

- FastAPI AI Control Plane
- Kubernetes-native workload orchestration
- PostgreSQL persistence
- JWT authentication and strict `platform_admin` authorization
- Model ingestion, quarantine and trusted promotion
- OCI model artifacts with Zot registry
- Cosign model verification
- Safetensors and GGUF support
- vLLM CUDA / Metal
- llama.cpp CUDA / Metal
- Runtime selection foundations
- Custom inference profiles
- Streaming AI Workspace
- Persistent conversations
- Dedicated Kubernetes workload identities
- Fail-closed NetworkPolicy enforcement
- PostgreSQL, worker and runtime network isolation

## Architecture

```text
Model Provider
      |
      v
Model Ingestion
      |
      v
Validation / Quarantine
      |
      v
Trusted Promotion
      |
      v
OCI Model Registry
      |
      v
Runtime Selection
      |
      +-------------------+
      |                   |
      v                   v
    vLLM              llama.cpp
      |                   |
      +---------+---------+
                |
                v
        Kubernetes / GPU
                |
                v
         AI Workspace / API
```

## Workload Identities

- `model-ingestion`
- `model-promotion`
- `runtime-activation`
- `ai-runtime`

Workload ServiceAccount token automount is disabled. The Control Plane retains Kubernetes API access for orchestration.

## Documentation

- [Architecture](docs/architecture.md)
- [Security](docs/security.md)
- [Roadmap](docs/roadmap.md)
- [Development Workflow](docs/development.md)

## V2 Roadmap

1. Model ingestion and format detection
2. llama.cpp integration
3. Runtime compatibility matrix and auto-selection
4. Profile Engine and custom profiles
5. AI Workspace, streaming and inference parameters
6. Observability
7. RAG
8. LLMOps / LoRA / evaluations / promotion
9. NVIDIA / GPU infrastructure
10. Autoscaling / multi-runtime / KServe / Triton
11. Security / policy-as-code
12. HA / federation / offline enterprise

## Branch Strategy

- `main`: stable and demonstrable checkpoints
- `v2-development`: active V2 integration branch

## Project Status

Plateform AI V2 is under active development. The long-term objective is a complete platform spanning Enterprise AI, LLMOps, GPU Infrastructure, Kubernetes, AI Security, RAG, Observability and Model Lifecycle Management.
