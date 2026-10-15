"""Generator deret waktu demo (Fase 4) — rencana baris MURNI (tanpa DB).

Yang dijaga di sini adalah dua aturan yang membuat data demo tidak merusak
jangkar kanonik (rencana Fase 4 butir C1/C2), plus determinisme: nilai deret
diturunkan dari hash kunci, bukan RNG berjalan, jadi hasilnya tidak bergantung
urutan iterasi dan bisa diulang persis.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.seed.timeseries import (
    ACTUAL_HORIZON_MARGIN,
    CANONICAL_REF,
    DEFAULT_END,
    DEFAULT_START,
    WEEKEND_FACTOR,
    actual_cutoff,
    actual_timestamps,
    plan_all,
    plan_menu_plan_rows,
    plan_quote_price_rows,
    plan_supply_rows,
    planned_portions,
    reference_price_value,
    supply_value,
    validate_range,
)

PAIR = ("lok-1|kom-1", "lok-1", "kom-1", Decimal("1400"))


def _pairs(n: int = 2):
    return [
        (f"lok-{i}|kom-1", f"lok-{i}", f"kom-{i}", Decimal(1000 + 100 * i))
        for i in range(1, n + 1)
    ]


# ------------------------------------------------------------------ validasi


def test_validate_range_menolak_rentang_ngawur():
    with pytest.raises(ValueError, match="offset zona waktu"):
        validate_range(datetime(2026, 9, 1), datetime(2026, 9, 2))
    with pytest.raises(ValueError, match="lebih awal"):
        validate_range(DEFAULT_END, DEFAULT_START)
    with pytest.raises(ValueError, match="lebih awal"):
        validate_range(DEFAULT_START, DEFAULT_START)
    with pytest.raises(ValueError, match="di luar batas"):
        validate_range(datetime(2019, 1, 1, tzinfo=UTC), datetime(2019, 2, 1, tzinfo=UTC))
    with pytest.raises(ValueError, match="di luar batas"):
        validate_range(DEFAULT_START, datetime(2031, 1, 1, tzinfo=UTC))


def test_validate_range_menerima_rentang_default():
    validate_range(DEFAULT_START, DEFAULT_END)


# -------------------------------------------------------------- batas aktual


def test_baris_aktual_tidak_menyentuh_jendela_kpi():
    """Window KPI = [REF-24 jam, REF]; baris demo harus berhenti di bawahnya."""
    stamps = actual_timestamps(DEFAULT_START, DEFAULT_END, 12)
    assert stamps, "harus ada baris aktual"
    cutoff = actual_cutoff()
    assert max(stamps) < cutoff
    assert all(cutoff - s >= timedelta(0) for s in stamps)
    # 7 Okt 12:00 adalah batas atas eksklusif: tepat 7 Okt 00:00 masih boleh.
    assert max(stamps) == datetime(2026, 10, 7, 0, 0, tzinfo=UTC)
    assert cutoff == datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
    assert CANONICAL_REF - ACTUAL_HORIZON_MARGIN == cutoff


def test_interval_minimal_satu_jam():
    with pytest.raises(ValueError, match="interval_hours"):
        actual_timestamps(DEFAULT_START, DEFAULT_END, 0)


def test_rentang_pendek_di_masa_lalu_tetap_dihasilkan():
    start = datetime(2026, 9, 1, tzinfo=UTC)
    end = datetime(2026, 9, 3, tzinfo=UTC)
    assert len(actual_timestamps(start, end, 12)) == 4  # 1 00:00, 1 12:00, 2 00:00, 2 12:00


# --------------------------------------------------------------- nilai deret


def test_nilai_pasokan_deterministik_dan_quantized():
    at = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)  # Rabu
    first = supply_value(Decimal("1400"), PAIR[0], at)
    assert first == supply_value(Decimal("1400"), PAIR[0], at)
    assert first.as_tuple().exponent == -2, "harus 2 desimal (kontrak O-NUM)"
    assert first >= 0


def test_nilai_pasokan_dalam_pita_derau():
    """Hari kerja: ±6% dari baseline; akhir pekan: tambahan faktor 0,92."""
    weekday = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)  # Rabu
    saturday = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)
    baseline = Decimal("1400")
    wd = supply_value(baseline, PAIR[0], weekday)
    sat = supply_value(baseline, PAIR[0], saturday)
    assert baseline * Decimal("0.94") <= wd <= baseline * Decimal("1.06")
    assert (
        baseline * WEEKEND_FACTOR * Decimal("0.94")
        <= sat
        <= baseline * WEEKEND_FACTOR * Decimal("1.06")
    )


def test_pola_mingguan_akhir_pekan_lebih_rendah():
    """Rata-rata akhir pekan harus lebih rendah dari hari kerja (narasi demo)."""
    stamps = [datetime(2026, 9, d, 12, 0, tzinfo=UTC) for d in range(1, 29)]
    values = [supply_value(Decimal("1000"), PAIR[0], s) for s in stamps]
    weekend = [v for s, v in zip(stamps, values) if s.weekday() >= 5]
    weekday = [v for s, v in zip(stamps, values) if s.weekday() < 5]
    assert sum(weekend) / len(weekend) < sum(weekday) / len(weekday)


def test_harga_referensi_selalu_positif():
    at = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)
    assert reference_price_value(Decimal("30000"), PAIR[0], at) > 0
    assert reference_price_value(Decimal("0.02"), PAIR[0], at) >= Decimal("0.01")


def test_porsi_rencana_mengikuti_pola_mingguan():
    rabu = planned_portions(1200, "lok-1", datetime(2026, 9, 2).date())
    sabtu = planned_portions(1200, "lok-1", datetime(2026, 9, 5).date())
    assert 0 < sabtu < rabu <= 1224  # derau porsi hanya ±2%


# ------------------------------------------------------------- rencana baris


def test_plan_supply_menghasilkan_kartesius_pasangan_kali_waktu():
    stamps = actual_timestamps(DEFAULT_START, DEFAULT_END, 12)
    rows = plan_supply_rows(_pairs(3), stamps)
    assert len(rows) == 3 * len(stamps)
    assert {r["origin"] for r in rows} == {"demo"}
    assert {r["source"] for r in rows} == {"mock_sap"}
    assert all(r["recorded_at"] < actual_cutoff() for r in rows)


def test_urutan_pasangan_tidak_mengubah_nilai():
    """Nilai diturunkan dari hash kunci, jadi urutan input tidak berpengaruh."""
    stamps = actual_timestamps(DEFAULT_START, DEFAULT_END, 24)
    pairs = _pairs(3)
    straight = plan_supply_rows(pairs, stamps)
    shuffled = plan_supply_rows(list(reversed(pairs)), list(reversed(stamps)))
    key = lambda r: (str(r["location_id"]), r["recorded_at"].isoformat())  # noqa: E731
    assert {key(r): r["quantity_kg"] for r in straight} == {
        key(r): r["quantity_kg"] for r in shuffled
    }


def test_plan_menu_harian_inklusif_tanpa_duplikat():
    rows = plan_menu_plan_rows(
        [("lok-1", 1200), ("lok-2", 900)], DEFAULT_START, DEFAULT_END
    )
    hari = sorted({r["plan_date"] for r in rows})
    assert hari[0] == DEFAULT_START.date()
    assert hari[-1] == DEFAULT_END.date()
    assert len(hari) == (DEFAULT_END.date() - DEFAULT_START.date()).days + 1
    keys = {(str(r["location_id"]), r["plan_date"]) for r in rows}
    assert len(keys) == len(rows), "tidak boleh ada (lokasi, tanggal) kembar"
    assert all(r["planned_portions"] > 0 for r in rows)
    assert {r["origin"] for r in rows} == {"demo"}


def test_plan_kutipan_pemasok_mingguan_dan_konsisten():
    quotes = [("sup-1|kom-1", "lok-1", "kom-1", "sup-1", Decimal("27000"))]
    rows = plan_quote_price_rows(quotes, DEFAULT_START, actual_cutoff())
    assert len(rows) == 6  # 1 Sep → 6 Okt, satu per pekan
    assert {r["source"] for r in rows} == {"supplier_quote"}
    assert all(r["supplier_id"] == "sup-1" for r in rows)
    assert all(r["price_per_kg"] > 0 for r in rows)
    gaps = {
        (rows[i + 1]["recorded_at"] - rows[i]["recorded_at"]).days
        for i in range(len(rows) - 1)
    }
    assert gaps == {7}


def test_plan_all_meringkas_batas_aktual_dan_rencana():
    plan = plan_all(
        supply_pairs=_pairs(2),
        reference_pairs=_pairs(2),
        quotes=[],
        menu_bases=[("lok-1", 1200)],
        start=DEFAULT_START,
        end=DEFAULT_END,
        interval_hours=12,
    )
    assert plan["range"]["actual_end"] == actual_cutoff().isoformat()
    assert plan["range"]["plan_end"] == DEFAULT_END.date().isoformat()
    assert plan["range"]["start"] == DEFAULT_START.isoformat()
    hari_rencana = len(plan["menu_plans"])
    assert hari_rencana == (DEFAULT_END.date() - DEFAULT_START.date()).days + 1
    assert len(plan["supply"]) == 2 * plan["actual_timestamps"]
    assert len(plan["prices"]) == len(plan["supply"])


def test_perkalian_data_tetap_terjangkau():
    """Skala nyata: 10 lokasi × 3 komoditas (30 pasangan) × 73 cap waktu."""
    stamps = actual_timestamps(DEFAULT_START, DEFAULT_END, 12)
    rows = plan_supply_rows(_pairs(30), stamps)
    assert len(rows) == 30 * len(stamps) == 2190
    assert 1500 <= len(rows) <= 3000
