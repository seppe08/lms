"""Sentry Agent Tracing helpers.

Conversations group ``gen_ai`` spans by ``gen_ai.conversation.id``. The FastAPI
runtime binds a client-supplied, stable conversation ID to the current Sentry
scope for every request and attributes the authenticated user so the
Conversations view can show who started each chat.

See https://docs.sentry.io/platforms/python/agent-tracing/#tracking-conversations
"""

import re
from typing import TYPE_CHECKING

import sentry_sdk.ai

if TYPE_CHECKING:
    from app.models.user import User

CONVERSATION_ID_HEADER = "X-Sentry-Conversation-ID"

# Sentry expects a short opaque ID: alphanumeric, dashes or underscores only.
_CONVERSATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def normalize_conversation_id(value: str | None) -> str | None:
    """Return a valid conversation ID, or ``None`` for absent/malformed values."""
    if value and _CONVERSATION_ID_PATTERN.fullmatch(value):
        return value
    return None


def bind_conversation_id(value: str | None) -> str | None:
    """Attach a conversation ID to the current Sentry scope.

    Returns the bound ID so callers can clear exactly what they set. Missing or
    invalid IDs are ignored; Sentry should see no conversation rather than an
    unstable one derived from a request or trace ID.
    """
    conversation_id = normalize_conversation_id(value)
    if conversation_id:
        sentry_sdk.ai.set_conversation_id(conversation_id)
    return conversation_id


def clear_conversation_id() -> None:
    """Remove the conversation ID from the current Sentry scope."""
    sentry_sdk.get_current_scope().remove_conversation_id()


def set_sentry_user(user: "User") -> None:
    """Attribute the current Sentry scope (and its conversation) to a user."""
    sentry_sdk.set_user({"id": str(user.id), "email": user.email})
