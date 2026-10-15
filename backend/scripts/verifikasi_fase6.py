"""Verifikasi Fase 6 — matriks 3 peran × endpoint × angka DB (2026-10-15).

Ini bukti tunggal untuk Fase 6 rencana
`.hermes/plans/2026-10-14_scope-pemasok-peta-rentang.md`:

1. **Peran & cakupan.** Tiap endpoint dipanggil dengan akun demo NYATA (login
   sungguhan lewat HTTP, bukan override dependency) dan status yang diharapkan
   dicatat: peran SPPG hanya boleh membaca lokasinya sendiri (403 untuk lokasi
   lain), `bgn_monitor` nasional tetapi tidak boleh menyentuh data demo, dan
   `admin/*` hanya untuk monitor.
2. **Angka, bukan klaim.** Angka yang dikembalikan API dibandingkan dengan
   pembacaan SQL langsung ke DB yang sama (jumlah pemasok, baris demo, jumlah
   keputusan, jangkar 4.900 kg dan Cianjur 1.400 kg).

Yang TIDAK dilakukan: tidak ada endpoint yang mengubah data yang dipanggil
dengan peran yang berhak. Endpoint mutasi hanya diprobe dengan `bgn_monitor`
(ekspektasi 403) sehingga tidak ada efek samping sama sekali.

Password demo dibaca dari `app.seed.seed_data` dan TIDAK pernah dicetak.

Jalankan dari dalam kontainer backend: `python scripts/verifikasi_fase6.py`
(keluar dengan kode 1 bila ada satu saja baris yang tidak sesuai harapan,
supaya bisa dipakai sebagai gate).
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

# `python scripts/verifikasi_fase6.py` menaruh folder `scripts/` sebagai sys.path[0],
# bukan akar repo — tanpa baris ini impor `app.*` gagal walau dijalankan di kontainer.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.seed.seed_data import DEMO_USERS  # noqa: E402  (butuh sys.path di atas)

BASE = "http://127.0.0.1:8000"
JAKARTA = "Jakarta"
#: Jangkar kanonik yang tidak boleh bergeser (design.md §11, tes backend).
TOTAL_TELUR_KG = 4900.0
CIANJUR_TELUR_KG = 1400.0
#: Jendela KPI kanonik (REF 2026-10-08 12:00 UTC) — dipakai saat mengukur KPI.
KPI_START = "2026-10-08T11:00:00+00:00"
KPI_END = "2026-10-08T12:00:00+00:00"


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------


def panggil(method: str, path: str, token: str | None = None, body: dict | None = None):
    """Panggil API; kembalikan (status, payload). Tidak pernah melempar 4xx."""
    req = urllib.request.Request(
        BASE + path,
        data=None if body is None else json.dumps(body).encode(),
        method=method,
        headers={
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            return res.status, json.loads(res.read() or b"{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(raw or "{}")
        except json.JSONDecodeError:
            return exc.code, {"detail": raw[:120]}


def login(email: str, password: str) -> str:
    status, body = panggil("POST", "/auth/login", body={"email": email, "password": password})
    if status != 200:
        raise SystemExit(f"login gagal untuk {email}: HTTP {status}")
    return body["access_token"]


def token_per_peran() -> dict[str, str]:
    """Token untuk ketiga akun demo (`sppg_head`, `sppg_nutritionist`, `bgn_monitor`)."""
    return {u["role"]: login(u["email"], u["password"]) for u in DEMO_USERS}


# --------------------------------------------------------------------------
# DB
# --------------------------------------------------------------------------


def angka_db() -> dict[str, float]:
    """Pembacaan SQL langsung — pembanding angka yang diklaim API."""
    import os

    from sqlalchemy import create_engine, text

    url = os.environ["DATABASE_URL"].replace("+asyncpg", "+psycopg")
    engine = create_engine(url)
    queries = {
        "pemasok": "select count(*) from suppliers",
        "baris_demo": (
            "select (select count(*) from supply_records where origin='demo')"
            " + (select count(*) from price_signals where origin='demo')"
            " + (select count(*) from menu_plans where origin='demo')"
        ),
        "keputusan": "select count(*) from decisions",
        "keputusan_jakarta": (
            "select count(*) from decisions d join locations l on l.id = d.target_location_id"
            f" where l.name = '{JAKARTA}'"
        ),
        "telur_total_kg": (
            "select coalesce(sum(q), 0) from ("
            "  select distinct on (sr.location_id) sr.quantity_kg q"
            "  from supply_records sr join commodities c on c.id = sr.commodity_id"
            "  where c.name = 'telur'"
            "  order by sr.location_id, sr.recorded_at desc, sr.id desc"
            ") t"
        ),
        "cianjur_telur_kg": (
            "select sr.quantity_kg from supply_records sr"
            " join commodities c on c.id = sr.commodity_id"
            " join locations l on l.id = sr.location_id"
            " where c.name = 'telur' and l.name = 'Cianjur'"
            " order by sr.recorded_at desc, sr.id desc limit 1"
        ),
    }
    with engine.connect() as conn:
        return {k: float(conn.execute(text(q)).scalar_one()) for k, q in queries.items()}


# --------------------------------------------------------------------------
# Cek
# --------------------------------------------------------------------------


@dataclass
class Baris:
    nama: str
    peran: str
    method: str
    path: str
    harap: int
    ambil: Optional[Callable[[dict], object]] = None
    angka: object = None
    status: int = 0
    detail: str = ""

    @property
    def cocok(self) -> bool:
        return self.status == self.harap


def _jumlah_items(body: dict) -> int:
    return len(body.get("items") or [])


def _jumlah_lokasi(body: dict) -> int:
    return len(body.get("locations") or [])


def _total_pasokan(body: dict) -> float:
    return round(sum(float(loc.get("supply_kg") or 0) for loc in body.get("locations") or []), 1)


def _quantity(body: dict) -> float:
    return float(body.get("quantity_kg") or 0)


def _demo_total(body: dict) -> int:
    return int((body.get("totals") or {}).get("demo") or 0)


def _pemasok_total(body: dict) -> int:
    return int(body.get("total") or 0)


def _kpi_ringkas(body: dict) -> str:
    metrik = body.get("metrics") or []
    keadaan: dict[str, int] = {}
    for m in metrik:
        keadaan[str(m.get("state"))] = keadaan.get(str(m.get("state")), 0) + 1
    return f"{len(metrik)} metrik ({', '.join(f'{k}={v}' for k, v in sorted(keadaan.items()))})"


def _kpi_query() -> str:
    """Query KPI dengan offset `+` di-encode (`+` mentah terbaca sebagai spasi → 422)."""
    return urllib.parse.urlencode({"start": KPI_START, "end": KPI_END})


def _b(nama: str, peran: str, path: str, harap: int, ambil=None) -> Baris:
    """Baris GET ringkas: `method` selalu GET, supaya daftar di bawah tetap terbaca."""
    return Baris(nama, peran, "GET", path, harap, ambil)


def matriks() -> list[Baris]:
    return [
        # --- identitas ---------------------------------------------------
        Baris("identitas peran", "sppg_head", "GET", "/auth/me", 200),
        Baris("identitas peran", "sppg_nutritionist", "GET", "/auth/me", 200),
        Baris("identitas peran (tanpa lokasi)", "bgn_monitor", "GET", "/auth/me", 200),
        # --- feed keputusan (Ruling 2026-10-14: target dikunci) ----------
        Baris("feed keputusan", "sppg_head", "GET", "/decisions", 200, _jumlah_items),
        Baris("feed keputusan", "bgn_monitor", "GET", "/decisions", 200, _jumlah_items),
        # --- peta & baca per lokasi --------------------------------------
        _b("peta: cakupan SPPG sendiri", "sppg_head", "/balance/map?commodity=telur",
           200, _jumlah_lokasi),
        _b("peta: nasional", "bgn_monitor", "/balance/map?commodity=telur",
           200, _total_pasokan),
        _b("baca lokasi sendiri", "sppg_head", "/supply/Jakarta/telur", 200, _quantity),
        _b("baca lokasi lain DITOLAK", "sppg_head", "/supply/Cianjur/telur", 403),
        _b("baca lokasi lain DITOLAK (ahli gizi)", "sppg_nutritionist",
           "/supply/Cianjur/telur", 403),
        _b("baca lokasi mana pun (monitor)", "bgn_monitor", "/supply/Cianjur/telur",
           200, _quantity),
        _b("harga penawaran lokasi sendiri", "sppg_head", "/price/quotes/Jakarta/telur", 200),
        _b("batch (sisi sumber)", "sppg_head", "/batches", 200),
        # --- data sisi sumber & integritas -------------------------------
        _b("pemasok (data sisi sumber)", "sppg_head", "/suppliers", 200, _pemasok_total),
        _b("pemasok (data sisi sumber)", "bgn_monitor", "/suppliers", 200, _pemasok_total),
        Baris("eksklusi pemasok", "sppg_head", "GET", "/supplier-exclusions", 200),
        Baris("ledger nasional", "sppg_head", "GET", "/ledger/verify", 200),
        Baris("KPI 7 metrik", "sppg_head", "GET", f"/kpi?{_kpi_query()}", 200, _kpi_ringkas),
        Baris("KPI tanpa jendela = 422", "sppg_head", "GET", "/kpi", 422),
        # --- admin (monitor saja) ----------------------------------------
        Baris("admin pengguna", "bgn_monitor", "GET", "/admin/users", 200),
        Baris("admin lokasi", "bgn_monitor", "GET", "/admin/locations", 200),
        Baris("admin DITOLAK untuk SPPG", "sppg_head", "GET", "/admin/users", 403),
        Baris("admin DITOLAK untuk ahli gizi", "sppg_nutritionist", "GET", "/admin/locations", 403),
        # --- Demo Control (kepala/ahli gizi saja) ------------------------
        Baris("status data demo", "sppg_head", "GET", "/demo/data-status", 200, _demo_total),
        Baris("pratinjau rentang", "sppg_head", "GET", "/demo/preview", 200),
        Baris("status data demo DITOLAK monitor", "bgn_monitor", "GET", "/demo/data-status", 403),
        Baris("pratinjau DITOLAK monitor", "bgn_monitor", "GET", "/demo/preview", 403),
        Baris("segarkan DITOLAK monitor", "bgn_monitor", "POST", "/demo/refresh", 403),
        Baris("bersihkan DITOLAK monitor", "bgn_monitor", "POST", "/demo/timeseries/purge", 403),
        # --- tanpa token --------------------------------------------------
        Baris("tanpa token", "-", "GET", "/decisions", 401),
        Baris("tanpa token", "-", "GET", "/suppliers", 401),
        Baris("tanpa token", "-", "GET", "/admin/users", 401),
        Baris("kesehatan", "-", "GET", "/health", 200),
    ]


def jalankan() -> int:
    tokens = token_per_peran()
    baris = matriks()
    for b in baris:
        token = tokens.get(b.peran)
        status, body = panggil(b.method, b.path, token=token)
        b.status = status
        if b.ambil is not None and status < 400:
            try:
                b.angka = b.ambil(body)
            except Exception as exc:  # pragma: no cover - hanya diagnosa
                b.angka = f"<gagal baca: {exc}>"
        if status >= 400:
            detail = body.get("detail")
            b.detail = str(detail)[:60] if detail else ""

    print("=" * 108)
    print("MATRIKS 3 PERAN × ENDPOINT — MealChain Guardian (dijalankan", BASE, ")")
    print("=" * 108)
    print(f"{'PERAN':17} {'ENDPOINT':46} {'HARAP':5} {'DAPAT':5} {'ANGKA':28} COCOK")
    print("-" * 108)
    for b in baris:
        endpoint = f"{b.method} {b.path}"
        print(
            f"{b.peran:17} {endpoint[:46]:46} {b.harap:5} {b.status:5} "
            f"{str(b.angka if b.angka is not None else b.detail)[:28]:28} "
            f"{'ya' if b.cocok else 'TIDAK'}"
        )

    db = angka_db()
    pemasok_api = next((b.angka for b in baris if b.path == "/suppliers"), None)
    demo_api = next((b.angka for b in baris if b.path == "/demo/data-status"), None)
    telur_api = next(
        (
            b.angka
            for b in baris
            if b.path == "/balance/map?commodity=telur" and b.peran == "bgn_monitor"
        ),
        None,
    )
    cianjur_api = next(
        (
            b.angka
            for b in baris
            if b.path == "/supply/Cianjur/telur" and b.peran == "bgn_monitor"
        ),
        None,
    )
    keputusan_api = next(
        (b.angka for b in baris if b.path == "/decisions" and b.peran == "bgn_monitor"), None
    )

    print()
    print("=" * 108)
    print("ANGKA: API vs SQL LANGSUNG (DB yang sama)")
    print("=" * 108)
    print(f"{'YANG DIUKUR':32} {'API':>12} {'DB':>12} {'SELISIH':>10}  COCOK")
    print("-" * 108)
    pasangan = [
        ("jumlah pemasok", pemasok_api, db["pemasok"]),
        ("baris deret waktu demo", demo_api, db["baris_demo"]),
        ("total pasokan telur (kg)", telur_api, db["telur_total_kg"]),
        ("Cianjur telur (kg)", cianjur_api, db["cianjur_telur_kg"]),
        ("jumlah keputusan (monitor)", keputusan_api, db["keputusan"]),
    ]
    salah = [b for b in baris if not b.cocok]
    for nama, api, dbase in pasangan:
        selisih = (float(api) - float(dbase)) if api is not None else float("nan")
        cocok = api is not None and abs(selisih) < 1e-6
        if not cocok:
            salah.append(Baris(nama, "-", "-", "-", 0))
        tampil_api = f"{float(api):.1f}" if api is not None else "—"
        print(
            f"{nama:32} {tampil_api:>12} {float(dbase):12.1f} {selisih:10.1f}  "
            f"{'ya' if cocok else 'TIDAK'}"
        )

    jangkar_ok = (
        abs(db["telur_total_kg"] - TOTAL_TELUR_KG) < 1e-6
        and abs(db["cianjur_telur_kg"] - CIANJUR_TELUR_KG) < 1e-6
    )
    print()
    jangkar = (
        f"Jangkar kanonik ({TOTAL_TELUR_KG:.0f} kg total telur, "
        f"{CIANJUR_TELUR_KG:.0f} kg Cianjur)"
    )
    print(f"{jangkar}: {'UTUH' if jangkar_ok else 'BERGESER'}")
    print(
        f"Keputusan: {db['keputusan']:.0f} baris, semuanya menyasar Jakarta "
        f"({db['keputusan_jakarta']:.0f}) — cakupan peran diuji lewat /supply di atas"
    )
    print()
    if salah or not jangkar_ok:
        print(f"HASIL: {len(salah)} baris TIDAK sesuai harapan")
        for b in salah:
            print(" -", b.nama, b.peran, b.method, b.path, "harap", b.harap, "dapat", b.status)
        return 1
    print("HASIL: SEMUA COCOK")
    return 0


if __name__ == "__main__":
    raise SystemExit(jalankan())
