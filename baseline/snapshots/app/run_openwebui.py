"""Relocatable Open WebUI launcher for the bundled Windows runtime."""

import os

# 0.11.2's import-time Alembic runner can hit a circular import on Windows.
# Build the local SQLite schema directly before starting the ASGI lifespan.
os.environ.setdefault("ENABLE_DB_MIGRATIONS", "false")
os.environ.setdefault("FROM_INIT_PY", "true")
import open_webui.main  # noqa: F401,E402
from open_webui.internal.db import Base, engine  # noqa: E402
import uvicorn  # noqa: E402

Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    uvicorn.run(
        open_webui.main.app,
        host="0.0.0.0",
        port=3000,
        forwarded_allow_ips="*",
        loop="none",
    )
