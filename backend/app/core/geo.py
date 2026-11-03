"""Geometri kecil yang dipakai lebih dari satu modul (satu implementasi).

Kenapa modul tersendiri: jarak "pemasok terjangkau" dipakai di dua tempat —
validasi data seed (`app/seed/suppliers_demo.py`, 7a) dan endpoint
`GET /suppliers` (7b). Menyalin rumus haversine ke dua berkas berarti dua
peluang berbeda hasil; jadi rumusnya hidup di sini dan dipakai bersama.
"""

import math

RADIUS_BUMI_KM = 6371.0


def haversine_km(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    """Jarak lingkaran besar (km) antara dua titik.

    Cukup akurat untuk memeriksa klaim "pemasok ini X km dari SPPG" — bukan
    untuk navigasi. Angka yang sama dipakai validasi seed dan endpoint, supaya
    "terjangkau menurut data" dan "terjangkau menurut API" tidak bisa berbeda.
    """
    rad = math.radians
    d_lat = rad(lat_b - lat_a)
    d_lon = rad(lon_b - lon_a)
    h = (
        math.sin(d_lat / 2) ** 2
        + math.cos(rad(lat_a)) * math.cos(rad(lat_b)) * math.sin(d_lon / 2) ** 2
    )
    return 2 * RADIUS_BUMI_KM * math.asin(math.sqrt(h))
