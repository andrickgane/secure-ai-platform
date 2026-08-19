#!/usr/bin/env bash

set -euo pipefail


echo "=================================================="
echo "Plateform AI - NetworkPolicy label check"
echo "=================================================="


echo
echo "== Namespaces =="
echo

kubectl get namespace \
  ai-system \
  ai-workloads \
  ingress-nginx \
  kube-system \
  registry \
  --show-labels


echo
echo "== Control Plane =="
echo

kubectl -n ai-system get pods \
  -l app.kubernetes.io/name=ai-control-plane \
  --show-labels


echo
echo "== PostgreSQL =="
echo

kubectl -n ai-system get pods \
  -l app.kubernetes.io/name=postgres \
  --show-labels


echo
echo "== Ingress NGINX =="
echo

kubectl -n ingress-nginx get pods \
  -l app.kubernetes.io/name=ingress-nginx \
  --show-labels


echo
echo "== Zot =="
echo

kubectl -n registry get pods \
  -l app.kubernetes.io/name=zot \
  --show-labels


echo
echo "== ai-workloads =="
echo

kubectl -n ai-workloads get pods \
  --show-labels \
  2>/dev/null \
  || true


echo
echo "=================================================="
echo "Label check complete"
echo "=================================================="
