from __future__ import annotations

from typing import Any


class ProfilePolicyError(Exception):
    """Base inference profile error."""


class ProfileOverrideNotAllowed(
    ProfilePolicyError
):
    """User tried to override a protected value."""


class ProfileLimitExceeded(
    ProfilePolicyError
):
    """Inference parameter exceeded profile limits."""


class ProfilePolicyService:
    """
    Enforces inference parameters defined by
    the selected AI profile.
    """

    def resolve_inference_parameters(
        self,
        profile_definition: dict[str, Any],
        *,
        temperature: float | None,
        max_tokens: int | None,
        top_p: float | None,
    ) -> dict[str, Any]:

        spec = profile_definition.get(
            "spec"
        )

        if not isinstance(
            spec,
            dict,
        ):
            raise ProfilePolicyError(
                "Profile spec is invalid"
            )

        defaults = spec.get(
            "defaults",
            {},
        )

        limits = spec.get(
            "limits",
            {},
        )

        security = spec.get(
            "security",
            {},
        )

        inference = spec.get(
            "inference",
            {},
        )

        if not isinstance(
            defaults,
            dict,
        ):
            raise ProfilePolicyError(
                "Profile defaults are invalid"
            )

        if not isinstance(
            limits,
            dict,
        ):
            raise ProfilePolicyError(
                "Profile limits are invalid"
            )

        if not isinstance(
            security,
            dict,
        ):
            raise ProfilePolicyError(
                "Profile security policy "
                "is invalid"
            )

        if not isinstance(
            inference,
            dict,
        ):
            inference = {}

        effective = {
            "temperature": float(
                defaults.get(
                    "temperature",
                    0.2,
                )
            ),

            "max_tokens": int(
                defaults.get(
                    "maxTokens",
                    512,
                )
            ),

            "top_p": float(
                defaults.get(
                    "topP",
                    0.9,
                )
            ),

            "max_model_len": int(
                defaults.get(
                    "maxModelLen",
                    4096,
                )
            ),

            "timeout_seconds": int(
                inference.get(
                    "timeoutSeconds",
                    120,
                )
            ),

            "streaming": (
                inference.get(
                    "streaming",
                    False,
                )
                is True
            ),
        }

        allow_user_overrides = (
            security.get(
                "allowUserOverrides",
                False,
            )
            is True
        )

        overridable_raw = security.get(
            "overridableParameters",
            [],
        )

        if not isinstance(
            overridable_raw,
            list,
        ):
            raise ProfilePolicyError(
                "Profile overridableParameters "
                "must be a list"
            )

        overridable = {
            str(item)
            for item in overridable_raw
        }

        requested = {
            "temperature": temperature,
            "maxTokens": max_tokens,
            "topP": top_p,
        }

        for (
            parameter,
            value,
        ) in requested.items():

            if value is None:
                continue

            if not allow_user_overrides:
                raise ProfileOverrideNotAllowed(
                    "User inference overrides "
                    "are disabled for this profile"
                )

            if parameter not in overridable:
                raise ProfileOverrideNotAllowed(
                    f"Parameter "
                    f"'{parameter}' "
                    "cannot be overridden"
                )

        # ==================================================
        # TEMPERATURE
        # ==================================================

        if temperature is not None:

            temperature_limits = (
                limits.get(
                    "temperature",
                    {},
                )
            )

            self._validate_range(
                parameter="temperature",
                value=temperature,
                limits=temperature_limits,
            )

            effective[
                "temperature"
            ] = temperature

        # ==================================================
        # TOP P
        # ==================================================

        if top_p is not None:

            top_p_limits = limits.get(
                "topP",
                {},
            )

            self._validate_range(
                parameter="topP",
                value=top_p,
                limits=top_p_limits,
            )

            effective[
                "top_p"
            ] = top_p

        # ==================================================
        # MAX TOKENS
        # ==================================================

        if max_tokens is not None:

            maximum = limits.get(
                "maxTokens"
            )

            if (
                maximum is not None
                and max_tokens
                > int(maximum)
            ):
                raise ProfileLimitExceeded(
                    f"maxTokens="
                    f"{max_tokens} "
                    "exceeds profile maximum "
                    f"{maximum}"
                )

            effective[
                "max_tokens"
            ] = max_tokens

        return effective

    @staticmethod
    def _validate_range(
        *,
        parameter: str,
        value: float,
        limits: Any,
    ) -> None:

        if not isinstance(
            limits,
            dict,
        ):
            return

        minimum = limits.get(
            "min"
        )

        maximum = limits.get(
            "max"
        )

        if (
            minimum is not None
            and value
            < float(minimum)
        ):
            raise ProfileLimitExceeded(
                f"{parameter}="
                f"{value} "
                "is below profile minimum "
                f"{minimum}"
            )

        if (
            maximum is not None
            and value
            > float(maximum)
        ):
            raise ProfileLimitExceeded(
                f"{parameter}="
                f"{value} "
                "exceeds profile maximum "
                f"{maximum}"
            )
