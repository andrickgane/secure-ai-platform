import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  FiCopy,
  FiEdit3,
  FiLock,
  FiPlus,
  FiRefreshCw,
  FiSearch,
  FiShield,
  FiSliders,
  FiTrash2,
  FiX,
} from "react-icons/fi";

import {
  getCurrentUser,
  getProfiles,
  getRuntimes,
} from "../api";

import {
  cloneProfile,
  createProfile,
  deleteProfile,
  getCustomProfile,
  updateProfile,
} from "../profileApi";

import "./Profiles.css";


function emptyValue(
  value
) {
  return (
    value === null ||
    value === undefined
  )
    ? ""
    : String(value);
}


function listValue(
  value
) {
  return Array.isArray(value)
    ? value.join(", ")
    : "";
}


function parseList(
  value
) {
  return String(
    value || ""
  )
    .split(",")
    .map(
      (item) =>
        item.trim()
    )
    .filter(Boolean);
}


function setIfValue(
  object,
  key,
  value,
  parser = (
    item
  ) => item
) {
  if (
    value === "" ||
    value === null ||
    value === undefined
  ) {
    return;
  }

  object[key] = parser(
    value
  );
}


function buildOverrides(
  form
) {
  const overrides = {};

  const defaults = {};

  setIfValue(
    defaults,
    "maxModelLen",
    form.maxModelLen,
    Number
  );

  setIfValue(
    defaults,
    "maxTokens",
    form.maxTokens,
    Number
  );

  setIfValue(
    defaults,
    "temperature",
    form.temperature,
    Number
  );

  setIfValue(
    defaults,
    "topP",
    form.topP,
    Number
  );

  if (
    Object.keys(
      defaults
    ).length
  ) {
    overrides.defaults =
      defaults;
  }


  const inference = {};

  setIfValue(
    inference,
    "timeoutSeconds",
    form.timeoutSeconds,
    Number
  );

  if (
    form.streaming !== ""
  ) {
    inference.streaming =
      form.streaming === "true";
  }

  const concurrency = {};

  setIfValue(
    concurrency,
    "maxRequests",
    form.maxRequests,
    Number
  );

  if (
    Object.keys(
      concurrency
    ).length
  ) {
    inference.concurrency =
      concurrency;
  }

  if (
    Object.keys(
      inference
    ).length
  ) {
    overrides.inference =
      inference;
  }


  const runtimePolicy = {};

  if (
    form.preferredRuntimes
      .trim()
  ) {
    runtimePolicy
      .preferredRuntimes =
      parseList(
        form.preferredRuntimes
      );
  }

  if (
    form.allowedRuntimes
      .trim()
  ) {
    runtimePolicy
      .allowedRuntimes =
      parseList(
        form.allowedRuntimes
      );
  }

  if (
    Object.keys(
      runtimePolicy
    ).length
  ) {
    overrides.runtimePolicy =
      runtimePolicy;
  }


  const security = {};

  if (
    form.allowUserOverrides !== ""
  ) {
    security
      .allowUserOverrides =
      form.allowUserOverrides
      === "true";
  }

  if (
    form.overridableParameters
      .trim()
  ) {
    security
      .overridableParameters =
      parseList(
        form.overridableParameters
      );
  }

  if (
    Object.keys(
      security
    ).length
  ) {
    overrides.security =
      security;
  }


  return overrides;
}


function createInitialForm(
  profiles
) {
  const interactive =
    profiles.find(
      (item) =>
        item.id ===
        "interactive"
    );

  return {
    name: "",

    displayName: "",

    description: "",

    category: "custom",

    baseProfile:
      interactive?.id ||
      profiles[0]?.id ||
      "",

    maxModelLen: "",

    maxTokens: "",

    temperature: "",

    topP: "",

    streaming: "",

    maxRequests: "",

    timeoutSeconds: "",

    preferredRuntimes: "",

    allowedRuntimes: "",

    allowUserOverrides: "",

    overridableParameters: "",
  };
}


function cloneInitialForm(
  profile
) {
  return {
    name: "",

    displayName:
      `${profile.display_name} Clone`,

    description: "",

    category:
      profile.category ||
      "custom",

    baseProfile:
      profile.id,

    maxModelLen: "",

    maxTokens: "",

    temperature: "",

    topP: "",

    streaming: "",

    maxRequests: "",

    timeoutSeconds: "",

    preferredRuntimes: "",

    allowedRuntimes: "",

    allowUserOverrides: "",

    overridableParameters: "",
  };
}


function formFromCustomProfile(
  profile
) {
  const overrides =
    profile.overrides || {};

  const defaults =
    overrides.defaults || {};

  const inference =
    overrides.inference || {};

  const concurrency =
    inference.concurrency || {};

  const runtimePolicy =
    overrides.runtimePolicy || {};

  const security =
    overrides.security || {};

  const hasAllowOverrides =
    Object.prototype
      .hasOwnProperty
      .call(
        security,
        "allowUserOverrides"
      );

  const hasStreaming =
    Object.prototype
      .hasOwnProperty
      .call(
        inference,
        "streaming"
      );

  return {
    name:
      profile.name,

    displayName:
      profile.display_name,

    description:
      profile.description || "",

    category:
      profile.category ||
      "custom",

    baseProfile:
      profile.base_profile,

    maxModelLen:
      emptyValue(
        defaults.maxModelLen
      ),

    maxTokens:
      emptyValue(
        defaults.maxTokens
      ),

    temperature:
      emptyValue(
        defaults.temperature
      ),

    topP:
      emptyValue(
        defaults.topP
      ),

    streaming:
      hasStreaming
        ? String(
            inference.streaming
          )
        : "",

    maxRequests:
      emptyValue(
        concurrency.maxRequests
      ),

    timeoutSeconds:
      emptyValue(
        inference.timeoutSeconds
      ),

    preferredRuntimes:
      listValue(
        runtimePolicy
          .preferredRuntimes
      ),

    allowedRuntimes:
      listValue(
        runtimePolicy
          .allowedRuntimes
      ),

    allowUserOverrides:
      hasAllowOverrides
        ? String(
            security
              .allowUserOverrides
          )
        : "",

    overridableParameters:
      listValue(
        security
          .overridableParameters
      ),
  };
}


function SourceBadge({
  profile,
}) {
  if (
    profile.source ===
    "builtin"
  ) {
    return (
      <span className="profile-source profile-source-builtin">
        <FiLock />
        Built-in
      </span>
    );
  }

  return (
    <span className="profile-source profile-source-custom">
      <FiSliders />
      Custom
    </span>
  );
}


function ProfileEditorModal({
  mode,
  sourceProfile,
  profiles,
  runtimes,
  onClose,
  onSaved,
}) {
  const [
    form,
    setForm,
  ] = useState(
    mode === "clone"
      ? cloneInitialForm(
          sourceProfile
        )
      : createInitialForm(
          profiles
        )
  );

  const [
    loading,
    setLoading,
  ] = useState(
    mode === "edit"
  );

  const [
    submitting,
    setSubmitting,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState("");


  useEffect(() => {
    if (
      mode !== "edit" ||
      !sourceProfile
    ) {
      return;
    }

    let active = true;

    async function load() {
      setLoading(true);
      setError("");

      try {
        const result =
          await getCustomProfile(
            sourceProfile.id
          );

        if (active) {
          setForm(
            formFromCustomProfile(
              result
            )
          );
        }

      } catch (err) {
        if (active) {
          setError(
            err.message ||
            "Unable to load profile"
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
    mode,
    sourceProfile,
  ]);


  function update(
    field,
    value
  ) {
    setForm(
      (current) => ({
        ...current,
        [field]: value,
      })
    );
  }


  async function submit(
    event
  ) {
    event.preventDefault();

    setSubmitting(true);
    setError("");

    const overrides =
      buildOverrides(
        form
      );

    try {
      if (
        mode === "create"
      ) {
        await createProfile({
          name:
            form.name.trim(),

          display_name:
            form.displayName.trim(),

          description:
            form.description.trim()
            || null,

          category:
            form.category.trim()
            || "custom",

          base_profile:
            form.baseProfile,

          overrides,
        });
      }

      if (
        mode === "clone"
      ) {
        await cloneProfile(
          sourceProfile.id,
          {
            name:
              form.name.trim(),

            display_name:
              form.displayName.trim()
              || null,

            description:
              form.description.trim()
              || null,

            category:
              form.category.trim()
              || null,

            overrides,
          }
        );
      }

      if (
        mode === "edit"
      ) {
        await updateProfile(
          sourceProfile.id,
          {
            display_name:
              form.displayName.trim(),

            description:
              form.description.trim()
              || null,

            category:
              form.category.trim()
              || "custom",

            base_profile:
              form.baseProfile,

            overrides,
          }
        );
      }

      await onSaved();

      onClose();

    } catch (err) {
      setError(
        err.message ||
        "Unable to save profile"
      );

    } finally {
      setSubmitting(false);
    }
  }


  const title =
    mode === "create"
      ? "Create custom profile"
      : mode === "clone"
        ? `Clone ${sourceProfile.display_name}`
        : `Edit ${sourceProfile.display_name}`;


  const baseProfiles =
    profiles.filter(
      (item) =>
        mode !== "edit" ||
        item.id !==
          sourceProfile?.id
    );


  return (
    <div
      className="profile-modal-backdrop"
      onMouseDown={
        (event) => {
          if (
            event.target ===
            event.currentTarget
          ) {
            onClose();
          }
        }
      }
    >

      <div className="profile-modal">

        <div className="profile-modal-header">

          <div>

            <span className="eyebrow">
              PROFILE ENGINE
            </span>

            <h2>
              {title}
            </h2>

            <p>
              Store only profile differences.
              Unspecified values continue to
              inherit from the base profile.
            </p>

          </div>


          <button
            type="button"
            className="profile-icon-button"
            onClick={onClose}
          >
            <FiX />
          </button>

        </div>


        {loading ? (
          <div className="profile-modal-loading">
            <FiRefreshCw />
            Loading profile...
          </div>

        ) : (

          <form
            className="profile-editor"
            onSubmit={submit}
          >

            {error && (
              <div className="profile-error">
                {error}
              </div>
            )}


            <section className="profile-form-section">

              <div className="profile-section-heading">

                <div>
                  <strong>
                    Identity
                  </strong>

                  <span>
                    Profile metadata and inheritance.
                  </span>
                </div>

              </div>


              <div className="profile-form-grid">

                <label>
                  Profile ID

                  <input
                    value={form.name}
                    disabled={
                      mode === "edit"
                    }
                    required
                    onChange={
                      (event) =>
                        update(
                          "name",
                          event.target.value
                        )
                    }
                    placeholder="team-coding"
                  />
                </label>


                <label>
                  Display name

                  <input
                    value={
                      form.displayName
                    }
                    required
                    onChange={
                      (event) =>
                        update(
                          "displayName",
                          event.target.value
                        )
                    }
                    placeholder="Team Coding"
                  />
                </label>


                <label>
                  Category

                  <input
                    value={
                      form.category
                    }
                    onChange={
                      (event) =>
                        update(
                          "category",
                          event.target.value
                        )
                    }
                    placeholder="coding"
                  />
                </label>


                <label>
                  Base profile

                  {mode === "clone" ? (
                    <input
                      value={
                        sourceProfile.id
                      }
                      disabled
                    />

                  ) : (

                    <select
                      value={
                        form.baseProfile
                      }
                      required
                      onChange={
                        (event) =>
                          update(
                            "baseProfile",
                            event.target.value
                          )
                      }
                    >
                      {baseProfiles.map(
                        (profile) => (
                          <option
                            key={
                              profile.id
                            }
                            value={
                              profile.id
                            }
                          >
                            {
                              profile.display_name
                            }
                            {" · "}
                            {
                              profile.source
                            }
                          </option>
                        )
                      )}
                    </select>

                  )}

                </label>

              </div>


              <label>
                Description

                <textarea
                  rows="3"
                  value={
                    form.description
                  }
                  onChange={
                    (event) =>
                      update(
                        "description",
                        event.target.value
                      )
                  }
                  placeholder="Describe the intended workload..."
                />
              </label>

            </section>


            <section className="profile-form-section">

              <div className="profile-section-heading">

                <div>
                  <strong>
                    Inference overrides
                  </strong>

                  <span>
                    Leave a field empty to inherit it.
                  </span>
                </div>

              </div>


              <div className="profile-form-grid profile-form-grid-4">

                <label>
                  Max context

                  <input
                    type="number"
                    min="1"
                    value={
                      form.maxModelLen
                    }
                    onChange={
                      (event) =>
                        update(
                          "maxModelLen",
                          event.target.value
                        )
                    }
                    placeholder="inherit"
                  />
                </label>


                <label>
                  Max tokens

                  <input
                    type="number"
                    min="1"
                    value={
                      form.maxTokens
                    }
                    onChange={
                      (event) =>
                        update(
                          "maxTokens",
                          event.target.value
                        )
                    }
                    placeholder="inherit"
                  />
                </label>


                <label>
                  Temperature

                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={
                      form.temperature
                    }
                    onChange={
                      (event) =>
                        update(
                          "temperature",
                          event.target.value
                        )
                    }
                    placeholder="inherit"
                  />
                </label>


                <label>
                  Top P

                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="1"
                    value={
                      form.topP
                    }
                    onChange={
                      (event) =>
                        update(
                          "topP",
                          event.target.value
                        )
                    }
                    placeholder="inherit"
                  />
                </label>


                <label>
                  Concurrency

                  <input
                    type="number"
                    min="1"
                    value={
                      form.maxRequests
                    }
                    onChange={
                      (event) =>
                        update(
                          "maxRequests",
                          event.target.value
                        )
                    }
                    placeholder="inherit"
                  />
                </label>


                <label>
                  Timeout seconds

                  <input
                    type="number"
                    min="1"
                    value={
                      form.timeoutSeconds
                    }
                    onChange={
                      (event) =>
                        update(
                          "timeoutSeconds",
                          event.target.value
                        )
                    }
                    placeholder="inherit"
                  />
                </label>


                <label>
                  Streaming

                  <select
                    value={
                      form.streaming
                    }
                    onChange={
                      (event) =>
                        update(
                          "streaming",
                          event.target.value
                        )
                    }
                  >
                    <option value="">
                      Inherit
                    </option>

                    <option value="true">
                      Enabled
                    </option>

                    <option value="false">
                      Disabled
                    </option>
                  </select>
                </label>

              </div>

            </section>


            <section className="profile-form-section">

              <div className="profile-section-heading">

                <div>
                  <strong>
                    Runtime policy
                  </strong>

                  <span>
                    Comma-separated runtime IDs.
                    Blank means inherit.
                  </span>
                </div>

              </div>


              <div className="profile-form-grid">

                <label>
                  Preferred runtimes

                  <input
                    value={
                      form.preferredRuntimes
                    }
                    onChange={
                      (event) =>
                        update(
                          "preferredRuntimes",
                          event.target.value
                        )
                    }
                    placeholder="vllm-metal, vllm-cuda"
                  />

                  <small>
                    Available:
                    {" "}
                    {
                      runtimes
                        .map(
                          (item) =>
                            item.id
                        )
                        .join(", ")
                    }
                  </small>
                </label>


                <label>
                  Allowed runtimes

                  <input
                    value={
                      form.allowedRuntimes
                    }
                    onChange={
                      (event) =>
                        update(
                          "allowedRuntimes",
                          event.target.value
                        )
                    }
                    placeholder="vllm-metal, llama-cpp-metal"
                  />
                </label>

              </div>

            </section>


            <section className="profile-form-section">

              <div className="profile-section-heading">

                <div>
                  <strong>
                    Security policy
                  </strong>

                  <span>
                    Control which inference values
                    callers may override.
                  </span>
                </div>

              </div>


              <div className="profile-form-grid">

                <label>
                  User overrides

                  <select
                    value={
                      form.allowUserOverrides
                    }
                    onChange={
                      (event) =>
                        update(
                          "allowUserOverrides",
                          event.target.value
                        )
                    }
                  >
                    <option value="">
                      Inherit
                    </option>

                    <option value="true">
                      Allowed
                    </option>

                    <option value="false">
                      Locked
                    </option>
                  </select>
                </label>


                <label>
                  Overridable parameters

                  <input
                    value={
                      form.overridableParameters
                    }
                    onChange={
                      (event) =>
                        update(
                          "overridableParameters",
                          event.target.value
                        )
                    }
                    placeholder="temperature, maxTokens, topP"
                  />
                </label>

              </div>

            </section>


            <div className="profile-modal-actions">

              <button
                type="button"
                className="profile-button-secondary"
                onClick={onClose}
              >
                Cancel
              </button>


              <button
                className="profile-button-primary"
                disabled={
                  submitting
                }
              >
                {submitting
                  ? "Saving..."
                  : mode === "clone"
                    ? "Create clone"
                    : mode === "edit"
                      ? "Save profile"
                      : "Create profile"}
              </button>

            </div>

          </form>

        )}

      </div>

    </div>
  );
}


function ProfileCard({
  profile,
  canManage,
  onClone,
  onEdit,
  onDelete,
}) {
  return (
    <article className="profile-card">

      <div className="profile-card-header">

        <div className="profile-title-group">

          <div className="profile-icon">
            {
              profile.source ===
              "builtin"
                ? <FiShield />
                : <FiSliders />
            }
          </div>


          <div>

            <h3>
              {
                profile.display_name
              }
            </h3>

            <span className="profile-id">
              {profile.id}
            </span>

          </div>

        </div>


        <SourceBadge
          profile={profile}
        />

      </div>


      <p className="profile-description">
        {
          profile.description ||
          "No description."
        }
      </p>


      {profile.base_profile && (
        <div className="profile-inheritance">
          inherits
          {" "}
          <strong>
            {
              profile.base_profile
            }
          </strong>
        </div>
      )}


      <div className="profile-metrics">

        <div>
          <span>
            Context
          </span>

          <strong>
            {
              profile.max_model_len
            }
          </strong>
        </div>


        <div>
          <span>
            Max tokens
          </span>

          <strong>
            {
              profile.max_tokens
            }
          </strong>
        </div>


        <div>
          <span>
            Temperature
          </span>

          <strong>
            {
              profile.temperature
            }
          </strong>
        </div>


        <div>
          <span>
            Concurrency
          </span>

          <strong>
            {
              profile.inference
                ?.max_requests ?? "—"
            }
          </strong>
        </div>

      </div>


      <div className="profile-policy-block">

        <span>
          Preferred runtimes
        </span>

        <div className="profile-runtime-list">

          {
            profile
              .preferred_runtimes
              ?.length
              ? profile
                  .preferred_runtimes
                  .map(
                    (runtime) => (
                      <code
                        key={
                          runtime
                        }
                      >
                        {runtime}
                      </code>
                    )
                  )
              : (
                <small>
                  Platform order
                </small>
              )
          }

        </div>

      </div>


      <div className="profile-policy-footer">

        <span>
          {
            profile.security
              ?.allow_user_overrides
              ? "Controlled user overrides"
              : "Inference parameters locked"
          }
        </span>

        <span>
          {
            profile.inference
              ?.streaming
              ? "Streaming"
              : "Non-streaming"
          }
        </span>

      </div>


      {canManage && (
        <div className="profile-card-actions">

          <button
            type="button"
            className="profile-action-button"
            onClick={
              () =>
                onClone(
                  profile
                )
            }
          >
            <FiCopy />
            Clone
          </button>


          {
            profile.source ===
            "custom" && (
              <>

                <button
                  type="button"
                  className="profile-action-button"
                  onClick={
                    () =>
                      onEdit(
                        profile
                      )
                  }
                >
                  <FiEdit3 />
                  Edit
                </button>


                <button
                  type="button"
                  className="profile-action-button profile-action-danger"
                  onClick={
                    () =>
                      onDelete(
                        profile
                      )
                  }
                >
                  <FiTrash2 />
                  Delete
                </button>

              </>
            )
          }

        </div>
      )}

    </article>
  );
}


export default function Profiles() {
  const [
    profiles,
    setProfiles,
  ] = useState([]);

  const [
    runtimes,
    setRuntimes,
  ] = useState([]);

  const [
    currentUser,
    setCurrentUser,
  ] = useState(null);

  const [
    loading,
    setLoading,
  ] = useState(true);

  const [
    error,
    setError,
  ] = useState("");

  const [
    search,
    setSearch,
  ] = useState("");

  const [
    sourceFilter,
    setSourceFilter,
  ] = useState("all");

  const [
    modal,
    setModal,
  ] = useState(null);


  const canManage =
    currentUser?.role ===
    "platform_admin";


  async function refresh() {
    setLoading(true);
    setError("");

    try {
      const [
        profileResult,
        runtimeResult,
        userResult,
      ] = await Promise.all([
        getProfiles(),
        getRuntimes(),
        getCurrentUser(),
      ]);

      setProfiles(
        profileResult
      );

      setRuntimes(
        runtimeResult
      );

      setCurrentUser(
        userResult
      );

    } catch (err) {
      setError(
        err.message ||
        "Unable to load profiles"
      );

    } finally {
      setLoading(false);
    }
  }


  useEffect(() => {
    refresh();
  }, []);


  const stats = useMemo(
    () => ({
      total:
        profiles.length,

      builtin:
        profiles.filter(
          (item) =>
            item.source ===
            "builtin"
        ).length,

      custom:
        profiles.filter(
          (item) =>
            item.source ===
            "custom"
        ).length,
    }),
    [
      profiles,
    ]
  );


  const filteredProfiles =
    useMemo(
      () => {
        const needle =
          search
            .trim()
            .toLowerCase();

        return profiles.filter(
          (profile) => {
            if (
              sourceFilter !==
                "all" &&
              profile.source !==
                sourceFilter
            ) {
              return false;
            }

            if (!needle) {
              return true;
            }

            const haystack = [
              profile.id,
              profile.display_name,
              profile.description,
              profile.category,
              profile.base_profile,
              ...(
                profile.allowed_runtimes ||
                []
              ),
              ...(
                profile.preferred_runtimes ||
                []
              ),
            ]
              .filter(Boolean)
              .join(" ")
              .toLowerCase();

            return haystack.includes(
              needle
            );
          }
        );
      },
      [
        profiles,
        search,
        sourceFilter,
      ]
    );


  async function removeProfile(
    profile
  ) {
    const confirmed =
      window.confirm(
        `Delete custom profile '${profile.id}'?`
      );

    if (!confirmed) {
      return;
    }

    setError("");

    try {
      await deleteProfile(
        profile.id
      );

      await refresh();

    } catch (err) {
      setError(
        err.message ||
        "Unable to delete profile"
      );
    }
  }


  return (
    <div className="profiles-page">

      <div className="profiles-heading">

        <div>

          <span className="eyebrow">
            PROFILE ENGINE
          </span>

          <h2>
            AI workload profiles
          </h2>

          <p>
            Govern runtime selection,
            inference parameters,
            resources and security
            through inherited workload
            policies.
          </p>

        </div>


        <div className="profiles-heading-actions">

          <button
            type="button"
            className="profile-button-secondary"
            onClick={refresh}
            disabled={loading}
          >
            <FiRefreshCw />
            Refresh
          </button>


          {canManage && (
            <button
              type="button"
              className="profile-button-primary"
              onClick={
                () =>
                  setModal({
                    mode: "create",
                    profile: null,
                  })
              }
            >
              <FiPlus />
              Create profile
            </button>
          )}

        </div>

      </div>


      <div className="profiles-summary">

        <div>

          <span>
            Total profiles
          </span>

          <strong>
            {stats.total}
          </strong>

        </div>


        <div>

          <span>
            Built-in
          </span>

          <strong>
            {stats.builtin}
          </strong>

        </div>


        <div>

          <span>
            Custom
          </span>

          <strong>
            {stats.custom}
          </strong>

        </div>

      </div>


      <div className="profiles-toolbar">

        <div className="profiles-search">

          <FiSearch />

          <input
            value={search}
            onChange={
              (event) =>
                setSearch(
                  event.target.value
                )
            }
            placeholder="Search profiles, runtimes..."
          />

        </div>


        <select
          value={sourceFilter}
          onChange={
            (event) =>
              setSourceFilter(
                event.target.value
              )
          }
        >
          <option value="all">
            All profiles
          </option>

          <option value="builtin">
            Built-in
          </option>

          <option value="custom">
            Custom
          </option>
        </select>

      </div>


      {error && (
        <div className="profile-error profiles-page-error">
          {error}
        </div>
      )}


      {loading ? (
        <div className="profiles-loading">
          <FiRefreshCw />
          Loading profile catalog...
        </div>

      ) : (

        <div className="profiles-grid">

          {
            filteredProfiles
              .length === 0 && (
              <div className="profiles-empty">

                <FiSliders />

                <h3>
                  No profiles found
                </h3>

                <p>
                  Adjust your search or
                  create a custom profile.
                </p>

              </div>
            )
          }


          {
            filteredProfiles.map(
              (profile) => (
                <ProfileCard
                  key={
                    profile.id
                  }
                  profile={
                    profile
                  }
                  canManage={
                    canManage
                  }
                  onClone={
                    (item) =>
                      setModal({
                        mode:
                          "clone",
                        profile:
                          item,
                      })
                  }
                  onEdit={
                    (item) =>
                      setModal({
                        mode:
                          "edit",
                        profile:
                          item,
                      })
                  }
                  onDelete={
                    removeProfile
                  }
                />
              )
            )
          }

        </div>

      )}


      {modal && (
        <ProfileEditorModal
          mode={
            modal.mode
          }
          sourceProfile={
            modal.profile
          }
          profiles={
            profiles
          }
          runtimes={
            runtimes
          }
          onClose={
            () =>
              setModal(null)
          }
          onSaved={
            refresh
          }
        />
      )}

    </div>
  );
}
