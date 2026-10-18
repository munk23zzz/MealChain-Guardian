"""Kontrak feature flag review 7 worker agent (P0).

Fitur ini masih gelap: default MATI, mode hanya `advisory`, dan timeout
dibaca dari environment. P0 belum menjalankan worker apa pun; tes ini
mengunci kontrak agar perilaku lama (1 supervisor + 4 tool baca) tidak
berubah tanpa sengaja.
"""

from app.core.config import Settings


def test_defaults_are_off_and_advisory() -> None:
    fields = Settings.model_fields
    assert fields["multi_agent_review"].default is False
    assert fields["agent_review_mode"].default == "advisory"
    assert fields["agent_review_timeout_seconds"].default == 75


def test_environment_can_override_flag(monkeypatch) -> None:
    monkeypatch.setenv("MULTI_AGENT_REVIEW", "true")
    monkeypatch.setenv("AGENT_REVIEW_MODE", "predecision")
    monkeypatch.setenv("AGENT_REVIEW_TIMEOUT_SECONDS", "90")

    settings = Settings(_env_file=None)

    assert settings.multi_agent_review is True
    assert settings.agent_review_mode == "predecision"
    assert settings.agent_review_timeout_seconds == 90
