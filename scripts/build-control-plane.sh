#!/usr/bin/env bash
set -Eeuo pipefail

VERSION="${1:-v1.0.0}"

: "${REGISTRY:?REGISTRY must be defined}"
: "${PLATFORM:=linux/amd64}"

ROOT="$(git rev-parse --show-toplevel)"
cd "${ROOT}"

LOCAL_IMAGE="ai-control-plane:${VERSION}"
REMOTE_IMAGE="${REGISTRY}/ai-platform/control-plane:${VERSION}"

echo "Validating Control Plane sources..."

python -m py_compile \
  api/app/main.py \
  api/app/routes/catalog.py \
  api/app/routes/deployments.py \
  api/app/routes/internal_runtime.py \
  api/app/services/deployment_service.py \
  api/app/services/kubernetes_service.py \
  api/app/services/runtime_activation_service.py \
  api/app/services/runtime_selector_service.py \
  api/app/services/trusted_model_service.py

echo "Building ${REMOTE_IMAGE}"

docker buildx build \
  --no-cache \
  --platform "${PLATFORM}" \
  -f api/Dockerfile \
  -t "${LOCAL_IMAGE}" \
  --load \
  .

docker tag "${LOCAL_IMAGE}" "${REMOTE_IMAGE}"
docker push "${REMOTE_IMAGE}"

echo "Published ${REMOTE_IMAGE}"
