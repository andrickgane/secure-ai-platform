import {
  FiEdit3,
  FiMessageSquare,
  FiPlus,
  FiTrash2,
} from "react-icons/fi";

import "./ConversationWorkspace.css";


function formatDate(
  value
) {
  if (!value) {
    return "";
  }

  const date =
    new Date(
      value
    );

  if (
    Number.isNaN(
      date.getTime()
    )
  ) {
    return "";
  }

  return date.toLocaleString(
    undefined,
    {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }
  );
}


export default function ConversationSidebar({
  conversations,
  activeId,
  loading,
  onNew,
  onOpen,
  onRename,
  onDelete,
}) {
  return (
    <aside className="aiw-conversation-sidebar">

      <div className="aiw-conversation-sidebar-header">

        <div>
          <span className="eyebrow">
            WORKSPACE
          </span>

          <strong>
            Conversations
          </strong>
        </div>


        <button
          type="button"
          className="aiw-new-chat-button"
          onClick={onNew}
        >
          <FiPlus />
          New chat
        </button>

      </div>


      <div className="aiw-conversation-list">

        {
          loading && (
            <div className="aiw-conversation-placeholder">
              Loading conversations...
            </div>
          )
        }


        {
          !loading &&
          conversations.length ===
            0 && (
            <div className="aiw-conversation-empty">

              <FiMessageSquare />

              <strong>
                No conversations
              </strong>

              <span>
                Start a new chat.
              </span>

            </div>
          )
        }


        {
          conversations.map(
            (conversation) => (
              <button
                type="button"

                key={
                  conversation.id
                }

                className={
                  `aiw-conversation-item ${
                    activeId ===
                    conversation.id
                      ? "active"
                      : ""
                  }`
                }

                onClick={
                  () =>
                    onOpen(
                      conversation.id
                    )
                }
              >

                <div className="aiw-conversation-main">

                  <FiMessageSquare />

                  <div>

                    <strong>
                      {
                        conversation.title
                      }
                    </strong>

                    <span>
                      {
                        conversation.model ||
                        "New conversation"
                      }
                    </span>

                    <small>
                      {
                        formatDate(
                          conversation.updated_at
                        )
                      }
                    </small>

                  </div>

                </div>


                <div className="aiw-conversation-actions">

                  <span
                    role="button"
                    tabIndex={0}
                    title="Rename"

                    onClick={
                      (event) => {
                        event.stopPropagation();

                        onRename(
                          conversation
                        );
                      }
                    }
                  >
                    <FiEdit3 />
                  </span>


                  <span
                    role="button"
                    tabIndex={0}
                    title="Delete"

                    onClick={
                      (event) => {
                        event.stopPropagation();

                        onDelete(
                          conversation
                        );
                      }
                    }
                  >
                    <FiTrash2 />
                  </span>

                </div>

              </button>
            )
          )
        }

      </div>

    </aside>
  );
}
