import os

# Configure test environment before importing app modules so Settings initializes cleanly.
os.environ["ENVIRONMENT"] = "testing"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-for-lms-api-minimum-32-chars"
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-for-lms-api-minimum-32-chars"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["CORS_ORIGINS"] = '["http://localhost:3000"]'
os.environ["SENTRY_DSN"] = ""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.common.rate_limit import auth_rate_limiter
from app.core.security import create_access_token
from app.db.base import Base
from app.main import create_app
from app.models import User, UserRole
from tests.factories import create_user_record


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Isolated per-test async database session with foreign keys enforced."""
    test_db_url = os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    connect_args = {"check_same_thread": False} if test_db_url.startswith("sqlite") else {}
    engine = create_async_engine(test_db_url, connect_args=connect_args)

    if test_db_url.startswith("sqlite"):

        @event.listens_for(engine.sync_engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, _connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    auth_rate_limiter.reset()
    test_app = create_app()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    test_app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client

    test_app.dependency_overrides.clear()


def auth_headers_for(user: User) -> dict[str, str]:
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def student_user(db_session: AsyncSession) -> User:
    return await create_user_record(
        db_session,
        email="student@example.com",
        full_name="Student One",
        role=UserRole.STUDENT,
    )


@pytest.fixture
async def second_student_user(db_session: AsyncSession) -> User:
    return await create_user_record(
        db_session,
        email="student2@example.com",
        full_name="Student Two",
        role=UserRole.STUDENT,
    )


@pytest.fixture
async def instructor_user(db_session: AsyncSession) -> User:
    return await create_user_record(
        db_session,
        email="instructor@example.com",
        full_name="Instructor One",
        role=UserRole.INSTRUCTOR,
    )


@pytest.fixture
async def other_instructor_user(db_session: AsyncSession) -> User:
    return await create_user_record(
        db_session,
        email="instructor2@example.com",
        full_name="Instructor Two",
        role=UserRole.INSTRUCTOR,
    )


@pytest.fixture
async def admin_user(db_session: AsyncSession) -> User:
    return await create_user_record(
        db_session,
        email="admin@example.com",
        full_name="Admin User",
        role=UserRole.ADMIN,
    )


@pytest.fixture
def student_headers(student_user: User) -> dict[str, str]:
    return auth_headers_for(student_user)


@pytest.fixture
def second_student_headers(second_student_user: User) -> dict[str, str]:
    return auth_headers_for(second_student_user)


@pytest.fixture
def instructor_headers(instructor_user: User) -> dict[str, str]:
    return auth_headers_for(instructor_user)


@pytest.fixture
def other_instructor_headers(other_instructor_user: User) -> dict[str, str]:
    return auth_headers_for(other_instructor_user)


@pytest.fixture
def admin_headers(admin_user: User) -> dict[str, str]:
    return auth_headers_for(admin_user)
