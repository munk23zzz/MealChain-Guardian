"""Jejak 10 tahap pipeline: lengkap dan jujur (29 Okt 2026).

Kontrak yang diuji di sini — semuanya berasal dari keluhan nyata "banyak data
tidak terdeteksi di 10 tahap, terutama lewat agent supervisor":

1. Prompt supervisor MEMUAT `decision_id` (dan id entitas terkait). Tool
   supervisor (`agent/tools.py::get_cost_eligibility`, `get_evidence_digest`)
   hanya bisa dipanggil dengan id keputusan; tanpa id di prompt, agen menjawab
   "saya memerlukan decision_id" — narasi berisi pertanyaan balik ke manusia,
   bukan angka.
2. Tahap SUPERVISE SELALU meninggalkan baris, termasuk saat provider mati
   (`status=unavailable`/`error`). Baris yang hilang membuat panel 10 tahap
   tidak bisa membedakan "tidak diawasi" dari "tidak pernah jalan".
3. Baris TRACE menyebut jumlah langkah NYATA (`steps_recorded`), bukan angka
   hardcode 6 — angka jejak yang dikarang membuat audit tidak bisa dipercaya.
4. Putaran pengadaan menulis SEMUA tahap yang dijalankannya (DETECT, VERIFY,
   TRACE, PREDICT, OPTIMIZE, ANALYZE, DECIDE, SUPERVISE).

Provider model TIDAK dipanggil: seluruh langkah model diganti stub, jadi tes
ini tidak membutuhkan jaringan/kredensial dan hasilnya deterministik. WAJIB
dijalankan pada klon DB (`bash scripts/f6-gate.sh backend/tests/<berkas>`),
bukan DB demo.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from app.services.supervisor_client import SupervisorResult, _build_prompt
from tests.dsn import DSN_ASYNC

DB_URL = DSN_ASYNC.replace("+asyncpg", "+psycopg")

TAHAP_PENGADAAN = (
    "DETECT",
    "VERIFY",
    "TRACE",
    "PREDICT",
    "OPTIMIZE",
    "ANALYZE",
    "DECIDE",
    "SUPERVISE",
)


# ---------------------------------------------------------------------------
# bantu
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _bersihkan(decision_id: str | None) -> None:
    """Hapus baris tes ini saja (trace ikut CASCADE dari decisions)."""
    if decision_id is None:
        return
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM decisions WHERE id = CAST(:d AS uuid)"),
                {"d": decision_id},
            )
    finally:
        engine.dispose()


def _baris_jejak(decision_id: str) -> list[dict]:
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            rows = (
                conn.execute(
                    text(
                        "SELECT step_name, tool_called, output_summary "
                        "FROM agent_traces WHERE decision_id = CAST(:d AS uuid) "
                        "ORDER BY step_at ASC, id ASC"
                    ),
                    {"d": decision_id},
                )
                .mappings()
                .all()
            )
            return [dict(r) for r in rows]
    finally:
        engine.dispose()


def _forecast_stub():
    return SimpleNamespace(
        qty_kg="700",
        method="statistical_fallback",
        source="statistical",
        fallback_used=False,
        sample_count=14,
        cache_hit=False,
        attempts=[],
        reason=None,
    )


def _verifier_stub(verdict: str = "CONSISTENT"):
    return SimpleNamespace(
        verdict=verdict,
        reason="bukti konsisten (stub)",
        provider=None,
        fallback_used=False,
        attempts=[],
    )


def _hipotesis_stub():
    return SimpleNamespace(
        status="ok",
        hypothesis="kekurangan terjadi karena pasokan lokal menipis (stub)",
        recommendation="tambah pasokan dari pemasok terdekat (stub)",
        confidence="0.5",
        provider=None,
        fallback_used=False,
        attempts=[],
        ungrounded_numbers=(),
    )


def _narasi_stub():
    """Narasi per tahap (DETECT/VERIFY/TRACE/PREDICT/OPTIMIZE/DECIDE)."""
    return SimpleNamespace(
        status="analyzed",
        hypothesis="narasi tahap pengadaan (stub)",
        recommendation=None,
        confidence="0.5",
        provider=None,
        fallback_used=False,
        attempts=[],
        ungrounded_numbers=(),
    )


# ---------------------------------------------------------------------------
# 1. prompt supervisor membawa id keputusan
# ---------------------------------------------------------------------------


def test_prompt_supervisor_membawa_decision_id_dan_id_entitas():
    prompt = _build_prompt(
        {
            "decision_id": "11111111-2222-3333-4444-555555555555",
            "supplier_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "batch_ids": ["bbbbbbbb-cccc-dddd-eeee-ffffffffffff"],
            "commodity": "telur",
            "target_location": "Jakarta",
        }
    )
    isi = json.loads(prompt)
    assert isi["decision_id"] == "11111111-2222-3333-4444-555555555555"
    assert isi["supplier_id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert isi["batch_ids"] == ["bbbbbbbb-cccc-dddd-eeee-ffffffffffff"]
    # Instruksi memakai tool, bukan bertanya balik ke manusia.
    assert "get_cost_eligibility" in isi["instruksi"]
    assert "get_evidence_digest" in isi["instruksi"]


def test_prompt_supervisor_tanpa_decision_id_tidak_mengarang_id():
    isi = json.loads(_build_prompt({"commodity": "telur"}))
    assert isi["decision_id"] is None


# ---------------------------------------------------------------------------
# 2 + 3. Event 1: SUPERVISE tetap tercatat saat provider mati
# ---------------------------------------------------------------------------


def test_event1_supervise_tetap_tercatat_saat_tanpa_provider(client, monkeypatch):
    from app.services import event1_orchestrator

    def supervisor_mati(_ctx):
        return SupervisorResult(status="unavailable", attempts=[])

    monkeypatch.setattr(event1_orchestrator, "run_supervisor", supervisor_mati)

    outcome = event1_orchestrator.run_event1(commodity="telur", target_location="Jakarta")
    try:
        baris = _baris_jejak(outcome["decision_id"])
        tahap = [b["step_name"] for b in baris]
        assert "SUPERVISE" in tahap, (
            "tahap SUPERVISE hilang saat provider mati — panel 10 tahap "
            "kehilangan bukti bahwa langkahnya memang dijalankan"
        )
        supervise = next(b for b in baris if b["step_name"] == "SUPERVISE")
        assert supervise["tool_called"] == "supervisor.unavailable"
        keluaran = supervise["output_summary"] or {}
        assert keluaran.get("status") == "unavailable"
        assert keluaran.get("summary") is None
        assert "note" in keluaran

        trace = next(b for b in baris if b["step_name"] == "TRACE")
        assert (trace["output_summary"] or {}).get("steps_recorded") == len(baris)
    finally:
        _bersihkan(outcome.get("decision_id"))


# ---------------------------------------------------------------------------
# 4. Pengadaan pemasok: seluruh tahap yang dijalankan punya baris
# ---------------------------------------------------------------------------


def test_pengadaan_menulis_semua_tahap_yang_dijalankan(client, monkeypatch):
    from app.services import demo_procurement_orchestrator as ork

    monkeypatch.setattr(ork, "run_verifier", lambda _ctx, **_kw: _verifier_stub())
    monkeypatch.setattr(ork, "run_hypothesis", lambda _ctx: _hipotesis_stub())
    monkeypatch.setattr(ork, "narasi_tahap", lambda _tahap, _fakta: _narasi_stub())
    monkeypatch.setattr(ork, "forecast_kebutuhan", _forecast_stub_async())
    monkeypatch.setattr(
        ork,
        "run_supervisor",
        lambda _ctx: SupervisorResult(
            status="narrated", summary="ringkasan uji", provider="primary:uji"
        ),
    )

    hasil = ork.run_supplier_procurement("telur", "Jakarta", ttl_minutes=30)
    decision_id = hasil["decision_id"]
    try:
        baris = _baris_jejak(decision_id)
        tahap = [b["step_name"] for b in baris]
        for nama in TAHAP_PENGADAAN:
            assert nama in tahap, f"tahap {nama} tidak tercatat (dapat: {tahap})"
        # ACT bukan bagian putaran ini (dieksekusi setelah approval manusia) —
        # tidak boleh dikarang di sini.
        assert "ACT" not in tahap

        trace = next(b for b in baris if b["step_name"] == "TRACE")
        assert (trace["output_summary"] or {}).get("steps_recorded") == len(baris)

        supervise = next(b for b in baris if b["step_name"] == "SUPERVISE")
        assert supervise["tool_called"] == "supervisor.narration"
        assert (supervise["output_summary"] or {}).get("decision_id") == decision_id
    finally:
        _bersihkan(decision_id)


def test_pengadaan_supervise_gagal_tetap_punya_baris(client, monkeypatch):
    from app.services import demo_procurement_orchestrator as ork

    monkeypatch.setattr(ork, "run_verifier", lambda _ctx, **_kw: _verifier_stub())
    monkeypatch.setattr(ork, "run_hypothesis", lambda _ctx: _hipotesis_stub())
    monkeypatch.setattr(ork, "narasi_tahap", lambda _tahap, _fakta: _narasi_stub())
    monkeypatch.setattr(ork, "forecast_kebutuhan", _forecast_stub_async())
    monkeypatch.setattr(
        ork,
        "run_supervisor",
        lambda _ctx: SupervisorResult(status="error", attempts=[]),
    )

    hasil = ork.run_supplier_procurement("telur", "Jakarta", ttl_minutes=30)
    decision_id = hasil["decision_id"]
    try:
        baris = _baris_jejak(decision_id)
        supervise = next(b for b in baris if b["step_name"] == "SUPERVISE")
        assert supervise["tool_called"] == "supervisor.error"
        assert (supervise["output_summary"] or {}).get("status") == "error"
    finally:
        _bersihkan(decision_id)


def _forecast_stub_async():
    """`forecast_kebutuhan` dipanggil dengan `await` → stub harus async."""

    async def _stub(*_args, **_kwargs):
        return _forecast_stub()

    return _stub
