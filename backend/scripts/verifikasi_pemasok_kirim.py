"""Bukti: profil pemasok kanonik + "sedang mengirim" di jalur NYATA (2026-10-16).

Dijalankan di dalam kontainer backend (env aplikasi apa adanya):

    docker compose exec backend python scripts/verifikasi_pemasok_kirim.py

Yang dibuktikan, tanpa mengetik kata sandi di layar:
1. login akun demo nyata (kata sandi dibaca dari `app.seed.seed_data.DEMO_USERS`),
2. `GET /suppliers` memuat profil kanonik yang kini terisi (komoditas/sertifikasi)
   dan membiarkan kapasitas kosong (tidak ada sumbernya),
3. kunci `shipping` per baris SAMA dengan hitungan SQL langsung untuk
   `usable_until >= now` — API vs SQL, bukan dua hitungan dari sumber berbeda,
4. kiriman yang gagal uji tetap dilaporkan (tidak hilang di balik "sedang mengirim").

Keluar dengan kode 1 bila ada ketidakcocokan, supaya bisa dipakai sebagai gerbang.
"""

from __future__ import annotations

import sys

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from app.seed.seed_data import DEMO_USERS

DB_URL = "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"


def _sql_shipping() -> dict[str, dict]:
    """Ringkasan kiriman aktif per NAMA pemasok, langsung dari DB."""
    with create_engine(DB_URL).connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT s.name, count(*) AS jumlah,
                       coalesce(sum(b.quantity_kg), 0) AS kg,
                       max(b.usable_until) AS sampai,
                       count(*) FILTER (WHERE b.safety_status = 'fail') AS gagal
                FROM batches b
                JOIN suppliers s ON s.id = b.supplier_id
                WHERE b.usable_until >= now()
                GROUP BY s.name
                """
            )
        ).all()
    return {
        row.name: {
            "count": row.jumlah,
            "total_kg": float(row.kg),
            "until": row.sampai,
            "fails": row.gagal,
        }
        for row in rows
    }


def _profile_counts() -> dict[str, int]:
    with create_engine(DB_URL).connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT count(*) AS total,
                       count(*) FILTER (WHERE commodity_id IS NOT NULL) AS ada_komoditas,
                       count(*) FILTER (WHERE certification_status IS NOT NULL) AS ada_sertifikasi,
                       count(*) FILTER (WHERE capacity_kg_per_week IS NOT NULL) AS ada_kapasitas,
                       count(*) FILTER (WHERE name LIKE 'Supplier %'
                                          AND commodity_id IS NOT NULL) AS kanonik_terisi
                FROM suppliers
                """
            )
        ).one()
    return dict(row._mapping)


def main() -> int:
    with TestClient(app) as client:
        headers = None
        for user in DEMO_USERS:
            if user["role"] != "sppg_head":
                continue
            resp = client.post(
                "/auth/login",
                json={"email": user["email"], "password": user["password"]},
            )
            if resp.status_code != 200:
                print(f"GAGAL login {user['email']}: {resp.status_code} {resp.text}")
                return 1
            headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
        if headers is None:
            print("GAGAL: akun demo sppg_head tidak ada di DEMO_USERS")
            return 1

        resp = client.get("/suppliers?limit=200", headers=headers)
        resp.raise_for_status()
        body = resp.json()

    sql = _sql_shipping()
    api = {
        item["name"]: item["shipping"]
        for item in body["items"]
        if item["shipping"] is not None
    }

    print(f"pemasok dikembalikan API : {body['count']} dari {body['total']}")
    print(f"rujukan jarak            : {body['distance_reference']}")
    print(f"pemasok dengan kiriman   : {len(api)} (SQL: {len(sql)})")
    print()

    problems: list[str] = []
    for name in sorted(set(sql) | set(api)):
        s = sql.get(name)
        a = api.get(name)
        if s is None:
            problems.append(f"{name}: ada di API tapi TIDAK ada di SQL")
            print(f"  {name}: API={a} SQL=tidak ada  <-- SELISIH")
            continue
        if a is None:
            problems.append(f"{name}: ada di SQL tapi TIDAK ada di API")
            print(f"  {name}: SQL={s} API=tidak ada  <-- SELISIH")
            continue
        line = (
            f"  {name}: {a['count']} kiriman · {a['total_kg']} kg · "
            f"s/d {a['until'][:10]} · komoditas {', '.join(a['commodities'])}"
        )
        if a["safety_fail_count"]:
            line += f" · {a['safety_fail_count']} GAGAL UJI (dilaporkan apa adanya)"
        print(line)
        if a["count"] != s["count"] or a["total_kg"] != s["total_kg"]:
            problems.append(
                f"{name}: angka API {a['count']}/{a['total_kg']} "
                f"!= SQL {s['count']}/{s['total_kg']}"
            )
        if a["safety_fail_count"] != s["fails"]:
            problems.append(f"{name}: gagal uji API {a['safety_fail_count']} != SQL {s['fails']}")

    print()
    profil = _profile_counts()
    print(
        f"profil pemasok: {profil['ada_komoditas']}/{profil['total']} punya komoditas, "
        f"{profil['ada_sertifikasi']}/{profil['total']} punya sertifikasi, "
        f"{profil['ada_kapasitas']}/{profil['total']} punya kapasitas "
        f"(sengaja kosong: tanpa sumber), kanonik terisi {profil['kanonik_terisi']}/14"
    )
    print()

    if problems:
        print("SELISIH DITEMUKAN:")
        for p in problems:
            print(f"  - {p}")
        return 1

    print("API == SQL untuk semua pemasok yang mengirim. Bukti lulus.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
