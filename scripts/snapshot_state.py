#!/usr/bin/env python3
"""Snapshot keadaan MealChain Guardian (BACA-SAJA).

Menghasilkan `docs/state-snapshot.json` (untuk mesin) dan
`docs/state-snapshot.md` (untuk manusia) dari database `mealchain` + API hidup.

Aturan:
- Hanya SELECT dan GET. Tidak ada INSERT/UPDATE/DELETE, tidak ada rebuild,
  tidak menyentuh sesi demo. Aman dijalankan saat aplikasi sedang dipakai.
- Angka yang tidak terukur ditulis None, bukan 0.

Jalankan:
  python scripts/snapshot_state.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "docs" / "state-snapshot.json"
OUT_MD = ROOT / "docs" / "state-snapshot.md"
API = "http://127.0.0.1:8000"
DB = ["docker", "exec", "mealchain-postgres", "psql", "-U", "mealchain",
      "-d", "mealchain", "-tAc"]


def sql(q: str):
    """Satu nilai skalar dari psql; None bila query gagal."""
    out = subprocess.run(DB + [q], capture_output=True, text=True)
    if out.returncode != 0:
        return None
    v = out.stdout.strip()
    if v == "":
        return None
    try:
        return int(v)
    except ValueError:
        return v


def sql_pairs(q: str) -> dict:
    out = subprocess.run(DB + [q], capture_output=True, text=True)
    hasil = {}
    if out.returncode != 0:
        return hasil
    for baris in out.stdout.strip().splitlines():
        if "|" not in baris:
            continue
        k, v = baris.split("|", 1)
        try:
            hasil[k.strip()] = int(v.strip())
        except ValueError:
            hasil[k.strip()] = v.strip()
    return hasil


def api(path: str, token: str | None = None):
    req = urllib.request.Request(API + path)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        return {"_error": str(exc)}


def login() -> str | None:
    """Login baca-saja: /auth/login tidak menulis apa pun ke DB.

    Kredensial diambil dari verify/invariants.spec.json (sumber yang sama dengan
    gerbang verifikasi), lalu .env. Tidak ada nilai rahasia yang dicetak.
    """
    kred: dict = {}
    spec = ROOT / "verify" / "invariants.spec.json"
    if spec.exists():
        try:
            blok = json.loads(spec.read_text(encoding="utf-8")).get("login", {})
            kred.update(blok.get("json") or {})
        except (json.JSONDecodeError, OSError):
            pass
    env = ROOT / ".env"
    if env.exists():
        for baris in env.read_text(encoding="utf-8", errors="ignore").splitlines():
            if baris.startswith("DEMO_EMAIL="):
                kred.setdefault("email", baris.split("=", 1)[1].strip().strip('"'))
            elif baris.startswith("DEMO_PASSWORD="):
                kred.setdefault("password", baris.split("=", 1)[1].strip().strip('"'))
    if not kred.get("email") or not kred.get("password"):
        return None
    req = urllib.request.Request(
        API + "/auth/login", data=json.dumps(kred).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode()).get("access_token")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return None


def main() -> int:
    tabel = ["agent_traces", "approvals", "batch_receipts", "batches", "commodities",
             "decision_evidence", "decisions", "delivery_events", "demand_records",
             "demo_sessions", "disposal_events", "ledger_blocks", "locations",
             "menu_plans", "price_signals", "road_routes", "sap_mock_material_stock",
             "sap_mock_purchase_orders", "supplier_exclusions", "suppliers",
             "supply_records", "users"]
    snap: dict = {
        "diambil_pada": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "catatan": "Dihasilkan scripts/snapshot_state.py (baca-saja) dari DB mealchain + API.",
        "db": {},
    }
    for t in tabel:
        snap["db"][t] = sql(f"select count(*) from {t}")

    snap["db"]["decisions_per_status"] = sql_pairs(
        "select status, count(*) from decisions group by 1 order by 2 desc")
    snap["db"]["decisions_per_type"] = sql_pairs(
        "select decision_type, count(*) from decisions group by 1 order by 2 desc")
    snap["db"]["decisions_terbuka"] = sql(
        "select count(*) from decisions where status in ('pending_approval','verifier_flagged')")
    snap["db"]["suppliers_per_sertifikat"] = sql_pairs(
        "select coalesce(certification_status,'none'), count(*) from suppliers group by 1")
    snap["db"]["exclusions_per_status"] = sql_pairs(
        "select status, count(*) from supplier_exclusions group by 1")
    snap["db"]["receipts_per_status"] = sql_pairs(
        "select status, count(*) from batch_receipts group by 1")
    snap["db"]["po_per_status"] = sql_pairs(
        "select status, count(*) from sap_mock_purchase_orders group by 1")
    snap["db"]["users_per_role"] = sql_pairs(
        "select role, count(*) from users group by 1")
    snap["db"]["batch_per_safety"] = sql_pairs(
        "select coalesce(safety_status,'pending'), count(*) from batches group by 1")
    snap["db"]["batch_kedaluwarsa_48jam"] = sql(
        "select count(*) from batches where usable_until is not null "
        "and usable_until < now() + interval '48 hours'")
    snap["db"]["batch_ditahan"] = sql(
        "select count(*) from batches where quarantine_status = 'quarantined'")
    snap["db"]["sesi_per_status"] = sql_pairs(
        "select status, count(*) from demo_sessions group by 1")

    # rentang deret waktu + baris bertanggal masa depan (temuan, bukan fitur)
    snap["db"]["supply_rentang"] = sql(
        "select min(recorded_at) at time zone 'Asia/Jakarta' || ' .. ' || "
        "max(recorded_at) at time zone 'Asia/Jakarta' from supply_records")
    snap["db"]["supply_masa_depan"] = sql(
        "select count(*) from supply_records where recorded_at > now()")
    snap["db"]["price_masa_depan"] = sql(
        "select count(*) from price_signals where recorded_at > now()")

    token = login()
    snap["api"] = {"login": bool(token)}
    if token:
        snap["api"]["sesi"] = api("/demo/session", token)
        snap["api"]["agenda_hari_ini"] = api(
            f"/agenda?start={datetime.now().astimezone().strftime('%Y-%m-%d')}"
            f"&end={datetime.now().astimezone().strftime('%Y-%m-%d')}", token)
        snap["api"]["kpi_hari_ini"] = api("/kpi?periode=today", token)
        snap["api"]["routes"] = api("/supplier-routes?limit=200", token)
        snap["api"]["ledger"] = api("/ledger/verify", token)
        snap["api"]["decisions_24j"] = api("/decisions?window=24h", token)
        snap["api"]["suppliers_ringkas"] = {
            k: v for k, v in (api("/suppliers?limit=200", token) or {}).items()
            if k not in ("items",)}

    OUT_JSON.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- versi dokumen manusia -------------------------------------------
    def g(*jalur, default="—"):
        cur = snap
        for k in jalur:
            if not isinstance(cur, dict) or k not in cur:
                return default
            cur = cur[k]
        return default if cur is None else cur

    sesi = (snap.get("api", {}).get("sesi") or {})
    agenda = ((snap.get("api", {}).get("agenda_hari_ini") or {}).get("days") or [{}])[0]
    kpi = (snap.get("api", {}).get("kpi_hari_ini") or {})
    routes = ((snap.get("api", {}).get("routes") or {}).get("summary") or {})
    ledger = snap.get("api", {}).get("ledger") or {}
    kartu = (snap.get("api", {}).get("decisions_24j") or {}).get("count")

    def metric(nama):
        for m in kpi.get("metrics", []) or []:
            if m.get("name") == nama:
                if m.get("state") != "available" or m.get("value") is None:
                    return f"— ({m.get('state')})"
                return f"{m.get('value')} {m.get('unit')} (sampel {m.get('sample_count')})"
        return "—"

    md = [
        "# Snapshot keadaan MealChain Guardian",
        "",
        f"Diambil **{snap['diambil_pada']}** oleh `scripts/snapshot_state.py` (baca-saja).",
        "Dokumen ini adalah sumber angka untuk dokumen lain: kalau angka di dokumen lain",
        "berbeda, dokumen ini yang berlaku sampai snapshot berikutnya.",
        "",
        "## Volume tabel",
        "",
        "| Tabel | Baris |",
        "| --- | ---: |",
    ]
    for t in tabel:
        md.append(f"| `{t}` | {snap['db'][t]} |")
    md += ["", "## Keputusan", "",
           f"- Terbuka (menunggu / ditandai verifier): **{snap['db']['decisions_terbuka']}**",
           f"- Kartu di jendela 24 jam: **{kartu}**"]
    for k, v in (snap["db"]["decisions_per_status"] or {}).items():
        md.append(f"- status `{k}`: {v}")
    md += ["", "## Batch & keamanan", "",
           f"- Total batch: **{snap['db']['batches']}**",
           f"- Batch kedaluwarsa < 48 jam: **{snap['db']['batch_kedaluwarsa_48jam']}**",
           f"- Batch ditahan (karantina): **{snap['db']['batch_ditahan']}**"]
    for k, v in (snap["db"]["batch_per_safety"] or {}).items():
        md.append(f"- safety `{k}`: {v}")
    md += ["", "## Pemasok", "",
           f"- Total: **{snap['db']['suppliers']}**"]
    for k, v in (snap["db"]["suppliers_per_sertifikat"] or {}).items():
        md.append(f"- sertifikat `{k}`: {v}")
    for k, v in (snap["db"]["exclusions_per_status"] or {}).items():
        md.append(f"- eksklusi `{k}`: {v}")
    md += ["", "## Kiriman & rantai audit", "",
           f"- Rute kiriman (cakupan Jakarta): **{routes.get('routes')}** "
           f"(berjalur {routes.get('with_road')}, tanpa jalur {routes.get('without_road')})",
           f"- Tahap perjalanan: {routes.get('journey_states')}",
           f"- Ledger: **{ledger.get('blocks')}** blok (arsip {ledger.get('archived_blocks')}, "
           f"yatim {ledger.get('orphan_blocks')}, valid={ledger.get('valid')})",
           f"- Jejak agen: **{snap['db']['agent_traces']}** langkah",
           f"- PO mock SAP: **{snap['db']['sap_mock_purchase_orders']}**",
           f"- Bukti keputusan: **{snap['db']['decision_evidence']}**",
           f"- Approval: **{snap['db']['approvals']}**"]
    md += ["", "## Agenda & KPI hari ini", "",
           f"- Agenda: menu {agenda.get('menu', {}).get('rows')} rencana · "
           f"pengiriman {agenda.get('delivery', {}).get('rows')} · "
           f"limbah {agenda.get('disposal', {}).get('rows')} catatan · "
           f"pasokan {agenda.get('supply', {}).get('rows')} baris · "
           f"harga {agenda.get('price', {}).get('rows')} baris · "
           f"batch kedaluwarsa {agenda.get('batches_expiring', {}).get('rows')} · "
           f"keputusan {agenda.get('decisions', {}).get('rows')}",
           f"- Meal Continuity: {metric('Meal Continuity Rate')}",
           f"- Avoidable Food Loss: {metric('Avoidable Food Loss')}",
           f"- Regional Imbalance: {metric('Regional Imbalance Resolution Rate')}",
           f"- Safe Delivered Cost: {metric('Safe Delivered Cost')}",
           f"- Price Deviation: {metric('Procurement Price Deviation')}",
           f"- Decision Time: {metric('Decision Time')}",
           f"- Evidence Completeness: {metric('Evidence Completeness')}",
           f"- Sesi demo: active={sesi.get('active')}, sisa={sesi.get('remaining_seconds')} detik"]
    md += ["", "## Catatan data", "",
           f"- Deret pasokan: {snap['db']['supply_rentang']}",
           f"- Baris bertanggal **masa depan**: pasokan {snap['db']['supply_masa_depan']}, "
           f"harga {snap['db']['price_masa_depan']} (artefak penyemai, bukan data live)",
           "- Semua baris berasal dari template demo (`origin` seed/demo), bukan data operasional nyata.",
           "", "_Dokumen ini dihasilkan otomatis; jangan diedit tangan._", ""]
    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print("JSON:", OUT_JSON)
    print("MD  :", OUT_MD)
    print("keputusan:", snap["db"]["decisions"], "| batch:", snap["db"]["batches"],
          "| pemasok:", snap["db"]["suppliers"], "| rute:", routes.get("routes"),
          "| ledger:", ledger.get("blocks"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
