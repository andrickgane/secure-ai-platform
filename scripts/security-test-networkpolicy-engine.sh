#!/usr/bin/env bash

set -u
set -o pipefail


NAMESPACE="ai-system"
SERVICE="ai-control-plane-internal"

FAILED=0


echo "=================================================="
echo "Plateform AI - NetworkPolicy Enforcement Test"
echo "=================================================="


# ==========================================================
# CURRENT STATE
# ==========================================================

echo
echo "== Current NetworkPolicies =="
echo

kubectl get networkpolicy -A


echo
echo "== NetworkPolicy agents =="
echo

kubectl -n kube-system get daemonset \
  kube-network-policies


# ==========================================================
# CONTROL PLANE SERVICE
# ==========================================================

CONTROL_PLANE_IP="$(
  kubectl -n "${NAMESPACE}" \
    get service "${SERVICE}" \
    -o jsonpath='{.spec.clusterIP}'
)"


echo
echo "Control Plane Service IP: ${CONTROL_PLANE_IP}"


# ==========================================================
# TEST 1
#
# ingress-nginx must reach the Control Plane.
# ==========================================================

echo
echo "[TEST 1] ingress-nginx -> Control Plane"
echo


HTTP_CODE="$(
  curl -k -s \
    -o /dev/null \
    -w '%{http_code}' \
    https://api.ai.local/docs
)"


echo "HTTP=${HTTP_CODE}"


if [[ "${HTTP_CODE}" == "200" ]]; then

    echo "PASS: ingress-nginx is allowed"

else

    echo "FAIL: public API unavailable"
    FAILED=1

fi


# ==========================================================
# TEST 2
#
# Arbitrary Pod must NOT reach the internal Control Plane.
# ==========================================================

echo
echo "[TEST 2] unauthorized Pod -> Control Plane"
echo


kubectl -n default delete pod \
  netpol-denied-test \
  --ignore-not-found \
  --wait=true \
  >/dev/null 2>&1 \
  || true


kubectl -n default run \
  netpol-denied-test \
  --image=busybox:1.36 \
  --restart=Never \
  --command \
  -- sh -c 'sleep 120' \
  >/dev/null


kubectl -n default wait \
  --for=condition=Ready \
  pod/netpol-denied-test \
  --timeout=60s \
  >/dev/null


DENIED_OUTPUT="$(
  kubectl -n default exec \
    netpol-denied-test \
    -- \
    wget \
      -T 3 \
      -qO- \
      "http://${CONTROL_PLANE_IP}:8080/api/v1/auth/me" \
      2>&1 \
    || true
)"


echo "${DENIED_OUTPUT}"


if echo "${DENIED_OUTPUT}" \
    | grep -Eqi \
      'timed out|timeout|connection refused|network is unreachable'
then

    echo "PASS: unauthorized Pod is blocked"

else

    echo "FAIL: unauthorized Pod may have reached Control Plane"
    FAILED=1

fi


kubectl -n default delete pod \
  netpol-denied-test \
  --wait=false \
  >/dev/null 2>&1 \
  || true


# ==========================================================
# TEST 3
#
# runtime-activation-labelled Pod must have a network path
# to the internal Control Plane.
#
# Any HTTP response proves that the NetworkPolicy allowed
# the TCP connection.
#
# 401 = application authentication rejected it.
# 404 = application processed the request but target/path
#       does not exist.
# 405 = endpoint exists but HTTP method is not accepted.
#
# All three prove network connectivity.
# ==========================================================

echo
echo "[TEST 3] runtime-activation -> internal Control Plane"
echo


kubectl -n ai-workloads delete pod \
  netpol-runtime-test \
  --ignore-not-found \
  --wait=true \
  >/dev/null 2>&1 \
  || true


kubectl -n ai-workloads run \
  netpol-runtime-test \
  --image=busybox:1.36 \
  --restart=Never \
  --labels='app.kubernetes.io/name=runtime-activation' \
  --command \
  -- sh -c 'sleep 120' \
  >/dev/null


kubectl -n ai-workloads wait \
  --for=condition=Ready \
  pod/netpol-runtime-test \
  --timeout=60s \
  >/dev/null


ALLOWED_OUTPUT="$(
  kubectl -n ai-workloads exec \
    netpol-runtime-test \
    -- \
    wget \
      -T 5 \
      -S \
      -O- \
      "http://${CONTROL_PLANE_IP}:8080/api/v1/internal/runtime/deployments/security-test/status" \
      2>&1 \
    || true
)"


echo "${ALLOWED_OUTPUT}"


if echo "${ALLOWED_OUTPUT}" \
    | grep -Eq \
      'HTTP/1\.[01] (401|404|405)'
then

    echo "PASS: runtime-activation network path is allowed"

else

    echo "FAIL: runtime-activation network path not confirmed"
    FAILED=1

fi


kubectl -n ai-workloads delete pod \
  netpol-runtime-test \
  --wait=false \
  >/dev/null 2>&1 \
  || true


# ==========================================================
# TEST 4
#
# Control Plane -> PostgreSQL
# ==========================================================

echo
echo "[TEST 4] Control Plane -> PostgreSQL"
echo


if kubectl -n ai-system exec -i \
    deployment/ai-control-plane \
    -c api \
    -- python - <<'PY'
import socket

with socket.create_connection(
    (
        "postgres.ai-system.svc.cluster.local",
        5432,
    ),
    timeout=5,
):
    print("POSTGRES = OK")
PY

then

    echo "PASS: PostgreSQL reachable"

else

    echo "FAIL: PostgreSQL unreachable"
    FAILED=1

fi


# ==========================================================
# RESULT
# ==========================================================

echo
echo "=================================================="


if [[ "${FAILED}" -ne 0 ]]; then

    echo "NETWORKPOLICY ENFORCEMENT TEST FAILED"
    echo "=================================================="

    exit 1

fi


echo "NETWORKPOLICY ENFORCEMENT TEST PASSED"
echo "=================================================="

exit 0
