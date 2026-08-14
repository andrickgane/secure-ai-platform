import {
  useEffect,
  useState,
} from "react";

import {
  getProfiles,
} from "../api";


export default function Profiles() {
  const [profiles, setProfiles] =
    useState([]);


  useEffect(() => {
    getProfiles()
      .then(setProfiles);
  }, []);


  return (
    <div>

      <div className="section-intro">

        <div>

          <span className="eyebrow">
            INFERENCE POLICY
          </span>

          <h2>
            AI workload profiles
          </h2>

          <p>
            Profiles govern sampling,
            resources, runtime access
            and inference limits.
          </p>

        </div>

      </div>


      <div className="card-grid">

        {profiles.map(
          (profile) => (

            <article
              className="catalog-card"
              key={profile.id}
            >

              <div className="card-topline">

                <span className="badge">
                  {profile.category}
                </span>

              </div>


              <h3>
                {profile.display_name}
              </h3>

              <p>
                {profile.description}
              </p>


              <div className="parameter-grid">

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
                    Max output
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
                      profile
                        .inference
                        .max_requests
                    }
                  </strong>
                </div>

              </div>


              <div className="metadata">

                <div>
                  <span>
                    Allowed runtimes
                  </span>

                  <strong>
                    {
                      profile
                        .allowed_runtimes
                        .join(", ")
                    }
                  </strong>
                </div>

                <div>
                  <span>
                    Overrides
                  </span>

                  <strong>
                    {
                      profile
                        .security
                        .allow_user_overrides
                        ? "Controlled"
                        : "Locked"
                    }
                  </strong>
                </div>

              </div>

            </article>

          )
        )}

      </div>

    </div>
  );
}
