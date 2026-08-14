import {
  useEffect,
  useState,
} from "react";

import {
  getAudit,
} from "../api";


export default function Audit() {
  const [events, setEvents] =
    useState([]);


  useEffect(() => {
    getAudit().then(setEvents);
  }, []);


  return (
    <section className="panel">

      <div className="panel-header">

        <div>

          <span className="eyebrow">
            SECURITY
          </span>

          <h3>
            Audit events
          </h3>

        </div>

      </div>


      <div className="audit-list">

        {events.map(
          (event) => (

            <div
              className="audit-row"
              key={event.id}
            >

              <div className="activity-dot" />

              <div>

                <strong>
                  {event.action}
                </strong>

                <span>
                  {
                    event.resource_type
                  }
                  {" · "}
                  {
                    event.resource_name ||
                    "-"
                  }
                </span>

              </div>


              <code>
                user:
                {
                  event.actor_user_id
                  ?? "system"
                }
              </code>


              <time>
                {new Date(
                  event.created_at
                ).toLocaleString()}
              </time>

            </div>

          )
        )}

      </div>

    </section>
  );
}
