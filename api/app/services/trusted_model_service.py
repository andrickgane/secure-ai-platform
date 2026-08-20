from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import ssl
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


class TrustedModelError(Exception):
    """Trusted model verification failure."""


OCI_MANIFEST_MEDIA_TYPE = "application/vnd.oci.image.manifest.v1+json"
EXPECTED_MODEL_ARTIFACT_TYPE = "application/vnd.secureai.model.v1"
EXPECTED_MODEL_LAYER_MEDIA_TYPE = "application/vnd.secureai.model.tar"
EXPECTED_SECURITY_REPORT_MEDIA_TYPE = "application/json"


class TrustedModelService:
    def __init__(
        self,
        project_root: Path | None = None,
        registry_username: str | None = None,
        registry_password: str | None = None,
        registry_ca_file: Path | None = None,
        cosign_public_key: Path | None = None,
        allow_insecure_registry: bool = False,
        registry_plain_http: bool = False,
    ) -> None:
        self.project_root = project_root.resolve() if project_root else None
        self.registry_username = registry_username or os.getenv(
            "ACP_REGISTRY_USERNAME"
        )
        self.registry_password = registry_password or os.getenv(
            "ACP_REGISTRY_PASSWORD"
        )

        ca_env = os.getenv("ACP_REGISTRY_CA_FILE")
        self.registry_ca_file = (
            registry_ca_file if registry_ca_file is not None
            else Path(ca_env) if ca_env
            else None
        )

        key_env = os.getenv("ACP_COSIGN_PUBLIC_KEY")
        self.cosign_public_key = (
            cosign_public_key if cosign_public_key is not None
            else Path(key_env) if key_env
            else None
        )

        self.allow_insecure_registry = allow_insecure_registry or (
            os.getenv("ACP_REGISTRY_INSECURE", "false").lower()
            in {"1", "true", "yes"}
        )
        self.registry_plain_http = registry_plain_http or (
            os.getenv("ACP_REGISTRY_PLAIN_HTTP", "false").lower()
            in {"1", "true", "yes"}
        )

    @staticmethod
    def _validate_digest(digest: str) -> None:
        if not isinstance(digest, str) or not digest.startswith("sha256:"):
            raise TrustedModelError("Only SHA-256 OCI digests are supported")
        value = digest.removeprefix("sha256:")
        if len(value) != 64:
            raise TrustedModelError("Invalid SHA-256 digest length")
        try:
            int(value, 16)
        except ValueError as exc:
            raise TrustedModelError("Invalid SHA-256 digest") from exc

    @staticmethod
    def _calculate_digest(content: bytes) -> str:
        return "sha256:" + hashlib.sha256(content).hexdigest()

    def _ssl_context(self) -> ssl.SSLContext:
        if self.allow_insecure_registry:
            return ssl._create_unverified_context()
        if self.registry_ca_file is not None:
            if not self.registry_ca_file.is_file():
                raise TrustedModelError(
                    f"Registry CA file not found: {self.registry_ca_file}"
                )
            return ssl.create_default_context(cafile=str(self.registry_ca_file))
        return ssl.create_default_context()

    def _authorization_header(self) -> str | None:
        if not self.registry_username:
            return None
        if not self.registry_password:
            raise TrustedModelError(
                "Registry username is configured but registry password is missing"
            )
        raw = f"{self.registry_username}:{self.registry_password}".encode()
        return "Basic " + base64.b64encode(raw).decode("ascii")

    @staticmethod
    def _build_reference(registry: str, repository: str, digest: str) -> str:
        return f"{registry}/{repository}@{digest}"

    def _fetch_manifest(
        self,
        registry: str,
        repository: str,
        digest: str,
        *,
        plain_http: bool,
    ) -> tuple[bytes, dict[str, Any]]:
        scheme = "http" if plain_http else "https"
        request = urllib.request.Request(
            url=f"{scheme}://{registry}/v2/{repository}/manifests/{digest}",
            headers={"Accept": OCI_MANIFEST_MEDIA_TYPE},
            method="GET",
        )
        auth = self._authorization_header()
        if auth:
            request.add_header("Authorization", auth)

        try:
            kwargs: dict[str, Any] = {"timeout": 30}
            if not plain_http:
                kwargs["context"] = self._ssl_context()
            with urllib.request.urlopen(request, **kwargs) as response:
                raw = response.read()
                content_type = response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as exc:
            messages = {
                401: "Registry authentication failed",
                403: "Registry access forbidden",
                404: "OCI artifact was not found in the trusted registry",
            }
            raise TrustedModelError(
                messages.get(exc.code, f"Registry returned HTTP {exc.code}")
            ) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise TrustedModelError(
                f"Could not contact registry '{registry}': {exc}"
            ) from exc

        try:
            manifest = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise TrustedModelError("Registry returned invalid OCI manifest") from exc

        if not isinstance(manifest, dict):
            raise TrustedModelError("OCI manifest must be a JSON object")
        if content_type and OCI_MANIFEST_MEDIA_TYPE not in content_type:
            raise TrustedModelError(
                f"Unexpected registry manifest media type: {content_type}"
            )
        return raw, manifest

    @staticmethod
    def _validate_manifest_structure(manifest: dict[str, Any]) -> dict[str, Any]:
        if manifest.get("schemaVersion") != 2:
            raise TrustedModelError("Unsupported OCI schemaVersion")
        if manifest.get("mediaType") != OCI_MANIFEST_MEDIA_TYPE:
            raise TrustedModelError("Artifact is not an OCI image manifest")

        artifact_type = manifest.get("artifactType")
        if artifact_type != EXPECTED_MODEL_ARTIFACT_TYPE:
            raise TrustedModelError(
                f"Unexpected OCI artifact type: {artifact_type}"
            )

        layers = manifest.get("layers")
        if not isinstance(layers, list) or not layers:
            raise TrustedModelError("OCI model artifact contains no valid layers")

        model_package_found = False
        report_found = False
        summary: list[dict[str, Any]] = []

        for layer in layers:
            if not isinstance(layer, dict):
                raise TrustedModelError("Invalid OCI layer descriptor")
            digest = layer.get("digest")
            media_type = layer.get("mediaType")
            size = layer.get("size")
            annotations = layer.get("annotations", {})
            if not isinstance(annotations, dict):
                annotations = {}
            title = annotations.get("org.opencontainers.image.title")

            if not digest:
                raise TrustedModelError("OCI layer has no digest")
            TrustedModelService._validate_digest(digest)
            if not isinstance(size, int) or size < 0:
                raise TrustedModelError("OCI layer has invalid size")

            if media_type == EXPECTED_MODEL_LAYER_MEDIA_TYPE:
                model_package_found = True
            if media_type == EXPECTED_SECURITY_REPORT_MEDIA_TYPE and (
                title is None or str(title).endswith("security-report.json")
            ):
                report_found = True

            summary.append(
                {
                    "title": title,
                    "media_type": media_type,
                    "digest": digest,
                    "size": size,
                }
            )

        if not model_package_found:
            raise TrustedModelError(
                "OCI artifact does not contain the trusted model.tar layer"
            )
        if not report_found:
            raise TrustedModelError(
                "OCI artifact does not contain security-report.json"
            )
        return {"artifact_type": artifact_type, "layers": summary}

    def _verify_cosign(
        self,
        reference: str,
        signature: dict[str, Any],
        *,
        plain_http: bool,
    ) -> None:
        cosign = shutil.which("cosign")
        if cosign is None:
            raise TrustedModelError("cosign executable was not found")

        command = [cosign, "verify"]
        if plain_http or self.allow_insecure_registry:
            command.append("--allow-insecure-registry")
        if self.registry_username:
            command += ["--registry-username", self.registry_username]
        if self.registry_password:
            command += ["--registry-password", self.registry_password]
        if self.registry_ca_file and not plain_http:
            command += ["--registry-cacert", str(self.registry_ca_file)]

        public_key_value = signature.get("publicKeyPath")
        public_key = (
            Path(public_key_value)
            if isinstance(public_key_value, str) and public_key_value
            else self.cosign_public_key
        )

        if public_key is not None:
            if not public_key.is_file():
                raise TrustedModelError(
                    f"Cosign public key was not found: {public_key}"
                )
            # Self-managed-key mode: no network dependency on Sigstore TUF/Rekor.
            command += [
                "--key",
                str(public_key),
                "--insecure-ignore-tlog",
            ]
        else:
            identity = signature.get("identity")
            issuer = signature.get("oidcIssuer")
            if not isinstance(identity, str) or not identity:
                raise TrustedModelError(
                    "Cosign verification requires a public key or identity"
                )
            if not isinstance(issuer, str) or not issuer:
                raise TrustedModelError("Cosign OIDC issuer is missing")
            command += [
                "--certificate-identity",
                identity,
                "--certificate-oidc-issuer",
                issuer,
            ]

        command.append(reference)

        try:
            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
        except subprocess.TimeoutExpired as exc:
            raise TrustedModelError("Cosign verification timed out") from exc
        except OSError as exc:
            raise TrustedModelError(f"Could not execute cosign: {exc}") from exc

        if process.returncode != 0:
            error = (
                process.stderr.strip()
                or process.stdout.strip()
                or "unknown cosign error"
            )
            raise TrustedModelError(f"Cosign OCI verification failed: {error}")

    def delete_manifest(
        self,
        registry: str,
        repository: str,
        digest: str,
        *,
        plain_http: bool | None = None,
    ) -> bool:
        """
        Delete one immutable OCI manifest from the trusted registry.

        Returns:
            True  -> manifest deleted
            False -> manifest was already absent
        """
        if not isinstance(registry, str) or not registry:
            raise TrustedModelError("OCI registry is missing")

        if not isinstance(repository, str) or not repository:
            raise TrustedModelError("OCI repository is missing")

        self._validate_digest(digest)

        if plain_http is None:
            plain_http = self.registry_plain_http

        scheme = "http" if plain_http else "https"

        request = urllib.request.Request(
            url=(
                f"{scheme}://{registry}/v2/"
                f"{repository}/manifests/{digest}"
            ),
            headers={
                "Accept": OCI_MANIFEST_MEDIA_TYPE,
            },
            method="DELETE",
        )

        auth = self._authorization_header()

        if auth:
            request.add_header(
                "Authorization",
                auth,
            )

        try:
            kwargs: dict[str, Any] = {
                "timeout": 30,
            }

            if not plain_http:
                kwargs["context"] = self._ssl_context()

            with urllib.request.urlopen(
                request,
                **kwargs,
            ) as response:
                if response.status not in {
                    200,
                    202,
                }:
                    raise TrustedModelError(
                        "Registry returned unexpected "
                        f"HTTP {response.status}"
                    )

            return True

        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return False

            messages = {
                401: "Registry authentication failed",
                403: "Registry access forbidden",
                405: "Registry manifest deletion is disabled",
            }

            raise TrustedModelError(
                messages.get(
                    exc.code,
                    f"Registry returned HTTP {exc.code}",
                )
            ) from exc

        except (
            urllib.error.URLError,
            TimeoutError,
        ) as exc:
            raise TrustedModelError(
                f"Could not contact registry '{registry}': {exc}"
            ) from exc


    def verify(self, artifact: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(artifact, dict):
            raise TrustedModelError("Artifact configuration is missing")
        if artifact.get("source") != "oci-registry":
            raise TrustedModelError("Model artifact must use 'oci-registry'")

        registry = artifact.get("registry")
        repository = artifact.get("repository")
        digest = artifact.get("digest")

        if not isinstance(registry, str) or not registry:
            raise TrustedModelError("OCI registry is missing")
        if not isinstance(repository, str) or not repository:
            raise TrustedModelError("OCI repository is missing")
        self._validate_digest(digest)

        plain_http = artifact.get("plainHttp", self.registry_plain_http)
        if not isinstance(plain_http, bool):
            raise TrustedModelError("artifact.plainHttp must be boolean")

        reference = self._build_reference(registry, repository, digest)
        raw, manifest = self._fetch_manifest(
            registry,
            repository,
            digest,
            plain_http=plain_http,
        )
        calculated = self._calculate_digest(raw)
        if calculated != digest:
            raise TrustedModelError(
                f"OCI manifest digest mismatch: expected={digest}, "
                f"calculated={calculated}"
            )

        info = self._validate_manifest_structure(manifest)
        signature = artifact.get("signature", {})
        if not isinstance(signature, dict):
            raise TrustedModelError(
                "Artifact signature configuration must be an object"
            )

        required = signature.get("required", True)
        if not isinstance(required, bool):
            raise TrustedModelError("signature.required must be boolean")

        verified = False
        if required:
            self._verify_cosign(reference, signature, plain_http=plain_http)
            verified = True

        return {
            "verified": True,
            "source": "oci-registry",
            "reference": reference,
            "registry": registry,
            "repository": repository,
            "digest": digest,
            "revision": artifact.get("sourceRevision"),
            "artifact_type": info["artifact_type"],
            "layers": info["layers"],
            "model_package_verified": True,
            "security_report_verified": True,
            "signature_verified": verified,
            "plain_http": plain_http,
        }
