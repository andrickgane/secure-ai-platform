from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.request
from typing import Any

from sqlalchemy import (
    select,
    text,
)
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.database import (
    SessionLocal,
)
from app.models.deployment import (
    Deployment,
)


logger = logging.getLogger(
    "plateform_ai.runtime_reconciler"
)


# PostgreSQL session-level advisory lock.
#
# The API currently runs multiple Uvicorn workers.
# Only one worker must perform reconciliation during
# a given cycle.
_RECONCILIATION_LOCK_ID = 764201846


class RuntimeReconciliationService:
    """
    Reconcile database deployment state with the
    actual external inference runtime.

    Important safety property:

    This service only performs a one-way transition:

        ready/deployed -> stopped

    It never promotes a stopped deployment to ready.

    Promotion to ready remains controlled by the
    trusted runtime activation callback.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        db: Session,
    ) -> None:
        self.settings = settings
        self.db = db

    # ======================================================
    # AUTH
    # ======================================================

    def _api_key_for_runtime(
        self,
        runtime: str,
    ) -> str | None:
        if runtime.startswith(
            "llama-cpp"
        ):
            return (
                self.settings
                .llama_cpp_api_key
            )

        if runtime.startswith(
            "vllm"
        ):
            return (
                self.settings
                .vllm_api_key
            )

        return None

    # ======================================================
    # PROBE
    # ======================================================

    def _probe(
        self,
        deployment: Deployment,
    ) -> tuple[
        bool,
        str,
    ]:
        if not deployment.endpoint:
            return (
                False,
                "missing endpoint",
            )

        api_key = (
            self._api_key_for_runtime(
                deployment.runtime
            )
        )

        if not api_key:
            return (
                True,
                (
                    "runtime has no "
                    "reconciliation probe"
                ),
            )

        url = (
            deployment.endpoint
            .rstrip("/")
            + "/v1/models"
        )

        request = urllib.request.Request(
            url,
            method="GET",
            headers={
                "Accept": (
                    "application/json"
                ),
                "Authorization": (
                    f"Bearer {api_key}"
                ),
            },
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=5,
            ) as response:
                if response.status != 200:
                    return (
                        False,
                        (
                            "model probe returned "
                            f"HTTP "
                            f"{response.status}"
                        ),
                    )

                payload = json.loads(
                    response.read()
                )

        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            OSError,
            json.JSONDecodeError,
        ) as exc:
            return (
                False,
                (
                    "model probe failed: "
                    f"{type(exc).__name__}"
                ),
            )

        if not isinstance(
            payload,
            dict,
        ):
            return (
                False,
                "invalid /v1/models payload",
            )

        items = payload.get(
            "data",
            [],
        )

        if not isinstance(
            items,
            list,
        ):
            return (
                False,
                "invalid /v1/models data",
            )

        served_models: set[str] = set()

        for item in items:
            if not isinstance(
                item,
                dict,
            ):
                continue

            model_id = item.get(
                "id"
            )

            if isinstance(
                model_id,
                str,
            ):
                served_models.add(
                    model_id
                )

        if deployment.model not in (
            served_models
        ):
            return (
                False,
                (
                    "expected model is "
                    "not currently served"
                ),
            )

        return (
            True,
            "runtime healthy",
        )

    # ======================================================
    # CYCLE
    # ======================================================

    def reconcile_once(
        self,
    ) -> int:
        locked = bool(
            self.db.scalar(
                text(
                    """
                    SELECT
                        pg_try_advisory_lock(
                            :lock_id
                        )
                    """
                ),
                {
                    "lock_id": (
                        _RECONCILIATION_LOCK_ID
                    ),
                },
            )
        )

        if not locked:
            return 0

        demoted = 0

        try:
            deployments = (
                self.db.execute(
                    select(
                        Deployment
                    )
                    .where(
                        Deployment.deployment_mode
                        == "external"
                    )
                    .where(
                        Deployment.status.in_(
                            (
                                "ready",
                                "deployed",
                            )
                        )
                    )
                    .order_by(
                        Deployment.id
                    )
                    .with_for_update(
                        skip_locked=True
                    )
                )
                .scalars()
                .all()
            )

            for deployment in (
                deployments
            ):
                api_key = (
                    self
                    ._api_key_for_runtime(
                        deployment.runtime
                    )
                )

                if api_key is None:
                    logger.warning(
                        (
                            "Skipping runtime "
                            "reconciliation for "
                            "unsupported external "
                            "runtime name=%s "
                            "runtime=%s"
                        ),
                        deployment.name,
                        deployment.runtime,
                    )

                    continue

                healthy, reason = (
                    self._probe(
                        deployment
                    )
                )

                if healthy:
                    logger.debug(
                        (
                            "Runtime healthy "
                            "name=%s runtime=%s"
                        ),
                        deployment.name,
                        deployment.runtime,
                    )

                    continue

                previous_status = (
                    deployment.status
                )

                deployment.status = (
                    "stopped"
                )

                self.db.flush()

                demoted += 1

                logger.warning(
                    (
                        "Runtime reconciliation "
                        "demoted deployment "
                        "name=%s runtime=%s "
                        "status=%s->stopped "
                        "reason=%s"
                    ),
                    deployment.name,
                    deployment.runtime,
                    previous_status,
                    reason,
                )

            self.db.commit()

            return demoted

        except Exception:
            self.db.rollback()

            logger.exception(
                (
                    "Runtime reconciliation "
                    "cycle failed"
                )
            )

            return 0

        finally:
            try:
                self.db.execute(
                    text(
                        """
                        SELECT
                            pg_advisory_unlock(
                                :lock_id
                            )
                        """
                    ),
                    {
                        "lock_id": (
                            _RECONCILIATION_LOCK_ID
                        ),
                    },
                )

            except Exception:
                logger.exception(
                    (
                        "Could not release "
                        "runtime reconciliation "
                        "advisory lock"
                    )
                )

    # ======================================================
    # ASYNC LOOP
    # ======================================================

    @classmethod
    async def run_forever(
        cls,
        *,
        settings: Settings,
        interval_seconds: int = 15,
    ) -> None:
        while True:
            db = SessionLocal()

            try:
                service = cls(
                    settings=settings,
                    db=db,
                )

                await asyncio.to_thread(
                    service.reconcile_once
                )

            except (
                asyncio.CancelledError
            ):
                raise

            except Exception:
                logger.exception(
                    (
                        "Unhandled runtime "
                        "reconciliation error"
                    )
                )

            finally:
                db.close()

            await asyncio.sleep(
                interval_seconds
            )
