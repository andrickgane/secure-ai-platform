# ==========================================================
# COSIGN
#
# Official Cosign v3.1.3 image.
# Digest pinned and shared with the Control Plane /
# Model Promotion trust chain.
# ==========================================================

FROM ghcr.io/sigstore/cosign/cosign:v3.1.3@sha256:9e5c2f2edc34351160407ca3416c61855bdf9403c3c5936e0f0be7fc261611b8 AS cosign


# ==========================================================
# RUNTIME ACTIVATION
#
# ORAS is intentionally NOT included.
#
# Runtime Activation accesses trusted Zot artifacts directly
# through the OCI Distribution API with curl and verifies
# them with Cosign.
#
# Model archives are NEVER extracted locally with tar.
# They are streamed to the isolated runtime host and handled
# by secure_extract.py.
# ==========================================================

FROM alpine:3.22@sha256:14358309a308569c32bdc37e2e0e9694be33a9d99e68afb0f5ff33cc1f695dce

ENV HOME=/home/appuser

RUN apk upgrade --no-cache \
    && apk add --no-cache \
        bash \
        ca-certificates \
        coreutils \
        curl \
        jq \
        openssh-client \
    && addgroup \
        -g 10001 \
        appgroup \
    && adduser \
        -D \
        -u 10001 \
        -G appgroup \
        -h /home/appuser \
        appuser


# ==========================================================
# COSIGN
# ==========================================================

COPY --from=cosign \
    /ko-app/cosign \
    /usr/local/bin/cosign


# ==========================================================
# RUNTIME ACTIVATION SCRIPTS
# ==========================================================

COPY runtime-activation/activate-model.sh \
    /usr/local/bin/activate-model

COPY runtime-activation/secure_extract.py \
    /usr/local/lib/ai-platform/secure_extract.py

COPY runtime-activation/deactivate-vllm.sh \
    /usr/local/bin/deactivate-vllm

COPY runtime-activation/deactivate-runtime.sh \
    /usr/local/bin/deactivate-runtime


# ==========================================================
# PERMISSIONS / TOOL VALIDATION
# ==========================================================

RUN chmod 0755 \
        /usr/local/bin/cosign \
        /usr/local/bin/activate-model \
        /usr/local/lib/ai-platform/secure_extract.py \
        /usr/local/bin/deactivate-runtime \
        /usr/local/bin/deactivate-vllm \
    && echo "===== COSIGN =====" \
    && /usr/local/bin/cosign version \
    && /usr/local/bin/cosign verify --help >/dev/null \
    && echo "===== SSH =====" \
    && ssh -V \
    && echo "===== CURL =====" \
    && curl --version \
    && echo "===== JQ =====" \
    && jq --version \
    && echo "PASS: Runtime Activation tools verified"


# ==========================================================
# NON-ROOT RUNTIME
# ==========================================================

USER 10001:10001

ENTRYPOINT ["/bin/bash"]
