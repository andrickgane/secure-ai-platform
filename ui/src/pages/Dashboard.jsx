import {
  useEffect,
  useState,
} from "react";

import {
  FiActivity,
  FiBox,
  FiCpu,
  FiUsers,
} from "react-icons/fi";

import {
  getDashboard,
} from "../api";


export default function Dashboard() {
  const [data, setData] =
    useState(null);

  const [error, setError] =
    useState("");


  useEffect(() => {
    getDashboard()
      .then(setData)
      .catch((err) =>
        setError(err.message)
      );
  }, []);


  if (error) {
    return (
      <div className="error-box">
        {error}
      </div>
    );
  }


  if (!data) {
    return (
      <div>
        Loading dashboard...
      </div>
    );
  }


  const stats = [
    {
      label: "Active deployments",
      value:
        data.active_deployments,
      icon: FiBox,
    },
    {
      label: "Active users",
      value:
        data.active_users,
      icon: FiUsers,
    },
    {
      label: "Inference requests",
      value:
        data.total_requests,
      icon: FiActivity,
    },
    {
      label: "Tokens processed",
      value:
        data.total_tokens,
      icon: FiCpu,
    },
  ];


  return (
    <div>

      <section className="hero-panel">

        <div>

          <span className="eyebrow">
            PLATFORM OVERVIEW
          </span>

          <h2>
            AI infrastructure,
            governed.
          </h2>

          <p>
            Monitor trusted model
            deployments, inference
            consumption and runtime
            activity from one place.
          </p>

        </div>


        <div className="hero-status">
          Operational
        </div>

      </section>


      <section className="stats-grid">

        {stats.map((stat) => {

          const Icon =
            stat.icon;

          return (
            <div
              className="stat-card"
              key={stat.label}
            >

              <div className="stat-icon">
                <Icon />
              </div>

              <span>
                {stat.label}
              </span>

              <strong>
                {stat.value}
              </strong>

            </div>
          );
        })}

      </section>


      <section className="two-column">

        <div className="panel">

          <div className="panel-header">

            <div>
              <span className="eyebrow">
                MODELS
              </span>

              <h3>
                Usage by model
              </h3>
            </div>

          </div>


          {data.usage_by_model.length === 0
            ? (
              <p className="muted">
                No inference activity.
              </p>
            )
            : data.usage_by_model.map(
              (item) => (
                <div
                  className="usage-row"
                  key={item.model}
                >
                  <div>
                    <strong>
                      {item.model}
                    </strong>

                    <span>
                      {item.requests}
                      {" "}
                      requests
                    </span>
                  </div>

                  <strong>
                    {item.total_tokens}
                    {" "}
                    tokens
                  </strong>
                </div>
              )
            )}

        </div>


        <div className="panel">

          <div className="panel-header">

            <div>
              <span className="eyebrow">
                ACTIVITY
              </span>

              <h3>
                Recent events
              </h3>
            </div>

          </div>


          {data.recent_activity.map(
            (item) => (
              <div
                className="activity-row"
                key={item.id}
              >

                <div className="activity-dot" />

                <div>

                  <strong>
                    {item.action}
                  </strong>

                  <span>
                    {
                      item.actor_email ||
                      "system"
                    }
                  </span>

                </div>

                <time>
                  {new Date(
                    item.created_at
                  ).toLocaleString()}
                </time>

              </div>
            )
          )}

        </div>

      </section>

    </div>
  );
}
