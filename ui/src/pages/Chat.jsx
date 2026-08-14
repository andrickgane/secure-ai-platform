import {
  useEffect,
  useState,
} from "react";

import {
  chatCompletion,
  getDeployments,
} from "../api";


export default function Chat() {
  const [deployments, setDeployments] =
    useState([]);

  const [deployment, setDeployment] =
    useState("");

  const [prompt, setPrompt] =
    useState("");

  const [messages, setMessages] =
    useState([]);

  const [loading, setLoading] =
    useState(false);


  useEffect(() => {
    getDeployments().then(
      (result) => {

        const ready =
          result.filter(
            (item) =>
              item.status ===
              "ready"
          );

        setDeployments(ready);

        if (ready.length) {
          setDeployment(
            ready[0].name
          );
        }
      }
    );
  }, []);


  async function send(event) {
    event.preventDefault();

    if (!prompt.trim()) {
      return;
    }

    const userMessage = {
      role: "user",
      content: prompt,
    };

    setMessages(
      (current) => [
        ...current,
        userMessage,
      ]
    );

    setPrompt("");
    setLoading(true);

    try {
      const result =
        await chatCompletion(
          deployment,
          {
            messages: [
              ...messages,
              userMessage,
            ],
          }
        );

      setMessages(
        (current) => [
          ...current,

          {
            role: "assistant",
            content:
              result.content,

            usage: {
              tokens:
                result.total_tokens,

              model:
                result.model,

              profile:
                result.profile,
            },
          },
        ]
      );

    } finally {
      setLoading(false);
    }
  }


  return (
    <div className="chat-layout">

      <section className="chat-panel">

        <div className="panel-header">

          <div>
            <span className="eyebrow">
              INFERENCE
            </span>

            <h3>
              AI Playground
            </h3>
          </div>


          <select
            value={deployment}

            onChange={(event) =>
              setDeployment(
                event.target.value
              )
            }
          >
            {deployments.map(
              (item) => (
                <option
                  key={item.name}
                  value={item.name}
                >
                  {item.name}
                </option>
              )
            )}
          </select>

        </div>


        <div className="messages">

          {messages.length === 0 && (
            <div className="empty-chat">

              <h3>
                Start a conversation
              </h3>

              <p>
                The selected deployment's
                profile controls inference
                parameters automatically.
              </p>

            </div>
          )}


          {messages.map(
            (message, index) => (

              <div
                key={index}

                className={
                  `message ${
                    message.role
                  }`
                }
              >

                <strong>
                  {message.role ===
                  "user"
                    ? "You"
                    : "Assistant"}
                </strong>

                <p>
                  {message.content}
                </p>

                {message.usage && (
                  <span>
                    {
                      message
                        .usage
                        .tokens
                    }
                    {" "}
                    tokens ·
                    {" "}
                    {
                      message
                        .usage
                        .profile
                    }
                  </span>
                )}

              </div>

            )
          )}

        </div>


        <form
          className="chat-input"
          onSubmit={send}
        >

          <textarea
            value={prompt}

            onChange={(event) =>
              setPrompt(
                event.target.value
              )
            }

            placeholder="Ask your deployed model..."
          />

          <button
            className="primary-button"
            disabled={
              loading ||
              !deployment
            }
          >
            {loading
              ? "Generating..."
              : "Send"}
          </button>

        </form>

      </section>

    </div>
  );
}
