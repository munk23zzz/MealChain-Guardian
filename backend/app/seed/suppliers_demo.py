"""Seed pemasok demo Fase 2 + Fase 7 — 21 pemasok deterministik.

Latar: permintaan pemilik proyek (2026-10-14) agar pemasok bisa ditampilkan di
peta, lalu (2026-10-15) agar pemasok contoh untuk SPPG Jakarta benar-benar
terjangkau dari Jakarta — bukan perusahaan di Medan/Makassar yang berjarak
ratusan kilometer. Data 14 pemasok kanonik tidak cukup (dan tidak punya
koordinat/kapasitas), jadi ditambah 21 pemasok demo dari
`data/seed/suppliers_demo.json`:

- **12 pemasok hub Jakarta** dengan koordinat ABSOLUT (`latitude`/`longitude`)
  di Jakarta + kota penyangga (Bekasi, Depok, Tangerang, Bogor, Karawang,
  Cisarua, Serang, Subang, Cianjur), jarak berjenjang 0-25 / 25-60 / 60-150 km.
- **9 hub lain**: satu pemasok lokal per hub (jaring nasional untuk
  `bgn_monitor` dan SPPG kota itu sendiri).

Aturan yang dijaga modul ini:

- **Aditif untuk kanonik, dan membersihkan sisanya.** 14 pemasok kanonik dari
  `sprint1_seed.json` tidak pernah di-UPDATE di sini; sebaliknya baris demo yang
  sudah tidak ada di berkas (mis. karena kotanya dipindah) DIHAPUS, supaya
  database tidak menyimpan pemasok hantu yang tidak bisa dijelaskan. Penghapusan
  ditolak keras bila ada baris lain yang menunjuknya (`batches`, `price_signals`,
  PO mock, eksklusi) - lebih baik gagal berisik daripada mencacah data.
- **Deterministik.** Id = UUID5 dari natural key (`demo_supplier::<nama>`),
  koordinat = nilai absolut dari berkas ATAU titik hub + geseran tetap dari
  tabel `OFFSETS` (tanpa random, tanpa panggilan geocoding).
- **Idempoten.** Dijalankan berulang: baris yang sudah ada hanya diperbarui
  kolom profilnya, jumlah baris tidak bertambah.
- **Terjangkau.** Setiap pemasok hub Jakarta wajib punya koordinat absolut dan
  jaraknya dari SPPG Jakarta <= `REACH_KM_MAX` (150 km); baris yang melanggar
  ditolak saat dimuat, bukan diam-diam tampil di peta.

Jalankan: `python -m app.seed.suppliers_demo` (atau lewat
`python -m app.seed.seed_data --reference-time ... --with-demo-suppliers`).
"""

import argparse
import asyncio
import json
import os
from pathlib import Path

from sqlalchemy import func, select

from app.core.geo import haversine_km
from app.db import create_engine, create_session_maker
from app.models import (
    Batch,
    Commodity,
    Location,
    PriceSignal,
    SapMockPurchaseOrder,
    Supplier,
    SupplierExclusion,
)
from app.seed.seed_data import (  # noqa: F401  (namespace sama)
    SEED_NAMESPACE,
    _seed_database_url,
    stable_uuid,
)


def _default_suppliers_path() -> Path:
    """Berkas data: env dulu, lalu mount container, lalu path repo (host).

    Tes bisa jalan di dalam container (`/data/seed/...`) maupun di host
    (`<repo>/data/seed/...`) - jangan sampai salah satu lingkungan gagal hanya
    karena path default.
    """
    env = os.environ.get("DEMO_SUPPLIERS_PATH")
    if env:
        return Path(env)
    container = Path("/data/seed/suppliers_demo.json")
    if container.exists():
        return container
    return Path(__file__).resolve().parents[3] / "data" / "seed" / "suppliers_demo.json"


DEMO_SUPPLIERS_PATH = _default_suppliers_path()

# Geseran tetap (derajat) untuk pemasok hub yang TIDAK memakai koordinat absolut
# - sekitar 2 km, cukup untuk memisahkan pin di peta tanpa keluar dari kota.
OFFSETS: tuple[tuple[float, float], ...] = (
    (0.0, 0.0),
    (0.018, 0.021),
    (-0.016, -0.019),
)

CERTIFICATIONS = {"none", "hygiene", "haccp"}

# Ambang "terjangkau" untuk klaster Jakarta (keputusan pemilik 2026-10-15:
# Jabodetabek + penyangga Jawa Barat <= 150 km). Ini aturan DATA, bukan aturan
# API: penyaringan per peran di endpoint ada di Fase 7b dan bersifat relevansi.
REACH_KM_MAX = 150.0
REACH_REFERENCE_HUB = "Jakarta"

# Batas Indonesia (longgar) - menangkap koordinat tertukar lat/long atau salah benua.
INDONESIA_LAT = (-11.5, 6.5)
INDONESIA_LON = (94.5, 141.5)


def row_coordinates(
    row: dict, hub_coords: dict[str, tuple[float, float]] | None = None
) -> tuple[float | None, float | None]:
    """Koordinat satu baris: absolut bila ada, kalau tidak hub + OFFSETS.

    Mengembalikan `(None, None)` bila baris memakai geseran hub tetapi koordinat
    hub-nya tidak tersedia (mis. lokasi tanpa titik) - pemanggil yang memutuskan
    apakah itu fatal, dan peta cukup tidak menampilkan pinnya.
    """
    lat, lon = row.get("latitude"), row.get("longitude")
    if lat is not None or lon is not None:
        return float(lat), float(lon)
    if hub_coords is None:
        return None, None
    ref = hub_coords.get(row["location"])
    if ref is None:
        return None, None
    d_lat, d_lon = OFFSETS[row["offset_index"]]
    return round(ref[0] + d_lat, 6), round(ref[1] + d_lon, 6)


def load_demo_rows(
    path: Path | None = None, hub_coords: dict[str, tuple[float, float]] | None = None
) -> list[dict]:
    """Baca berkas data demo (murni, tanpa DB) - dipakai juga oleh tes.

    `hub_coords` opsional: bila diberikan, aturan "pemasok hub Jakarta harus
    terjangkau" ikut ditegakkan (butuh titik SPPG Jakarta dari tabel `locations`,
    jadi tidak bisa diperiksa dari berkas saja).
    """
    with open(path or DEMO_SUPPLIERS_PATH, encoding="utf-8") as f:
        payload = json.load(f)
    rows = payload["suppliers"]
    seen: set[str] = set()
    for row in rows:
        name = row["name"]
        if name in seen:
            raise ValueError(f"Nama pemasok demo duplikat: {name}")
        seen.add(name)
        if row["certification_status"] not in CERTIFICATIONS:
            raise ValueError(
                f"Sertifikasi tidak dikenal untuk {name}: {row['certification_status']}"
            )
        if not 0 <= float(row["reliability_score"]) <= 1:
            raise ValueError(f"reliability_score di luar 0..1: {name}")

        lat, lon = row.get("latitude"), row.get("longitude")
        if (lat is None) != (lon is None):
            raise ValueError(
                f"Koordinat separuh untuk {name}: isi latitude dan longitude sekaligus"
            )
        if lat is not None:
            if not INDONESIA_LAT[0] <= float(lat) <= INDONESIA_LAT[1]:
                raise ValueError(f"latitude di luar Indonesia: {name} ({lat})")
            if not INDONESIA_LON[0] <= float(lon) <= INDONESIA_LON[1]:
                raise ValueError(f"longitude di luar Indonesia: {name} ({lon})")
        elif "offset_index" not in row or row["offset_index"] not in range(len(OFFSETS)):
            raise ValueError(f"offset_index tidak dikenal: {name}")

        if hub_coords is not None and row["location"] == REACH_REFERENCE_HUB:
            if lat is None:
                raise ValueError(
                    f"Pemasok hub {REACH_REFERENCE_HUB} wajib berkoordinat absolut: {name}"
                )
            ref = hub_coords.get(REACH_REFERENCE_HUB)
            if ref is None:
                raise ValueError(
                    f"Titik hub {REACH_REFERENCE_HUB} tidak tersedia untuk memeriksa jarak: {name}"
                )
            distance = haversine_km(float(lat), float(lon), ref[0], ref[1])
            if distance > REACH_KM_MAX:
                raise ValueError(
                    f"Pemasok hub {REACH_REFERENCE_HUB} di luar jangkauan "
                    f"{REACH_KM_MAX:.0f} km: {name} ({distance:.1f} km)"
                )
    return rows


def demo_supplier_id(name: str):
    """UUID5 natural key khusus data demo (tidak menabrak id kanonik)."""
    return stable_uuid("demo_supplier", name)


async def _referencing_rows(session, supplier_ids: list) -> list[str]:
    """Sebutkan tabel yang masih menunjuk id pemasok (untuk pesan penolakan)."""
    checks = (
        (Batch, "batches"),
        (PriceSignal, "price_signals"),
        (SapMockPurchaseOrder, "sap_mock_purchase_orders"),
        (SupplierExclusion, "supplier_exclusions"),
    )
    found: list[str] = []
    for model, label in checks:
        count = (
            await session.execute(
                select(func.count())
                .select_from(model)
                .where(model.supplier_id.in_(supplier_ids))
            )
        ).scalar_one()
        if count:
            found.append(f"{label}: {count} baris")
    return found


async def seed_demo_suppliers(path: Path | None = None) -> dict[str, int]:
    """Selaraskan pemasok demo dengan berkas data (idempoten) + buang baris usang.

    Hitungan yang dikembalikan: `created`, `updated`, `removed`.
    """
    engine = create_engine(_seed_database_url())
    session_maker = create_session_maker(engine)
    counts = {"created": 0, "updated": 0, "removed": 0}
    try:
        async with session_maker() as session:
            locations = list((await session.execute(select(Location))).scalars())
            loc_by_name = {r.name: r for r in locations}
            hub_coords = {
                r.name: (float(r.latitude), float(r.longitude))
                for r in locations
                if r.latitude is not None and r.longitude is not None
            }
            com_by_name = {
                r.name: r for r in (await session.execute(select(Commodity))).scalars()
            }
            existing = {
                r.name: r for r in (await session.execute(select(Supplier))).scalars()
            }

            rows = load_demo_rows(path, hub_coords=hub_coords)
            for row in rows:
                loc = loc_by_name.get(row["location"])
                if loc is None:
                    raise ValueError(f"Lokasi tidak ada di DB: {row['location']}")
                com = com_by_name.get(row["commodity"])
                if com is None:
                    raise ValueError(f"Komoditas tidak ada di DB: {row['commodity']}")
                latitude, longitude = row_coordinates(row, hub_coords)
                profile = {
                    "location_id": loc.id,
                    "commodity_id": com.id,
                    "reliability_score": row["reliability_score"],
                    "capacity_kg_per_week": row["capacity_kg_per_week"],
                    "certification_status": row["certification_status"],
                    "contact_name": row["contact_name"],
                    "address": row["address"],
                    "latitude": latitude,
                    "longitude": longitude,
                }
                current = existing.get(row["name"])
                if current is None:
                    session.add(
                        Supplier(id=demo_supplier_id(row["name"]), name=row["name"], **profile)
                    )
                    counts["created"] += 1
                else:
                    for key, value in profile.items():
                        setattr(current, key, value)
                    counts["updated"] += 1

            # Baris demo yang sudah tidak ada di berkas: hapus, tapi jangan pernah
            # menyentuh baris kanonik (id-nya UUID acak, bukan natural key demo).
            keep = {row["name"] for row in rows}
            stale = [
                row
                for row in existing.values()
                if row.name not in keep and demo_supplier_id(row.name) == row.id
            ]
            if stale:
                blocking = await _referencing_rows(session, [row.id for row in stale])
                if blocking:
                    names = ", ".join(sorted(row.name for row in stale))
                    raise RuntimeError(
                        "Pemasok demo usang masih direferensikan baris lain - "
                        f"bersihkan dulu: {names} ({'; '.join(blocking)})"
                    )
                for row in stale:
                    await session.delete(row)
                counts["removed"] = len(stale)

            await session.commit()
    finally:
        await engine.dispose()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed pemasok demo (idempoten)")
    parser.add_argument("--path", default=None, help="override berkas JSON")
    args = parser.parse_args()
    counts = asyncio.run(
        seed_demo_suppliers(Path(args.path) if args.path else None)
    )
    print(
        f"Pemasok demo selesai (idempoten). Baru: {counts['created']}, "
        f"diperbarui: {counts['updated']}, dibuang: {counts['removed']}"
    )


if __name__ == "__main__":
    main()
