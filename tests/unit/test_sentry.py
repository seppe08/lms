import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.main import create_app


def _settings(**overrides: object) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        SECRET_KEY="a" * 32,
        JWT_SECRET_KEY="b" * 32,
        **overrides,  # type: ignore[arg-type]
    )


def test_sentry_defaults() -> None:
    cfg = _settings()

    assert cfg.SENTRY_DSN is None
    assert cfg.SENTRY_TRACES_SAMPLE_RATE == 0.1
    assert cfg.SENTRY_CAPTURE_LOGS is True


@pytest.mark.parametrize("rate", [-0.1, 1.1])
def test_sentry_traces_sample_rate_is_bounded(rate: float) -> None:
    with pytest.raises(ValidationError):
        _settings(SENTRY_TRACES_SAMPLE_RATE=rate)


def test_create_app_configures_sentry_when_dsn_is_set(monkeypatch: pytest.MonkeyPatch) -> None:
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
    integrations = init_kwargs[0]["integrations"]
    assert isinstance(integrations, list)
    assert len(integrations) == 1
    assert isinstance(integrations[0], LoggingIntegration)


def test_create_app_skips_log_forwarding_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sentry_sdk

    init_kwargs: list[dict[str, object]] = []
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: init_kwargs.append(kwargs))

    create_app(
        _settings(
            SENTRY_DSN="https://public-key@o1.ingest.sentry.io/1",
            SENTRY_CAPTURE_LOGS=False,
        )
    )

    assert init_kwargs[0]["integrations"] == []
