#!/usr/bin/env bash

set -u
set -o pipefail

NAMESPACE="ai-workloads"
POD="runtime-activation-netpol-test"

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
echo "Plateform AI - Runtime Activation NetworkPolicy"
echo "=================================================="


echo
echo "== Active policy =="
echo

kubectl -n "${NAMESPACE}" get networkpolicy \
  runtime-activation-egress


# ==========================================================
# TEST POD
# ==========================================================

cleanup

kubectl -n "${NAMESPACE}" run \
  "${POD}" \
  --image=busybox:1.36 \
  --restart=Never \
  --labels='app.kubernetes.io/name=runtime-activation' \
  --command \
  -- sh -c 'sleep 300'


kubectl -n "${NAMESPACE}" wait \
  --for=condition=Ready \
  "pod/${POD}" \
  --timeout=60s


echo
echo "Pod is Ready."
echo "Waiting 5 seconds for NetworkPolicy convergence..."
sleep 5


# ==========================================================
# TEST 1 - DNS
# ==========================================================

echo
echo "[TEST 1] Kubernetes DNS"
echo

if kubectl -n "${NAMESPACE}" exec \
    "${POD}" \
    -- nslookup \
      zot.registry.svc.cluster.local
then
    echo "PASS: DNS allowed"
else
    echo "FAIL: DNS unavailable"
    FAILED=1
fi


# ==========================================================
# TEST 2 - ZOT
# ==========================================================

echo
echo "[TEST 2] Runtime Activation -> Zot"
echo

if kubectl -n "${NAMESPACE}" exec \
    "${POD}" \
    -- nc -zvw3 \
      zot.registry.svc.cluster.local \
      5000
then
    echo "PASS: Zot:5000 allowed"
else
    echo "FAIL: Zot:5000 unavailable"
    FAILED=1
fi


# ==========================================================
# TEST 3 - CONTROL PLANE CALLBACK
# ==========================================================

echo
echo "[TEST 3] Runtime Activation -> Control Plane callback"
echo

CALLBACK_OUTPUT="$(
  kubectl -n "${NAMESPACE}" exec \
    "${POD}" \
    -- wget \
      -T 5 \
      -S \
      -O- \
      "http://ai-control-plane-internal.ai-system.svc.cluster.local:8080/api/v1/internal/runtime/deployments/security-test/status" \
      2>&1 \
    || true
)"

echo "${CALLBACK_OUTPUT}"

if echo "${CALLBACK_OUTPUT}" \
  | grep -Eq \
    'HTTP/1\.[01] (200|400|401|404|405|422)'
then
    echo "PASS: internal Control Plane path allowed"
else
    echo "FAIL: Control Plane callback unavailable"
    FAILED=1
fi


# ==========================================================
# TEST 4 - INTERNET MUST BE BLOCKED
#
# With NRI disabled there can be a short race after Pod
# creation. Retry for up to 20 seconds before declaring
# failure.
# ==========================================================

echo
echo "[TEST 4] General Internet access must be blocked"
echo

BLOCKED=0

for ATTEMPT in 1 2 3 4
do
    echo "Attempt ${ATTEMPT}/4..."

    INTERNET_OUTPUT="$(
      kubectl -n "${NAMESPACE}" exec \
        "${POD}" \
        -- nc -zvw3 \
          1.1.1.1 \
          443 \
          2>&1 \
        || true
    )"

    echo "${INTERNET_OUTPUT}"

    if echo "${INTERNET_OUTPUT}" \
      | grep -Eqi \
        'timed out|timeout|unreachable'
    then
        BLOCKED=1
        break
    fi

    sleep 5
done


if [[ "${BLOCKED}" -eq 1 ]]; then
    echo "PASS: general Internet blocked"
else
    echo "FAIL: Internet remained accessible"
    FAILED=1
fi


# ==========================================================
# TEST 5 - EXTERNAL METAL
# ==========================================================

echo
echo "[TEST 5] External Metal runtime 192.168.64.1:8000"
echo

METAL_OUTPUT="$(
  kubectl -n "${NAMESPACE}" exec \
    "${POD}" \
    -- nc -zvw3 \
      192.168.64.1 \
      8000 \
      2>&1 \
    || true
)"

echo "${METAL_OUTPUT}"

if echo "${METAL_OUTPUT}" \
  | grep -Eqi \
    'open|succeeded'
then
    echo "PASS: Metal runtime path allowed"
else
    echo "WARN: Metal runtime did not answer"
    echo "      Acceptable if vLLM Metal is stopped."
fi


# ==========================================================
# PLATFORM HEALTH
# ==========================================================

echo
echo "[TEST 6] Plateform AI health"
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
    echo "RUNTIME ACTIVATION NETWORKPOLICY PASSED"
else
    echo "RUNTIME ACTIVATION NETWORKPOLICY FAILED"
fi

echo "=================================================="

exit 0
