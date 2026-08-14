import {
  useEffect,
  useState,
} from "react";

import {
  FiActivity,
  FiBox,
  FiCpu,
  FiGrid,
  FiLogOut,
  FiMessageSquare,
  FiShield,
  FiSliders,
  FiUsers,
} from "react-icons/fi";

import {
  clearToken,
  getCurrentUser,
  getToken,
  login,
  setToken,
} from "./api";

import Dashboard from "./pages/Dashboard";
import Models from "./pages/Models";
import Profiles from "./pages/Profiles";
import Deployments from "./pages/Deployments";
import Chat from "./pages/Chat";
import Users from "./pages/Users";
import Audit from "./pages/Audit";


const navigation = [
  {
    id: "dashboard",
    label: "Overview",
    icon: FiGrid,
  },
  {
    id: "deployments",
    label: "Deployments",
    icon: FiBox,
  },
  {
    id: "models",
    label: "Models",
    icon: FiCpu,
  },
  {
    id: "profiles",
    label: "Profiles",
    icon: FiSliders,
  },
  {
    id: "chat",
    label: "Playground",
    icon: FiMessageSquare,
  },
  {
    id: "users",
    label: "Users",
    icon: FiUsers,
  },
  {
    id: "audit",
    label: "Audit",
    icon: FiActivity,
  },
];


function Login({
  onAuthenticated,
}) {
  const [email, setEmail] =
    useState(
      "admin@secure-ai.local"
    );

  const [password, setPassword] =
    useState("");

  const [error, setError] =
    useState("");

  const [loading, setLoading] =
    useState(false);


  async function submit(event) {
    event.preventDefault();

    setError("");
    setLoading(true);

    try {
      const result =
        await login(
          email,
          password
        );

      setToken(
        result.access_token
      );

      await onAuthenticated();

    } catch (err) {
      setError(err.message);

    } finally {
      setLoading(false);
    }
  }


  return (
    <div className="login-page">

      <div className="login-brand">

        <div className="brand-mark">
          AI
        </div>

        <div>
          <strong>
            AI Control Plane
          </strong>

          <span>
            Secure AI infrastructure
          </span>
        </div>

      </div>


      <div className="login-layout">

        <div className="login-copy">

          <span className="eyebrow">
            AI INFRASTRUCTURE
          </span>

          <h1>
            Deploy trusted AI workloads.
          </h1>

          <p>
            Govern models, profiles,
            runtimes and inference from
            one secure control plane.
          </p>

          <div className="login-features">

            <div>
              <FiShield />
              Trusted model supply chain
            </div>

            <div>
              <FiCpu />
              Runtime-aware orchestration
            </div>

            <div>
              <FiActivity />
              Auditable inference
            </div>

          </div>

        </div>


        <form
          className="login-card"
          onSubmit={submit}
        >

          <span className="eyebrow">
            PLATFORM ACCESS
          </span>

          <h2>
            Welcome back
          </h2>

          <p>
            Sign in to your AI
            Control Plane.
          </p>


          <label>
            Email

            <input
              type="email"
              value={email}

              onChange={(event) =>
                setEmail(
                  event.target.value
                )
              }

              required
            />
          </label>


          <label>
            Password

            <input
              type="password"
              value={password}

              onChange={(event) =>
                setPassword(
                  event.target.value
                )
              }

              required
            />
          </label>


          {error && (
            <div className="error-box">
              {error}
            </div>
          )}


          <button
            className="primary-button"
            disabled={loading}
          >
            {loading
              ? "Signing in..."
              : "Sign in"}
          </button>

        </form>

      </div>

    </div>
  );
}


export default function App() {
  const [user, setUser] =
    useState(null);

  const [loading, setLoading] =
    useState(true);

  const [page, setPage] =
    useState("dashboard");


  async function loadUser() {
    try {
      const result =
        await getCurrentUser();

      setUser(result);

    } catch {
      clearToken();
      setUser(null);
    }
  }


  useEffect(() => {
    async function init() {
      if (getToken()) {
        await loadUser();
      }

      setLoading(false);
    }

    init();
  }, []);


  if (loading) {
    return (
      <div className="center-page">
        Loading platform...
      </div>
    );
  }


  if (!user) {
    return (
      <Login
        onAuthenticated={
          loadUser
        }
      />
    );
  }


  function logout() {
    clearToken();
    setUser(null);
  }


  let content;

  switch (page) {
    case "models":
      content = <Models />;
      break;

    case "profiles":
      content = <Profiles />;
      break;

    case "deployments":
      content = <Deployments />;
      break;

    case "chat":
      content = <Chat />;
      break;

    case "users":
      content = <Users />;
      break;

    case "audit":
      content = <Audit />;
      break;

    default:
      content = <Dashboard />;
  }


  return (
    <div className="app-shell">

      <aside className="sidebar">

        <div className="sidebar-brand">

          <div className="brand-mark">
            AI
          </div>

          <div>
            <strong>
              Control Plane
            </strong>

            <span>
              AI Platform
            </span>
          </div>

        </div>


        <nav>

          <span className="nav-section">
            PLATFORM
          </span>

          {navigation.map(
            (item) => {

              const Icon =
                item.icon;

              return (
                <button
                  key={item.id}

                  className={
                    page === item.id
                      ? "nav-item active"
                      : "nav-item"
                  }

                  onClick={() =>
                    setPage(item.id)
                  }
                >
                  <Icon />

                  {item.label}
                </button>
              );
            }
          )}

        </nav>


        <div className="sidebar-bottom">

          <div className="user-chip">

            <div className="avatar">
              {user.email
                .charAt(0)
                .toUpperCase()}
            </div>

            <div>
              <strong>
                {user.email}
              </strong>

              <span>
                {user.role}
              </span>
            </div>

          </div>


          <button
            className="logout-button"
            onClick={logout}
          >
            <FiLogOut />

            Sign out
          </button>

        </div>

      </aside>


      <main className="main-content">

        <header className="topbar">

          <div>

            <span className="eyebrow">
              AI CONTROL PLANE
            </span>

            <h1>
              {
                navigation.find(
                  (item) =>
                    item.id === page
                )?.label ||
                "Overview"
              }
            </h1>

          </div>


          <div className="status-pill">
            <span />
            Platform healthy
          </div>

        </header>


        <div className="page-content">
          {content}
        </div>

      </main>

    </div>
  );
}
