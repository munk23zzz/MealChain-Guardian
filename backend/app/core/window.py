"""Jendela waktu feed (24 jam / 7 hari / 1 bulan) — satu definisi untuk API.

Dipisah dari router supaya aturan "1 bulan = bulan berjalan WIB" tidak ditulis
ulang di tempat lain dan bisa diuji tanpa database.

Aturan yang dipegang:
- "24 jam" dan "7 hari" = jendela BERGULIR dari `now`.
- "1 bulan" = bulan berjalan menurut WIB (bukan 30 hari bergulir). Alasannya
  tampilan: label periode menulis nama bulan, jadi jendelanya harus satu bulan
  kalender — bukan rentang yang terbaca dua bulan.
- Kunci tak dikenal / kosong → `None` = tanpa saringan (perilaku lama, bukan
  diam-diam memilih 24 jam yang bisa menyembunyikan data).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

WINDOW_KEYS: tuple[str, ...] = ("24h", "7d", "30d")
_WIB = timedelta(hours=7)


def window_start(window: str | None, now: datetime | None = None) -> datetime | None:
    """Awal jendela (UTC, timezone-aware), atau None bila tanpa saringan."""
    if window is None:
        return None
    kunci = window.strip().lower()
    if kunci not in WINDOW_KEYS:
        return None
    saat = now or datetime.now(timezone.utc)
    if saat.tzinfo is None:
        saat = saat.replace(tzinfo=timezone.utc)
    if kunci == "24h":
        return saat - timedelta(hours=24)
    if kunci == "7d":
        return saat - timedelta(days=7)
    # 30 hari: awal bulan berjalan menurut WIB.
    wib = saat.astimezone(timezone.utc) + _WIB
    awal_wib = datetime(wib.year, wib.month, 1, tzinfo=timezone.utc)
    return awal_wib - _WIB
