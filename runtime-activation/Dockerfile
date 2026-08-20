FROM ghcr.io/oras-project/oras:v1.3.2 AS oras
FROM ghcr.io/sigstore/cosign/cosign:v3.1.2 AS cosign

FROM alpine:3.22

RUN apk add --no-cache \
      bash \
      ca-certificates \
      curl \
      jq \
      openssh-client \
      tar \
      coreutils \
    && addgroup -g 10001 appgroup \
    && adduser -D -u 10001 -G appgroup appuser

COPY --from=oras /bin/oras /usr/local/bin/oras
COPY --from=cosign /ko-app/cosign /usr/local/bin/cosign

COPY runtime-activation/activate-model.sh /usr/local/bin/activate-model
COPY runtime-activation/secure_extract.py /usr/local/lib/ai-platform/secure_extract.py
COPY runtime-activation/deactivate-vllm.sh /usr/local/bin/deactivate-vllm
COPY runtime-activation/deactivate-runtime.sh /usr/local/bin/deactivate-runtime

RUN chmod 0755 \
      /usr/local/bin/oras \
      /usr/local/bin/cosign \
      /usr/local/bin/activate-model \
      /usr/local/lib/ai-platform/secure_extract.py \
      /usr/local/bin/deactivate-runtime \
      /usr/local/bin/deactivate-vllm \
    && oras version \
    && cosign version

USER 10001:10001

ENTRYPOINT ["/bin/bash"]
