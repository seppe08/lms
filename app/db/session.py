from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.core.config import settings


def create_engine_from_url(database_url: str) -> AsyncEngine:
    connect_args: dict[str, object] = {}
    kwargs: dict[str, object] = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_async_engine(database_url, connect_args=connect_args, **kwargs)


engine = create_engine_from_url(settings.DATABASE_URL)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
