"""Unit test 4 tool supervisor — murni stdlib, transport di-mock, tanpa jaringan.

Dijalankan host-only (agent/ tidak ada di image backend):

    docker compose run --rm -v "<repo>/agent:/agent:ro" backend \
      pytest tests/test_supervisor_tools.py -q
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "agent"))

import tools  # noqa: E402


def _iso(hours: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


@pytest.fixture(autouse=True)
def _token(monkeypatch):
    monkeypatch.setenv("MEALCHAIN_API_TOKEN", "token-uji")
    monkeypatch.setenv("MEALCHAIN_API_URL", "http://backend:8000")


def test_tanpa_token_menolak_dengan_alasan_jelas(monkeypatch):
    monkeypatch.delenv("MEALCHAIN_API_TOKEN", raising=False)
    with pytest.raises(tools.ToolError, match="MEALCHAIN_API_TOKEN"):
        tools.get_supply_demand("Jakarta", "telur")


def test_supply_demand_memakai_angka_api(monkeypatch):
    def fake_request(path, method="GET", body=None):
        assert path == "/balance/Jakarta/telur"
        assert method == "GET"
        return {
            "location": "Jakarta",
            "commodity": "telur",
            "supply_kg": 314.2,
            "demand_kg": 1080.0,
            "shortage_kg": 765.8,
            "surplus_kg": 0.0,
            "status": "shortage",
            "data_state": "terukur",
        }

    monkeypatch.setattr(tools, "_request", fake_request)
    hasil = tools.get_supply_demand("Jakarta", "telur")
    assert hasil["kekurangan_kg"] == 765.8
    assert hasil["status"] == "shortage"
    assert hasil["sumber"] == "/balance/Jakarta/telur"


def test_safety_freshness_menghitung_gagal_dan_terburuk(monkeypatch):
    batches = {
        "batches": [
            {
                "id": "b1",
                "location": "Jakarta",
                "commodity": "telur",
                "quantity_kg": 120.0,
                "safety_status": "pass",
                "freshness_score": 0.86,
                "usable_until": _iso(72),
            },
            {
                "id": "b2",
                "location": "Jakarta",
                "commodity": "telur",
                "quantity_kg": 80.0,
                "safety_status": "fail",
                "freshness_score": 0.40,
                "usable_until": _iso(10),
            },
            {
                "id": "b3",
                "location": "Bogor",
                "commodity": "telur",
                "quantity_kg": 50.0,
                "safety_status": "pass",
                "freshness_score": 0.99,
                "usable_until": _iso(100),
            },
        ]
    }
    monkeypatch.setattr(
        tools,
        "_request",
        lambda path, method="GET", body=None: batches,
    )
    hasil = tools.get_safety_freshness("Jakarta", "telur")
    assert hasil["jumlah_batch"] == 2
    assert hasil["status_keamanan"] == {"pass": 1, "fail": 1}
    assert hasil["ada_yang_gagal"] is True
    assert hasil["kesegaran_terburuk"] == 0.4
    assert hasil["batch_kedaluwarsa_48_jam"] == 1
    assert hasil["total_kg"] == 200.0
    assert [b["id"] for b in hasil["batch_terburuk"]] == ["b2", "b1"]
    # batch Bogor tidak boleh ikut: tool menyaring lokasi
    assert all(b["id"] != "b3" for b in hasil["batch_terburuk"])


def test_biaya_dan_kelayakan_tidak_menghitung_ulang(monkeypatch):
    payload = {
        "decision_id": "d-1",
        "decision_type": "regional_balance",
        "status": "pending_approval",
        "source_location": "Cianjur",
        "target_location": "Jakarta",
        "commodity": "telur",
        "quantity_kg": 600.0,
        "safe_delivered_cost": 9200000.0,
        "cost_breakdown": {"purchase": "15720000", "logistics": "486000"},
        "supplier": {"name": "Koperasi Telur Cipanas Bersama", "reliability_score": 0.92},
        "safety": {"worst_status": "pass", "blocked": False, "batches_checked": 1},
        "verifier": {"verdict": "consistent", "verified_by": "verifier_agent"},
        "can_execute": False,
    }
    monkeypatch.setattr(
        tools, "_request", lambda path, method="GET", body=None: payload
    )
    hasil = tools.get_cost_eligibility("d-1")
    assert hasil["safe_delivered_cost"] == 9200000.0
    assert hasil["supplier"] == "Koperasi Telur Cipanas Bersama"
    assert hasil["can_execute"] is False
    assert hasil["safety_blocked"] is False
    assert hasil["sumber"].endswith("/approval-summary")


def test_bukti_menggabungkan_trace_dan_tanda_tangan(monkeypatch):
    def fake_request(path, method="GET", body=None):
        if path.endswith("/traces"):
            return {
                "steps": [
                    {
                        "step_name": "DETECT",
                        "tool_called": "demand.snapshot",
                        "step_at": "2026-10-17T13:26:01+00:00",
                    },
                    {
                        "step_name": "DECIDE",
                        "tool_called": "supply_balance.propose",
                        "step_at": "2026-10-17T13:28:01+00:00",
                    },
                ]
            }
        if path.endswith("/dossier"):
            return {
                "content_address": "mc1-abc",
                "signature": {"state": "signed", "algorithm": "ECDSA"},
                "verify": True,
            }
        raise AssertionError(f"path tak terduga: {path}")

    monkeypatch.setattr(tools, "_request", fake_request)
    hasil = tools.get_evidence_digest("d-1")
    assert hasil["langkah"] == ["DETECT", "DECIDE"]
    assert hasil["tanda_tangan"] == "signed"
    assert hasil["verifikasi_tanda_tangan"] is True
    assert hasil["alamat_konten"] == "mc1-abc"


def test_semua_batch_membaca_semua_halaman(monkeypatch):
    """`/batches` berplafon 500 (bawaan 50): batch di halaman berikutnya harus ikut.

    Tanpa paginasi, agen kesegaran/keamanan melaporkan "0 batch" untuk lokasi yang
    batch-nya kebetulan tidak masuk halaman pertama — terukur di demo: Jakarta/telur
    punya 3 batch tetapi agen melaporkan 0.
    """
    halaman = {
        "offset=0": (
            {
                "batches": [
                    {"id": "lain", "location": "Medan", "commodity": "ayam",
                     "quantity_kg": 10.0, "safety_status": "pass",
                     "freshness_score": 0.9, "usable_until": _iso(48)}
                ],
                "total": 2,
            }
        ),
        "offset=1": (
            {
                "batches": [
                    {"id": "jkt", "location": "Jakarta", "commodity": "telur",
                     "quantity_kg": 30.0, "safety_status": "pass",
                     "freshness_score": 0.8, "usable_until": _iso(48)}
                ],
                "total": 2,
            }
        ),
    }
    dilihat: list[str] = []

    def fake_request(path, method="GET", body=None):
        dilihat.append(path)
        for kunci, nilai in halaman.items():
            if kunci in path:
                return nilai
        raise AssertionError(f"path tak terduga: {path}")

    monkeypatch.setattr(tools, "_request", fake_request)
    hasil = tools.get_safety_freshness("Jakarta", "telur")
    assert hasil["jumlah_batch"] == 1, "batch Jakarta di halaman 2 harus terbaca"
    assert hasil["total_kg"] == 30.0
    assert len(dilihat) == 2, "tool harus memanggil halaman kedua"
    assert all("/batches?limit=500" in p for p in dilihat)


def test_error_api_tidak_dikarang(monkeypatch):
    def fake_request(path, method="GET", body=None):
        raise tools.ToolError("HTTP 503 pada /balance/Jakarta/telur")

    monkeypatch.setattr(tools, "_request", fake_request)
    with pytest.raises(tools.ToolError, match="503"):
        tools.get_supply_demand("Jakarta", "telur")
