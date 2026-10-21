"""Rencana alokasi surplus -> kekurangan (greedy, murni — tanpa DB).

LATAR (terukur 2026-10-20). Panel "Rencana alokasi surplus" di halaman Surplus &
Limbah dihitung di klien dari `GET /balance/map`. Endpoint itu dibatasi cakupan
peran (Ruling 2026-10-14): `sppg_*` hanya menerima lokasinya SENDIRI, sementara
halaman Surplus & Limbah justru hanya boleh dibuka peran SPPG. Satu lokasi tidak
pernah bisa berisi pasangan surplus->kekurangan, jadi panel itu mustahil terisi
untuk siapa pun yang boleh membukanya (terukur: Kepala Bandung melihat
"0 lokasi surplus, 1 lokasi kekurangan").

Modul ini memindahkan hitungannya ke server, lintas lokasi, dengan aturan yang
SAMA seperti versi klien (`frontend/lib/surplus.ts`) supaya arti angkanya tidak
berubah:
  * kebutuhan terbesar diisi surplus terbesar lebih dulu;
  * satu sumber boleh melayani beberapa tujuan, satu tujuan boleh diisi
    beberapa sumber;
  * hanya lokasi yang KEDUA sisinya punya baris yang boleh jadi sumber/tujuan
    (PLAN-023) — surplus di atas permintaan yang tidak tercatat bukan fakta.

Yang dikirim endpoint adalah PASANGAN hasil olahan (dari, ke, kg, jarak), bukan
angka mentah supply/demand per lokasi.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Sequence

__all__ = ["Node", "build_allocations", "haversine_km"]

EARTH_RADIUS_KM = 6371.0


@dataclass(frozen=True)
class Node:
    """Satu lokasi pada satu sisi neraca (surplus atau kekurangan)."""

    location: str
    kg: Decimal
    region: str | None = None
    latitude: float | None = None
    longitude: float | None = None


def haversine_km(a: Node, b: Node) -> int | None:
    """Jarak lingkaran besar (km, dibulatkan) — `None` bila koordinat tak lengkap.

    Dibulatkan seperti versi klien (`Math.round`) supaya angka di panel tidak
    berubah hanya karena pindah sisi hitung.
    """
    try:
        lat1, lon1 = float(a.latitude), float(a.longitude)  # type: ignore[arg-type]
        lat2, lon2 = float(b.latitude), float(b.longitude)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(v) for v in (lat1, lon1, lat2, lon2)):
        return None
    rad = math.pi / 180
    d_lat = (lat2 - lat1) * rad
    d_lon = (lon2 - lon1) * rad
    h = (
        math.sin(d_lat / 2) ** 2
        + math.cos(lat1 * rad) * math.cos(lat2 * rad) * math.sin(d_lon / 2) ** 2
    )
    return int(round(2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(h)))))


def _urut_terbesar(nodes: Iterable[Node]) -> list[Node]:
    return sorted((n for n in nodes if n.kg > 0), key=lambda n: n.kg, reverse=True)


def build_allocations(
    surpluses: Sequence[Node],
    shortages: Sequence[Node],
    limit: int = 6,
    min_surplus_kg: Decimal | float = Decimal("0"),
) -> list[dict]:
    """Pasangkan kekurangan terbesar dengan surplus terbesar.

    `min_surplus_kg` membuang sumber yang surplusnya terlalu kecil untuk
    direncanakan (permintaan pemilik 20 Okt 2026: di bawah 150 kg tidak
    direncanakan). Ambang berlaku pada SURPLUS LOKASI, bukan pada tiap baris:
    sumber 400 kg tetap boleh mengisi tujuan berkebutuhan 40 kg.
    

    Mengembalikan daftar `{from, to, kg, distance_km, region}`. `region` =
    wilayah TUJUAN (yang menerima), sama dengan versi klien.
    """
    if limit <= 0:
        return []
    ambang = Decimal(str(min_surplus_kg))
    pools = [
        {"node": n, "left": n.kg}
        for n in _urut_terbesar(surpluses)
        if n.kg >= ambang
    ]
    needs = [{"node": n, "left": n.kg} for n in _urut_terbesar(shortages)]

    rows: list[dict] = []
    for need in needs:
        for pool in pools:
            if need["left"] <= 0:
                break
            if pool["left"] <= 0:
                continue
            kg = min(pool["left"], need["left"])
            if kg <= 0:
                continue
            pool["left"] -= kg
            need["left"] -= kg
            rows.append(
                {
                    "from": pool["node"].location,
                    "to": need["node"].location,
                    "kg": round(float(kg), 2),
                    "distance_km": haversine_km(pool["node"], need["node"]),
                    "region": need["node"].region,
                }
            )
            if len(rows) >= limit:
                return rows
    return rows
