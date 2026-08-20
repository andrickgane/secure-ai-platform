# Plateform AI Architecture

## Overview

Plateform AI uses a Kubernetes-based Control Plane to manage AI model lifecycle and inference workloads.

```text
Users / Applications
        |
        v
AI Workspace / API
        |
        v
AI Control Plane
   |      |      |
   |      |      +--> Deployment Engine
   |      +---------> Profile Engine
   +----------------> Model Lifecycle
                         |
                         v
                  Trusted OCI Model
                         |
                         v
                    Zot Registry
                         |
                         v
                 Runtime Selection
                  /             \
               vLLM          llama.cpp
                  \             /
                   Kubernetes / GPU
```

## Model Formats

- Safetensors -> vLLM
- GGUF -> llama.cpp

## Runtime Families

- vLLM CUDA
- vLLM Metal
- llama.cpp CUDA
- llama.cpp Metal

## Kubernetes Identities

- `ai-control-plane`: orchestration identity
- `model-ingestion`: ingestion workload
- `model-promotion`: trusted promotion workload
- `runtime-activation`: runtime lifecycle workload
- `ai-runtime`: Kubernetes inference workload

## Future Architecture

Planned areas include RAG, evaluations, LoRA, observability, GPU Operator, MIG, autoscaling, KServe, Triton, multi-runtime routing and multi-cluster deployment.
