#!/usr/bin/env bash

set -u
set -o pipefail

NAMESPACE="ai-workloads"
POD="ai-runtime-netpol-test"
DENIED_POD="ai-runtime-denied-test"

FAILED=0


cleanup() {

    kubectl -n "${NAMESPACE}" delete pod \
      "${POD}" \
      --ignore-not-found \
      --wait=false \
      >/dev/null 2>&1 \
      || true

    kubectl -n default delete pod \
      "${DENIED_POD}" \
      --ignore-not-found \
      --wait=false \
      >/dev/null 2>&1 \
      || true
}

trap cleanup EXIT


echo "=================================================="
echo "Plateform AI - AI Runtime NetworkPolicy"
echo "=================================================="


# ==========================================================
# POLICY
# ==========================================================

echo
echo "== Active policy =="
echo

kubectl -n "${NAMESPACE}" get networkpolicy \
  ai-runtime


# ==========================================================
# CREATE FAKE RUNTIME
#
# Same selector used by dynamically created AI runtimes:
#
# managed-by=ai-control-plane
#
# BusyBox httpd listens on 8000 so we can validate ingress.
# ==========================================================

cleanup

kubectl -n "${NAMESPACE}" run \
  "${POD}" \
  --image=busybox:1.36 \
  --restart=Never \
  --labels='managed-by=ai-control-plane' \
  --command \
  -- sh -c '
      mkdir -p /www
      echo "AI_RUNTIME_NETWORK_OK" > /www/index.html
      httpd -f -p 8000 -h /www
  '


kubectl -n "${NAMESPACE}" wait \
  --for=condition=Ready \
  "pod/${POD}" \
  --timeout=60s


RUNTIME_IP="$(
    kubectl -n "${NAMESPACE}" get pod \
      "${POD}" \
      -o jsonpath='{.status.podIP}'
)"


echo
echo "Runtime IP: ${RUNTIME_IP}"


# ==========================================================
# TEST 1 - DNS
# ==========================================================

echo
echo "[TEST 1] Runtime -> Kubernetes DNS"
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
echo "[TEST 2] Runtime -> Zot:5000"
echo

if kubectl -n "${NAMESPACE}" exec \
    "${POD}" \
    -- nc -zvw3 \
      zot.registry.svc.cluster.local \
      5000
then

    echo "PASS: Zot:5000 allowed"

else

    echo "FAIL: Zot unavailable"
    FAILED=1

fi


# ==========================================================
# TEST 3 - INTERNET MUST BE BLOCKED
# ==========================================================

echo
echo "[TEST 3] Runtime -> Internet:443"
echo

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

    echo "PASS: Internet blocked"

else

    echo "FAIL: Runtime can access Internet"
    FAILED=1

fi


# ==========================================================
# TEST 4 - CONTROL PLANE -> RUNTIME
# ==========================================================

echo
echo "[TEST 4] Control Plane -> Runtime:8000"
echo

ACP_OUTPUT="$(
    kubectl -n ai-system exec \
      deployment/ai-control-plane \
      -c api \
      -- python -c "
import urllib.request

url = 'http://${RUNTIME_IP}:8000/'

with urllib.request.urlopen(
    url,
    timeout=5,
) as response:
    print(response.read().decode())
" \
      2>&1 \
      || true
)"

echo "${ACP_OUTPUT}"


if echo "${ACP_OUTPUT}" \
    | grep -q \
      'AI_RUNTIME_NETWORK_OK'
then

    echo "PASS: Control Plane -> Runtime allowed"

else

    echo "FAIL: Control Plane cannot reach Runtime"
    FAILED=1

fi


# ==========================================================
# TEST 5 - RANDOM POD MUST NOT REACH RUNTIME
# ==========================================================

echo
echo "[TEST 5] Unauthorized Pod -> Runtime:8000"
echo

kubectl -n default run \
  "${DENIED_POD}" \
  --image=busybox:1.36 \
  --restart=Never \
  --command \
  -- sh -c 'sleep 300'


kubectl -n default wait \
  --for=condition=Ready \
  "pod/${DENIED_POD}" \
  --timeout=60s


DENIED_OUTPUT="$(
    kubectl -n default exec \
      "${DENIED_POD}" \
      -- nc -zvw3 \
        "${RUNTIME_IP}" \
        8000 \
        2>&1 \
      || true
)"

echo "${DENIED_OUTPUT}"


if echo "${DENIED_OUTPUT}" \
    | grep -Eqi \
      'timed out|timeout|unreachable'
then

    echo "PASS: unauthorized Pod blocked"

else

    echo "FAIL: unauthorized Pod reached Runtime"
    FAILED=1

fi


# ==========================================================
# TEST 6 - PLATFORM HEALTH
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

    echo "AI RUNTIME NETWORKPOLICY PASSED"

else

    echo "AI RUNTIME NETWORKPOLICY FAILED"

    echo
    echo "Rollback:"
    echo "kubectl -n ai-workloads delete networkpolicy ai-runtime"

fi

echo "=================================================="

# Always return 0 to avoid terminating an interactive shell
# where 'set -e' may previously have been enabled.
exit 0
