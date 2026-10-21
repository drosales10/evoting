"""Lifecycle guards for a statute consultation. HTTP routers map these to status codes."""

from __future__ import annotations

EDITABLE_STATUSES = frozenset({"DRAFT", "REGISTRATION"})


class StatuteFlowError(Exception):
    def __init__(self, message: str, status_code: int = 409) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def require_editable(status: str) -> None:
    """Text and structure change only before the freeze."""
    if status not in EDITABLE_STATUSES:
        raise StatuteFlowError(
            "El texto del estatuto solo se edita en borrador o en registro",
        )


def require_status(status: str, expected: str, message: str) -> None:
    if status != expected:
        raise StatuteFlowError(message)


def require_can_cast(*, eligible: bool, has_voted: bool, reason: str | None) -> None:
    """One sealed ballot per eligible member."""
    if not eligible:
        detail = "El miembro no es elegible para esta consulta"
        if reason:
            detail = f"{detail}: {reason}"
        raise StatuteFlowError(detail, status_code=403)
    if has_voted:
        raise StatuteFlowError(
            "El miembro ya emitió su boleta para esta consulta",
            status_code=409,
        )
