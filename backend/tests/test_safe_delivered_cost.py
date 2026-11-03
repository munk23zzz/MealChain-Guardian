"""Task 6 Sprint 2: Safe Delivered Cost deterministik.

Kontrak terkunci (plan Task 6):
total = Purchase + Transport + Handling + Expected Loss
        + Freshness Risk Penalty + Safety Risk Penalty

Revisi 2026-10-29b (permintaan pemilik, lanjutan konsep Performance & Audit):
- LAJU SUSUT PER KOMODITAS (core/shrinkage.py): beras 0,8%, telur 4%,
  wortel 15%, ayam 12% per umur simpan. 20% (kontrak lama) hanya cadangan
  untuk komoditas tak terdaftar, dan sumbernya WAJIB dilaporkan di
  `shrinkage_rate_source` — bukan disamarkan sebagai angka tabel.
- PENALTI KESEGARAN: kurva linear, bukan cliff. purchase × 0,50 ×
  (0,60 − freshness) ÷ 0,60 untuk freshness < 0,60. Nol di 0,60 (kontinu),
  maksimum 50% di freshness 0 — besaran puncak tidak berubah, diskontinuitas
  yang hilang. freshness 0,599 tidak lagi melonjak ke +50%.
- loss_in_storage = purchase × (laju_komoditas ÷ umur_simpan) × hari_simpan.
  `(1 − freshness)` BUKAN pengali susut: kesegaran mengukur mutu saat terima,
  bukan lama penyimpanan. Kesegaran tetap menambah RISIKO (penalti).
- `hari_simpan = 0` → susut nol (barang langsung dipakai tidak menyusut).
- `hari_simpan = umur_simpan` → susut = purchase × laju (identitas, bukan rumus
  baru; dipakai sebagai pemeriksaan kewajaran).
- Freshness risk: freshness < 0.60 → penalty = purchase × 0.50
- Safety risk: needs_verification → penalty = purchase × 0.10
- Safety FAIL ditolak SEBELUM perhitungan (ValueError) — tidak pernah
  dihitung, tidak pernah diranking.
- Umur simpan dari tabel profil komoditas bila tidak dikirim; komoditas tak
  dikenal + tanpa umur = ValueError (bukan angka bawaan yang dikarang).
- Rounding HALF_UP 2dp per komponen; total = jumlah komponen terbulatkan
  (breakdown selalu menjumlah persis ke total — audit trail).
"""

import inspect
from decimal import Decimal

import pytest

from app.core import safe_delivered_cost as modul_sdc
from app.core.safe_delivered_cost import (
    FORMULA_VERSION,
    SafeDeliveredCostInputs,
    SafeDeliveredCostResult,
    calculate_safe_delivered_cost,
)
from app.core.shrinkage import LAJU_SUSUT
from app.core.storage_window import (
    BASIS_ASUMSI,
    BASIS_RENCANA,
    storage_days_for,
)

TELUR_UMUR = Decimal("28")  # `commodity_policy.PROFILES["telur"].shelf_life_days`


def _inputs(**overrides):
    base = {
        "purchase_cost": Decimal("12500000"),  # 25.000 × 500 kg (Skill §8)
        "transport_cost": Decimal("1000000"),
        "handling_cost": Decimal("250000"),
        "freshness_score": Decimal("1.00"),
        "safety_status": "pass",
        "commodity": "telur",
    }
    base.update(overrides)
    return SafeDeliveredCostInputs(**base)


# ---------------------------------------------------------------- dasar ----


def test_clean_batch_sums_all_components():
    r = calculate_safe_delivered_cost(_inputs())
    assert isinstance(r, SafeDeliveredCostResult)
    # Barang yang diterima tetap tersimpan (asumsi 1 hari) → susut KECIL, bukan nol.
    # 12.500.000 × 0,04 (telur) × (1 ÷ 28) = 17.857,142… → 17.857,14
    assert r.loss_in_storage == Decimal("17857.14")
    assert r.freshness_risk_penalty == Decimal("0")
    assert r.safety_risk_penalty == Decimal("0")
    assert r.total == Decimal("13767857.14")


def test_loss_in_storage_sama_dengan_alias_expected_loss():
    """Satu angka, dua nama. Kode lama membaca `expected_loss`."""
    r = calculate_safe_delivered_cost(_inputs(storage_days=Decimal("7")))
    assert r.expected_loss == r.loss_in_storage


def test_expected_loss_formula_locked():
    """Susut = purchase × (laju_komoditas ÷ umur) × hari.

    12.500.000 × 0,04 × (7 ÷ 28) = 125.000 — aritmetika saja, bukan klaim PASS.
    """
    r = calculate_safe_delivered_cost(
        _inputs(freshness_score=Decimal("0.75"), storage_days=Decimal("7"))
    )
    assert r.loss_in_storage == Decimal("125000.00")
    assert r.freshness_risk_penalty == Decimal("0")
    assert r.total == Decimal("13875000.00")


def test_hari_simpan_nol_tidak_menyusut():
    """Barang yang langsung dipakai tidak menyusut (sifat #1 konsep §4.2)."""
    r = calculate_safe_delivered_cost(
        _inputs(freshness_score=Decimal("0.20"), storage_days=Decimal("0"))
    )
    assert r.loss_in_storage == Decimal("0.00")


def test_hari_simpan_sama_dengan_umur_menghasilkan_laju_komoditas():
    """Identitas: hari = umur → susut = purchase × laju komoditas (4% telur)."""
    r = calculate_safe_delivered_cost(
        _inputs(storage_days=TELUR_UMUR, freshness_score=Decimal("0.20"))
    )
    assert r.loss_in_storage == (
        Decimal("12500000") * LAJU_SUSUT["telur"]
    ).quantize(Decimal("0.01"))


def test_susut_tidak_bergerak_karena_kesegaran():
    """Mutu kiriman TIDAK boleh mengubah susut gudang (inti T1/T2)."""
    segar = calculate_safe_delivered_cost(
        _inputs(freshness_score=Decimal("1.00"), storage_days=Decimal("7"))
    )
    layu = calculate_safe_delivered_cost(
        _inputs(freshness_score=Decimal("0.30"), storage_days=Decimal("7"))
    )
    assert segar.loss_in_storage == layu.loss_in_storage
    # Kesegaran tetap terlihat — di RISIKO, bukan di susut.
    assert layu.freshness_risk_penalty > segar.freshness_risk_penalty


def test_baris_loss_in_storage_tidak_memuat_freshness():
    """Pemeriksaan review konsep §4.4, dijalankan sebagai tes.

    Kalau kelak ada yang menambahkan `(1 − freshness)` kembali ke rumus susut,
    tes ini gagal sebelum angkanya dipakai meranking kandidat.
    """
    sumber = inspect.getsource(modul_sdc.calculate_safe_delivered_cost)
    baris = [ln for ln in sumber.splitlines() if "loss_in_storage =" in ln]
    assert baris, "baris hitung loss_in_storage tidak ditemukan"
    for ln in baris:
        assert "freshness" not in ln.lower(), f"freshness kembali ke susut: {ln}"


# ------------------------------------------------------------ umur & hari --


def test_umur_simpan_diambil_dari_profil_komoditas():
    r = calculate_safe_delivered_cost(_inputs())
    assert r.shelf_life_days == TELUR_UMUR
    # r_hari = laju komoditas ÷ umur
    assert r.daily_shrinkage_rate == LAJU_SUSUT["telur"] / TELUR_UMUR
    assert r.shrinkage_rate == LAJU_SUSUT["telur"]
    assert r.shrinkage_rate_source == "tabel_laju_susut_komoditas"


def test_tanpa_komoditas_dan_tanpa_umur_ditolak():
    """Bukan 0, bukan tebakan: input yang tidak lengkap ditolak."""
    with pytest.raises(ValueError, match="shelf_life_days"):
        calculate_safe_delivered_cost(_inputs(commodity=None))


def test_komoditas_tak_dikenal_ditolak_dengan_pesan_jelas():
    with pytest.raises(ValueError, match="profil"):
        calculate_safe_delivered_cost(_inputs(commodity="ubi-jalar"))


def test_hari_simpan_dibatasi_umur_simpan():
    """Barang tidak mungkin tersimpan melewati umurnya → dijepit di umur."""
    r = calculate_safe_delivered_cost(_inputs(storage_days=Decimal("100")))
    assert r.storage_days == TELUR_UMUR
    assert r.loss_in_storage == Decimal("500000.00")  # purchase × 0,04 (telur)


def test_hari_simpan_negatif_ditolak():
    with pytest.raises(ValueError, match="storage_days"):
        calculate_safe_delivered_cost(_inputs(storage_days=Decimal("-1")))


def test_basis_hari_simpan_dilaporkan_apa_adanya():
    tanpa = calculate_safe_delivered_cost(_inputs())
    assert tanpa.storage_basis == BASIS_ASUMSI
    dikirim = calculate_safe_delivered_cost(_inputs(storage_days=Decimal("3")))
    assert dikirim.storage_basis == "dikirim_pemanggil"


def test_versi_rumus_ikut_dilaporkan():
    r = calculate_safe_delivered_cost(_inputs())
    assert r.formula_version == FORMULA_VERSION


# --------------------------------------------- jendela simpan (storage_window)


def test_jendela_rencana_menu_dipakai_bila_diketahui():
    from datetime import UTC, datetime, timedelta

    tiba = datetime(2026, 10, 29, 6, tzinfo=UTC)
    hari, basis = storage_days_for(
        needed_by=tiba + timedelta(hours=30), arrival_at=tiba
    )
    assert basis == BASIS_RENCANA
    assert hari == Decimal("1.25")  # 30 jam, dibulatkan KE ATAS


def test_jendela_tanpa_tanggal_kebutuhan_memakai_asumsi_dan_mengatakannya():
    hari, basis = storage_days_for(needed_by=None, arrival_at=None)
    assert hari == Decimal("1.00")
    assert basis == BASIS_ASUMSI


def test_jendela_dibatasi_umur_simpan():
    from datetime import UTC, datetime, timedelta

    tiba = datetime(2026, 10, 29, 6, tzinfo=UTC)
    hari, _ = storage_days_for(
        needed_by=tiba + timedelta(days=90), arrival_at=tiba, shelf_life_days=28
    )
    assert hari == Decimal("28.00")


def test_jendela_tidak_negatif_bila_kebutuhan_sudah_lewat():
    from datetime import UTC, datetime, timedelta

    tiba = datetime(2026, 10, 29, 6, tzinfo=UTC)
    hari, _ = storage_days_for(
        needed_by=tiba - timedelta(hours=5), arrival_at=tiba
    )
    assert hari == Decimal("0.00")


# ---------------------------------------------------------------- penalti --


def test_freshness_risk_penalty_below_060():
    """Kurva linear: 12.500.000 × 0,50 × (0,60 − 0,59) ÷ 0,60 = 104.166,67."""
    r = calculate_safe_delivered_cost(
        _inputs(freshness_score=Decimal("0.59"), storage_days=Decimal("7"))
    )
    assert r.freshness_risk_penalty == Decimal("104166.67")
    # Susut TIDAK ikut berubah karena freshness (bandingkan tes rumus di atas).
    assert r.loss_in_storage == Decimal("125000.00")


def test_freshness_tidak_lagi_cliff():
    """Selisih kecil di sekitar 0,60 harus menghasilkan selisih kecil.

    Kontrak lama: 0,599 → +50%, 0,601 → 0 (lonjakan 6,25 jt untuk 0,002
    kesegaran). Kurva linear membuat selisihnya sebanding.
    """
    bawah = calculate_safe_delivered_cost(_inputs(freshness_score=Decimal("0.599")))
    atas = calculate_safe_delivered_cost(_inputs(freshness_score=Decimal("0.601")))
    selisih = bawah.freshness_risk_penalty - atas.freshness_risk_penalty
    assert atas.freshness_risk_penalty == Decimal("0.00")
    # 12.500.000 × 0,5 × (0,001 ÷ 0,6) = 10.416,67
    assert bawah.freshness_risk_penalty == Decimal("10416.67")
    assert selisih == Decimal("10416.67")


def test_freshness_puncak_tetap_50_persen():
    """Besaran puncak tidak berubah: freshness 0 → penalti 50% purchase."""
    r = calculate_safe_delivered_cost(_inputs(freshness_score=Decimal("0")))
    assert r.freshness_risk_penalty == Decimal("6250000.00")


def test_locked_600kg_numeric_breakdown():
    """Contoh Sprint 2 dengan hari simpan eksplisit (7 dari 28 hari)."""
    purchase = Decimal("600") * Decimal("26200")
    r = calculate_safe_delivered_cost(
        _inputs(
            purchase_cost=purchase,
            transport_cost=Decimal("21600"),
            handling_cost=Decimal("150000"),
            freshness_score=Decimal("0.50"),
            storage_days=Decimal("7"),
        )
    )
    assert r.purchase_cost == Decimal("15720000.00")
    assert r.transport_cost == Decimal("21600.00")
    assert r.handling_cost == Decimal("150000.00")
    assert r.loss_in_storage == Decimal("157200.00")  # 15,72 jt × 0,04 × 0,25
    assert r.freshness_risk_penalty == Decimal("1310000.00")  # 0,5 × (0,1÷0,6)
    assert r.safety_risk_penalty == Decimal("0.00")
    assert r.total == Decimal("17358800.00")
    assert r.total == sum(
        (
            r.purchase_cost,
            r.transport_cost,
            r.handling_cost,
            r.loss_in_storage,
            r.freshness_risk_penalty,
            r.safety_risk_penalty,
        ),
        Decimal("0"),
    )


def test_freshness_boundary_060_no_penalty():
    r = calculate_safe_delivered_cost(_inputs(freshness_score=Decimal("0.60")))
    assert r.freshness_risk_penalty == Decimal("0")


def test_safety_needs_verification_penalty_10pct():
    r = calculate_safe_delivered_cost(
        _inputs(safety_status="needs_verification")
    )
    assert r.safety_risk_penalty == Decimal("1250000.00")  # purchase × 0.1


def test_safety_pending_no_penalty_not_fail():
    r = calculate_safe_delivered_cost(_inputs(safety_status="pending"))
    assert r.safety_risk_penalty == Decimal("0")


def test_safety_fail_rejected_before_calculation():
    with pytest.raises(ValueError, match="fail"):
        calculate_safe_delivered_cost(_inputs(safety_status="fail"))


# --------------------------------------------------------------- validasi --


def test_negative_costs_rejected():
    with pytest.raises(ValueError, match="transport"):
        calculate_safe_delivered_cost(_inputs(transport_cost=Decimal("-1")))
    with pytest.raises(ValueError, match="handling"):
        calculate_safe_delivered_cost(_inputs(handling_cost=Decimal("-0.01")))
    with pytest.raises(ValueError, match="purchase"):
        calculate_safe_delivered_cost(_inputs(purchase_cost=Decimal("0")))


def test_freshness_out_of_range_rejected():
    with pytest.raises(ValueError, match="0"):
        calculate_safe_delivered_cost(_inputs(freshness_score=Decimal("1.2")))
    with pytest.raises(ValueError, match="0"):
        calculate_safe_delivered_cost(_inputs(freshness_score=Decimal("-0.1")))


def test_zero_transport_and_handling_allowed():
    r = calculate_safe_delivered_cost(
        _inputs(
            transport_cost=Decimal("0"),
            handling_cost=Decimal("0"),
            storage_days=Decimal("0"),
        )
    )
    assert r.total == Decimal("12500000.00")


# ---------------------------------------------------------- pembulatan 2dp --


def test_breakdown_sums_exactly_to_total():
    r = calculate_safe_delivered_cost(
        _inputs(
            purchase_cost="12345678.555",
            transport_cost="987654.321",
            handling_cost="0.004",
            freshness_score="0.83",
            safety_status="needs_verification",
            storage_days=Decimal("5"),
        )
    )
    assert (
        r.purchase_cost
        + r.transport_cost
        + r.handling_cost
        + r.loss_in_storage
        + r.freshness_risk_penalty
        + r.safety_risk_penalty
        == r.total
    )


def test_deterministic_repeat():
    i = _inputs(
        freshness_score="0.83",
        safety_status="needs_verification",
        storage_days=Decimal("4"),
    )
    a = calculate_safe_delivered_cost(i)
    b = calculate_safe_delivered_cost(i)
    assert a == b


def test_setiap_komponen_dibulatkan_2dp():
    """Kontrak modul: "Rounding HALF_UP 2dp per komponen; total = jumlah
    komponen terbulatkan".

    Uji audit 2026-10-11: hanya expected_loss yang di-quantize; freshness_risk
    dan safety_risk keluar mentah (mis. 12345.67 × 0.50 = 6172.835) sehingga
    breakdown tidak lagi 2dp — padahal angka ini dipakai membandingkan/meranking
    biaya dan (nanti) dikirim sebagai NetPriceAmount ke SAP.
    """
    r = calculate_safe_delivered_cost(
        _inputs(
            purchase_cost=Decimal("12345.67"),
            transport_cost=Decimal("150.005"),
            handling_cost=Decimal("50.004"),
            freshness_score=Decimal("0.55"),  # < 0.60 → freshness risk aktif
            safety_status="needs_verification",  # → safety risk aktif
            storage_days=Decimal("14"),  # separuh umur telur
        )
    )
    komponen = {
        "purchase_cost": r.purchase_cost,
        "transport_cost": r.transport_cost,
        "handling_cost": r.handling_cost,
        "loss_in_storage": r.loss_in_storage,
        "freshness_risk_penalty": r.freshness_risk_penalty,
        "safety_risk_penalty": r.safety_risk_penalty,
        "total": r.total,
    }
    for nama, nilai in komponen.items():
        eksponen = nilai.as_tuple().exponent
        assert isinstance(eksponen, int) and -eksponen <= 2, f"{nama} tidak 2dp: {nilai}"

    # nilai terbulatkan HALF_UP, bukan dipotong
    assert r.freshness_risk_penalty == Decimal("514.40")  # 12.345,67 × 0,5 × (0,05÷0,6)
    assert r.safety_risk_penalty == Decimal("1234.57")  # 1234.567
    assert r.transport_cost == Decimal("150.01")  # 150.005
    assert r.handling_cost == Decimal("50.00")  # 50.004
    assert r.loss_in_storage == Decimal("246.91")  # 12.345,67 × 0,04 × 0,5

    # breakdown tetap menjumlah persis ke total
    assert (
        r.purchase_cost
        + r.transport_cost
        + r.handling_cost
        + r.loss_in_storage
        + r.freshness_risk_penalty
        + r.safety_risk_penalty
        == r.total
    )
