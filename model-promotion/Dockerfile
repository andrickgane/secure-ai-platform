# ==========================================================
# ORAS HARDENED BUILDER
#
# ORAS:
#   Version : v1.3.3
#   Commit  : 210747c29c1d38732b3194878dfd8b5a6b9ad7eb
#
# Toolchain:
#   Go 1.26.6
# ==========================================================

FROM golang:1.26.6-bookworm@sha256:116d58cbd88c1297624acc6e967a060012422bacf9930927e23fb719189c6f36 AS oras-builder

ARG ORAS_VERSION=v1.3.3
ARG ORAS_COMMIT=210747c29c1d38732b3194878dfd8b5a6b9ad7eb

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
        --branch "${ORAS_VERSION}" \
        https://github.com/oras-project/oras.git \
        /src/oras

WORKDIR /src/oras


# ==========================================================
# ORAS SOURCE INTEGRITY
# ==========================================================

RUN echo "===== ORAS SOURCE =====" \
    && ACTUAL_COMMIT="$(git rev-parse HEAD)" \
    && echo "actual=${ACTUAL_COMMIT}" \
    && echo "expected=${ORAS_COMMIT}" \
    && test "${ACTUAL_COMMIT}" = "${ORAS_COMMIT}" \
    && test "$(git describe --tags --exact-match)" = "${ORAS_VERSION}" \
    && echo "PASS: ORAS source verified"


# ==========================================================
# GO TOOLCHAIN / MODULES
# ==========================================================

RUN echo "===== GO TOOLCHAIN =====" \
    && go version \
    && test "$(go env GOVERSION)" = "go1.26.6" \
    && echo "PASS: Go toolchain verified"

RUN echo "===== ORAS SECURITY MODULES =====" \
    && go list -m golang.org/x/crypto \
    && go list -m oras.land/oras-go/v2


# ==========================================================
# ORAS BUILD
# ==========================================================

RUN mkdir -p /out \
    && GIT_COMMIT="$(git rev-parse HEAD)" \
    && CGO_ENABLED=0 \
       GOOS=linux \
       go build \
       -trimpath \
       -ldflags="-s -w \
       -X oras.land/oras/internal/version.GitCommit=${GIT_COMMIT} \
       -X oras.land/oras/internal/version.GitTreeState=clean" \
       -o /out/oras \
       oras.land/oras/cmd/oras

RUN echo "===== ORAS BUILD RESULT =====" \
    && /out/oras version \
    && /out/oras login --help >/dev/null \
    && /out/oras push --help >/dev/null \
    && /out/oras manifest fetch --help >/dev/null \
    && echo "PASS: ORAS required commands available"


# ==========================================================
# COSIGN OFFICIAL RELEASE
#
# v3.1.3 fixes GHSA-fx35-mq7g-6g98.
# Same trusted Cosign source already used by Control Plane.
# ==========================================================

FROM ghcr.io/sigstore/cosign/cosign:v3.1.3@sha256:9e5c2f2edc34351160407ca3416c61855bdf9403c3c5936e0f0be7fc261611b8 AS cosign


# ==========================================================
# MODEL PROMOTION RUNTIME
# ==========================================================

FROM python:3.14.6-slim@sha256:7bec7ddcddeff7975d6ba9b4be7dd6f6b2f55e7491539145e2978f7f97ce9144

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/promotion

WORKDIR /opt/model-promotion


# ==========================================================
# SYSTEM SECURITY
# ==========================================================

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get upgrade -y \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates \
        tar \
    && rm -rf /var/lib/apt/lists/*


# ==========================================================
# TRUSTED SUPPLY CHAIN TOOLS
# ==========================================================

COPY --from=oras-builder \
    /out/oras \
    /usr/local/bin/oras

COPY --from=cosign \
    /ko-app/cosign \
    /usr/local/bin/cosign

RUN chmod 0755 \
        /usr/local/bin/oras \
        /usr/local/bin/cosign \
    && echo "===== ORAS =====" \
    && /usr/local/bin/oras version \
    && echo "===== COSIGN =====" \
    && /usr/local/bin/cosign version \
    && /usr/local/bin/oras login --help >/dev/null \
    && /usr/local/bin/oras push --help >/dev/null \
    && /usr/local/bin/oras manifest fetch --help >/dev/null \
    && /usr/local/bin/cosign sign --help >/dev/null \
    && echo "PASS: Model Promotion tools verified"


# ==========================================================
# PYTHON DEPENDENCIES
# ==========================================================

COPY model-promotion/requirements.lock.txt \
    /tmp/requirements.lock.txt

RUN pip install \
    --require-hashes \
    --no-cache-dir \
    --requirement /tmp/requirements.lock.txt


# ==========================================================
# WORKER
# ==========================================================

COPY model-promotion/worker.py \
    /opt/model-promotion/worker.py


# ==========================================================
# SECURE MODEL EXTRACTION
#
# Shared hardened extractor used by Kubernetes model-puller
# and external Runtime Activation.
# ==========================================================

COPY runtime-activation/secure_extract.py \
    /usr/local/lib/ai-platform/secure_extract.py

RUN chmod 0755 \
    /usr/local/lib/ai-platform/secure_extract.py


# ==========================================================
# NON-ROOT RUNTIME
# ==========================================================

RUN groupadd \
        --gid 10001 \
        promotion \
    && useradd \
        --uid 10001 \
        --gid 10001 \
        --create-home \
        --home-dir /home/promotion \
        --shell /usr/sbin/nologin \
        promotion \
    && mkdir -p \
        /workspace \
        /tmp/promotion \
        /keys \
    && chown -R \
        10001:10001 \
        /workspace \
        /tmp/promotion \
        /opt/model-promotion \
        /home/promotion \
        /keys

USER 10001:10001

ENTRYPOINT ["python", "/opt/model-promotion/worker.py"]
