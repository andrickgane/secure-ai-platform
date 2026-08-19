#!/usr/bin/env bash
set -Eeuo pipefail

for variable in \
  MODEL_ID \
  RUNTIME_SSH_USER \
  RUNTIME_SSH_HOST \
  RUNTIME_SSH_PORT \
  VLLM_BIN \
  LLAMA_CPP_BIN
do
  [[ -n "${!variable:-}" ]] || {
    echo "Missing environment variable: ${variable}" >&2
    exit 1
  }
done

mkdir -p /tmp/ssh

cp /ssh-secret/id_ed25519 /tmp/ssh/id_ed25519
cp /ssh-secret/known_hosts /tmp/ssh/known_hosts

chmod 0600 /tmp/ssh/id_ed25519
chmod 0644 /tmp/ssh/known_hosts

ssh \
  -i /tmp/ssh/id_ed25519 \
  -o BatchMode=yes \
  -o IdentitiesOnly=yes \
  -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile=/tmp/ssh/known_hosts \
  -o ConnectTimeout=10 \
  -p "${RUNTIME_SSH_PORT}" \
  "${RUNTIME_SSH_USER}@${RUNTIME_SSH_HOST}" \
  /bin/bash -s -- \
  "${MODEL_ID}" \
  "${VLLM_BIN}" \
  "${LLAMA_CPP_BIN}" <<'REMOTE'
set -Eeuo pipefail

REQUESTED_MODEL="$1"
VLLM_BIN="$2"
LLAMA_CPP_BIN="$3"

STATE_DIR="${HOME}/.local/state/ai-platform"

deactivate_runtime() {
  local prefix="$1"
  local process_pattern="$2"

  local model_file="${STATE_DIR}/${prefix}.model"
  local pid_file="${STATE_DIR}/${prefix}.pid"
  local digest_file="${STATE_DIR}/${prefix}.digest"

  local active_model=""
  active_model="$(cat "${model_file}" 2>/dev/null || true)"

  # Do not stop another deployed model.
  if [[ -n "${active_model}" && "${active_model}" != "${REQUESTED_MODEL}" ]]; then
    return 0
  fi

  local pid=""
  pid="$(cat "${pid_file}" 2>/dev/null || true)"

  if [[ "${pid}" =~ ^[0-9]+$ ]]; then
    kill "${pid}" 2>/dev/null || true

    for _ in $(seq 1 10); do
      kill -0 "${pid}" 2>/dev/null || break
      sleep 1
    done

    kill -9 "${pid}" 2>/dev/null || true
  fi

  if [[ -n "${process_pattern}" ]]; then
    pkill -TERM -f "${process_pattern}" 2>/dev/null || true
  fi

  rm -f \
    "${pid_file}" \
    "${model_file}" \
    "${digest_file}"
}

deactivate_runtime \
  "vllm-metal" \
  "${VLLM_BIN} serve"

deactivate_runtime \
  "llama-cpp-metal" \
  "${LLAMA_CPP_BIN}"
REMOTE
