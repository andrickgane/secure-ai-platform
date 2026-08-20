#!/usr/bin/env bash

set -euo pipefail

BACKUP_DIR="backups"
BACKUP_FILE="${BACKUP_DIR}/networkpolicies-before-controller.yaml"

mkdir -p "${BACKUP_DIR}"

echo "=================================================="
echo "Plateform AI - NetworkPolicy pre-controller cleanup"
echo "=================================================="

echo
echo "[1/3] Backup current NetworkPolicies..."

kubectl get networkpolicy -A -o yaml \
  > "${BACKUP_FILE}"

echo "Backup written to:"
echo "${BACKUP_FILE}"


echo
echo "[2/3] Removing legacy policies..."

kubectl -n ai-system delete networkpolicy \
  ai-control-plane \
  --ignore-not-found

kubectl -n ai-workloads delete networkpolicy \
  ai-workloads-network-policy \
  --ignore-not-found

kubectl -n ai-workloads delete networkpolicy \
  model-ingestion-egress \
  --ignore-not-found

kubectl -n ai-workloads delete networkpolicy \
  model-promotion-egress \
  --ignore-not-found

kubectl -n ai-workloads delete networkpolicy \
  runtime-activation-egress \
  --ignore-not-found


echo
echo "[3/3] Remaining NetworkPolicies:"
echo

kubectl get networkpolicy -A || true


echo
echo "=================================================="
echo "Cleanup complete"
echo "=================================================="
