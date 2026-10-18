"""Karantina batch — status batch yang DITAHAN dari kandidat alokasi.

Bedanya dengan status keamanan: `safety_status='needs_verification'` masih boleh
masuk kandidat sebagai review-required, sedangkan `quarantine_status='quarantined'`
mengeluarkan batch dari kandidat SAMPAI manusia melepas atau menyatakannya gagal.

Pembagian kewenangan mengikuti proposal: agent hanya boleh mengusulkan karantina,
keputusan menahan/melepas dibuat manusia lewat approval & endpoint ber-peran.
Modul ini murni (tanpa DB) supaya transisi bisa diuji tanpa infrastruktur.
"""

from __future__ import annotations

NONE = "none"
QUARANTINED = "quarantined"
RELEASED = "released"
FAILED = "failed"

AKSI_TAHAN = "tahan"
AKSI_LEPAS = "lepas"
AKSI_GAGAL = "gagal"

STATUS_VALID = (NONE, QUARANTINED, RELEASED, FAILED)
SAFETY_VALID = ("pending", "pass", "fail", "needs_verification")

_TRANSISI = {
    (NONE, AKSI_TAHAN): QUARANTINED,
    (RELEASED, AKSI_TAHAN): QUARANTINED,
    (QUARANTINED, AKSI_LEPAS): RELEASED,
    (QUARANTINED, AKSI_GAGAL): FAILED,
}


def status_setelah(status: str, aksi: str) -> str:
    """Status baru setelah `aksi`; ValueError bila transisi tidak sah.

    `failed` bersifat terminal: batch yang sudah dinyatakan gagal tidak boleh
    ditahan, dilepas, atau digagalkan ulang — itu berarti keputusan keamanan
    dibatalkan tanpa alur, dan alur itu memang tidak ada.
    """
    if status not in STATUS_VALID:
        raise ValueError(f"status karantina tidak dikenal: {status!r}")
    kunci = (status, aksi)
    if kunci not in _TRANSISI:
        raise ValueError(f"transisi tidak sah: {status} + {aksi}")
    return _TRANSISI[kunci]


def boleh_ditahan(safety_status: str) -> tuple[bool, str]:
    """Boleh tidaknya batch ditahan, beserta alasan bila tidak boleh.

    Batch yang sudah `fail` tidak perlu karantina: ia sudah gugur dari kandidat
    dan sudah tercatat sebagai kegagalan keamanan. Menahannya hanya menyamarkan
    status itu.
    """
    if safety_status not in SAFETY_VALID:
        raise ValueError(f"safety_status tidak dikenal: {safety_status!r}")
    if safety_status == "fail":
        return False, "batch sudah fail; karantina tidak diperlukan"
    return True, ""
