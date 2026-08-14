#!/usr/bin/env bash
set -Eeuo pipefail

for variable in MODEL_ID RUNTIME_SSH_USER RUNTIME_SSH_HOST RUNTIME_SSH_PORT VLLM_BIN; do
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
  "${VLLM_BIN}" <<'REMOTE'
set -Eeuo pipefail
REQUESTED_MODEL="$1"
VLLM_BIN="$2"
STATE_DIR="${HOME}/.local/state/ai-platform"

ACTIVE_MODEL="$(cat "${STATE_DIR}/vllm.model" 2>/dev/null || true)"
if [[ -n "${ACTIVE_MODEL}" && "${ACTIVE_MODEL}" != "${REQUESTED_MODEL}" ]]; then
  exit 0
fi

PID="$(cat "${STATE_DIR}/vllm.pid" 2>/dev/null || true)"
if [[ "${PID}" =~ ^[0-9]+$ ]]; then
  kill "${PID}" 2>/dev/null || true
  sleep 2
  kill -9 "${PID}" 2>/dev/null || true
fi

pkill -TERM -f "${VLLM_BIN} serve" 2>/dev/null || true
rm -f \
  "${STATE_DIR}/vllm.pid" \
  "${STATE_DIR}/vllm.model" \
  "${STATE_DIR}/vllm.digest"
REMOTE
