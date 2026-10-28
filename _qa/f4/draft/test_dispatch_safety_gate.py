"""Gerbang kelayakan sampai kandidat dispatchable (Fase 4 MG butir 1, 3, 6).

Yang dikunci berkas ini adalah SATU rantai keputusan:

    batch (fakta aman + umur + bukti)  ->  evaluator tunggal
        ->  kandidat (boleh `on_hold` untuk verifikasi, TIDAK boleh `usable`)
        ->  jendela kirim dari `needed_by` (bukan dari UI)

Sebelum Fase 4, generator kandidat punya aturannya sendiri: hanya `fail` dan
`quarantined` yang dibuang, `pending` lolos sebagai kandidat eligible, dan
`usable_until` tidak pernah diuji terhadap waktu tiba. Tes di sini gagal pada
kode lama (`TypeError: unexpected keyword argument 'evaluation_time'`) — itu
bukti RED yang dimaksud, bukan kegagalan fixture.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.core.candidate import PriceInfo
from app.core.candidate_generation import generate_candidates
from app.services import recommendation_service as rs

SEKARANG = datetime(2026, 10, 27, 8, 0, tzinfo=UTC)
SUMBER, TUJUAN, KOMODITAS = "Cianjur", "Jakarta", "telur"


def _batch(**ubah) -> dict:
    """Batch sehat lengkap dengan fakta kelayakan (bentuk dari fetch_operational_facts)."""
    data = {
        "batch_id": "b-1",
        "supplier_id": "sup-1",
        "excluded_destinations": [],
        "location": SUMBER,
        "commodity": KOMODITAS,
        "quantity_kg": Decimal("600"),
        "freshness_score": Decimal("0.90"),
        "freshness_status": "pass",
        "safety_status": "pass",
        "quarantine_status": "none",
        "usable_until": SEKARANG + timedelta(days=5),
        "temperature_log": [
            {"timestamp": (SEKARANG - timedelta(hours=2)).isoformat(), "temperature_c": 4.0},
            {"timestamp": (SEKARANG - timedelta(hours=1)).isoformat(), "temperature_c": 5.0},
        ],
    }
    data.update(ubah)
    return data


def _kwargs(batches=None, *, arrival=None, **ubah):
    data = dict(
        source_records={(SUMBER, KOMODITAS): 1400, ("Jakarta", KOMODITAS): 300},
        destination_records={(SUMBER, KOMODITAS): 500, (TUJUAN, KOMODITAS): 1000},
        batches=[_batch()] if batches is None else batches,
        logistics_by_pair={
            (SUMBER, TUJUAN): {
                "feasible": True,
                "distance_km": 120,
                "estimated_time_min": 150.0,
            }
        },
        prices={(SUMBER, TUJUAN, KOMODITAS): PriceInfo(Decimal("26500"))},
    )
    data.update(ubah)
    if arrival is not None:
        data["arrival_due_by_pair"] = {(SUMBER, TUJUAN, KOMODITAS): arrival}
    return data


def test_batch_sehat_menghasilkan_kandidat_usable() -> None:
    hasil = generate_candidates(**_kwargs(), evaluation_time=SEKARANG)
    assert len(hasil) == 1
    assert hasil[0].eligibility_status == "usable"
    assert hasil[0].blocking_reasons == ()


def test_batch_pending_dilaporkan_on_hold_bukan_usable() -> None:
    """`pending` boleh muncul (untuk verifikasi) tetapi bukan kandidat usable."""
    hasil = generate_candidates(
        **_kwargs(batches=[_batch(safety_status="pending")]), evaluation_time=SEKARANG
    )
    assert len(hasil) == 1
    assert hasil[0].eligibility_status == "on_hold"
    assert "safety_pending" in hasil[0].blocking_reasons


def test_batch_needs_verification_on_hold() -> None:
    hasil = generate_candidates(
        **_kwargs(batches=[_batch(safety_status="needs_verification")]),
        evaluation_time=SEKARANG,
    )
    assert hasil[0].eligibility_status == "on_hold"
    assert "safety_needs_verification" in hasil[0].blocking_reasons


def test_log_suhu_kurang_on_hold_bukan_pass() -> None:
    satu = [_batch()["temperature_log"][0]]
    hasil = generate_candidates(
        **_kwargs(batches=[_batch(temperature_log=satu)]), evaluation_time=SEKARANG
    )
    assert hasil[0].eligibility_status == "on_hold"
    assert "temperature_evidence_incomplete" in hasil[0].blocking_reasons


def test_batch_fail_tidak_menghasilkan_kandidat() -> None:
    hasil = generate_candidates(
        **_kwargs(batches=[_batch(safety_status="fail")]), evaluation_time=SEKARANG
    )
    assert hasil == []


def test_usable_until_kosong_tidak_dianggap_aman() -> None:
    hasil = generate_candidates(
        **_kwargs(batches=[_batch(usable_until=None)]), evaluation_time=SEKARANG
    )
    assert hasil == []


def test_barang_kedaluwarsa_sebelum_tiba_tidak_menghasilkan_kandidat() -> None:
    """Umur barang diuji terhadap WAKTU TIBA hasil logistik, bukan hari ini."""
    hasil = generate_candidates(
        **_kwargs(batches=[_batch(usable_until=SEKARANG + timedelta(days=1))]),
        evaluation_time=SEKARANG,
        arrival=(SEKARANG + timedelta(days=2)),
    )
    assert hasil == []


def test_kandidat_tanpa_fakta_kelayakan_tetap_dinilai_aturan_lama() -> None:
    """Kontrak kompatibilitas: fixture lama yang tidak membawa `usable_until`.

    Dict batch tanpa kunci `usable_until` berasal dari pemanggil lama yang tidak
    menyuplai fakta kelayakan; ia dinilai aturan lama supaya kontrak 6-tuple
    Task 9 tetap sah. Begitu kuncinya ADA (termasuk bernilai None), evaluator
    berlaku — lihat tes `usable_until_kosong` di atas.
    """
    tanpa_fakta = _batch()
    tanpa_fakta.pop("usable_until")
    tanpa_fakta.pop("temperature_log")
    tanpa_fakta.pop("quarantine_status")
    hasil = generate_candidates(
        **_kwargs(batches=[tanpa_fakta]), evaluation_time=SEKARANG
    )
    assert len(hasil) == 1
    assert hasil[0].eligibility_status == "usable"


# --- Jendela kirim dari kebutuhan (butir 6) ---------------------------------


def _facts(needed_by, *, batches=None, logistics=None):
    supply = {(SUMBER, KOMODITAS): Decimal("1400"), (TUJUAN, KOMODITAS): Decimal("300")}
    demand = {(SUMBER, KOMODITAS): Decimal("500"), (TUJUAN, KOMODITAS): Decimal("1000")}
    refs = {(SUMBER, KOMODITAS): Decimal("26500"), (TUJUAN, KOMODITAS): Decimal("30500")}
    quotes = {}
    reliability = {"sup-1": Decimal("0.80")}
    return (
        supply,
        demand,
        refs,
        quotes,
        batches or [_batch()],
        reliability,
        {},
        {},
        {(TUJUAN, KOMODITAS): needed_by},
    )


def _run(coro):
    import asyncio

    return asyncio.run(coro)


def test_needed_by_yang_sudah_lewat_tidak_menghasilkan_kandidat() -> None:
    out = _run(
        rs.build_recommendations(
            lambda: _facts(SEKARANG - timedelta(hours=1)),
            as_of=SEKARANG,
        )
    )
    assert out["recommendations"] == []


def test_needed_by_yang_masih_lapang_menghasilkan_kandidat_dengan_jendela() -> None:
    out = _run(
        rs.build_recommendations(
            lambda: _facts(SEKARANG + timedelta(hours=12)),
            as_of=SEKARANG,
        )
    )
    assert out["recommendations"], "jadwal lapang seharusnya masih bisa dikirim"
    jendela = out["recommendations"][0]["delivery_window"]
    assert jendela["state"] == "terpenuhi"
    assert Decimal(jendela["window_min"]) > 0


def test_estimasi_melebihi_jendela_tidak_menghasilkan_kandidat() -> None:
    """Perjalanan 150 menit + persiapan tidak muat dalam 2 jam tersisa."""
    out = _run(
        rs.build_recommendations(
            lambda: _facts(SEKARANG + timedelta(minutes=100)),
            as_of=SEKARANG,
        )
    )
    assert out["recommendations"] == []


def test_tanpa_baris_permintaan_jendela_ditandai_tidak_tercatat() -> None:
    facts = _facts(SEKARANG + timedelta(hours=12))
    # Baris ke-9 diganti peta kosong: tidak ada needed_by untuk pasangan ini.
    facts = facts[:8] + ({},)
    out = _run(rs.build_recommendations(lambda: facts, as_of=SEKARANG))
    assert out["recommendations"], "tanpa batas, kandidat lama tetap muncul"
    assert out["recommendations"][0]["delivery_window"]["state"] == "tidak_tercatat"


def test_barang_kedaluwarsa_sebelum_tiba_gugur_di_pipeline() -> None:
    out = _run(
        rs.build_recommendations(
            lambda: _facts(
                SEKARANG + timedelta(hours=12),
                batches=[_batch(usable_until=SEKARANG + timedelta(hours=1))],
            ),
            as_of=SEKARANG,
        )
    )
    assert out["recommendations"] == []


def test_payload_kandidat_on_hold_tidak_ditandai_lolos() -> None:
    out = _run(
        rs.build_recommendations(
            lambda: _facts(
                SEKARANG + timedelta(hours=12),
                batches=[_batch(safety_status="pending")],
            ),
            as_of=SEKARANG,
        )
    )
    assert out["recommendations"], "on_hold tetap dilaporkan untuk verifikasi"
    top = out["recommendations"][0]
    assert top["eligibility"]["status"] == "on_hold"
    assert "safety_pending" in top["eligibility"]["blocking_reasons"]
    assert top["review_required"] is True
