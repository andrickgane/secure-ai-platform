#!/usr/bin/env bash

set -euo pipefail


echo "=================================================="
echo "Plateform AI - Legacy RBAC cleanup"
echo "=================================================="


# ==========================================================
# LEGACY NAMESPACED RBAC
# ==========================================================

echo
echo "[1/5] Removing legacy ai-workloads Control Plane RBAC..."

kubectl -n ai-workloads delete rolebinding \
  ai-control-plane \
  --ignore-not-found

kubectl -n ai-workloads delete role \
  ai-control-plane \
  --ignore-not-found


# ==========================================================
# LEGACY RUNTIME ORCHESTRATOR
#
# Replaced by:
# Role/ai-control-plane-workloads
# RoleBinding/ai-control-plane-workloads
# ==========================================================

echo
echo "[2/5] Removing redundant runtime orchestrator RBAC..."

kubectl -n ai-workloads delete rolebinding \
  ai-control-plane-runtime-orchestrator \
  --ignore-not-found

kubectl -n ai-workloads delete role \
  ai-control-plane-runtime-orchestrator \
  --ignore-not-found


# ==========================================================
# LEGACY NODE READER
#
# Replaced by:
# ClusterRole/ai-control-plane-capacity-reader
# ClusterRoleBinding/ai-control-plane-capacity-reader
# ==========================================================

echo
echo "[3/5] Removing legacy node reader..."

kubectl delete clusterrolebinding \
  ai-control-plane-node-reader \
  --ignore-not-found

kubectl delete clusterrole \
  ai-control-plane-node-reader \
  --ignore-not-found


# ==========================================================
# LEGACY SERVICE ACCOUNT
#
# The active Control Plane SA is now:
#
# ai-system/ai-control-plane
#
# The old ai-workloads/ai-control-plane SA must disappear.
# ==========================================================

echo
echo "[4/5] Removing legacy ServiceAccount..."

kubectl -n ai-workloads delete serviceaccount \
  ai-control-plane \
  --ignore-not-found


# ==========================================================
# VERIFY ACTIVE RBAC
# ==========================================================

echo
echo "[5/5] Active Plateform AI RBAC:"
echo

kubectl -n ai-workloads get rolebinding \
  -o custom-columns='NAME:.metadata.name,SUBJECTS:.subjects[*].name,SUBJECT_NS:.subjects[*].namespace,ROLE:.roleRef.name' \
  | grep -E 'NAME|ai-control-plane' || true

echo

kubectl get clusterrolebinding \
  -o custom-columns='NAME:.metadata.name,SUBJECTS:.subjects[*].name,SUBJECT_NS:.subjects[*].namespace,ROLE:.roleRef.name' \
  | grep -E 'NAME|ai-control-plane' || true


echo
echo "=================================================="
echo "Legacy RBAC cleanup complete"
echo "=================================================="
