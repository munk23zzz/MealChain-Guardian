"""Atribusi jejak agen: `agent_name` wajib = kunci tampilan "Kualitas per agen".

Bug yang dikunci di sini (terukur 4 Nov 2026): papan "Kualitas per agen" di UI
menampilkan 0 "tercatat" untuk semua agen. Penyebabnya bukan UI — baris
`agent_traces` hasil semai/pipeline menulis nama kelas (`detection_agent`,
`sap_agent`, `worker.detect`, `orchestrator`) atau `NULL`, sedangkan
`frontend/lib/agent-quality.ts` hanya menghitung sembilan kunci
`supply..verifier` (kontrak `SWARM_AGENTS`). Tidak ada baris yang cocok, jadi
tidak ada angka yang bisa dihitung.

Kontrak sekarang: penulis jejak di backend menormalkan nama lewat
`app.services.agent_attribution` (`agent_key`), sehingga nama apa pun yang
tersimpan adalah salah satu dari sembilan kunci itu — tanpa mengubah frontend.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pytest
from sqlalchemy import create_engine as create_sync_engine
from sqlalchemy import select, text

from app.core.config import settings
from app.db import create_engine, create_session_maker
from app.services.agent_attribution import (
    AGENT_KEYS,
    agent_key,
    agent_key_for,
    normalize_agent_name,
)
from tests.dsn import DSN_SYNC

#: Tahap yang boleh ditulis `trace_persistence._VALID_STEPS`.
VALID_STEPS = (
    "DETECT",
    "VERIFY",
    "TRACE",
    "PREDICT",
    "OPTIMIZE",
    "ANALYZE",
    "DECIDE",
    "SUPERVISE",
    "ACT",
    "LEARN",
)


# ── kontrak nama (murni, tanpa DB) ──────────────────────────────────────────


def test_sembilan_kunci_kontrak() -> None:
    assert AGENT_KEYS == (
        "supply",
        "demand",
        "freshness",
        "safety",
        "price",
        "logistics",
        "evidence",
        "supervisor",
        "verifier",
    )


def test_kunci_backend_sama_dengan_kontrak_frontend() -> None:
    """`frontend/lib/agent-swarm.ts` adalah sumber kebenaran kunci tampilan.

    Tes ini gagal bila backend menambah/menghapus kunci tanpa menyelaraskan
    kontrak tampilan (atau sebaliknya) — persis kelas bug yang membuat papan
    menampilkan 0. Dilewati bila berkas frontend tidak ter-mount (image backend
    hanya memuat `backend/`).
    """
    sumber = Path(__file__).resolve().parents[2] / "frontend" / "lib" / "agent-swarm.ts"
    if not sumber.is_file():
        pytest.skip("frontend/lib/agent-swarm.ts tidak tersedia di image ini")
    isi = sumber.read_text(encoding="utf-8")
    blok = isi.split("export const SWARM_AGENTS", 1)[-1].split("];", 1)[0]
    kunci = tuple(re.findall(r'key:\s*"([a-z_]+)"', blok))
    assert kunci == AGENT_KEYS


def test_setiap_tahap_pipeline_punya_agen_kontrak() -> None:
    """Tidak ada tahap yang tersimpan dengan `agent_name` kosong lagi."""
    for tahap in VALID_STEPS:
        kunci = agent_key(tahap)
        assert kunci in AGENT_KEYS, f"{tahap} → {kunci!r}"


def test_nama_kelas_lama_dinormalkan_ke_kunci_kontrak() -> None:
    """Nama yang beredar di data lama tetap terbaca sebagai kunci tampilan."""
    assert normalize_agent_name("detection_agent") == "supply"
    assert normalize_agent_name("sap_agent") == "evidence"
    assert normalize_agent_name("worker.detect") == "supply"
    assert normalize_agent_name("orchestrator") == "supervisor"
    assert normalize_agent_name("verifier_agent") == "verifier"
    assert normalize_agent_name("supervisor_agent") == "supervisor"
    assert normalize_agent_name("SUPPLY") == "supply"
    assert normalize_agent_name("") is None
    assert normalize_agent_name(None) is None
    assert normalize_agent_name("tidak-dikenal") is None


def test_alat_menentukan_agen_lebih_spesifik_daripada_tahap() -> None:
    # DETECT bawaan = supply, tetapi alatnya milik agen demand.
    assert agent_key("DETECT", "demand.snapshot") == "demand"
    assert agent_key("DETECT") == "supply"
    # Suhu = bukti keamanan pangan, bukan bukti administrasi.
    assert agent_key("VERIFY", "evidence.temperature") == "safety"
    assert agent_key("VERIFY", "evidence.crosscheck") == "evidence"
    # Prefiks komoditas: `telur.supply_gap` tetap pasokan.
    assert agent_key("DETECT", "telur.supply_gap") == "supply"
    assert agent_key("PREDICT", "forecast.daily") == "demand"
    assert agent_key("OPTIMIZE", "logistics.reroute") == "logistics"
    assert agent_key("OPTIMIZE", "price.signal") == "price"
    assert agent_key("DECIDE", "supply_balance.propose") == "supervisor"
    assert agent_key("ACT", "purchase_order.commit") == "evidence"
    assert agent_key("SUPERVISE", "supervisor.narration") == "supervisor"


def test_tahap_asing_gagal_tegas_bukan_menulis_kosong() -> None:
    assert agent_key_for("TAHAP_ASING", None) is None
    with pytest.raises(ValueError, match="tidak punya agen kontrak"):
        agent_key("TAHAP_ASING")


def test_penyemai_demo_tidak_lagi_menulis_nama_kelas() -> None:
    """Literal lama tidak boleh kembali ke template (sumber bug 0/8)."""
    import inspect

    from app.seed import demo_template

    sumber = inspect.getsource(demo_template)
    for nama_lama in ('"detection_agent"', '"sap_agent"', '"orchestrator"'):
        assert nama_lama not in sumber, f"nama kelas lama kembali: {nama_lama}"


# ── bukti pada data: semai nyata lalu periksa `agent_traces` ────────────────


def _jalankan(fn):
    async def _main():
        eng = create_engine(settings.database_url)
        maker = create_session_maker(eng)
        try:
            async with maker() as db:
                return await fn(db)
        finally:
            await eng.dispose()

    return asyncio.run(_main())


def _semai_kasus_jakarta() -> None:
    """Jalankan jalur RESMI penyemai kasus demo untuk Jakarta (force=True)."""
    from app.api.demo import _seed_demo_cases
    from app.models import Location

    async def _siapkan(db) -> None:
        jakarta = (
            await db.execute(select(Location).where(Location.name == "Jakarta"))
        ).scalar_one()
        await _seed_demo_cases(db, True, jakarta)
        await db.commit()

    _jalankan(_siapkan)


@pytest.fixture(scope="module")
def jejak_kasus_jakarta() -> list[tuple[str, str]]:
    """Baris jejak kasus skrip Jakarta SETELAH disemai ulang lewat jalur resmi.

    Hanya kasus yang memang ditulis `_seed_demo_cases` (empat cerita skrip +
    kasus komoditas). Kasus lain (`bukti-hari-ini`) punya penyemai sendiri.
    """
    from app.api.demo import DEMO_CASES
    from app.services.scenario_specs import kasus_komoditas

    kasus = list(DEMO_CASES) + [spec.key for spec in kasus_komoditas()]
    _semai_kasus_jakarta()
    with create_sync_engine(DSN_SYNC, pool_pre_ping=True).connect() as conn:
        baris = conn.execute(
            text(
                "SELECT t.step_name, COALESCE(t.agent_name, '') "
                "FROM agent_traces t JOIN decisions d ON d.id = t.decision_id "
                "JOIN locations l ON l.id = d.target_location_id "
                "WHERE d.demo_case = ANY(:kasus) AND l.name = 'Jakarta'"
            ),
            {"kasus": kasus},
        ).all()
    return [(str(langkah), str(nama)) for langkah, nama in baris]


def test_penyemaian_kasus_demo_menulis_agen_kontrak(
    jejak_kasus_jakarta: list[tuple[str, str]],
) -> None:
    """Setelah semai: minimal 6 dari 9 kunci kontrak punya baris, tak ada NULL."""
    assert jejak_kasus_jakarta, "penyemaian tidak menulis satu pun baris jejak"
    kosong = [langkah for langkah, nama in jejak_kasus_jakarta if not nama]
    assert not kosong, f"masih ada baris tanpa agent_name: {sorted(set(kosong))}"

    nama = {nama for _, nama in jejak_kasus_jakarta}
    asing = nama - set(AGENT_KEYS)
    assert not asing, f"agent_name di luar kunci tampilan: {sorted(asing)}"
    assert len(nama) >= 6, f"hanya {len(nama)} kunci cocok: {sorted(nama)}"
