"""Audit integritas data demo/seed — READ-ONLY, keluar dengan kode status.

Kenapa ada: DB kerja ini dipakai bersama oleh aplikasi demo, seed kanonik, deret
aktual, dan suite pytest. Kerusakan yang paling mahal bukan error, melainkan data
yang "kelihatan benar": baris yatim, pasangan natural-key ganda, residu run tes,
atau deret yang kurang separuh — semuanya tampil sebagai layar kosong/angka aneh,
bukan sebagai kegagalan.

Skrip ini memeriksa enam lapisan dan mencetak laporan terstruktur:

1. **Skema** — versi Alembic di DB vs kepala repo (berkas migrasi terakhir).
2. **Hitungan per origin** — supply/price/demand/menu/kiriman/limbah, dibanding
   baseline kanonik (seed) + deret demo yang terdokumentasi.
3. **Baris yatim** — SETIAP foreign key di skema publik diperiksa generik
   (`child.col NOT NULL AND NOT EXISTS parent`), bukan hanya yang diingat.
4. **Natural key ganda** — email user, nama lokasi, nama komoditas,
   pasangan (nama pemasok, lokasi).
5. **Residu** — keputusan `origin='seed'` tanpa `demo_case` (buatan tes),
   PO `MC-*` tanpa keputusan, user `@test.local`.
6. **Rantai bukti** — `verify_chain()` dari `app.services.ledger_service`.

Pakai:

    docker compose exec -T -e PYTHONPATH=/app backend python scripts/audit_data_integrity.py
    ... --json        # ringkas, untuk dibaca mesin
    ... --strict      # anggap "perlu perhatian" sebagai kegagalan (exit 1)

Exit code: 0 = bersih · 2 = ada temuan · 1 = skrip gagal (koneksi/skema).
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

URL = "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"

# Baseline kanonik (dokumentasi: skill dev-loop, references/perluasan-deret-dan-isolasi.md §6).
# `None` = tidak dipaku (hanya dilaporkan).
BASELINE = {
    "supply_records": {"seed": 30, "demo": 3870},
    "price_signals": {"seed": 44, "demo": 4010},
    "menu_plans": {"seed": 70, "demo": 590},
    "delivery_events": {"seed": 70, "demo": 290},
    "disposal_events": {"seed": 20, "demo": 58},
    "demand_records": {"seed": 168, "demo": None},
}

# Tabel data yang punya kolom origin; urut dari induk ke anak supaya laporan enak dibaca.
TABEL_ORIGIN = [
    "supply_records",
    "price_signals",
    "demand_records",
    "menu_plans",
    "batches",
    "delivery_events",
    "disposal_events",
]

CHECKS_NATURAL_KEY = [
    ("users", "email"),
    ("locations", "name"),
    ("commodities", "name"),
    ("suppliers", "name, location_id"),
]


def _kepala_alembic() -> str:
    """Nomor migrasi terakhir dari nama berkas di alembic/versions.

    Hanya berkas berprefiks nomor (`017_...`) yang dihitung: `__init__.py` dan
    pembantu lain tinggal di folder yang sama dan akan menang bila diurutkan
    sebagai teks biasa ("_" > "0").
    """
    akar = Path(__file__).resolve().parent.parent / "alembic" / "versions"
    if not akar.is_dir():
        return "?"
    bernomor = [
        p.stem for p in akar.glob("*.py") if p.stem[:3].isdigit()
    ]
    return max(bernomor) if bernomor else "?"


def _hitungan_origin(conn) -> dict:
    hasil: dict[str, dict[str, int]] = {}
    for tabel in TABEL_ORIGIN:
        baris = conn.execute(
            text(
                f"SELECT COALESCE(origin, '(tanpa origin)') AS o, count(*) "
                f"FROM {tabel} GROUP BY 1 ORDER BY 1"
            )
        ).all()
        hasil[tabel] = {o: int(n) for o, n in baris}
    return hasil


def _yatim(conn) -> list[dict]:
    """Setiap FK di skema publik: hitung anak yang tidak punya induk."""
    fks = conn.execute(
        text(
            """
            SELECT tc.table_name AS anak,
                   kcu.column_name AS kolom,
                   ccu.table_name AS induk,
                   ccu.column_name AS kolom_induk
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage ccu
              ON tc.constraint_name = ccu.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = 'public'
            ORDER BY 1, 2
            """
        )
    ).mappings().all()
    temuan = []
    for fk in fks:
        n = conn.execute(
            text(
                f'SELECT count(*) FROM public."{fk["anak"]}" c '
                f'WHERE c."{fk["kolom"]}" IS NOT NULL '
                f'AND NOT EXISTS (SELECT 1 FROM public."{fk["induk"]}" p '
                f'WHERE p."{fk["kolom_induk"]}" = c."{fk["kolom"]}")'
            )
        ).scalar_one()
        if n:
            temuan.append(
                {
                    "tabel": fk["anak"],
                    "kolom": fk["kolom"],
                    "induk": fk["induk"],
                    "baris_yatim": int(n),
                }
            )
    return temuan


def _natural_key_ganda(conn) -> list[dict]:
    temuan = []
    for tabel, kolom in CHECKS_NATURAL_KEY:
        n = conn.execute(
            text(
                f"SELECT count(*) FROM (SELECT {kolom} FROM {tabel} "
                f"GROUP BY {kolom} HAVING count(*) > 1) x"
            )
        ).scalar_one()
        if n:
            temuan.append({"tabel": tabel, "kunci": kolom, "grup_ganda": int(n)})
    return temuan


def _residu(conn) -> dict:
    return {
        "keputusan_tanpa_demo_case_dan_bukan_demo": int(
            conn.execute(
                text(
                    "SELECT count(*) FROM decisions "
                    "WHERE demo_case IS NULL AND origin <> 'demo'"
                )
            ).scalar_one()
        ),
        "po_tanpa_keputusan": int(
            conn.execute(
                text(
                    # Hanya PO buatan eksekusi (`MC-*`). Baris `4500000001` adalah
                    # PO adapter yang memang DI-SEED tanpa keputusan (seed json
                    # `mock_sap.purchase_orders`, 1 baris) — bukan residu.
                    "SELECT count(*) FROM sap_mock_purchase_orders "
                    "WHERE decision_id IS NULL AND po_number LIKE 'MC-%'"
                )
            ).scalar_one()
        ),
        "user_tes": int(
            conn.execute(
                text(
                    "SELECT count(*) FROM users WHERE email LIKE '%test.local' "
                    "OR email LIKE '%uji-peran.local'"
                )
            ).scalar_one()
        ),
        "kasus_demo": int(
            conn.execute(
                text(
                    "SELECT count(DISTINCT demo_case) FROM decisions "
                    "WHERE demo_case IS NOT NULL"
                )
            ).scalar_one()
        ),
    }


def _kasus_demo(conn) -> list[dict]:
    """Kesiapan skrip demo: status, sisa TTL, jumlah trace & approval per kasus.

    TTL demo pendek (puluhan menit–jam), jadi "kasus siap" bukan sifat permanen:
    angka sisa_menit di sini yang menentukan apakah tombol Setuju masih bisa ditekan.
    """
    rows = conn.execute(
        text(
            "SELECT d.demo_case, d.status, "
            "       to_char(d.expires_at, 'YYYY-MM-DD HH24:MI') AS kedaluwarsa, "
            "       round(extract(epoch FROM (d.expires_at - now()))/60)::int AS sisa_menit, "
            "       (SELECT count(*) FROM agent_traces t WHERE t.decision_id = d.id) AS trace, "
            "       (SELECT count(*) FROM approvals a WHERE a.decision_id = d.id) AS approval "
            "FROM decisions d WHERE d.demo_case IS NOT NULL "
            "ORDER BY d.demo_case, d.status"
        )
    ).mappings().all()
    return [dict(r) for r in rows]


def _demografi(conn) -> dict:
    satu = lambda sql: int(conn.execute(text(sql)).scalar_one())  # noqa: E731
    return {
        "users": satu("SELECT count(*) FROM users"),
        "locations": satu("SELECT count(*) FROM locations"),
        "commodities": satu("SELECT count(*) FROM commodities"),
        "suppliers": satu("SELECT count(*) FROM suppliers"),
        "decisions": satu("SELECT count(*) FROM decisions"),
        "approvals": satu("SELECT count(*) FROM approvals"),
        "agent_traces": satu("SELECT count(*) FROM agent_traces"),
        "ledger_blocks": satu("SELECT count(*) FROM ledger_blocks"),
    }


def audit() -> dict:
    engine = create_engine(URL)
    try:
        with engine.connect() as conn:
            versi_db = conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one_or_none()
            laporan = {
                "skema": {
                    "alembic_db": versi_db,
                    "alembic_kepala_repo": _kepala_alembic(),
                    "cocok": versi_db is not None
                    and _kepala_alembic().endswith(str(versi_db)),
                },
                "origin": _hitungan_origin(conn),
                "yatim": _yatim(conn),
                "natural_key_ganda": _natural_key_ganda(conn),
                "residu": _residu(conn),
                "kasus_demo": _kasus_demo(conn),
                "demografi": _demografi(conn),
            }
    finally:
        engine.dispose()

    # Rantai bukti lewat fungsi aplikasi (bukan SQL tandingan).
    async def _ledger() -> dict:
        from sqlalchemy.ext.asyncio import create_async_engine

        from app.db import create_session_maker
        from app.services.ledger_service import verify_chain

        url = URL.replace("postgresql+psycopg", "postgresql+asyncpg")
        engine = create_async_engine(url)
        try:
            async with create_session_maker(engine)() as session:
                return await verify_chain(session)
        finally:
            await engine.dispose()

    try:
        laporan["ledger"] = asyncio.run(_ledger())
    except Exception as exc:  # pragma: no cover - hanya bila DB/fungsi berubah
        laporan["ledger"] = {"valid": None, "error": f"{type(exc).__name__}: {exc}"}

    # ── selisih baseline ────────────────────────────────────────────────────
    # Aturan pembanding berbeda menurut origin, dan itu bukan kelonggaran:
    # * `seed`  → HARUS persis. Seed kanonik adalah kontrak; kelebihan berarti
    #   generasi seed ganda (sisa refresh) dan kekurangan berarti data hilang.
    # * `demo`  → minimal. Deret demo memang bertambah setiap kali aktivitas
    #   "hari ini" disemai (mis. 2 limbah/hari) atau "Segarkan ke hari ini"
    #   menulis snapshot baru; yang salah adalah bila KURANG dari baseline.
    selisih = []
    for tabel, harapan in BASELINE.items():
        nyata = laporan["origin"].get(tabel, {})
        for origin, nilai in harapan.items():
            if nilai is None:
                continue
            dapat = nyata.get(origin, 0)
            if origin == "demo":
                if dapat < nilai:
                    selisih.append(
                        {
                            "tabel": tabel,
                            "origin": origin,
                            "harapan": f">= {nilai}",
                            "nyata": dapat,
                        }
                    )
            elif dapat != nilai:
                selisih.append(
                    {"tabel": tabel, "origin": origin, "harapan": nilai, "nyata": dapat}
                )
    laporan["selisih_baseline"] = selisih

    perlu = (
        bool(laporan["yatim"])
        or bool(laporan["natural_key_ganda"])
        or bool(selisih)
        or not laporan["skema"]["cocok"]
        or laporan["ledger"].get("valid") is not True
        or laporan["residu"]["user_tes"] > 0
    )
    laporan["perlu_perhatian"] = perlu
    return laporan


def cetak(laporan: dict) -> None:
    s = laporan["skema"]
    print("== 1. SKEMA ==")
    print(f"  alembic DB         : {s['alembic_db']}")
    print(f"  kepala repo        : {s['alembic_kepala_repo']}")
    print(f"  cocok              : {'ya' if s['cocok'] else 'TIDAK'}")

    print("\n== 2. HITUNGAN PER ORIGIN ==")
    for tabel, isi in laporan["origin"].items():
        harap = BASELINE.get(tabel, {})
        bagian = []
        for origin, n in isi.items():
            tanda = ""
            if origin in harap and harap[origin] is not None:
                cocok = n >= harap[origin] if origin == "demo" else n == harap[origin]
                tanda = " ok" if cocok else (
                    f" (harap >= {harap[origin]})" if origin == "demo"
                    else f" (harap {harap[origin]})"
                )
            bagian.append(f"{origin}={n}{tanda}")
        print(f"  {tabel:18} " + ", ".join(bagian))

    print("\n== 3. BARIS YATIM (semua FK) ==")
    if laporan["yatim"]:
        for t in laporan["yatim"]:
            print(
                f"  {t['tabel']}.{t['kolom']} -> {t['induk']}: {t['baris_yatim']} baris"
            )
    else:
        print("  tidak ada")

    print("\n== 4. NATURAL KEY GANDA ==")
    if laporan["natural_key_ganda"]:
        for t in laporan["natural_key_ganda"]:
            print(f"  {t['tabel']}({t['kunci']}): {t['grup_ganda']} grup")
    else:
        print("  tidak ada")

    r = laporan["residu"]
    print("\n== 5. RESIDU ==")
    print(f"  keputusan non-demo  : {r['keputusan_tanpa_demo_case_dan_bukan_demo']}")
    print(f"  PO tanpa keputusan  : {r['po_tanpa_keputusan']}")
    print(f"  user tes tersisa    : {r['user_tes']}")
    print(f"  kasus demo terpasang: {r['kasus_demo']} (harap 4)")
    print("\n== 5b. KESIAPAN KASUS DEMO (TTL bergulir) ==")
    if laporan["kasus_demo"]:
        print(
            f"  {'kasus':22} {'status':18} {'kedaluwarsa':17} {'sisa':>6} "
            f"{'trace':>6} {'approval':>8}"
        )
        for k in laporan["kasus_demo"]:
            print(
                f"  {k['demo_case']:22} {k['status']:18} {k['kedaluwarsa']:17} "
                f"{k['sisa_menit']:>6} {k['trace']:>6} {k['approval']:>8}"
            )
        siap = [
            k
            for k in laporan["kasus_demo"]
            if k["status"] in ("pending_approval", "verifier_flagged")
            and k["sisa_menit"] > 0
        ]
        lewat = sum(
            1
            for k in laporan["kasus_demo"]
            if k["sisa_menit"] <= 0
            and k["status"] in ("pending_approval", "verifier_flagged")
        )
        print(f"  siap ditindak sekarang: {len(siap)} · lewat tenggat: {lewat}")
        if siap:
            terdekat = min(siap, key=lambda k: k["sisa_menit"])
            print(
                f"  jendela demo tersisa: {terdekat['sisa_menit']} menit "
                f"({terdekat['demo_case']}) — klik \"Segarkan ke hari ini\" "
                f"sebelum presentasi bila kurang dari 30 menit"
            )
    else:
        print("  belum ada kasus demo — jalankan POST /demo/seed {\"force\": true}")

    print("\n== 6. RANTAI BUKTI & DEMOGRAFI ==")
    led = laporan["ledger"]
    print(f"  ledger valid        : {led.get('valid')} ({led.get('blocks')} blok)")
    for k, v in laporan["demografi"].items():
        print(f"  {k:18}: {v}")

    print("\n== 7. SELISIH BASELINE ==")
    if laporan["selisih_baseline"]:
        for d in laporan["selisih_baseline"]:
            print(f"  {d['tabel']}[{d['origin']}]: harap {d['harapan']}, nyata {d['nyata']}")
    else:
        print("  tidak ada")

    print(
        "\nVERDICT: "
        + ("PERLU PERHATIAN" if laporan["perlu_perhatian"] else "BERSIH")
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit integritas data demo (read-only)")
    parser.add_argument("--json", action="store_true", help="cetak JSON saja")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit 2 bila ada temuan (default: temuan tetap exit 0)",
    )
    args = parser.parse_args()
    try:
        laporan = audit()
    except Exception as exc:
        print(f"GAGAL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(laporan, indent=2, ensure_ascii=False))
    else:
        cetak(laporan)
    if args.strict and laporan["perlu_perhatian"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
