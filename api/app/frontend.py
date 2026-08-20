from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


DEFAULT_FRONTEND_DIR = Path(
    "/opt/ai-platform/ui"
)


def mount_frontend(
    app: FastAPI,
) -> None:
    """
    Serve the production React/Vite application from FastAPI.

    API routes must be registered before this function is called.

    Routing rules:

        /api/*       -> FastAPI API
        /docs        -> FastAPI Swagger
        /openapi.json
        /assets/*    -> Vite static assets
        everything else -> React SPA index.html
    """

    frontend_dir = Path(
        os.getenv(
            "ACP_FRONTEND_DIR",
            str(DEFAULT_FRONTEND_DIR),
        )
    ).resolve()

    index_file = (
        frontend_dir
        / "index.html"
    )

    assets_dir = (
        frontend_dir
        / "assets"
    )

    if not index_file.is_file():
        print(
            "Frontend not mounted: "
            f"{index_file} does not exist",
            flush=True,
        )
        return

    if assets_dir.is_dir():
        app.mount(
            "/assets",
            StaticFiles(
                directory=str(
                    assets_dir
                )
            ),
            name="frontend-assets",
        )

    @app.get(
        "/",
        include_in_schema=False,
    )
    async def frontend_root():
        return FileResponse(
            index_file
        )

    @app.get(
        "/{full_path:path}",
        include_in_schema=False,
    )
    async def frontend_spa(
        full_path: str,
    ):
        # Never transform missing API endpoints
        # into index.html.
        protected_prefixes = (
            "api/",
            "docs",
            "redoc",
            "openapi.json",
        )

        if full_path.startswith(
            protected_prefixes
        ):
            raise HTTPException(
                status_code=404,
                detail="Not found",
            )

        requested_file = (
            frontend_dir
            / full_path
        ).resolve()

        # Prevent directory traversal.
        try:
            requested_file.relative_to(
                frontend_dir
            )
        except ValueError:
            raise HTTPException(
                status_code=404,
                detail="Not found",
            )

        # favicon, manifest, etc.
        if requested_file.is_file():
            return FileResponse(
                requested_file
            )

        # React client-side routing.
        return FileResponse(
            index_file
        )
