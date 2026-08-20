
# ==========================================================
# WEB UI BUILD
# ==========================================================

FROM node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32 AS ui-builder

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

ARG COSIGN_VERSION

FROM ghcr.io/sigstore/cosign/cosign:v3.1.3@sha256:9e5c2f2edc34351160407ca3416c61855bdf9403c3c5936e0f0be7fc261611b8 AS cosign


# ==========================================================
# AI CONTROL PLANE
# ==========================================================

FROM python:3.14.6-slim@sha256:7bec7ddcddeff7975d6ba9b4be7dd6f6b2f55e7491539145e2978f7f97ce9144

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/appuser

WORKDIR /opt/ai-platform


# ==========================================================
# SYSTEM DEPENDENCIES + SECURITY UPDATES
# ==========================================================

RUN apt-get update \
    && apt-get upgrade -y \
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
    /ko-app/cosign \
    /usr/local/bin/cosign

RUN chmod 0755 \
    /usr/local/bin/cosign


# ==========================================================
# PYTHON DEPENDENCIES
# ==========================================================

COPY api/requirements.lock.txt \
    /tmp/requirements.lock.txt

RUN pip install \
    --require-hashes \
    --no-cache-dir \
    --requirement /tmp/requirements.lock.txt


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
