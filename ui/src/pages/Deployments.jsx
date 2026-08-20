import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  createDeployment,
  deleteDeployment,
  getDeployments,
  getModels,
  getProfiles,
} from "../api";


const RUNTIME_CAPACITIES = [
  4096,
  8192,
  16384,
  32768,
];


function formatCapacity(value) {
  return `${value / 1024}K`;
}


export default function Deployments() {
  const [deployments, setDeployments] =
    useState([]);

  const [models, setModels] =
    useState([]);

  const [profiles, setProfiles] =
    useState([]);

  const [error, setError] =
    useState("");

  const [form, setForm] =
    useState({
      name: "",
      model: "",
      profile: "",
      runtime: "auto",
      runtime_capacity: "auto",
    });


  const selectedProfile =
    useMemo(
      () =>
        profiles.find(
          (profile) =>
            profile.id === form.profile
        ),
      [
        profiles,
        form.profile,
      ]
    );


  const profileDefaultCapacity =
    Number(
      selectedProfile
        ?.max_model_len ||
      4096
    );


  const profileMaximumCapacity =
    Number(
      selectedProfile
        ?.limits
        ?.max_model_len ||
      profileDefaultCapacity
    );


  const capacityParameters =
    selectedProfile
      ?.security
      ?.overridable_parameters;


  const capacityOverrideAllowed =
    selectedProfile
      ?.security
      ?.allow_user_overrides === true &&
    Array.isArray(
      capacityParameters
    ) &&
    capacityParameters.includes(
      "runtimeCapacity"
    );


  const availableCapacities =
    RUNTIME_CAPACITIES.filter(
      (capacity) =>
        capacity >=
          profileDefaultCapacity &&
        capacity <=
          profileMaximumCapacity
    );


  async function refresh() {
    const [
      deploymentsResult,
      modelsResult,
      profilesResult,
    ] = await Promise.all([
      getDeployments(),
      getModels(),
      getProfiles(),
    ]);

    setDeployments(
      deploymentsResult
    );

    setModels(
      modelsResult
    );

    setProfiles(
      profilesResult
    );

    if (
      !form.model &&
      modelsResult.length
    ) {
      setForm(
        (current) => ({
          ...current,

          model:
            modelsResult[0].id,

          profile:
            modelsResult[0]
              .default_profile ||
            profilesResult[0]?.id ||
            "",

          runtime_capacity:
            "auto",
        })
      );
    }
  }


  useEffect(() => {
    refresh();
  }, []);


  async function submit(event) {
    event.preventDefault();

    setError("");

    const payload = {
      ...form,

      runtime_capacity:
        form.runtime_capacity ===
        "auto"
          ? null
          : Number(
              form.runtime_capacity
            ),
    };

    try {
      await createDeployment(
        payload
      );

      setForm(
        (current) => ({
          ...current,
          name: "",
          runtime_capacity:
            "auto",
        })
      );

      await refresh();

    } catch (err) {
      setError(
        err.message
      );
    }
  }


  async function remove(name) {
    await deleteDeployment(
      name
    );

    await refresh();
  }


  return (
    <div>

      <div className="section-intro">

        <div>

          <span className="eyebrow">
            WORKLOADS
          </span>

          <h2>
            Deploy AI assistants
          </h2>

          <p>
            Select the model, workload
            profile and runtime.
            Capacity remains governed
            by the selected profile.
          </p>

        </div>

      </div>


      <section className="panel">

        <div className="panel-header">
          <h3>
            New deployment
          </h3>
        </div>


        <form
          className="deployment-form"
          onSubmit={submit}
        >

          <label>
            Name

            <input
              value={form.name}

              placeholder="assistant-prod"

              onChange={
                (event) =>
                  setForm({
                    ...form,
                    name:
                      event.target.value,
                  })
              }

              required
            />
          </label>


          <label>
            Model

            <select
              value={form.model}

              onChange={
                (event) =>
                  setForm({
                    ...form,
                    model:
                      event.target.value,
                  })
              }
            >

              {models.map(
                (model) => (
                  <option
                    key={model.id}
                    value={model.id}
                  >
                    {
                      model.display_name
                    }
                  </option>
                )
              )}

            </select>
          </label>


          <label>
            Profile

            <select
              value={form.profile}

              onChange={
                (event) =>
                  setForm({
                    ...form,

                    profile:
                      event.target.value,

                    runtime_capacity:
                      "auto",
                  })
              }
            >

              {profiles.map(
                (profile) => (
                  <option
                    key={profile.id}
                    value={profile.id}
                  >
                    {
                      profile.display_name
                    }
                  </option>
                )
              )}

            </select>
          </label>


          <label>
            Runtime

            <select
              value={form.runtime}

              onChange={
                (event) =>
                  setForm({
                    ...form,

                    runtime:
                      event.target.value,
                  })
              }
            >

              <option value="auto">
                Automatic
              </option>

              <option value="vllm-metal">
                vLLM Metal
              </option>

              <option value="vllm-cuda">
                vLLM CUDA
              </option>

              <option value="llama-cpp-metal">
                llama.cpp Metal
              </option>

            </select>
          </label>


          <label>
            Runtime capacity

            <select
              value={
                form.runtime_capacity
              }

              disabled={
                !capacityOverrideAllowed
              }

              onChange={
                (event) =>
                  setForm({
                    ...form,

                    runtime_capacity:
                      event.target.value,
                  })
              }
            >

              <option value="auto">
                Auto ({
                  formatCapacity(
                    profileDefaultCapacity
                  )
                })
              </option>

              {
                capacityOverrideAllowed &&
                availableCapacities.map(
                  (capacity) => (
                    <option
                      key={capacity}
                      value={capacity}
                    >
                      {
                        formatCapacity(
                          capacity
                        )
                      }
                    </option>
                  )
                )
              }

            </select>

          </label>


          <button className="primary-button">
            Deploy
          </button>

        </form>


        {error && (
          <div className="error-box">
            {error}
          </div>
        )}

      </section>


      <section className="panel">

        <div className="panel-header">

          <div>
            <span className="eyebrow">
              CURRENT STATE
            </span>

            <h3>
              Deployments
            </h3>
          </div>

        </div>


        <div className="table">

          {deployments.map(
            (deployment) => (

              <div
                className="table-row"
                key={deployment.id}
              >

                <div>
                  <strong>
                    {deployment.name}
                  </strong>

                  <span>
                    {deployment.model}
                  </span>
                </div>


                <div>
                  <span>
                    Profile
                  </span>

                  <strong>
                    {deployment.profile}
                  </strong>
                </div>


                <div>
                  <span>
                    Runtime
                  </span>

                  <strong>
                    {deployment.runtime}
                  </strong>
                </div>


                <div>
                  <span
                    className={
                      `status-badge ${
                        deployment.status
                      }`
                    }
                  >
                    {deployment.status}
                  </span>
                </div>


                <button
                  className="danger-button"
                  onClick={
                    () =>
                      remove(
                        deployment.name
                      )
                  }
                >
                  Delete
                </button>

              </div>

            )
          )}

        </div>

      </section>

    </div>
  );
}
