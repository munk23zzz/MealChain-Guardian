"""Inferhub caller — unit test dengan transport urllib di-stub.

Kontrak:
- POST {model, messages:[{role:user,content:prompt}], max_tokens, temperature}
- header Authorization: Bearer (key dari env, tidak pernah di-print/log)
- struktur response: choices[0].message.content (some provider menambahkan
  reasoning_content — diabaikan, hanya content yang diambil)
- HTTP error (402/429/5xx) → InferhubInvocationError dengan status_code
- INFERHUB_URL / INFERHUB_API_KEY kosong → RuntimeError (pemanggil memutuskan
  UNAVAILABLE — jujur, tanpa panggilan jaringan)
"""

import json
import urllib.error

import pytest

from app.ai_providers.inferhub_caller import (
    InferhubInvocationError,
    build_caller,
)


class _FakeHTTPError(urllib.error.HTTPError):
    def __init__(self, status: int, body: bytes = b""):
        super().__init__("https://x", status, "err", hdrs=None, fp=None)
        self._body = body

    def read(self) -> bytes:
        return self._body


def _install_fake_urlopen(monkeypatch, *, payload=None, http_error=None, other_error=None):
    sent = {}

    def fake_urlopen(req, timeout=None):
        sent["url"] = req.full_url
        sent["headers"] = dict(req.header_items())
        sent["body"] = json.loads(req.data.decode())
        if http_error is not None:
            raise http_error
        if other_error is not None:
            raise other_error
        return _FakeResponse(payload)

    import app.ai_providers.inferhub_caller as mod

    monkeypatch.setattr(mod, "urlopen", fake_urlopen)
    return sent


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self) -> bytes:
        return json.dumps(self._payload).encode()


def test_build_caller_missing_env_raises(monkeypatch):
    monkeypatch.delenv("INFERHUB_URL", raising=False)
    monkeypatch.delenv("INFERHUB_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        build_caller("cb/kimi-k3")


def test_caller_posts_openai_shaped_body_with_bearer(monkeypatch):
    monkeypatch.setenv("INFERHUB_URL", "https://api.inferhub.dev/v1/chat/completions")
    monkeypatch.setenv("INFERHUB_API_KEY", "test-key-123")
    sent = _install_fake_urlopen(
        monkeypatch,
        payload={"choices": [{"message": {"content": '{"verdict":"CONSISTENT"}'}}]},
    )
    caller = build_caller("cb/kimi-k3")
    out = caller('Konteks: {"a":1}')
    assert out == '{"verdict":"CONSISTENT"}'
    assert sent["url"] == "https://api.inferhub.dev/v1/chat/completions"
    assert sent["body"]["model"] == "cb/kimi-k3"
    assert sent["body"]["messages"][0]["content"].startswith("Konteks:")
    assert sent["body"]["temperature"] == 0
    headers = {k.lower(): v for k, v in sent["headers"].items()}
    assert headers.get("authorization") == "Bearer test-key-123"


def test_http_429_maps_to_rate_limited_status(monkeypatch):
    monkeypatch.setenv("INFERHUB_URL", "https://api.inferhub.dev/v1/chat/completions")
    monkeypatch.setenv("INFERHUB_API_KEY", "test-key-123")
    _install_fake_urlopen(monkeypatch, http_error=_FakeHTTPError(429))
    caller = build_caller("cb/kimi-k3")
    with pytest.raises(InferhubInvocationError) as excinfo:
        caller("x")
    assert excinfo.value.status_code == 429


def test_http_402_maps_to_status_402(monkeypatch):
    monkeypatch.setenv("INFERHUB_URL", "https://api.inferhub.dev/v1/chat/completions")
    monkeypatch.setenv("INFERHUB_API_KEY", "test-key-123")
    _install_fake_urlopen(monkeypatch, http_error=_FakeHTTPError(402))
    caller = build_caller("ali/qwen3.8-max-0902")
    with pytest.raises(InferhubInvocationError) as excinfo:
        caller("x")
    assert excinfo.value.status_code == 402


def test_empty_content_is_returned_as_is(monkeypatch):
    # kimi tanpa max_tokens cukup pernah membalas content kosong — caller
    # jujur mengembalikan apa adanya; parser client yang menilai
    monkeypatch.setenv("INFERHUB_URL", "https://api.inferhub.dev/v1/chat/completions")
    monkeypatch.setenv("INFERHUB_API_KEY", "test-key-123")
    _install_fake_urlopen(monkeypatch, payload={"choices": [{"message": {"content": ""}}]})
    caller = build_caller("cb/kimi-k3")
    assert caller("x") == ""


# --- normalisasi endpoint (29 Okt 2026) ---------------------------------------------------
#
# INFERHUB_URL di operator berisi base `https://api.inferhub.dev/v1` sehingga POST
# mendarat di `/v1` dan SELALU 404 ("404 page not found"), padahal API InferHub hidup dan
# katalognya 397 model. Akibat yang terukur di rantai nyata: 8 slot fallback InferHub mati
# serentak dan chain turun langsung ke Bedrock. Tes ini mengunci bentuk URL yang dikirim.


def test_base_url_tanpa_subpath_dinormalisasi_ke_chat_completions(monkeypatch):
    monkeypatch.setenv("INFERHUB_URL", "https://api.inferhub.dev/v1")
    monkeypatch.setenv("INFERHUB_API_KEY", "test-key-123")
    sent = _install_fake_urlopen(
        monkeypatch,
        payload={"choices": [{"message": {"content": "ok"}}]},
    )

    assert build_caller("cb/kimi-k3")("halo") == "ok"
    assert sent["url"] == "https://api.inferhub.dev/v1/chat/completions"


def test_base_url_dengan_garis_miring_penutup_tidak_menggandakan_subpath(monkeypatch):
    monkeypatch.setenv("INFERHUB_URL", "https://api.inferhub.dev/v1/")
    monkeypatch.setenv("INFERHUB_API_KEY", "test-key-123")
    sent = _install_fake_urlopen(
        monkeypatch,
        payload={"choices": [{"message": {"content": "ok"}}]},
    )

    build_caller("cb/kimi-k3")("halo")
    assert sent["url"] == "https://api.inferhub.dev/v1/chat/completions"


def test_url_lengkap_tidak_diubah(monkeypatch):
    monkeypatch.setenv("INFERHUB_URL", "https://api.inferhub.dev/v1/chat/completions")
    monkeypatch.setenv("INFERHUB_API_KEY", "test-key-123")
    sent = _install_fake_urlopen(
        monkeypatch,
        payload={"choices": [{"message": {"content": "ok"}}]},
    )

    build_caller("cb/kimi-k3")("halo")
    assert sent["url"] == "https://api.inferhub.dev/v1/chat/completions"
