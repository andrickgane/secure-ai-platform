#!/usr/bin/env bash

set -u
set -o pipefail


echo "=================================================="
echo "Plateform AI - NetworkPolicy preflight"
echo "=================================================="


echo
echo "== CNI / NetworkPolicy components =="
echo

kubectl get pods -A \
  -o custom-columns='NAMESPACE:.metadata.namespace,NAME:.metadata.name,IMAGE:.spec.containers[*].image' \
| grep -Ei \
'flannel|calico|cilium|kube-router|antrea|network-pol|netpol' \
|| true


echo
echo "== Flannel image =="
echo

kubectl -n kube-flannel get daemonset \
  -o jsonpath='{range .items[*]}{.metadata.name}{" => "}{range .spec.template.spec.containers[*]}{.image}{" "}{end}{"\n"}{end}' \
2>/dev/null \
|| true


echo
echo "== Kubernetes API =="
echo

KUBE_API_CLUSTER_IP="$(
  kubectl -n default get service kubernetes \
    -o jsonpath='{.spec.clusterIP}'
)"

echo "Service IP : ${KUBE_API_CLUSTER_IP}"

KUBE_API_ENDPOINT="$(
  kubectl -n default get endpoints kubernetes \
    -o jsonpath='{.subsets[0].addresses[0].ip}' \
    2>/dev/null \
    || true
)"

echo "Endpoint IP: ${KUBE_API_ENDPOINT:-unknown}"


echo
echo "== Current NetworkPolicies =="
echo

kubectl get networkpolicy -A \
  -o wide \
  2>/dev/null \
  || true


echo
echo "=================================================="
echo "Preflight complete"
echo "=================================================="
