#!/usr/bin/env bash

set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

export PYTHONPATH="${ROOT}/api${PYTHONPATH:+:${PYTHONPATH}}"

echo "=================================================="
echo "PLATEFORM AI - SECURITY P1 FINALIZATION"
echo "=================================================="


# ==========================================================
# 1. PLATFORM ADMIN RBAC
# ==========================================================

echo
echo "[1/8] Canonical platform_admin authorization"
echo

python - <<'PY'
from pathlib import Path

path = Path("api/app/routes/model_requests.py")
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
    start = text.index(authorization_marker)
    end = text.index(create_marker, start)

    text = (
        text[:start]
        + create_marker
        + text[end + len(create_marker):]
    )

if "Depends(require_admin)" in text:
    raise SystemExit(
        "ERROR: Depends(require_admin) remains "
        "in model_requests.py"
    )

if "def require_platform_admin(" in text:
    raise SystemExit(
        "ERROR: local require_platform_admin remains "
        "in model_requests.py"
    )

if (
    "from app.core.auth import require_platform_admin"
    not in text
):
    raise SystemExit(
        "ERROR: canonical require_platform_admin "
        "import missing"
    )

path.write_text(text)

print(
    "PASS: model_requests uses canonical "
    "require_platform_admin"
)
PY


# ==========================================================
# 2. UNIQUE IMPLEMENTATION
# ==========================================================

echo
echo "[2/8] Verify single platform-admin implementation"
echo

COUNT="$(
  grep -R \
    --include='*.py' \
    --exclude-dir='__pycache__' \
    -c '^def require_platform_admin(' \
    api/app \
  | awk -F: '{sum += $2} END {print sum+0}'
)"

if [[ "${COUNT}" != "1" ]]; then
    echo "ERROR: require_platform_admin count=${COUNT}"

    grep -RIn \
      --include='*.py' \
      --exclude-dir='__pycache__' \
      '^def require_platform_admin(' \
      api/app \
      || true

    exit 1
fi

echo "PASS: single canonical implementation"


# ==========================================================
# 3. ROLE ENFORCEMENT
# ==========================================================

echo
echo "[3/8] Test platform-admin role enforcement"
echo

python - <<'PY'
from types import SimpleNamespace

from fastapi import HTTPException

from app.core.auth import require_platform_admin


for role in (
    "user",
    "viewer",
    "admin",
):
    try:
        require_platform_admin(
            SimpleNamespace(role=role)
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

returned = require_platform_admin(
    platform_admin
)

assert returned is platform_admin

print(
    "PASS: platform_admin -> authorized"
)

print()
print(
    "PLATFORM ADMIN RBAC TEST PASSED"
)
PY


# ==========================================================
# 4. WORKLOAD IDENTITIES
# ==========================================================

echo
echo "[4/8] Verify workload identities"
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
    text = Path(filename).read_text()

    for pattern in patterns:
        assert pattern in text, (
            f"{filename}: missing {pattern}"
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
    'service_account_name=('
    '\n                "model-ingestion"'
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
# 5. NETWORK SECURITY
# ==========================================================

echo
echo "[5/8] Verify NetworkPolicy fail-closed"
echo

if grep -RIn \
    --exclude-dir='.git' \
    --exclude-dir='.venv' \
    -- '--fail-open=true' \
    deploy
then
    echo "ERROR: --fail-open=true detected"
    exit 1
fi

grep -q \
  -- '--fail-open=false' \
  deploy/security/kube-network-policies.yaml

grep -q \
  -- '--disable-nri=true' \
  deploy/security/kube-network-policies.yaml

echo "PASS: NetworkPolicy engine fail-closed"


# ==========================================================
# 6. PYTHON
# ==========================================================

echo
echo "[6/8] Python compilation"
echo

python -m compileall -q api/app

echo "PASS: Python compileall"


# ==========================================================
# 7. KUBERNETES MANIFESTS
# ==========================================================

echo
echo "[7/8] Kubernetes manifest validation"
echo

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
# 8. GIT SANITY
# ==========================================================

echo
echo "[8/8] Git sanity"
echo

git diff --check

echo "PASS: git diff --check"

echo
echo "=================================================="
echo "SECURITY P1 SOURCE FINALIZATION PASSED"
echo "=================================================="
