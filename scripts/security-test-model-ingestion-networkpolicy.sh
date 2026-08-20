#!/usr/bin/env bash

set -u
set -o pipefail

NAMESPACE="ai-workloads"
POD="model-ingestion-netpol-test"

FAILED=0


cleanup() {
    kubectl -n "${NAMESPACE}" delete pod \
      "${POD}" \
      --ignore-not-found \
      --wait=false \
      >/dev/null 2>&1 \
      || true
}

trap cleanup EXIT


echo "=================================================="
echo "Plateform AI - Model Ingestion NetworkPolicy"
echo "=================================================="


# ==========================================================
# POLICY
# ==========================================================

echo
echo "== Active policy =="
echo

kubectl -n "${NAMESPACE}" get networkpolicy \
  model-ingestion-egress


# ==========================================================
# CREATE TEST POD
# ==========================================================

cleanup

kubectl -n "${NAMESPACE}" run \
  "${POD}" \
  --image=busybox:1.36 \
  --restart=Never \
  --labels='app.kubernetes.io/name=model-ingestion' \
  --command \
  -- sh -c 'sleep 300'


kubectl -n "${NAMESPACE}" wait \
  --for=condition=Ready \
  "pod/${POD}" \
  --timeout=60s


# ==========================================================
# TEST 1 - DNS
# ==========================================================

echo
echo "[TEST 1] Kubernetes DNS"
echo

if kubectl -n "${NAMESPACE}" exec \
    "${POD}" \
    -- nslookup \
      huggingface.co
then

    echo "PASS: DNS allowed"

else

    echo "FAIL: DNS unavailable"
    FAILED=1

fi


# ==========================================================
# TEST 2 - POSTGRESQL
# ==========================================================

echo
echo "[TEST 2] Model Ingestion -> PostgreSQL"
echo

if kubectl -n "${NAMESPACE}" exec \
    "${POD}" \
    -- nc -zvw3 \
      postgres.ai-system.svc.cluster.local \
      5432
then

    echo "PASS: PostgreSQL:5432 allowed"

else

    echo "FAIL: PostgreSQL unavailable"
    FAILED=1

fi


# ==========================================================
# TEST 3 - HTTPS INTERNET
#
# Model ingestion currently needs HTTPS access to remote
# model providers such as Hugging Face.
# ==========================================================

echo
echo "[TEST 3] HTTPS -> Hugging Face"
echo

if kubectl -n "${NAMESPACE}" exec \
    "${POD}" \
    -- nc -zvw5 \
      huggingface.co \
      443
then

    echo "PASS: HTTPS model-provider access allowed"

else

    echo "FAIL: HTTPS model-provider access unavailable"
    FAILED=1

fi


# ==========================================================
# TEST 4 - HTTP INTERNET MUST BE BLOCKED
# ==========================================================

echo
echo "[TEST 4] Internet HTTP :80 must be blocked"
echo

HTTP_OUTPUT="$(
  kubectl -n "${NAMESPACE}" exec \
    "${POD}" \
    -- nc -zvw3 \
      1.1.1.1 \
      80 \
      2>&1 \
    || true
)"

echo "${HTTP_OUTPUT}"

if echo "${HTTP_OUTPUT}" \
  | grep -Eqi \
    'timed out|timeout|unreachable'
then

    echo "PASS: Internet :80 blocked"

else

    echo "FAIL: Internet :80 may be allowed"
    FAILED=1

fi


# ==========================================================
# TEST 5 - ZOT MUST NOT BE ACCESSIBLE
# ==========================================================

echo
echo "[TEST 5] Model Ingestion -> Zot must be blocked"
echo

ZOT_OUTPUT="$(
  kubectl -n "${NAMESPACE}" exec \
    "${POD}" \
    -- nc -zvw3 \
      zot.registry.svc.cluster.local \
      5000 \
      2>&1 \
    || true
)"

echo "${ZOT_OUTPUT}"

if echo "${ZOT_OUTPUT}" \
  | grep -Eqi \
    'timed out|timeout|unreachable'
then

    echo "PASS: Zot blocked for ingestion"

else

    echo "FAIL: ingestion can reach Zot"
    FAILED=1

fi


# ==========================================================
# TEST 6 - CONTROL PLANE INTERNAL API MUST BE BLOCKED
# ==========================================================

echo
echo "[TEST 6] Model Ingestion -> internal Control Plane"
echo

ACP_OUTPUT="$(
  kubectl -n "${NAMESPACE}" exec \
    "${POD}" \
    -- nc -zvw3 \
      ai-control-plane-internal.ai-system.svc.cluster.local \
      8080 \
      2>&1 \
    || true
)"

echo "${ACP_OUTPUT}"

if echo "${ACP_OUTPUT}" \
  | grep -Eqi \
    'timed out|timeout|unreachable'
then

    echo "PASS: internal Control Plane blocked"

else

    echo "FAIL: ingestion can reach internal Control Plane"
    FAILED=1

fi


# ==========================================================
# PLATFORM HEALTH
# ==========================================================

echo
echo "[TEST 7] Plateform AI health"
echo

HTTP_CODE="$(
  curl -k -s \
    -o /dev/null \
    -w '%{http_code}' \
    https://api.ai.local/docs
)"

echo "API HTTP=${HTTP_CODE}"

if [[ "${HTTP_CODE}" == "200" ]]; then

    echo "PASS: Control Plane healthy"

else

    echo "FAIL: Control Plane unhealthy"
    FAILED=1

fi


# ==========================================================
# RESULT
# ==========================================================

echo
echo "=================================================="

if [[ "${FAILED}" -eq 0 ]]; then

    echo "MODEL INGESTION NETWORKPOLICY PASSED"

else

    echo "MODEL INGESTION NETWORKPOLICY FAILED"

    echo
    echo "Rollback:"
    echo "kubectl -n ai-workloads delete networkpolicy model-ingestion-egress"

fi

echo "=================================================="

# Do not terminate an interactive shell configured with set -e.
exit 0
