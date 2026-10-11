"""Test klien SAP AI Core (S4-10) — TANPA jaringan.

Transport disuntik (fake) supaya bentuk request, parsing, taksonomi error, dan
aturan \"rahasia tidak bocor\" diuji deterministik. Kontrak nyata yang diukur
2026-10-11 ada di docstring modul `app.ai_providers.sap_ai_core_caller`.
"""

from __future__ import annotations

import base64
import json

import pytest

from app.ai_providers.sap_ai_core_caller import (
    DEFAULT_TARGET_COLUMN,
    SapAiCoreClient,
    SapAiCoreConfig,
    SapAiCoreError,
    build_llm_caller,
    build_rpt_caller,
)

ENV_LENGKAP = {
    "SAP_AI_CORE_AUTH_URL": "https://auth.example",
    "SAP_AI_CORE_API_URL": "https://api.example",
    "SAP_AI_CORE_CLIENT_ID": "client-id-uji",
    "SAP_AI_CORE_CLIENT_SECRET": "rahasia-uji-jangan-bocor",
    "SAP_AI_CORE_RESOURCE_GROUP": "default",
    "SAP_AI_CORE_DEPLOYMENT_ID_LLM": "dep-llm",
    "SAP_AI_CORE_DEPLOYMENT_ID_RPT": "dep-rpt",
}
RAHASIA = ENV_LENGKAP["SAP_AI_CORE_CLIENT_SECRET"]


class TransportPalsu:
    """Transport palsu: mencatat panggilan, menjawab dari antrean."""

    def __init__(self, *responses: tuple[int, bytes]):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append(
            {"method": method, "url": url, "headers": dict(headers), "body": body}
        )
        if not self.responses:
            raise AssertionError(f"panggilan tak terduga: {method} {url}")
        return self.responses.pop(0)

    @property
    def urls(self) -> list[str]:
        return [c["url"] for c in self.calls]


def _token_response(expires_in: int = 3600) -> tuple[int, bytes]:
    return 200, json.dumps({"access_token": "tok-1", "expires_in": expires_in}).encode()


def _invoke_response(text: str = "halo") -> tuple[int, bytes]:
    return 200, json.dumps({"content": [{"type": "text", "text": text}]}).encode()


def _predict_response(predictions: list[float]) -> tuple[int, bytes]:
    return (
        200,
        json.dumps(
            {
                "predictions": [
                    {
                        DEFAULT_TARGET_COLUMN: [
                            {
                                "prediction": p,
                                "confidence": None,
                                "confidence_interval": [p - 10.0, p + 10.0],
                            }
                        ]
                    }
                    for p in predictions
                ],
                "metadata": {"num_predictions": len(predictions)},
            }
        ).encode(),
    )


def _payload(panggilan: dict) -> dict:
    return json.loads(panggilan["body"].decode("utf-8"))


# --- konfigurasi -----------------------------------------------------------


def test_config_dari_env_lengkap():
    cfg = SapAiCoreConfig.from_env(ENV_LENGKAP)
    assert cfg.api_url == "https://api.example"
    assert cfg.resource_group == "default"
    assert cfg.deployment("llm") == "dep-llm"
    assert cfg.deployment("rpt") == "dep-rpt"


def test_config_env_kurang_menolak_tanpa_jaringan():
    kurang = {k: v for k, v in ENV_LENGKAP.items() if k != "SAP_AI_CORE_CLIENT_SECRET"}
    with pytest.raises(RuntimeError) as exc:
        SapAiCoreConfig.from_env(kurang)
    assert "SAP_AI_CORE_CLIENT_SECRET" in str(exc.value)


def test_config_tanpa_deployment_id_ditolak_jenis():
    # env tak lengkap ditolak saat build (jujur) ...
    kurang = {k: v for k, v in ENV_LENGKAP.items() if k != "SAP_AI_CORE_DEPLOYMENT_ID_RPT"}
    with pytest.raises(RuntimeError) as exc:
        SapAiCoreConfig.from_env(kurang)
    assert "SAP_AI_CORE_DEPLOYMENT_ID_RPT" in str(exc.value)

    # ... dan id kosong ditolak saat dipakai (tanpa menyentuh jaringan)
    import dataclasses

    cfg = dataclasses.replace(SapAiCoreConfig.from_env(ENV_LENGKAP), deployment_rpt="")
    with pytest.raises(RuntimeError):
        cfg.deployment("rpt")
    with pytest.raises(SapAiCoreError):
        cfg.deployment("tidak-ada")


def test_build_caller_env_kosong_menolak(monkeypatch):
    for k in ENV_LENGKAP:
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(RuntimeError):
        build_llm_caller()
    with pytest.raises(RuntimeError):
        build_rpt_caller()


# --- token -----------------------------------------------------------------


def test_token_client_credentials_dan_di_cache():
    tp = TransportPalsu(_token_response(), _invoke_response("a"), _invoke_response("b"))
    client = SapAiCoreClient(SapAiCoreConfig.from_env(ENV_LENGKAP), transport=tp)

    client.invoke("prompt-1")
    client.invoke("prompt-2")

    # hanya SATU permintaan token untuk dua invoke (cache)
    assert sum(1 for u in tp.urls if u.endswith("/oauth/token")) == 1
    token_call = tp.calls[0]
    assert token_call["url"] == "https://auth.example/oauth/token"
    dasar = base64.b64encode(f"client-id-uji:{RAHASIA}".encode()).decode()
    assert token_call["headers"]["Authorization"] == f"Basic {dasar}"
    assert RAHASIA not in token_call["url"]
    assert RAHASIA.encode() not in (token_call["body"] or b"")
    # REGRESI (ditemukan uji live 11 Okt): tanpa grant_type di body, SAP
    # menjawab 400 invalid_request walau header Basic sudah benar.
    assert token_call["body"] == b"grant_type=client_credentials"
    assert token_call["headers"]["Content-Type"] == "application/x-www-form-urlencoded"


def test_token_diperbarui_setelah_kedaluwarsa():
    tp = TransportPalsu(
        _token_response(expires_in=3600),
        _invoke_response("a"),
        _token_response(expires_in=3600),
        _invoke_response("b"),
    )
    client = SapAiCoreClient(SapAiCoreConfig.from_env(ENV_LENGKAP), transport=tp)
    client.invoke("p1")
    # paksa lewat masa berlaku (deterministik; jangan bergantung resolusi jam)
    client._token_expiry = 0.0
    client.invoke("p2")
    assert sum(1 for u in tp.urls if u.endswith("/oauth/token")) == 2


# --- invoke (LLM) ----------------------------------------------------------


def test_invoke_bentuk_request_dan_parsing():
    tp = TransportPalsu(_token_response(), _invoke_response("jawaban-nyata"))
    client = SapAiCoreClient(SapAiCoreConfig.from_env(ENV_LENGKAP), transport=tp)

    hasil = client.invoke("Tolong jawab", max_tokens=64)

    assert hasil == "jawaban-nyata"
    panggilan = tp.calls[1]
    assert panggilan["method"] == "POST"
    assert panggilan["url"] == "https://api.example/v2/inference/deployments/dep-llm/invoke"
    assert panggilan["headers"]["Authorization"] == "Bearer tok-1"
    assert panggilan["headers"]["AI-Resource-Group"] == "default"
    body = _payload(panggilan)
    assert body["messages"] == [{"role": "user", "content": "Tolong jawab"}]
    assert body["max_tokens"] == 64
    assert body["anthropic_version"]  # gaya Bedrock, bukan OpenAI chat
    assert "model" not in body


def test_invoke_menggabungkan_beberapa_bagian_teks():
    tp = TransportPalsu(
        _token_response(),
        (
            200,
            json.dumps(
                {"content": [{"type": "text", "text": "bagian-1 "}, {"type": "text", "text": "bagian-2"}]}
            ).encode(),
        ),
    )
    client = SapAiCoreClient(SapAiCoreConfig.from_env(ENV_LENGKAP), transport=tp)
    assert client.invoke("p") == "bagian-1 bagian-2"


def test_invoke_http_error_membawa_status():
    tp = TransportPalsu(_token_response(), (429, b'{"detail":"throttled"}'))
    client = SapAiCoreClient(SapAiCoreConfig.from_env(ENV_LENGKAP), transport=tp)
    with pytest.raises(SapAiCoreError) as exc:
        client.invoke("p")
    assert exc.value.status_code == 429


def test_invoke_struktur_tak_dikenal_ditolak():
    tp = TransportPalsu(_token_response(), (200, b'{"bukan":"kontrak"}'))
    client = SapAiCoreClient(SapAiCoreConfig.from_env(ENV_LENGKAP), transport=tp)
    with pytest.raises(SapAiCoreError):
        client.invoke("p")


def test_pesan_error_tidak_membocorkan_rahasia():
    body = json.dumps({"detail": f"kredensial {RAHASIA} ditolak"}).encode()
    tp = TransportPalsu(_token_response(), (401, body))
    client = SapAiCoreClient(SapAiCoreConfig.from_env(ENV_LENGKAP), transport=tp)
    with pytest.raises(SapAiCoreError) as exc:
        client.invoke("p")
    assert RAHASIA not in str(exc.value)
    assert RAHASIA not in repr(exc.value)


def test_token_gagal_membawa_status_tanpa_bocor():
    body = json.dumps({"error": f"invalid_client {RAHASIA}"}).encode()
    tp = TransportPalsu((401, body))
    client = SapAiCoreClient(SapAiCoreConfig.from_env(ENV_LENGKAP), transport=tp)
    with pytest.raises(SapAiCoreError) as exc:
        client.invoke("p")
    assert exc.value.status_code == 401
    assert RAHASIA not in str(exc.value)


# --- predict (RPT-1.6) -----------------------------------------------------


def test_predict_membentuk_baris_query_dan_menjumlahkan():
    tp = TransportPalsu(_token_response(), _predict_response([100.0, 110.0, 120.0]))
    client = SapAiCoreClient(SapAiCoreConfig.from_env(ENV_LENGKAP), transport=tp)

    hasil = client.predict([400.0, 420.0, 380.0], horizon=3)

    panggilan = tp.calls[1]
    assert panggilan["url"] == "https://api.example/v2/inference/deployments/dep-rpt/predict"
    body = _payload(panggilan)
    kolom = body["prediction_config"]["target_columns"][0]
    assert kolom["name"] == DEFAULT_TARGET_COLUMN
    assert kolom["prediction_placeholder"] is None
    assert len(body["rows"]) == 6  # 3 riwayat + 3 query
    riwayat, query = body["rows"][:3], body["rows"][3:]
    assert all(r[DEFAULT_TARGET_COLUMN] is not None for r in riwayat)
    assert all(r[DEFAULT_TARGET_COLUMN] is None for r in query)
    assert hasil["predictions"] == [100.0, 110.0, 120.0]
    assert hasil["total_kg"] == 330.0
    assert 0.0 <= hasil["confidence"] <= 1.0


def test_predict_selisih_riwayat_dan_query_ditolak():
    tp = TransportPalsu(_token_response())
    client = SapAiCoreClient(SapAiCoreConfig.from_env(ENV_LENGKAP), transport=tp)
    with pytest.raises(SapAiCoreError):
        client.predict([], horizon=0)


def test_rpt_caller_menghasilkan_json_yang_dibaca_parser_forecast():
    """Pintu masuk produksi: prompt forecast → JSON yang diparse SAP-RPT path."""
    from app.ai_providers.forecast_client import _parse_sap_response

    tp = TransportPalsu(_token_response(), _predict_response([300.0, 310.0, 320.0, 330.0]))
    caller = build_rpt_caller(client=SapAiCoreClient(SapAiCoreConfig.from_env(ENV_LENGKAP), transport=tp))
    prompt = json.dumps(
        {"task": "forecast demand", "history_daily_kg": [280.0, 290.0], "horizon_days": 4}
    )

    teks = caller(prompt)

    parsed = _parse_sap_response(teks)
    assert parsed is not None
    qty, confidence = parsed
    assert qty == 1260.0  # 300+310+320+330 — dijumlahkan KODE, bukan model
    assert confidence is not None and 0.0 <= confidence <= 1.0


def test_rpt_caller_prompt_tak_terbaca_ditolak_tanpa_panggilan():
    tp = TransportPalsu(_token_response())
    caller = build_rpt_caller(client=SapAiCoreClient(SapAiCoreConfig.from_env(ENV_LENGKAP), transport=tp))
    with pytest.raises(SapAiCoreError):
        caller("ini bukan json")
    assert tp.calls == []  # tidak ada panggilan jaringan sama sekali


def test_llm_caller_meneruskan_prompt_apa_adanya():
    tp = TransportPalsu(_token_response(), _invoke_response("VERDICT: CONSISTENT"))
    caller = build_llm_caller(client=SapAiCoreClient(SapAiCoreConfig.from_env(ENV_LENGKAP), transport=tp))
    assert caller("judge ini") == "VERDICT: CONSISTENT"
    assert _payload(tp.calls[1])["messages"][0]["content"] == "judge ini"


def test_rpt_caller_lolos_run_forecast_label_jujur():
    """Rantai produksi: label SAP-RPT-1.6 hanya untuk response nyata."""
    from app.ai_providers.forecast_client import run_forecast

    tp = TransportPalsu(_token_response(), _predict_response([100.0, 200.0]))
    caller = build_rpt_caller(client=SapAiCoreClient(SapAiCoreConfig.from_env(ENV_LENGKAP), transport=tp))

    hasil = run_forecast([400.0, 420.0], horizon_days=2, sap_rpt=caller)

    assert hasil.method == "sap_rpt_1_6"
    assert hasil.provider == "SAP-RPT-1.6"
    assert hasil.forecast_qty_kg == 300.0
    assert hasil.fallback_used is False
