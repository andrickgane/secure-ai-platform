import {
  apiRequest,
  clearToken,
  getToken,
} from "./api";


const API_BASE = "/api/v1";


export function getConversations() {
  return apiRequest(
    "/conversations"
  );
}


export function getConversation(
  conversationId
) {
  return apiRequest(
    `/conversations/${conversationId}`
  );
}


export function createConversation(
  payload
) {
  return apiRequest(
    "/conversations",
    {
      method: "POST",
      body: JSON.stringify(
        payload
      ),
    }
  );
}


export function updateConversation(
  conversationId,
  payload
) {
  return apiRequest(
    `/conversations/${conversationId}`,
    {
      method: "PATCH",
      body: JSON.stringify(
        payload
      ),
    }
  );
}


export function deleteConversation(
  conversationId
) {
  return apiRequest(
    `/conversations/${conversationId}`,
    {
      method: "DELETE",
    }
  );
}


export function addConversationMessage(
  conversationId,
  payload
) {
  return apiRequest(
    `/conversations/${conversationId}/messages`,
    {
      method: "POST",
      body: JSON.stringify(
        payload
      ),
    }
  );
}


async function multipartRequest(
  path,
  options
) {
  const token =
    getToken();

  const headers = {};

  if (token) {
    headers.Authorization =
      `Bearer ${token}`;
  }

  const response =
    await fetch(
      `${API_BASE}${path}`,
      {
        ...options,
        headers: {
          ...headers,
          ...(
            options?.headers ||
            {}
          ),
        },
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

      if (
        typeof payload.detail ===
        "string"
      ) {
        message =
          payload.detail;

      } else if (
        payload.detail?.message
      ) {
        message =
          payload.detail.message;

      } else if (
        payload.detail
      ) {
        message =
          JSON.stringify(
            payload.detail
          );
      }

    } catch {
      // Ignore malformed error body.
    }

    throw new Error(
      message
    );
  }


  if (
    response.status ===
    204
  ) {
    return null;
  }

  return response.json();
}


export function uploadConversationAttachment(
  conversationId,
  file
) {
  const formData =
    new FormData();

  formData.append(
    "file",
    file
  );

  return multipartRequest(
    `/conversations/${conversationId}/attachments`,
    {
      method: "POST",
      body: formData,
    }
  );
}


export function deleteConversationAttachment(
  conversationId,
  attachmentId
) {
  return multipartRequest(
    `/conversations/${conversationId}/attachments/${attachmentId}`,
    {
      method: "DELETE",
    }
  );
}


export async function downloadConversationAttachment(
  conversationId,
  attachment
) {
  const token =
    getToken();

  const response =
    await fetch(
      `${API_BASE}/conversations/${conversationId}/attachments/${attachment.id}/content`,
      {
        headers: {
          Authorization:
            `Bearer ${token}`,
        },
      }
    );


  if (!response.ok) {
    throw new Error(
      `Download failed: HTTP ${response.status}`
    );
  }


  const blob =
    await response.blob();

  const url =
    URL.createObjectURL(
      blob
    );

  const anchor =
    document.createElement(
      "a"
    );

  anchor.href = url;

  anchor.download =
    attachment.filename;

  document.body.appendChild(
    anchor
  );

  anchor.click();

  anchor.remove();

  URL.revokeObjectURL(
    url
  );
}
