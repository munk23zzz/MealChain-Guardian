"""Profil komoditas berversi (Fase 3 MG) — satu sumber aturan suhu & masa layak.

Sebelum modul ini, aturan komoditas tersebar di tiga tempat yang bisa berbeda
pendapat:

- `api/freshness.py` — `_SHELF_LIFE_BY_COMMODITY` (dari `settings`);
- `core/commodity_limits.py` — peta rentang suhu (beras 15-30 °C, sisanya 0-8 °C);
- `api/safety.py` — memakai peta yang sama, tetapi tanpa `shelf_life_days`.

Nama tabel/kolom (`commodity_profile`, `commodity_policies`) sebelumnya **nol
kemunculan** di kode. Profil ini yang menjawab tiga pertanyaan yang sebelumnya
dijawab "0-8 °C untuk semua":

1. Apakah komoditas ini WAJIB rantai dingin (`cold_chain_required`)?
2. Kalau ya, rentangnya berapa — dan kalau tidak, jangan mengukur excursion?
3. Berapa sampel minimum, dan berapa usia maksimum sampel agar masih dianggap
   observasi (bukan log lama)?

`policy_kind` dipisah dari `policy_basis` supaya angka demo tidak menyamar
sebagai standar regulasi: selama rentang belum divalidasi domain owner, nilainya
`simulated_policy` dan API/UI wajib menyebutnya begitu (rencana Fase 3,
gerbang keluar butir terakhir).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

__all__ = [
    "AMBIENT",
    "COLD_CHAIN",
    "CommodityPolicy",
    "POLICY_KIND_SIMULATED",
    "POLICY_KIND_UNAVAILABLE",
    "PROFILES",
    "policy_for",
    "validate_policy_row",
]

#: Penanda dasar kebijakan (bentuk yang sama dengan `risk_method.kind` di overview).
POLICY_KIND_SIMULATED = "simulated_policy"
POLICY_KIND_UNAVAILABLE = "unavailable"

COLD_CHAIN = True
AMBIENT = False


@dataclass(frozen=True)
class CommodityPolicy:
    """Satu baris profil komoditas — immutable supaya tidak bisa diubah di tengah.

    Validasi dilakukan di `__post_init__` (bukan di pemanggil) karena profil
    dipakai core, API, seed, dan Joule: satu tempat yang menolak, semuanya
    terlindungi. Profil cacat yang lolos ke DB akan membuat evaluasi batch
    menjawab dengan angka yang tidak bisa dipertanggungjawabkan.
    """

    commodity: str
    cold_chain_required: bool
    safe_temp_min_c: float | None
    safe_temp_max_c: float | None
    shelf_life_days: float
    min_temperature_samples: int
    policy_version: str
    policy_basis: str
    policy_kind: str = POLICY_KIND_SIMULATED
    #: Usia maksimum sampel terakhir agar masih dianggap observasi. ``None`` =
    #: komoditas ambient tanpa kewajiban bukti suhu (tidak pernah "stale").
    max_observation_age_minutes: int | None = None
    #: Ambang excursion yang membuat safety `fail` (menit). Default sama dengan
    #: `core/safety.py` supaya dua tempat tidak memakai ambang berbeda.
    max_excursion_minutes: float = 30.0

    def __post_init__(self) -> None:
        nama = (self.commodity or "").strip()
        if not nama:
            raise ValueError("commodity wajib diisi")
        if not (self.policy_version or "").strip():
            raise ValueError("policy_version wajib diisi")
        if not (self.policy_basis or "").strip():
            raise ValueError("policy_basis wajib diisi")
        if self.policy_kind not in (POLICY_KIND_SIMULATED, POLICY_KIND_UNAVAILABLE):
            raise ValueError(
                f"policy_kind tidak dikenal: {self.policy_kind!r}; "
                f"pilihan: {POLICY_KIND_SIMULATED}, {POLICY_KIND_UNAVAILABLE}"
            )

        # `shelf_life_days <= 0` membuat skor kesegaran mustahil dihitung
        # (pembagian nol / umur negatif). Ditolak di sini, bukan dihitung.
        if not _finite(self.shelf_life_days) or self.shelf_life_days <= 0:
            raise ValueError("shelf_life_days harus > 0")

        if self.min_temperature_samples < 0:
            raise ValueError("min_temperature_samples harus >= 0")
        if not isinstance(self.min_temperature_samples, int):
            raise ValueError("min_temperature_samples harus bilangan bulat")

        if self.max_observation_age_minutes is not None and (
            self.max_observation_age_minutes <= 0
        ):
            raise ValueError("max_observation_age_minutes harus > 0 bila diisi")
        if not _finite(self.max_excursion_minutes) or self.max_excursion_minutes <= 0:
            raise ValueError("max_excursion_minutes harus > 0")

        punya_min = self.safe_temp_min_c is not None
        punya_max = self.safe_temp_max_c is not None
        if punya_min != punya_max:
            raise ValueError(
                "safe_temp_min_c dan safe_temp_max_c harus diisi bersama atau kosong bersama"
            )
        if punya_min and punya_max:
            bawah = self.safe_temp_min_c
            atas = self.safe_temp_max_c
            assert bawah is not None and atas is not None  # ditegakkan di atas
            if not _finite(bawah) or not _finite(atas):
                raise ValueError("rentang suhu harus bilangan hingga")
            if bawah > atas:
                raise ValueError(
                    "safe_temp_min_c tidak boleh lebih besar dari safe_temp_max_c"
                )

        if self.cold_chain_required and not punya_min:
            raise ValueError(
                "komoditas rantai dingin wajib punya safe_temp_min_c/safe_temp_max_c"
            )
        if self.cold_chain_required and self.min_temperature_samples < 2:
            # Satu sampel tidak bisa membentuk interval; menuntut minimal dua
            # membuat "bukti cukup" berarti sesuatu yang bisa diukur.
            raise ValueError(
                "komoditas rantai dingin butuh min_temperature_samples >= 2"
            )
        # CATATAN: `max_observation_age_minutes` sengaja TIDAK diwajibkan di sini.
        # Profil sintetis untuk pemanggil lama (`compute_freshness_score` bentuk
        # posisional) tidak punya gagasan "usia maksimum sampel", dan mengarang
        # angkanya justru yang dilarang rencana. Kewajiban itu ditegakkan di
        # `validate_policy_row` — batas migrasi/API, tempat profil nyata masuk.

    # ── turunan ────────────────────────────────────────────────────────────

    @property
    def has_temperature_band(self) -> bool:
        """True bila profil punya rentang suhu yang bisa dipakai mengukur excursion."""
        return self.safe_temp_min_c is not None and self.safe_temp_max_c is not None

    @property
    def temp_band(self) -> tuple[float, float] | None:
        if self.safe_temp_min_c is None or self.safe_temp_max_c is None:
            return None
        return (float(self.safe_temp_min_c), float(self.safe_temp_max_c))

    @property
    def requires_temperature_evidence(self) -> bool:
        """Bukti suhu diminta hanya bila komoditas memang rantai dingin."""
        return self.cold_chain_required and self.has_temperature_band

    def to_dict(self) -> dict:
        """Bentuk yang dikirim API (dan dibaca Joule) — satu nama, bukan dua."""
        return {
            "commodity": self.commodity,
            "cold_chain_required": self.cold_chain_required,
            "safe_temp_min_c": self.safe_temp_min_c,
            "safe_temp_max_c": self.safe_temp_max_c,
            "shelf_life_days": self.shelf_life_days,
            "min_temperature_samples": self.min_temperature_samples,
            "max_observation_age_minutes": self.max_observation_age_minutes,
            "max_excursion_minutes": self.max_excursion_minutes,
            "policy_version": self.policy_version,
            "policy_basis": self.policy_basis,
            "policy_kind": self.policy_kind,
        }

    def with_overrides(self, **nilai) -> CommodityPolicy:
        """Salinan dengan sebagian nilai diganti (dipakai migrasi/tes)."""
        return replace(self, **nilai)


def _finite(nilai: float) -> bool:
    return isinstance(nilai, int | float) and nilai == nilai and abs(nilai) != float("inf")


#: Dasar kebijakan yang dipakai semua profil di bawah. Angka suhu/umur simpan
#: BELUM divalidasi domain owner, jadi tidak boleh disebut standar regulasi.
_BASIS = (
    "Asumsi demo (belum divalidasi domain owner): masa layak dari seed "
    "`data/seed/sprint1_seed.json`, rentang suhu dari praktik rantai dingin "
    "SPPG. Ditandai simulated_policy agar tidak terbaca sebagai regulasi."
)

_VERSI = "sim-2026-10-27.v1"

#: Profil per komoditas. Kunci = nama komoditas seperti di tabel `commodities`.
PROFILES: dict[str, CommodityPolicy] = {
    "telur": CommodityPolicy(
        commodity="telur",
        cold_chain_required=COLD_CHAIN,
        safe_temp_min_c=0.0,
        safe_temp_max_c=8.0,
        shelf_life_days=28.0,
        min_temperature_samples=2,
        max_observation_age_minutes=6 * 60,
        policy_version=_VERSI,
        policy_basis=_BASIS,
    ),
    "ayam": CommodityPolicy(
        commodity="ayam",
        cold_chain_required=COLD_CHAIN,
        safe_temp_min_c=0.0,
        safe_temp_max_c=8.0,
        shelf_life_days=5.0,
        min_temperature_samples=2,
        max_observation_age_minutes=6 * 60,
        policy_version=_VERSI,
        policy_basis=_BASIS,
    ),
    "wortel": CommodityPolicy(
        commodity="wortel",
        cold_chain_required=COLD_CHAIN,
        safe_temp_min_c=0.0,
        safe_temp_max_c=8.0,
        shelf_life_days=21.0,
        min_temperature_samples=2,
        max_observation_age_minutes=6 * 60,
        policy_version=_VERSI,
        policy_basis=_BASIS,
    ),
    "beras": CommodityPolicy(
        commodity="beras",
        cold_chain_required=AMBIENT,
        # Ambient: TIDAK ada rentang. Beras disimpan pada suhu ruang 26-28 °C;
        # rentang dingin 0-8 °C akan menuduhnya excursion padahal penyimpanannya
        # benar (itu bug yang sudah diperbaiki 20 Okt lewat peta 15-30 °C).
        safe_temp_min_c=None,
        safe_temp_max_c=None,
        shelf_life_days=180.0,
        min_temperature_samples=0,
        max_observation_age_minutes=None,
        policy_version=_VERSI,
        policy_basis=_BASIS,
    ),
}


def policy_for(commodity: str | None) -> CommodityPolicy:
    """Profil untuk satu nama komoditas.

    Komoditas tak dikenal DITOLAK (`KeyError`), bukan diberi rentang bawaan:
    bawaan 0-8 °C untuk semua itulah sumber bug "beras dinilai fail". Pemanggil
    yang tidak tahu komoditasnya harus memutuskan sendiri, bukan mewarisi aturan
    rantai dingin tanpa dasar.
    """
    kunci = (commodity or "").strip().lower()
    if kunci not in PROFILES:
        raise KeyError(
            f"komoditas {commodity!r} belum punya profil; "
            f"tersedia: {', '.join(sorted(PROFILES))}"
        )
    return PROFILES[kunci]


def validate_policy_row(row: dict) -> CommodityPolicy:
    """Bangun profil dari satu baris DB/seed, menolak yang cacat.

    Dipakai migrasi (validasi data sebelum/sesudah tulis) dan seed, supaya
    nilai cacat tidak pernah masuk tabel. `ValueError` membawa nama kolomnya.
    """
    wajib = (
        "commodity",
        "cold_chain_required",
        "shelf_life_days",
        "min_temperature_samples",
        "policy_version",
        "policy_basis",
    )
    kurang = [kolom for kolom in wajib if kolom not in row]
    if kurang:
        raise ValueError(f"baris profil kehilangan kolom: {', '.join(kurang)}")
    # Batas usia sampel WAJIB untuk komoditas rantai dingin di sini (bukan di
    # konstruktor): hanya baris profil nyata yang harus menyatakannya, sedangkan
    # profil sintetis pemanggil lama tidak punya gagasan itu.
    if bool(row["cold_chain_required"]) and row.get("max_observation_age_minutes") is None:
        raise ValueError(
            "komoditas rantai dingin wajib punya max_observation_age_minutes"
        )
    return CommodityPolicy(
        commodity=str(row["commodity"]),
        cold_chain_required=bool(row["cold_chain_required"]),
        safe_temp_min_c=(
            None if row.get("safe_temp_min_c") is None else float(row["safe_temp_min_c"])
        ),
        safe_temp_max_c=(
            None if row.get("safe_temp_max_c") is None else float(row["safe_temp_max_c"])
        ),
        shelf_life_days=float(row["shelf_life_days"]),
        min_temperature_samples=int(row["min_temperature_samples"]),
        max_observation_age_minutes=(
            None
            if row.get("max_observation_age_minutes") is None
            else int(row["max_observation_age_minutes"])
        ),
        max_excursion_minutes=float(row.get("max_excursion_minutes") or 30.0),
        policy_version=str(row["policy_version"]),
        policy_basis=str(row["policy_basis"]),
        policy_kind=str(row.get("policy_kind") or POLICY_KIND_SIMULATED),
    )
