"""Hierarki keputusan pada ranah bahan + penjelasan usulan (Fase 6).

Rencana (`MG/overview.md` §"Prioritas keputusan pada ranah bahan", Fase 6
butir 2) meminta hierarki itu menjadi **fungsi eksplisit di core**, bukan
narasi prompt. Modul ini adalah fungsi itu:

1. Keselamatan dan kelengkapan bukti.
2. Kelayakan kebutuhan bahan/menu dan waktu tiba.
3. Kontinuitas pasokan bahan.
4. Invoice dan SDC.
5. Mitigasi risiko susut.

Lapis 1-3 adalah **gerbang**: kandidat yang gagal di sana tidak boleh muncul
sebagai usulan/PO, sekalipun harganya paling murah. Lapis 4-5 adalah
**pembanding** sesudah gerbang — karena itu tidak ada satu pun kode blokir yang
dipetakan ke sana. Ranking yang sudah ada (`Candidate Score DESC`, lalu SDC
ASC) TIDAK diubah: gerbang berjalan sebelum ranking.

Konsekuensi yang dijaga modul ini: kegagalan bukti tidak boleh disamarkan
sebagai "warning kosmetik" lalu kandidat tetap diusulkan sebagai aman. Kandidat
yang tertahan dilaporkan TERPISAH (`HeldCandidate`) beserta alasan dan langkah
verifikasi berikutnya — informasi tidak dihapus, hanya tidak diberi peringkat.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core import batch_eligibility as be

__all__ = [
    "CONTINUITY_LAYER",
    "EVIDENCE_LAYER",
    "HeldCandidate",
    "NEXT_STEP",
    "PRIORITY_LAYERS",
    "PriorityLayer",
    "TIME_LAYER",
    "explain_hold",
]


@dataclass(frozen=True)
class PriorityLayer:
    nomor: int
    nama: str
    maksud: str
    gerbang: bool


PRIORITY_LAYERS: tuple[PriorityLayer, ...] = (
    PriorityLayer(
        1,
        "Keselamatan dan kelengkapan bukti",
        "Batch harus aman DAN buktinya cukup; `fail`/bukti kurang tidak diusulkan.",
        True,
    ),
    PriorityLayer(
        2,
        "Kelayakan kebutuhan bahan dan waktu tiba",
        "Bahan yang dibutuhkan rencana menu, tiba sebelum tenggat (`needed_by`).",
        True,
    ),
    PriorityLayer(
        3,
        "Kontinuitas pasokan bahan",
        "Cadangan kontinuitas lokasi asal tidak diekspor.",
        True,
    ),
    PriorityLayer(
        4,
        "Invoice dan SDC",
        "Pembanding biaya komersial (invoice) dan biaya analitis (SDC).",
        False,
    ),
    PriorityLayer(
        5,
        "Mitigasi risiko susut",
        "Penyesuaian risiko kesegaran; memengaruhi SDC, bukan invoice.",
        False,
    ),
)

EVIDENCE_LAYER = 1
TIME_LAYER = 2
CONTINUITY_LAYER = 3

#: Peta kode blokir `app.core.batch_eligibility` → lapis hierarki.
#: Kode yang TIDAK ada di sini berarti bukan gerbang bahan (mis. alasan
#: administratif) dan tetap dilaporkan dengan lapis 1 sebagai konservatif.
_LAYER_BY_REASON: dict[str, int] = {
    be.QUARANTINE_BLOCK: EVIDENCE_LAYER,
    be.EXPIRY_UNKNOWN: EVIDENCE_LAYER,
    be.BATCH_EXPIRED: EVIDENCE_LAYER,
    be.SAFETY_FAIL: EVIDENCE_LAYER,
    be.SAFETY_PENDING: EVIDENCE_LAYER,
    be.SAFETY_NEEDS_VERIFICATION: EVIDENCE_LAYER,
    be.SAFETY_STATUS_UNKNOWN: EVIDENCE_LAYER,
    be.EVIDENCE_MISSING: EVIDENCE_LAYER,
    be.TEMPERATURE_INCOMPLETE: EVIDENCE_LAYER,
    be.FRESHNESS_FAIL: EVIDENCE_LAYER,
    be.EXPIRED_BEFORE_ARRIVAL: TIME_LAYER,
    be.DELIVERY_WINDOW_EXCEEDED: TIME_LAYER,
}

#: Langkah berikutnya per kode blokir. Didefinisikan DI SINI (core) supaya
#: `services/batch_eligibility_service` tidak menyimpan salinan kedua; kalimat
#: yang dibaca petugas dan kalimat yang dipakai penjelasan usulan harus sama.
#: `None` = tidak ada yang perlu dikerjakan.
NEXT_STEP: dict[str | None, str | None] = {
    None: None,
    be.QUARANTINE_BLOCK: "lepas karantina atau tolak batch",
    be.SAFETY_FAIL: "tolak batch — gagal uji keamanan pangan",
    be.SAFETY_PENDING: "uji keamanan pangan lalu catat verifikasi",
    be.SAFETY_NEEDS_VERIFICATION: "selesaikan verifikasi verifier",
    be.SAFETY_STATUS_UNKNOWN: "tentukan status keamanan pangan batch",
    be.EVIDENCE_MISSING: "lengkapi bukti batch atau tolak",
    be.TEMPERATURE_INCOMPLETE: "lengkapi bukti suhu lalu selesaikan verifikasi",
    be.FRESHNESS_FAIL: "tolak batch — kesegaran di bawah ambang",
    be.BATCH_EXPIRED: "tolak batch — sudah lewat masa layak",
    be.EXPIRY_UNKNOWN: "lengkapi masa layak atau tolak batch",
    be.EXPIRED_BEFORE_ARRIVAL: "jadwalkan ulang pengiriman atau tolak batch",
    be.DELIVERY_WINDOW_EXCEEDED: "jadwalkan ulang pengiriman",
}


def explain_hold(reasons) -> tuple[int, str, str | None]:
    """(lapis, nama lapis, langkah berikutnya) untuk kumpulan kode blokir.

    Lapis = yang TERPARAH (paling awal) di antara alasannya: satu alasan
    keselamatan sudah cukup membuat usulan berhenti di lapis 1. Alasannya
    sendiri tetap dilaporkan lengkap oleh pemanggil — fungsi ini tidak memilih
    satu alasan untuk disembunyikan.
    """
    kode = [str(r) for r in (reasons or ()) if r]
    if not kode:
        return EVIDENCE_LAYER, PRIORITY_LAYERS[0].nama, None
    lapis = min(_LAYER_BY_REASON.get(k, EVIDENCE_LAYER) for k in kode)
    nama = next(p.nama for p in PRIORITY_LAYERS if p.nomor == lapis)
    return lapis, nama, NEXT_STEP.get(kode[0])


@dataclass(frozen=True)
class HeldCandidate:
    """Kandidat yang TERTAHAN gerbang — dilaporkan, bukan diberi peringkat.

    Bentuknya sengaja menyerupai elemen `recommendations[]` (asal, tujuan,
    komoditas, supplier, kuantitas) tetapi dengan penanda `is_candidate=False`
    dan alasan blokir. UI/Joule dapat menampilkan "perlu verifikasi" tanpa
    harus merakit ulang evaluasi batch.
    """

    source_location: str
    destination_location: str
    commodity: str
    supplier_id: str | None
    quantity_kg: str
    status: str
    blocking_reasons: tuple[str, ...]
    next_step: str | None
    layer: int
    layer_name: str
    batch_ids: tuple[str, ...] = ()

    @property
    def is_candidate(self) -> bool:
        return False

    def to_dict(self) -> dict:
        return {
            "source_location": self.source_location,
            "destination_location": self.destination_location,
            "commodity": self.commodity,
            "supplier_id": self.supplier_id,
            "quantity_kg": str(self.quantity_kg),
            "status": self.status,
            "blocking_reasons": list(self.blocking_reasons),
            "next_step": self.next_step,
            "layer": self.layer,
            "layer_name": self.layer_name,
            "batch_ids": list(self.batch_ids),
            "is_candidate": False,
        }


def held_candidate(
    *,
    source_location: str,
    destination_location: str,
    commodity: str,
    supplier_id: str | None,
    quantity_kg,
    status: str,
    reasons,
    batch_ids=(),
) -> HeldCandidate:
    """Bangun `HeldCandidate` dari hasil fusi bukti (atau alasan eksplisit)."""
    lapis, nama, langkah = explain_hold(reasons)
    return HeldCandidate(
        source_location=source_location,
        destination_location=destination_location,
        commodity=commodity,
        supplier_id=supplier_id,
        quantity_kg=str(quantity_kg),
        status=status,
        blocking_reasons=tuple(str(r) for r in (reasons or ())),
        next_step=langkah,
        layer=lapis,
        layer_name=nama,
        batch_ids=tuple(str(b) for b in batch_ids),
    )
