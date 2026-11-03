"""Jembatan evaluator kelayakan batch ke API penerimaan & detail batch.

Fase 4 MG (poin 5): sesudah `app.core.batch_eligibility` menjadi SATU definisi
kelayakan, API tidak boleh lagi punya aturan sendiri. Modul ini hanya
mengerjakan dua hal yang memang milik lapisan HTTP:

1. **Menyiapkan fakta** — menerjemahkan baris `batches` (ORM atau `Row`) menjadi
   masukan evaluator. `freshness_status` TIDAK disimpan di tabel; ia diturunkan
   dari `freshness_score` memakai ambang kanonik `app.core.freshness`. Tanpa
   terjemahan ini, evaluator akan melihat `freshness_status` kosong dan
   `freshness_fail` tidak pernah bisa terjadi — persis jenis celah yang ditutup
   Fase 4.
2. **Memetakan kode → kalimat** — `blocking_reasons` berisi kode stabil
   (`safety_pending`, `batch_expired`, …). Petugas dapur butuh kalimat yang
   menyebut SEBABNYA, dan UI butuh `next_step` (langkah berikutnya). Pemetaan
   ini sengaja satu arah (kode → kalimat), supaya `safety_pending` tidak pernah
   dilaporkan sebagai `safety_fail`.

Tidak ada kebijakan bisnis baru di sini: daftar bukti wajib tetap milik
`BatchPolicy` (bawaannya kosong), dan status tidak pernah diubah oleh modul ini.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.batch_eligibility import (
    BATCH_EXPIRED,
    DELIVERY_WINDOW_EXCEEDED,
    EVIDENCE_MISSING,
    EXPIRED_BEFORE_ARRIVAL,
    EXPIRY_UNKNOWN,
    FRESHNESS_FAIL,
    ON_HOLD,
    POLICY_BAWAAN,
    QUARANTINE_BLOCK,
    QUARANTINED,
    REJECTED,
    SAFETY_FAIL,
    SAFETY_NEEDS_VERIFICATION,
    SAFETY_PENDING,
    SAFETY_STATUS_UNKNOWN,
    TEMPERATURE_INCOMPLETE,
    USABLE,
    BatchEvaluation,
    evaluate_batch,
)
from app.core.freshness import classify_freshness

__all__ = [
    "NEXT_STEP",
    "PESAN_TOLAK",
    "evaluasi_batch",
    "fakta_batch",
    "next_step",
    "payload_eligibility",
    "pesan_tolak",
]

#: Kalimat 409 per kode blokir. Kalimat `safety_fail` dan `batch_expired`
#: dipertahankan apa adanya dari gerbang sebelumnya supaya pengguna yang sudah
#: terbiasa membaca "TIDAK AMAN"/"kedaluwarsa" tidak kehilangan penanda itu.
PESAN_TOLAK: dict[str, str] = {
    QUARANTINE_BLOCK: (
        "barang masih berstatus karantina — tidak boleh masuk stok; "
        "tunggu keputusan pelepasan atau penolakan"
    ),
    SAFETY_FAIL: (
        "barang berstatus TIDAK AMAN atau belum terverifikasi — tolak penerimaan"
        " atau periksa ulang keamanannya"
    ),
    # `on_hold` punya kalimatnya sendiri: "belum diuji" bukan "gagal uji", dan
    # menyamakan keduanya membuat petugas membuang barang yang masih bisa diuji.
    # Kedua kalimat `on_hold` memuat "belum terbukti aman" supaya pembaca tetap
    # melihat penanda keamanan, TANPA menyamakannya dengan `safety_fail`
    # ("TIDAK AMAN"): barang ini masih bisa lolos setelah diuji/diverifikasi.
    SAFETY_PENDING: (
        "barang belum diuji keamanan pangannya (safety pending) — belum terbukti"
        " aman; selesaikan uji lalu catat hasil verifikasi sebelum disetujui"
    ),
    SAFETY_NEEDS_VERIFICATION: (
        "barang menunggu verifikasi keamanan pangan — belum terbukti aman;"
        " selesaikan verifikasi verifier sebelum disetujui"
    ),
    SAFETY_STATUS_UNKNOWN: (
        "status keamanan barang tidak dikenal — tentukan statusnya sebelum"
        " disetujui"
    ),
    EVIDENCE_MISSING: (
        "bukti barang tidak lengkap — lengkapi bukti yang disyaratkan atau tolak"
        " penerimaan"
    ),
    TEMPERATURE_INCOMPLETE: (
        "bukti suhu barang tidak lengkap — tidak boleh masuk stok; tolak"
        " penerimaan atau lengkapi pembacaan suhu"
    ),
    FRESHNESS_FAIL: (
        "kesegaran barang di bawah ambang verifikasi — tidak boleh masuk stok;"
        " tolak penerimaan"
    ),
    BATCH_EXPIRED: (
        "barang sudah kedaluwarsa — tidak boleh masuk stok; tolak penerimaan"
    ),
    EXPIRY_UNKNOWN: (
        "masa layak barang tidak tercatat — tidak dapat dibuktikan layak;"
        " lengkapi masa layak atau tolak penerimaan"
    ),
    EXPIRED_BEFORE_ARRIVAL: (
        "barang kedaluwarsa sebelum jadwal tiba — tidak boleh masuk stok"
    ),
    DELIVERY_WINDOW_EXCEEDED: (
        "jadwal kirim sudah terlampaui — barang tidak boleh masuk stok tanpa"
        " penjadwalan ulang"
    ),
}

#: Langkah berikutnya untuk UI (`GET /batches/{id}`). `None` = tidak ada yang
#: perlu dikerjakan (batch `usable`). Hanya menyebut tindakan yang memang ada
#: endpoint/alasannya — bukan prosedur baru.
NEXT_STEP: dict[str, str | None] = {
    USABLE: None,
    SAFETY_PENDING: "uji keamanan pangan lalu catat verifikasi",
    SAFETY_NEEDS_VERIFICATION: "selesaikan verifikasi verifier",
    SAFETY_STATUS_UNKNOWN: "tentukan status keamanan pangan batch",
    TEMPERATURE_INCOMPLETE: "lengkapi bukti suhu lalu selesaikan verifikasi",
    QUARANTINE_BLOCK: "lepas karantina atau tolak batch",
    SAFETY_FAIL: "tolak batch — gagal uji keamanan pangan",
    FRESHNESS_FAIL: "tolak batch — kesegaran di bawah ambang",
    BATCH_EXPIRED: "tolak batch — sudah lewat masa layak",
    EXPIRY_UNKNOWN: "lengkapi masa layak atau tolak batch",
    EXPIRED_BEFORE_ARRIVAL: "jadwalkan ulang pengiriman atau tolak batch",
    EVIDENCE_MISSING: "lengkapi bukti batch atau tolak",
    DELIVERY_WINDOW_EXCEEDED: "jadwalkan ulang pengiriman",
}

_PESAN_BAWAAN = "barang belum terbukti layak — tolak penerimaan"


def _nilai(objek: Any, kunci: str) -> Any:
    """Ambil atribut/kunci; `Row` dan ORM diperlakukan sama."""
    if isinstance(objek, dict):
        return objek.get(kunci)
    return getattr(objek, kunci, None)


def fakta_batch(batch: Any) -> dict:
    """Bentuk masukan evaluator dari satu baris `batches` (ORM atau `Row`)."""
    score = _nilai(batch, "freshness_score")
    kesegaran = _nilai(batch, "freshness_status")
    if not kesegaran and score is not None:
        try:
            kesegaran = classify_freshness(float(score))
        except ValueError:
            # Skor di luar [0,1] bukan alasan mengarang status: biarkan None,
            # dan evaluator memperlakukannya sebagai "tidak dapat dibuktikan".
            kesegaran = None
    return {
        "batch_id": _nilai(batch, "batch_id") or _nilai(batch, "id"),
        "safety_status": _nilai(batch, "safety_status"),
        "quarantine_status": _nilai(batch, "quarantine_status"),
        "usable_until": _nilai(batch, "usable_until"),
        "temperature_log": _nilai(batch, "temperature_log"),
        "freshness_status": kesegaran,
    }


def evaluasi_batch(batch: Any, sekarang: datetime | None = None) -> BatchEvaluation:
    """Nilai satu batch dengan evaluator tunggal; waktu dari server, bukan UI."""
    return evaluate_batch(
        fakta_batch(batch),
        POLICY_BAWAAN,
        evaluation_time=sekarang or datetime.now(UTC),
    )


def pesan_tolak(evaluation: BatchEvaluation) -> str:
    """Kalimat 409 untuk kode pertama; usable tidak punya pesan."""
    return PESAN_TOLAK.get(evaluation.code or "", _PESAN_BAWAAN)


def next_step(evaluation: BatchEvaluation) -> str | None:
    return NEXT_STEP.get(evaluation.code or USABLE)


def payload_eligibility(evaluation: BatchEvaluation) -> dict:
    """Bentuk `eligibility` untuk `GET /batches/{id}` — dihitung SERVER."""
    return {
        "status": evaluation.status,
        "blocking_reasons": list(evaluation.blocking_reasons),
        "next_step": next_step(evaluation),
    }


#: Status yang BOLEH lolos ke pencatatan penerimaan. `on_hold` termasuk:
#: ceklis petugas adalah bukti untuk verifikasi lanjutan, bukan penerimaan stok
#: (stok hanya bertambah lewat persetujuan, dan persetujuan menuntut `usable`).
BOLEH_DICATAT = (USABLE, ON_HOLD)

#: Status yang membuat catatan/persetujuan penerimaan ditolak 409.
TIDAK_BOLEH_DICATAT = (REJECTED, QUARANTINED)
