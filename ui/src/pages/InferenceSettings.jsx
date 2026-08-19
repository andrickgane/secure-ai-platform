import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  FiLock,
  FiRefreshCw,
  FiSliders,
} from "react-icons/fi";

import {
  getEffectiveProfile,
} from "../profileApi";

import "./InferenceSettings.css";


function objectValue(
  value
) {
  return (
    value &&
    typeof value === "object" &&
    !Array.isArray(value)
  )
    ? value
    : {};
}


function ParameterField({
  label,
  name,
  value,
  defaultValue,
  min,
  max,
  step,
  enabled,
  disabled,
  onChange,
}) {
  const locked =
    !enabled;

  return (
    <label className="aiw-setting-field">

      <div className="aiw-setting-label">

        <span>
          {label}
        </span>

        {locked && (
          <FiLock
            title="Locked by profile"
          />
        )}

      </div>

      <input
        type="number"

        value={value}

        min={min}

        max={max}

        step={step}

        disabled={
          disabled ||
          locked
        }

        placeholder={
          defaultValue != null
            ? String(defaultValue)
            : "Profile default"
        }

        onChange={
          (event) =>
            onChange(
              name,
              event.target.value
            )
        }
      />

      <small>
        Default:
        {" "}
        <strong>
          {
            defaultValue ??
            "—"
          }
        </strong>

        {
          min != null &&
          max != null &&
          (
            <>
              {" "}
              · limits
              {" "}
              {min}
              {" → "}
              {max}
            </>
          )
        }

        {
          min == null &&
          max != null &&
          (
            <>
              {" "}
              · max
              {" "}
              {max}
            </>
          )
        }
      </small>

    </label>
  );
}


export default function InferenceSettings({
  selectedDeployment,
  value,
  onChange,
  disabled = false,
}) {
  const [
    profile,
    setProfile,
  ] = useState(null);

  const [
    loading,
    setLoading,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState("");


  const profileId =
    selectedDeployment
      ?.profile || "";


  useEffect(() => {
    if (!profileId) {
      setProfile(null);
      setError("");

      return;
    }

    let active = true;

    async function load() {
      setLoading(true);
      setError("");

      try {
        const result =
          await getEffectiveProfile(
            profileId
          );

        if (active) {
          setProfile(
            result
          );
        }

      } catch (err) {
        if (active) {
          setProfile(null);

          setError(
            err.message ||
            "Unable to load profile policy"
          );
        }

      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    load();

    return () => {
      active = false;
    };

  }, [
    profileId,
  ]);


  const policy =
    useMemo(
      () => {
        const definition =
          objectValue(
            profile?.definition
          );

        const spec =
          objectValue(
            definition.spec
          );

        const defaults =
          objectValue(
            spec.defaults
          );

        const limits =
          objectValue(
            spec.limits
          );

        const temperatureLimits =
          objectValue(
            limits.temperature
          );

        const topPLimits =
          objectValue(
            limits.topP
          );

        const security =
          objectValue(
            spec.security
          );

        const overridable =
          Array.isArray(
            security
              .overridableParameters
          )
            ? security
                .overridableParameters
            : [];

        return {
          defaults,

          limits,

          temperatureLimits,

          topPLimits,

          allowUserOverrides:
            security
              .allowUserOverrides ===
            true,

          overridable,
        };
      },
      [
        profile,
      ]
    );


  function canOverride(
    parameter
  ) {
    return (
      policy
        .allowUserOverrides &&
      policy
        .overridable
        .includes(
          parameter
        )
    );
  }


  function update(
    name,
    newValue
  ) {
    onChange({
      ...value,
      [name]:
        newValue,
    });
  }


  function reset() {
    onChange({
      temperature: "",
      maxTokens: "",
      topP: "",
    });
  }


  const overrideCount =
    Object.values(
      value
    ).filter(
      (item) =>
        item !== ""
    ).length;


  return (
    <section className="aiw-settings-panel">

      <div className="aiw-settings-header">

        <div className="aiw-settings-title">

          <div className="aiw-settings-icon">
            <FiSliders />
          </div>

          <div>

            <strong>
              Inference settings
            </strong>

            <span>
              Governed by
              {" "}
              {
                profileId ||
                "the deployment profile"
              }
            </span>

          </div>

        </div>


        <button
          type="button"
          className="aiw-settings-reset"
          disabled={
            disabled ||
            overrideCount === 0
          }
          onClick={reset}
        >
          <FiRefreshCw />
          Reset defaults
        </button>

      </div>


      {loading && (
        <div className="aiw-settings-loading">
          Loading profile policy...
        </div>
      )}


      {error && (
        <div className="aiw-settings-error">
          {error}
        </div>
      )}


      {
        !loading &&
        !error &&
        profile &&
        (
          <>

            <div className="aiw-settings-grid">

              <ParameterField
                label="Temperature"
                name="temperature"

                value={
                  value.temperature
                }

                defaultValue={
                  policy
                    .defaults
                    .temperature
                }

                min={
                  policy
                    .temperatureLimits
                    .min
                }

                max={
                  policy
                    .temperatureLimits
                    .max
                }

                step="0.01"

                enabled={
                  canOverride(
                    "temperature"
                  )
                }

                disabled={
                  disabled
                }

                onChange={
                  update
                }
              />


              <ParameterField
                label="Max tokens"
                name="maxTokens"

                value={
                  value.maxTokens
                }

                defaultValue={
                  policy
                    .defaults
                    .maxTokens
                }

                min={1}

                max={
                  policy
                    .limits
                    .maxTokens
                }

                step="1"

                enabled={
                  canOverride(
                    "maxTokens"
                  )
                }

                disabled={
                  disabled
                }

                onChange={
                  update
                }
              />


              <ParameterField
                label="Top P"
                name="topP"

                value={
                  value.topP
                }

                defaultValue={
                  policy
                    .defaults
                    .topP
                }

                min={
                  policy
                    .topPLimits
                    .min
                }

                max={
                  policy
                    .topPLimits
                    .max
                }

                step="0.01"

                enabled={
                  canOverride(
                    "topP"
                  )
                }

                disabled={
                  disabled
                }

                onChange={
                  update
                }
              />


              <div className="aiw-setting-readonly">

                <span>
                  Context
                </span>

                <strong>
                  {
                    policy
                      .defaults
                      .maxModelLen ??
                    "—"
                  }
                </strong>

                <small>
                  Profile controlled
                  {" "}
                  · max
                  {" "}
                  {
                    policy
                      .limits
                      .maxModelLen ??
                    "—"
                  }
                </small>

              </div>

            </div>


            <div className="aiw-settings-policy">

              <div>

                <span>
                  Profile
                </span>

                <strong>
                  {profileId}
                </strong>

              </div>


              <div>

                <span>
                  User overrides
                </span>

                <strong>
                  {
                    policy
                      .allowUserOverrides
                      ? "Controlled"
                      : "Locked"
                  }
                </strong>

              </div>


              <div>

                <span>
                  Active overrides
                </span>

                <strong>
                  {overrideCount}
                </strong>

              </div>


              <div>

                <span>
                  Runtime
                </span>

                <strong>
                  {
                    selectedDeployment
                      ?.runtime ||
                    "—"
                  }
                </strong>

              </div>

            </div>

          </>
        )
      }

    </section>
  );
}
