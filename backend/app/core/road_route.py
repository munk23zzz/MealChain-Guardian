"""Rute **jalan** (OSRM) untuk garis pemasok → tujuan di peta.

Keputusan pemilik 2026-10-16 (dua tanya-jawab, lihat
`docs/verification/fase-10.md`):

1. Garis di peta harus **mengikuti jalan**, bukan garis lurus. Karena itu
   geometrinya datang dari OSRM (routing OpenStreetMap) — sejalan dengan
   `docs/Architecture.md` yang sejak awal menyebut OSM/OSRM.
2. Rute diambil **saat seeding/sync** lalu disimpan di tabel cache
   (`road_routes`), BUKAN saat peta dibuka. Alasannya: demo tidak boleh
   bergantung pada internet, hasilnya harus sama setiap kali, dan server OSRM
   demo publik tidak boleh dibanjiri permintaan dari peramban pengunjung.

Modul ini sengaja MURNI (tanpa jaringan, tanpa DB) supaya bisa diuji cepat; yang
melakukan panggilan jaringan adalah `app/seed/road_routes.py` (sinkronisasi) dan
yang membaca cache adalah `app/api/supplier_routes.py`.

Prinsip yang sama seperti modul data lain di repo ini: **tidak ada angka atau
garis karangan.** Kalau rute belum ada di cache atau OSRM menolak, endpoint
mengirim `road = null` + alasan yang bisa dibaca manusia; jarak lurus (haversine
yang sudah dipakai Fase 7) tetap dilaporkan sebagai fakta terpisah, bukan
pengganti diam-diam.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Iterable, Optional

from app.core.geo import haversine_km
from app.core.journey import journey_payload

PROFIL_DEFAULT = "driving"
SUMBER_OSRM = "osrm"

# Alasan `road = null` — ditampilkan apa adanya, bukan disamarkan.
ALASAN_BELUM_DISINKRON = "belum_disinkron"
ALASAN_LAYANAN_TIDAK_TERJANGKAU = "layanan_rute_tidak_terjangkau"
ALASAN_RUTE_TIDAK_DITEMUKAN = "rute_tidak_ditemukan"
ALASAN_RESPONS_TIDAK_DIKENAL = "respons_rute_tidak_dikenal"


class RoadRouteError(RuntimeError):
    """Rute tidak bisa dipakai. `reason` = salah satu ALASAN_* di atas."""

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}: {detail}" if detail else reason)


# ---------------------------------------------------------------------------
# Kunci cache & URL permintaan
# ---------------------------------------------------------------------------


def route_key(
    lat_a: float,
    lon_a: float,
    lat_b: float,
    lon_b: float,
    profile: str = PROFIL_DEFAULT,
) -> str:
    """Kunci cache rute. Dibulatkan 4 desimal (±11 m) supaya pemasok dan tujuan
    yang sama tidak membuat baris cache baru hanya karena beda pembulatan.

    Arah ikut jadi bagian kunci: rute A→B dan B→A bisa berbeda (jalan satu arah).
    """
    return (
        f"{profile}:{float(lat_a):.4f},{float(lon_a):.4f}"
        f">{float(lat_b):.4f},{float(lon_b):.4f}"
    )


def osrm_url(
    base_url: str,
    lat_a: float,
    lon_a: float,
    lat_b: float,
    lon_b: float,
    profile: str = PROFIL_DEFAULT,
) -> str:
    """URL permintaan rute OSRM.

    Perhatian urutan: OSRM menuntut `lon,lat` (kebalikan konvensi lat/lon yang
    dipakai di seluruh repo ini). Tertukar tidak menghasilkan error — hasilnya
    rute di benua lain, jadi urutannya dikunci di sini, bukan di pemanggil.

    `overview=full` dipilih sadar: geometri `simplified` hanya ~36 titik untuk
    rute 110 km sehingga sudut jalan terpotong di zoom >= 12 — garis terlihat
    "memotong" blok kota. `full` memberi geometri jalan sebenarnya (Cianjur→
    Jakarta 3.011 titik, ~72 KB). Cache-nya hidup di tabel `road_routes` (DB),
    bukan berkas yang ikut ter-commit, jadi ukuran itu tidak membebani repo.
    """
    coords = (
        f"{float(lon_a):.4f},{float(lat_a):.4f};"
        f"{float(lon_b):.4f},{float(lat_b):.4f}"
    )
    base = base_url.rstrip("/")
    return (
        f"{base}/route/v1/{profile}/{coords}"
        "?overview=full&geometries=geojson&alternatives=false&steps=false"
    )


# ---------------------------------------------------------------------------
# Penguraian respons OSRM
# ---------------------------------------------------------------------------


def _angka(value: Any, nama: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RoadRouteError(ALASAN_RESPONS_TIDAK_DIKENAL, f"{nama} bukan angka")
    value = float(value)
    if value != value or value in (float("inf"), float("-inf")):  # NaN/Inf
        raise RoadRouteError(ALASAN_RESPONS_TIDAK_DIKENAL, f"{nama} bukan angka nyata")
    return value


def parse_osrm_route(payload: Any) -> dict:
    """Ubah respons OSRM menjadi baris cache. Gagal → RoadRouteError.

    Sengaja ketat: respons yang tidak berbentuk seperti yang diharapkan DITOLAK,
    supaya tidak ada garis setengah benar yang lolos ke peta.
    """
    if not isinstance(payload, dict):
        raise RoadRouteError(ALASAN_RESPONS_TIDAK_DIKENAL, "respons bukan objek")

    code = payload.get("code")
    if code != "Ok":
        alasan = (
            ALASAN_RUTE_TIDAK_DITEMUKAN if code == "NoRoute" else ALASAN_RESPONS_TIDAK_DIKENAL
        )
        raise RoadRouteError(alasan, f"code={code}")

    routes = payload.get("routes")
    if not isinstance(routes, list) or not routes:
        raise RoadRouteError(ALASAN_RUTE_TIDAK_DITEMUKAN, "tidak ada rute")

    route = routes[0]
    if not isinstance(route, dict):
        raise RoadRouteError(ALASAN_RESPONS_TIDAK_DIKENAL, "rute bukan objek")

    geometry = route.get("geometry")
    if not isinstance(geometry, dict) or geometry.get("type") != "LineString":
        raise RoadRouteError(ALASAN_RESPONS_TIDAK_DIKENAL, "geometri bukan LineString")

    raw_coords = geometry.get("coordinates")
    if not isinstance(raw_coords, list) or len(raw_coords) < 2:
        # Satu titik bukan garis. Menggambarnya = mengarang rute.
        raise RoadRouteError(ALASAN_RESPONS_TIDAK_DIKENAL, "titik geometri < 2")

    coords: list[list[float]] = []
    for titik in raw_coords:
        if not isinstance(titik, (list, tuple)) or len(titik) != 2:
            raise RoadRouteError(ALASAN_RESPONS_TIDAK_DIKENAL, "titik cacat")
        lon = _angka(titik[0], "longitude")
        lat = _angka(titik[1], "latitude")
        if not (-180 <= lon <= 180) or not (-90 <= lat <= 90):
            raise RoadRouteError(ALASAN_RESPONS_TIDAK_DIKENAL, "koordinat di luar rentang")
        coords.append([lon, lat])

    distance = _angka(route.get("distance"), "distance")
    duration = _angka(route.get("duration"), "duration")
    if distance < 0 or duration < 0:
        raise RoadRouteError(ALASAN_RESPONS_TIDAK_DIKENAL, "jarak/durasi negatif")

    return {
        "distance_m": int(round(distance)),
        "duration_s": int(round(duration)),
        "geometry": {"type": "LineString", "coordinates": coords},
        "source": SUMBER_OSRM,
    }


# ---------------------------------------------------------------------------
# Rencana sinkronisasi
# ---------------------------------------------------------------------------


def plan_route_sync(
    requests: Iterable[dict], cached_keys: set[str]
) -> dict:
    """Tentukan rute mana yang perlu diambil dari OSRM.

    Dua penghematan sekaligus: kunci yang sudah ada di cache dilewati
    (`sudah_ada`), dan kunci yang muncul lebih dari sekali dalam satu permintaan
    hanya diambil sekali (`duplikat`) — mis. dua batch dari pemasok dan tujuan
    yang sama tetap satu panggilan ke server OSRM demo.
    """
    perlu: list[dict] = []
    sudah_ada = 0
    duplikat = 0
    dilihat: set[str] = set()
    for req in requests:
        key = req["key"]
        if key in cached_keys:
            sudah_ada += 1
            continue
        if key in dilihat:
            duplikat += 1
            continue
        dilihat.add(key)
        perlu.append(req)
    return {"perlu_diambil": perlu, "sudah_ada": sudah_ada, "duplikat": duplikat}


# ---------------------------------------------------------------------------
# Perakitan payload endpoint
# ---------------------------------------------------------------------------


def _titik(blok: Any) -> Optional[tuple[float, float]]:
    if not isinstance(blok, dict):
        return None
    lat, lon = blok.get("latitude"), blok.get("longitude")
    if lat is None or lon is None:
        return None
    try:
        return float(lat), float(lon)
    except (TypeError, ValueError):
        return None


def build_route_payloads(
    shipments: Iterable[dict],
    cache: dict[str, dict],
    now: datetime | None = None,
) -> dict:
    """Susun payload rute untuk endpoint dari baris kiriman + cache.

    Kiriman yang tujuan/pemasoknya tidak punya koordinat DILEWATI (dihitung di
    `dilewati_tanpa_koordinat`) — titik pusat negara sebagai pengganti akan
    menyesatkan. Rute yang belum ada di cache tetap dikirim dengan `road = null`
    + `road_missing_reason`, supaya UI bisa bilang "belum disinkronkan" alih-alih
    menggambar garis lurus yang menyamar sebagai rute jalan.

    Sejak Fase 12, tiap rute juga membawa `journey`: jam berangkat (dari DB),
    estimasi tiba, keadaan perjalanan, dan sisa menit. Waktu tempuhnya diambil
    dari `road.duration_s` (OSRM) — kalau rutenya belum tersinkron, estimasi tiba
    TIDAK dibuat (lihat `app/core/journey.py`).
    """
    routes: list[dict] = []
    dilewati = 0

    for s in shipments:
        origin = _titik(s.get("origin"))
        dest = _titik(s.get("destination"))
        if origin is None or dest is None:
            dilewati += 1
            continue

        straight_km = round(haversine_km(origin[0], origin[1], dest[0], dest[1]), 2)
        key = route_key(origin[0], origin[1], dest[0], dest[1])
        row = cache.get(key)

        road: Optional[dict] = None
        reason: Optional[str] = ALASAN_BELUM_DISINKRON
        # Baris cache dengan durasi 0 detik bukan rute: pemasok dan tujuan
        # berimpit (10 baris seperti ini ada di data DEMO). Dulu baris itu
        # dilaporkan sebagai `road` dengan duration_min 0, tetapi `journey`
        # sengaja tidak membuat ETA untuk durasi 0 — hasilnya kontrak yang
        # bertentangan sendiri (`road` ada, `eta_at` null) dan tes rute gagal
        # `None == 0.0`. Sekarang jujur: tanpa jalan, alasan disebutkan.
        if row and float(row.get("duration_s") or 0) > 0:
            distance_km = round(row["distance_m"] / 1000, 1)
            road = {
                "distance_km": distance_km,
                "duration_min": round(row["duration_s"] / 60, 1),
                "ratio_vs_straight": (
                    round(distance_km / straight_km, 2) if straight_km > 0 else None
                ),
                "geometry": row["geometry"],
                "source": row.get("source", SUMBER_OSRM),
                "fetched_at": row["fetched_at"].isoformat(),
            }
            reason = None

        usable_until = s.get("usable_until")
        journey = journey_payload(
            now=now or datetime.now(UTC),
            dispatched_at=s.get("dispatched_at"),
            travel_s=row["duration_s"] if row else None,
            travel_source=row.get("source") if row else None,
            usable_until=usable_until,
        )
        routes.append(
            {
                "batch_id": str(s["batch_id"]) if s.get("batch_id") else None,
                "supplier_id": str(s["supplier_id"]),
                "supplier_name": s["supplier_name"],
                "origin": {
                    "latitude": origin[0],
                    "longitude": origin[1],
                    "name": (s.get("origin") or {}).get("name"),
                },
                "destination_id": str(s["destination_id"]),
                "destination_name": s["destination_name"],
                "destination": {
                    "latitude": dest[0],
                    "longitude": dest[1],
                    "name": (s.get("destination") or {}).get("name"),
                },
                "commodity": s.get("commodity"),
                "quantity_kg": s.get("quantity_kg"),
                "harvested_at": (
                    s["harvested_at"].isoformat() if s.get("harvested_at") else None
                ),
                "usable_until": usable_until.isoformat() if usable_until else None,
                "safety_status": s.get("safety_status"),
                "straight_km": straight_km,
                "route_key": key,
                "road": road,
                "road_missing_reason": reason,
                "journey": journey,
            }
        )

    return {"routes": routes, "dilewati_tanpa_koordinat": dilewati}
