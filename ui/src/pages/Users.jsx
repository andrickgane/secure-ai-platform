import {
  useEffect,
  useState,
} from "react";

import {
  getUsers,
} from "../api";


export default function Users() {
  const [users, setUsers] =
    useState([]);


  useEffect(() => {
    getUsers().then(setUsers);
  }, []);


  return (
    <section className="panel">

      <div className="panel-header">

        <div>
          <span className="eyebrow">
            ACCESS CONTROL
          </span>

          <h3>
            Platform users
          </h3>
        </div>

      </div>


      <div className="table">

        {users.map(
          (user) => (

            <div
              className="table-row"
              key={user.id}
            >

              <div>

                <strong>
                  {user.email}
                </strong>

                <span>
                  User #{user.id}
                </span>

              </div>


              <div>

                <span>
                  Role
                </span>

                <strong>
                  {user.role}
                </strong>

              </div>


              <div>

                <span>
                  Status
                </span>

                <strong>
                  {user.is_active
                    ? "Active"
                    : "Disabled"}
                </strong>

              </div>

            </div>

          )
        )}

      </div>

    </section>
  );
}
