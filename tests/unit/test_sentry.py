import subprocess
import sys
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.core.config import Settings
from app.core.sentry_agent import (
    CONVERSATION_ID_HEADER,
    normalize_conversation_id,
    set_sentry_user,
)
from app.main import create_app


def _settings(**overrides: object) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        SECRET_KEY="a" * 32,
        JWT_SECRET_KEY="b" * 32,
        **overrides,  # type: ignore[arg-type]
    )


@pytest.fixture
def stub_sentry_init(monkeypatch: pytest.MonkeyPatch) -> None:
    import sentry_sdk

    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: None)


def test_sentry_defaults() -> None:
    cfg = _settings()

    assert cfg.SENTRY_DSN is None
    assert cfg.SENTRY_TRACES_SAMPLE_RATE == 0.1
    assert cfg.SENTRY_CAPTURE_LOGS is True
    assert cfg.SENTRY_AI_CAPTURE_INPUTS is True
    assert cfg.SENTRY_AI_CAPTURE_OUTPUTS is True


@pytest.mark.parametrize("rate", [-0.1, 1.1])
def test_sentry_traces_sample_rate_is_bounded(rate: float) -> None:
    with pytest.raises(ValidationError):
        _settings(SENTRY_TRACES_SAMPLE_RATE=rate)


def test_create_app_configures_sentry_agent_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    import sentry_sdk
    from sentry_sdk.integrations.logging import LoggingIntegration

    init_kwargs: list[dict[str, object]] = []
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: init_kwargs.append(kwargs))

    create_app(
        _settings(
            SENTRY_DSN="https://public-key@o1.ingest.sentry.io/1",
            ENVIRONMENT="testing",
            SENTRY_TRACES_SAMPLE_RATE=0.5,
            SENTRY_CAPTURE_LOGS=True,
        )
    )

    assert len(init_kwargs) == 1
    assert init_kwargs[0]["dsn"] == "https://public-key@o1.ingest.sentry.io/1"
    assert init_kwargs[0]["environment"] == "testing"
    assert init_kwargs[0]["traces_sample_rate"] == 0.5
    assert init_kwargs[0]["data_collection"] == {"gen_ai": {"inputs": True, "outputs": True}}
    integrations = init_kwargs[0]["integrations"]
    assert isinstance(integrations, list)
    assert len(integrations) == 1
    assert isinstance(integrations[0], LoggingIntegration)


def test_ai_content_capture_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    import sentry_sdk

    init_kwargs: list[dict[str, object]] = []
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: init_kwargs.append(kwargs))

    create_app(
        _settings(
            SENTRY_DSN="https://public-key@o1.ingest.sentry.io/1",
            SENTRY_AI_CAPTURE_INPUTS=False,
            SENTRY_AI_CAPTURE_OUTPUTS=False,
            SENTRY_CAPTURE_LOGS=False,
        )
    )

    assert init_kwargs[0]["data_collection"] == {"gen_ai": {"inputs": False, "outputs": False}}
    assert init_kwargs[0]["integrations"] == []


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("conv_abc123", "conv_abc123"),
        ("sess-987654", "sess-987654"),
        ("", None),
        (None, None),
        ("https://example.com/chat/1", None),
        ("conv with spaces", None),
        ("x" * 129, None),
    ],
)
def test_normalize_conversation_id(value: str | None, expected: str | None) -> None:
    assert normalize_conversation_id(value) == expected


def test_agent_module_imports_sentry_ai_submodule() -> None:
    # sentry_sdk.ai is a submodule and is not an attribute of sentry_sdk until
    # imported. Verify a clean interpreter gets it from our module.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, app.core.sentry_agent; assert 'sentry_sdk.ai' in sys.modules",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


async def test_conversation_header_is_bound_to_request_scope(stub_sentry_init: None) -> None:
    import sentry_sdk

    application = create_app(_settings(SENTRY_DSN="https://public-key@o1.ingest.sentry.io/1"))

    @application.get("/agent-scope")
    async def agent_scope() -> dict[str, str | None]:
        scope = sentry_sdk.get_current_scope()
        return {"conversation_id": scope.get_conversation_id()}

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://testserver"
    ) as client:
        response = await client.get("/agent-scope", headers={CONVERSATION_ID_HEADER: "conv_abc123"})

    assert response.status_code == 200
    assert response.json() == {"conversation_id": "conv_abc123"}
    assert sentry_sdk.get_current_scope().get_conversation_id() is None


async def test_invalid_conversation_header_is_ignored(stub_sentry_init: None) -> None:
    import sentry_sdk

    application = create_app(_settings(SENTRY_DSN="https://public-key@o1.ingest.sentry.io/1"))

    @application.get("/agent-scope")
    async def agent_scope() -> dict[str, str | None]:
        return {"conversation_id": sentry_sdk.get_current_scope().get_conversation_id()}

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://testserver"
    ) as client:
        response = await client.get(
            "/agent-scope", headers={CONVERSATION_ID_HEADER: "https://example.com/chat"}
        )

    assert response.status_code == 200
    assert response.json() == {"conversation_id": None}


def test_sentry_user_attribution(monkeypatch: pytest.MonkeyPatch) -> None:
    import sentry_sdk

    calls: list[object] = []
    monkeypatch.setattr(sentry_sdk, "set_user", lambda user: calls.append(user))

    set_sentry_user(SimpleNamespace(id=42, email="student@example.com"))  # type: ignore[arg-type]

    assert calls == [{"id": "42", "email": "student@example.com"}]
