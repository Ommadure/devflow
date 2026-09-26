"""DevFlow API entry point.

Phase 0 ships only the app factory and a liveness probe, so the toolchain, Docker and CI
have something real to check. Phase 1 adds configuration, logging, errors, the database
and authentication.
"""

from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="DevFlow API", version="0.1.0")

    @app.get("/health", tags=["infrastructure"])
    async def health() -> dict[str, str]:
        # Liveness only: touches nothing, so a slow database can never make the platform
        # restart a healthy process. Readiness (/ready) arrives with the database in Phase 1.
        return {"status": "ok"}

    return app


app = create_app()
