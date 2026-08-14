import {
  useEffect,
  useState,
} from "react";

import {
  createDeployment,
  deleteDeployment,
  getDeployments,
  getModels,
  getProfiles,
} from "../api";


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
    });


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

    if (!form.model &&
        modelsResult.length) {

      setForm((current) => ({
        ...current,

        model:
          modelsResult[0].id,

        profile:
          modelsResult[0]
            .default_profile ||
          profilesResult[0]?.id ||
          "",
      }));
    }
  }


  useEffect(() => {
    refresh();
  }, []);


  async function submit(event) {
    event.preventDefault();

    setError("");

    try {
      await createDeployment(
        form
      );

      setForm((current) => ({
        ...current,
        name: "",
      }));

      await refresh();

    } catch (err) {
      setError(err.message);
    }
  }


  async function remove(name) {
    await deleteDeployment(name);

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
            Select only the model and
            workload profile. Runtime
            selection can be delegated
            to the platform.
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

              onChange={(event) =>
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

              onChange={(event) =>
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

              onChange={(event) =>
                setForm({
                  ...form,
                  profile:
                    event.target.value,
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

              onChange={(event) =>
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
                  onClick={() =>
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
