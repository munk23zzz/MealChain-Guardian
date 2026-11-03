"""Wiring jendela kirim dari kebutuhan — Fase 4 MG butir 6 (lapisan layanan).

Modul murni `core/delivery_policy.py` sudah diuji sendiri. Berkas ini mengunci
wiring-nya: `DemandRecord.needed_by` harus benar-benar sampai ke rantai
rekomendasi, dan kandidat yang tidak bisa tiba sebelum kebutuhan (atau yang
masa-layaknya habis di jalan) harus GUGUR — bukan diam-diam tetap berperingkat.

Kontrak yang diuji:
- `needed_by` lewat saat evaluasi             → kandidat gugur (`delivery_window_exceeded`)
- anggaran waktu < estimasi angkut            → kandidat gugur (sebab sama)
- `usable_until` < waktu tiba                 → kandidat gugur (`expired_before_arrival`)
- tanpa baris permintaan                      → kandidat tetap ada, tetapi
  `delivery_window.state == "tidak_tercatat"` (jadwal TIDAK diklaim terpenuhi)
- jendela pas (window == estimasi)            → kandidat bertahan (batas inklusif)
"""

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.services import recommendation_service as rs

UTC = timezone.utc
AS_OF = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)

SUPPLY = {("Cianjur", "telur"): Decimal("1400"), ("Jakarta", "telur"): Decimal("300")}
DEMAND = {("Cianjur", "telur"): Decimal("500"), ("Jakarta", "telur"): Decimal("1000")}
REFS = {("Cianjur", "telur"): Decimal("26500"), ("Jakarta", "telur"): Decimal("30500")}
QUOTES = {("Cianjur", "telur"): (Decimal("26200"), "11111111-1111-1111-1111-111111111111")}
RELIABILITY = {"11111111-1111-1111-1111-111111111111": Decimal("0.80")}
LOGI = {
    ("Cianjur", "Jakarta"): {
        "distance_km": 120,
        "estimated_time_min": 150.0,
        "feasible": True,
    }
}


def _batch(usable_until=None):
    return {
        "batch_id": "b-1",
        "location": "Cianjur",
        "commodity": "telur",
        "quantity_kg": Decimal("600"),
        "freshness_score": Decimal("0.90"),
        "freshness_status": "pass",
        "safety_status": "pass",
        "usable_until": usable_until,
    }


def _facts(needed_by, *, usable_until=None):
    # `usable_until` bawaan sengaja jauh: gerbang bukti Fase 6 menahan batch
    # tanpa masa layak sebagai `expiry_unknown`, dan tes ini bukan tentang itu.
    if usable_until is None:
        usable_until = AS_OF + timedelta(days=30)
    hierarki = {"needed_by": {("Jakarta", "telur"): needed_by}}
    return (
        SUPPLY,
        DEMAND,
        REFS,
        QUOTES,
        [_batch(usable_until)],
        RELIABILITY,
        {},
        hierarki,
    )


def _run(facts, logi=LOGI):
    return asyncio.run(
        rs.build_recommendations(lambda: facts, as_of=AS_OF, logistics_by_pair=logi)
    )


def test_needed_by_jauh_kandidat_lolos_dan_jendela_dilaporkan():
    out = _run(_facts(AS_OF + timedelta(hours=12)))
    assert len(out["recommendations"]) == 1
    jendela = out["recommendations"][0]["delivery_window"]
    assert jendela["state"] == "terpenuhi"
    # 12 jam = 720 menit anggaran; lead_time bawaan 0 → 720 menit.
    assert jendela["window_min"] == 720.0
    assert jendela["arrival_due_at"] is not None


def test_needed_by_sudah_lewat_kandidat_gugur():
    out = _run(_facts(AS_OF - timedelta(hours=1)))
    assert out["recommendations"] == []
    assert [h["blocking_reasons"] for h in out["held"]] == [
        ["delivery_window_exceeded"]
    ]


def test_anggaran_waktu_kurang_dari_estimasi_kandidat_gugur():
    # 100 menit anggaran untuk perjalanan 150 menit → tidak mungkin tiba.
    out = _run(_facts(AS_OF + timedelta(minutes=100)))
    assert out["recommendations"] == []
    assert "delivery_window_exceeded" in out["held"][0]["blocking_reasons"]


def test_jendela_pas_dengan_estimasi_masih_lolos():
    # Batas inklusif: anggaran persis 150 menit = estimasi angkut.
    out = _run(_facts(AS_OF + timedelta(minutes=150)))
    assert len(out["recommendations"]) == 1


def test_usable_until_habis_di_jalan_kandidat_gugur():
    # needed_by masih lama, tetapi barang kedaluwarsa sebelum kendaraan tiba.
    out = _run(
        _facts(AS_OF + timedelta(hours=12), usable_until=AS_OF + timedelta(minutes=60))
    )
    assert out["recommendations"] == []
    assert "expired_before_arrival" in out["held"][0]["blocking_reasons"]


def test_tanpa_needed_by_tidak_diklaim_terpenuhi():
    out = _run(_facts(None))
    assert len(out["recommendations"]) == 1
    jendela = out["recommendations"][0]["delivery_window"]
    assert jendela["state"] == "tidak_tercatat"
    assert jendela["window_min"] is None
    assert jendela["needed_by"] is None


def test_kandidat_gugur_tidak_dihitung_dalam_jumlah_rekomendasi():
    out = _run(_facts(AS_OF - timedelta(minutes=1)))
    assert out["recommendations"] == []
    assert len(out["held"]) == 1
