#!/usr/bin/env bash

set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

export PYTHONPATH="${ROOT}/api${PYTHONPATH:+:${PYTHONPATH}}"

TAG="v2.1.0-dev.35"

IMAGE="registry.andrick.local:31039/ai-platform/control-plane:${TAG}"


echo "=================================================="
echo "PLATEFORM AI - BUILD / DEPLOY ${TAG}"
echo "=================================================="


# ==========================================================
# SECURITY VALIDATION
# ==========================================================

echo
echo "[1/7] Security validation"
echo

./scripts/security-finalize-p1.sh


# ==========================================================
# BUILD
# ==========================================================

echo
echo "[2/7] Docker build"
echo
echo "${IMAGE}"
echo

docker build \
  -t "${IMAGE}" \
  -f api/Dockerfile \
  .


# ==========================================================
# PUSH
# ==========================================================

echo
echo "[3/7] Docker push"
echo

docker push "${IMAGE}"

echo
echo "Image:"
docker image inspect \
  "${IMAGE}" \
  --format 'ID={{.Id}} TAGS={{.RepoTags}}'


# ==========================================================
# UPDATE DECLARATIVE MANIFEST
# ==========================================================

echo
echo "[4/7] Update deployment manifest"
echo

perl -0pi -e '
s#registry\.andrick\.local:31039/ai-platform/control-plane:v2\.1\.0-dev\.[0-9]+#registry.andrick.local:31039/ai-platform/control-plane:v2.1.0-dev.35#g
' deploy/api/deployment.yaml


COUNT="$(
  grep -c \
    'registry.andrick.local:31039/ai-platform/control-plane:v2.1.0-dev.35' \
    deploy/api/deployment.yaml
)"

if [[ "${COUNT}" != "2" ]]; then
    echo "ERROR: expected exactly 2 .35 references"
    echo "Found: ${COUNT}"
    exit 1
fi


grep -n \
  'registry.andrick.local:31039/ai-platform/control-plane' \
  deploy/api/deployment.yaml


kubectl apply \
  --dry-run=client \
  -f deploy/api/deployment.yaml \
  >/dev/null

git diff --check


# ==========================================================
# DEPLOY
# ==========================================================

echo
echo "[5/7] Deploy ${TAG}"
echo

kubectl apply \
  -f deploy/api/deployment.yaml


kubectl -n ai-system rollout status \
  deployment/ai-control-plane \
  --timeout=180s


# ==========================================================
# VERIFY RUNNING IMAGE
# ==========================================================

echo
echo "[6/7] Verify deployment"
echo

RUNNING_IMAGES="$(
  kubectl -n ai-system get deployment \
    ai-control-plane \
    -o jsonpath='{range .spec.template.spec.initContainers[*]}INIT {.name}{" = "}{.image}{"\n"}{end}{range .spec.template.spec.containers[*]}CONTAINER {.name}{" = "}{.image}{"\n"}{end}'
)"

echo "${RUNNING_IMAGES}"

IMAGE_COUNT="$(
  echo "${RUNNING_IMAGES}" \
  | grep -c \
    'control-plane:v2.1.0-dev.35'
)"

if [[ "${IMAGE_COUNT}" != "2" ]]; then
    echo
    echo "ERROR: .35 not used by both init + API"
    exit 1
fi


# ==========================================================
# HEALTH
# ==========================================================

echo
echo "[7/7] Platform health"
echo

kubectl -n ai-system get pods


HTTP_CODE="$(
  curl -k -s \
    -o /dev/null \
    -w '%{http_code}' \
    https://api.ai.local/docs
)"

echo
echo "API HTTP=${HTTP_CODE}"

if [[ "${HTTP_CODE}" != "200" ]]; then
    echo "ERROR: API health check failed"
    exit 1
fi


ERRORS="$(
  kubectl -n ai-system logs \
    deployment/ai-control-plane \
    -c api \
    --tail=300 \
  | grep -Ei \
    'traceback|exception|fatal' \
  || true
)"

if [[ -n "${ERRORS}" ]]; then
    echo
    echo "${ERRORS}"
    echo
    echo "ERROR: application runtime errors detected"
    exit 1
fi


echo
echo "=================================================="
echo "${TAG} DEPLOYED SUCCESSFULLY"
echo "=================================================="
