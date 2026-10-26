"""Gerbang keselamatan deterministik untuk penerimaan & eksekusi (temuan F-01, A-01).

Modul ini murni (tanpa DB, tanpa I/O) supaya aturan keselamatan bisa diuji
tanpa infrastruktur. Dipakai oleh `app/api/receipts.py` dan `app/api/actions.py`.

Prinsip: **fail-closed**. Semua yang tidak terbukti aman dianggap menghalangi:

- status keamanan selain `pass` (termasuk `pending`, `needs_verification`,
  `fail`, kosong) → blokir;
- bukti suhu tidak lengkap (kurang dari dua sampel valid, entri rusak,
  timestamp duplikat) → blokir;
- batch dikarantina (`quarantined`) atau dinyatakan gagal (`failed`) → blokir;
- barang kedaluwarsa → blokir;
- kumpulan batch kosong → blokir (tidak ada bukti, bukan berarti aman).

Sebelum 25 Oktober 2026 penerimaan hanya menolak `fail` dan eksekusi memakai
`any(status != "fail")`, sehingga satu batch `pending` cukup untuk meloloskan
pengiriman, dan barang kedaluwarsa diberi `usable_until` baru saat dispatch.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Mapping

from app.core import quarantine as karantina
from app.core.temperature import summarize_temperature_log

BLOKIR_SAFETY_BUKAN_PASS = "safety_status_bukan_pass"
BLOKIR_SUHU_TIDAK_LENGKAP = "bukti_suhu_tidak_lengkap"
BLOKIR_EKSEKUSI_KEDALUWARSA = "kedaluwarsa"
BLOKIR_EKSEKUSI_KARANTINA = "dikarantina"
BLOKIR_EKSEKUSI_TANPA_BATCH = "tidak_ada_batch_sumber"
BLOKIR_SAFETY_FAIL_SUMBER = "safety_status_fail_sumber"

#: Status karantina yang menghalangi pemakaian batch.
KARANTINA_BLOKIR = (karantina.QUARANTINED, karantina.FAILED)

#: Rentang aman bawaan bila pemanggil tidak menyuplai aturan komoditas.
RENTANG_AMAN_BAWAAN = (0.0, 8.0)


def _teks(nilai: Any) -> str:
    return str(nilai or "").strip().lower()


def _nilai(objek: Any, kunci: str) -> Any:
    if isinstance(objek, Mapping):
        return objek.get(kunci)
    return getattr(objek, kunci, None)


def _bukti_suhu_lengkap(
    log: Iterable[dict] | None,
    safe_min_c: float,
    safe_max_c: float,
) -> bool:
    ringkasan = summarize_temperature_log(list(log or []), safe_min_c, safe_max_c)
    return bool(ringkasan.complete) and ringkasan.observed_minutes > 0


def _alasan_batch(
    *,
    safety_status: Any,
    quarantine_status: Any,
    usable_until: datetime | None,
    temperature_log: Iterable[dict] | None,
    sekarang: datetime,
    safe_min_c: float,
    safe_max_c: float,
) -> str | None:
    # Urutan sengaja: fakta fisik yang paling tegas dulu. Barang kedaluwarsa
    # ditolak dengan pesan kedaluwarsa walau status keamanannya juga belum
    # `pass` — petugas tidak bisa memperbaikinya dengan menunggu verifikasi.
    if usable_until is not None and usable_until < sekarang:
        return BLOKIR_EKSEKUSI_KEDALUWARSA
    if _teks(quarantine_status) in KARANTINA_BLOKIR:
        return BLOKIR_EKSEKUSI_KARANTINA
    if _teks(safety_status) != "pass":
        return BLOKIR_SAFETY_BUKAN_PASS
    if not _bukti_suhu_lengkap(temperature_log, safe_min_c, safe_max_c):
        return BLOKIR_SUHU_TIDAK_LENGKAP
    return None


def penghalang_sumber(batches: Iterable[Any], *, sekarang: datetime) -> str | None:
    """Alasan eksekusi diblokir karena keadaan batch SUMBER, atau `None`.

    Definisi TUNGGAL yang dipakai bersama oleh guard `execute` dan
    `approval-summary` (`can_execute`), sehingga tombol di UI tidak pernah
    menjanjikan eksekusi yang pasti ditolak 409.

    Sengaja LEBIH SEMPIT daripada `batch_blokir_eksekusi`: `pending` dan
    `needs_verification` TIDAK memblokir — itu keadaan normal sebelum
    pengujian, dan memblokirnya membuat keputusan mustahil dieksekusi hanya
    karena ada batch lain di lokasi+komoditas yang sama (terbukti pada seed
    kanonik: Jakarta/ayam `['fail','pass']`). Yang memblokir hanya fakta
    keras: tidak ada batch, `fail`, karantina, atau kedaluwarsa.
    """
    daftar = list(batches)
    if not daftar:
        return BLOKIR_EKSEKUSI_TANPA_BATCH
    for batch in daftar:
        if _teks(_nilai(batch, "safety_status")) == "fail":
            return BLOKIR_SAFETY_FAIL_SUMBER
        if _teks(_nilai(batch, "quarantine_status")) in KARANTINA_BLOKIR:
            return BLOKIR_EKSEKUSI_KARANTINA
        kedaluwarsa = _nilai(batch, "usable_until")
        if kedaluwarsa is not None and kedaluwarsa < sekarang:
            return BLOKIR_EKSEKUSI_KEDALUWARSA
    return None


def receipt_blokir_alasan(
    *,
    safety_status: Any,
    quarantine_status: Any = karantina.NONE,
    usable_until: datetime | None,
    temperature_log: Iterable[dict] | None,
    sekarang: datetime,
    safe_min_c: float = RENTANG_AMAN_BAWAAN[0],
    safe_max_c: float = RENTANG_AMAN_BAWAAN[1],
) -> str | None:
    """Alasan penerimaan barang ditolak, atau `None` bila boleh disetujui."""
    return _alasan_batch(
        safety_status=safety_status,
        quarantine_status=quarantine_status,
        usable_until=usable_until,
        temperature_log=temperature_log,
        sekarang=sekarang,
        safe_min_c=safe_min_c,
        safe_max_c=safe_max_c,
    )


def batch_blokir_eksekusi(
    *,
    safety_status: Any,
    quarantine_status: Any,
    usable_until: datetime | None,
    temperature_log: Iterable[dict] | None,
    sekarang: datetime,
    safe_min_c: float = RENTANG_AMAN_BAWAAN[0],
    safe_max_c: float = RENTANG_AMAN_BAWAAN[1],
) -> str | None:
    """Alasan satu batch tidak boleh dieksekusi/dikirim, atau `None` bila aman."""
    return _alasan_batch(
        safety_status=safety_status,
        quarantine_status=quarantine_status,
        usable_until=usable_until,
        temperature_log=temperature_log,
        sekarang=sekarang,
        safe_min_c=safe_min_c,
        safe_max_c=safe_max_c,
    )


def kumpulan_batch_blokir_eksekusi(
    batches: Iterable[Any],
    *,
    sekarang: datetime,
    safe_min_c: float = RENTANG_AMAN_BAWAAN[0],
    safe_max_c: float = RENTANG_AMAN_BAWAAN[1],
) -> str | None:
    """Alasan kumpulan batch sumber tidak boleh dieksekusi.

    Semua batch harus lolos. Satu batch ragu = blokir (fail-closed), dan
    kumpulan kosong juga blokir karena tidak ada bukti sama sekali.
    """
    daftar = list(batches)
    if not daftar:
        return BLOKIR_EKSEKUSI_TANPA_BATCH
    for b in daftar:
        alasan = batch_blokir_eksekusi(
            safety_status=_nilai(b, "safety_status"),
            quarantine_status=_nilai(b, "quarantine_status"),
            usable_until=_nilai(b, "usable_until"),
            temperature_log=_nilai(b, "temperature_log"),
            sekarang=sekarang,
            safe_min_c=safe_min_c,
            safe_max_c=safe_max_c,
        )
        if alasan is not None:
            return alasan
    return None
