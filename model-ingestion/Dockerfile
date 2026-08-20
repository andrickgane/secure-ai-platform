# ==========================================================
# GITLEAKS HARDENED BUILDER
#
# Functional baseline:
#   Gitleaks v8.18.4
#
# Security hardening:
#   Go 1.26.6
#   golang.org/x/text v0.39.0
#
# The exact upstream source commit is verified and a
# synthetic GitHub PAT canary MUST be detected at build time.
# ==========================================================

FROM golang:1.26.6-bookworm@sha256:116d58cbd88c1297624acc6e967a060012422bacf9930927e23fb719189c6f36 AS gitleaks-builder

ARG GITLEAKS_VERSION=v8.18.4
ARG GITLEAKS_COMMIT=02808f45d038526bfcceebcbf6421c1047997ff9
ARG X_TEXT_VERSION=v0.39.0

ENV GOTOOLCHAIN=local

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get upgrade -y \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src

RUN git clone \
        --depth 1 \
        --branch "${GITLEAKS_VERSION}" \
        https://github.com/gitleaks/gitleaks.git \
        /src/gitleaks

WORKDIR /src/gitleaks


# ==========================================================
# SOURCE INTEGRITY
# ==========================================================

RUN echo "===== GITLEAKS SOURCE =====" \
    && ACTUAL_COMMIT="$(git rev-parse HEAD)" \
    && echo "commit=${ACTUAL_COMMIT}" \
    && echo "expected=${GITLEAKS_COMMIT}" \
    && test "${ACTUAL_COMMIT}" = "${GITLEAKS_COMMIT}" \
    && test "$(git describe --tags --exact-match)" = "${GITLEAKS_VERSION}" \
    && echo "PASS: Gitleaks source verified"


# ==========================================================
# GO TOOLCHAIN
# ==========================================================

RUN echo "===== GO TOOLCHAIN =====" \
    && go version \
    && test "$(go env GOVERSION)" = "go1.26.6" \
    && echo "PASS: Go toolchain verified"


# ==========================================================
# SECURITY DEPENDENCY PATCH
#
# Only x/text is intentionally upgraded.
# Broad dependency upgrades are prohibited here because they
# could alter Gitleaks detection behaviour.
# ==========================================================

RUN echo "===== X/TEXT BEFORE =====" \
    && go list -m golang.org/x/text \
    && go get "golang.org/x/text@${X_TEXT_VERSION}" \
    && go mod tidy \
    && echo "===== X/TEXT AFTER =====" \
    && go list -m golang.org/x/text \
    && test "$(go list -m -f '{{.Version}}' golang.org/x/text)" = "${X_TEXT_VERSION}" \
    && echo "PASS: x/text security patch verified"


# ==========================================================
# BUILD
# ==========================================================

RUN mkdir -p /out \
    && CGO_ENABLED=0 go build \
        -trimpath \
        -ldflags="-s -w -X=github.com/zricethezav/gitleaks/v8/cmd.Version=${GITLEAKS_VERSION}" \
        -o /out/gitleaks \
        .


# ==========================================================
# BUILD-TIME FUNCTIONAL SECURITY CANARY
#
# Exit code 10 = secret detected.
# Anything else MUST fail the image build.
# ==========================================================

RUN set -eu; \
    mkdir -p /tmp/gitleaks-canary; \
    printf '%s\n' \
        'token = "ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789"' \
        > /tmp/gitleaks-canary/secret.txt; \
    set +e; \
    /out/gitleaks detect \
        --no-git \
        --source /tmp/gitleaks-canary \
        --report-format json \
        --report-path /tmp/gitleaks-canary/report.json \
        --exit-code 10; \
    RC=$?; \
    set -e; \
    echo "GITLEAKS_CANARY_RC=${RC}"; \
    cat /tmp/gitleaks-canary/report.json; \
    if [ "${RC}" -ne 10 ]; then \
        echo "ERROR: Gitleaks failed security canary"; \
        exit 1; \
    fi; \
    grep -q '"RuleID": "github-pat"' \
        /tmp/gitleaks-canary/report.json; \
    echo "PASS: Gitleaks security canary"; \
    rm -rf /tmp/gitleaks-canary


# ==========================================================
# MODEL INGESTION RUNTIME
# ==========================================================

FROM python:3.14.6-slim@sha256:7bec7ddcddeff7975d6ba9b4be7dd6f6b2f55e7491539145e2978f7f97ce9144

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/ingestion \
    HF_HOME=/workspace/huggingface-cache

WORKDIR /opt/model-ingestion


# ==========================================================
# SYSTEM SECURITY
# ==========================================================

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get upgrade -y \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*


# ==========================================================
# GITLEAKS
# ==========================================================

COPY --from=gitleaks-builder \
    /out/gitleaks \
    /usr/local/bin/gitleaks

RUN chmod 0755 /usr/local/bin/gitleaks \
    && test "$(/usr/local/bin/gitleaks version)" = "v8.18.4"


# ==========================================================
# PYTHON DEPENDENCIES
# ==========================================================

COPY model-ingestion/requirements.lock.txt \
    /tmp/requirements.lock.txt

RUN pip install \
    --require-hashes \
    --no-cache-dir \
    --requirement /tmp/requirements.lock.txt


# ==========================================================
# WORKER
# ==========================================================

COPY model-ingestion/worker.py \
    /opt/model-ingestion/worker.py


# ==========================================================
# NON-ROOT RUNTIME
# ==========================================================

RUN groupadd \
        --gid 10001 \
        ingestion \
    && useradd \
        --uid 10001 \
        --gid 10001 \
        --create-home \
        --home-dir /home/ingestion \
        --shell /usr/sbin/nologin \
        ingestion \
    && mkdir -p \
        /workspace \
        /tmp/ingestion \
    && chown -R \
        10001:10001 \
        /workspace \
        /tmp/ingestion \
        /opt/model-ingestion \
        /home/ingestion

USER 10001:10001

ENTRYPOINT ["python", "/opt/model-ingestion/worker.py"]
