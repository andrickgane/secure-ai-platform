import {
  getToken,
} from "./api";


function extractErrorMessage(
  payload,
  fallback
) {
  if (
    typeof payload?.detail ===
    "string"
  ) {
    return payload.detail;
  }

  if (
    payload?.detail &&
    typeof payload.detail ===
      "object"
  ) {
    if (
      typeof payload.detail.message ===
      "string"
    ) {
      return payload.detail.message;
    }

    try {
      return JSON.stringify(
        payload.detail
      );
    } catch {
      return fallback;
    }
  }

  return fallback;
}


function parseEventBlock(
  block
) {
  const lines =
    block.split(/\r?\n/);

  let eventName =
    "message";

  const dataLines = [];

  for (
    const line of lines
  ) {
    if (
      line.startsWith(
        "event:"
      )
    ) {
      eventName =
        line
          .slice(6)
          .trim();

      continue;
    }

    if (
      line.startsWith(
        "data:"
      )
    ) {
      dataLines.push(
        line
          .slice(5)
          .trimStart()
      );
    }
  }

  if (
    dataLines.length === 0
  ) {
    return null;
  }

  const raw =
    dataLines.join("\n");

  let data;

  try {
    data =
      JSON.parse(raw);

  } catch {
    data = {
      raw,
    };
  }

  return {
    event: eventName,
    data,
  };
}


export async function chatCompletionStream(
  deploymentName,
  payload,
  {
    signal,
    onMeta,
    onDelta,
    onDone,
    onError,
  } = {}
) {
  const token =
    getToken();

  if (!token) {
    throw new Error(
      "Authentication token is missing."
    );
  }

  const response =
    await fetch(
      `/api/v1/deployments/${
        encodeURIComponent(
          deploymentName
        )
      }/chat/completions/stream`,
      {
        method: "POST",

        signal,

        headers: {
          "Authorization":
            `Bearer ${token}`,

          "Content-Type":
            "application/json",

          "Accept":
            "text/event-stream",
        },

        body:
          JSON.stringify(
            payload
          ),
      }
    );


  if (!response.ok) {
    let payloadError = null;

    try {
      payloadError =
        await response.json();

    } catch {
      // Ignore invalid error JSON.
    }

    throw new Error(
      extractErrorMessage(
        payloadError,
        (
          `Streaming request failed `
          + `with HTTP ${response.status}`
        )
      )
    );
  }


  if (!response.body) {
    throw new Error(
      "Streaming response body is unavailable."
    );
  }


  const reader =
    response.body
      .getReader();

  const decoder =
    new TextDecoder(
      "utf-8"
    );

  let buffer = "";


  function dispatch(
    parsed
  ) {
    if (!parsed) {
      return;
    }

    const {
      event,
      data,
    } = parsed;

    if (
      event === "meta"
    ) {
      onMeta?.(
        data
      );

      return;
    }

    if (
      event === "delta"
    ) {
      onDelta?.(
        data
      );

      return;
    }

    if (
      event === "done"
    ) {
      onDone?.(
        data
      );

      return;
    }

    if (
      event === "error"
    ) {
      onError?.(
        data
      );
    }
  }


  try {
    while (true) {
      const {
        value,
        done,
      } =
        await reader.read();

      if (done) {
        break;
      }

      buffer +=
        decoder.decode(
          value,
          {
            stream: true,
          }
        );

      buffer =
        buffer.replace(
          /\r\n/g,
          "\n"
        );

      let separator =
        buffer.indexOf(
          "\n\n"
        );

      while (
        separator >= 0
      ) {
        const block =
          buffer
            .slice(
              0,
              separator
            )
            .trim();

        buffer =
          buffer.slice(
            separator + 2
          );

        if (block) {
          dispatch(
            parseEventBlock(
              block
            )
          );
        }

        separator =
          buffer.indexOf(
            "\n\n"
          );
      }
    }


    buffer +=
      decoder.decode();

    const remaining =
      buffer.trim();

    if (remaining) {
      dispatch(
        parseEventBlock(
          remaining
        )
      );
    }

  } finally {
    reader.releaseLock();
  }
}
