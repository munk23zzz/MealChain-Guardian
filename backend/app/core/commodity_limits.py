"""Batas suhu aman PER KOMODITAS — satu sumber untuk safety & freshness.

Sebelumnya `api/freshness.py` punya peta sendiri (beras 15–30 °C), sedangkan
`api/safety.py` memakai `settings.safe_temp_min_c/max_c` (0–8 °C) untuk semua
komoditas. Akibatnya mencatat penerimaan beras pada suhu ruang 27 °C langsung
dinilai `fail` dan tidak bisa disetujui — bertentangan dengan freshness yang
justru menganggapnya wajar. Peta ini dipakai kedua endpoint supaya penilaian
keamanan dan kesegaran tidak saling bertentangan.
"""

from __future__ import annotations

SAFE_TEMP_BY_COMMODITY: dict[str, tuple[float, float]] = {
    "telur": (0.0, 8.0),
    "ayam": (0.0, 8.0),
    "wortel": (0.0, 8.0),
    "beras": (15.0, 30.0),
}

DEFAULT_SAFE_TEMP: tuple[float, float] = (0.0, 8.0)


def safe_temp_for(commodity: str | None) -> tuple[float, float]:
    """Rentang suhu aman untuk satu nama komoditas (bawaan 0–8 °C)."""
    kunci = (commodity or "").strip().lower()
    return SAFE_TEMP_BY_COMMODITY.get(kunci, DEFAULT_SAFE_TEMP)
