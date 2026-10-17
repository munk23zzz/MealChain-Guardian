"""Papan status integrasi (PLAN-012 · 2026-10-17) — kontrak KEJUJURAN.

Yang dipaku di sini bukan tampilan, tetapi aturan bukti:

1. Tanpa token → **401**. Read-only bukan berarti publik.
2. Setiap komponen wajib membawa `id`, `name`, `category`, `category_label`,
   `evidence` (apa yang diperiksa), `artifact` (sumber), dan `checked_at`.
3. Kategori hanya boleh dari daftar tertutup, dan **tidak boleh ada
   `operational`/`probe_passed`** karena endpoint ini tidak menjalankan probe
   apa pun (`probes_run == 0`). Label hijau tanpa probe = kesalahan yang justru
   ingin dicegah PLAN-012.
4. Kategori harus MENGIKUTI KENYATAAN env, bukan konstanta: ARN AgentCore kosong
   berarti "artefak siap" (bukan hijau), ARN terisi berarti "terkonfigurasi";
   Memory tanpa id berarti "tidak tersedia". Kalau papan ini hardcode, poin 4
   gagal — dan itu memang tujuannya.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

ALLOWED = {
    "configured",
    "provisioned",
    "contract_tested",
    "artifacts_ready",
    "fail_closed",
    "unavailable",
    "not_started",
}


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _payload(client, headers) -> dict:
    resp = client.get("/integrations/status", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _komponen(payload: dict, cid: str) -> dict:
    for item in payload["components"]:
        if item["id"] == cid:
            return item
    raise AssertionError(f"komponen {cid} tidak ada di payload")


def test_tanpa_token_ditolak_401(client):
    assert client.get("/integrations/status").status_code == 401


def test_setiap_komponen_membawa_bukti_dan_waktu(client, monitor_headers):
    payload = _payload(client, monitor_headers)
    assert payload["components"], "papan tidak boleh kosong"
    for item in payload["components"]:
        wajib = (
            "id",
            "name",
            "category",
            "category_label",
            "evidence",
            "artifact",
            "checked_at",
        )
        for kunci in wajib:
            assert item.get(kunci), f"{item.get('id')}: kolom {kunci} kosong"
        assert item["category"] in ALLOWED, item["category"]
        # checked_at harus ISO yang bisa diurai
        assert "T" in item["checked_at"]


def test_tidak_ada_label_hijau_tanpa_probe(client, monitor_headers):
    payload = _payload(client, monitor_headers)
    # Endpoint ini sengaja tanpa probe jaringan → tidak boleh ada klaim probe.
    assert payload["probes_run"] == 0
    kategori = {item["category"] for item in payload["components"]}
    assert "operational" not in kategori
    assert "probe_passed" not in kategori
    assert set(payload["categories"]) == ALLOWED


def test_agentcore_runtime_mengikuti_env_arn(client, monitor_headers, monkeypatch):
    monkeypatch.delenv("AGENTCORE_RUNTIME_ARN", raising=False)
    kosong = _komponen(_payload(client, monitor_headers), "agentcore_runtime")
    assert kosong["category"] == "artifacts_ready"
    assert "kosong" in kosong["evidence"]

    monkeypatch.setenv(
        "AGENTCORE_RUNTIME_ARN", "arn:aws:bedrock-agentcore:ap-southeast-1:1:runtime/x"
    )
    terisi = _komponen(_payload(client, monitor_headers), "agentcore_runtime")
    assert terisi["category"] == "configured"


def test_agentcore_memory_mengikuti_env(client, monitor_headers, monkeypatch):
    monkeypatch.delenv("AGENTCORE_MEMORY_ID", raising=False)
    mem = _komponen(_payload(client, monitor_headers), "agentcore_memory")
    assert mem["category"] == "unavailable"

    monkeypatch.setenv("AGENTCORE_MEMORY_ID", "mem-0123456789abcdef")
    memory = _komponen(_payload(client, monitor_headers), "agentcore_memory")
    assert memory["category"] == "provisioned"
    # Provisioned BUKAN berarti dipakai aplikasi — catatannya harus jujur.
    assert "adapter" in memory["note"].lower()


def test_sap_ai_core_mengikuti_env(client, monitor_headers, monkeypatch):
    monkeypatch.delenv("SAP_AI_CORE_CLIENT_ID", raising=False)
    assert _komponen(_payload(client, monitor_headers), "sap_ai_core")["category"] == "unavailable"

    monkeypatch.setenv("SAP_AI_CORE_CLIENT_ID", "client-id-demo")
    sap = _komponen(_payload(client, monitor_headers), "sap_ai_core")
    assert sap["category"] == "contract_tested"


def test_komponen_tanpa_implementasi_berbunyi_belum_dimulai(client, monitor_headers):
    payload = _payload(client, monitor_headers)
    mcp = _komponen(payload, "aws_for_sap_mcp")
    assert mcp["category"] == "not_started"
    gateway = _komponen(payload, "agentcore_gateway")
    assert gateway["category"] in {"not_started", "configured"}
