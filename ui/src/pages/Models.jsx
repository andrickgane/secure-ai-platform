import {
  useEffect,
  useState,
} from "react";

import {
  getModels,
} from "../api";


export default function Models() {
  const [models, setModels] =
    useState([]);


  useEffect(() => {
    getModels().then(setModels);
  }, []);


  return (
    <div>

      <div className="section-intro">

        <div>
          <span className="eyebrow">
            TRUSTED CATALOG
          </span>

          <h2>
            Approved models
          </h2>

          <p>
            Only models approved by
            the platform security
            policy are exposed here.
          </p>
        </div>

      </div>


      <div className="card-grid">

        {models.map((model) => (

          <article
            className="catalog-card"
            key={model.id}
          >

            <div className="card-topline">

              <span className="badge">
                MODEL
              </span>

              {model.approved && (
                <span className="approved">
                  Approved
                </span>
              )}

            </div>


            <h3>
              {model.display_name}
            </h3>

            <p>
              {model.description ||
                "Trusted AI model available for platform deployment."}
            </p>


            <div className="tag-row">

              {model.capabilities.map(
                (capability) => (
                  <span
                    className="tag"
                    key={capability}
                  >
                    {capability}
                  </span>
                )
              )}

            </div>


            <div className="metadata">

              <div>
                <span>
                  Default profile
                </span>

                <strong>
                  {model.default_profile}
                </strong>
              </div>

              <div>
                <span>
                  Runtimes
                </span>

                <strong>
                  {
                    model
                      .supported_runtimes
                      .join(", ")
                  }
                </strong>
              </div>

            </div>

          </article>

        ))}

      </div>

    </div>
  );
}
