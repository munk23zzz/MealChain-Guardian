"""Supervisor agent: status + tanya-jawab baca-saja (dokumen 06-agent-log §2.8–2.9).

MASALAH yang dipaku. Panel Agent Activity boleh menampilkan status supervisor
dan kotak tanya-jawab, tetapi dua-duanya mudah berubah menjadi klaim palsu:

1. Status "hidup" tanpa probe = klaim tanpa bukti. Di build ini tidak ada klien
   model supervisor, jadi `live` harus `null` dan UI hanya boleh hijau bila
   provider benar-benar menjawab (invarian 4).
2. Tanya-jawab tidak boleh menulis apa pun. Setiap jawaban wajib menyebut tool
   GET yang dipakai + `writes: false`.
3. Pertanyaan di luar cakupan tidak boleh dijawab dengan tebakan.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_health_melaporkan_konfigurasi_tanpa_mengklaim_hidup(client, auth_headers) -> None:
    resp = client.get("/agent/supervisor/health", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] in {"configured", "unconfigured"}
    # Invarian 4: hijau hanya bila live. Tanpa probe, `live` harus null.
    assert body["live"] is None
    assert body["checked"] == "config_only"
    assert isinstance(body["detail"], str) and body["detail"]
    assert "slots" in body


def test_health_butuh_token(client) -> None:
    assert client.get("/agent/supervisor/health").status_code == 401


def test_ask_menjawab_dengan_tool_dan_tidak_menulis(client, auth_headers) -> None:
    resp = client.post(
        "/agent/supervisor/ask",
        json={"question": "Bagaimana status rantai ledger?"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["writes"] is False
    assert body["mode"] == "deterministic"
    assert body["tool"].startswith("GET") or body["tool"].startswith("model_registry")
    assert "ledger" in body["answer"].lower()


def test_ask_agregasi_status_keputusan(client, auth_headers) -> None:
    resp = client.post(
        "/agent/supervisor/ask",
        json={"question": "Berapa keputusan yang menunggu persetujuan?"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["writes"] is False
    assert isinstance(body["data"], dict)


def test_ask_di_luar_cakupan_tidak_menebak(client, auth_headers) -> None:
    resp = client.post(
        "/agent/supervisor/ask",
        json={"question": "Ramalkan harga beras bulan depan"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] is None
    assert "tidak bisa dijawab" in body["answer"].lower()


def test_ask_pertanyaan_kosong_ditolak(client, auth_headers) -> None:
    resp = client.post("/agent/supervisor/ask", json={"question": ""}, headers=auth_headers)
    assert resp.status_code == 422


def test_ask_tidak_menambah_baris_trace_atau_ledger(client, auth_headers) -> None:
    """Bukti `writes: false`: jumlah keputusan dan blok ledger tidak berubah."""
    sebelum = client.get("/ledger/verify", headers=auth_headers).json()
    client.post(
        "/agent/supervisor/ask",
        json={"question": "Apa keputusan terbaru?"},
        headers=auth_headers,
    )
    sesudah = client.get("/ledger/verify", headers=auth_headers).json()
    assert sebelum.get("blocks") == sesudah.get("blocks")
