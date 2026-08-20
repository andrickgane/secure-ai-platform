const API_BASE = "/api/v1";


export function getToken() {
  return localStorage.getItem(
    "acp_access_token"
  );
}


export function setToken(token) {
  localStorage.setItem(
    "acp_access_token",
    token
  );
}


export function clearToken() {
  localStorage.removeItem(
    "acp_access_token"
  );
}


export async function apiRequest(
  path,
  options = {}
) {
  const token = getToken();

  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  if (token) {
    headers.Authorization =
      `Bearer ${token}`;
  }

  const response = await fetch(
    `${API_BASE}${path}`,
    {
      ...options,
      headers,
    }
  );

  if (response.status === 401) {
    clearToken();

    throw new Error(
      "Authentication required"
    );
  }

  if (!response.ok) {
    let message =
      `HTTP ${response.status}`;

    try {
      const payload =
        await response.json();

      const detail = payload.detail;

      if (typeof detail === "string") {
        message = detail;
      } else if (Array.isArray(detail)) {
        message = detail
          .map((item) => {
            if (typeof item === "string") {
              return item;
            }

            if (item?.msg) {
              const location = Array.isArray(item.loc)
                ? item.loc.join(".")
                : "";

              return location
                ? `${location}: ${item.msg}`
                : item.msg;
            }

            return JSON.stringify(item);
          })
          .join("\n");
      } else if (
        detail &&
        typeof detail === "object"
      ) {
        message =
          detail.message ||
          detail.msg ||
          JSON.stringify(detail, null, 2);
      }
    } catch {
      // ignore JSON parsing failure
    }

    throw new Error(message);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}


export function login(
  email,
  password
) {
  return apiRequest(
    "/auth/login",
    {
      method: "POST",

      body: JSON.stringify({
        email,
        password,
      }),
    }
  );
}


export function getCurrentUser() {
  return apiRequest(
    "/auth/me"
  );
}


export function getDashboard() {
  return apiRequest(
    "/dashboard/summary"
  );
}


export function getModels() {
  return apiRequest(
    "/models"
  );
}


export function deleteModel(
  modelId
) {
  return apiRequest(
    `/models/${encodeURIComponent(modelId)}`,
    {
      method: "DELETE",
    }
  );
}


export function getProfiles() {
  return apiRequest(
    "/profiles"
  );
}


export function getRuntimes() {
  return apiRequest(
    "/runtimes"
  );
}


export function getDeployments() {
  return apiRequest(
    "/deployments"
  );
}


export function createDeployment(
  payload
) {
  return apiRequest(
    "/deployments",
    {
      method: "POST",

      body: JSON.stringify(
        payload
      ),
    }
  );
}


export function deleteDeployment(
  name
) {
  return apiRequest(
    `/deployments/${name}`,
    {
      method: "DELETE",
    }
  );
}


export function chatCompletion(
  deploymentName,
  payload
) {
  return apiRequest(
    `/deployments/${deploymentName}/chat/completions`,
    {
      method: "POST",

      body: JSON.stringify(
        payload
      ),
    }
  );
}


export function getUsers() {
  return apiRequest(
    "/users"
  );
}


export function getAudit() {
  return apiRequest(
    "/audit?limit=100"
  );
}


// ============================================================
// MODEL REQUESTS
// ============================================================

export function getModelRequests() {
  return apiRequest(
    "/model-requests"
  );
}


export function createModelRequest(
  payload
) {
  return apiRequest(
    "/model-requests",
    {
      method: "POST",

      body: JSON.stringify(
        payload
      ),
    }
  );
}


export function updateModelRequestStatus(
  requestId,
  payload
) {
  return apiRequest(
    `/model-requests/${requestId}/status`,
    {
      method: "PATCH",

      body: JSON.stringify(
        payload
      ),
    }
  );
}


export function ingestModelRequest(
  requestId,
  artifactPatterns = []
) {
  return apiRequest(
    `/model-requests/${requestId}/ingest`,
    {
      method: "POST",

      body: JSON.stringify({
        artifact_patterns: artifactPatterns,
      }),
    }
  );
}


/*
 * Promotion is exposed by the backend model-request
 * workflow after administrative approval.
 */
export function promoteModelRequest(
  requestId
) {
  return apiRequest(
    `/model-requests/${requestId}/promote`,
    {
      method: "POST",
    }
  );
}
