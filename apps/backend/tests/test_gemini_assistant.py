"""Unit tests for Gemini assistant helpers (no live API calls)."""

from __future__ import annotations

from app.services.gemini_assistant import gemini_configured


def test_gemini_configured_requires_flag_and_key(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "gemini_enabled", False)
    monkeypatch.setattr(config.settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(config.settings, "gemini_model_id", "gemini-3.5-flash")
    assert gemini_configured() is False

    monkeypatch.setattr(config.settings, "gemini_enabled", True)
    assert gemini_configured() is True

    monkeypatch.setattr(config.settings, "gemini_api_key", None)
    assert gemini_configured() is False
