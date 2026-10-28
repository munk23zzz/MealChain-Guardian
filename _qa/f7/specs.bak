"""Spesifikasi kasus replay/realtime — SATU daftar yang dibaca generator.

Rencana MG Fase 7 (`phase-07-realtime-scenarios.md`) meminta `ScenarioCaseSpec`
sebagai bentuk deklarasi kasus, lalu generator yang menghasilkan seluruh baris
berelasi dari spec itu. Modul ini hanya berisi DATA (tanpa I/O, tanpa DB) supaya
bisa diuji cepat dan supaya tidak ada dua tempat yang mendefinisikan kasus.

Dua jenis kasus:

- **scripted** — empat kasus cerita yang sudah dipakai demo (penolakan berulang,
  shortage, pemasok janggal, gangguan logistik). Isi ceritanya (jejak, alasan
  tolak, bukti) tetap ditulis `api/demo.py`; yang diambil dari sini adalah
  IDENTITAS kasus dan waktu kejadiannya, supaya replay bisa direproduksi dan
  realtime tidak bertabrakan dengan replay.
- **commodity** — kasus yang menguji KOMODITAS, bukan cerita: satu rantai dingin
  dengan bukti sah (`usable`), satu rantai dingin dengan bukti tidak cukup
  (`on_hold` — sengaja, untuk didemokan), dan satu ambient (beras) yang hanya
  boleh ada bila profil ambient memang aktif.

Semua offset waktu NEGATIF atau nol relatif `evaluation_anchor`, kecuali
`needed_by` yang memang TENGGAT (bukan peristiwa): sebuah kebutuhan boleh
"dibutuhkan sebelum besok" sementara panen dan log suhunya sudah terjadi.
Aturan yang dijaga generator: peristiwa simulasi (panen, log, jejak, keputusan)
tidak pernah berada di masa depan relatif jangkar, dan `needed_by` tidak pernah
melewati `usable_until` batch yang dipakai.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "BATCH_ON_HOLD",
    "BATCH_PASS",
    "KIND_COMMODITY",
    "KIND_SCRIPTED",
    "SCENARIO_CASES",
    "SCENARIO_VERSION",
    "BatchSpec",
    "ScenarioCaseSpec",
    "spec_untuk",
]

#: Versi skenario ikut masuk ke identitas baris. Naikkan bila isi kasus berubah
#: sehingga data lama tidak "dipakai ulang" sebagai generasi yang sama.
SCENARIO_VERSION = "fase7-2026-10-27.v1"

KIND_SCRIPTED = "scripted"
KIND_COMMODITY = "commodity"

#: Status batch yang disengaja (nilai kolom `batches.safety_status`).
BATCH_PASS = "pass"
#: Bukti sengaja tidak cukup: kartu harus menunjukkan VERIFIKASI, bukan error.
BATCH_ON_HOLD = "needs_verification"


@dataclass(frozen=True)
class BatchSpec:
    """Rencana satu batch milik kasus.

    `usable_offset_min` dihitung dari jangkar (positif = masih layak setelah
    jangkar). Panen, kirim, dan log memakai offset negatif: semuanya peristiwa
    yang SUDAH terjadi saat dataset dievaluasi.
    """

    label: str
    quantity_kg: float
    harvest_offset_min: int
    dispatched_offset_min: int | None
    #: Interval sampel suhu (menit relatif jangkar) dan nilainya. Panjang kedua
    #: tuple harus sama — dijaga `__post_init__`.
    temperature_offsets_min: tuple[int, ...] = ()
    temperatures_c: tuple[float, ...] = ()
    #: Entri log yang SENGAJA rusak (bukan angka / tanpa timestamp). Dipakai
    #: kasus `on_hold`: bukti ada tetapi tidak bisa dipakai.
    malformed_samples: int = 0
    certificate: str = "hygiene"
    #: Status yang disengaja. `pass` hanya sah bila lognya memang sah.
    safety_status: str = BATCH_PASS

    def __post_init__(self) -> None:
        if self.quantity_kg <= 0:
            raise ValueError(f"batch {self.label}: quantity_kg harus > 0")
        if self.harvest_offset_min > 0:
            raise ValueError(f"batch {self.label}: panen tidak boleh di masa depan")
        if self.dispatched_offset_min is not None:
            if self.dispatched_offset_min > 0:
                raise ValueError(f"batch {self.label}: kirim tidak boleh di masa depan")
            if self.dispatched_offset_min < self.harvest_offset_min:
                raise ValueError(f"batch {self.label}: kirim sebelum panen")
        if len(self.temperature_offsets_min) != len(self.temperatures_c):
            raise ValueError(
                f"batch {self.label}: jumlah offset suhu != jumlah sampel"
            )
        if any(offset > 0 for offset in self.temperature_offsets_min):
            raise ValueError(f"batch {self.label}: sampel suhu tidak boleh di masa depan")
        if self.malformed_samples < 0:
            raise ValueError(f"batch {self.label}: malformed_samples tidak boleh negatif")
        if self.safety_status not in (BATCH_PASS, BATCH_ON_HOLD, "pending", "fail"):
            raise ValueError(
                f"batch {self.label}: safety_status tidak dikenal: {self.safety_status!r}"
            )


@dataclass(frozen=True)
class ScenarioCaseSpec:
    """Deklarasi satu kasus demo.

    Bentuknya mengikuti rencana: `key, commodity, source_location,
    target_location, supplier, quantity_kg, batch_specs[], harvest_offset,
    demand_needed_by_offset, temperature_log_offsets[], price_signals[],
    logistics_override, intended_outcome`.
    """

    key: str
    kind: str
    commodity: str
    #: Kota tujuan kasus. Daftar kandidat sumber dipilih seeder (pulau + jarak),
    #: sama seperti empat kasus cerita; spec hanya menyatakan preferensinya.
    target_location: str
    source_candidates: tuple[str, ...]
    quantity_kg: float
    intended_outcome: str
    #: Jenis keputusan yang lahir dari kasus ini (`None` = kasus data/batch saja).
    decision_type: str | None = None
    #: Status keputusan yang lahir (hanya kasus komoditas yang memakai ini).
    decision_status: str | None = None
    #: Offset `generated_at` keputusan (negatif = sebelum jangkar).
    decision_offset_min: int = -45
    #: Offset TENGGAT kebutuhan (`demand_records.needed_by`), relatif jangkar.
    demand_needed_by_offset_min: int | None = None
    #: Offset `recorded_at` baris kebutuhan, relatif jangkar. WAJIB BERBEDA
    #: untuk kasus dengan komoditas+kota yang sama: kunci unik tabel
    #: `demand_records` adalah (lokasi, komoditas, recorded_at), jadi dua kasus
    #: wortel pada jam yang sama akan saling menimpa — kebutuhan 420 kg/8 jam
    #: hilang dan hanya 380 kg/6 jam yang tersisa.
    demand_recorded_offset_min: int = -30
    #: Harga acuan (PIHPS) untuk kasus ini, rupiah per kg.
    price_per_kg: float | None = None
    price_offset_min: int | None = None
    batches: tuple[BatchSpec, ...] = ()
    #: Catatan kebijakan yang dibawa ke laporan/UI (bukan dihitung ulang).
    policy_note: str = ""

    def __post_init__(self) -> None:
        if self.kind not in (KIND_SCRIPTED, KIND_COMMODITY):
            raise ValueError(f"kasus {self.key}: kind tidak dikenal: {self.kind!r}")
        if self.intended_outcome not in ("usable", "on_hold", "quarantined", "rejected"):
            raise ValueError(
                f"kasus {self.key}: intended_outcome tidak dikenal: "
                f"{self.intended_outcome!r}"
            )
        if self.quantity_kg <= 0:
            raise ValueError(f"kasus {self.key}: quantity_kg harus > 0")
        if self.decision_offset_min > 0:
            raise ValueError(f"kasus {self.key}: keputusan tidak boleh di masa depan")
        if self.price_offset_min is not None and self.price_offset_min > 0:
            raise ValueError(f"kasus {self.key}: sinyal harga tidak boleh di masa depan")
        if self.demand_recorded_offset_min > 0:
            raise ValueError(
                f"kasus {self.key}: pencatatan kebutuhan tidak boleh di masa depan"
            )
        if self.kind == KIND_COMMODITY and not self.batches:
            raise ValueError(f"kasus {self.key}: kasus komoditas wajib punya batch")


#: Empat kasus cerita: identitas + waktu datang dari sini, isi cerita dari
#: `api/demo.py` (jejak dan bukti tidak diduplikasi).
_SCRIPTED: tuple[ScenarioCaseSpec, ...] = (
    ScenarioCaseSpec(
        key="rejection-loop-kuota",
        kind=KIND_SCRIPTED,
        commodity="telur",
        target_location="Jakarta",
        source_candidates=("Cianjur", "Bogor", "Surabaya"),
        quantity_kg=600.0,
        intended_outcome="rejected",
        decision_type="supplier_procurement",
        decision_offset_min=-150,
        policy_note="kuota SPPG penuh -> negosiasi ulang -> skema bertahap",
    ),
    ScenarioCaseSpec(
        key="shortage-darurat",
        kind=KIND_SCRIPTED,
        commodity="telur",
        target_location="Jakarta",
        source_candidates=("Bogor", "Cianjur", "Surabaya"),
        quantity_kg=780.0,
        intended_outcome="on_hold",
        decision_type="safety_disruption",
        decision_offset_min=-25,
        policy_note="shortage 780 kg, jendela keamanan 30 menit",
    ),
    ScenarioCaseSpec(
        key="supplier-janggal",
        kind=KIND_SCRIPTED,
        commodity="telur",
        target_location="Jakarta",
        source_candidates=("Cianjur", "Bogor", "Surabaya"),
        quantity_kg=600.0,
        intended_outcome="on_hold",
        decision_type="price_anomaly",
        decision_offset_min=-40,
        policy_note="harga 40% di bawah referensi -> verifier FLAGGED",
    ),
    ScenarioCaseSpec(
        key="gangguan-logistik",
        kind=KIND_SCRIPTED,
        commodity="telur",
        target_location="Jakarta",
        source_candidates=("Bogor", "Cianjur", "Surabaya"),
        quantity_kg=600.0,
        intended_outcome="on_hold",
        decision_type="safety_disruption",
        decision_offset_min=-60,
        policy_note="rute banjir -> sumber alternatif Cianjur",
    ),
)

#: Kasus komoditas (Fase 7 butir 5 & 6).
#:
#: - `wortel-coldchain-sah`  : rantai dingin, log sah (5 sampel 0-8 °C, <= 6 jam
#:   sebelum jangkar) -> `pass` -> `usable`.
#: - `wortel-coldchain-hold` : rantai dingin, HANYA satu sampel sah + dua entri
#:   rusak -> bukti tidak cukup -> `needs_verification` -> `on_hold` (bukan
#:   error provider, bukan kegagalan aplikasi).
#: - `beras-ambient`         : beras (profil ambient) -> tidak diukur excursion,
#:   log suhu ruang 27 °C sah sebagai catatan, bukan penilaian rantai dingin.
#:
#: Ketiganya memakai kota tujuan Jakarta (kota demo utama) dan sumber di pulau
#: yang sama, sama seperti aturan empat kasus cerita.
_COMMODITY: tuple[ScenarioCaseSpec, ...] = (
    ScenarioCaseSpec(
        key="wortel-coldchain-sah",
        kind=KIND_COMMODITY,
        commodity="wortel",
        target_location="Jakarta",
        source_candidates=("Bogor", "Cianjur", "Bandung"),
        quantity_kg=420.0,
        intended_outcome="usable",
        decision_type="supplier_procurement",
        decision_status="pending_approval",
        decision_offset_min=-60,
        # Tenggat kebutuhan 8 jam setelah jangkar: tiba jauh sebelum tenggat,
        # dan batch masih layak (masa layak wortel 21 hari).
        demand_needed_by_offset_min=8 * 60,
        demand_recorded_offset_min=-30,
        price_per_kg=12500.0,
        price_offset_min=-90,
        batches=(
            BatchSpec(
                label="wortel-sah",
                quantity_kg=420.0,
                harvest_offset_min=-420,
                dispatched_offset_min=-300,
                temperature_offsets_min=(-330, -270, -210, -150, -90),
                temperatures_c=(3.4, 3.8, 4.1, 3.2, 3.9),
                certificate="hygiene",
                safety_status=BATCH_PASS,
            ),
        ),
        policy_note=(
            "rantai dingin 0-8 °C, 5 sampel dalam 6 jam terakhir, "
            "masa layak 21 hari (policy simulated_policy)"
        ),
    ),
    ScenarioCaseSpec(
        key="wortel-coldchain-hold",
        kind=KIND_COMMODITY,
        commodity="wortel",
        target_location="Jakarta",
        source_candidates=("Bogor", "Cianjur", "Bandung"),
        quantity_kg=380.0,
        intended_outcome="on_hold",
        decision_type="supplier_procurement",
        decision_status="pending_approval",
        decision_offset_min=-50,
        demand_needed_by_offset_min=6 * 60,
        # Beda 7 menit dari kasus wortel sah: kunci unik `demand_records`
        # (lokasi, komoditas, recorded_at) tidak boleh membuat dua kebutuhan
        # wortel saling menimpa.
        demand_recorded_offset_min=-23,
        price_per_kg=12800.0,
        price_offset_min=-80,
        batches=(
            BatchSpec(
                label="wortel-bukti-kurang",
                quantity_kg=380.0,
                harvest_offset_min=-360,
                dispatched_offset_min=-240,
                # Satu sampel sah + dua entri rusak: profil menuntut >= 2 sampel,
                # jadi bukti TIDAK cukup untuk `pass` — inilah `on_hold`.
                temperature_offsets_min=(-120,),
                temperatures_c=(4.2,),
                malformed_samples=2,
                certificate="hygiene",
                safety_status=BATCH_ON_HOLD,
            ),
        ),
        policy_note=(
            "bukti suhu tidak cukup (1 sampel sah < minimum 2 + 2 entri rusak) "
            "-> needs_verification, bukan error"
        ),
    ),
    ScenarioCaseSpec(
        key="beras-ambient",
        kind=KIND_COMMODITY,
        commodity="beras",
        target_location="Jakarta",
        source_candidates=("Bogor", "Cianjur", "Bandung"),
        quantity_kg=600.0,
        intended_outcome="usable",
        decision_type="supplier_procurement",
        decision_status="pending_approval",
        decision_offset_min=-55,
        demand_needed_by_offset_min=12 * 60,
        demand_recorded_offset_min=-35,
        price_per_kg=14200.0,
        price_offset_min=-120,
        batches=(
            BatchSpec(
                label="beras-ambient",
                quantity_kg=600.0,
                harvest_offset_min=-1440,
                dispatched_offset_min=-720,
                # Suhu ruang: sah sebagai CATATAN, tetapi profil ambient tidak
                # mengukur excursion — jangan dinilai dengan rentang 0-8 °C.
                temperature_offsets_min=(-480, -240),
                temperatures_c=(27.0, 26.6),
                certificate="hygiene",
                safety_status=BATCH_PASS,
            ),
        ),
        policy_note=(
            "komoditas ambient: cold_chain_required=false, tidak ada rentang; "
            "log suhu ruang dicatat, bukan dinilai excursion (policy simulated_policy)"
        ),
    ),
)

SCENARIO_CASES: tuple[ScenarioCaseSpec, ...] = _SCRIPTED + _COMMODITY

_BY_KEY = {spec.key: spec for spec in SCENARIO_CASES}


def spec_untuk(key: str) -> ScenarioCaseSpec:
    """Spec untuk satu kunci kasus; kunci asing ditolak (bukan ditebak)."""
    try:
        return _BY_KEY[key]
    except KeyError:
        raise KeyError(
            f"kasus skenario tidak dikenal: {key!r}; "
            f"tersedia: {', '.join(sorted(_BY_KEY))}"
        ) from None


def kasus_komoditas() -> tuple[ScenarioCaseSpec, ...]:
    """Kasus yang menguji komoditas (bukan cerita)."""
    return tuple(spec for spec in SCENARIO_CASES if spec.kind == KIND_COMMODITY)


def kasus_scripted() -> tuple[ScenarioCaseSpec, ...]:
    """Kasus cerita (empat kasus demo lama)."""
    return tuple(spec for spec in SCENARIO_CASES if spec.kind == KIND_SCRIPTED)
