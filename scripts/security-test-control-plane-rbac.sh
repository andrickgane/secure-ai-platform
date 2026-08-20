#!/usr/bin/env bash

set -u
set -o pipefail


SA="system:serviceaccount:ai-system:ai-control-plane"
NAMESPACE="ai-workloads"

FAILED=0


# ==========================================================
# RBAC TEST FUNCTION
# ==========================================================

test_permission() {

    local expected="$1"
    shift

    local result

    # kubectl auth can-i exits with:
    #
    # 0 => yes
    # 1 => no
    #
    # Both are legitimate outcomes for this security test,
    # therefore we must not allow `set -e` semantics here.

    result="$(
        kubectl auth can-i \
          "$@" \
          --as="${SA}" \
          2>/dev/null \
        || true
    )"

    printf "%-58s expected=%-3s actual=%s\n" \
        "$*" \
        "${expected}" \
        "${result}"

    if [[ "${result}" != "${expected}" ]]; then

        echo "  -> SECURITY TEST FAILED"

        FAILED=1
    fi
}


# ==========================================================
# HEADER
# ==========================================================

echo "=================================================="
echo "Plateform AI - Control Plane RBAC Security Test"
echo "=================================================="


# ==========================================================
# ALLOWED PERMISSIONS
# ==========================================================

echo
echo "ALLOWED:"
echo

test_permission yes \
  create jobs.batch \
  -n "${NAMESPACE}"

test_permission yes \
  get jobs.batch \
  -n "${NAMESPACE}"

test_permission yes \
  list jobs.batch \
  -n "${NAMESPACE}"

test_permission yes \
  delete jobs.batch \
  -n "${NAMESPACE}"

test_permission yes \
  create deployments.apps \
  -n "${NAMESPACE}"

test_permission yes \
  get deployments.apps \
  -n "${NAMESPACE}"

test_permission yes \
  delete deployments.apps \
  -n "${NAMESPACE}"

test_permission yes \
  create services \
  -n "${NAMESPACE}"

test_permission yes \
  get services \
  -n "${NAMESPACE}"

test_permission yes \
  delete services \
  -n "${NAMESPACE}"

test_permission yes \
  get pods \
  -n "${NAMESPACE}"

test_permission yes \
  list pods \
  -n "${NAMESPACE}"

test_permission yes \
  get nodes

test_permission yes \
  list nodes


# ==========================================================
# FORBIDDEN PERMISSIONS
# ==========================================================

echo
echo "DENIED:"
echo


# ----------------------------------------------------------
# Secrets
# ----------------------------------------------------------

test_permission no \
  get secrets \
  -n "${NAMESPACE}"

test_permission no \
  list secrets \
  -n "${NAMESPACE}"

test_permission no \
  create secrets \
  -n "${NAMESPACE}"

test_permission no \
  patch secrets \
  -n "${NAMESPACE}"

test_permission no \
  delete secrets \
  -n "${NAMESPACE}"


# ----------------------------------------------------------
# ConfigMaps
# ----------------------------------------------------------

test_permission no \
  create configmaps \
  -n "${NAMESPACE}"

test_permission no \
  patch configmaps \
  -n "${NAMESPACE}"

test_permission no \
  delete configmaps \
  -n "${NAMESPACE}"


# ----------------------------------------------------------
# Persistent storage
# ----------------------------------------------------------

test_permission no \
  create persistentvolumeclaims \
  -n "${NAMESPACE}"

test_permission no \
  patch persistentvolumeclaims \
  -n "${NAMESPACE}"

test_permission no \
  delete persistentvolumeclaims \
  -n "${NAMESPACE}"


# ----------------------------------------------------------
# Direct Pod mutation
# ----------------------------------------------------------

test_permission no \
  create pods \
  -n "${NAMESPACE}"

test_permission no \
  delete pods \
  -n "${NAMESPACE}"

test_permission no \
  patch pods \
  -n "${NAMESPACE}"


# ----------------------------------------------------------
# Remote command execution
# ----------------------------------------------------------

test_permission no \
  create pods/exec \
  -n "${NAMESPACE}"

test_permission no \
  create pods/attach \
  -n "${NAMESPACE}"

test_permission no \
  create pods/portforward \
  -n "${NAMESPACE}"


# ----------------------------------------------------------
# Kubernetes RBAC escalation
# ----------------------------------------------------------

test_permission no \
  create roles.rbac.authorization.k8s.io \
  -n "${NAMESPACE}"

test_permission no \
  create rolebindings.rbac.authorization.k8s.io \
  -n "${NAMESPACE}"

test_permission no \
  create clusterroles.rbac.authorization.k8s.io

test_permission no \
  create clusterrolebindings.rbac.authorization.k8s.io


# ----------------------------------------------------------
# Namespace / node mutation
# ----------------------------------------------------------

test_permission no \
  create namespaces

test_permission no \
  patch nodes

test_permission no \
  delete nodes


# ==========================================================
# RESULT
# ==========================================================

echo
echo "=================================================="

if [[ "${FAILED}" -ne 0 ]]; then

    echo "RBAC SECURITY TEST FAILED"
    echo "=================================================="

    exit 1
fi

echo "RBAC SECURITY TEST PASSED"
echo "=================================================="

exit 0
