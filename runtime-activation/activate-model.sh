#!/usr/bin/env bash
set -Eeuo pipefail

# ==========================================================
# COMMON REQUIRED ENVIRONMENT
# ==========================================================

for variable in \
  DEPLOYMENT_NAME MODEL_ID ARTIFACT_REFERENCE ARTIFACT_DIGEST \
  MAX_MODEL_LEN INFERENCE_ENDPOINT RUNTIME_NAME \
  REGISTRY_USERNAME REGISTRY_PASSWORD \
  RUNTIME_SSH_USER RUNTIME_SSH_HOST RUNTIME_SSH_PORT \
  REMOTE_MODELS_ROOT CALLBACK_URL CALLBACK_TOKEN
do
  [[ -n "${!variable:-}" ]] || {
    echo "Missing environment variable: ${variable}" >&2
    exit 1
  }
done


# ==========================================================
# RUNTIME-SPECIFIC CONFIGURATION
# ==========================================================

case "${RUNTIME_NAME}" in

  vllm-metal)
    : "${VLLM_BIN:?Missing VLLM_BIN}"
    : "${VLLM_API_KEY:?Missing VLLM_API_KEY}"

    RUNTIME_BIN="${VLLM_BIN}"
    RUNTIME_API_KEY="${VLLM_API_KEY}"
    STATE_PREFIX="vllm-metal"
    ;;

  llama-cpp-metal)
    : "${LLAMA_CPP_BIN:?Missing LLAMA_CPP_BIN}"
    : "${LLAMA_CPP_API_KEY:?Missing LLAMA_CPP_API_KEY}"

    RUNTIME_BIN="${LLAMA_CPP_BIN}"
    RUNTIME_API_KEY="${LLAMA_CPP_API_KEY}"
    STATE_PREFIX="llama-cpp-metal"
    ;;

  *)
    echo "Unsupported external runtime: ${RUNTIME_NAME}" >&2
    exit 1
    ;;
esac


# ==========================================================
# CALLBACK
# ==========================================================

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


# ==========================================================
# INPUT VALIDATION
# ==========================================================

[[ "${MODEL_ID}" =~ ^[A-Za-z0-9._-]+$ ]]
[[ "${ARTIFACT_DIGEST}" =~ ^sha256:[0-9a-f]{64}$ ]]
[[ "${REMOTE_MODELS_ROOT}" =~ ^/[A-Za-z0-9._/-]+$ ]]
[[ "${RUNTIME_BIN}" =~ ^/[A-Za-z0-9._/-]+$ ]]

case "${ARTIFACT_REFERENCE}" in
  zot.registry.svc.cluster.local:5000/ai-models-trusted/*@sha256:*) ;;
  *)
    echo "Artifact outside trusted internal Zot namespace" >&2
    exit 1
    ;;
esac


# ==========================================================
# OCI REFERENCE
# ==========================================================

REGISTRY="${ARTIFACT_REFERENCE%%/*}"
REST="${ARTIFACT_REFERENCE#*/}"
REPOSITORY="${REST%@*}"
REFERENCE_DIGEST="${REST##*@}"

[[ "${REFERENCE_DIGEST}" == "${ARTIFACT_DIGEST}" ]]


# ==========================================================
# SSH
# ==========================================================

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


# ==========================================================
# TRUST VERIFICATION
# ==========================================================

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
  >/tmp/manifest.json

MANIFEST_DIGEST="$(
  sha256sum /tmp/manifest.json | awk '{print "sha256:" $1}'
)"

[[ "${MANIFEST_DIGEST}" == "${ARTIFACT_DIGEST}" ]]

ARTIFACT_TYPE="$(
  jq -er '.artifactType' /tmp/manifest.json
)"

CANONICAL_ARTIFACT_TYPE="application/vnd.secureai.model.v1"
CANONICAL_MODEL_LAYER_TYPE="application/vnd.secureai.model.tar"

if [[ "${ARTIFACT_TYPE}" != "${CANONICAL_ARTIFACT_TYPE}" ]]; then
  if [[ -n "${LEGACY_MODEL_ARTIFACT_TYPE:-}" ]] &&
     [[ "${ARTIFACT_TYPE}" == "${LEGACY_MODEL_ARTIFACT_TYPE}" ]]; then

    echo "WARNING: accepting configured legacy OCI artifact type"

  else
    echo "Unexpected OCI artifact type: ${ARTIFACT_TYPE}" >&2
    exit 1
  fi
fi

MODEL_BLOB="$(
  jq -er     --arg canonical "${CANONICAL_MODEL_LAYER_TYPE}"     --arg legacy "${LEGACY_MODEL_LAYER_TYPE:-}" '
      .layers[]
      | select(
          .mediaType == $canonical
          or (
            ($legacy | length) > 0
            and .mediaType == $legacy
          )
        )
      | .digest
    ' /tmp/manifest.json   | head -1
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
  >/tmp/security-report.json


# ==========================================================
# REMOTE CACHE
# ==========================================================

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


# ==========================================================
# CACHE VALIDATION
# ==========================================================

READY_CACHE=0

if [[ "${REMOTE_MARKER}" == "${ARTIFACT_DIGEST}" ]]; then

  case "${RUNTIME_NAME}" in

    vllm-metal)
      if "${SSH[@]}" \
        "test -f '${REMOTE_MODEL_DIR}/config.json' \
         && test -n \"\$(find '${REMOTE_MODEL_DIR}' \
             -type f -name '*.safetensors' -print -quit)\""
      then
        READY_CACHE=1
      fi
      ;;

    llama-cpp-metal)
      if "${SSH[@]}" \
        "test -n \"\$(find '${REMOTE_MODEL_DIR}' \
           -type f \
           -name '*.gguf' \
           ! -name 'mmproj-*' \
           ! -name '*mmproj*' \
           -print -quit)\""
      then
        READY_CACHE=1
      fi
      ;;

  esac
fi


# ==========================================================
# MODEL DELIVERY
# ==========================================================

if [[ "${READY_CACHE}" != "1" ]]; then

  "${SSH[@]}" \
    "rm -rf '${REMOTE_MODEL_DIR}' \
     && mkdir -p '${REMOTE_MODEL_DIR}'"

  # Stream the trusted OCI model layer directly:
  #
  # Zot -> activation Job -> SSH -> isolated runtime
  #
  # The activation pod never stores the complete model tar.

  curl -fsS \
    -u "${REGISTRY_USERNAME}:${REGISTRY_PASSWORD}" \
    "http://${REGISTRY}/v2/${REPOSITORY}/blobs/${MODEL_BLOB}" \
  | "${SSH[@]}" \
      "tar -xf - -C '${REMOTE_MODEL_DIR}'"

  case "${RUNTIME_NAME}" in

    vllm-metal)
      "${SSH[@]}" \
        "test -f '${REMOTE_MODEL_DIR}/config.json' \
         && test -n \"\$(find '${REMOTE_MODEL_DIR}' \
             -type f -name '*.safetensors' -print -quit)\""
      ;;

    llama-cpp-metal)
      "${SSH[@]}" \
        "test -n \"\$(find '${REMOTE_MODEL_DIR}' \
           -type f \
           -name '*.gguf' \
           ! -name 'mmproj-*' \
           ! -name '*mmproj*' \
           -print -quit)\""
      ;;

  esac

  "${SCP[@]}" \
    /tmp/security-report.json \
    "${RUNTIME_SSH_USER}@${RUNTIME_SSH_HOST}:${REMOTE_VERSION_DIR}/security-report.json"

  "${SSH[@]}" \
    "printf '%s\n' '${ARTIFACT_DIGEST}' \
      > '${REMOTE_VERSION_DIR}/.artifact-digest'"
fi


# ==========================================================
# VLLM METAL
# ==========================================================

if [[ "${RUNTIME_NAME}" == "vllm-metal" ]]; then

  # ======================================================
  # SECURE VLLM API KEY
  # ======================================================
  #
  # Transfer the secret through stdin.
  # The secret never becomes an SSH command argument.
  printf '%s\n' "${VLLM_API_KEY}" \
    | "${SSH[@]}" \
      'umask 077; mkdir -p "$HOME/ai-platform/secrets"; chmod 700 "$HOME/ai-platform/secrets"; cat > "$HOME/ai-platform/secrets/vllm-api-key"; chmod 600 "$HOME/ai-platform/secrets/vllm-api-key"'

  "${SSH[@]}" /bin/bash -s -- \
    "${VLLM_BIN}" \
    "${REMOTE_MODEL_DIR}" \
    "${MODEL_ID}" \
    "ai-platform/secrets/vllm-api-key" \
    "${MAX_MODEL_LEN}" \
    "${REMOTE_STATE_DIR}" \
    "${ARTIFACT_DIGEST}" <<'REMOTE'
set -Eeuo pipefail

VLLM_BIN="$1"
MODEL_DIR="$2"
MODEL_ID="$3"
API_KEY_FILE="${HOME}/${4}"
export VLLM_API_KEY="$(cat "${API_KEY_FILE}")"
MAX_MODEL_LEN="$5"
STATE_DIR="$6"
ARTIFACT_DIGEST="$7"

PREFIX="vllm-metal"

PID_FILE="${STATE_DIR}/${PREFIX}.pid"
MODEL_FILE="${STATE_DIR}/${PREFIX}.model"
DIGEST_FILE="${STATE_DIR}/${PREFIX}.digest"
LOG_FILE="${STATE_DIR}/${PREFIX}.log"

if [[ -f "${PID_FILE}" ]]; then
  PID="$(cat "${PID_FILE}" 2>/dev/null || true)"

  if [[ "${PID}" =~ ^[0-9]+$ ]]; then
    kill "${PID}" 2>/dev/null || true

    for _ in $(seq 1 30); do
      kill -0 "${PID}" 2>/dev/null || break
      sleep 1
    done

    kill -9 "${PID}" 2>/dev/null || true
  fi
fi

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
  --max-model-len "${MAX_MODEL_LEN}" \
  >"${LOG_FILE}" 2>&1 </dev/null &

NEW_PID="$!"

printf '%s\n' "${NEW_PID}" >"${PID_FILE}"
printf '%s\n' "${MODEL_ID}" >"${MODEL_FILE}"
printf '%s\n' "${ARTIFACT_DIGEST}" >"${DIGEST_FILE}"
REMOTE
fi


# ==========================================================
# LLAMA.CPP METAL
# ==========================================================

if [[ "${RUNTIME_NAME}" == "llama-cpp-metal" ]]; then

  # ======================================================
  # SECURE LLAMA.CPP API KEY
  # ======================================================
  #
  # Transfer the secret through stdin instead of argv.
  printf '%s\n' "${LLAMA_CPP_API_KEY}" \
    | "${SSH[@]}" \
      'umask 077; mkdir -p "$HOME/ai-platform/secrets"; chmod 700 "$HOME/ai-platform/secrets"; cat > "$HOME/ai-platform/secrets/llama-api-key"; chmod 600 "$HOME/ai-platform/secrets/llama-api-key"'

  "${SSH[@]}" /bin/bash -s -- \
    "${LLAMA_CPP_BIN}" \
    "${REMOTE_MODEL_DIR}" \
    "${MODEL_ID}" \
    "ai-platform/secrets/llama-api-key" \
    "${MAX_MODEL_LEN}" \
    "${REMOTE_STATE_DIR}" \
    "${ARTIFACT_DIGEST}" <<'REMOTE'
set -Eeuo pipefail

LLAMA_CPP_BIN="$1"
MODEL_DIR="$2"
MODEL_ID="$3"
API_KEY_FILE="${HOME}/${4}"
MAX_MODEL_LEN="$5"
STATE_DIR="$6"
ARTIFACT_DIGEST="$7"

PREFIX="llama-cpp-metal"

PID_FILE="${STATE_DIR}/${PREFIX}.pid"
MODEL_FILE="${STATE_DIR}/${PREFIX}.model"
DIGEST_FILE="${STATE_DIR}/${PREFIX}.digest"
LOG_FILE="${STATE_DIR}/${PREFIX}.log"

GGUF_MODEL="$(
  find "${MODEL_DIR}" \
    -type f \
    -name '*.gguf' \
    ! -name 'mmproj-*' \
    ! -name '*mmproj*' \
    -print \
  | head -1
)"

if [[ -z "${GGUF_MODEL}" ]]; then
  echo "No primary GGUF model found" >&2
  exit 1
fi

if [[ -f "${PID_FILE}" ]]; then
  PID="$(cat "${PID_FILE}" 2>/dev/null || true)"

  if [[ "${PID}" =~ ^[0-9]+$ ]]; then
    kill "${PID}" 2>/dev/null || true

    for _ in $(seq 1 30); do
      kill -0 "${PID}" 2>/dev/null || break
      sleep 1
    done

    kill -9 "${PID}" 2>/dev/null || true
  fi
fi

pkill -TERM -f "${LLAMA_CPP_BIN}" 2>/dev/null || true
sleep 2

nohup env \
  LLAMA_ARG_API_KEY_FILE="${API_KEY_FILE}" \
  "${LLAMA_CPP_BIN}" \
  --model "${GGUF_MODEL}" \
  --host 0.0.0.0 \
  --port 8081 \
  --alias "${MODEL_ID}" \
  --ctx-size "${MAX_MODEL_LEN}" \
  --n-gpu-layers 99 \
  --no-webui \
  >"${LOG_FILE}" 2>&1 </dev/null &

NEW_PID="$!"

printf '%s\n' "${NEW_PID}" >"${PID_FILE}"
printf '%s\n' "${MODEL_ID}" >"${MODEL_FILE}"
printf '%s\n' "${ARTIFACT_DIGEST}" >"${DIGEST_FILE}"
REMOTE
fi


# ==========================================================
# READINESS
# ==========================================================

READY=0

for _ in $(seq 1 450); do

  if PAYLOAD="$(
    curl -fsS \
      --connect-timeout 3 \
      --max-time 10 \
      -H "Authorization: Bearer ${RUNTIME_API_KEY}" \
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
    "tail -200 '${REMOTE_STATE_DIR}/${STATE_PREFIX}.log' || true" \
    >&2

  exit 1
fi


# ==========================================================
# SUCCESS
# ==========================================================

callback ready "${INFERENCE_ENDPOINT}"

trap - ERR

echo "Runtime activation completed: ${MODEL_ID} via ${RUNTIME_NAME}"
