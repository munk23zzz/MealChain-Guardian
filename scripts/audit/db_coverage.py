#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""db_coverage.py — generator matriks cakupan database MealChain Guardian.

Menjawab satu pertanyaan: **setiap bagian layar di frontend, datanya datang dari
tabel.kolom yang mana — dan apakah datanya benar-benar ada?** Hasilnya ditulis ke
`docs/db-coverage-matrix.md` dan ditulis ulang setiap kali skrip dijalankan.

Skrip ini TIDAK menyalin teks statis. Semua klaim diverifikasi ke kondisi live:

  1. daftar route        -> impor `app.main` di kontainer backend, cetak path+method
  2. skema               -> `Base.metadata` (SQLAlchemy) + `information_schema` (DB)
  3. kosakata enum       -> CHECK constraint dari `pg_constraint` + `Literal[...]`
                            di kode + nilai `select distinct` di DB
  4. endpoint            -> login user demo, panggil GET, rekam status/kunci/jumlah
  5. rantai frontend     -> `frontend/lib/api.ts` (+ modul request lain) diparse
                            untuk nama fungsi -> METHOD path, lalu dicocokkan ke
                            route live; komponen diparse untuk label yang dipakai
  6. bukti baris         -> satu query SQL per baris matriks (jumlah + contoh id)

Setiap baris matriks membawa pemeriksaan: label UI ada di komponen? fungsi api ada
dan menunjuk route yang benar? tabel.kolom ada di DB? query bukti mengembalikan
baris? Kalau salah satu gagal, barisnya ditandai dan masuk daftar "klaim tak
terverifikasi" — bukan disembunyikan.

Pemakaian:
    python3 scripts/audit/db_coverage.py            # tulis docs/db-coverage-matrix.md
    python3 scripts/audit/db_coverage.py --check    # tulis + periksa ulang angka di berkas
    python3 scripts/audit/db_coverage.py --quiet    # hanya ringkasan stdout

Prasyarat: stack demo berjalan (backend :8000, kontainer `mealchain-postgres`),
dijalankan dari akar repo. Tidak menulis apa pun ke DB: hanya SELECT.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = ROOT / "docs" / "db-coverage-matrix.md"
PG_CONTAINER = "mealchain-postgres"
PG_USER = "mealchain"
PG_DB = "mealchain"
BACKEND_SERVICE = "backend"
API_BASE = "http://localhost:8000"
SEP = "\x1f"
WIB = timezone(timedelta(hours=7))

DEMO_LOGIN = {
    "sppg_head": {"email": "sppg.head@demo.local", "password": "Demo#SPPG2026"},
    "bgn_monitor": {"email": "bgn.monitor@demo.local", "password": "Demo#BGN2026"},
}

# ---------------------------------------------------------------------------
# 1. Shell + docker helper
# ---------------------------------------------------------------------------


def run(cmd: list[str], stdin: str | None = None, timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=str(ROOT), input=stdin, capture_output=True, text=True, timeout=timeout
    )


def backend_py(code: str) -> str:
    """Jalankan python di dalam kontainer backend (mount repo = /app)."""
    proc = run(["docker", "compose", "exec", "-T", BACKEND_SERVICE, "python", "-c", code])
    if proc.returncode != 0:
        raise RuntimeError(f"gagal menjalankan python di backend:\n{proc.stderr.strip()}")
    return proc.stdout


def psql(sql: str) -> list[list[str]]:
    """SELECT di DB demo; hasil -At -F <US> (satu baris = list kolom)."""
    proc = run(
        [
            "docker", "exec", PG_CONTAINER, "psql", "-U", PG_USER, "-d", PG_DB,
            "-At", "-F", SEP, "-v", "ON_ERROR_STOP=1", "-c", sql,
        ]
    )
    if proc.returncode != 0:
        raise RuntimeError(f"psql gagal: {sql[:120]}...\n{proc.stderr.strip()}")
    out = proc.stdout.strip("\n")
    if not out:
        return []
    return [line.split(SEP) for line in out.split("\n")]


def scalar(sql: str) -> str:
    rows = psql(sql)
    return rows[0][0] if rows and rows[0] else ""


# ---------------------------------------------------------------------------
# 2. Intropeksi live: route FastAPI, skema, CHECK
# ---------------------------------------------------------------------------

ROUTE_PROBE = r"""
import app.main as m
for r in m.app.routes:
    p = getattr(r, "path", None)
    if p is None:
        continue
    ms = ",".join(sorted(x for x in getattr(r, "methods", ()) if x not in ("HEAD", "OPTIONS")))
    print("%s\t%s\t%s" % (ms, p, getattr(r, "name", "")))
"""

META_PROBE = r"""
import app.models  # noqa: F401  (mendaftarkan seluruh model ke Base.metadata)
from app.db import Base
for t in Base.metadata.sorted_tables:
    for c in t.columns:
        print("%s\t%s\t%s\t%s" % (t.name, c.name, c.type, "NULL" if c.nullable else "NOT NULL"))
"""


def live_routes() -> list[dict]:
    rows = []
    for line in backend_py(ROUTE_PROBE).strip().split("\n"):
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        methods, path = parts[0], parts[1]
        name = parts[2] if len(parts) > 2 else ""
        for m in methods.split(","):
            if m:
                rows.append({"method": m, "path": path, "name": name})
    return rows


def live_metadata() -> dict[str, dict[str, str]]:
    """table -> {column: type} dari SQLAlchemy Base.metadata."""
    schema: dict[str, dict[str, str]] = {}
    for line in backend_py(META_PROBE).strip().split("\n"):
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        schema.setdefault(parts[0], {})[parts[1]] = parts[2]
    return schema


def db_columns() -> dict[str, dict[str, str]]:
    """table -> {column: data_type} dari information_schema (yang benar-benar ada)."""
    rows = psql(
        "select table_name, column_name, data_type from information_schema.columns "
        "where table_schema='public' order by table_name, ordinal_position"
    )
    out: dict[str, dict[str, str]] = {}
    for table, column, dtype in rows:
        out.setdefault(table, {})[column] = dtype
    return out


def db_checks() -> dict[str, dict[str, str]]:
    rows = psql(
        "select c.relname, con.conname, pg_get_constraintdef(con.oid) from pg_constraint con "
        "join pg_class c on c.oid=con.conrelid join pg_namespace n on n.oid=c.relnamespace "
        "where n.nspname='public' and con.contype='c'"
    )
    out: dict[str, dict[str, str]] = {}
    for table, name, definition in rows:
        out.setdefault(table, {})[name] = definition
    return out


def wait_for_stable_db(max_seconds: int = 150, gap: int = 5) -> tuple[dict[str, int], int]:
    """Tunggu sampai isi DB berhenti bergerak DAN tabel inti terisi.

    DB demo dipakai bersama: proses lain bisa sedang menjalankan reset/seed
    deret demo. Mengaudit di tengah reset menghasilkan laporan yang salah
    tentang aplikasinya (bukan tentang datanya). Fungsi ini menunggu sampai
    dua potret berturut-turut sama dan `decisions` serta `batches` terisi.
    """
    prev = db_snapshot()
    attempts = max(1, max_seconds // gap)
    for i in range(attempts):
        time.sleep(gap)
        cur = db_snapshot()
        stable = cur == prev
        ready = cur.get("decisions", 0) > 0 and cur.get("batches", 0) > 0
        prev = cur
        if stable and ready:
            return cur, i + 1
    return prev, attempts


def db_snapshot() -> dict[str, int]:
    """Jumlah baris SEBENARNYA (count(*)) per tabel — bukan n_live_tup.

    Dipakai dua kali (awal & akhir run): DB demo bisa sedang ditulis proses lain
    (reset/seed deret demo), dan laporan harus bisa menyebut apakah isinya
    bergerak selama audit.
    """
    rows = psql(
        "select relname, (xpath('/row/c/text()', query_to_xml("
        "format('select count(*) c from %I', relname), false, true, '')))[1]::text::int "
        "from pg_class where relkind='r' and relnamespace='public'::regnamespace "
        "order by relname"
    )
    return {name: int(count) for name, count in rows}


def origin_split(tables: list[str]) -> dict[str, dict[str, int]]:
    """Komposisi seed vs demo per tabel yang punya kolom `origin`."""
    out: dict[str, dict[str, int]] = {}
    for table in tables:
        try:
            rows = psql(f"select coalesce(origin::text,'(NULL)'), count(*) from {table} group by 1")
        except RuntimeError:
            continue
        out[table] = {value: int(n) for value, n in rows}
    return out


def session_rows(tables: list[str]) -> dict[str, int]:
    """Baris yang terikat sesi demo (`demo_session_id` terisi)."""
    out: dict[str, int] = {}
    for table in tables:
        try:
            out[table] = int(scalar(f"select count(*) from {table} where demo_session_id is not null"))
        except RuntimeError:
            continue
    return out


# ---------------------------------------------------------------------------
# 3. HTTP: login + probe GET
# ---------------------------------------------------------------------------


def http_json(method: str, path: str, token: str | None = None, body: dict | None = None) -> tuple[int, object]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API_BASE + path, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    # Satu percobaan ulang untuk 5xx: DB demo bisa sedang ditulis proses lain
    # (reset/seed deret demo), dan galat sesaat itu bukan temuan tentang layar.
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                raw = resp.read().decode("utf-8", "replace")
                status = resp.status
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            status = exc.code
        except Exception as exc:  # noqa: BLE001 — transport failure = temuan, bukan crash
            return -1, {"transport_error": repr(exc)}
        if status < 500 or attempt == 2:
            break
        time.sleep(2)
    try:
        return status, json.loads(raw)
    except json.JSONDecodeError:
        return status, {"non_json": raw[:400]}


def login(role: str) -> str:
    status, payload = http_json("POST", "/auth/login", body=DEMO_LOGIN[role])
    if status != 200 or not isinstance(payload, dict) or "access_token" not in payload:
        raise RuntimeError(f"login {role} gagal: HTTP {status} {payload}")
    return payload["access_token"]


def flatten_keys(obj: object, prefix: str = "", depth: int = 0) -> set[str]:
    keys: set[str] = set()
    if depth > 2:
        return keys
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(k)
            keys |= flatten_keys(v, prefix + k + ".", depth + 1)
    elif isinstance(obj, list):
        for item in obj[:3]:
            keys |= flatten_keys(item, prefix, depth + 1)
    return keys


def payload_count(obj: object) -> int:
    """Jumlah 'baris' yang bisa dibaca mata dari sebuah respons."""
    if isinstance(obj, list):
        return len(obj)
    if isinstance(obj, dict):
        best = 0
        for v in obj.values():
            if isinstance(v, list):
                best = max(best, len(v))
            elif isinstance(v, dict):
                best = max(best, payload_count(v))
        if best == 0:
            return 1 if obj else 0
        return best
    return 1 if obj is not None else 0


# ---------------------------------------------------------------------------
# 4. Index frontend: fungsi api.ts -> METHOD path, komponen, tab, hook
# ---------------------------------------------------------------------------

REQUEST_TEMPLATE = re.compile(r"`(/(?:[^`\\\n]|\$\{[^}]*\})*)`")
REQUEST_STRING = re.compile(r'"(\/[^"\n]*)"')


def normalize_path(raw: str) -> str:
    path = raw.split("?")[0]
    # `${var}` yang menempel pada segmen (mis. "/sap/purchase-orders${akhiran}")
    # adalah sufiks query, bukan segmen path: buang. Yang menggantikan satu
    # segmen penuh ("/decisions/${id}/traces") jadi wildcard.
    path = re.sub(r"(?<=[^/])\$\{[^}]*\}", "", path)
    path = re.sub(r"\$\{[^}]*\}", "{param}", path)
    path = re.sub(r"\{[^}]*\}", "{param}", path)
    return path.rstrip(",")


def parse_api_index() -> dict[str, dict]:
    """fungsi -> {method, path, file}. Mendukung lebih dari satu modul request."""
    index: dict[str, dict] = {}
    for rel in ("frontend/lib/api.ts", "frontend/lib/supplier-exclusions.ts"):
        path_file = ROOT / rel
        if not path_file.exists():
            continue
        text = path_file.read_text(encoding="utf-8", errors="replace")
        names = re.findall(r"^export\s+(?:async\s+)?function\s+(\w+)", text, flags=re.M)
        chunks = re.split(r"^export\s+(?:async\s+)?function\s+\w+", text, flags=re.M)[1:]
        for name, body in zip(names, chunks):
            body = body.split("\nexport ")[0]
            resolved = None
            if "balancePath(" in body:
                resolved = "/balance/{param}/{param}"
            if resolved is None:
                match = REQUEST_TEMPLATE.search(body)
                if match:
                    resolved = normalize_path(match.group(1))
            if resolved is None:
                match = REQUEST_STRING.search(body)
                if match:
                    resolved = normalize_path(match.group(1))
            if resolved is None and "/sap/purchase-orders/" in body:
                resolved = "/sap/purchase-orders/{param}/pdf"
            method_match = re.search(r'method:\s*["\'](\w+)["\']', body)
            index[name] = {
                "method": (method_match.group(1).upper() if method_match else "GET"),
                "path": resolved or "(tidak terbaca)",
                "file": rel,
            }
    return index


def read_component_sources() -> dict[str, str]:
    sources: dict[str, str] = {}
    for path_file in sorted((ROOT / "frontend" / "components").glob("*.tsx")):
        sources[path_file.stem] = path_file.read_text(encoding="utf-8", errors="replace")
    sources["page"] = (ROOT / "frontend" / "app" / "page.tsx").read_text(
        encoding="utf-8", errors="replace"
    )
    return sources


def rel_source(rel: str) -> str:
    path_file = ROOT / rel
    if not path_file.exists():
        return ""
    return path_file.read_text(encoding="utf-8", errors="replace")


def parse_nav_items() -> list[dict]:
    src = rel_source("frontend/app/page.tsx")
    start = src.find("const navItems")
    end = src.find("const visibleNavItems", start)
    block = src[start:end]
    items = []
    for match in re.finditer(r"id:\s*\"([\w-]+)\"", block):
        # label ikut setelah id, tetapi bisa terpisah beberapa baris oleh
        # komentar — karena itu dicari ke depan, bukan satu regex gabungan.
        tail = block[match.end(): match.end() + 500]
        label_match = re.search(r"label:\s*(`[^`]*`|\"[^\"]*\")", tail)
        if not label_match:
            continue
        label = label_match.group(1).strip("`\"")
        # label bertemplat ("Recommendations${n ? ` (${n})` : \"\"}") dipotong di
        # '${' pertama: yang dicari nama layarnya, bukan ekspresi hitungannya.
        label = label.split("${")[0].strip()
        items.append({"id": match.group(1), "label": label})
    return items


def parse_tab_components() -> tuple[dict[str, list[str]], dict[str, str]]:
    """tab id -> (komponen yang dirender, teks blok JSX-nya).

    Blok dikenali dari `{tab === "<id>" && ...}`. Bentuknya bisa
    `&& (` (blok kurung), `&& isApprover && (` (penjaga peran), atau
    `&& <Komponen ... />` (satu baris). Titik awal blok = '(' pertama sebelum
    '<' pertama; kalau '<' lebih dulu, blok berakhir di akhir baris.
    """
    src = rel_source("frontend/app/page.tsx")
    comps: dict[str, set[str]] = {}
    blocks: dict[str, str] = {}
    for match in re.finditer(r'\{tab === "([\w-]+)" &&\s*', src):
        tab = match.group(1)
        i = match.end()
        window = src[i:i + 200]
        first_paren = window.find("(")
        first_tag = window.find("<")
        if first_paren != -1 and (first_tag == -1 or first_paren < first_tag):
            i += first_paren
            depth = 0
            start = i
            while i < len(src):
                ch = src[i]
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
                i += 1
            block = src[start:i]
        else:
            end = src.find("\n", i)
            block = src[i:end if end != -1 else len(src)]
        comps.setdefault(tab, set()).update(re.findall(r"<([A-Z][A-Za-z0-9]+)", block))
        blocks[tab] = blocks.get(tab, "") + "\n" + block
    return {k: sorted(v) for k, v in comps.items()}, blocks


def parse_hooks() -> dict[str, list[str]]:
    """hook -> fungsi api yang dipanggilnya (rantai komponen -> hook -> api)."""
    out: dict[str, list[str]] = {}
    for path_file in sorted((ROOT / "frontend" / "lib" / "hooks").glob("use*.ts")):
        src = path_file.read_text(encoding="utf-8", errors="replace")
        fns = sorted(set(re.findall(r"\b(fetch[A-Z]\w+|run[A-Z]\w+|verifyLedger)\s*\(", src)))
        out[path_file.stem] = fns
    return out


def hook_bindings(page_src: str) -> dict[str, list[str]]:
    """hook -> nama variabel hasil destructure/assignment di page.tsx.

    Dipakai untuk mengatribusikan hook ke tab: blok `{tab === "x" && ...}`
    memakai variabel (`kpi`, `kpiQuery`), bukan nama hook-nya.
    """
    out: dict[str, list[str]] = {}
    for match in re.finditer(r"const\s*\{([^}]*)\}\s*=\s*(use[A-Z]\w+)\(", page_src):
        for part in match.group(1).split(","):
            # `data: decisions` → nama yang dipakai di JSX adalah aliasnya.
            pieces = part.split(":")
            name = (pieces[1] if len(pieces) > 1 else pieces[0]).split("=")[0].strip()
            if name:
                out.setdefault(match.group(2), []).append(name)
    for match in re.finditer(r"const\s+(\w+)\s*=\s*(use[A-Z]\w+)\(", page_src):
        var = match.group(1)
        out.setdefault(match.group(2), []).append(var)
        # `const decisions = decisionsQuery.data` → yang dipakai di JSX adalah
        # turunan ini, bukan variabel query-nya.
        for alias in re.finditer(
            r"const\s+(\w+)\s*=\s*" + re.escape(var) + r"\.\w+", page_src
        ):
            out[match.group(2)].append(alias.group(1))
    return out


def tab_api_functions(block: str, comps: list[str], components: dict[str, str],
                      api_index: dict[str, dict], hooks: dict[str, list[str]],
                      bindings: dict[str, list[str]]) -> dict:
    """Fungsi api yang dijangkau satu tab, dipisah menurut jalurnya.

    - `direct`: dipanggil langsung di blok tab atau di komponen yang dirender tab
    - `hooks` : hook yang variabelnya dipakai blok tab (atribusi dari nama variabel)
    - `via_hooks`: fungsi api yang dipanggil hook tersebut
    Pemisahan ini disengaja: atribusi lewat variabel bersifat perkiraan, jadi ia
    tidak dicampur ke klaim "dipanggil langsung".
    """
    haystacks = [block] + [components.get(c, "") for c in comps]
    direct = sorted(
        fn for fn in api_index
        if any(re.search(r"\b" + re.escape(fn) + r"\s*\(", h) for h in haystacks)
    )
    used_hooks = sorted(
        hook for hook, names in bindings.items()
        if hook in hooks and any(re.search(r"\b" + re.escape(n) + r"\b", block) for n in names)
    )
    via_hooks = sorted({fn for hook in used_hooks for fn in hooks.get(hook, [])})
    return {"direct": direct, "hooks": used_hooks, "via_hooks": via_hooks}


def module_imported(stem: str, components: dict[str, str]) -> bool:
    """Berkas komponen diimpor di tempat lain (default atau named export)."""
    pattern = re.compile(
        r'from\s+"\./' + re.escape(stem) + r'"'
        r'|from\s+"\.\./components/' + re.escape(stem) + r'"'
    )
    return any(
        pattern.search(src) for other, src in components.items() if other != stem
    )


def orphan_components(components: dict[str, str]) -> list[str]:
    """Komponen yang tidak pernah dipasang: tak jadi tag JSX dan modulnya tak diimpor.

    Impor saja sudah cukup untuk dianggap terpakai karena sebagian berkas
    mengekspor beberapa komponen (mis. `SupplierExclusionView` dari
    `SupplierExclusionPanel.tsx`) dan yang dipakai bukan default export-nya.
    """
    orphans = []
    for name in components:
        if name == "page":
            continue
        pattern = re.compile(r"<" + re.escape(name) + r"[\s/>]")
        used_as_tag = any(
            pattern.search(src) for other, src in components.items() if other != name
        )
        if not used_as_tag and not module_imported(name, components):
            orphans.append(name)
    return sorted(orphans)


# ---------------------------------------------------------------------------
# 5. Resolusi id nyata dari DB (bukan id karangan)
# ---------------------------------------------------------------------------


def resolve_params(tokens: dict[str, str]) -> dict[str, str]:
    """Id nyata dari DB, lalu DIVERIFIKASI lewat API.

    DB demo bisa sedang di-reset proses lain, jadi id yang baru dibaca bisa
    keburu hilang. Kandidat diambil dari query (bukan dikarang), lalu dicoba
    sampai ada yang membalas 2xx untuk peran SPPG; kalau semua gagal, jatuh ke
    id dari daftar yang memang dikembalikan API.
    """
    jakarta = scalar("select id from locations where name='Jakarta'")
    cek = []
    if jakarta:
        cek = [
            row[0] for row in psql(
                "select d.id from decisions d "
                "left join agent_traces t on t.decision_id=d.id "
                f"where d.target_location_id='{jakarta}' "
                "group by d.id order by count(t.id) desc, d.id limit 5"
            )
        ]
    decision_id = ""
    for candidate in cek:
        status, _ = http_json("GET", f"/decisions/{candidate}", tokens["sppg_head"])
        if status == 200:
            decision_id = candidate
            break
    if not decision_id:
        status, payload = http_json("GET", "/decisions?limit=5", tokens["sppg_head"])
        if status == 200 and isinstance(payload, dict) and payload.get("items"):
            decision_id = str(payload["items"][0].get("decision_id", ""))

    batch_candidates = [
        row[0] for row in psql(
            "select b.id from batches b join batch_receipts r on r.batch_id=b.id "
            + (f"where b.location_id='{jakarta}' " if jakarta else "")
            + "order by b.id limit 5"
        )
    ] if psql("select count(*) from batch_receipts")[0][0] != "0" else []
    batch_id = batch_candidates[0] if batch_candidates else scalar(
        "select id from batches " + (f"where location_id='{jakarta}' " if jakarta else "") + "order by id limit 1"
    )

    params: dict[str, str] = {
        "location": "Jakarta",
        "commodity": "telur",
        "location_id": jakarta,
        "decision_id": decision_id,
        "batch_id": batch_id,
        "receipt_id": scalar("select id from batch_receipts order by id limit 1"),
        "exclusion_id": scalar("select id from supplier_exclusions order by id limit 1"),
        "supplier_id": scalar("select id from suppliers order by id limit 1"),
    }
    # PO yang benar-benar terlihat oleh peran SPPG (bukan nomor yang ditebak)
    params["po_number"] = scalar(
        "select po_number from sap_mock_purchase_orders where decision_id is not null "
        "order by po_number limit 1"
    )
    if not params["po_number"]:
        params["po_number"] = scalar("select po_number from sap_mock_purchase_orders order by po_number limit 1")
    # jendela KPI/agenda diturunkan dari data, bukan tanggal hari ini
    params["start"] = scalar(
        "select to_char(min(delivered_at) at time zone 'Asia/Jakarta', 'YYYY-MM-DD') from delivery_events"
    ) or "2026-09-01"
    params["start_iso"] = params["start"] + "T00:00:00+07:00"
    params["end"] = scalar(
        "select to_char(max(delivered_at) at time zone 'Asia/Jakarta', 'YYYY-MM-DD') from delivery_events"
    ) or "2026-10-21"
    params["end_iso"] = params["end"] + "T23:59:59+07:00"
    return params


def fill(template: str, params: dict[str, str]) -> str:
    def repl(match: re.Match) -> str:
        key = match.group(1)
        value = str(params.get(key, match.group(0)))
        # Nilai yang mengisi parameter query harus di-encode: `+07:00` pada
        # timestamp RFC3339 akan dibaca server sebagai spasi (422).
        before = template[match.start() - 1] if match.start() else ""
        return urllib.parse.quote(value, safe="") if before == "=" else value

    return re.sub(r"\{(\w+)\}", repl, template)


# ---------------------------------------------------------------------------
# 6. Registry baris matriks
#
# Setiap baris = satu bagian layar. `fields` adalah teks yang HARUS ditemukan di
# sumber komponen (bukti bahwa bagian itu benar-benar dirender), `api` adalah
# fungsi frontend yang harus ada di index request, `tables` adalah kolom yang
# harus ada di skema live, `evidence` adalah query yang membuktikan datanya ada.
# ---------------------------------------------------------------------------


def S(table: str, **kw) -> dict:
    base = {
        "table": table,
        "key": "id",
        "dim_table": "locations",
        "dim_col": "location_id",
        "where": "",
        "date_col": None,
        "num_col": None,
        "text_col": None,
        "sort_col": None,
        "null_col": None,
        "page_size": 10,
    }
    base.update(kw)
    return base


# Panel yang sengaja dipensiunkan (bukan cacat data). Bukti: tes PRD mengunci
# `page.tsx` agar tidak memuat komponennya, jadi memasangnya kembali akan
# memerahkan tes. Nilainya = kutipan bukti yang ikut dicetak di matriks.
RETIRED: dict[str, str] = {
    "Konsol operasi — snapshot kondisi": (
        "sengaja: `tests/prd-nav.test.tsx:60` menuntut `page.tsx` TANPA `<OpsConsole`"
    ),
    "Konsol operasi — analisis agent & usulan": (
        "sengaja: sama, `tests/prd-nav.test.tsx:60` (console tidak dipasang)"
    ),
    "Status integrasi (panel tidak terpasang)": (
        "sengaja: `tests/prd-nav.test.tsx:50-52` menuntut `page.tsx` TANPA "
        "`IntegrationStatusPanel`/`useIntegrationStatus`"
    ),
}

SECTIONS: list[dict] = [
    # ---------------- Hari Ini ----------------
    {
        "screen": "today",
        "section": "Tile status hari ini",
        "anchor": "frontend/components/TodayDashboard.tsx",
        "fields": ["Hari Ini", "Menunggu persetujuan", "Ditandai verifikator", "Rekomendasi"],
        "api": ["fetchDecisions", "fetchBatches", "fetchKpis"],
        "tables": [
            "decisions.status", "decisions.expires_at", "decisions.decision_type",
            "batches.usable_until", "batches.safety_status", "delivery_events.delivered_at",
        ],
        "evidence": (
            "select count(*)::text, coalesce(min(id::text),'-') from decisions "
            "where status in ('pending_approval','verifier_flagged')"
        ),
        "probe": "/decisions",
        "state": S("decisions", dim_col="target_location_id", date_col="expires_at",
                   text_col="rejection_reason", sort_col="status", null_col="rejection_reason",
                   page_size=10),
    },
    {
        "screen": "today",
        "section": "Agenda harian",
        "anchor": "frontend/components/TodayDashboard.tsx",
        "fields": ["Agenda harian", "Tidak ada agenda yang belum lewat tenggat"],
        "api": ["fetchAgenda"],
        "tables": ["menu_plans.plan_date", "menu_plans.planned_portions", "delivery_events.delivered_at"],
        "evidence": (
            "select count(*)::text, coalesce(min(plan_date::text),'-') from menu_plans"
        ),
        "probe": "/agenda?start={start}&end={end}",
        "state": S("menu_plans", date_col="plan_date", num_col="planned_portions",
                   page_size=10, sort_col="plan_date"),
    },
    {
        "screen": "today",
        "section": "Rantai audit (Merkle ledger)",
        "anchor": "frontend/components/TodayDashboard.tsx",
        "fields": ["Rantai audit", "Blok terverifikasi", "Kode verifikasi"],
        "api": ["verifyLedger"],
        "tables": ["ledger_blocks.payload_hash", "ledger_blocks.prev_hash", "ledger_blocks.height"],
        "evidence": (
            "select count(*)::text, coalesce(min(height::text),'-') from ledger_blocks"
        ),
        "probe": "/ledger/verify",
        "state": S("ledger_blocks", dim_table=None, date_col="created_at",
                   text_col="payload", sort_col="height", null_col="entity_id", page_size=20),
    },
    # ---------------- Overview ----------------
    {
        "screen": "overview",
        "section": "Ringkasan peta pasokan (bento KPI)",
        "anchor": "frontend/app/page.tsx",
        "fields": ["Overview Pasokan &amp; Distribusi", "Selisih pasokan jaringan", "Data simulasi", "Sinkron otomatis"],
        "api": ["fetchBalanceMap"],
        "tables": [
            "supply_records.quantity_kg", "demand_records.quantity_kg",
            "locations.name", "locations.role_hint",
        ],
        "evidence": (
            "select count(*)::text, coalesce(min(name),'-') from locations"
        ),
        "probe": "/balance/map?commodity={commodity}",
        "state": S("supply_records", dim_col="location_id", date_col="recorded_at",
                   num_col="quantity_kg", text_col="source", sort_col="quantity_kg",
                   page_size=10),
    },
    {
        "screen": "overview",
        "section": "Peta kondisi komoditas",
        "anchor": "frontend/components/SupplyMap.tsx",
        "fields": ["Peta kondisi komoditas", "Legenda status", "Status Lokasi", "Pemasok"],
        "api": ["fetchBalanceMap", "fetchBalance"],
        "tables": [
            "supply_records.quantity_kg", "locations.latitude", "locations.longitude",
            "suppliers.latitude", "suppliers.longitude",
        ],
        "evidence": (
            "select count(distinct location_id)::text, coalesce(min(location_id::text),'-') "
            "from supply_records"
        ),
        "probe": "/balance/map?commodity={commodity}",
        "state": S("supply_records", dim_col="location_id", date_col="recorded_at",
                   num_col="quantity_kg", text_col="source", sort_col="quantity_kg",
                   page_size=10),
    },
    {
        "screen": "overview",
        "section": "Grafik kecukupan pasokan",
        "anchor": "frontend/components/SupplyAdequacyChart.tsx",
        "fields": ["Kecukupan pasokan", "Kesegaran", "Legenda kualitas stok"],
        "api": ["fetchBalanceMap"],
        "tables": [
            "batches.freshness_score", "supply_records.quantity_kg", "demand_records.quantity_kg",
        ],
        "evidence": (
            "select count(*)::text, coalesce(min(id::text),'-') from batches "
            "where freshness_score is not null"
        ),
        "probe": "/balance/map?commodity={commodity}",
        "state": S("batches", dim_col="location_id", date_col="harvested_at",
                   num_col="freshness_score", text_col="certification_status",
                   sort_col="freshness_score", null_col="usable_until", page_size=10),
    },
    {
        "screen": "overview",
        "section": "Grafik keseimbangan pasokan",
        "anchor": "frontend/components/SupplyBalanceChart.tsx",
        "fields": ["Pasokan per lokasi", "Legenda keseimbangan pasokan"],
        "api": ["fetchBalanceMap"],
        "tables": ["supply_records.quantity_kg", "demand_records.quantity_kg", "locations.name"],
        "evidence": (
            "select count(*)::text, coalesce(min(id::text),'-') from demand_records"
        ),
        "probe": "/balance/map?commodity={commodity}",
        "state": S("demand_records", dim_col="location_id", date_col="needed_by",
                   num_col="quantity_kg", sort_col="quantity_kg", page_size=10),
    },
    {
        "screen": "overview",
        "section": "Kartu informasi pengiriman",
        "anchor": "frontend/components/ShipmentCard.tsx",
        "fields": ["Informasi pengiriman", "Periksa kiriman"],
        "api": ["fetchSupplierRoutes"],
        "tables": [
            "road_routes.distance_m", "road_routes.duration_s", "batches.dispatched_at",
            "suppliers.latitude",
        ],
        "evidence": (
            "select count(*)::text, coalesce(min(route_key),'-') from road_routes"
        ),
        "probe": "/supplier-routes?limit=50",
        "state": S("road_routes", dim_table=None, date_col="fetched_at",
                   num_col="distance_m", text_col="route_key", sort_col="distance_m",
                   page_size=20),
    },
    {
        "screen": "overview",
        "section": "Telemetri node",
        "anchor": "frontend/components/NodeTelemetry.tsx",
        "fields": ["Telemetri node", "Memuat kondisi lokasi…"],
        "api": ["fetchBalanceMap"],
        "tables": ["supply_records.quantity_kg", "locations.latitude", "locations.longitude"],
        "evidence": (
            "select count(*)::text, coalesce(min(name),'-') from locations "
            "where latitude is not null"
        ),
        "probe": "/balance/map?commodity={commodity}",
        "state": S("supply_records", dim_col="location_id", date_col="recorded_at",
                   num_col="quantity_kg", text_col="source", sort_col="quantity_kg",
                   page_size=10),
    },
    # ---------------- Recommendations ----------------
    {
        "screen": "recommendations",
        "section": "Feed rekomendasi + filter/sort + pager",
        "anchor": "frontend/components/RecommendationCard.tsx",
        "fields": ["Rekomendasi baru", "Penyeimbangan pasokan regional", "Lewat tenggat"],
        "api": ["fetchDecisions"],
        "tables": [
            "decisions.decision_type", "decisions.status", "decisions.quantity_kg",
            "decisions.safe_delivered_cost", "decisions.expires_at",
        ],
        "evidence": (
            "select count(*)::text, coalesce(min(id::text),'-') from decisions"
        ),
        "probe": "/decisions?limit=100",
        "state": S("decisions", dim_col="target_location_id", date_col="expires_at",
                   num_col="safe_delivered_cost", text_col="rejection_reason",
                   sort_col="created_at", null_col="rejection_reason", page_size=10),
    },
    {
        "screen": "recommendations",
        "section": "Konsol operasi — snapshot kondisi",
        "anchor": "frontend/components/OpsConsole.tsx",
        "fields": ["Muat kondisi", "Pasokan", "Permintaan", "Surplus", "Shortage"],
        "api": ["fetchBalance"],
        "tables": ["supply_records.quantity_kg", "demand_records.quantity_kg", "locations.name"],
        "evidence": (
            "select count(*)::text, coalesce(min(id::text),'-') from supply_records "
            "where location_id=(select id from locations where name='Jakarta')"
        ),
        "probe": "/balance/{location}/{commodity}",
        "state": S("supply_records", dim_col="location_id", date_col="recorded_at",
                   num_col="quantity_kg", text_col="source", sort_col="quantity_kg",
                   page_size=10),
    },
    {
        "screen": "recommendations",
        "section": "Konsol operasi — analisis agent & usulan",
        "anchor": "frontend/components/OpsConsole.tsx",
        "fields": ["Jalankan Analisis Agent", "SDC", "Ajukan", "Hasil Event 1 penuh"],
        "api": ["runAnalysis", "createDecision", "proposeAction", "runEvent1"],
        "tables": [
            "decisions.safe_delivered_cost", "decisions.quantity_kg",
            "price_signals.price_per_kg", "agent_traces.step_name",
        ],
        "evidence": (
            "select count(*)::text, coalesce(min(id::text),'-') from price_signals"
        ),
        "probe": "/balance/analyze",
        "probe_method": "POST",
        "probe_body": {"commodity": "telur"},
        "state": S("price_signals", dim_col="location_id", date_col="recorded_at",
                   num_col="price_per_kg", text_col="source", sort_col="price_per_kg",
                   page_size=10),
    },
    {
        "screen": "recommendations",
        "section": "Panel anomali harga (Event 2)",
        "anchor": "frontend/components/Event2Panel.tsx",
        "fields": ["Event 2 — Deteksi Anomali Harga", "Deviasi", "Klasifikasi", "Masuk review queue"],
        "api": ["fetchPriceQuotes"],
        "tables": [
            "price_signals.price_per_kg", "price_signals.source", "price_signals.supplier_id",
        ],
        "evidence": (
            "select count(*)::text, coalesce(min(source),'-') from price_signals "
            "where location_id=(select id from locations where name='Jakarta')"
        ),
        "probe": "/price/quotes/{location}/{commodity}",
        "state": S("price_signals", dim_col="location_id", date_col="recorded_at",
                   num_col="price_per_kg", text_col="source", sort_col="price_per_kg",
                   page_size=10),
    },
    # ---------------- Decision & Evidence ----------------
    {
        "screen": "evidence",
        "section": "Ringkasan keputusan & bukti",
        "anchor": "frontend/components/DecisionEvidence.tsx",
        "fields": ["Ringkasan keputusan", "Keputusan yang diperiksa", "Terbaca", "Unduh bukti (JSON)"],
        "api": ["fetchDecision", "fetchDecisionTraces"],
        "tables": [
            "decisions.status", "decisions.safe_delivered_cost", "decision_evidence.evidence_type",
            "decision_evidence.payload", "agent_traces.step_name",
        ],
        "evidence": (
            "select count(*)::text, coalesce(min(evidence_type),'-') from decision_evidence"
        ),
        "probe": "/decisions/{decision_id}",
        "state": S("decision_evidence", dim_col="decision_id",
                   dim_table="decisions", date_col="recorded_at",
                   text_col="evidence_type", sort_col="evidence_type",
                   null_col="is_consistent", page_size=10),
    },
    {
        "screen": "evidence",
        "section": "Jejak & riwayat persetujuan",
        "anchor": "frontend/components/DecisionEvidence.tsx",
        "fields": ["Jejak & riwayat", "Kelola persetujuan…", "Peran penyetuju"],
        "api": ["fetchDecisionChain", "fetchApprovalSummary"],
        "tables": [
            "approvals.approved", "approvals.comment", "approvals.approved_at",
            "decisions.iteration", "decisions.supersedes_id",
        ],
        "evidence": (
            "select count(*)::text, coalesce(min(decision_id::text),'-') from approvals"
        ),
        "probe": "/decisions/{decision_id}/chain",
        "state": S("approvals", dim_col="decision_id", dim_table="decisions",
                   date_col="approved_at", text_col="comment", sort_col="approved_at",
                   null_col="comment", page_size=10),
    },
    {
        "screen": "evidence",
        "section": "Integritas bukti & dossier",
        "anchor": "frontend/components/IntegrityPanel.tsx",
        "fields": ["Integritas Bukti", "Merkle Ledger", "Dossier Keputusan", "Tanda tangan", "Blok"],
        "api": ["fetchDossier", "verifyLedger"],
        "tables": [
            "ledger_blocks.payload_hash", "ledger_blocks.entity_id", "decision_evidence.payload",
        ],
        "evidence": (
            "select count(*)::text, coalesce(min(entity_id::text),'-') from ledger_blocks "
            "where entity_id is not null"
        ),
        "probe": "/decisions/{decision_id}/dossier",
        "state": S("ledger_blocks", dim_table=None, date_col="created_at",
                   text_col="payload", sort_col="height", null_col="entity_id", page_size=20),
    },
    {
        "screen": "evidence",
        "section": "Daftar purchase order (SAP simulasi)",
        "anchor": "frontend/components/PurchaseOrderList.tsx",
        "fields": ["Data berasal dari SAP simulasi", "SAP simulasi", "Unduh PDF",
                   "Belum ada purchase order tercatat."],
        "api": ["fetchPurchaseOrders", "fetchPurchaseOrderSummary", "fetchPurchaseOrderPdf"],
        "tables": [
            "sap_mock_purchase_orders.po_number", "sap_mock_purchase_orders.status",
            "sap_mock_purchase_orders.price", "sap_mock_purchase_orders.ordered_quantity",
            "sap_mock_purchase_orders.decision_id",
        ],
        "evidence": (
            "select count(*)::text, coalesce(min(po_number),'-') from sap_mock_purchase_orders"
        ),
        "probe": "/sap/purchase-orders",
        "state": S("sap_mock_purchase_orders", dim_table=None, date_col="created_at",
                   num_col="price", text_col="po_number", sort_col="po_number",
                   null_col="decision_id", page_size=10),
    },
    # ---------------- Keamanan Pangan ----------------
    {
        "screen": "safety",
        "section": "Papan batch & uji keamanan",
        "anchor": "frontend/components/FoodSafetyBoard.tsx",
        "fields": ["Periksa kiriman", "Batch diperiksa", "Kesegaran", "Layak sampai", "Berat batch gagal"],
        "api": ["fetchBatches", "evaluateSafety", "evaluateFreshness"],
        "tables": [
            "batches.safety_status", "batches.freshness_score", "batches.usable_until",
            "batches.temperature_log", "batches.certification_status",
        ],
        "evidence": (
            "select count(*)::text, coalesce(min(id::text),'-') from batches"
        ),
        "probe": "/batches?limit=500",
        "state": S("batches", dim_col="location_id", date_col="usable_until",
                   num_col="freshness_score", text_col="quarantine_reason",
                   sort_col="freshness_score", null_col="usable_until", page_size=10),
    },
    {
        "screen": "safety",
        "section": "Penerimaan barang",
        "anchor": "frontend/components/FoodSafetyBoard.tsx",
        "fields": ["Penerimaan barang", "Catat hasil terima & hitung ulang", "Kirim penolakan",
                   "Menunggu persetujuan"],
        "api": ["fetchReceipts", "fetchPendingReceipts", "recordReceipt", "approveReceipt", "rejectReceipt"],
        "tables": [
            "batch_receipts.status", "batch_receipts.checked", "batch_receipts.review_note",
            "batch_receipts.recorded_at",
        ],
        "evidence": (
            "select count(*)::text, coalesce(min(id::text),'-') from batch_receipts"
        ),
        "probe": "/receipts/menunggu",
        "state": S("batch_receipts", dim_col="batch_id", dim_table="batches",
                   date_col="recorded_at", text_col="review_note", sort_col="status",
                   null_col="review_note", page_size=10),
    },
    {
        "screen": "safety",
        "section": "Karantina batch",
        "anchor": "frontend/components/FoodSafetyBoard.tsx",
        "fields": ["Lepas dari karantina", "Nyatakan gagal", "Ditahan (karantina)",
                   "Alasan (tercatat di ledger)"],
        "api": ["ubahKarantina"],
        "tables": [
            "batches.quarantine_status", "batches.quarantine_reason", "batches.quarantined_at",
            "batches.quarantine_actor_id",
        ],
        "evidence": (
            "select count(*)::text, coalesce(min(id::text),'-') from batches "
            "where quarantine_status <> 'none'"
        ),
        "probe": "/batches?limit=500",
        "state": S("batches", dim_col="location_id", date_col="quarantined_at",
                   text_col="quarantine_reason", sort_col="quarantine_status",
                   null_col="quarantine_reason", page_size=10),
    },
    # ---------------- Surplus & Limbah ----------------
    {
        "screen": "surplus",
        "section": "Rencana alokasi surplus",
        "anchor": "frontend/components/SurplusBoard.tsx",
        "fields": ["Rencana alokasi surplus", "Total surplus", "Total kekurangan", "Tujuan", "Dari"],
        "api": ["fetchSurplusAllocations"],
        "tables": [
            "supply_records.quantity_kg", "demand_records.quantity_kg",
            "locations.name", "locations.latitude",
        ],
        "evidence": (
            "select count(*)::text, coalesce(min(id::text),'-') from supply_records "
            "where recorded_at=(select max(recorded_at) from supply_records)"
        ),
        "probe": "/surplus/allocations?commodity={commodity}",
        "state": S("supply_records", dim_col="location_id", date_col="recorded_at",
                   num_col="quantity_kg", text_col="source", sort_col="quantity_kg",
                   page_size=10),
    },
    {
        "screen": "surplus",
        "section": "Pencatatan limbah",
        "anchor": "frontend/components/SurplusBoard.tsx",
        "fields": ["Pencatatan limbah", "Neraca hari ini"],
        "api": ["fetchWasteSummary"],
        "tables": [
            "disposal_events.quantity_kg", "disposal_events.reason", "disposal_events.partner_name",
        ],
        "evidence": (
            "select count(*)::text, coalesce(min(id::text),'-') from disposal_events"
        ),
        "probe": "/waste/summary?days=30",
        "state": S("disposal_events", dim_col="location_id", date_col="disposed_at",
                   num_col="quantity_kg", text_col="reason", sort_col="quantity_kg",
                   null_col="partner_name", page_size=10),
    },
    # ---------------- Pemasok ----------------
    {
        "screen": "suppliers",
        "section": "Daftar pemasok + pencarian",
        "anchor": "frontend/components/SupplierBoard.tsx",
        "fields": ["Daftar pemasok", "Pemasok terdaftar", "Rata-rata keandalan",
                   "Dalam jangkauan", "Hapus pencarian"],
        "api": ["fetchSuppliers"],
        "tables": [
            "suppliers.name", "suppliers.reliability_score", "suppliers.certification_status",
            "suppliers.capacity_kg_per_week", "suppliers.latitude", "suppliers.address",
        ],
        "evidence": (
            "select count(*)::text, coalesce(min(name),'-') from suppliers"
        ),
        "probe": "/suppliers?limit=200",
        "state": S("suppliers", dim_col="location_id", date_col="created_at",
                   num_col="reliability_score", text_col="address", sort_col="reliability_score",
                   null_col="latitude", page_size=10),
    },
    {
        "screen": "suppliers",
        "section": "Jalur kiriman (jalan)",
        "anchor": "frontend/components/SupplierBoard.tsx",
        "fields": ["Jalur kirim", "Jalur kiriman (jalan)", "Sedang mengirim barang"],
        "api": ["fetchSupplierRoutes"],
        "tables": [
            "road_routes.distance_m", "road_routes.duration_s", "road_routes.geometry",
            "batches.dispatched_at",
        ],
        "evidence": (
            "select count(*)::text, coalesce(min(route_key),'-') from road_routes"
        ),
        "probe": "/supplier-routes?limit=200",
        "state": S("road_routes", dim_table=None, date_col="fetched_at",
                   num_col="distance_m", text_col="route_key", sort_col="distance_m",
                   page_size=20),
    },
    {
        "screen": "suppliers",
        "section": "Supplier governance (eksklusi/pemulihan)",
        "anchor": "frontend/components/SupplierExclusionPanel.tsx",
        "fields": ["Supplier governance", "Ajukan exclusion", "Ajukan pemulihan",
                   "Alasan exclusion", "ID bukti tersimpan (opsional bila memilih di atas)"],
        "api": ["fetchExclusions", "fetchSupplierContext", "proposeSupplierExclusion",
                "proposeSupplierRestoration"],
        "tables": [
            "supplier_exclusions.status", "supplier_exclusions.reason",
            "supplier_exclusions.evidence_refs", "supplier_exclusions.scope_location_id",
        ],
        "evidence": (
            "select count(*)::text, coalesce(min(id::text),'-') from supplier_exclusions"
        ),
        "probe": "/supplier-exclusions",
        "state": S("supplier_exclusions", dim_col="scope_location_id", date_col="created_at",
                   text_col="reason", sort_col="status", null_col="revoked_at", page_size=10),
    },
    # ---------------- KPI & Kualitas Agen ----------------
    {
        "screen": "kpi-kualitas",
        "section": "KPI (jendela periode)",
        "anchor": "frontend/components/KPIDashboard.tsx",
        "fields": ["Jendela periode KPI", "Avoidable Food Loss", "Procurement Price Deviation"],
        "api": ["fetchKpis"],
        "tables": [
            "delivery_events.delivered_portions", "menu_plans.planned_portions",
            "disposal_events.quantity_kg", "decisions.safe_delivered_cost",
        ],
        "evidence": (
            "select count(*)::text, coalesce(min(id::text),'-') from delivery_events"
        ),
        "probe": "/kpi?start={start_iso}&end={end_iso}",
        "state": S("delivery_events", dim_col="menu_plan_id", dim_table="menu_plans",
                   date_col="delivered_at", num_col="delivered_portions",
                   sort_col="delivered_portions", page_size=10),
    },
    {
        "screen": "kpi-kualitas",
        "section": "Kualitas agen (sampel run)",
        "anchor": "frontend/components/AgentQualityBoard.tsx",
        "fields": ["Kualitas Agen", "Run dinilai", "Rata-rata durasi", "Tingkat fallback",
                   "Kesesuaian verifier"],
        "api": ["fetchDecisionTraces", "fetchApprovalSummary"],
        "tables": [
            "agent_traces.step_name", "agent_traces.duration_ms", "agent_traces.output_summary",
            "approvals.approved",
        ],
        "evidence": (
            "select count(*)::text, coalesce(min(id::text),'-') from agent_traces"
        ),
        "probe": "/decisions/{decision_id}/traces",
        "state": S("agent_traces", dim_col="decision_id", dim_table="decisions",
                   date_col="step_at", num_col="duration_ms", text_col="tool_called",
                   sort_col="duration_ms", null_col="confidence", page_size=10),
    },
    # ---------------- Agent Log ----------------
    {
        "screen": "agent-log",
        "section": "Status provider model",
        "anchor": "frontend/components/ProviderPanel.tsx",
        "fields": ["Status provider model", "Verifier", "Forecast", "Supervisor"],
        "api": ["fetchDecisionTraces"],
        "tables": ["agent_traces.step_name", "agent_traces.output_summary", "agent_traces.agent_name"],
        "evidence": (
            "select count(*)::text, coalesce(min(step_name),'-') from agent_traces "
            "where step_name in ('VERIFY','PREDICT','SUPERVISE')"
        ),
        "probe": "/decisions/{decision_id}/traces",
        "state": S("agent_traces", dim_col="decision_id", dim_table="decisions",
                   date_col="step_at", num_col="duration_ms", text_col="tool_called",
                   sort_col="duration_ms", null_col="confidence", page_size=10),
    },
    {
        "screen": "agent-log",
        "section": "Jejak langkah agen (trace viewer)",
        "anchor": "frontend/components/AgentTraceViewer.tsx",
        "fields": ["SUPERVISE"],
        "api": ["fetchDecisionTraces"],
        "tables": [
            "agent_traces.tool_called", "agent_traces.duration_ms", "agent_traces.input_summary",
            "agent_traces.citations", "agent_traces.run_id",
        ],
        "evidence": (
            "select count(*)::text, coalesce(min(step_name),'-') from agent_traces"
        ),
        "probe": "/decisions/{decision_id}/traces",
        "state": S("agent_traces", dim_col="decision_id", dim_table="decisions",
                   date_col="step_at", num_col="duration_ms", text_col="tool_called",
                   sort_col="duration_ms", null_col="confidence", page_size=10),
    },
    # ---------------- Demo Control ----------------
    {
        "screen": "demo-control",
        "section": "Status data demo & sesi",
        "anchor": "frontend/components/DemoControlPanel.tsx",
        "fields": ["Demo Control", "Siapkan data demo", "Akhiri sesi", "Perpanjang 30 menit"],
        "api": ["fetchDemoDataStatus", "fetchDemoSession", "fetchDemoPreview",
                "startDemoSession", "extendDemoSession", "endDemoSession", "refreshDemoToToday"],
        "tables": [
            "demo_sessions.status", "demo_sessions.expires_at", "demo_sessions.anchor_now",
            "batches.demo_session_id", "decisions.demo_session_id",
        ],
        "evidence": (
            "select count(*)::text, coalesce(min(status),'-') from demo_sessions"
        ),
        "probe": "/demo/data-status",
        "state": S("demo_sessions", dim_table=None, date_col="expires_at",
                   text_col="status", sort_col="started_at", null_col="ended_at", page_size=10),
    },
    {
        "screen": "demo-control",
        "section": "Jalankan agent + bukti pipeline",
        "anchor": "frontend/components/DemoControlPanel.tsx",
        "fields": ["Jalankan agent", "Langkah pipeline yang tercatat", "Tujuh agen review", "Bukti agent"],
        "api": ["fetchDemoAgentCommodities", "fetchDemoAgentLastRun", "runDemoAgent"],
        "tables": [
            "agent_traces.agent_name", "agent_traces.step_name", "decisions.demo_case",
            "decisions.origin",
        ],
        "evidence": (
            "select count(*)::text, coalesce(min(agent_name),'-') from agent_traces "
            "where agent_name is not null"
        ),
        "probe": "/demo/agent/last-run",
        "state": S("agent_traces", dim_col="decision_id", dim_table="decisions",
                   date_col="step_at", num_col="duration_ms", text_col="agent_name",
                   sort_col="duration_ms", null_col="confidence", page_size=10),
    },
    # ---------------- Pengaturan ----------------
    {
        "screen": "settings",
        "section": "Pengguna (admin)",
        "anchor": "frontend/components/SettingsPanel.tsx",
        "fields": ["Memuat pengguna & lokasi…", "Peran", "Nama", "Simpan"],
        "api": ["fetchAdminUsers", "updateAdminUser"],
        "tables": ["users.role", "users.email", "users.location_id", "users.name"],
        "evidence": (
            "select count(*)::text, coalesce(min(email),'-') from users"
        ),
        "probe": "/admin/users",
        "primary_role": "bgn_monitor",
        "state": S("users", dim_table=None, date_col="created_at", text_col="name",
                   sort_col="role", null_col="location_id", page_size=10),
    },
    {
        "screen": "settings",
        "section": "Lokasi (admin)",
        "anchor": "frontend/components/SettingsPanel.tsx",
        "fields": ["Wilayah", "Koordinat", "Lokasi"],
        "api": ["fetchAdminLocations", "updateAdminLocation"],
        "tables": ["locations.name", "locations.region", "locations.role_hint",
                   "locations.latitude", "locations.longitude"],
        "evidence": (
            "select count(*)::text, coalesce(min(name),'-') from locations"
        ),
        "probe": "/admin/locations",
        "primary_role": "bgn_monitor",
        "state": S("locations", dim_table=None, date_col="created_at", num_col=None,
                   text_col="region", sort_col="name", null_col="latitude", page_size=10),
    },
    # ---------------- Global (di luar tab) ----------------
    {
        "screen": "global",
        "section": "Login & identitas sesi",
        "anchor": "frontend/app/page.tsx",
        "fields": ["Masuk ke konsol", "Email", "Password"],
        "api": ["login", "fetchMe"],
        "tables": ["users.email", "users.password_hash", "users.role", "users.location_id"],
        "evidence": (
            "select count(*)::text, coalesce(min(email),'-') from users"
        ),
        "probe": "/auth/me",
        "state": S("users", dim_table=None, date_col="created_at", text_col="name",
                   sort_col="role", null_col="location_id", page_size=10),
    },
    {
        "screen": "global",
        "section": "Top bar: notifikasi & cakupan lokasi",
        "anchor": "frontend/components/TopBar.tsx",
        "fields": ["Rekomendasi baru", "Tidak ada keputusan menunggu tindakan",
                   "Pilih lokasi yang disorot di peta", "Buka informasi notifikasi"],
        "api": ["fetchMe", "fetchDecisions"],
        "tables": ["decisions.status", "decisions.expires_at", "users.location_id",
                   "locations.name"],
        "evidence": (
            "select count(*)::text, coalesce(min(id::text),'-') from decisions "
            "where status='pending_approval' and expires_at > now()"
        ),
        "probe": "/decisions",
        "state": S("decisions", dim_col="target_location_id", date_col="expires_at",
                   num_col="safe_delivered_cost", text_col="rejection_reason",
                   sort_col="expires_at", null_col="rejection_reason", page_size=10),
    },
    {
        "screen": "global",
        "section": "Status integrasi (panel tidak terpasang)",
        "anchor": "frontend/components/IntegrationStatusPanel.tsx",
        "fields": ["Bukti integrasi per komponen", "Memuat status integrasi…"],
        "api": ["fetchIntegrationStatus"],
        "tables": [],
        "evidence": None,  # tidak ada tabel: status dibaca dari env/artefak
        "probe": "/integrations/status",
        "state": None,
    },
]

# ---------------------------------------------------------------------------
# 7. Definisi enum (kode vs CHECK vs data)
# ---------------------------------------------------------------------------

ENUMS: list[dict] = [
    {
        "name": "role user",
        "table": "users",
        "column": "role",
        "check": "check_user_role",
        "code": [
            ("tuple", "backend/app/api/auth.py", "MUTATING_ROLES"),
            ("ts_keys", "frontend/app/page.tsx", "ROLE_LABEL"),
        ],
        "badge": ("frontend/components/NavIcon.tsx", None),
    },
    {
        "name": "decision_type",
        "table": "decisions",
        "column": "decision_type",
        "check": "decisions_decision_type_check",
        "code": [
            ("literal_assign", "backend/app/api/decisions.py", "decision_type"),
            ("ts_keys", "frontend/components/RecommendationCard.tsx", "DECISION_TYPE_LABELS"),
        ],
        "badge": None,
    },
    {
        "name": "status keputusan",
        "table": "decisions",
        "column": "status",
        "check": "decisions_status_check",
        # Tidak ada Literal/enum di backend: status ditulis sebagai string di
        # beberapa service. StatusBadge COLORS bukan kontrak nilai (ia peta
        # warna lintas-enum), jadi tidak dipakai sebagai "kosakata kode".
        "code": [],
        "badge": ("frontend/components/StatusBadge.tsx", "COLORS"),
        "warn_colors": True,
        "note": "kode tidak punya enum; nilai ditulis tersebar sebagai string",
    },
    {
        "name": "safety_status batch",
        "table": "batches",
        "column": "safety_status",
        "check": "batches_safety_status_check",
        "code": [
            ("tuple", "backend/app/core/quarantine.py", "SAFETY_VALID"),
            ("json_values", "backend/app/core/safety.py", "safety_status"),
        ],
        "badge": ("frontend/components/StatusBadge.tsx", "COLORS"),
        "note": "FoodSafetyBoard merender status ini sebagai teks, bukan StatusBadge",
    },
    {
        "name": "kesegaran (turunan freshness_score)",
        "table": "batches",
        "column": "freshness_score",
        "check": "batches_freshness_range_check",
        "code": [
            ("thresholds", "backend/app/core/freshness.py", "classify_freshness"),
        ],
        "badge": None,
        "derived": True,
        "note": "status turunan: pass / needs_verification / fail dari freshness_score",
    },
    {
        "name": "status penerimaan (receipt)",
        "table": "batch_receipts",
        "column": "status",
        "check": "batch_receipts_status_check",
        "code": [
            ("server_default", "backend/app/models/batch_receipts.py", "status"),
        ],
        "badge": None,
        "note": "default \"menunggu\" di api/receipts.py; status lain ditulis endpoint approve/reject",
    },
    {
        "name": "status eksklusi pemasok",
        "table": "supplier_exclusions",
        "column": "status",
        "check": "supplier_exclusions_status_check",
        "code": [
            ("literal_assign", "backend/app/api/supplier_exclusions.py", "status"),
            ("ts_union", "frontend/lib/supplier-exclusions.ts", "SupplierExclusion"),
        ],
        "badge": None,
    },
    {
        "name": "origin data",
        "table": "batches",
        "column": "origin",
        "check": "check_batches_origin_vocab",
        "code": [
            ("string_literals", "backend/app/seed/timeseries.py", "origin"),
        ],
        "badge": None,
    },
    {
        "name": "status PO (SAP mock)",
        "table": "sap_mock_purchase_orders",
        "column": "status",
        "check": "sap_mock_po_status_check",
        "code": [
            ("literal_assign", "backend/app/api/sap_orders.py", "status"),
        ],
        "badge": None,
    },
    {
        "name": "status pengiriman (delivery)",
        "table": "delivery_events",
        "column": "status",
        "check": None,
        "code": [
            ("server_default", "backend/app/models/kpi_facts.py", "status"),
        ],
        "badge": None,
        "note": "status hanya punya server_default; tidak ada CHECK maupun enum di kode",
    },
    {
        "name": "status karantina batch",
        "table": "batches",
        "column": "quarantine_status",
        "check": "batches_quarantine_status_check",
        "code": [
            ("tuple", "backend/app/core/quarantine.py", "STATUS_VALID"),
        ],
        "badge": ("frontend/components/StatusBadge.tsx", "COLORS"),
        "note": "input API memakai aksi tahan/lepas/gagal (Literal) yang dipetakan ke status ini",
    },
]


def check_vocab(definition: str) -> list[str]:
    return re.findall(r"'([^']+)'::(?:text|character varying)", definition)


def code_values(kind: str, rel: str, key: str) -> list[str]:
    src = rel_source(rel)
    if not src:
        return []
    if kind == "tuple":
        match = re.search(re.escape(key) + r"\s*=\s*\(([^)]*)\)", src)
        return re.findall(r'"([^"]+)"', match.group(1)) if match else []
    if kind == "ts_keys":
        match = re.search(re.escape(key) + r"[^=]*=\s*\{", src)
        if not match:
            return []
        i, depth = match.end() - 1, 0
        while i < len(src):
            if src[i] == "{":
                depth += 1
            elif src[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        body = src[match.end():i]
        return re.findall(r"^\s*([A-Za-z_][\w]*)\s*:", body, flags=re.M)
    if kind == "literal_assign":
        match = re.search(re.escape(key) + r"\s*:\s*Literal\[([^\]]*)\]", src)
        return re.findall(r'"([^"]+)"', match.group(1)) if match else []
    if kind == "json_values":
        return sorted(set(re.findall(r'"' + re.escape(key) + r'"\s*:\s*"([^"]+)"', src)))
    if kind == "string_literals":
        return sorted(set(re.findall(r"origin\s*=\s*['\"]([a-z]+)['\"]", src)))
    if kind == "server_default":
        # Cari definisi kolom ini saja, lalu potong di kolom berikutnya: kalau
        # tidak, `server_default` milik kolom lain (mis. origin='seed') terbaca
        # sebagai default kolom status.
        start = re.search(r"^\s*" + re.escape(key) + r":\s*Mapped\[", src, flags=re.M)
        if not start:
            return []
        tail = src[start.start():]
        nxt = re.search(r"\n\s{4}\w+:\s*Mapped\[", tail[1:])
        statement = tail[: nxt.start() + 1] if nxt else tail[:600]
        match = re.search(r"server_default=[\"']([^\"']+)[\"']", statement)
        return [match.group(1)] if match else []
    if kind == "ts_union":
        match = re.search(re.escape(key) + r"\s*=\s*\{([^}]*)\}", src)
        if not match:
            return []
        block = match.group(1)
        field = re.search(r"status\s*:\s*([^;]+);", block)
        return re.findall(r'"([^"]+)"', field.group(1)) if field else []
    if kind == "thresholds":
        # Status kesegaran tidak disimpan di kolom; nilainya turunan dari skor.
        # Yang bisa dibandingkan adalah LABEL keluaran classify_freshness.
        body = src.split("def classify_freshness")[-1].split("\ndef ")[0]
        return sorted(set(re.findall(r'return "([a-z_]+)"', body)))
    return []


def badge_colors(rel: str | None, key: str | None) -> set[str]:
    if not rel or not key:
        return set()
    src = rel_source(rel)
    match = re.search(re.escape(key) + r"[^=]*=\s*\{", src)
    if not match:
        return set()
    i, depth = match.end() - 1, 0
    while i < len(src):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    return set(re.findall(r"^\s*([A-Z_][A-Z0-9_]*)\s*:", src[match.end():i], flags=re.M))


# ---------------------------------------------------------------------------
# 8. Probe state tampilan
# ---------------------------------------------------------------------------

STATE_KEYS = [
    ("kosong", "Tidak ada baris sama sekali untuk satu kunci dimensi"),
    ("satu_item", "Tepat satu baris untuk satu kunci dimensi"),
    ("banyak_halaman", "Baris > ukuran halaman (pager benar-benar terpakai)"),
    ("filter_tanpa_hasil", "Filter pada dimensi yang tidak punya baris"),
    ("sort", "Kolom urut punya lebih dari satu nilai"),
    ("error", "Endpoint membalas 4xx untuk masukan tak sah"),
    ("loading", "Cabang memuat ada di komponen"),
    ("null_opsional", "Kolom opsional berisi NULL"),
    ("teks_panjang", "Ada nilai teks >= 80 karakter"),
    ("angka_nol", "Ada nilai numerik 0"),
    ("angka_negatif", "Ada nilai numerik negatif"),
    ("angka_besar", "Ada nilai numerik >= 1.000.000"),
    ("tanggal_lampau", "Ada tanggal sebelum sekarang"),
    ("tanggal_hari_ini", "Ada tanggal hari ini (WIB)"),
    ("tanggal_masa_depan", "Ada tanggal setelah sekarang"),
    ("unicode", "Ada teks non-ASCII (bahasa Indonesia/Unicode)"),
    ("format_lokal", "Formatter rupiah & tanggal lokal tersedia + ada nilai uang"),
]


def numeric_guards(checks: dict[str, dict[str, str]]) -> dict[tuple[str, str], str]:
    """Kolom numerik yang dijaga CHECK `>= 0` / `> 0` — state negatif/nol mustahil."""
    out: dict[tuple[str, str], str] = {}
    for table, defs in checks.items():
        for definition in defs.values():
            for column, op in re.findall(r"\(?([a-z_]+)\)?\s*(>=|>)\s*\(?0\)?(?:::numeric)?", definition):
                kind = "ge" if op == ">=" else "gt"
                if out.get((table, column)) != "gt":
                    out[(table, column)] = kind
    return out


def state_sql(scope: dict) -> str:
    t = scope["table"]
    where = scope.get("where") or "true"
    parts: list[str] = [f"(select count(*) from {t} where {where})"]
    if scope.get("dim_table") and scope.get("dim_col"):
        dt, dc = scope["dim_table"], scope["dim_col"]
        parts += [
            "(select count(*) from (select d.id from %s d where not exists "
            "(select 1 from %s x where x.%s=d.id and (%s))) z)" % (dt, t, dc, where),
            "(select count(*) from (select d.id from %s d where (select count(*) from %s x "
            "where x.%s=d.id and (%s))=1) z)" % (dt, t, dc, where),
        ]
    else:
        parts += ["NULL", "NULL"]
    parts.append(
        f"(select count(distinct ({scope['sort_col']})::text) from {t} where {where})"
        if scope.get("sort_col") else "NULL"
    )
    parts.append(
        f"(select count(*) from {t} where {where} and {scope['null_col']} is null)"
        if scope.get("null_col") else "NULL"
    )
    parts.append(
        f"(select coalesce(max(length(({scope['text_col']})::text)),0) from {t} where {where})"
        if scope.get("text_col") else "NULL"
    )
    parts.append(
        f"(select count(*) from {t} where {where} and ({scope['text_col']})::text ~ '[^ -~]')"
        if scope.get("text_col") else "NULL"
    )
    parts.append(
        f"(select count(*) from {t} where {where} and {scope['num_col']}=0)"
        if scope.get("num_col") else "NULL"
    )
    parts.append(
        f"(select count(*) from {t} where {where} and {scope['num_col']}<0)"
        if scope.get("num_col") else "NULL"
    )
    parts.append(
        f"(select coalesce(max(abs({scope['num_col']})),0) from {t} where {where})"
        if scope.get("num_col") else "NULL"
    )
    dc = scope.get("date_col")
    if dc:
        jakarta_date = "(now() at time zone 'Asia/Jakarta')::date"
        parts += [
            f"(select count(*) from {t} where {where} and ({dc}) < now())",
            f"(select count(*) from {t} where {where} and (({dc}) at time zone 'Asia/Jakarta')::date = {jakarta_date})",
            f"(select count(*) from {t} where {where} and ({dc}) > now())",
        ]
    else:
        parts += ["NULL", "NULL", "NULL"]
    return "select " + ", ".join(parts)


def state_values(scope: dict) -> dict[str, str]:
    row = psql(state_sql(scope))[0]
    keys = ["rows", "dim_kosong", "dim_satu", "sort_distinct", "nulls", "max_len",
            "unicode", "nol", "negatif", "max_num", "lampau", "hari_ini", "masa_depan"]
    vals = dict(zip(keys, row))
    return {k: ("" if v in ("", "NULL") else v) for k, v in vals.items()}


def loading_branch(source: str) -> bool:
    return bool(re.search(r"Memuat|LoadingState|isLoading|loading", source))


def error_probe(template: str, method: str, token: str, body: dict | None,
                params: dict[str, str]) -> tuple[int, str]:
    """Picu galat secara sengaja pada endpoint baris ini.

    Tiga cara, berurutan: id nyata diganti UUID nol (404), parameter query
    wajib dihapus (422), atau parameter angka diberi nilai tak sah (422).
    Kalau tidak ada yang memicu 4xx, state galat memang tidak bisa dibuktikan
    dari luar — itu dilaporkan apa adanya, bukan dikarang.
    """
    zero = "00000000-0000-0000-0000-000000000000"
    if re.search(r"\{(decision_id|batch_id|receipt_id|exclusion_id|po_number|supplier_id|location)\}", template):
        bad = fill(re.sub(r"\{(decision_id|batch_id|receipt_id|exclusion_id|po_number|supplier_id|location)\}", zero, template), params)
        status, _ = http_json(method, bad, token, body)
        if status >= 400:
            return status, bad
    filled_path = fill(template, params)
    if "?" in filled_path:
        tanpa_query = filled_path.split("?")[0]
        status, _ = http_json(method, tanpa_query, token, body)
        if status >= 400:
            return status, tanpa_query + " (tanpa parameter query)"
    suffix = "&limit=abc" if "?" in filled_path else "?limit=abc"
    bad = filled_path + suffix
    status, _ = http_json(method, bad, token, body)
    return status, bad


# ---------------------------------------------------------------------------
# 9. Evaluasi baris
# ---------------------------------------------------------------------------


def route_matches(template: str, route: str) -> bool:
    a = template.strip("/").split("/")
    b = route.strip("/").split("/")
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if x.startswith("{") and y.startswith("{"):
            continue
        if x != y:
            return False
    return True


def evaluate(rows_ctx: dict) -> list[dict]:
    api_index = rows_ctx["api_index"]
    schema = rows_ctx["schema"]
    db_cols = rows_ctx["db_cols"]
    routes = rows_ctx["routes"]
    components = rows_ctx["components"]
    tokens = rows_ctx["tokens"]
    params = rows_ctx["params"]
    cache = rows_ctx["http_cache"]
    guards = rows_ctx["guards"]

    def call(method: str, path: str, role: str, body: dict | None = None):
        # Kunci cache memakai PERAN, bukan potongan token: dua token JWT demo
        # berbagi prefiks "eyJhbGciOiJ", jadi kunci berbasis token membuat
        # respons sppg_head dipakai ulang untuk bgn_monitor (403 palsu).
        key = (method, path, role, json.dumps(body, sort_keys=True) if body else "")
        if key not in cache:
            cache[key] = http_json(method, path, tokens[role], body)
        return cache[key]

    out = []
    for row in SECTIONS:
        problems: list[str] = []
        # Panel yang SENGAJA tidak dipasang: tes PRD mengunci `page.tsx` supaya
        # tidak memuat komponen ini, jadi "tidak dirender" di sini adalah
        # keputusan produk yang punya bukti, bukan cacat data. Tanpa daftar ini
        # matriks melaporkan GAP dan pembaca akan mengejar komponen yang memang
        # sudah dipensiunkan.
        retired_evidence = RETIRED.get(row["section"])
        anchor_src = rel_source(row["anchor"])
        if not anchor_src:
            problems.append(f"komponen {row['anchor']} tidak ada")
        # Apakah panel ini benar-benar dirender? Komponen yang tidak pernah muncul
        # sebagai tag JSX di berkas lain = tidak terpasang (lihat orphan_components).
        # Anchor `app/page.tsx` selalu terpasang.
        anchor_stem = Path(row["anchor"]).stem
        installed = anchor_stem == "page" or anchor_stem not in rows_ctx["orphans"]
        if not installed and not retired_evidence:
            problems.append("komponen ada di repo tetapi tidak dirender oleh layar mana pun")
        missing_fields = [f for f in row["fields"] if f not in anchor_src]
        if missing_fields:
            problems.append("label tidak ditemukan: " + ", ".join(missing_fields))

        endpoints, api_problems = [], []
        for fn in row["api"]:
            info = api_index.get(fn)
            if not info:
                api_problems.append(f"{fn} tidak ada di index request frontend")
                continue
            if info["path"] == "(tidak terbaca)":
                api_problems.append(f"path {fn} tidak terbaca dari sumbernya")
                continue
            hit = next(
                (r for r in routes
                 if r["method"] == info["method"] and route_matches(info["path"], r["path"])),
                None,
            )
            if hit is None:
                api_problems.append(f"{fn} -> {info['method']} {info['path']} tidak cocok route live")
            endpoints.append(f"{info['method']} {hit['path'] if hit else info['path']}")
        problems.extend(api_problems)

        # Kolom diperiksa ke DB yang benar-benar ada (information_schema), bukan
        # ke model: `ledger_blocks` sengaja tanpa model SQLAlchemy.
        bad_tables = []
        for spec in row["tables"]:
            table, _, column = spec.partition(".")
            if column not in db_cols.get(table, {}):
                bad_tables.append(spec)
        if bad_tables:
            problems.append("kolom tidak ada di DB live: " + ", ".join(bad_tables))

        evidence_n, evidence_sample = 0, "-"
        if row["evidence"]:
            result = psql(row["evidence"])
            evidence_n = int(result[0][0]) if result and result[0] else 0
            evidence_sample = result[0][1] if result and len(result[0]) > 1 else "-"

        # probe live per peran
        probe_path = fill(row["probe"], params)
        probe_method = row.get("probe_method", "GET")
        probe_body = row.get("probe_body")
        probes = []
        payload_keys: set[str] = set()
        for role in ("sppg_head", "bgn_monitor"):
            status, payload = call(probe_method, probe_path, role, probe_body)
            probes.append({"role": role, "status": status, "path": probe_path,
                           "count": payload_count(payload)})
            payload_keys |= flatten_keys(payload)
        # Peran utama per baris: layar Pengaturan hanya dirender untuk bgn_monitor,
        # panel OpsConsole/Demo hanya untuk peran SPPG. 403 pada peran lain adalah
        # desain (cakupan lokasi/peran), bukan kegagalan data — dicatat terpisah.
        primary = row.get("primary_role", "sppg_head")
        primary_probe = next(p for p in probes if p["role"] == primary)
        ok_probe = 200 <= primary_probe["status"] < 300
        if not ok_probe:
            problems.append(
                f"probe endpoint gagal untuk peran utama {primary}: HTTP {primary_probe['status']}")
        restricted = [p for p in probes if p["role"] != primary and p["status"] in (401, 403)]

        # state
        states: dict[str, tuple[str, str]] = {}
        src_loading = loading_branch(anchor_src)
        if row["state"]:
            sv = state_values(row["state"])
            page_size = row["state"].get("page_size", 10)
            rows_n = int(sv.get("rows") or 0)
            states["kosong"] = (
                ("TERBUKTI", f"{sv.get('dim_kosong')} kunci dimensi tanpa baris")
                if sv.get("dim_kosong") not in ("", "0", None)
                else ("GAP", "belum ada kunci dimensi yang kosong")
            )
            states["satu_item"] = (
                ("TERBUKTI", f"{sv.get('dim_satu')} kunci dimensi berisi tepat 1 baris")
                if sv.get("dim_satu") not in ("", "0", None)
                else ("GAP", "belum ada kunci dimensi berisi tepat 1 baris")
            )
            states["banyak_halaman"] = (
                ("TERBUKTI", f"{rows_n} baris > {page_size}/halaman")
                if rows_n > page_size
                else ("GAP", f"{rows_n} baris <= {page_size}/halaman")
            )
            states["filter_tanpa_hasil"] = states["kosong"]
            states["sort"] = (
                ("TERBUKTI", f"{sv.get('sort_distinct')} nilai berbeda")
                if sv.get("sort_distinct") not in ("", "1", "0", None)
                else ("GAP", "kolom urut hanya 1 nilai / tidak ada")
            )
            status_err, err_path = error_probe(row["probe"], probe_method,
                                               "sppg_head", probe_body, params)
            states["error"] = (
                ("TERBUKTI", f"HTTP {status_err} pada {err_path}")
                if status_err >= 400
                else ("GAP", f"tidak ada masukan tak sah yang memicu galat (HTTP {status_err})")
            )
            states["null_opsional"] = (
                ("TERBUKTI", f"{sv.get('nulls')} baris NULL")
                if sv.get("nulls") not in ("", "0", None)
                else ("GAP", "kolom opsional terisi semua / tidak ada kolom opsional")
            )
            states["teks_panjang"] = (
                ("TERBUKTI", f"panjang maks {sv.get('max_len')} karakter")
                if int(sv.get("max_len") or 0) >= 80
                else ("GAP", f"panjang maks {sv.get('max_len') or 0} karakter")
            )
            states["angka_nol"] = (
                ("TERBUKTI", f"{sv.get('nol')} baris bernilai 0")
                if sv.get("nol") not in ("", "0", None)
                else ("N/A" if guards.get((row["state"]["table"], row["state"].get("num_col") or "")) == "gt"
                      else "GAP", "skema mewajibkan > 0 (CHECK)" if guards.get((row["state"]["table"], row["state"].get("num_col") or "")) == "gt"
                      else "tidak ada nilai 0")
            )
            states["angka_negatif"] = (
                ("TERBUKTI", f"{sv.get('negatif')} baris negatif")
                if sv.get("negatif") not in ("", "0", None)
                else ("N/A" if (row["state"]["table"], row["state"].get("num_col") or "") in guards
                      else "GAP", "skema melarang nilai negatif (CHECK >= 0)" if (row["state"]["table"], row["state"].get("num_col") or "") in guards
                      else "tidak ada nilai negatif")
            )
            states["angka_besar"] = (
                ("TERBUKTI", f"maks {sv.get('max_num')}")
                if float(sv.get("max_num") or 0) >= 1_000_000
                else ("GAP", f"maks {sv.get('max_num') or 0}")
            )
            states["tanggal_lampau"] = (
                ("TERBUKTI", f"{sv.get('lampau')} baris")
                if sv.get("lampau") not in ("", "0", None)
                else ("GAP", "tidak ada tanggal lampau")
            )
            states["tanggal_hari_ini"] = (
                ("TERBUKTI", f"{sv.get('hari_ini')} baris")
                if sv.get("hari_ini") not in ("", "0", None)
                else ("GAP", "tidak ada baris bertanggal hari ini (WIB)")
            )
            states["tanggal_masa_depan"] = (
                ("TERBUKTI", f"{sv.get('masa_depan')} baris")
                if sv.get("masa_depan") not in ("", "0", None)
                else ("GAP", "tidak ada tanggal masa depan")
            )
            states["unicode"] = (
                ("TERBUKTI", f"{sv.get('unicode')} baris non-ASCII")
                if sv.get("unicode") not in ("", "0", None)
                else ("GAP", "teks hanya ASCII")
            )
        else:
            for key, _ in STATE_KEYS:
                if key not in ("error", "loading"):
                    states[key] = ("N/A", "baris tanpa tabel data")
            status_err, err_path = error_probe(row["probe"], probe_method,
                                               "sppg_head", probe_body, params)
            states["error"] = (
                ("TERBUKTI", f"HTTP {status_err} pada {err_path}") if status_err >= 400
                else ("GAP", f"HTTP {status_err}")
            )
        states["loading"] = (
            ("TERBUKTI", "cabang 'Memuat'/LoadingState ditemukan di komponen")
            if src_loading else ("GAP", "komponen tanpa cabang memuat")
        )
        has_money = any(
            "price" in spec or "cost" in spec or "quantity" in spec or "kg" in spec
            for spec in row["tables"]
        )
        states["format_lokal"] = (
            ("TERBUKTI", "formatIDR (lib/auth) + formatDateTime (lib/datetime) dipakai; ada kolom uang")
            if has_money and "formatIDR" in rel_source("frontend/lib/auth.ts")
            and "formatDateTime" in rel_source("frontend/lib/datetime.ts")
            and evidence_n > 0
            else ("GAP", "tidak ada kolom uang pada baris ini / formatter tidak ditemukan")
        )

        if row["evidence"] is None:
            data_ok = any(p["count"] > 0 for p in probes)
        else:
            data_ok = evidence_n > 0
        if retired_evidence and not installed:
            status = "DIPENSIUNKAN"
        else:
            status = "TERBUKTI" if (data_ok and ok_probe and not problems) else "GAP"
        if row["evidence"] and not data_ok:
            problems.append("query bukti mengembalikan 0 baris")
        elif row["evidence"] is None and not data_ok:
            problems.append("respons endpoint kosong")
        out.append({
            **row,
            "retired_evidence": retired_evidence,
            "endpoints": sorted(set(endpoints)),
            "probe_results": probes,
            "evidence_n": evidence_n,
            "evidence_sample": evidence_sample,
            "states": states,
            "installed": installed,
            "problems": problems,
            "restricted": restricted,
            "status": status,
            "payload_keys": payload_keys,
        })
    return out


# ---------------------------------------------------------------------------
# 10. Enum evaluation
# ---------------------------------------------------------------------------


def evaluate_enums(ctx: dict) -> list[dict]:
    checks = ctx["checks"]
    out = []
    for spec in ENUMS:
        definition = checks.get(spec["table"], {}).get(spec["check"] or "", "")
        allowed = check_vocab(definition) if spec["check"] else []
        code = {}
        for kind, rel, key in spec["code"]:
            vals = code_values(kind, rel, key)
            if vals:
                code[f"{Path(rel).name}:{key}"] = sorted(set(vals))
        if spec.get("derived"):
            # Nilai turunan: hitung bucket memakai ambang yang SAMA dengan kode.
            fresh_src = rel_source("backend/app/core/freshness.py")
            pass_match = re.search(r"PASS_THRESHOLD\s*=\s*([0-9.]+)", fresh_src)
            verify_match = re.search(r"VERIFY_THRESHOLD\s*=\s*([0-9.]+)", fresh_src)
            pass_t = float(pass_match.group(1)) if pass_match else 0.85
            verify_t = float(verify_match.group(1)) if verify_match else 0.60
            distinct_rows = psql(
                "select case when freshness_score >= {p} then 'pass' "
                "when freshness_score >= {v} then 'needs_verification' else 'fail' end, count(*) "
                "from batches where freshness_score is not null group by 1 order by 1".format(
                    p=pass_t, v=verify_t)
            )
            distinct = {v: int(n) for v, n in distinct_rows}
            nulls = int(scalar("select count(*) from batches where freshness_score is null"))
            if nulls:
                distinct["(NULL)"] = nulls
            allowed = list(code.get("freshness.py:classify_freshness", [])) or allowed
        else:
            distinct_rows = psql(
                f"select coalesce({spec['column']}::text,'(NULL)'), count(*) from {spec['table']} "
                f"group by 1 order by 1"
            )
            distinct = {v: int(n) for v, n in distinct_rows}
        colors = badge_colors(*spec["badge"]) if spec["badge"] else set()

        flags: list[tuple[str, str]] = []
        if not spec["check"] and not spec.get("derived"):
            flags.append(("tanpa_check", "tidak ada CHECK constraint di DB"))
        flat_code = {v for vals in code.values() for v in vals}
        if allowed and flat_code and not spec.get("derived"):
            outside = sorted(flat_code - set(allowed))
            if outside:
                asal = ", ".join(
                    f"{src} ({', '.join(v for v in outside if v in vals)})"
                    for src, vals in code.items() if any(v in vals for v in outside)
                )
                flags.append(("kode_di_luar_skema",
                              "kode memakai nilai di luar CHECK: " + ", ".join(outside)
                              + f" — sumber: {asal}"))
            narrower = sorted(set(allowed) - flat_code)
            if narrower:
                flags.append(("skema_lebih_luas",
                              "CHECK mengizinkan nilai yang tidak ada di kode: " + ", ".join(narrower)))
        if allowed:
            extra = sorted(set(distinct) - set(allowed) - {"(NULL)"})
            if extra:
                flags.append(("data_di_luar_skema",
                              "data memakai nilai di luar kosakata: " + ", ".join(extra)))
            unproven = sorted(set(allowed) - set(distinct))
            if unproven:
                flags.append(("belum_terbukti", "nilai sah belum ada di data: " + ", ".join(unproven)))
        elif distinct:
            flags.append(("kosakata_data", "kosakata hanya dari data: " + ", ".join(sorted(distinct))))
        if colors and spec.get("warn_colors"):
            uncovered = sorted(v for v in distinct if v != "(NULL)" and v.upper() not in colors)
            if uncovered:
                flags.append(("tanpa_warna",
                              "StatusBadge tidak punya kelas warna (jatuh ke netral): " + ", ".join(uncovered)))
        out.append({
            **spec,
            "allowed": allowed,
            "code": code,
            "distinct": distinct,
            "colors": colors,
            "flags": flags,
        })
    return out


# ---------------------------------------------------------------------------
# 11. Render
# ---------------------------------------------------------------------------

SCREEN_TITLES = {
    "today": "Hari Ini",
    "overview": "Overview",
    "recommendations": "Recommendations",
    "evidence": "Decision & Evidence",
    "safety": "Keamanan Pangan",
    "surplus": "Surplus & Limbah",
    "suppliers": "Pemasok",
    "kpi-kualitas": "KPI & Kualitas Agen",
    "agent-log": "Agent Log",
    "demo-control": "Demo Control",
    "settings": "Pengaturan",
    "global": "Global (di luar tab)",
}


def md_escape(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def render(rows: list[dict], enums: list[dict], ctx: dict) -> tuple[str, dict]:
    nav = ctx["nav"]
    routes = ctx["routes"]
    schema = ctx["schema"]
    db_cols = ctx["db_cols"]
    checks = ctx["checks"]
    tab_comps = ctx["tab_components"]
    orphans = ctx["orphans"]
    api_index = ctx["api_index"]
    params = ctx["params"]

    screen_order = [n["id"] for n in nav] + ["global"]
    section_order = {(s["screen"], s["section"]): i for i, s in enumerate(SECTIONS)}
    rows_sorted = sorted(
        rows,
        key=lambda r: (
            screen_order.index(r["screen"]) if r["screen"] in screen_order else 99,
            section_order.get((r["screen"], r["section"]), 99),
        ),
    )

    gap_rows = [r for r in rows_sorted if r["status"] == "GAP"]
    proven_rows = [r for r in rows_sorted if r["status"] == "TERBUKTI"]
    retired_rows = [r for r in rows_sorted if r["status"] == "DIPENSIUNKAN"]
    unverified = [r for r in rows_sorted if r["problems"]]
    # "tanpa data" = punya tabel data tetapi query buktinya 0 baris. Baris tanpa
    # tabel (status integrasi) dihitung terpisah: bukan kekosongan data.
    demo_rows = [r for r in rows_sorted if r["evidence"] is not None and r["evidence_n"] == 0]
    no_table_rows = [r for r in rows_sorted if r["evidence"] is None]
    uninstalled = [r for r in rows_sorted if not r["installed"]]

    state_gap = [
        (r, key) for r in rows_sorted for key, (status, _) in r["states"].items() if status == "GAP"
    ]
    state_na = [
        (r, key) for r in rows_sorted for key, (status, _) in r["states"].items() if status == "N/A"
    ]
    state_proven = [
        (r, key) for r in rows_sorted for key, (status, _) in r["states"].items() if status == "TERBUKTI"
    ]
    enum_flags = [(e, kind, note) for e in enums for kind, note in e["flags"]]

    model_vs_db = []
    for table in sorted(set(schema) | set(db_cols)):
        hanya_model = sorted(set(schema.get(table, {})) - set(db_cols.get(table, {})))
        hanya_db = sorted(set(db_cols.get(table, {})) - set(schema.get(table, {})))
        if hanya_model or hanya_db:
            model_vs_db.append((table, hanya_model, hanya_db))

    lines: list[str] = []
    add = lines.append

    add("# Matriks Cakupan Database — MealChain Guardian")
    add("")
    add(f"Dibuat otomatis oleh `scripts/audit/db_coverage.py` pada "
        f"{datetime.now(WIB).strftime('%Y-%m-%d %H:%M WIB')}. "
        "Seluruh angka di bawah diambil dari kondisi live saat skrip berjalan; "
        "berkas ini ditulis ulang setiap kali skrip dijalankan.")
    add("")
    add("**Sumber bukti:** route dari `app.main` (kontainer backend), skema dari "
        "`Base.metadata` + `information_schema`, kosakata dari `pg_constraint` + "
        "`Literal[...]` kode, respons dari panggilan HTTP nyata dengan akun demo, "
        "dan satu query SQL per baris matriks. Tidak ada angka yang ditulis tangan.")
    add("")
    add("## Ringkasan angka")
    add("")
    add("| Ukuran | Nilai |")
    add("|---|---|")
    add(f"| Layar/tab di sidebar | {len(nav)} (terbaca dari `navItems` di `app/page.tsx`) |")
    add(f"| Baris matriks (layar/bagian) | {len(rows_sorted)} |")
    add(f"| Baris TERBUKTI (data ada + endpoint 2xx) | {len(proven_rows)} |")
    add(f"| Baris GAP (belum ada data demo / klaim gagal) | {len(gap_rows)} |")
    add(f"| Baris DIPENSIUNKAN (panel sengaja tidak dipasang, ada bukti tes) | {len(retired_rows)} |")
    add(f"| Baris tanpa baris data sama sekali | {len(demo_rows)} |")
    add(f"| Baris tanpa tabel data (status dari env/artefak) | {len(no_table_rows)} |")
    add(f"| Baris yang panelnya tidak terpasang di layar | {len(uninstalled)} "
        f"(dari itu {len(retired_rows)} dipensiunkan sengaja) |")
    add(f"| Baris dengan klaim tak terverifikasi | {len(unverified)} |")
    add(f"| Tabel di `Base.metadata` | {len(schema)} |")
    add(f"| Tabel di DB (`information_schema`) | {len(db_cols)} |")
    add(f"| Route FastAPI hidup (path+method) | {len(routes)} |")
    add(f"| Route GET yang diprobe | {len(ctx['probed_paths'])} |")
    add(f"| Fungsi request frontend terbaca (`lib/*.ts`) | {len(api_index)} |")
    add(f"| Enum diperiksa | {len(enums)} |")
    add(f"| Enum dengan ketidaksinkronan (kode vs skema vs data) | {len(set(id(e) for e, _, _ in enum_flags))} |")
    add(f"| Sel state tampilan diperiksa | {len(state_proven) + len(state_gap) + len(state_na)} |")
    add(f"| Sel state TERBUKTI | {len(state_proven)} |")
    add(f"| Sel state GAP | {len(state_gap)} |")
    add(f"| Sel state tidak berlaku (N/A) | {len(state_na)} |")
    add(f"| Komponen di `frontend/components` | {len(ctx['components']) - 1} |")
    add(f"| Komponen tidak terpasang di layar mana pun | {len(orphans)} |")
    add("")
    add("Legenda status baris: **TERBUKTI** = semua klaim lolos pemeriksaan (label UI ada, "
        "fungsi api menunjuk route live, kolom ada di skema, endpoint membalas 2xx untuk "
        "peran utama layar itu, query bukti > 0 baris). **GAP** = ada klaim yang gagal "
        "atau datanya kosong; alasannya ada di kolom bukti dan di §5. Kolom *Terpasang* "
        "menandai panel yang benar-benar dirender; 403 pada peran lain adalah cakupan "
        "peran (desain), bukan kegagalan.")
    add("")

    snap_start = ctx["snap_start"]
    snap_end = ctx["snap_end"]
    moved = {t: (snap_start.get(t, 0), snap_end.get(t, 0))
             for t in sorted(set(snap_start) | set(snap_end))
             if snap_start.get(t, 0) != snap_end.get(t, 0)}
    add("## 0. Kondisi DB saat audit")
    add("")
    add("Jumlah baris dihitung dengan `count(*)` (bukan `n_live_tup`) pada awal dan akhir "
        "run. Kolom *bergerak* menandai tabel yang isinya berubah **selama** audit — "
        "kalau ada, angka di laporan ini adalah potret satu titik waktu, bukan nilai stabil.")
    add("")
    if moved:
        add(f"**Perhatian:** {len(moved)} tabel berubah selama audit (ada penulis lain di DB "
            "demo yang sama, mis. reset/seed deret demo). Angka baris di bawah = potret saat "
            "query dijalankan.")
        add("")
    add("| Tabel | Baris (awal) | Baris (akhir) | origin: seed / demo | Baris ber-sesi demo | Bergerak |")
    add("|---|---|---|---|---|---|")
    for table in sorted(snap_end):
        origin = ctx["origin"].get(table)
        origin_txt = (f"{origin.get('seed', 0)} / {origin.get('demo', 0)}" if origin else "—")
        marker = "ya" if table in moved else "tidak"
        add(f"| `{table}` | {snap_start.get(table, 0)} | {snap_end.get(table, 0)} | "
            f"{origin_txt} | {ctx['sessions'].get(table, '—')} | {marker} |")
    add("")

    add("## 1. Matriks layar → data")
    add("")
    add("Kolom *fungsi api* dan *endpoint* dihasilkan dari rantai nyata: nama fungsi "
        "diparse dari `frontend/lib/api.ts` (+ `lib/supplier-exclusions.ts`), path-nya "
        "dicocokkan ke route FastAPI yang hidup. Kolom *bukti demo* memuat hasil query "
        "per baris plus status HTTP endpoint utamanya untuk dua peran demo.")
    add("")
    add("| # | Layar | Bagian/panel | Terpasang | Field/kartu (terverifikasi di komponen) | Fungsi api | Endpoint backend | Tabel.kolom sumber | Bukti demo (query + HTTP) | Status |")
    add("|---|---|---|---|---|---|---|---|---|---|")
    for i, row in enumerate(rows_sorted, start=1):
        probe_txt = " · ".join(
            f"{p['role']} {p['status']}/{p['count']} baris" for p in row["probe_results"]
        )
        ev = (f"SQL {row['evidence_n']} baris, contoh `{row['evidence_sample']}`" if row["evidence"]
              else "tanpa tabel data (status dibaca dari env/artefak)")
        add("| {} | {} | {} | {} | {} | {} | {} | {} | {} ; {} | {} |".format(
            i,
            md_escape(SCREEN_TITLES.get(row["screen"], row["screen"])),
            md_escape(row["section"]),
            "ya" if row["installed"] else "**tidak**",
            md_escape(" · ".join(row["fields"])),
            md_escape(", ".join(row["api"])),
            md_escape("<br>".join(row["endpoints"])),
            md_escape(", ".join(row["tables"]) or "—"),
            md_escape(ev),
            md_escape(probe_txt),
            row["status"],
        ))
    add("")

    add("## 2. Peta layar → komponen → fungsi api")
    add("")
    add("Bagian ini membuktikan tidak ada layar yang tertinggal: komponen tiap tab "
        "dibaca dari blok `{tab === \"...\" && (...)}` di `app/page.tsx`, lalu fungsi "
        "api-nya dilacak lewat komponen dan hook (`lib/hooks/*`).")
    add("")
    add("| Layar | Komponen yang dirender | Fungsi api dipanggil langsung | Hook yang variabelnya dipakai | Fungsi api lewat hook |")
    add("|---|---|---|---|---|")
    for item in nav:
        comps = tab_comps.get(item["id"], [])
        info = ctx["tab_api"].get(item["id"], {"direct": [], "hooks": [], "via_hooks": []})
        add("| {} | {} | {} | {} | {} |".format(
            md_escape(item["label"]),
            md_escape(", ".join(comps)) or "—",
            md_escape(", ".join(info["direct"])) or "—",
            md_escape(", ".join(info["hooks"])) or "—",
            md_escape(", ".join(info["via_hooks"])) or "—",
        ))
    add("")
    if orphans:
        add("Komponen yang **tidak terpasang** di layar mana pun (endpoint-nya tetap hidup): "
            + ", ".join(f"`{o}`" for o in orphans) + ".")
        add("")

    add("## 3. Inventaris enum & nilai status")
    add("")
    add("Tiga sumber dibandingkan: kosakata **kode** (`Literal[...]`, tuple konstanta, "
        "union TypeScript), kosakata **skema** (`CHECK` constraint dari `pg_constraint`), "
        "dan nilai yang **benar-benar ada di data** (`select distinct`).")
    add("")
    add("| Enum | Kolom | Nilai di kode | CHECK di DB | Nilai di data (n) | Warna StatusBadge | Sinkron? | Catatan |")
    add("|---|---|---|---|---|---|---|---|")
    for enum in enums:
        code_txt = "; ".join(
            f"`{src}`: {', '.join(vals)}" for src, vals in enum["code"].items()
        ) or "—"
        allowed_txt = ", ".join(enum["allowed"]) if enum["allowed"] else "**tidak ada CHECK**"
        data_txt = ", ".join(f"{k} ({v})" for k, v in sorted(enum["distinct"].items())) or "—"
        colors_txt = (", ".join(sorted(c for c in enum["colors"])) if enum["colors"] else "—")
        verdict = "ya" if not enum["flags"] else "**tidak**"
        add("| {} | `{}.{}` | {} | {} | {} | {} | {} | {} |".format(
            md_escape(enum["name"]),
            enum["table"], enum["column"],
            md_escape(code_txt),
            md_escape(allowed_txt),
            md_escape(data_txt),
            md_escape(colors_txt),
            verdict,
            md_escape(enum.get("note") or "—"),
        ))
    add("")
    add("### 3.1 Ketidaksinkronan kode vs skema vs data")
    add("")
    add("| Enum | Jenis | Keterangan |")
    add("|---|---|---|")
    for enum, kind, note in enum_flags:
        add(f"| {md_escape(enum['name'])} | `{kind}` | {md_escape(note)} |")
    add("")
    add("Arti jenis: `kode_di_luar_skema` = kontrak kode menerima nilai yang ditolak DB "
        "(bug tulis); `skema_lebih_luas` = CHECK mengizinkan nilai yang tidak bisa "
        "dihasilkan kode (kontrak API lebih sempit dari skema); `belum_terbukti` = nilai "
        "sah yang belum punya satu baris pun di data demo; `data_di_luar_skema` = baris "
        "yang melanggar CHECK (tidak mungkin terjadi kecuali constraint dimatikan); "
        "`tanpa_check` = kolom status tanpa constraint sama sekali; `tanpa_warna` = "
        "`StatusBadge` tidak punya kelas warna sehingga nilai itu jatuh ke abu-abu netral.")
    add("")

    add("## 4. Inventaris state tampilan per layar")
    add("")
    add("State diuji dengan data nyata, bukan dengan membaca kode saja. `✓` = TERBUKTI "
        "(ada query/record yang membuktikannya), `GAP` = belum ada data demo yang bisa "
        "memicu state itu, `–` = tidak berlaku untuk baris tersebut (tidak punya tabel "
        "data / kolom terkait). Rincian bukti per sel ada di §4.2 untuk semua GAP, dan "
        "template query-nya di §6.")
    add("")
    header = "| Layar / bagian | " + " | ".join(k for k, _ in STATE_KEYS) + " |"
    add(header)
    add("|" + "---|" * (len(STATE_KEYS) + 1))
    for row in rows_sorted:
        cells = []
        for key, _ in STATE_KEYS:
            status, note = row["states"].get(key, ("N/A", ""))
            if status == "TERBUKTI":
                cells.append("✓")
            elif status == "GAP":
                cells.append("GAP")
            else:
                cells.append("–")
        add(f"| {md_escape(SCREEN_TITLES.get(row['screen'], row['screen']))} — {md_escape(row['section'])} | "
            + " | ".join(cells) + " |")
    add("")
    add("### 4.1 Arti tiap state")
    add("")
    add("| State | Definisi operasional |")
    add("|---|---|")
    for key, desc in STATE_KEYS:
        add(f"| `{key}` | {desc} |")
    add("")
    add("### 4.2 Bukti / alasan per state")
    add("")
    add("| Layar / bagian | State | Status | Bukti / alasan |")
    add("|---|---|---|---|")
    for row in rows_sorted:
        for key, _ in STATE_KEYS:
            status, note = row["states"].get(key, ("N/A", ""))
            add(f"| {md_escape(row['section'])} | `{key}` | {status} | {md_escape(note)} |")
    add("")

    add("## 5. Ringkasan GAP")
    add("")
    add("### 5.1 Baris tanpa data demo")
    add("")
    if demo_rows:
        add("| Layar | Bagian | Bukti | Alasan |")
        add("|---|---|---|---|")
        for row in demo_rows:
            reason = "query bukti 0 baris" if row["evidence"] else "tidak ada tabel data"
            add(f"| {md_escape(SCREEN_TITLES.get(row['screen'], row['screen']))} | "
                f"{md_escape(row['section'])} | SQL {row['evidence_n']} baris | {reason} |")
    else:
        add("Tidak ada: setiap baris matriks punya minimal satu baris data.")
    add("")
    add("### 5.2 Panel yang sengaja dipensiunkan (bukan GAP, ada bukti tes)")
    add("")
    if retired_rows:
        add("| Layar | Bagian | Bukti keputusan |")
        add("|---|---|---|")
        for row in retired_rows:
            add(f"| {md_escape(SCREEN_TITLES.get(row['screen'], row['screen']))} | "
                f"{md_escape(row['section'])} | {md_escape(row.get('retired_evidence') or '—')} |")
    else:
        add("Tidak ada.")
    add("")
    add("### 5.3 Baris GAP karena klaim gagal (bukan karena data kosong)")
    add("")
    failed = [r for r in gap_rows if r["evidence_n"] > 0]
    if failed:
        add("| Layar | Bagian | Masalah |")
        add("|---|---|---|")
        for row in failed:
            add(f"| {md_escape(SCREEN_TITLES.get(row['screen'], row['screen']))} | "
                f"{md_escape(row['section'])} | {md_escape('; '.join(row['problems']))} |")
    else:
        add("Tidak ada.")
    add("")
    add("### 5.4 State tampilan yang belum bisa dibuktikan")
    add("")
    per_state: dict[str, list[str]] = {}
    for row, key in state_gap:
        per_state.setdefault(key, []).append(row["section"])
    if per_state:
        add("| State | Jumlah layar | Layar |")
        add("|---|---|---|")
        for key, _ in STATE_KEYS:
            if key in per_state:
                add(f"| `{key}` | {len(per_state[key])} | {md_escape(', '.join(per_state[key]))} |")
    else:
        add("Tidak ada.")
    add("")
    add("### 5.4 Ketidaksinkronan enum")
    add("")
    if enum_flags:
        add("Lihat §3.1 — " + f"{len(set(id(e) for e, _, _ in enum_flags))} enum dengan "
            f"{len(enum_flags)} temuan. Yang paling berdampak: "
            + ", ".join(sorted({e["name"] for e, kind, _ in enum_flags if kind in ("kode_di_luar_skema", "data_di_luar_skema")}))
            + (" (kontrak tulis vs skema)" if any(kind == "kode_di_luar_skema" for _, kind, _ in enum_flags) else "")
            + ".")
    else:
        add("Tidak ada.")
    add("")
    add("### 5.5 Catatan model vs DB")
    add("")
    if model_vs_db:
        add("| Tabel | Kolom hanya di model | Kolom hanya di DB |")
        add("|---|---|---|")
        for table, only_model, only_db in model_vs_db:
            add(f"| `{table}` | {', '.join(only_model) or '—'} | {', '.join(only_db) or '—'} |")
    else:
        add("Tidak ada selisih: setiap kolom model ada di DB dan sebaliknya.")
    add("")

    add("## 6. Metode & query")
    add("")
    add("### 6.1 Parameter nyata yang dipakai probe")
    add("")
    add("| Parameter | Nilai | Asal |")
    add("|---|---|---|")
    for key in ("decision_id", "batch_id", "receipt_id", "exclusion_id", "po_number",
                "start_iso", "end_iso"):
        origin = {
            "decision_id": "keputusan dengan jejak terbanyak pada cakupan Jakarta (`agent_traces`)",
            "batch_id": "batch Jakarta yang punya baris penerimaan (`batch_receipts`)",
            "receipt_id": "`batch_receipts.id` pertama",
            "exclusion_id": "`supplier_exclusions.id` pertama",
            "po_number": "PO pertama yang punya `decision_id`",
            "start_iso": "`min(delivery_events.delivered_at)` WIB",
            "end_iso": "`max(delivery_events.delivered_at)` WIB",
        }[key]
        add(f"| `{key}` | `{params.get(key, '')}` | {origin} |")
    add("")
    add("### 6.2 Template query state per baris")
    add("")
    add("Setiap baris memakai satu query agregat dengan bentuk berikut (kolom opsional "
        "dilewati bila baris tidak menampilkan kolom itu):")
    add("")
    add("```sql")
    add("select")
    add("  (select count(*) from <tabel> where <saringan>),                         -- baris total")
    add("  (select count(*) from (select d.id from <dimensi> d")
    add("     where not exists (select 1 from <tabel> x")
    add("       where x.<fk>=d.id and <saringan>)) z),                            -- kunci kosong")
    add("  (select count(*) from (select d.id from <dimensi> d")
    add("     where (select count(*) from <tabel> x")
    add("       where x.<fk>=d.id and <saringan>)=1) z),                          -- tepat 1 item")
    add("  (select count(distinct (<kolom_urut>)::text) from <tabel> where <saringan>),")
    add("  (select count(*) from <tabel> where <saringan> and <kolom_null> is null),")
    add("  (select max(length((<kolom_teks>)::text)) from <tabel> where <saringan>),")
    add("  (select count(*) from <tabel> where <saringan> and (<kolom_teks>)::text ~ '[^ -~]'),")
    add("  (select count(*) from <tabel> where <saringan> and <kolom_angka>=0),")
    add("  (select count(*) from <tabel> where <saringan> and <kolom_angka><0),")
    add("  (select max(abs(<kolom_angka>)) from <tabel> where <saringan>),")
    add("  (select count(*) from <tabel> where <saringan> and (<tanggal>) < now()),")
    add("  (select count(*) from <tabel> where <saringan>")
    add("     and ((<tanggal>) at time zone 'Asia/Jakarta')::date")
    add("     = (now() at time zone 'Asia/Jakarta')::date),                      -- hari ini WIB")
    add("  (select count(*) from <tabel> where <saringan> and (<tanggal>) > now())")
    add("```")
    add("")
    add("### 6.3 Cara menjalankan ulang")
    add("")
    add("```bash")
    add("cd mealchain-guardian")
    add("python3 scripts/audit/db_coverage.py          # tulis docs/db-coverage-matrix.md")
    add("python3 scripts/audit/db_coverage.py --check  # tulis + periksa angka ringkasan")
    add("```")
    add("")
    add("Skrip hanya membaca: `SELECT` ke DB demo dan `GET`/satu `POST /balance/analyze` "
        "(tanpa penulisan keputusan) ke API. Tidak ada migrasi, tidak ada DELETE.")
    add("")

    text = "\n".join(lines)
    stats = {
        "screens": len(nav),
        "rows": len(rows_sorted),
        "proven": len(proven_rows),
        "gap": len(gap_rows),
        "demo_rows": len(demo_rows),
        "unverified": len(unverified),
        "state_total": len(state_proven) + len(state_gap) + len(state_na),
        "state_proven": len(state_proven),
        "state_gap": len(state_gap),
        "state_na": len(state_na),
        "enum_flags": len(enum_flags),
        "enums_with_flags": len(set(id(e) for e, _, _ in enum_flags)),
        "tables": len(schema),
        "routes": len(routes),
        "api_fns": len(api_index),
        "orphans": len(orphans),
        "uninstalled_rows": len(uninstalled),
    }
    return text, stats


# ---------------------------------------------------------------------------
# 12. Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="periksa angka ringkasan vs isi berkas")
    parser.add_argument("--no-wait", action="store_true",
                        help="jangan menunggu DB stabil (audit apa adanya, berguna saat demo berjalan)")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    print("[1/6] intropeksi route + skema dari live app ...")
    routes = live_routes()
    schema = live_metadata()
    db_cols = db_columns()
    checks = db_checks()
    if args.no_wait:
        snap_start = db_snapshot()
    else:
        print("      menunggu DB berhenti bergerak (DB demo dipakai bersama) ...")
        snap_start, waits = wait_for_stable_db()
        if waits > 1:
            print(f"      DB stabil setelah {waits} potret ({waits * 5} detik)")
    origin_tables = [t for t, cols in db_cols.items() if "origin" in cols]
    session_tables = [t for t, cols in db_cols.items() if "demo_session_id" in cols]
    origin = origin_split(origin_tables)
    sessions = session_rows(session_tables)

    print(f"      {len(routes)} route, {len(schema)} tabel (model), {len(db_cols)} tabel (DB)")

    print("[2/6] login user demo ...")
    tokens = {role: login(role) for role in DEMO_LOGIN}

    print("[3/6] index frontend (api.ts, komponen, tab, hook) ...")
    api_index = parse_api_index()
    components = read_component_sources()
    nav = parse_nav_items()
    tab_components, tab_sources = parse_tab_components()
    hooks = parse_hooks()
    orphans = orphan_components(components)
    bindings = hook_bindings(components["page"])

    tab_api = {
        tab: tab_api_functions(block, tab_components.get(tab, []), components,
                               api_index, hooks, bindings)
        for tab, block in tab_sources.items()
    }

    params = resolve_params(tokens)
    print(f"      decision_id={params['decision_id'][:8]}… batch_id={params['batch_id'][:8]}… "
          f"jendela={params['start']}..{params['end']}")

    print("[4/6] probe endpoint + query bukti ...")
    ctx = {
        "routes": routes, "schema": schema, "db_cols": db_cols, "checks": checks,
        "api_index": api_index, "components": components, "nav": nav,
        "tab_components": tab_components, "hooks": hooks, "orphans": orphans,
        "tab_api": tab_api, "tab_sources": tab_sources,
        "tokens": tokens, "params": params, "http_cache": {},
        "snap_start": snap_start, "origin": origin, "sessions": sessions,
        "guards": numeric_guards(checks),
    }
    rows = evaluate(ctx)

    probed, seen = [], set()
    for row in rows:
        for probe in row["probe_results"]:
            key = (probe["path"],)
            if key not in seen:
                seen.add(key)
                probed.append(probe["path"])
    ctx["probed_paths"] = probed

    print("[5/6] inventaris enum (kode vs CHECK vs data) ...")
    enums = evaluate_enums(ctx)
    ctx["snap_end"] = db_snapshot()

    print("[6/6] render + tulis docs/db-coverage-matrix.md ...")
    text, stats = render(rows, enums, ctx)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(text, encoding="utf-8")

    print()
    print(f"ditulis: {OUT_PATH.relative_to(ROOT)}  ({len(text.splitlines())} baris, {len(text)} byte)")
    print(f"  layar/tab            : {stats['screens']}")
    print(f"  baris matriks        : {stats['rows']} (TERBUKTI {stats['proven']}, GAP {stats['gap']})")
    print(f"  baris tanpa data     : {stats['demo_rows']}")
    print(f"  klaim tak terverifikasi: {stats['unverified']}")
    print(f"  sel state            : {stats['state_total']} (TERBUKTI {stats['state_proven']}, "
          f"GAP {stats['state_gap']}, N/A {stats['state_na']})")
    print(f"  enum                 : {stats['enums_with_flags']} dengan temuan / "
          f"{stats['enum_flags']} temuan")
    print(f"  tabel / route / api  : {stats['tables']} / {stats['routes']} / {stats['api_fns']}")

    for row in rows:
        if row["problems"]:
            print(f"  ! {row['screen']} / {row['section']}: {'; '.join(row['problems'])}")

    if args.check:
        return self_check(text, stats)
    return 0


def self_check(text: str, stats: dict) -> int:
    """Baca ulang berkas hasil dan cocokkan dengan angka yang dilaporkan."""
    written = OUT_PATH.read_text(encoding="utf-8")
    problems: list[str] = []

    matrix = written.split("## 1. Matriks layar → data")[1].split("## 2.")[0]
    matrix_rows = [l for l in matrix.splitlines() if l.startswith("| ") and not l.startswith("| #")
                   and not l.startswith("|---")]
    if len(matrix_rows) != stats["rows"]:
        problems.append(f"baris matriks di berkas {len(matrix_rows)} != dilaporkan {stats['rows']}")

    gap_cells = matrix_rows and sum(1 for l in matrix_rows if l.rstrip().endswith("GAP |"))
    if gap_cells != stats["gap"]:
        problems.append(f"status GAP di berkas {gap_cells} != dilaporkan {stats['gap']}")

    states_section = written.split("### 4.2 Bukti / alasan per state")[1].split("## 5.")[0]
    state_rows = [l for l in states_section.splitlines() if l.startswith("| ") and "`" in l]
    if len(state_rows) != stats["state_total"]:
        problems.append(f"sel state di berkas {len(state_rows)} != dilaporkan {stats['state_total']}")
    proven_cells = sum(1 for l in state_rows if "| TERBUKTI |" in l)
    gap_state_cells = sum(1 for l in state_rows if "| GAP |" in l)
    if proven_cells != stats["state_proven"]:
        problems.append(f"state TERBUKTI di berkas {proven_cells} != {stats['state_proven']}")
    if gap_state_cells != stats["state_gap"]:
        problems.append(f"state GAP di berkas {gap_state_cells} != {stats['state_gap']}")

    enum_section = written.split("### 3.1 Ketidaksinkronan kode vs skema vs data")[1].split("## 4.")[0]
    enum_rows = [l for l in enum_section.splitlines() if l.startswith("| ") and "`" in l and "---" not in l]
    if len(enum_rows) != stats["enum_flags"]:
        problems.append(f"temuan enum di berkas {len(enum_rows)} != {stats['enum_flags']}")

    header_counts = {
        "Layar/tab di sidebar": stats["screens"],
        "Baris matriks (layar/bagian)": stats["rows"],
        "Baris GAP (belum ada data demo / klaim gagal)": stats["gap"],
    }
    for label, expected in header_counts.items():
        match = re.search(r"\| " + re.escape(label) + r" \| (\d+)", written)
        if not match:
            problems.append(f"ringkasan '{label}' tidak ditemukan")
        elif int(match.group(1)) != expected:
            problems.append(f"ringkasan '{label}' = {match.group(1)} != {expected}")

    if problems:
        print()
        print("SELF-CHECK GAGAL:")
        for problem in problems:
            print("  - " + problem)
        return 1
    print()
    print(f"self-check OK: {stats['rows']} baris matriks, {stats['gap']} GAP, "
          f"{stats['state_total']} sel state, {stats['enum_flags']} temuan enum "
          f"— angka di berkas cocok dengan hasil hitung.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
