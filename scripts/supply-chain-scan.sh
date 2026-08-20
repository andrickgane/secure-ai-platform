#!/usr/bin/env bash

set -Eeuo pipefail

IMAGE="${1:-}"

if [ -z "${IMAGE}" ]; then
    echo "Usage: $0 <docker-image>"
    exit 2
fi

ROOT="$(git rev-parse --show-toplevel)"

OUTPUT_ROOT="${SUPPLY_CHAIN_OUTPUT_DIR:-/tmp/plateform-ai-supply-chain}"

SYFT_IMAGE="ghcr.io/anchore/syft:v1.50.0@sha256:1288ea4c8b38767b4e620c1e312c8cb26b6e887a99b4f07ab6cd19fc6f225026"

TRIVY_IMAGE="ghcr.io/aquasecurity/trivy:0.73.0@sha256:7cced7cae583819fc7806d4cbc0dbbc7cad18b99f7d3e235192e6da8c091045c"

TRIVY_POLICY="${ROOT}/.trivyignore.yaml"

mkdir -p "${OUTPUT_ROOT}"

SAFE_IMAGE_NAME="$(
    printf '%s' "${IMAGE}" \
    | tr '/:@' '____' \
    | tr -cd 'A-Za-z0-9._-'
)"

SBOM_FILE="${OUTPUT_ROOT}/${SAFE_IMAGE_NAME}.spdx.json"
TRIVY_FILE="${OUTPUT_ROOT}/${SAFE_IMAGE_NAME}.trivy.json"

echo "=================================================="
echo "Plateform AI Supply Chain Security Gate"
echo "=================================================="
echo
echo "Image  : ${IMAGE}"
echo "Output : ${OUTPUT_ROOT}"
echo

# ==========================================================
# LOCAL IMAGE
# ==========================================================

echo "===== DOCKER IMAGE ====="

docker image inspect "${IMAGE}" >/dev/null 2>&1 || {
    echo "ERROR: image locale introuvable: ${IMAGE}"
    exit 1
}

IMAGE_ID="$(
    docker image inspect \
        "${IMAGE}" \
        --format '{{.Id}}'
)"

echo "PASS: ${IMAGE_ID}"

# ==========================================================
# DOCKER SOCKET
# ==========================================================

echo
echo "===== DOCKER SOCKET ====="

DOCKER_SOCKET="/var/run/docker.sock"

if [ ! -S "${DOCKER_SOCKET}" ]; then
    if [ -S "${HOME}/.docker/run/docker.sock" ]; then
        DOCKER_SOCKET="${HOME}/.docker/run/docker.sock"
    else
        echo "ERROR: Docker socket introuvable"
        exit 1
    fi
fi

echo "PASS: ${DOCKER_SOCKET}"

# ==========================================================
# POLICY
# ==========================================================

echo
echo "===== SECURITY POLICY ====="

if [ ! -s "${TRIVY_POLICY}" ]; then
    echo "ERROR: ${TRIVY_POLICY} absent"
    exit 1
fi

if ! grep -q 'expired_at:' "${TRIVY_POLICY}"; then
    echo "ERROR: aucune expiration définie dans la politique"
    exit 1
fi

echo "PASS: ${TRIVY_POLICY}"

# ==========================================================
# TOOLS
# ==========================================================

echo
echo "===== SUPPLY CHAIN TOOL IMAGES ====="

docker pull "${SYFT_IMAGE}" >/dev/null

echo "PASS: Syft v1.50.0"

docker pull "${TRIVY_IMAGE}" >/dev/null

echo "PASS: Trivy v0.73.0"

# ==========================================================
# SBOM
# ==========================================================

echo
echo "===== SBOM SPDX ====="

docker run \
    --rm \
    -v "${DOCKER_SOCKET}:/var/run/docker.sock" \
    "${SYFT_IMAGE}" \
    "docker:${IMAGE}" \
    -o spdx-json \
    > "${SBOM_FILE}"

test -s "${SBOM_FILE}" || {
    echo "ERROR: SBOM vide"
    exit 1
}

echo "PASS: ${SBOM_FILE}"

# ==========================================================
# RAW TRIVY REPORT
#
# IMPORTANT:
# No exception is applied here.
# This report always contains the complete vulnerability state.
# ==========================================================

echo
echo "===== TRIVY RAW SECURITY REPORT ====="

mkdir -p "${HOME}/Library/Caches/trivy"

docker run \
    --rm \
    -v "${DOCKER_SOCKET}:/var/run/docker.sock" \
    -v "${HOME}/Library/Caches/trivy:/root/.cache/" \
    "${TRIVY_IMAGE}" \
    image \
    --skip-version-check \
    --scanners vuln \
    --format json \
    "${IMAGE}" \
    > "${TRIVY_FILE}"

test -s "${TRIVY_FILE}" || {
    echo "ERROR: rapport Trivy vide"
    exit 1
}

echo "PASS: ${TRIVY_FILE}"

# ==========================================================
# ENFORCEMENT GATE
#
# Only explicitly approved, path-scoped and time-bounded
# exceptions in .trivyignore.yaml are suppressed.
# ==========================================================

echo
echo "===== SECURITY ENFORCEMENT GATE ====="
echo "Policy:"
echo "  - block fixable HIGH/CRITICAL vulnerabilities"
echo "  - allow only explicit temporary exceptions"
echo "  - preserve complete raw report"
echo

if ! docker run \
    --rm \
    -v "${DOCKER_SOCKET}:/var/run/docker.sock" \
    -v "${HOME}/Library/Caches/trivy:/root/.cache/" \
    -v "${ROOT}:/workspace:ro" \
    "${TRIVY_IMAGE}" \
    image \
    --skip-version-check \
    --scanners vuln \
    --severity HIGH,CRITICAL \
    --ignore-unfixed \
    --ignorefile /workspace/.trivyignore.yaml \
    --show-suppressed \
    --exit-code 1 \
    "${IMAGE}"
then
    echo
    echo "=================================================="
    echo "SUPPLY CHAIN SECURITY GATE FAILED"
    echo "=================================================="
    echo
    echo "Image  : ${IMAGE}"
    echo "Report : ${TRIVY_FILE}"
    exit 1
fi

echo
echo "=================================================="
echo "SUPPLY CHAIN SECURITY GATE PASSED"
echo "=================================================="
echo
echo "Image  : ${IMAGE}"
echo "SBOM   : ${SBOM_FILE}"
echo "Trivy  : ${TRIVY_FILE}"
echo "Policy : ${TRIVY_POLICY}"
