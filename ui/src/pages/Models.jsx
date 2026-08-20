import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  FiCheckCircle,
  FiClock,
  FiCloud,
  FiCpu,
  FiDownloadCloud,
  FiExternalLink,
  FiPackage,
  FiPlus,
  FiRefreshCw,
  FiSearch,
  FiShield,
  FiUploadCloud,
  FiTrash2,
  FiX,
  FiXCircle,
} from "react-icons/fi";

import {
  createModelRequest,
  deleteModel,
  getModelRequests,
  getModels,
  getProfiles,
  ingestModelRequest,
  promoteModelRequest,
  updateModelRequestStatus,
} from "../api";


function normalizeStatus(
  status
) {
  return String(
    status || "unknown"
  ).toLowerCase();
}


function StatusBadge({
  status,
}) {
  const normalized =
    normalizeStatus(status);

  let icon =
    <FiClock />;

  if (
    [
      "published",
      "approved",
      "ready",
      "completed",
      "promoted",
    ].includes(normalized)
  ) {
    icon =
      <FiCheckCircle />;
  }

  if (
    [
      "failed",
      "rejected",
      "error",
    ].includes(normalized)
  ) {
    icon =
      <FiXCircle />;
  }

  if (
    [
      "ingesting",
      "scanning",
      "promoting",
    ].includes(normalized)
  ) {
    icon =
      <FiRefreshCw />;
  }

  return (
    <span
      className={
        `model-status model-status-${normalized}`
      }
    >
      {icon}

      {status || "unknown"}
    </span>
  );
}


function RequestModelModal({
  profiles,
  onClose,
  onCreated,
}) {
  const [provider, setProvider] =
    useState("huggingface");

  const [repository, setRepository] =
    useState("");

  const [revision, setRevision] =
    useState("main");

  const [requestedProfile, setRequestedProfile] =
    useState("");

  const [purpose, setPurpose] =
    useState("");

  const [
    artifactPatterns,
    setArtifactPatterns,
  ] = useState([
    "*Q4_K_M.gguf",
    "*.safetensors",
    "*.json",
    "tokenizer*",
    "*.model",
    "README.md",
  ]);

  const [
    downloadCompleteRepository,
    setDownloadCompleteRepository,
  ] = useState(false);

  const [submitting, setSubmitting] =
    useState(false);

  const [error, setError] =
    useState("");


  useEffect(() => {
    if (
      !requestedProfile &&
      profiles.length
    ) {
      const first =
        profiles[0];

      setRequestedProfile(
        first.name ||
        first.id ||
        first.profile ||
        ""
      );
    }
  }, [
    profiles,
    requestedProfile,
  ]);


  function updateArtifactPattern(
    index,
    value
  ) {
    setArtifactPatterns(
      (current) =>
        current.map(
          (pattern, currentIndex) =>
            currentIndex === index
              ? value
              : pattern
        )
    );
  }


  function addArtifactPattern() {
    setArtifactPatterns(
      (current) => [
        ...current,
        "",
      ]
    );
  }


  function removeArtifactPattern(
    index
  ) {
    setArtifactPatterns(
      (current) =>
        current.filter(
          (_, currentIndex) =>
            currentIndex !== index
        )
    );
  }


  async function submit(
    event
  ) {
    event.preventDefault();

    if (
      !repository.trim()
    ) {
      return;
    }

    const cleanedArtifactPatterns =
      artifactPatterns
        .map(
          (pattern) =>
            pattern.trim()
        )
        .filter(Boolean);

    if (
      cleanedArtifactPatterns.length === 0 &&
      !downloadCompleteRepository
    ) {
      setError(
        "Select at least one artifact pattern "
        + "or explicitly allow a complete "
        + "repository download."
      );

      return;
    }

    setSubmitting(true);
    setError("");

    try {
      const result =
        await createModelRequest({
          provider,
          repository:
            repository.trim(),
          revision:
            revision.trim() ||
            "main",
          requested_profile:
            requestedProfile ||
            null,
          purpose:
            purpose.trim() ||
            "Model evaluation",

          artifact_patterns:
            cleanedArtifactPatterns,

          download_complete_repository:
            downloadCompleteRepository,
        });

      await onCreated(
        result
      );

      onClose();

    } catch (err) {
      setError(
        err.message ||
        "Unable to create model request"
      );

    } finally {
      setSubmitting(false);
    }
  }


  return (
    <div
      className="model-modal-backdrop"
      onMouseDown={(event) => {
        if (
          event.target ===
          event.currentTarget
        ) {
          onClose();
        }
      }}
    >

      <div className="model-modal">

        <div className="model-modal-header">

          <div>
            <span className="eyebrow">
              MODEL SUPPLY CHAIN
            </span>

            <h2>
              Request external model
            </h2>

            <p>
              Register a model for controlled
              ingestion into the trusted
              platform catalog.
            </p>
          </div>

          <button
            type="button"
            className="model-icon-button"
            onClick={onClose}
          >
            <FiX />
          </button>

        </div>


        <form
          className="model-request-form"
          onSubmit={submit}
        >

          <div className="model-form-grid">

            <label>
              Provider

              <select
                value={provider}
                onChange={(event) =>
                  setProvider(
                    event.target.value
                  )
                }
              >
                <option value="huggingface">
                  Hugging Face
                </option>
              </select>
            </label>


            <label>
              Revision

              <input
                value={revision}
                onChange={(event) =>
                  setRevision(
                    event.target.value
                  )
                }
                placeholder="main"
              />
            </label>

          </div>


          <label>
            Hugging Face repository

            <input
              value={repository}
              onChange={(event) =>
                setRepository(
                  event.target.value
                )
              }
              placeholder="mistralai/Mistral-7B-Instruct-v0.3"
              autoFocus
              required
            />

            <span className="model-field-help">
              Use the Hugging Face
              organization/model repository
              identifier.
            </span>
          </label>


          <label>
            Requested inference profile

            <select
              value={requestedProfile}
              onChange={(event) =>
                setRequestedProfile(
                  event.target.value
                )
              }
            >
              {profiles.length === 0 && (
                <option value="">
                  Default platform profile
                </option>
              )}

              {profiles.map(
                (profile) => {
                  const value =
                    profile.name ||
                    profile.id ||
                    profile.profile;

                  return (
                    <option
                      key={value}
                      value={value}
                    >
                      {value}
                    </option>
                  );
                }
              )}
            </select>
          </label>


          <div className="model-artifact-section">

            <div className="model-artifact-header">

              <div>
                <strong>
                  Artifact selection
                </strong>

                <span className="model-field-help">
                  Only matching files will be downloaded
                  from the immutable Hugging Face revision.
                </span>
              </div>

              <button
                type="button"
                className="model-action-button"
                onClick={addArtifactPattern}
                disabled={
                  downloadCompleteRepository
                }
              >
                <FiPlus />
                Add pattern
              </button>

            </div>


            <div className="model-artifact-patterns">

              {artifactPatterns.map(
                (pattern, index) => (
                  <div
                    className="model-artifact-pattern-row"
                    key={index}
                  >
                    <input
                      value={pattern}
                      disabled={
                        downloadCompleteRepository
                      }
                      onChange={(event) =>
                        updateArtifactPattern(
                          index,
                          event.target.value
                        )
                      }
                      placeholder="*.safetensors or *Q4_K_M.gguf"
                    />

                    <button
                      type="button"
                      className="model-icon-button"
                      disabled={
                        downloadCompleteRepository
                      }
                      onClick={() =>
                        removeArtifactPattern(
                          index
                        )
                      }
                      aria-label="Remove artifact pattern"
                    >
                      <FiX />
                    </button>
                  </div>
                )
              )}

            </div>


            <label className="model-full-repository-toggle">

              <input
                type="checkbox"
                checked={
                  downloadCompleteRepository
                }
                onChange={(event) =>
                  setDownloadCompleteRepository(
                    event.target.checked
                  )
                }
              />

              <div>
                <strong>
                  Download complete repository
                </strong>

                <span>
                  Explicitly allow all files in the
                  repository to be downloaded. This can
                  consume significant storage.
                </span>
              </div>

            </label>

          </div>


          <label>
            Business / technical purpose

            <textarea
              value={purpose}
              onChange={(event) =>
                setPurpose(
                  event.target.value
                )
              }
              placeholder="Evaluate the model for secure enterprise inference..."
              rows={4}
            />
          </label>


          <div className="model-security-note">
            <FiShield />

            <div>
              <strong>
                Controlled model ingestion
              </strong>

              <span>
                Creating this request does
                not allow the inference
                runtime to download the
                model directly.
              </span>
            </div>
          </div>


          {error && (
            <div className="model-error">
              {error}
            </div>
          )}


          <div className="model-modal-actions">

            <button
              type="button"
              className="model-button-secondary"
              onClick={onClose}
              disabled={submitting}
            >
              Cancel
            </button>

            <button
              type="submit"
              className="model-button-primary"
              disabled={
                submitting ||
                !repository.trim()
              }
            >
              <FiCloud />

              {submitting
                ? "Submitting..."
                : "Submit request"
              }
            </button>

          </div>

        </form>

      </div>

    </div>
  );
}


export default function Models() {
  const [models, setModels] =
    useState([]);

  const [requests, setRequests] =
    useState([]);

  const [profiles, setProfiles] =
    useState([]);

  const [activeTab, setActiveTab] =
    useState("catalog");

  const [search, setSearch] =
    useState("");

  const [showRequestModal, setShowRequestModal] =
    useState(false);

  const [loading, setLoading] =
    useState(true);

  const [actionId, setActionId] =
    useState(null);

  const [
    deletingModelId,
    setDeletingModelId,
  ] = useState(null);

  const [error, setError] =
    useState("");


  async function loadData() {
    setLoading(true);
    setError("");

    try {
      const [
        modelResult,
        requestResult,
        profileResult,
      ] =
        await Promise.all([
          getModels(),
          getModelRequests(),
          getProfiles(),
        ]);

      setModels(
        Array.isArray(modelResult)
          ? modelResult
          : []
      );

      setRequests(
        Array.isArray(requestResult)
          ? requestResult
          : []
      );

      setProfiles(
        Array.isArray(profileResult)
          ? profileResult
          : []
      );

    } catch (err) {
      setError(
        err.message ||
        "Unable to load model catalog"
      );

    } finally {
      setLoading(false);
    }
  }


  useEffect(() => {
    loadData();
  }, []);


  const filteredModels =
    useMemo(() => {
      const term =
        search
          .trim()
          .toLowerCase();

      if (!term) {
        return models;
      }

      return models.filter(
        (model) =>
          JSON.stringify(model)
            .toLowerCase()
            .includes(term)
      );
    }, [
      models,
      search,
    ]);


  const filteredRequests =
    useMemo(() => {
      const term =
        search
          .trim()
          .toLowerCase();

      if (!term) {
        return requests;
      }

      return requests.filter(
        (request) =>
          JSON.stringify(request)
            .toLowerCase()
            .includes(term)
      );
    }, [
      requests,
      search,
    ]);


  async function removeModel(
    model
  ) {
    const modelId =
      model.id ||
      model.model_id ||
      model.catalog_model_id;

    if (!modelId) {
      setError(
        "Model catalog entry has no model ID."
      );
      return;
    }

    const displayName =
      model.display_name ||
      model.name ||
      model.repository ||
      modelId;

    const confirmed =
      window.confirm(
        `Delete trusted model "${displayName}"?\n\n`
        + "The immutable OCI manifest will be removed "
        + "from the trusted registry.\n"
        + "The request audit history will be preserved."
      );

    if (!confirmed) {
      return;
    }

    setDeletingModelId(
      modelId
    );

    setError("");

    try {
      await deleteModel(
        modelId
      );

      await loadData();

      setActiveTab(
        "catalog"
      );

    } catch (err) {
      setError(
        err.message ||
        "Unable to delete trusted model"
      );

    } finally {
      setDeletingModelId(null);
    }
  }


  async function runAction(
    requestId,
    operation
  ) {
    setActionId(
      requestId
    );

    setError("");

    try {
      await operation();

      await loadData();

      setActiveTab(
        "requests"
      );

    } catch (err) {
      setError(
        err.message ||
        "Model operation failed"
      );

    } finally {
      setActionId(null);
    }
  }


  async function approveRequest(
    request
  ) {
    await runAction(
      request.id,
      () =>
        updateModelRequestStatus(
          request.id,
          {
            status: "approved",
            status_message:
              "Approved by platform administrator",
          }
        )
    );
  }


  async function rejectRequest(
    request
  ) {
    await runAction(
      request.id,
      () =>
        updateModelRequestStatus(
          request.id,
          {
            status: "rejected",
            status_message:
              "Rejected by platform administrator",
          }
        )
    );
  }


  async function ingestRequest(
    request
  ) {
    await runAction(
      request.id,
      () =>
        ingestModelRequest(
          request.id
        )
    );
  }


  async function promoteRequest(
    request
  ) {
    await runAction(
      request.id,
      () =>
        promoteModelRequest(
          request.id
        )
    );
  }


  function requestActions(
    request
  ) {
    const status =
      normalizeStatus(
        request.status
      );

    const busy =
      actionId === request.id;


    if (
      status === "pending"
    ) {
      return (
        <>
          <button
            className="model-action-button"
            disabled={busy}
            onClick={() =>
              ingestRequest(
                request
              )
            }
          >
            <FiDownloadCloud />
            Ingest
          </button>

          <button
            className="model-action-button danger"
            disabled={busy}
            onClick={() =>
              rejectRequest(
                request
              )
            }
          >
            Reject
          </button>
        </>
      );
    }


    if (
      [
        "ingested",
        "validated",
        "scanned",
        "ready_for_approval",
        "pending_approval",
      ].includes(status)
    ) {
      return (
        <>
          <button
            className="model-action-button success"
            disabled={busy}
            onClick={() =>
              approveRequest(
                request
              )
            }
          >
            <FiCheckCircle />
            Approve
          </button>

          <button
            className="model-action-button danger"
            disabled={busy}
            onClick={() =>
              rejectRequest(
                request
              )
            }
          >
            Reject
          </button>
        </>
      );
    }


    if (
      status === "approved"
    ) {
      return (
        <button
          className="model-action-button success"
          disabled={busy}
          onClick={() =>
            promoteRequest(
              request
            )
          }
        >
          <FiUploadCloud />
          Promote
        </button>
      );
    }


    if (
      [
        "failed",
        "ingestion_failed",
      ].includes(status)
    ) {
      return (
        <button
          className="model-action-button"
          disabled={busy}
          onClick={() =>
            ingestRequest(
              request
            )
          }
        >
          <FiRefreshCw />
          Retry ingestion
        </button>
      );
    }


    return (
      <span className="model-no-action">
        —
      </span>
    );
  }


  return (
    <div className="models-v2">

      <div className="models-v2-header">

        <div>
          <span className="eyebrow">
            MODEL GOVERNANCE
          </span>

          <h2>
            AI Model Catalog
          </h2>

          <p>
            Govern approved models and
            external model-import requests
            through the trusted AI supply
            chain.
          </p>
        </div>


        <div className="models-v2-header-actions">

          <button
            className="model-button-secondary"
            onClick={loadData}
            disabled={loading}
          >
            <FiRefreshCw />
            Refresh
          </button>

          <button
            className="model-button-primary"
            onClick={() =>
              setShowRequestModal(true)
            }
          >
            <FiPlus />
            Request model
          </button>

        </div>

      </div>


      <div className="models-summary">

        <div>
          <FiPackage />

          <span>
            Trusted models
          </span>

          <strong>
            {models.length}
          </strong>
        </div>


        <div>
          <FiCloud />

          <span>
            Model requests
          </span>

          <strong>
            {requests.length}
          </strong>
        </div>


        <div>
          <FiClock />

          <span>
            Pending
          </span>

          <strong>
            {
              requests.filter(
                (item) =>
                  normalizeStatus(
                    item.status
                  ) === "pending"
              ).length
            }
          </strong>
        </div>


        <div>
          <FiShield />

          <span>
            Published
          </span>

          <strong>
            {
              requests.filter(
                (item) =>
                  normalizeStatus(
                    item.status
                  ) === "published"
              ).length
            }
          </strong>
        </div>

      </div>


      <div className="models-toolbar">

        <div className="models-tabs">

          <button
            className={
              activeTab === "catalog"
                ? "active"
                : ""
            }
            onClick={() =>
              setActiveTab(
                "catalog"
              )
            }
          >
            Trusted Models

            <span>
              {models.length}
            </span>
          </button>


          <button
            className={
              activeTab === "requests"
                ? "active"
                : ""
            }
            onClick={() =>
              setActiveTab(
                "requests"
              )
            }
          >
            Model Requests

            <span>
              {requests.length}
            </span>
          </button>

        </div>


        <div className="models-search">
          <FiSearch />

          <input
            value={search}
            onChange={(event) =>
              setSearch(
                event.target.value
              )
            }
            placeholder="Search models..."
          />
        </div>

      </div>


      {error && (
        <div className="model-error models-page-error">
          {error}
        </div>
      )}


      {loading ? (
        <div className="models-loading">
          <FiRefreshCw />
          Loading model catalog...
        </div>

      ) : activeTab === "catalog" ? (

        <div className="model-card-grid">

          {filteredModels.length === 0 && (
            <div className="models-empty">
              <FiCpu />

              <h3>
                No trusted model found
              </h3>

              <p>
                Request an external model
                to begin the controlled
                ingestion workflow.
              </p>
            </div>
          )}


          {filteredModels.map(
            (model, index) => {
              const name =
                model.name ||
                model.model_id ||
                model.catalog_model_id ||
                model.repository ||
                `Model ${index + 1}`;

              const repository =
                model.repository ||
                model.source_repository ||
                model.source ||
                "";

              const digest =
                model.artifact_digest ||
                model.digest ||
                "";

              return (
                <article
                  key={
                    model.id ||
                    `${name}-${index}`
                  }
                  className="model-catalog-card"
                >

                  <div className="model-card-icon">
                    <FiCpu />
                  </div>


                  <div className="model-card-content">

                    <div className="model-card-title">

                      <div>
                        <h3>
                          {name}
                        </h3>

                        {repository && (
                          <span>
                            {repository}
                          </span>
                        )}
                      </div>

                      <StatusBadge
                        status={
                          model.status ||
                          "published"
                        }
                      />

                    </div>


                    <div className="model-card-metadata">

                      {model.provider && (
                        <span>
                          Provider
                          <strong>
                            {model.provider}
                          </strong>
                        </span>
                      )}

                      {model.revision && (
                        <span>
                          Revision
                          <strong>
                            {model.revision}
                          </strong>
                        </span>
                      )}

                      {model.profile && (
                        <span>
                          Profile
                          <strong>
                            {model.profile}
                          </strong>
                        </span>
                      )}

                    </div>


                    {digest && (
                      <div className="model-digest">
                        <FiShield />

                        <div>
                          <span>
                            Trusted artifact
                          </span>

                          <code>
                            {digest}
                          </code>
                        </div>
                      </div>
                    )}


                    {model.source === "trusted-registry" && (
                      <div className="model-catalog-actions">

                        <button
                          type="button"
                          className="model-action-button danger"
                          disabled={
                            deletingModelId === model.id
                          }
                          onClick={() =>
                            removeModel(
                              model
                            )
                          }
                        >
                          <FiTrash2 />

                          {
                            deletingModelId === model.id
                              ? "Deleting..."
                              : "Delete model"
                          }
                        </button>

                      </div>
                    )}

                  </div>

                </article>
              );
            }
          )}

        </div>

      ) : (

        <div className="model-request-table-wrapper">

          <table className="model-request-table">

            <thead>
              <tr>
                <th>
                  Repository
                </th>

                <th>
                  Provider
                </th>

                <th>
                  Revision
                </th>

                <th>
                  Profile
                </th>

                <th>
                  Status
                </th>

                <th>
                  Actions
                </th>
              </tr>
            </thead>


            <tbody>

              {filteredRequests.length === 0 && (
                <tr>
                  <td
                    colSpan="6"
                    className="models-table-empty"
                  >
                    No model request found.
                  </td>
                </tr>
              )}


              {filteredRequests.map(
                (request) => (
                  <tr key={request.id}>

                    <td>
                      <div className="model-repository-cell">

                        <strong>
                          {request.repository}
                        </strong>

                        {request.purpose && (
                          <span>
                            {request.purpose}
                          </span>
                        )}

                        {request.status_message && (
                          <small>
                            {request.status_message}
                          </small>
                        )}

                      </div>
                    </td>


                    <td>
                      <span className="model-provider">
                        <FiExternalLink />
                        {request.provider}
                      </span>
                    </td>


                    <td>
                      <code className="model-revision">
                        {
                          request.revision ||
                          "main"
                        }
                      </code>
                    </td>


                    <td>
                      {
                        request.requested_profile ||
                        "—"
                      }
                    </td>


                    <td>
                      <StatusBadge
                        status={request.status}
                      />
                    </td>


                    <td>
                      <div className="model-actions">
                        {requestActions(
                          request
                        )}
                      </div>
                    </td>

                  </tr>
                )
              )}

            </tbody>

          </table>

        </div>
      )}


      {showRequestModal && (
        <RequestModelModal
          profiles={profiles}
          onClose={() =>
            setShowRequestModal(false)
          }
          onCreated={async () => {
            await loadData();

            setActiveTab(
              "requests"
            );
          }}
        />
      )}

    </div>
  );
}
