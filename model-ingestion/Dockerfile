FROM python:3.14.6-slim

ARG TARGETARCH
ARG GITLEAKS_VERSION=8.30.1

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/ingestion \
    HF_HOME=/workspace/huggingface-cache

WORKDIR /opt/model-ingestion


# ==========================================================
# SYSTEM
# ==========================================================

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        tar \
    && rm -rf /var/lib/apt/lists/*


# ==========================================================
# GITLEAKS
# ==========================================================

RUN case "${TARGETARCH}" in \
        arm64) GITLEAKS_ARCH="arm64" ;; \
        amd64) GITLEAKS_ARCH="x64" ;; \
        *) echo "Unsupported architecture: ${TARGETARCH}" && exit 1 ;; \
    esac \
    && curl -fsSL \
        "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_${GITLEAKS_ARCH}.tar.gz" \
        -o /tmp/gitleaks.tar.gz \
    && tar -xzf /tmp/gitleaks.tar.gz \
        -C /usr/local/bin \
        gitleaks \
    && chmod 0755 /usr/local/bin/gitleaks \
    && rm /tmp/gitleaks.tar.gz \
    && gitleaks version


# ==========================================================
# PYTHON
# ==========================================================

COPY model-ingestion/requirements.lock.txt \
    /tmp/requirements.lock.txt

RUN pip install \
    --require-hashes \
    --requirement /tmp/requirements.lock.txt


# ==========================================================
# WORKER
# ==========================================================

COPY model-ingestion/worker.py \
    /opt/model-ingestion/worker.py


# ==========================================================
# NON ROOT
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
