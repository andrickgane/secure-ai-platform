#!/usr/bin/env bash

set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

export PYTHONPATH="${ROOT}/api${PYTHONPATH:+:${PYTHONPATH}}"

echo "=================================================="
echo "PLATEFORM AI - REPAIR SECURITY / PRE-PUSH"
echo "=================================================="


# ==========================================================
# 1. REMOVE LOCAL AUDIT ARTIFACTS FROM GIT INDEX
# ==========================================================

echo
echo "[1/8] Remove local audit artifacts from staging"
echo

git restore --staged \
  backups/networkpolicies-before-controller.yaml \
  plateform-ai-security-audit.txt \
  2>/dev/null \
  || true


# ==========================================================
# 2. HARDEN .gitignore
# ==========================================================

echo
echo "[2/8] Update .gitignore"
echo

touch .gitignore

ensure_ignore() {
    local ENTRY="$1"

    if ! grep -Fxq "${ENTRY}" .gitignore; then
        printf '%s\n' "${ENTRY}" >> .gitignore
    fi
}

ensure_ignore ""
ensure_ignore "# Local audit and backup artifacts"
ensure_ignore "backups/"
ensure_ignore "plateform-ai-security-audit.txt"
ensure_ignore "*.before-*"
ensure_ignore "*.bak"

ensure_ignore ""
ensure_ignore "# Local environment"
ensure_ignore ".venv/"
ensure_ignore "__pycache__/"
ensure_ignore ".pytest_cache/"
ensure_ignore ".DS_Store"

ensure_ignore ""
ensure_ignore "# Local secrets"
ensure_ignore ".env"
ensure_ignore ".env.local"
ensure_ignore ".env.*.local"

rm -f \
  'custom-columns=NAME:.metadata.name,AUTOMOUNT:.automountServiceAccountToken' \
  "jsonpath='" \
  || true


# ==========================================================
# 3. FIX CANONICAL PLATFORM ADMIN AUTHORIZATION
# ==========================================================

echo
echo "[3/8] Canonical platform_admin authorization"
echo

python - <<'PY'
from pathlib import Path

path = Path(
    "api/app/routes/model_requests.py"
)

text = path.read_text()

text = text.replace(
    "from app.core.auth import require_admin",
    "from app.core.auth import require_platform_admin",
    1,
)

authorization_marker = """# ============================================================
# AUTHORIZATION
# ============================================================
"""

create_marker = """# ============================================================
# CREATE MODEL REQUEST
# ============================================================
"""

if authorization_marker in text:

    start = text.index(
        authorization_marker
    )

    end = text.index(
        create_marker,
        start,
    )

    text = (
        text[:start]
        + create_marker
        + text[end + len(create_marker):]
    )


if "Depends(require_admin)" in text:
    raise SystemExit(
        "require_admin remains in model_requests.py"
    )

if "def require_platform_admin(" in text:
    raise SystemExit(
        "local require_platform_admin remains"
    )

if (
    "from app.core.auth import require_platform_admin"
    not in text
):
    raise SystemExit(
        "canonical require_platform_admin import missing"
    )

path.write_text(text)

print(
    "PASS: model_requests canonical authorization"
)
PY


# ==========================================================
# 4. TEST AUTHORIZATION
# ==========================================================

echo
echo "[4/8] Authorization unit test"
echo

python - <<'PY'
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

    user = SimpleNamespace(
        role=role,
    )

    try:
        require_platform_admin(
            user
        )

    except HTTPException as exc:

        assert exc.status_code == 403

        print(
            f"PASS: {role} -> 403"
        )

    else:

        raise AssertionError(
            f"{role} unexpectedly authorized"
        )


platform_admin = SimpleNamespace(
    role="platform_admin",
)

assert (
    require_platform_admin(
        platform_admin
    )
    is platform_admin
)

print(
    "PASS: platform_admin -> authorized"
)

print()
print(
    "PLATFORM ADMIN RBAC TEST PASSED"
)
PY


# ==========================================================
# 5. WORKLOAD IDENTITY
# ==========================================================

echo
echo "[5/8] Workload identities"
echo

python - <<'PY'
from pathlib import Path


checks = {

    "api/app/services/model_ingestion_service.py": [
        '"model-ingestion"',
        "automount_service_account_token=False",
    ],

    "api/app/services/model_promotion_service.py": [
        '"model-promotion"',
        "automount_service_account_token=False",
    ],

    "api/app/services/runtime_activation_service.py": [
        'service_account_name="runtime-activation"',
        "automount_service_account_token=False",
    ],

    "api/app/services/kubernetes_service.py": [
        'service_account_name="ai-runtime"',
        "automount_service_account_token=False",
    ],
}


for filename, patterns in checks.items():

    content = Path(
        filename
    ).read_text()

    for pattern in patterns:

        assert pattern in content, (
            filename,
            pattern,
        )

    print(
        f"PASS: {filename}"
    )


promotion = Path(
    "api/app/services/model_promotion_service.py"
).read_text()

activation = Path(
    "api/app/services/runtime_activation_service.py"
).read_text()

assert (
    '"model-ingestion"'
    not in promotion
)

assert (
    'service_account_name="model-ingestion"'
    not in activation
)

print()
print(
    "WORKLOAD IDENTITY SOURCE TEST PASSED"
)
PY


# ==========================================================
# 6. NETWORK SECURITY
# ==========================================================

echo
echo "[6/8] Network security"
echo

if grep -RIn \
    --exclude-dir='.git' \
    --exclude-dir='.venv' \
    -- '--fail-open=true' \
    deploy
then

    echo "ERROR: fail-open=true found"
    exit 1
fi

grep -q \
  -- '--fail-open=false' \
  deploy/security/kube-network-policies.yaml

grep -q \
  -- '--disable-nri=true' \
  deploy/security/kube-network-policies.yaml

echo "PASS: NetworkPolicy fail-closed"


# ==========================================================
# 7. SOURCE / MANIFEST VALIDATION
# ==========================================================

echo
echo "[7/8] Source and manifest validation"
echo

python -m compileall -q api/app

git diff --check

for MANIFEST in \
  deploy/api/deployment.yaml \
  deploy/api/serviceaccount-rbac.yaml \
  deploy/security/workload-serviceaccounts.yaml \
  deploy/security/ai-system-networkpolicies.yaml \
  deploy/security/ai-workloads-networkpolicies.yaml \
  deploy/security/kube-network-policies.yaml
do

    kubectl apply \
      --dry-run=client \
      -f "${MANIFEST}" \
      >/dev/null

    echo "PASS: ${MANIFEST}"

done


# ==========================================================
# 8. RESTAGE CLEAN REPOSITORY
# ==========================================================

echo
echo "[8/8] Restage clean repository"
echo

git add .gitignore

git add -A


FORBIDDEN="$(
  git diff \
    --cached \
    --name-only \
  | grep -E \
    '(^backups/|^plateform-ai-security-audit\.txt$)' \
  || true
)"

if [[ -n "${FORBIDDEN}" ]]; then

    echo "${FORBIDDEN}"
    echo
    echo "ERROR: local audit artifacts still staged"
    exit 1
fi


if git ls-files \
  --error-unmatch \
  deploy/postgres/secret.yaml \
  >/dev/null 2>&1
then

    echo "ERROR: real postgres secret is tracked"
    exit 1
fi


echo
echo "=================================================="
echo "REPAIR PASSED"
echo "=================================================="

echo
echo "Ignored local files:"
git check-ignore -v \
  backups/networkpolicies-before-controller.yaml \
  plateform-ai-security-audit.txt \
  || true
