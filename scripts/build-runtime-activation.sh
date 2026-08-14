#!/usr/bin/env bash
set -Eeuo pipefail

VERSION="${1:-v1.0.0}"

: "${REGISTRY:?REGISTRY must be defined}"
: "${PLATFORM:=linux/amd64}"

ROOT="$(git rev-parse --show-toplevel)"
cd "${ROOT}"

LOCAL_IMAGE="runtime-activation:${VERSION}"
REMOTE_IMAGE="${REGISTRY}/ai-platform/runtime-activation:${VERSION}"

echo "Building ${REMOTE_IMAGE}"

docker buildx build \
  --no-cache \
  --platform "${PLATFORM}" \
  -f runtime-activation/Dockerfile \
  -t "${LOCAL_IMAGE}" \
  --load \
  .

docker tag "${LOCAL_IMAGE}" "${REMOTE_IMAGE}"
docker push "${REMOTE_IMAGE}"

echo "Published ${REMOTE_IMAGE}"
