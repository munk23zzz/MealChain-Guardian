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
from sqlalchemy import create_engine, text

from app.main import app
from tests.dsn import DSN_SYNC
from tests.test_actions import _drop_user, _login, _mk_user

#: Status keputusan yang sah — cermin CHECK `decisions_status_check` di DB.
STATUS_KEPUTUSAN = {
    "proposed",
    "verifier_flagged",
    "pending_approval",
    "approved",
    "rejected",
    "executed",
    "review_only",
}


def _status_keputusan(decision_id: str) -> str:
    """Status baris DB untuk satu keputusan (pembanding `last-run`, bukan angka karangan)."""
    engine = create_engine(DSN_SYNC)
    try:
        with engine.connect() as conn:
            return str(
                conn.execute(
                    text("SELECT status FROM decisions WHERE id = CAST(:id AS uuid)"),
                    {"id": decision_id},
                ).scalar_one()
            )
    finally:
        engine.dispose()


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
        # Status TIDAK dipaku `proposed`: putaran yang sama bisa sudah disetujui
        # sesudah dibuat (suite ini memang menyetujui beberapa putaran), dan
        # endpoint wajib melaporkan status TERKINI. Yang diuji: angkanya sama
        # dengan baris DB-nya — bukan angka karangan.
        assert body["status"] == _status_keputusan(body["decision_id"])
        assert body["status"] in STATUS_KEPUTUSAN
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


def test_last_run_hanya_putaran_pipeline(client, pemakai):
    """Bukti "putaran agent" wajib berasal dari pipeline penuh, bukan baris seed.

    Regresi (gerbang 21 Okt 2026): endpoint jatuh ke "keputusan dengan DETECT
    terakhir", sehingga keputusan hasil template/seed — yang juga menulis
    DETECT/DECIDE/ACT — dilaporkan sebagai putaran agent. Akibatnya `status`
    bukan `proposed` dan `supply_gap.gap_kg` kosong padahal `mode` pengadaan.

    Ciri putaran NYATA: ada langkah pipeline penuh (PREDICT/OPTIMIZE/SUPERVISE)
    yang ditulis tanpa `agent_name` (baris review worker memakai nama agen).
    """
    kepala = pemakai("sppg_head", "Jakarta")
    resp = client.get("/demo/agent/last-run", headers=_login(client, kepala))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    if not body["found"]:
        return
    nama = {langkah["step_name"] for langkah in body["steps"]}
    assert {"DETECT", "DECIDE"} <= nama, (
        "bukti putaran agent tanpa DETECT+DECIDE: " + ", ".join(sorted(nama))
    )
    assert nama & {"PREDICT", "OPTIMIZE", "SUPERVISE"}, (
        "bukti putaran agent tanpa satu pun langkah pipeline: "
        + ", ".join(sorted(nama))
    )
    # Catatan: pengecualian salinan 4 kasus skrip (`decisions.demo_case` terisi)
    # diuji lewat kode endpoint (filter `demo_case IS NULL`), bukan lewat payload —
    # payload sengaja tidak membuka kolom penyemai ke UI.


def test_last_run_memilih_putaran_pipeline_penuh(client, pemakai):
    """Kasus POSITIF: putaran pipeline lengkap benar-benar terpilih.

    Tanpa tes ini, filter "jejak pipeline lengkap" bisa lolos hanya karena
    endpoint selalu menjawab `found: false` (baris semai tidak memenuhi syarat) —
    panel Demo Control lalu diam-diam tidak pernah menampilkan bukti.
    """
    kunci = uuid.uuid5(uuid.NAMESPACE_URL, "mealchain:uji-last-run-pipeline")
    langkah = ("DETECT", "VERIFY", "TRACE", "PREDICT", "OPTIMIZE", "DECIDE", "SUPERVISE")
    engine = create_engine(DSN_SYNC)

    def _bersihkan(conn) -> None:
        # FK agent_traces → decisions ON DELETE CASCADE, jadi satu DELETE cukup.
        conn.execute(
            text("DELETE FROM decisions WHERE id = CAST(:id AS uuid)"), {"id": str(kunci)}
        )

    try:
        with engine.begin() as conn:
            _bersihkan(conn)
            conn.execute(
                text(
                    "INSERT INTO decisions (id, decision_type, status, proposed_by, "
                    "expires_at, created_at, origin) VALUES (CAST(:id AS uuid), "
                    "'supplier_procurement', 'proposed', 'supervisor_agent', "
                    "now() + interval '1 hour', now(), 'demo')"
                ),
                {"id": str(kunci)},
            )
            for nama in langkah:
                conn.execute(
                    text(
                        "INSERT INTO agent_traces (decision_id, step_name, tool_called, step_at) "
                        "VALUES (CAST(:id AS uuid), :step, :tool, now())"
                    ),
                    {"id": str(kunci), "step": nama, "tool": f"uji.{nama.lower()}"},
                )

        kepala = pemakai("sppg_head", "Jakarta")
        resp = client.get("/demo/agent/last-run", headers=_login(client, kepala))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["found"] is True, "putaran pipeline lengkap tidak terdeteksi"
        assert body["decision_id"] == str(kunci), "putaran pipeline terbaru wajib menang"
        assert body["mode"] == "supplier_procurement"
        assert {s["step_name"] for s in body["steps"]} == set(langkah)
    finally:
        with engine.begin() as conn:
            _bersihkan(conn)
        engine.dispose()

