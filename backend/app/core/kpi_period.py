"""Periode KPI — dihitung SERVER, hari kalender Asia/Jakarta.

Kenapa modul terpisah dan murni: sebelum ini rentang KPI dihitung klien
(`frontend/lib/kpi.ts`) sebagai jam bergulir — "24 jam" dan "7 hari" — sehingga
"hari ini" bukan hari kalender dan dua klien bisa mengirim jendela berbeda untuk
tombol yang sama. Kontrak di sini adalah satu-satunya sumber rentang:

- `today`  : [00.00 hari ini WIB, sekarang]
- `7d`     : [00.00 H-6 WIB, sekarang] — tujuh tanggal kalender termasuk hari ini
- `1bulan` : [00.00 tanggal 1 bulan berjalan WIB, sekarang]

Batas dihitung di zona Asia/Jakarta (WIB, UTC+7, tanpa DST), lalu dikembalikan
sebagai instan UTC supaya pembandingan dan tanda tangan konsisten. `now`
disuntikkan pemanggil supaya batas tengah malam/akhir bulan bisa diuji tanpa
menunggu jam sungguhan.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

#: Zona acuan produk: hari kalender Indonesia bagian barat.
ZONA_KPI = ZoneInfo("Asia/Jakarta")

#: Kunci periode yang sah, urut tampil di UI.
PERIODE_KPI: tuple[str, ...] = ("today", "7d", "1bulan")

#: Label manusia untuk kunci periode (dipakai API dan UI).
LABEL_PERIODE: dict[str, str] = {
    "today": "Hari ini",
    "7d": "7 hari",
    "1bulan": "1 bulan",
}


def resolve_periode(kunci: str, now: datetime) -> tuple[datetime, datetime]:
    """Rentang `[awal, akhir]` untuk satu kunci periode, dalam instan UTC.

    `akhir` selalu `now` (bukan tengah malam berikutnya): KPI tidak boleh
    menghitung fakta yang belum terjadi. `awal` adalah tengah malam WIB sesuai
    kunci. Kunci tak dikenal → `KeyError`; `now` tanpa zona → `ValueError`
    (tanpa zona, batas hari bisa bergeser 7 jam).
    """
    if now.tzinfo is None or now.tzinfo.utcoffset(now) is None:
        raise ValueError("now wajib menyertakan zona waktu")
    if kunci not in LABEL_PERIODE:
        raise KeyError(kunci)

    lokal = now.astimezone(ZONA_KPI)
    tengah_malam = lokal.replace(hour=0, minute=0, second=0, microsecond=0)

    if kunci == "today":
        awal_lokal = tengah_malam
    elif kunci == "7d":
        # Tujuh tanggal kalender: H-6 s.d. hari ini.
        awal_lokal = tengah_malam - timedelta(days=6)
    else:  # "1bulan"
        awal_lokal = tengah_malam.replace(day=1)

    return awal_lokal.astimezone(timezone.utc), now.astimezone(timezone.utc)


__all__ = ["LABEL_PERIODE", "PERIODE_KPI", "ZONA_KPI", "resolve_periode"]
