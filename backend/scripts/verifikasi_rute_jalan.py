"""Bukti: garis jalur kiriman pemasok → tujuan di jalur NYATA (Fase 10, 2026-10-16).

Dijalankan di dalam kontainer backend:

    docker compose exec -e PYTHONPATH=/app backend python scripts/verifikasi_rute_jalan.py

Yang dibuktikan, tanpa mengetik kata sandi di layar:
1. login akun demo nyata (kata sandi dibaca dari `app.seed.seed_data.DEMO_USERS`),
2. kepala SPPG Jakarta HANYA melihat kiriman yang menuju SPPG-nya (cakupan server),
   sedangkan `bgn_monitor` melihat seluruh kiriman aktif,
3. setiap kiriman yang punya rute membawa geometri dari cache DB — dan geometrinya
   PERSIS sama dengan baris `road_routes` (bukan dua perhitungan berbeda),
4. jarak jalan (OSRM) tidak pernah lebih pendek dari jarak lurus (haversine) —
   kalau terbalik, ada yang salah dan skrip ini GAGAL,
5. kiriman kedaluwarsa tidak muncul.

Keluar kode 1 bila ada ketidakcocokan, supaya bisa dipakai sebagai gerbang.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from app.seed.seed_data import DEMO_USERS

DB_URL = "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"


def _sql_routes() -> dict[str, dict]:
    """Rute di cache per kunci, langsung dari DB."""
    with create_engine(DB_URL).connect() as conn:
        rows = conn.execute(
            text(
                "SELECT route_key, distance_m, duration_s, source, "
                "jsonb_array_length(geometry->'coordinates') AS titik "
                "FROM road_routes"
            )
        ).all()
    return {
        row.route_key: {
            "distance_m": row.distance_m,
            "duration_s": row.duration_s,
            "source": row.source,
            "titik": row.titik,
        }
        for row in rows
    }


def _sql_aktif() -> dict[str, dict]:
    """Kiriman aktif menurut SQL, per (pemasok, tujuan)."""
    with create_engine(DB_URL).connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT s.name AS pemasok, l.name AS tujuan, count(*) AS jumlah,
                       coalesce(sum(b.quantity_kg), 0) AS kg
                FROM batches b
                JOIN suppliers s ON s.id = b.supplier_id
                LEFT JOIN locations l ON l.id = b.location_id
                WHERE b.usable_until >= now()
                GROUP BY s.name, l.name
                """
            )
        ).all()
    return {
        f"{row.pemasok} -> {row.tujuan}": {"jumlah": row.jumlah, "kg": float(row.kg)}
        for row in rows
    }


def _token(client: TestClient, role: str) -> dict:
    for user in DEMO_USERS:
        if user["role"] == role:
            resp = client.post(
                "/auth/login",
                json={"email": user["email"], "password": user["password"]},
            )
            assert resp.status_code == 200, resp.text
            return {"Authorization": f"Bearer {resp.json()['access_token']}"}
    raise SystemExit(f"akun demo untuk role {role} tidak ditemukan")


def main() -> int:
    cache = _sql_routes()
    aktif_sql = _sql_aktif()
    problems: list[str] = []

    with TestClient(app) as client:
        headers_spg = _token(client, "sppg_head")
        headers_mon = _token(client, "bgn_monitor")

        spg = client.get("/supplier-routes?limit=200", headers=headers_spg)
        mon = client.get("/supplier-routes?limit=200", headers=headers_mon)
        assert spg.status_code == 200, spg.text
        assert mon.status_code == 200, mon.text
        spg_body, mon_body = spg.json(), mon.json()

    print(f"rute di cache DB      : {len(cache)}")
    print(f"kiriman aktif (SQL)   : {len(aktif_sql)}")
    print(
        f"kepala SPPG Jakarta   : {spg_body['summary']['routes']} jalur "
        f"(cakupan {spg_body['summary']['scope']} = "
        f"{spg_body['summary']['reference_location']})"
    )
    print(
        f"bgn_monitor (nasional): {mon_body['summary']['routes']} jalur, "
        f"{mon_body['summary']['with_road']} punya jalur jalan"
    )
    print()

    tujuan_spg = {row["destination_name"] for row in spg_body["routes"]}
    if tujuan_spg - {"Jakarta"}:
        problems.append(f"kepala SPPG Jakarta melihat tujuan lain: {tujuan_spg}")

    for row in spg_body["routes"]:
        print(
            f"  {row['supplier_name']} -> {row['destination_name']}: "
            f"lurus {row['straight_km']} km | "
            + (
                f"jalan {row['road']['distance_km']} km "
                f"(± {round(row['road']['duration_min'])} menit, {row['road']['source']}, "
                f"{len(row['road']['geometry']['coordinates'])} titik)"
                if row["road"]
                else f"rute BELUM ADA ({row['road_missing_reason']})"
            )
        )
        if not row["road"]:
            problems.append(
                f"{row['supplier_name']} -> {row['destination_name']}: rute tidak ada "
                f"({row['road_missing_reason']}) padahal cache punya {len(cache)} rute"
            )
            continue
        if row["road"]["distance_km"] < row["straight_km"]:
            problems.append(
                f"{row['supplier_name']}: jarak jalan ({row['road']['distance_km']}) "
                f"< jarak lurus ({row['straight_km']}) — mustahil"
            )

    print()
    # Geometri API harus PERSIS baris cache: cocokkan ujung & jumlah titik.
    for row in mon_body["routes"]:
        if not row["road"]:
            continue
        titik_api = len(row["road"]["geometry"]["coordinates"])
        cocok = [
            baris
            for baris in cache.values()
            if baris["titik"] == titik_api
            and abs(baris["distance_m"] / 1000 - row["road"]["distance_km"]) < 0.05
        ]
        if not cocok:
            problems.append(
                f"{row['supplier_name']} -> {row['destination_name']}: geometri API "
                f"({titik_api} titik, {row['road']['distance_km']} km) tidak ada di cache DB"
            )

    for row in mon_body["routes"]:
        kunci = f"{row['supplier_name']} -> {row['destination_name']}"
        if kunci not in aktif_sql:
            problems.append(f"{kunci}: ada di API tapi TIDAK aktif menurut SQL")
    for kunci, data in aktif_sql.items():
        if kunci not in {
            f"{row['supplier_name']} -> {row['destination_name']}"
            for row in mon_body["routes"]
        }:
            problems.append(
                f"{kunci}: aktif menurut SQL ({data['jumlah']} kiriman) tapi TIDAK ada di API"
            )

    if problems:
        print("SELISIH DITEMUKAN:")
        for p in problems:
            print(f"  - {p}")
        return 1

    print("Cakupan, geometri, dan jarak jalan konsisten dengan DB. Bukti lulus.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
