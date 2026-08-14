#!/usr/bin/env bash
set -Eeuo pipefail

for variable in \
  DEPLOYMENT_NAME MODEL_ID ARTIFACT_REFERENCE ARTIFACT_DIGEST \
  MAX_MODEL_LEN INFERENCE_ENDPOINT RUNTIME_NAME \
  REGISTRY_USERNAME REGISTRY_PASSWORD \
  RUNTIME_SSH_USER RUNTIME_SSH_HOST RUNTIME_SSH_PORT \
  VLLM_BIN REMOTE_MODELS_ROOT VLLM_API_KEY \
  CALLBACK_URL CALLBACK_TOKEN
do
  [[ -n "${!variable:-}" ]] || {
    echo "Missing environment variable: ${variable}" >&2
    exit 1
  }
done

callback() {
  local result="$1"
  local endpoint="$2"

  curl -fsS --retry 5 --retry-delay 2 \
    -X POST \
    "${CALLBACK_URL}/api/v1/internal/runtime/deployments/${DEPLOYMENT_NAME}/status" \
    -H "X-Internal-Token: ${CALLBACK_TOKEN}" \
    -H 'Content-Type: application/json' \
    -d "$(
      jq -nc \
        --arg status "${result}" \
        --arg endpoint "${endpoint}" \
        --arg runtime "${RUNTIME_NAME}" \
        '{
          status:$status,
          endpoint:(if $endpoint=="" then null else $endpoint end),
          runtime:$runtime
        }'
    )"
}

on_error() {
  code="$?"
  trap - ERR
  callback failed "" || true
  exit "${code}"
}
trap on_error ERR

[[ "${MODEL_ID}" =~ ^[A-Za-z0-9._-]+$ ]]
[[ "${ARTIFACT_DIGEST}" =~ ^sha256:[0-9a-f]{64}$ ]]
[[ "${REMOTE_MODELS_ROOT}" =~ ^/[A-Za-z0-9._/-]+$ ]]
[[ "${VLLM_BIN}" =~ ^/[A-Za-z0-9._/-]+$ ]]

case "${ARTIFACT_REFERENCE}" in
  zot.registry.svc.cluster.local:5000/ai-models-trusted/*@sha256:*) ;;
  *)
    echo "Artifact outside trusted internal Zot namespace" >&2
    exit 1
    ;;
esac

REGISTRY="${ARTIFACT_REFERENCE%%/*}"
REST="${ARTIFACT_REFERENCE#*/}"
REPOSITORY="${REST%@*}"
REFERENCE_DIGEST="${REST##*@}"
[[ "${REFERENCE_DIGEST}" == "${ARTIFACT_DIGEST}" ]]

mkdir -p /tmp/ssh
cp /ssh-secret/id_ed25519 /tmp/ssh/id_ed25519
cp /ssh-secret/known_hosts /tmp/ssh/known_hosts
chmod 0600 /tmp/ssh/id_ed25519
chmod 0644 /tmp/ssh/known_hosts

SSH=(
  ssh
  -i /tmp/ssh/id_ed25519
  -o BatchMode=yes
  -o IdentitiesOnly=yes
  -o StrictHostKeyChecking=yes
  -o UserKnownHostsFile=/tmp/ssh/known_hosts
  -o ConnectTimeout=10
  -p "${RUNTIME_SSH_PORT}"
  "${RUNTIME_SSH_USER}@${RUNTIME_SSH_HOST}"
)

SCP=(
  scp
  -i /tmp/ssh/id_ed25519
  -o BatchMode=yes
  -o IdentitiesOnly=yes
  -o StrictHostKeyChecking=yes
  -o UserKnownHostsFile=/tmp/ssh/known_hosts
  -P "${RUNTIME_SSH_PORT}"
)

"${SSH[@]}" true

# Defense-in-depth: verify the exact immutable OCI artifact again.
cosign verify \
  --key /keys/cosign.pub \
  --insecure-ignore-tlog \
  --allow-insecure-registry \
  --registry-username "${REGISTRY_USERNAME}" \
  --registry-password "${REGISTRY_PASSWORD}" \
  "${ARTIFACT_REFERENCE}" \
  >/tmp/cosign.json

curl -fsS --retry 3 \
  -u "${REGISTRY_USERNAME}:${REGISTRY_PASSWORD}" \
  -H 'Accept: application/vnd.oci.image.manifest.v1+json' \
  "http://${REGISTRY}/v2/${REPOSITORY}/manifests/${ARTIFACT_DIGEST}" \
  > /tmp/manifest.json

MANIFEST_DIGEST="$(
  sha256sum /tmp/manifest.json | awk '{print "sha256:" $1}'
)"
[[ "${MANIFEST_DIGEST}" == "${ARTIFACT_DIGEST}" ]]

[[ "$(
  jq -er '.artifactType' /tmp/manifest.json
)" == "application/vnd.secureai.model.v1" ]]

MODEL_BLOB="$(
  jq -er '
    .layers[]
    | select(.mediaType=="application/vnd.secureai.model.tar")
    | .digest
  ' /tmp/manifest.json | head -1
)"

REPORT_BLOB="$(
  jq -er '
    .layers[]
    | select(.mediaType=="application/json")
    | .digest
  ' /tmp/manifest.json | head -1
)"

[[ "${MODEL_BLOB}" =~ ^sha256:[0-9a-f]{64}$ ]]
[[ "${REPORT_BLOB}" =~ ^sha256:[0-9a-f]{64}$ ]]

curl -fsS --retry 3 \
  -u "${REGISTRY_USERNAME}:${REGISTRY_PASSWORD}" \
  "http://${REGISTRY}/v2/${REPOSITORY}/blobs/${REPORT_BLOB}" \
  | jq -e . \
  > /tmp/security-report.json

DIGEST_HEX="${ARTIFACT_DIGEST#sha256:}"
REMOTE_VERSION_DIR="${REMOTE_MODELS_ROOT}/${MODEL_ID}/${DIGEST_HEX}"
REMOTE_MODEL_DIR="${REMOTE_VERSION_DIR}/model"
REMOTE_HOME="$("${SSH[@]}" 'printf %s "$HOME"')"
REMOTE_STATE_DIR="${REMOTE_HOME}/.local/state/ai-platform"

"${SSH[@]}" \
  "mkdir -p '${REMOTE_MODEL_DIR}' '${REMOTE_STATE_DIR}'"

REMOTE_MARKER="$(
  "${SSH[@]}" \
    "cat '${REMOTE_VERSION_DIR}/.artifact-digest' 2>/dev/null || true"
)"

READY_CACHE=0
if [[ "${REMOTE_MARKER}" == "${ARTIFACT_DIGEST}" ]]; then
  if "${SSH[@]}" \
    "test -f '${REMOTE_MODEL_DIR}/config.json' \
     && test -n \"\$(find '${REMOTE_MODEL_DIR}' -type f -name '*.safetensors' -print -quit)\""
  then
    READY_CACHE=1
  fi
fi

if [[ "${READY_CACHE}" != "1" ]]; then
  "${SSH[@]}" \
    "rm -rf '${REMOTE_MODEL_DIR}' && mkdir -p '${REMOTE_MODEL_DIR}'"

  # No 27GB tar is stored in the activation pod. The trusted blob
  # streams Zot -> Kubernetes Job -> SSH -> extraction on the isolated runtime.
  curl -fsS \
    -u "${REGISTRY_USERNAME}:${REGISTRY_PASSWORD}" \
    "http://${REGISTRY}/v2/${REPOSITORY}/blobs/${MODEL_BLOB}" \
  | "${SSH[@]}" \
      "tar -xf - -C '${REMOTE_MODEL_DIR}'"

  "${SSH[@]}" \
    "test -f '${REMOTE_MODEL_DIR}/config.json' \
     && test -n \"\$(find '${REMOTE_MODEL_DIR}' -type f -name '*.safetensors' -print -quit)\""

  "${SCP[@]}" \
    /tmp/security-report.json \
    "${RUNTIME_SSH_USER}@${RUNTIME_SSH_HOST}:${REMOTE_VERSION_DIR}/security-report.json"

  "${SSH[@]}" \
    "printf '%s\n' '${ARTIFACT_DIGEST}' > '${REMOTE_VERSION_DIR}/.artifact-digest'"
fi

# Switch the one native Metal runtime.
"${SSH[@]}" /bin/bash -s -- \
  "${VLLM_BIN}" \
  "${REMOTE_MODEL_DIR}" \
  "${MODEL_ID}" \
  "${VLLM_API_KEY}" \
  "${MAX_MODEL_LEN}" \
  "${REMOTE_STATE_DIR}" \
  "${ARTIFACT_DIGEST}" <<'REMOTE'
set -Eeuo pipefail

VLLM_BIN="$1"
MODEL_DIR="$2"
MODEL_ID="$3"
VLLM_API_KEY="$4"
MAX_MODEL_LEN="$5"
STATE_DIR="$6"
ARTIFACT_DIGEST="$7"

mkdir -p "${STATE_DIR}"

PID_FILE="${STATE_DIR}/vllm.pid"
MODEL_FILE="${STATE_DIR}/vllm.model"
DIGEST_FILE="${STATE_DIR}/vllm.digest"
LOG_FILE="${STATE_DIR}/vllm.log"

if [[ -f "${PID_FILE}" ]]; then
  PID="$(cat "${PID_FILE}" 2>/dev/null || true)"
  if [[ "${PID}" =~ ^[0-9]+$ ]]; then
    kill "${PID}" 2>/dev/null || true
    i=0
    while [[ "${i}" -lt 30 ]]; do
      kill -0 "${PID}" 2>/dev/null || break
      sleep 1
      i=$((i + 1))
    done
    kill -9 "${PID}" 2>/dev/null || true
  fi
fi

# Also removes an older manually started V1 process with no pidfile.
pkill -TERM -f "${VLLM_BIN} serve" 2>/dev/null || true
sleep 2

nohup env \
  HF_HUB_OFFLINE=1 \
  TRANSFORMERS_OFFLINE=1 \
  VLLM_PLUGINS=metal \
  "${VLLM_BIN}" serve \
  "${MODEL_DIR}" \
  --host 0.0.0.0 \
  --port 8000 \
  --served-model-name "${MODEL_ID}" \
  --api-key "${VLLM_API_KEY}" \
  --max-model-len "${MAX_MODEL_LEN}" \
  > "${LOG_FILE}" 2>&1 < /dev/null &

NEW_PID="$!"
printf '%s\n' "${NEW_PID}" > "${PID_FILE}"
printf '%s\n' "${MODEL_ID}" > "${MODEL_FILE}"
printf '%s\n' "${ARTIFACT_DIGEST}" > "${DIGEST_FILE}"
REMOTE

# Readiness = actual requested model exposed by vLLM.
READY=0
for _ in $(seq 1 450); do
  if PAYLOAD="$(
    curl -fsS \
      --connect-timeout 3 \
      --max-time 10 \
      -H "Authorization: Bearer ${VLLM_API_KEY}" \
      "${INFERENCE_ENDPOINT}/v1/models" \
      2>/dev/null
  )"
  then
    if jq -e \
      --arg model "${MODEL_ID}" \
      '.data[]? | select(.id==$model)' \
      >/dev/null <<<"${PAYLOAD}"
    then
      READY=1
      break
    fi
  fi
  sleep 2
done

if [[ "${READY}" != "1" ]]; then
  "${SSH[@]}" \
    "tail -200 '${REMOTE_STATE_DIR}/vllm.log' || true" \
    >&2
  exit 1
fi

callback ready "${INFERENCE_ENDPOINT}"
trap - ERR
echo "Runtime activation completed: ${MODEL_ID}"
