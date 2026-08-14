FROM alpine:3.22 AS tools

ARG TARGETARCH
ARG ORAS_VERSION=1.3.3
ARG COSIGN_VERSION=3.0.6

RUN apk add --no-cache \
    ca-certificates \
    curl \
    tar

# ==========================================================
# ORAS
# ==========================================================

RUN case "${TARGETARCH}" in \
      amd64) ORAS_ARCH="amd64" ;; \
      arm64) ORAS_ARCH="arm64" ;; \
      *) echo "Unsupported architecture: ${TARGETARCH}" && exit 1 ;; \
    esac \
    && curl -fsSL \
      "https://github.com/oras-project/oras/releases/download/v${ORAS_VERSION}/oras_${ORAS_VERSION}_linux_${ORAS_ARCH}.tar.gz" \
      -o /tmp/oras.tar.gz \
    && tar -xzf /tmp/oras.tar.gz \
      -C /usr/local/bin \
      oras \
    && chmod 0755 /usr/local/bin/oras

# ==========================================================
# COSIGN
# ==========================================================

RUN case "${TARGETARCH}" in \
      amd64) COSIGN_ARCH="amd64" ;; \
      arm64) COSIGN_ARCH="arm64" ;; \
      *) echo "Unsupported architecture: ${TARGETARCH}" && exit 1 ;; \
    esac \
    && curl -fsSL \
      "https://github.com/sigstore/cosign/releases/download/v${COSIGN_VERSION}/cosign-linux-${COSIGN_ARCH}" \
      -o /usr/local/bin/cosign \
    && chmod 0755 /usr/local/bin/cosign


# ==========================================================
# RUNTIME
# ==========================================================

FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/promotion

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      ca-certificates \
      tar \
    && rm -rf /var/lib/apt/lists/*

COPY --from=tools \
  /usr/local/bin/oras \
  /usr/local/bin/oras

COPY --from=tools \
  /usr/local/bin/cosign \
  /usr/local/bin/cosign

WORKDIR /opt/model-promotion

COPY model-promotion/requirements.txt \
  /tmp/requirements.txt

RUN pip install \
  --requirement /tmp/requirements.txt

COPY model-promotion/worker.py \
  /opt/model-promotion/worker.py

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
