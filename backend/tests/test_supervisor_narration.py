"""SUPERVISE step — narasi supervisor dari chain model env (permintaan Roy).

Kontrak:
- supervisor naratif = langkah TERAKHIR, SETELAH verifier (angka
  safety-critical sudah terkunci; narasi tidak pernah mengubah verdict,
  rekomendasi, cost, atau angka apa pun)
- label provider jujur (`primary:bedrock`, `fallback_1:inferhub`, ...),
  fallback_used sesuai attempt aktual
- model gagal/EOF/kosong env → status dijelaskan apa adanya
  (`unavailable`/`error`), decision tetap lahir — supervisor tidak kritikal
- verifier TIDAK tersentuh narasi (attempts verifier milik verifier)
"""

import pytest
from sqlalchemy import create_engine, text

from app.ai_providers import ai_provider_chain as chain_mod
from tests.dsn import DSN_ASYNC  # DSN mengikuti DATABASE_URL

DB_URL = (
    DSN_ASYNC
).replace("+asyncpg", "+psycopg")


def _cleanup(decision_id: str | None) -> None:
    if decision_id is None:
        return
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM agent_traces WHERE decision_id = :d"),
                {"d": decision_id},
            )
            conn.execute(
                text("DELETE FROM decisions WHERE id = :d"), {"d": decision_id}
            )
    finally:
        engine.dispose()


def _stub_chain(*responses):
    """Chain stub: callable → teks, atau Exception untuk slot mati.

    Panjang chain tidak dibatasi 3 slot: label dihasilkan sebagai
    primary/fallback_N supaya bisa menguji chain panjang (uji audit 2026-10-11).
    """
    callables = []
    for resp in responses:
        if isinstance(resp, Exception):
            def dead(prompt: str, _e=resp):
                raise _e

            callables.append(dead)
        else:
            def ok(prompt: str, _t=resp):
                return _t

            callables.append(ok)
    kinds = ["bedrock", "inferhub", "inferhub", "inferhub"][: len(callables)]
    labels = ["primary"] + [f"fallback_{i}" for i in range(1, len(callables))]
    return [
        (f"{label}:{kind}", fn, kind)
        for label, kind, fn in zip(labels, kinds, callables)
    ]

NARRATION_OK = (
    '{"ringkasan": "Distribusi telur Bogor ke Jakarta layak dieksekusi '
    'setelah approval ganda.", "confidence": 0.8}'
)


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


def _trace_rows(decision_id: str) -> list[dict]:
    """Baris jejak keputusan ini (untuk memeriksa isi tahap SUPERVISE)."""
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


def test_supervise_step_narrates_with_honest_labels(client, monkeypatch):
    from app.services.event1_orchestrator import run_event1

    monkeypatch.setattr(
        chain_mod,
        "build_default_callers",
        lambda agent: _stub_chain(NARRATION_OK)
        if agent == "supervisor"
        else [],
    )
    outcome = run_event1(commodity="telur", target_location="Jakarta")
    try:
        sup = outcome["supervisor"]
        assert sup["status"] == "narrated"
        assert sup["provider"] == "primary:bedrock"
        assert sup["fallback_used"] is False
        assert "Bogor" in sup["summary"] or "Jakarta" in sup["summary"]
        # SUPERVISE = langkah terakhir
        assert outcome["trace_steps"][-1] == "SUPERVISE"
        # verifier tidak tersentuh narasi
        assert outcome["verifier"]["attempts"] == []
    finally:
        _cleanup(outcome.get("decision_id"))


def test_supervise_falls_back_to_second_model(client, monkeypatch):
    from app.services.event1_orchestrator import run_event1

    monkeypatch.setattr(
        chain_mod,
        "build_default_callers",
        lambda agent: _stub_chain(RuntimeError("primary mati"), NARRATION_OK)
        if agent == "supervisor"
        else [],
    )
    outcome = run_event1(commodity="telur", target_location="Jakarta")
    try:
        sup = outcome["supervisor"]
        assert sup["status"] == "narrated"
        assert sup["provider"] == "fallback_1:inferhub"
        assert sup["fallback_used"] is True
        assert len(sup["attempts"]) == 2
    finally:
        _cleanup(outcome.get("decision_id"))


def test_supervise_unavailable_recorded_honestly(client):
    """Tanpa model: SUPERVISE jujur unavailable; decision tetap lahir."""
    from app.services.event1_orchestrator import run_event1

    outcome = run_event1(commodity="telur", target_location="Jakarta")
    try:
        sup = outcome["supervisor"]
        assert sup["status"] == "unavailable"
        assert sup["attempts"] == []
        # 29 Okt 2026: tahap SUPERVISE SELALU meninggalkan baris — kegagalan
        # narasi adalah fakta yang harus terbaca di panel 10 tahap, bukan
        # tahap yang lenyap (dulu: `"SUPERVISE" not in trace_steps`).
        assert "SUPERVISE" in outcome["trace_steps"]
        rows = _trace_rows(outcome["decision_id"])
        supervise = next(r for r in rows if r["step_name"] == "SUPERVISE")
        assert supervise["tool_called"] == "supervisor.unavailable"
        assert (supervise["output_summary"] or {})["status"] == "unavailable"
        assert outcome["decision_snapshot"]["status"] in {
            "proposed",
            "pending_approval",
        }
    finally:
        _cleanup(outcome.get("decision_id"))


def test_supervise_chain_panjang_label_jujur(client, monkeypatch):
    """Pemenang slot ke-4 tidak boleh dilaporkan sebagai slot pertama.

    Uji audit 2026-10-11: supervisor_client memakai peta 3 entri
    {"primary": 0, "fallback_1": 1, "fallback_2": 2} dan `.get(..., 0)`, jadi
    pemenang `fallback_3` dipetakan ke indeks 0 dan dilaporkan sebagai
    "primary:bedrock" — label yang salah untuk langkah yang mengklaim
    provider (aturan anti-fabricate). resilience.py sudah punya helper
    `provider_slot_index` yang benar.
    """
    from app.services.event1_orchestrator import run_event1

    monkeypatch.setattr(
        chain_mod,
        "build_default_callers",
        lambda agent: _stub_chain(
            RuntimeError("primary mati"),
            RuntimeError("fallback_1 mati"),
            RuntimeError("fallback_2 mati"),
            NARRATION_OK,
        )
        if agent == "supervisor"
        else [],
    )
    outcome = run_event1(commodity="telur", target_location="Jakarta")
    try:
        sup = outcome["supervisor"]
        assert sup["status"] == "narrated"
        assert sup["provider"] == "fallback_3:inferhub"
        assert sup["fallback_used"] is True
        assert len(sup["attempts"]) == 4
    finally:
        _cleanup(outcome.get("decision_id"))
