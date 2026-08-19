import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  FiCheck,
  FiClipboard,
  FiCpu,
  FiDownload,
  FiFile,
  FiMessageSquare,
  FiPlus,
  FiRefreshCw,
  FiSend,
  FiSquare,
  FiTrash2,
  FiX,
} from "react-icons/fi";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import {
  Prism as SyntaxHighlighter,
} from "react-syntax-highlighter";

import {
  oneDark,
} from "react-syntax-highlighter/dist/esm/styles/prism";

import {
  getDeployments,
} from "../api";

import {
  chatCompletionStream,
} from "../streamApi";

import {
  addConversationMessage,
  createConversation,
  deleteConversation,
  deleteConversationAttachment,
  downloadConversationAttachment,
  getConversation,
  getConversations,
  updateConversation,
  uploadConversationAttachment,
} from "../conversationApi";

import ConversationSidebar
  from "./ConversationSidebar";

import InferencePerformance
  from "./InferencePerformance";

import InferenceSettings
  from "./InferenceSettings";

import "./ChatStream.css";
import "./ConversationWorkspace.css";


const ACTIVE_CONVERSATION_KEY =
  "aiw_active_conversation";


function CodeBlock({
  className,
  children,
}) {
  const [
    copied,
    setCopied,
  ] = useState(false);

  const match =
    /language-(\w+)/.exec(
      className || ""
    );

  const language =
    match?.[1] || "text";

  const code =
    String(children)
      .replace(
        /\n$/,
        ""
      );


  async function copyCode() {
    try {
      await navigator
        .clipboard
        .writeText(
          code
        );

      setCopied(true);

      window.setTimeout(
        () =>
          setCopied(false),
        1500
      );

    } catch {
      setCopied(false);
    }
  }


  return (
    <div className="aiw-code-block">

      <div className="aiw-code-header">

        <span>
          {language}
        </span>

        <button
          type="button"
          onClick={copyCode}
          className="aiw-copy-button"
        >
          {
            copied
              ? <FiCheck />
              : <FiClipboard />
          }

          {
            copied
              ? "Copied"
              : "Copy"
          }
        </button>

      </div>


      <SyntaxHighlighter
        language={language}
        style={oneDark}
        customStyle={{
          margin: 0,
          borderRadius:
            "0 0 10px 10px",
          fontSize: "13px",
          lineHeight: "1.6",
        }}
        PreTag="div"
      >
        {code}
      </SyntaxHighlighter>

    </div>
  );
}


function MarkdownMessage({
  content,
}) {
  return (
    <ReactMarkdown
      remarkPlugins={[
        remarkGfm,
      ]}
      components={{
        code({
          inline,
          className,
          children,
          ...props
        }) {
          if (inline) {
            return (
              <code
                className="aiw-inline-code"
                {...props}
              >
                {children}
              </code>
            );
          }

          return (
            <CodeBlock
              className={
                className
              }
            >
              {children}
            </CodeBlock>
          );
        },

        table({
          children,
        }) {
          return (
            <div className="aiw-table-wrapper">
              <table>
                {children}
              </table>
            </div>
          );
        },
      }}
    >
      {content || ""}
    </ReactMarkdown>
  );
}


function Message({
  message,
}) {
  const assistant =
    message.role ===
    "assistant";

  const usage =
    message.usage || {};


  return (
    <article
      className={
        `aiw-message ${
          assistant
            ? "aiw-message-assistant"
            : "aiw-message-user"
        }`
      }
    >

      <div className="aiw-message-avatar">
        {
          assistant
            ? "AI"
            : "You"
        }
      </div>


      <div className="aiw-message-body">

        <div className="aiw-message-header">

          <strong>
            {
              assistant
                ? "Assistant"
                : "You"
            }
          </strong>


          {
            assistant &&
            (
              message.streaming ||
              Object.keys(
                usage
              ).length > 0
            ) && (
              <div className="aiw-message-meta">

                {
                  usage.model && (
                    <span>
                      {usage.model}
                    </span>
                  )
                }

                {
                  usage.runtime && (
                    <span>
                      {usage.runtime}
                    </span>
                  )
                }

                {
                  usage.profile && (
                    <span>
                      Profile:
                      {" "}
                      {usage.profile}
                    </span>
                  )
                }

                {
                  usage.tokens != null && (
                    <span>
                      {usage.tokens}
                      {" "}
                      tokens
                    </span>
                  )
                }

                {
                  usage.ttftMs != null && (
                    <span>
                      TTFT
                      {" "}
                      {
                        (
                          usage.ttftMs /
                          1000
                        ).toFixed(2)
                      }
                      s
                    </span>
                  )
                }

                {
                  usage.latencyMs != null && (
                    <span>
                      Latency
                      {" "}
                      {
                        (
                          usage.latencyMs /
                          1000
                        ).toFixed(2)
                      }
                      s
                    </span>
                  )
                }

                {
                  message.streaming && (
                    <span className="aiw-streaming-badge">
                      Streaming
                    </span>
                  )
                }

                {
                  message.stopped && (
                    <span className="aiw-stopped-badge">
                      Stopped
                    </span>
                  )
                }

              </div>
            )
          }

        </div>


        {
          Array.isArray(
            message.attachments
          ) &&
          message.attachments.length >
            0 && (
            <div className="aiw-message-attachments">

              {
                message.attachments.map(
                  (attachment) => (
                    <button
                      type="button"
                      key={
                        attachment.id
                      }
                      className="aiw-message-attachment"
                      onClick={
                        () =>
                          message.onDownloadAttachment?.(
                            attachment
                          )
                      }
                    >
                      <FiFile />

                      <div>
                        <strong>
                          {
                            attachment.filename
                          }
                        </strong>

                        <span>
                          {
                            formatBytes(
                              attachment.size_bytes
                            )
                          }
                        </span>
                      </div>

                      <FiDownload />
                    </button>
                  )
                )
              }

            </div>
          )
        }


        <div className="aiw-markdown">

          {
            assistant &&
            message.streaming &&
            !message.content
              ? (
                <div className="aiw-thinking">
                  <span />
                  <span />
                  <span />
                </div>
              )
              : (
                <>
                  <MarkdownMessage
                    content={
                      message.content
                    }
                  />

                  {
                    message.streaming && (
                      <span className="aiw-stream-cursor" />
                    )
                  }
                </>
              )
          }

        </div>


        {
          assistant &&
          usage.parameters && (
            <div className="aiw-effective-parameters">

              <span>
                temp
                {" "}
                <strong>
                  {
                    usage.parameters
                      .temperature
                  }
                </strong>
              </span>

              <span>
                max tokens
                {" "}
                <strong>
                  {
                    usage.parameters
                      .max_tokens
                  }
                </strong>
              </span>

              <span>
                top-p
                {" "}
                <strong>
                  {
                    usage.parameters
                      .top_p
                  }
                </strong>
              </span>

              <span>
                context
                {" "}
                <strong>
                  {
                    usage.parameters
                      .max_model_len
                  }
                </strong>
              </span>

            </div>
          )
        }


        {
          assistant &&
          !message.streaming && (
            <InferencePerformance
              usage={
                usage
              }
            />
          )
        }

      </div>

    </article>
  );
}


function formatBytes(
  bytes
) {
  if (
    bytes == null
  ) {
    return "";
  }

  if (
    bytes < 1024
  ) {
    return `${bytes} B`;
  }

  if (
    bytes <
    1024 * 1024
  ) {
    return (
      `${(
        bytes / 1024
      ).toFixed(1)} KB`
    );
  }

  return (
    `${(
      bytes /
      1024 /
      1024
    ).toFixed(1)} MB`
  );
}


function storedMessageToUi(
  message,
  allAttachments = []
) {
  return {
    id:
      `db-${message.id}`,

    role:
      message.role,

    content:
      message.content,

    streaming:
      false,

    stopped:
      message.status ===
      "stopped",

    attachments:
      allAttachments.filter(
        (attachment) =>
          attachment.message_id ===
          message.id
      ),

    usage: {
      model:
        message.model,

      profile:
        message.profile,

      runtime:
        message.runtime,

      parameters:
        message.parameters,

      tokens:
        message.total_tokens,

      promptTokens:
        message.prompt_tokens,

      completionTokens:
        message.completion_tokens,

      latencyMs:
        message.latency_ms,

      ttftMs:
        message.first_token_latency_ms,

      generationDurationMs:
        message.generation_duration_ms,

      generationTokensPerSecond:
        message.generation_tokens_per_second,

      outputTokensPerSecond:
        message.output_tokens_per_second,
    },
  };
}


export default function Chat() {
  const [
    deployments,
    setDeployments,
  ] = useState([]);

  const [
    deployment,
    setDeployment,
  ] = useState("");

  const [
    prompt,
    setPrompt,
  ] = useState("");

  const [
    messages,
    setMessages,
  ] = useState([]);

  const [
    loading,
    setLoading,
  ] = useState(false);

  const [
    loadingDeployments,
    setLoadingDeployments,
  ] = useState(true);

  const [
    error,
    setError,
  ] = useState("");


  const [
    inferenceOverrides,
    setInferenceOverrides,
  ] = useState({
    temperature: "",
    maxTokens: "",
    topP: "",
  });


  const [
    conversations,
    setConversations,
  ] = useState([]);

  const [
    activeConversationId,
    setActiveConversationId,
  ] = useState(null);

  const [
    pendingAttachments,
    setPendingAttachments,
  ] = useState([]);

  const [
    loadingConversations,
    setLoadingConversations,
  ] = useState(true);

  const [
    uploading,
    setUploading,
  ] = useState(false);


  const bottomRef =
    useRef(null);

  const abortRef =
    useRef(null);

  const fileInputRef =
    useRef(null);


  const selectedDeployment =
    useMemo(
      () =>
        deployments.find(
          (item) =>
            item.name ===
            deployment
        ),
      [
        deployments,
        deployment,
      ]
    );


  useEffect(() => {
    async function bootstrap() {
      await loadDeployments();

      await restoreConversations();
    }

    bootstrap();

    return () => {
      abortRef.current
        ?.abort();
    };
  }, []);


  useEffect(() => {
    bottomRef.current
      ?.scrollIntoView({
        behavior: "smooth",
      });
  }, [
    messages,
    loading,
  ]);


  async function loadDeployments() {
    setLoadingDeployments(
      true
    );

    try {
      const result =
        await getDeployments();

      const ready =
        result.filter(
          (item) =>
            item.status ===
              "ready" ||
            item.status ===
              "deployed"
        );

      setDeployments(
        ready
      );

      setDeployment(
        (current) => {
          if (
            current &&
            ready.some(
              (item) =>
                item.name ===
                current
            )
          ) {
            return current;
          }

          return (
            ready[0]?.name ||
            ""
          );
        }
      );

      return ready;

    } catch (err) {
      setError(
        err.message ||
        "Unable to load deployments"
      );

      return [];

    } finally {
      setLoadingDeployments(
        false
      );
    }
  }


  async function refreshConversationList() {
    const result =
      await getConversations();

    setConversations(
      result
    );

    return result;
  }


  async function restoreConversations() {
    setLoadingConversations(
      true
    );

    try {
      const list =
        await refreshConversationList();

      const stored =
        window.localStorage
          .getItem(
            ACTIVE_CONVERSATION_KEY
          );

      const storedId =
        stored
          ? Number(stored)
          : null;

      if (
        storedId &&
        list.some(
          (item) =>
            item.id ===
            storedId
        )
      ) {
        await openConversation(
          storedId
        );
      }

    } catch (err) {
      setError(
        err.message ||
        "Unable to load conversations"
      );

    } finally {
      setLoadingConversations(
        false
      );
    }
  }


  async function openConversation(
    conversationId
  ) {
    if (loading) {
      return;
    }

    setError("");

    try {
      const detail =
        await getConversation(
          conversationId
        );

      setActiveConversationId(
        detail.id
      );

      window.localStorage
        .setItem(
          ACTIVE_CONVERSATION_KEY,
          String(detail.id)
        );

      const allAttachments =
        detail.attachments || [];

      setMessages(
        detail.messages.map(
          (message) =>
            storedMessageToUi(
              message,
              allAttachments
            )
        )
      );

      setPendingAttachments(
        allAttachments.filter(
          (attachment) =>
            attachment.message_id == null
        )
      );

      if (
        detail.deployment_name
      ) {
        setDeployment(
          detail.deployment_name
        );
      }

      setInferenceOverrides({
        temperature: "",
        maxTokens: "",
        topP: "",
      });

    } catch (err) {
      setError(
        err.message ||
        "Unable to open conversation"
      );
    }
  }


  function newConversation() {
    if (loading) {
      return;
    }

    setActiveConversationId(
      null
    );

    window.localStorage
      .removeItem(
        ACTIVE_CONVERSATION_KEY
      );

    setMessages([]);

    setPendingAttachments([]);

    setPrompt("");

    setError("");

    setInferenceOverrides({
      temperature: "",
      maxTokens: "",
      topP: "",
    });
  }


  async function ensureConversation() {
    if (
      activeConversationId
    ) {
      return (
        activeConversationId
      );
    }

    const created =
      await createConversation({
        deployment_name:
          deployment || null,
      });

    setActiveConversationId(
      created.id
    );

    window.localStorage
      .setItem(
        ACTIVE_CONVERSATION_KEY,
        String(created.id)
      );

    setConversations(
      (current) => [
        created,
        ...current.filter(
          (item) =>
            item.id !==
            created.id
        ),
      ]
    );

    return created.id;
  }


  async function renameConversation(
    conversation
  ) {
    const title =
      window.prompt(
        "Conversation title",
        conversation.title
      );

    if (
      !title ||
      !title.trim()
    ) {
      return;
    }

    try {
      await updateConversation(
        conversation.id,
        {
          title:
            title.trim(),
        }
      );

      await refreshConversationList();

    } catch (err) {
      setError(
        err.message ||
        "Unable to rename conversation"
      );
    }
  }


  async function removeConversation(
    conversation
  ) {
    const confirmed =
      window.confirm(
        `Delete '${conversation.title}'?`
      );

    if (!confirmed) {
      return;
    }

    try {
      await deleteConversation(
        conversation.id
      );

      if (
        activeConversationId ===
        conversation.id
      ) {
        newConversation();
      }

      await refreshConversationList();

    } catch (err) {
      setError(
        err.message ||
        "Unable to delete conversation"
      );
    }
  }


  function updateAssistant(
    id,
    updater
  ) {
    setMessages(
      (current) =>
        current.map(
          (message) =>
            message.id === id
              ? updater(
                  message
                )
              : message
        )
    );
  }


  async function send(
    event
  ) {
    event?.preventDefault();

    const content =
      prompt.trim();

    if (
      !content ||
      loading ||
      !selectedDeployment
    ) {
      return;
    }


    setLoading(true);
    setError("");


    let conversationId;

    try {
      conversationId =
        await ensureConversation();

    } catch (err) {
      setLoading(false);

      setError(
        err.message ||
        "Unable to create conversation"
      );

      return;
    }


    const messageAttachments = [
      ...pendingAttachments,
    ];

    const userMessage = {
      id:
        crypto.randomUUID(),

      role:
        "user",

      content,

      attachments:
        messageAttachments,
    };


    const conversationMessages = [
      ...messages,
      userMessage,
    ].filter(
      (message) =>
        (
          message.role ===
            "user" ||
          message.role ===
            "assistant"
        ) &&
        typeof message.content ===
          "string" &&
        message.content
          .trim()
          .length > 0
    );


    setMessages(
      conversationMessages
    );

    setPrompt("");


    try {
      await addConversationMessage(
        conversationId,
        {
          role:
            "user",

          content,

          attachment_ids:
            messageAttachments.map(
              (attachment) =>
                attachment.id
            ),
        }
      );

      setPendingAttachments([]);

      await refreshConversationList();

    } catch (err) {
      setLoading(false);

      setError(
        err.message ||
        "Unable to persist user message"
      );

      return;
    }


    const assistantId =
      crypto.randomUUID();

    setMessages(
      (current) => [
        ...current,
        {
          id:
            assistantId,

          role:
            "assistant",

          content:
            "",

          streaming:
            true,

          stopped:
            false,

          usage:
            {},
        },
      ]
    );


    const controller =
      new AbortController();

    abortRef.current =
      controller;


    let assistantContent =
      "";

    let metadata = {};

    let doneData = {};

    let persistenceStatus =
      "completed";


    try {
      await chatCompletionStream(
        deployment,

        {
          messages:
            conversationMessages.map(
              ({
                role,
                content:
                  messageContent,
              }) => ({
                role,

                content:
                  messageContent
                    .trim(),
              })
            ),

          conversation_id:
            conversationId,

          attachment_ids:
            messageAttachments.map(
              (attachment) =>
                attachment.id
            ),

          ...(
            inferenceOverrides
              .temperature !== ""
              ? {
                  temperature:
                    Number(
                      inferenceOverrides
                        .temperature
                    ),
                }
              : {}
          ),

          ...(
            inferenceOverrides
              .maxTokens !== ""
              ? {
                  max_tokens:
                    Number(
                      inferenceOverrides
                        .maxTokens
                    ),
                }
              : {}
          ),

          ...(
            inferenceOverrides
              .topP !== ""
              ? {
                  top_p:
                    Number(
                      inferenceOverrides
                        .topP
                    ),
                }
              : {}
          ),
        },

        {
          signal:
            controller.signal,


          onMeta(
            data
          ) {
            metadata =
              data || {};

            updateAssistant(
              assistantId,

              (message) => ({
                ...message,

                usage: {
                  ...message.usage,

                  model:
                    data.model,

                  runtime:
                    data.runtime,

                  profile:
                    data.profile,

                  parameters:
                    data.parameters,
                },
              })
            );
          },


          onDelta(
            delta
          ) {
            const chunk =
              typeof delta.content ===
                "string"
                ? delta.content
                : "";

            if (!chunk) {
              return;
            }

            assistantContent +=
              chunk;

            updateAssistant(
              assistantId,

              (message) => ({
                ...message,

                content:
                  (
                    message.content ||
                    ""
                  ) +
                  chunk,
              })
            );
          },


          onDone(
            data
          ) {
            doneData =
              data || {};

            updateAssistant(
              assistantId,

              (message) => ({
                ...message,

                streaming:
                  false,

                usage: {
                  ...message.usage,

                  tokens:
                    data.total_tokens,

                  promptTokens:
                    data.prompt_tokens,

                  completionTokens:
                    data.completion_tokens,

                  latencyMs:
                    data.latency_ms,

                  ttftMs:
                    data.first_token_latency_ms,

                  generationDurationMs:
                    data.generation_duration_ms,

                  generationTokensPerSecond:
                    data.generation_tokens_per_second,

                  outputTokensPerSecond:
                    data.output_tokens_per_second,

                  finishReason:
                    data.finish_reason,
                },
              })
            );
          },


          onError(
            streamError
          ) {
            throw new Error(
              streamError?.message ||
              "Streaming inference failed"
            );
          },
        }
      );


      updateAssistant(
        assistantId,

        (message) => ({
          ...message,

          streaming:
            false,
        })
      );


    } catch (err) {
      if (
        err?.name ===
        "AbortError"
      ) {
        persistenceStatus =
          "stopped";

        updateAssistant(
          assistantId,

          (message) => ({
            ...message,

            streaming:
              false,

            stopped:
              true,
          })
        );

      } else {
        persistenceStatus =
          "error";

        updateAssistant(
          assistantId,

          (message) => ({
            ...message,

            streaming:
              false,
          })
        );

        setError(
          err.message ||
          "Inference request failed"
        );
      }

    } finally {
      if (
        assistantContent.trim()
      ) {
        try {
          await addConversationMessage(
            conversationId,
            {
              role:
                "assistant",

              content:
                assistantContent,

              model:
                metadata.model ||
                selectedDeployment.model,

              profile:
                metadata.profile ||
                selectedDeployment.profile,

              runtime:
                metadata.runtime ||
                selectedDeployment.runtime,

              parameters:
                metadata.parameters ||
                null,

              prompt_tokens:
                doneData.prompt_tokens ??
                null,

              completion_tokens:
                doneData.completion_tokens ??
                null,

              total_tokens:
                doneData.total_tokens ??
                null,

              latency_ms:
                doneData.latency_ms ??
                null,

              first_token_latency_ms:
                doneData
                  .first_token_latency_ms ??
                null,

              generation_duration_ms:
                doneData
                  .generation_duration_ms ??
                null,

              generation_tokens_per_second:
                doneData
                  .generation_tokens_per_second ??
                null,

              output_tokens_per_second:
                doneData
                  .output_tokens_per_second ??
                null,

              status:
                persistenceStatus,
            }
          );

          await refreshConversationList();

        } catch (persistError) {
          setError(
            persistError.message ||
            "Response generated but could not be persisted"
          );
        }
      }


      if (
        abortRef.current ===
        controller
      ) {
        abortRef.current =
          null;
      }

      setLoading(false);
    }
  }


  function stopGeneration() {
    abortRef.current
      ?.abort();
  }


  function handleKeyDown(
    event
  ) {
    if (
      event.key ===
        "Enter" &&
      !event.shiftKey
    ) {
      event.preventDefault();

      send(event);
    }
  }


  function clearConversationView() {
    if (loading) {
      return;
    }

    newConversation();
  }


  function changeDeployment(
    value
  ) {
    if (loading) {
      return;
    }

    setDeployment(
      value
    );

    newConversation();
  }


  async function uploadFiles(
    files
  ) {
    if (
      !files.length ||
      uploading
    ) {
      return;
    }

    setUploading(true);
    setError("");

    try {
      const conversationId =
        await ensureConversation();

      for (
        const file of files
      ) {
        const attachment =
          await uploadConversationAttachment(
            conversationId,
            file
          );

        setPendingAttachments(
          (current) => [
            ...current,
            attachment,
          ]
        );
      }

      await refreshConversationList();

    } catch (err) {
      setError(
        err.message ||
        "Unable to upload attachment"
      );

    } finally {
      setUploading(false);
    }
  }


  async function removeAttachment(
    attachment
  ) {
    if (
      !activeConversationId
    ) {
      return;
    }

    try {
      await deleteConversationAttachment(
        activeConversationId,
        attachment.id
      );

      setPendingAttachments(
        (current) =>
          current.filter(
            (item) =>
              item.id !==
              attachment.id
          )
      );

    } catch (err) {
      setError(
        err.message ||
        "Unable to delete attachment"
      );
    }
  }


  async function downloadAttachment(
    attachment
  ) {
    if (
      !activeConversationId
    ) {
      return;
    }

    try {
      await downloadConversationAttachment(
        activeConversationId,
        attachment
      );

    } catch (err) {
      setError(
        err.message ||
        "Unable to download attachment"
      );
    }
  }


  return (
    <div className="aiw-layout aiw-layout-conversations">

      <ConversationSidebar
        conversations={
          conversations
        }

        activeId={
          activeConversationId
        }

        loading={
          loadingConversations
        }

        onNew={
          newConversation
        }

        onOpen={
          openConversation
        }

        onRename={
          renameConversation
        }

        onDelete={
          removeConversation
        }
      />


      <section className="aiw-workspace">

        <header className="aiw-header">

          <div>

            <span className="eyebrow">
              AI WORKSPACE
            </span>

            <h3>
              Secure Inference
            </h3>

            <p>
              Persistent governed conversations,
              streaming inference and secure
              attachments.
            </p>

          </div>


          <div className="aiw-header-actions">

            {
              loading && (
                <button
                  type="button"
                  className="aiw-stop-button"
                  onClick={
                    stopGeneration
                  }
                >
                  <FiSquare />
                  Stop
                </button>
              )
            }


            <button
              type="button"
              className="aiw-secondary-button"
              onClick={
                loadDeployments
              }
              disabled={
                loadingDeployments ||
                loading
              }
            >
              <FiRefreshCw />
              Refresh
            </button>


            <button
              type="button"
              className="aiw-secondary-button"
              onClick={
                clearConversationView
              }
              disabled={
                loading ||
                (
                  messages.length === 0 &&
                  pendingAttachments.length === 0
                )
              }
            >
              <FiTrash2 />
              New chat
            </button>

          </div>

        </header>


        <div className="aiw-runtime-bar">

          <div className="aiw-runtime-field">

            <label>
              Active deployment
            </label>

            <select
              value={
                deployment
              }

              onChange={
                (event) =>
                  changeDeployment(
                    event.target.value
                  )
              }

              disabled={
                loadingDeployments ||
                loading
              }
            >

              {
                deployments.length ===
                  0 && (
                  <option value="">
                    No ready deployment
                  </option>
                )
              }


              {
                deployments.map(
                  (item) => (
                    <option
                      key={
                        item.name
                      }

                      value={
                        item.name
                      }
                    >
                      {item.name}
                    </option>
                  )
                )
              }

            </select>

          </div>


          <div className="aiw-runtime-status">

            <span
              className={
                `aiw-status-dot ${
                  selectedDeployment
                    ? "ready"
                    : ""
                }`
              }
            />


            <div>

              <strong>
                {
                  selectedDeployment
                    ? (
                      loading
                        ? "Generating"
                        : "Runtime ready"
                    )
                    : "Runtime unavailable"
                }
              </strong>

              <span>
                {
                  selectedDeployment
                    ?.runtime ||
                  "Select a ready deployment"
                }
              </span>

            </div>

          </div>

        </div>


        <InferenceSettings
          selectedDeployment={
            selectedDeployment
          }

          value={
            inferenceOverrides
          }

          onChange={
            setInferenceOverrides
          }

          disabled={
            loading
          }
        />


        <div className="aiw-messages">

          {
            messages.length ===
              0 &&
            !loading && (
              <div className="aiw-empty-state">

                <div className="aiw-empty-icon">
                  <FiMessageSquare />
                </div>

                <h2>
                  AI Workspace
                </h2>

                <p>
                  Start a persistent conversation
                  or attach documents with the
                  + button.
                </p>


                <div className="aiw-empty-grid">

                  <button
                    type="button"
                    onClick={
                      () =>
                        setPrompt(
                          "Explain the architecture of a secure enterprise RAG platform."
                        )
                    }
                  >
                    <strong>
                      Architecture
                    </strong>

                    <span>
                      Design a secure RAG platform
                    </span>
                  </button>


                  <button
                    type="button"
                    onClick={
                      () =>
                        setPrompt(
                          "Write a Kubernetes NetworkPolicy example and explain the security controls."
                        )
                    }
                  >
                    <strong>
                      Kubernetes
                    </strong>

                    <span>
                      Generate infrastructure code
                    </span>
                  </button>


                  <button
                    type="button"
                    onClick={
                      () =>
                        setPrompt(
                          "Explain how vLLM continuous batching and KV cache improve inference performance."
                        )
                    }
                  >
                    <strong>
                      vLLM
                    </strong>

                    <span>
                      Analyze inference performance
                    </span>
                  </button>

                </div>

              </div>
            )
          }


          {
            messages.map(
              (
                message,
                index
              ) => (
                <Message
                  key={
                    message.id ||
                    `${message.role}-${index}`
                  }

                  message={{
                    ...message,

                    onDownloadAttachment:
                      downloadAttachment,
                  }}
                />
              )
            )
          }


          <div
            ref={
              bottomRef
            }
          />

        </div>


        {
          error && (
            <div className="aiw-error">
              {error}
            </div>
          )
        }


        <div className="aiw-upload-note">
          Attachments are stored securely with
          the conversation. They are not yet
          injected into model context; RAG support
          will enable that later.
        </div>


        <div className="aiw-composer-wrapper">

          {
            pendingAttachments.length > 0 && (
              <div className="aiw-composer-pending">

                {
                  pendingAttachments.map(
                    (attachment) => (
                      <div
                        className="aiw-attachment-chip"
                        key={
                          attachment.id
                        }
                      >
                        <FiFile />

                        <span>
                          {
                            attachment.filename
                          }
                        </span>

                        <small>
                          {
                            formatBytes(
                              attachment.size_bytes
                            )
                          }
                        </small>

                        <button
                          type="button"
                          className="aiw-attachment-action"
                          title="Remove attachment"
                          onClick={
                            () =>
                              removeAttachment(
                                attachment
                              )
                          }
                        >
                          <FiX />
                        </button>

                      </div>
                    )
                  )
                }

              </div>
            )
          }

          <form
            className="aiw-composer aiw-composer-with-attachments"
            onSubmit={
              send
            }
          >

            <input
              ref={
                fileInputRef
              }

              type="file"

              hidden

              multiple

              accept=".txt,.md,.markdown,.csv,.json,.yaml,.yml,.xml,.html,.css,.py,.sh,.bash,.js,.jsx,.ts,.tsx,.go,.java,.c,.cpp,.h,.sql,.tf,.tfvars,.hcl,.ini,.conf,.log,.pdf,.png,.jpg,.jpeg,.webp,.gif"

              onChange={
                async (
                  event
                ) => {
                  const files =
                    Array.from(
                      event.target
                        .files || []
                    );

                  event.target.value =
                    "";

                  await uploadFiles(
                    files
                  );
                }
              }
            />


            <button
              type="button"

              className="aiw-attach-button"

              title="Add attachment"

              disabled={
                uploading ||
                loading ||
                !selectedDeployment
              }

              onClick={
                () =>
                  fileInputRef
                    .current
                    ?.click()
              }
            >
              {
                uploading
                  ? "…"
                  : <FiPlus />
              }
            </button>


            <textarea
              value={
                prompt
              }

              onChange={
                (event) =>
                  setPrompt(
                    event.target.value
                  )
              }

              onKeyDown={
                handleKeyDown
              }

              placeholder={
                selectedDeployment
                  ? (
                    loading
                      ? "Generation in progress..."
                      : "Message the deployed model..."
                  )
                  : "Select a ready deployment first..."
              }

              disabled={
                loading ||
                !selectedDeployment
              }

              rows={1}
            />


            {
              loading ? (
                <button
                  type="button"

                  className="aiw-send-button aiw-send-stop"

                  onClick={
                    stopGeneration
                  }

                  aria-label="Stop generation"
                >
                  <FiSquare />
                </button>

              ) : (

                <button
                  className="aiw-send-button"

                  disabled={
                    !selectedDeployment ||
                    !prompt.trim()
                  }

                  aria-label="Send message"
                >
                  <FiSend />
                </button>

              )
            }

          </form>


          <div className="aiw-composer-footer">

            <div>
              <FiCpu />

              <span>
                {
                  deployment ||
                  "No deployment selected"
                }
              </span>
            </div>


            <span>
              {
                loading
                  ? "Streaming response · Stop to interrupt"
                  : "Enter to send · Shift + Enter for new line"
              }
            </span>

          </div>

        </div>

      </section>

    </div>
  );
}
