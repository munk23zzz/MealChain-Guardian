"""Safe Delivered Cost engine deterministik (Task 6 Sprint 2).

Kontrak terkunci (plan Task 6):
total = Purchase + Transport + Handling + Expected Loss
        + Freshness Risk Penalty + Safety Risk Penalty

Ruling (ledger 2026-10-05, dicatat sebelum eksekusi):
- freshness_risk = purchase × 0.50 bila freshness < 0.60, else 0.
- safety_risk = purchase × 0.10 bila safety needs_verification, else 0
  (pending/pass = 0; FAIL ditolak SEBELUM perhitungan — ValueError —
  tidak pernah dihitung, tidak pernah diranking).
- Rounding HALF_UP 2dp per komponen; total = jumlah komponen terbulatkan,
  sehingga breakdown selalu menjumlah persis ke total (audit-proof).
- Semua nilai uang diterima apa adanya (str/int/Decimal), tervalidasi
  non-negatif; purchase wajib > 0; freshness ∈ [0,1]; murni deterministik.

Perubahan 2026-10-29 (konsep Performance & Audit, §4–§5) — susut jadi fungsi WAKTU:
- `loss_in_storage = purchase × (laju ÷ umur_simpan) × hari_simpan`.
  Sebelumnya `purchase × 0.2 × (1 − freshness)`: satu fraksi kesegaran dipakai
  sebagai pengganti fraksi umur simpan, sehingga susut gudang bergerak karena
  MUTU KIRIMAN, bukan karena LAMA PENYIMPANAN.
- `(1 − freshness)` berhenti menjadi pengali susut. Kesegaran hanya hidup di
  dimensi kilogram (kg tidak layak saat terima → penerimaan, potongan, kg
  sortir) dan di penalti risiko — risiko bukan susut, jadi penaltinya tetap.
- Kedua fraksi TIDAK boleh dikalikan. Pemeriksaan review:
  `grep -n "loss_in_storage =" backend/app/core/safe_delivered_cost.py` tidak
  boleh memuat `freshness`.
- Dua sifat yang bisa diuji: `hari_simpan = 0` → susut nol (barang yang langsung
  dipakai tidak menyusut); `hari_simpan = umur_simpan` → susut sebesar laju
  komoditas (identitas, bukan rumus baru).

Revisi 2026-10-29b (permintaan pemilik):
- `laju` tidak lagi seragam 20%. `core/shrinkage.py` menyimpan laju per
  komoditas (beras 0,8% · telur 4% · wortel 15% · ayam 12% per umur simpan);
  20% tinggal cadangan untuk komoditas tak terdaftar dan sumbernya dilaporkan
  di `shrinkage_rate_source`. Laju 20% untuk beras berarti 20% nilai beras
  hilang dalam 180 hari — tidak masuk akal untuk komoditas kering.
- Penalti kesegaran tidak lagi cliff: `purchase × 0,50 × (0,60 − f) ÷ 0,60`
  untuk f < 0,60. Nol di 0,60 (kontinu), puncak 50% di f = 0 (besaran lama
  dipertahankan), dan f 0,599 tidak lagi melonjak dari 0 ke 50% purchase.
"""

from dataclasses import dataclass
from decimal import (
    ROUND_HALF_UP,
    Decimal,
    InvalidOperation,
)

from app.core.commodity_policy import policy_for
from app.core.shrinkage import DEFAULT_LAJU, laju_susut
from app.core.storage_window import BASIS_ASUMSI, DEFAULT_STORAGE_DAYS

__all__ = [
    "FORMULA_VERSION",
    "STORAGE_SHRINKAGE_RATE",
    "SafeDeliveredCostInputs",
    "SafeDeliveredCostResult",
    "calculate_safe_delivered_cost",
]

#: Naik setiap kali rumus/komponen berubah. Tertulis di breakdown, dibaca
#: `kpi_service` sebagai baris "Versi rumus dalam sampel", dicatat di docs.
FORMULA_VERSION = "sdc-2026.10.29b"

#: Nama lama untuk laju cadangan. Angka ini bukan lagi laju semua komoditas:
#: lihat `core/shrinkage.LAJU_SUSUT`. Dipertahankan sebagai cadangan + supaya
#: pembaca lama tidak memakai angka yang tidak lagi berarti.
STORAGE_SHRINKAGE_RATE = DEFAULT_LAJU

_FRESHNESS_RISK_FACTOR = Decimal("0.50")
_FRESHNESS_RISK_THRESHOLD = Decimal("0.60")
_SAFETY_RISK_RATE = Decimal("0.10")
_TWO_DP = Decimal("0.01")

_VALID_SAFETY = frozenset(
    {"pending", "pass", "fail", "needs_verification"}
)


def _to_decimal(value, name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{name} bukan angka valid: {value!r}") from exc


def _require_nonnegative(value, name: str) -> Decimal:
    d = _to_decimal(value, name)
    if d < 0:
        raise ValueError(f"{name} tidak boleh negatif: {d}")
    return d


@dataclass(frozen=True)
class SafeDeliveredCostInputs:
    purchase_cost: Decimal
    transport_cost: Decimal
    handling_cost: Decimal
    freshness_score: Decimal
    safety_status: str
    #: Nama komoditas (kunci profil). Dipakai mencari `shelf_life_days` bila
    #: pemanggil tidak mengirimkannya. Komoditas tak dikenal + tanpa umur
    #: simpan = ValueError, bukan angka bawaan yang dikarang.
    commodity: str | None = None
    #: Umur simpan komoditas (hari). Kosong → dari `commodity_policy`.
    shelf_life_days: Decimal | None = None
    #: Lama barang disimpan di gudang SPPG (hari). Kosong → asumsi siklus
    #: harian (`storage_window.DEFAULT_STORAGE_DAYS`), basisnya dilaporkan.
    storage_days: Decimal | None = None
    #: Asal angka `storage_days`: `rencana_menu`, `asumsi_siklus_harian`, dst.
    #: Kosong → diturunkan dari apakah `storage_days` dikirim pemanggil.
    storage_basis: str | None = None
    #: Laju susut per umur simpan. Kosong → tabel `core/shrinkage` per komoditas.
    shrinkage_rate: Decimal | None = None
    #: Asal angka laju (`tabel_laju_susut_komoditas`, `laju_default_0.2`, ...).
    shrinkage_rate_source: str | None = None

    def __post_init__(self) -> None:
        purchase = _require_nonnegative(self.purchase_cost, "purchase_cost")
        if purchase <= 0:
            raise ValueError("purchase_cost wajib > 0")
        object.__setattr__(self, "purchase_cost", purchase)
        object.__setattr__(
            self,
            "transport_cost",
            _require_nonnegative(self.transport_cost, "transport_cost"),
        )
        object.__setattr__(
            self,
            "handling_cost",
            _require_nonnegative(self.handling_cost, "handling_cost"),
        )
        freshness = _to_decimal(self.freshness_score, "freshness_score")
        if freshness < 0 or freshness > 1:
            raise ValueError(
                f"freshness_score wajib dalam [0,1], dapat {freshness}"
            )
        object.__setattr__(self, "freshness_score", freshness)
        if self.safety_status not in _VALID_SAFETY:
            raise ValueError(
                f"safety_status tidak dikenal: {self.safety_status!r}"
            )

        # ---- umur simpan: dari tabel komoditas bila tidak dikirim ----------
        if self.shelf_life_days is None:
            umur = _umur_simpan_komoditas(self.commodity)
        else:
            umur = _to_decimal(self.shelf_life_days, "shelf_life_days")
        if umur <= 0:
            raise ValueError(f"shelf_life_days wajib > 0, dapat {umur}")
        object.__setattr__(self, "shelf_life_days", umur)

        # ---- laju susut: tabel per komoditas, cadangan dilabeli -------------
        if self.shrinkage_rate is None:
            laju, sumber_laju = laju_susut(self.commodity)
        else:
            laju = _require_nonnegative(self.shrinkage_rate, "shrinkage_rate")
            if laju > 1:
                raise ValueError(
                    f"shrinkage_rate adalah fraksi per umur simpan (0..1), dapat {laju}"
                )
            sumber_laju = self.shrinkage_rate_source or "dikirim_pemanggil"
        object.__setattr__(self, "shrinkage_rate", laju)
        object.__setattr__(self, "shrinkage_rate_source", sumber_laju)

        # ---- hari simpan: tidak pernah diam-diam menjadi nol --------------
        dikirim = self.storage_days is not None
        hari = (
            _to_decimal(self.storage_days, "storage_days")
            if dikirim
            else DEFAULT_STORAGE_DAYS
        )
        if hari < 0:
            raise ValueError(f"storage_days tidak boleh negatif: {hari}")
        if hari > umur:
            # Barang tidak mungkin tersimpan lebih lama dari umur simpannya.
            hari = umur
        object.__setattr__(self, "storage_days", hari)
        if self.storage_basis is None:
            object.__setattr__(
                self,
                "storage_basis",
                "dikirim_pemanggil" if dikirim else BASIS_ASUMSI,
            )

    # ── turunan ────────────────────────────────────────────────────────────

    @property
    def daily_shrinkage_rate(self) -> Decimal:
        """`r_hari` = laju komoditas ÷ umur simpan (fraksi per hari)."""
        assert self.shelf_life_days is not None  # ditegakkan di __post_init__
        assert self.shrinkage_rate is not None
        return self.shrinkage_rate / self.shelf_life_days

    @property
    def storage_fraction(self) -> Decimal:
        """`hari_simpan ÷ umur_simpan` — fraksi umur yang benar-benar terpakai."""
        assert self.storage_days is not None and self.shelf_life_days is not None
        return self.storage_days / self.shelf_life_days


def _umur_simpan_komoditas(commodity: str | None) -> Decimal:
    """Umur simpan dari tabel profil komoditas — bukan dari kesegaran."""
    try:
        profil = policy_for(commodity)
    except KeyError as exc:
        raise ValueError(
            "shelf_life_days atau commodity wajib diisi: susut gudang dihitung "
            "dari umur simpan komoditas, dan komoditas "
            f"{commodity!r} belum punya profil"
        ) from exc
    return Decimal(str(profil.shelf_life_days))


@dataclass(frozen=True)
class SafeDeliveredCostResult:
    purchase_cost: Decimal
    transport_cost: Decimal
    handling_cost: Decimal
    #: Susut gudang — fungsi WAKTU, bukan kesegaran.
    loss_in_storage: Decimal
    freshness_risk_penalty: Decimal
    safety_risk_penalty: Decimal
    total: Decimal
    #: Alias kontrak lama: `expected_loss` == `loss_in_storage`. Dibaca
    #: `cost_breakdown["expected_loss"]`, `commercial_cost`, dan panel bukti.
    expected_loss: Decimal
    #: Jejak hitung — supaya panel audit bisa menjelaskan asal angka tanpa
    #: menghitung ulang.
    storage_days: Decimal
    shelf_life_days: Decimal
    storage_basis: str
    daily_shrinkage_rate: Decimal
    #: Laju yang benar-benar dipakai + asalnya (tabel komoditas / cadangan).
    shrinkage_rate: Decimal
    shrinkage_rate_source: str
    formula_version: str = FORMULA_VERSION


def _freshness_ramp(freshness: Decimal) -> Decimal:
    """Fraksi penalti linear: 0 di ambang, 1 di freshness 0 (bukan cliff)."""
    if freshness >= _FRESHNESS_RISK_THRESHOLD:
        return Decimal("0")
    return (_FRESHNESS_RISK_THRESHOLD - freshness) / _FRESHNESS_RISK_THRESHOLD


def calculate_safe_delivered_cost(
    inputs: SafeDeliveredCostInputs,
) -> SafeDeliveredCostResult:
    """SDC lengkap; safety fail ditolak sebelum ada angka dihitung."""
    if inputs.safety_status == "fail":
        raise ValueError(
            "batch dengan safety_status=fail tidak boleh dihitung biaya "
            "eligible-nya — hard exclusion terkunci"
        )
    # Rounding HALF_UP 2dp PER KOMPONEN (kontrak modul), lalu total = jumlah
    # komponen terbulatkan sehingga breakdown selalu menjumlah persis ke total.
    # Sebelumnya hanya expected_loss yang di-quantize: freshness/safety penalty
    # keluar tiga desimal (mis. 12.345,67 × 0,50 = 6.172,835) dan angka itu ikut
    # dipakai membandingkan biaya serta (nanti) dikirim sebagai NetPriceAmount.
    purchase = inputs.purchase_cost.quantize(_TWO_DP, rounding=ROUND_HALF_UP)
    transport = inputs.transport_cost.quantize(_TWO_DP, rounding=ROUND_HALF_UP)
    handling = inputs.handling_cost.quantize(_TWO_DP, rounding=ROUND_HALF_UP)
    # Susut gudang = purchase × laju komoditas × fraksi umur. SATU dimensi:
    # waktu. Kesegaran TIDAK muncul di sini — lihat `storage_window` untuk asal
    # `hari_simpan` dan alasannya.
    loss_in_storage = (
        purchase * inputs.shrinkage_rate * inputs.storage_fraction
    ).quantize(_TWO_DP, rounding=ROUND_HALF_UP)
    # Alias kontrak lama: kode lain (cost_breakdown, commercial_cost, panel
    # bukti) membaca `expected_loss`. Angkanya SATU, bukan dua rumus.
    expected_loss = loss_in_storage
    freshness_risk = (
        (
            purchase * _FRESHNESS_RISK_FACTOR * _freshness_ramp(inputs.freshness_score)
        ).quantize(_TWO_DP, rounding=ROUND_HALF_UP)
        if inputs.freshness_score < _FRESHNESS_RISK_THRESHOLD
        else Decimal("0.00")
    )
    safety_risk = (
        (purchase * _SAFETY_RISK_RATE).quantize(_TWO_DP, rounding=ROUND_HALF_UP)
        if inputs.safety_status == "needs_verification"
        else Decimal("0.00")
    )
    total = (
        purchase
        + transport
        + handling
        + expected_loss
        + freshness_risk
        + safety_risk
    )
    assert inputs.shelf_life_days is not None
    assert inputs.storage_days is not None
    assert inputs.storage_basis is not None
    assert inputs.shrinkage_rate is not None
    assert inputs.shrinkage_rate_source is not None
    return SafeDeliveredCostResult(
        purchase_cost=purchase,
        transport_cost=transport,
        handling_cost=handling,
        loss_in_storage=loss_in_storage,
        freshness_risk_penalty=freshness_risk,
        safety_risk_penalty=safety_risk,
        total=total,
        expected_loss=expected_loss,
        storage_days=inputs.storage_days,
        shelf_life_days=inputs.shelf_life_days,
        storage_basis=inputs.storage_basis,
        daily_shrinkage_rate=inputs.daily_shrinkage_rate,
        shrinkage_rate=inputs.shrinkage_rate,
        shrinkage_rate_source=inputs.shrinkage_rate_source,
    )
