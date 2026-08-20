ARG COSIGN_VERSION=v3.1.2
ARG TARGETARCH

# ==========================================================
# WEB UI BUILD
# ==========================================================

FROM node:22-alpine AS ui-builder

WORKDIR /build/ui

COPY ui/package*.json ./

RUN if [ -f package-lock.json ]; then \
        npm ci; \
    else \
        npm install; \
    fi

COPY ui/ ./

RUN npm run build



# ==========================================================
# COSIGN
# ==========================================================

FROM alpine:3.22 AS cosign

ARG COSIGN_VERSION
ARG TARGETARCH


RUN apk add --no-cache \
        ca-certificates \
        curl \
    && case "${TARGETARCH}" in \
        amd64) COSIGN_ARCH="amd64" ;; \
        arm64) COSIGN_ARCH="arm64" ;; \
        *) echo "Unsupported architecture: ${TARGETARCH}" && exit 1 ;; \
    esac \
    && curl -fsSL \
        "https://github.com/sigstore/cosign/releases/download/${COSIGN_VERSION}/cosign-linux-${COSIGN_ARCH}" \
        -o /cosign \
    && chmod 0755 /cosign


# ==========================================================
# AI CONTROL PLANE
# ==========================================================

FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/appuser

WORKDIR /opt/ai-platform


# ==========================================================
# SYSTEM DEPENDENCIES
# ==========================================================

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd \
        --gid 10001 \
        appgroup \
    && useradd \
        --uid 10001 \
        --gid 10001 \
        --create-home \
        --home-dir /home/appuser \
        --shell /usr/sbin/nologin \
        appuser


# ==========================================================
# COSIGN
# ==========================================================

COPY --from=cosign \
    /cosign \
    /usr/local/bin/cosign

RUN chmod 0755 \
    /usr/local/bin/cosign


# ==========================================================
# PYTHON DEPENDENCIES
# ==========================================================

COPY api/requirements.txt \
    /tmp/requirements.txt

RUN pip install \
    --no-cache-dir \
    --requirement /tmp/requirements.txt


# ==========================================================
# CONTROL PLANE API
# ==========================================================

COPY api \
    /opt/ai-platform/api


# ==========================================================
# PLATFORM CATALOG
# ==========================================================

COPY catalog \
    /opt/ai-platform/catalog

# ==========================================================
# WEB UI
# ==========================================================

COPY --from=ui-builder \
    /build/ui/dist \
    /opt/ai-platform/ui


# ==========================================================
# PERMISSIONS
# ==========================================================

RUN chown -R \
        10001:10001 \
        /opt/ai-platform \
        /home/appuser


# ==========================================================
# NON-ROOT RUNTIME
# ==========================================================

USER 10001:10001

ENV ACP_FRONTEND_DIR=/opt/ai-platform/ui

WORKDIR /opt/ai-platform/api

EXPOSE 8080


# ==========================================================
# FASTAPI
# ==========================================================

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
