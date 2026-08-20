#!/usr/bin/env bash

set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

export PYTHONPATH="${ROOT}/api${PYTHONPATH:+:${PYTHONPATH}}"

FAILED=0


pass() {
    echo "PASS: $*"
}


fail() {
    echo "FAIL: $*"
    FAILED=1
}


echo "=================================================="
echo "PLATEFORM AI - PRE-PUSH SECURITY CHECK"
echo "=================================================="


# ==========================================================
# 1. GIT
# ==========================================================

echo
echo "[1] Git integrity"
echo

if git diff --check; then
    pass "working tree whitespace"
else
    fail "working tree whitespace"
fi

if git diff --cached --check; then
    pass "staged whitespace"
else
    fail "staged whitespace"
fi


# ==========================================================
# 2. PYTHON
# ==========================================================

echo
echo "[2] Python"
echo

if python -m compileall -q api/app; then
    pass "Python compileall"
else
    fail "Python compileall"
fi


# ==========================================================
# 3. PLATFORM ADMIN RBAC
# ==========================================================

echo
echo "[3] Platform-admin RBAC"
echo

COUNT="$(
  grep -R \
    --include='*.py' \
    --exclude-dir='__pycache__' \
    -c '^def require_platform_admin(' \
    api/app \
  | awk -F: \
      '{sum += $2} END {print sum+0}'
)"

if [[ "${COUNT}" == "1" ]]; then
    pass "single require_platform_admin implementation"
else
    fail "require_platform_admin implementations=${COUNT}"
fi


if grep -q \
  'from app.core.auth import require_platform_admin' \
  api/app/routes/model_requests.py
then
    pass "model_requests canonical guard"
else
    fail "model_requests canonical guard"
fi


if grep -q \
  'Depends(require_admin)' \
  api/app/routes/model_requests.py
then
    fail "model_requests authorization downgrade"
else
    pass "no model_requests authorization downgrade"
fi


if PYTHONPATH="${ROOT}/api" python - <<'PY'
from types import SimpleNamespace

from fastapi import HTTPException

from app.core.auth import (
    require_platform_admin,
)

for role in (
    "user",
    "viewer",
    "admin",
):

    try:
        require_platform_admin(
            SimpleNamespace(
                role=role,
            )
        )

    except HTTPException as exc:
        assert exc.status_code == 403

    else:
        raise SystemExit(1)


assert (
    require_platform_admin(
        SimpleNamespace(
            role="platform_admin",
        )
    ).role
    == "platform_admin"
)
PY
then
    pass "platform_admin role enforcement"
else
    fail "platform_admin role enforcement"
fi


# ==========================================================
# 4. WORKLOAD IDENTITY
# ==========================================================

echo
echo "[4] Workload identity"
echo

if PYTHONPATH="${ROOT}/api" python - <<'PY'
from pathlib import Path

checks = {
    "api/app/services/model_ingestion_service.py":
        '"model-ingestion"',

    "api/app/services/model_promotion_service.py":
        '"model-promotion"',

    "api/app/services/runtime_activation_service.py":
        'service_account_name="runtime-activation"',

    "api/app/services/kubernetes_service.py":
        'service_account_name="ai-runtime"',
}

for filename, identity in checks.items():

    text = Path(
        filename
    ).read_text()

    assert identity in text

    assert (
        "automount_service_account_token=False"
        in text
    )
PY
then
    pass "workload identities"
else
    fail "workload identities"
fi


# ==========================================================
# 5. NETWORK POLICY
# ==========================================================

echo
echo "[5] Network security"
echo

if grep -R \
  --exclude-dir='.git' \
  --exclude-dir='.venv' \
  -- '--fail-open=true' \
  deploy \
  >/dev/null
then
    fail "fail-open=true detected"
else
    pass "no fail-open=true"
fi


if grep -q \
  -- '--fail-open=false' \
  deploy/security/kube-network-policies.yaml
then
    pass "fail-open=false"
else
    fail "fail-open=false missing"
fi


# ==========================================================
# 6. LEGACY NETWORK REFERENCES
# ==========================================================

echo
echo "[6] Legacy infrastructure"
echo

LEGACY="$(
  grep -RIn \
    --exclude-dir='.git' \
    --exclude-dir='.venv' \
    --exclude-dir='node_modules' \
    --exclude='plateform-ai-security-audit.txt' \
    -E \
    'registry\.secure-ai\.local|api\.secure-ai\.local' \
    api \
    deploy \
    catalog \
    model-ingestion \
    model-promotion \
    runtime-activation \
  || true
)"

if [[ -z "${LEGACY}" ]]; then

    pass "no legacy secure-ai.local infrastructure references"

else

    echo "${LEGACY}"
    fail "legacy infrastructure references"
fi


# ==========================================================
# 7. PRIVATE KEY CONTENT
#
# model_security.yar intentionally contains private-key
# BEGIN markers because those are malware/security signatures.
# ==========================================================

echo
echo "[7] Private key material"
echo

PRIVATE_KEYS="$(
  git grep \
    --cached \
    -nE \
    -- \
    '-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----' \
    ':!model-ingestion/yara/rules/model_security.yar' \
  || true
)"

if [[ -z "${PRIVATE_KEYS}" ]]; then

    pass "no private key material"

else

    echo "${PRIVATE_KEYS}"
    fail "private key material detected"
fi


# ==========================================================
# 8. TOKEN PATTERNS
# ==========================================================

echo
echo "[8] Credential patterns"
echo

TOKENS="$(
  git grep \
    --cached \
    -nE \
    -- \
    '(sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16})' \
  || true
)"

if [[ -z "${TOKENS}" ]]; then

    pass "no obvious credential tokens"
else

    echo "${TOKENS}"
    fail "possible credential token"
fi


# ==========================================================
# 9. LOCAL FILES
# ==========================================================

echo
echo "[9] Local-only artifacts"
echo

FORBIDDEN="$(
  git diff \
    --cached \
    --name-only \
  | grep -E \
    '(^backups/|^plateform-ai-security-audit\.txt$|\.before-)' \
  || true
)"

if [[ -z "${FORBIDDEN}" ]]; then

    pass "no local audit/backup artifacts staged"

else

    echo "${FORBIDDEN}"
    fail "local artifacts staged"
fi


if git ls-files \
  --error-unmatch \
  deploy/postgres/secret.yaml \
  >/dev/null 2>&1
then

    fail "real PostgreSQL secret tracked"

else

    pass "real PostgreSQL secret not tracked"
fi


# ==========================================================
# 10. SECRET EXAMPLES
# ==========================================================

echo
echo "[10] Secret examples"
echo

if grep -Eq \
  'CHANGE_ME|CHANGE_ME_STRONG_PASSWORD' \
  deploy/postgres/secret-example.yaml
then

    pass "PostgreSQL secret example contains placeholders"

else

    fail "PostgreSQL secret example needs placeholder review"
fi


# ==========================================================
# 11. KUBERNETES MANIFESTS
# ==========================================================

echo
echo "[11] Kubernetes manifests"
echo

for MANIFEST in \
  deploy/api/deployment.yaml \
  deploy/api/serviceaccount-rbac.yaml \
  deploy/security/workload-serviceaccounts.yaml \
  deploy/security/ai-system-networkpolicies.yaml \
  deploy/security/ai-workloads-networkpolicies.yaml \
  deploy/security/kube-network-policies.yaml
do

    if kubectl apply \
      --dry-run=client \
      -f "${MANIFEST}" \
      >/dev/null
    then

        pass "${MANIFEST}"

    else

        fail "${MANIFEST}"
    fi

done


# ==========================================================
# 12. PLATFORM HEALTH
# ==========================================================

echo
echo "[12] Running platform"
echo

if kubectl -n ai-system \
  get deployment ai-control-plane \
  >/dev/null 2>&1
then

    pass "Control Plane deployment"

else

    fail "Control Plane deployment"
fi


HTTP_CODE="$(
  curl -k -s \
    -o /dev/null \
    -w '%{http_code}' \
    https://api.ai.local/docs \
  || true
)"

if [[ "${HTTP_CODE}" == "200" ]]; then

    pass "API HTTP 200"

else

    fail "API HTTP=${HTTP_CODE}"
fi


# ==========================================================
# RESULT
# ==========================================================

echo
echo "=================================================="

if [[ "${FAILED}" -ne 0 ]]; then

    echo "PRE-PUSH SECURITY CHECK FAILED"
    echo "DO NOT PUSH"
    exit 1

fi

echo "PRE-PUSH SECURITY CHECK PASSED"
echo "REPOSITORY READY FOR COMMIT"
echo "=================================================="
