"""Kontrak endpoint Demo Control sederhana: `POST /demo/agent/run` + `GET /demo/agent/last-run`.

Konteks: tab Demo Control disederhanakan (keputusan Roy 2026-10-19) — tanpa
Event 2/3, satu tombol "Jalankan agent" yang memakai lokasi SPPG akun sendiri,
dan satu blok bukti yang dibaca dari DB (bukan dari ingatan klien).

Yang diuji di sini adalah KONTRAK endpoint (guard peran, pemakaian lokasi akun,
pemetaan galat, bentuk bukti). Sejak keputusan pemilik 2026-10-19 endpoint ini
menilai PEMASOK yang memasok SPPG akun sendiri (`supplier_procurement`), jadi
yang diganti fake adalah `run_supplier_procurement` — provider nyata tidak
dipanggil dan tidak ada baris DB uji yang ditulis.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.test_actions import _drop_user, _login, _mk_user


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def pemakai():
    dibuat: list[str] = []

    def _buat(role: str, lokasi: str | None):
        user = _mk_user(role, lokasi)
        dibuat.append(user["email"])
        return user

    yield _buat
    for email in dibuat:
        _drop_user(email)


def _fake_outcome(**kwargs) -> dict:
    return {
        "decision_id": "00000000-0000-0000-0000-000000000002",
        "detect": {"commodity": kwargs.get("commodity")},
        "verifier": {"verdict": "PASS"},
        "forecast": {"forecast_qty_kg": 360.5},
        "supervisor": {
            "status": "narrated",
            "summary": "ringkasan uji",
            "provider": "primary:sap_ai_core",
            "fallback_used": False,
            "attempts": [],
        },
        "mode": "supplier_procurement",
        "suppliers": {"candidates": [], "ranked": [], "chosen": None},
        "decision_snapshot": {"status": "proposed", "approved": False},
        "trace_steps": ["DETECT", "VERIFY", "TRACE", "PREDICT", "OPTIMIZE",
                        "DECIDE", "SUPERVISE"],
    }


# --- guard peran -----------------------------------------------------------


def test_run_tanpa_token_ditolak_401(client):
    assert client.post("/demo/agent/run", json={}).status_code == 401


def test_run_bgn_monitor_ditolak_403(client, monitor_headers):
    resp = client.post("/demo/agent/run", json={}, headers=monitor_headers)
    assert resp.status_code == 403


def test_run_ahli_gizi_ditolak_403(client, pemakai):
    """Jalankan agent membuat keputusan operasional -> kepala SPPG saja."""
    gizi = pemakai("sppg_nutritionist", "Jakarta")
    resp = client.post("/demo/agent/run", json={}, headers=_login(client, gizi))
    assert resp.status_code == 403


# Catatan: "kepala SPPG tanpa lokasi" TIDAK bisa diuji lewat API karena constraint
# `check_user_role_location_scope` menolak baris seperti itu (sppg_head wajib
# punya location_id). Guard 400 di endpoint tetap dipertahankan sebagai
# pertahanan berlapis bila aturan peran itu berubah; yang dipaku tes adalah
# perilaku yang bisa terjadi di domain.


# --- jalur sukses ----------------------------------------------------------


def test_run_memakai_lokasi_akun_dan_komoditas_bawaan(client, monkeypatch, pemakai):
    dipanggil: dict = {}

    def _fake(commodity, target_location, **kwargs):
        dipanggil.update(commodity=commodity, target_location=target_location, **kwargs)
        return _fake_outcome(commodity=commodity)

    monkeypatch.setattr("app.api.demo.run_supplier_procurement", _fake)

    head = pemakai("sppg_head", "Jakarta")
    resp = client.post("/demo/agent/run", json={}, headers=_login(client, head))

    assert resp.status_code == 201, resp.text
    # Tanpa payload: beras + lokasi akun sendiri (bukan lokasi yang diketik klien).
    assert dipanggil == {"commodity": "beras", "target_location": "Jakarta", "ttl_minutes": 30}
    body = resp.json()
    assert body["target_location"] == "Jakarta"
    assert body["supervisor"]["status"] == "narrated"
    assert body["agent_review"]["status"] in {
        "disabled",
        "unavailable",
        "failed",
        "completed",
        "partial",
    }


def test_run_komoditas_dan_ttl_bisa_diubah(client, monkeypatch, pemakai):
    dipanggil: dict = {}

    def _fake(commodity, target_location, **kwargs):
        dipanggil.update(commodity=commodity, target_location=target_location, **kwargs)
        return _fake_outcome(commodity=commodity)

    monkeypatch.setattr("app.api.demo.run_supplier_procurement", _fake)

    head = pemakai("sppg_head", "Jakarta")
    resp = client.post(
        "/demo/agent/run",
        json={"commodity": "telur", "ttl_minutes": 45},
        headers=_login(client, head),
    )
    assert resp.status_code == 201, resp.text
    assert dipanggil == {"commodity": "telur", "target_location": "Jakarta", "ttl_minutes": 45}


def test_run_ttl_di_luar_batas_422(client, pemakai):
    head = pemakai("sppg_head", "Jakarta")
    resp = client.post(
        "/demo/agent/run", json={"ttl_minutes": 0}, headers=_login(client, head)
    )
    assert resp.status_code == 422


def test_run_tanpa_pemasok_layak_dijawab_409(client, monkeypatch, pemakai):
    def _fake(commodity, target_location, **kwargs):
        raise ValueError(
            f"tidak ada pemasok yang memasok {target_location} untuk {commodity}"
        )

    monkeypatch.setattr("app.api.demo.run_supplier_procurement", _fake)

    head = pemakai("sppg_head", "Jakarta")
    resp = client.post("/demo/agent/run", json={}, headers=_login(client, head))
    assert resp.status_code == 409
    assert "pemasok" in resp.json()["detail"].lower()


# --- pilihan komoditas ------------------------------------------------------


def test_commodities_tanpa_token_ditolak_401(client):
    assert client.get("/demo/agent/commodities").status_code == 401


def test_commodities_bgn_monitor_ditolak_403(client, monitor_headers):
    assert (
        client.get("/demo/agent/commodities", headers=monitor_headers).status_code
        == 403
    )


def test_commodities_daftar_dari_database(client, pemakai):
    """Dropdown hanya boleh menawarkan komoditas yang punya data di DB."""
    kepala = pemakai("sppg_head", "Jakarta")
    resp = client.get("/demo/agent/commodities", headers=_login(client, kepala))
    assert resp.status_code == 200, resp.text
    daftar = resp.json()["commodities"]
    assert isinstance(daftar, list) and daftar, "seed wajib menyediakan komoditas"
    assert daftar == sorted(daftar)
    assert "beras" in daftar


# --- bukti (last run) ------------------------------------------------------


def test_last_run_tanpa_token_ditolak_401(client):
    assert client.get("/demo/agent/last-run").status_code == 401


def test_last_run_bgn_monitor_ditolak_403(client, monitor_headers):
    assert client.get("/demo/agent/last-run", headers=monitor_headers).status_code == 403


def test_last_run_memakai_keepala_sppg(client, pemakai):
    head = pemakai("sppg_head", "Jakarta")
    resp = client.get("/demo/agent/last-run", headers=_login(client, head))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "found" in body
    if body["found"]:
        # Semua angka di blok bukti berasal dari DB: id keputusan nyata, langkah
        # nyata, dan narasi/provider yang benar-benar tercatat.
        uuid.UUID(body["decision_id"])
        assert body["steps"], "bukti tanpa langkah bukan bukti"
        assert "DETECT" in [s["step_name"] for s in body["steps"]]
        assert body["supervisor"]["status"] in {"narrated", "unavailable", "error", "missing"}
        assert body["status"] == "proposed"
        # Tujuh kartu agen di panel "Bukti agent": kunci tetap dan status
        # hanya dari baris review yang tersimpan.
        assert [a["key"] for a in body["agents"]] == [
            "supply",
            "demand",
            "freshness",
            "safety",
            "price",
            "logistics",
            "evidence",
        ]
        for agen in body["agents"]:
            assert agen["status"] in {
                "ok",
                "degraded",
                "error",
                "missing",
            }
            if agen["status"] == "missing":
                assert agen["duration_ms"] is None
    else:
        assert body.get("steps", []) == []
        assert body["agents"] == []

def test_last_run_memuat_bukti_pemasok(client, pemakai):
    """Bukti pengadaan: pemasok yang dinilai + kekurangan yang dipenuhi.

    Bentuknya wajib stabil walau belum ada putaran (`found: false`), supaya UI
    tidak perlu menebak kunci yang hilang.
    """
    kepala = pemakai("sppg_head", "Jakarta")
    resp = client.get("/demo/agent/last-run", headers=_login(client, kepala))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "supplier" in body and "supply_gap" in body and "mode" in body
    if not body["found"]:
        assert body["supplier"] is None
        return
    if body["mode"] == "supplier_procurement":
        # Angka bukti berasal dari trace DB, bukan dihitung ulang endpoint.
        assert body["supplier"]["name"], "keputusan pengadaan wajib punya pemasok"
        assert body["supply_gap"]["gap_kg"] is not None
        assert body["source_location"] is None

