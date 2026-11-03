"""Evaluator kelayakan batch — SATU definisi untuk rekomendasi, approval,
dispatch, dan penerimaan barang (Fase 4 MG, poin 2 dan 4).

Modul ini MURNI: tanpa FastAPI, tanpa SQLAlchemy, tanpa I/O. Pemanggil
menyuplai data batch (Mapping atau objek ber-atribut) dan policy; keluarannya
`BatchEvaluation` yang membawa kode alasan stabil untuk API (409) dan UI.

Kenapa ada modul ini: sebelum Fase 4, tiga jalur memakai aturan berbeda —
`penghalang_sumber` meloloskan `pending`/`needs_verification`,
`receipt_blokir_alasan` menuntut bukti suhu lengkap, dan generator kandidat
hanya membuang `fail`/`quarantined`. Akibatnya batch yang belum terbukti aman
bisa dieksekusi lalu diterima sebagai stok `usable`.

Aturan (fail-closed, urutan kode di `blocking_reasons` tetap deterministik):

1. karantina (`quarantined`/`failed`) → `quarantined`
2. `usable_until` kosong → `expiry_unknown` (tidak terbukti layak)
3. `usable_until` sudah lewat → `batch_expired`
4. safety `fail` → `safety_fail`
5. safety `pending` → `safety_pending` (on_hold, bukan lolos)
6. safety `needs_verification` → `safety_needs_verification` (on_hold)
7. safety tak dikenal → `safety_status_unknown` (on_hold)
8. bukti yang disyaratkan policy tidak ada → `evidence_missing`
9. bukti suhu tidak lengkap → `temperature_evidence_incomplete` (on_hold)
10. freshness `fail` → `freshness_fail`
11. `usable_until` < `arrival_due_at` → `expired_before_arrival`
12. delivery window terlampaui → `delivery_window_exceeded`

`expiry_unknown` sengaja memblokir: `usable_until` NULL berarti tidak ada
provenance masa layak, dan "tidak dapat dibuktikan" tidak sama dengan "aman".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Mapping

from app.core import quarantine as karantina
from app.core.temperature import summarize_temperature_log

__all__ = [
    "BatchEvaluation",
    "BatchNotEligible",
    "BatchPolicy",
    "EvidenceFusion",
    "POLICY_BAWAAN",
    "REJECTED",
    "ON_HOLD",
    "QUARANTINED",
    "USABLE",
    "assert_dispatchable",
    "batch_policy_from",
    "evaluate_batch",
    "fuse_evidence",
    "partition_batches",
]

USABLE = "usable"
ON_HOLD = "on_hold"
REJECTED = "rejected"
QUARANTINED = "quarantined"

SAFETY_FAIL = "safety_fail"
SAFETY_PENDING = "safety_pending"
SAFETY_NEEDS_VERIFICATION = "safety_needs_verification"
SAFETY_STATUS_UNKNOWN = "safety_status_unknown"
EVIDENCE_MISSING = "evidence_missing"
TEMPERATURE_INCOMPLETE = "temperature_evidence_incomplete"
FRESHNESS_FAIL = "freshness_fail"
BATCH_EXPIRED = "batch_expired"
EXPIRY_UNKNOWN = "expiry_unknown"
EXPIRED_BEFORE_ARRIVAL = "expired_before_arrival"
DELIVERY_WINDOW_EXCEEDED = "delivery_window_exceeded"
QUARANTINE_BLOCK = "quarantined"

#: Peringkat keparahan; status akhir = yang terparah.
_RANK = {USABLE: 0, ON_HOLD: 1, REJECTED: 2, QUARANTINED: 3}


@dataclass(frozen=True)
class BatchPolicy:
    """Aturan kelayakan yang disuplai pemanggil — bukan dibaca dari UI.

    `required_evidence` berisi nama bukti yang wajib ada (mis.
    `temperature_log`, `harvest_record`). Daftar per komoditas BELUM diputuskan
    pemilik data; karena itu nilai bawaannya kosong dan modul ini tidak
    mengarang profil bukti per komoditas.
    """

    policy_version: str = "batch-policy-v1"
    safe_min_c: float = 0.0
    safe_max_c: float = 8.0
    required_evidence: tuple[str, ...] = ()
    require_temperature_log: bool = True


POLICY_BAWAAN = BatchPolicy()


@dataclass(frozen=True)
class BatchEvaluation:
    batch_id: str | None
    status: str
    blocking_reasons: tuple[str, ...]
    policy_version: str
    evaluation_time: datetime
    arrival_due_at: datetime | None

    @property
    def code(self) -> str | None:
        """Kode alasan pertama (untuk pesan 409), atau None bila usable."""
        return self.blocking_reasons[0] if self.blocking_reasons else None

    @property
    def dispatchable(self) -> bool:
        return self.status == USABLE


class BatchNotEligible(Exception):  # noqa: N818  (nama domain; API memetakannya ke 409)
    """Kegagalan kelayakan dengan kode stabil; dipetakan ke 409 di API."""

    def __init__(self, reasons: Iterable[str]):
        self.reasons = tuple(reasons)
        if not self.reasons:
            raise ValueError("BatchNotEligible butuh minimal satu alasan")
        super().__init__(self.reasons[0])

    @property
    def code(self) -> str:
        return self.reasons[0]


def _nilai(objek: Any, kunci: str) -> Any:
    if isinstance(objek, Mapping):
        return objek.get(kunci)
    return getattr(objek, kunci, None)


def _teks(nilai: Any) -> str:
    return str(nilai or "").strip().lower()


def _temperature_lengkap(batch: Any, policy: BatchPolicy, waktu: datetime) -> bool | None:
    """True/False bila bukti suhu bisa dinilai; None bila tidak ada bukti sama sekali.

    `temperature_evidence_complete` (precomputed oleh service yang membaca
    JSONB) menang supaya pipeline rekomendasi tidak perlu membawa log penuh.
    """
    precomputed = _nilai(batch, "temperature_evidence_complete")
    if precomputed is not None:
        return bool(precomputed)
    log = _nilai(batch, "temperature_log")
    if log is None:
        return None
    ringkasan = summarize_temperature_log(
        list(log), policy.safe_min_c, policy.safe_max_c
    )
    return bool(ringkasan.complete) and ringkasan.observed_minutes > 0


def evaluate_batch(
    batch: Any,
    policy: BatchPolicy | None = None,
    evaluation_time: datetime | None = None,
    arrival_due_at: datetime | None = None,
) -> BatchEvaluation:
    """Nilai satu batch. Semua argumen waktu WAJIB dari pemanggil (bukan UI)."""
    policy = policy or POLICY_BAWAAN
    if evaluation_time is None:
        raise ValueError("evaluation_time wajib diisi pemanggil")
    waktu = evaluation_time

    alasan: list[str] = []
    status = USABLE

    def tambah(kode: str, nilai_status: str) -> None:
        nonlocal status
        alasan.append(kode)
        if _RANK[nilai_status] > _RANK[status]:
            status = nilai_status

    # 1-2. Karantina dan umur layak: fakta paling tegas lebih dulu.
    if _teks(_nilai(batch, "quarantine_status")) in (karantina.QUARANTINED, karantina.FAILED):
        tambah(QUARANTINE_BLOCK, QUARANTINED)

    usable_until = _nilai(batch, "usable_until")
    if usable_until is None:
        tambah(EXPIRY_UNKNOWN, REJECTED)
    elif usable_until < waktu:
        tambah(BATCH_EXPIRED, REJECTED)

    # 3-6. Status keamanan pangan.
    safety = _teks(_nilai(batch, "safety_status"))
    if safety == "fail":
        tambah(SAFETY_FAIL, REJECTED)
    elif safety == "pending":
        tambah(SAFETY_PENDING, ON_HOLD)
    elif safety == "needs_verification":
        tambah(SAFETY_NEEDS_VERIFICATION, ON_HOLD)
    elif safety != "pass":
        tambah(SAFETY_STATUS_UNKNOWN, ON_HOLD)

    # 7. Bukti yang disyaratkan policy.
    bukti = {_teks(nama) for nama in (_nilai(batch, "evidence") or ())}
    hilang = [
        nama
        for nama in policy.required_evidence
        if _teks(nama) not in bukti
    ]
    if hilang:
        tambah(EVIDENCE_MISSING, REJECTED)

    # 8. Bukti suhu: kurang → on_hold (bukan pass), tidak ada sama sekali → bukti hilang.
    if policy.require_temperature_log:
        suhu = _temperature_lengkap(batch, policy, waktu)
        if suhu is False:
            tambah(TEMPERATURE_INCOMPLETE, ON_HOLD)
        elif suhu is None:
            tambah(EVIDENCE_MISSING, REJECTED)

    # 9. Freshness.
    if _teks(_nilai(batch, "freshness_status")) == "fail":
        tambah(FRESHNESS_FAIL, REJECTED)

    # 10. Barang harus masih layak saat TIBA, bukan hanya saat dievaluasi.
    if arrival_due_at is not None and usable_until is not None and usable_until < arrival_due_at:
        tambah(EXPIRED_BEFORE_ARRIVAL, REJECTED)

    # 11. Delivery window (dihitung service dari needed_by, bukan dari UI).
    if bool(_nilai(batch, "delivery_window_exceeded")):
        tambah(DELIVERY_WINDOW_EXCEEDED, REJECTED)

    return BatchEvaluation(
        batch_id=_nilai(batch, "batch_id") or _nilai(batch, "id"),
        status=status,
        blocking_reasons=tuple(alasan),
        policy_version=policy.policy_version,
        evaluation_time=evaluation_time,
        arrival_due_at=arrival_due_at,
    )


def assert_dispatchable(evaluation: BatchEvaluation) -> None:
    """Lempar `BatchNotEligible` bila hasil evaluasi belum `usable`."""
    if not evaluation.dispatchable:
        raise BatchNotEligible(evaluation.blocking_reasons)


def partition_batches(
    batches: Iterable[Any],
    *,
    policy: BatchPolicy | None = None,
    evaluation_time: datetime,
    arrival_due_at: datetime | None = None,
) -> tuple[list[BatchEvaluation], list[BatchEvaluation], list[BatchEvaluation]]:
    """Pisahkan hasil evaluasi menjadi (usable, on_hold, ditolak).

    `on_hold` TETAP dilaporkan (untuk verifikasi manusia) tetapi tidak boleh
    masuk daftar kandidat `usable` — itu inti poin 3 Fase 4.
    """
    usable: list[BatchEvaluation] = []
    on_hold: list[BatchEvaluation] = []
    ditolak: list[BatchEvaluation] = []
    for batch in batches:
        hasil = evaluate_batch(batch, policy, evaluation_time, arrival_due_at)
        if hasil.status == USABLE:
            usable.append(hasil)
        elif hasil.status == ON_HOLD:
            on_hold.append(hasil)
        else:
            ditolak.append(hasil)
    return usable, on_hold, ditolak


def batch_policy_from(policy: Any) -> BatchPolicy:
    """Terima `BatchPolicy` (sudah kanonik) atau profil komoditas berversi.

    Fase 3 memperkenalkan `core.commodity_policy.CommodityPolicy` dengan nama
    field berbeda (`safe_temp_min_c`, `requires_temperature_evidence`). Tanpa
    penerjemah ini, pemanggil harus menyalin aturan rentang/sampel sendiri —
    persis duplikasi yang membuat "beras dinilai rantai dingin" dulu.
    """
    if isinstance(policy, BatchPolicy) or policy is None:
        return policy or POLICY_BAWAAN
    punya_rentang = getattr(policy, "has_temperature_band", None)
    if punya_rentang is not None and not punya_rentang:
        # Profil ambient (mis. beras): tidak ada rentang, tidak ada kewajiban
        # bukti suhu. Angka 0-0 di bawah tidak pernah dipakai untuk mengukur
        # excursion karena `require_temperature_log=False`.
        return BatchPolicy(
            policy_version=str(getattr(policy, "policy_version", "batch-policy-v1")),
            safe_min_c=0.0,
            safe_max_c=0.0,
            required_evidence=(),
            require_temperature_log=False,
        )
    return BatchPolicy(
        policy_version=str(getattr(policy, "policy_version", "batch-policy-v1")),
        safe_min_c=float(getattr(policy, "safe_temp_min_c", 0.0) or 0.0),
        safe_max_c=float(getattr(policy, "safe_temp_max_c", 8.0) or 8.0),
        required_evidence=(),
        require_temperature_log=bool(
            getattr(policy, "requires_temperature_evidence", True)
        ),
    )


@dataclass(frozen=True)
class EvidenceFusion:
    """Hasil FUSI bukti satu grup batch (Fase 6 butir 1).

    Sebelum ini generator kandidat hanya membuang `fail`/`quarantined` lalu
    menjumlahkan seluruh batch sisanya — batch yang buktinya tidak lengkap
    (`pending`, `needs_verification`, log suhu kosong) tetap menyumbang
    kilogram dan muncul sebagai usulan "aman". Hasil fusi memisahkan tiga
    keranjang secara eksplisit supaya quantity hanya diambil dari `usable`.
    """

    status: str
    usable: tuple[BatchEvaluation, ...]
    held: tuple[BatchEvaluation, ...]
    rejected: tuple[BatchEvaluation, ...]

    @property
    def unusable(self) -> tuple[BatchEvaluation, ...]:
        """`held` lalu `rejected` — urutan deterministik, tanpa duplikat."""
        return self.held + self.rejected

    @property
    def usable_batch_ids(self) -> tuple[str, ...]:
        return tuple(str(e.batch_id) for e in self.usable if e.batch_id is not None)

    @property
    def blocking_reasons(self) -> tuple[str, ...]:
        """Kode alasan unik, urut kemunculan (held lebih dulu)."""
        terlihat: list[str] = []
        for evaluasi in self.unusable:
            for kode in evaluasi.blocking_reasons:
                if kode not in terlihat:
                    terlihat.append(kode)
        return tuple(terlihat)


def fuse_evidence(
    batches: Iterable[Any],
    *,
    policy: Any = None,
    evaluation_time: datetime,
    arrival_due_at: datetime | None = None,
) -> EvidenceFusion:
    """Nilai seluruh batch satu grup lalu rangkum jadi satu kesimpulan.

    `status` = `usable` bila ADA batch yang benar-benar layak; selain itu yang
    terparah di antara yang tersisa. Grup tanpa batch sama sekali = `rejected`
    (tidak ada bukti apa pun, jadi tidak boleh lolos sebagai aman).
    """
    daftar = list(batches)
    kanonik = batch_policy_from(policy)
    usable, held, ditolak = partition_batches(
        daftar,
        policy=kanonik,
        evaluation_time=evaluation_time,
        arrival_due_at=arrival_due_at,
    )
    if usable:
        status = USABLE
    elif held or ditolak:
        status = max(
            (e.status for e in (*held, *ditolak)), key=lambda s: _RANK.get(s, 99)
        )
    else:
        status = REJECTED
    return EvidenceFusion(
        status=status,
        usable=tuple(usable),
        held=tuple(held),
        rejected=tuple(ditolak),
    )
