"""Local development server launcher for FastAPI on port 3000.

Bootstraps a gitignored `.env` with freshly generated local secrets and a local
SQLite database only when no `.env` or `DATABASE_URL` is configured, then runs
Uvicorn serving `app.main:app`.
"""

import asyncio
import os
import secrets
import sys
from pathlib import Path

import uvicorn

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

ENV_FILE = ROOT_DIR / ".env"


def ensure_local_env() -> None:
    """Create a local gitignored .env if neither .env nor DATABASE_URL exists."""
    if ENV_FILE.exists() or os.environ.get("DATABASE_URL"):
        return

    secret_key = secrets.token_hex(32)
    jwt_secret_key = secrets.token_hex(32)
    content = (
        "PROJECT_NAME=LMS API\n"
        "ENVIRONMENT=development\n"
        "DEBUG=false\n"
        "LOG_LEVEL=INFO\n"
        "DATABASE_URL=sqlite+aiosqlite:///./dev_lms.db\n"
        f"SECRET_KEY={secret_key}\n"
        f"JWT_SECRET_KEY={jwt_secret_key}\n"
        'CORS_ORIGINS=["http://localhost:3000"]\n'
    )
    ENV_FILE.write_text(content, encoding="utf-8")


async def ensure_sqlite_schema() -> None:
    """Initialize SQLite tables automatically for zero-config local preview."""
    import app.models  # noqa: F401
    from app.core.config import settings
    from app.db.base import Base
    from app.db.session import engine

    if settings.DATABASE_URL.startswith("sqlite"):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


def main() -> None:
    ensure_local_env()
    asyncio.run(ensure_sqlite_schema())
    port = int(os.environ.get("APP_PORT", "3000"))
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
