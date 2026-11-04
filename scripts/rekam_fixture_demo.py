#!/usr/bin/env python3
"""Rekam respons API MealChain Guardian menjadi berkas fixture statis.

Dipakai untuk demo statis (GitHub Pages): UI diekspor sebagai HTML/JS, lalu
`frontend/lib/mock-api.ts` menjawab semua panggilan fetch dari berkas JSON yang
dihasilkan skrip ini. Tidak ada API yang perlu hidup saat halaman dibuka.

Cara pakai (stack lokal harus hidup: docker compose up -d):

    python scripts/rekam_fixture_demo.py

Hasil: frontend/public/mock/api.json — peta {peran: {"METHOD /path?kueri": {...}}}.

Catatan:
  * Hanya respons 2xx yang disimpan sebagai data; 401/403 ikut disimpan supaya
    perilaku per peran (mis. /admin/* hanya untuk BGN) tampil apa adanya.
  * Semua kombinasi lokasi x komoditas direkam untuk peran BGN; peran SPPG
    hanya lokasinya sendiri (backend memang membatasi cakupan).
  * Skrip ini HANYA membaca (GET). Tidak ada tulisan ke database.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

API = "http://localhost:8000"
OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "mock" / "api.json"
ROLES = {
    "sppg_head": ("sppg.head@demo.local", "Demo#SPPG2026"),
    "sppg_nutritionist": ("sppg.nutritionist@demo.local", "Demo#Nut2026"),
    "bgn_monitor": ("bgn.monitor@demo.local", "Demo#BGN2026"),
}


def call(path: str, method: str = "GET", body=None, token: str | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw)
        except Exception:
            return exc.code, raw[:400]


def main() -> None:
    tokens: dict[str, str] = {}
    for role, (email, password) in ROLES.items():
        status, body = call("/auth/login", "POST", {"email": email, "password": password})
        if status != 200:
            raise SystemExit(f"login {role} gagal: {status} {body}")
        tokens[role] = body["access_token"]

    bgn = tokens["bgn_monitor"]
    _, lokasi_body = call("/admin/locations", token=bgn)
    locations = [x["name"] for x in lokasi_body["locations"]]
    _, komoditas_body = call("/demo/agent/commodities", token=tokens["sppg_head"])
    commodities = komoditas_body["commodities"]

    _, daftar = call("/decisions", token=bgn)
    items = daftar.get("items", daftar) if isinstance(daftar, dict) else daftar
    # SEMUA keputusan, bukan empat pertama: rincian tiap id dipakai popup
    # "Decision & Evidence". Kalau hanya sebagian yang direkam, sisa baris jatuh
    # ke pola {id} dan menampilkan isi keputusan LAIN (mis. baris "pending"
    # membuka body "executed") — kontradiksi yang langsung terlihat juri.
    decision_ids = [x["decision_id"] for x in items][:60] if items else []
    _, batches = call("/batches?limit=500", token=bgn)
    batch_list = batches if isinstance(batches, list) else batches.get("batches", [])
    def id_batch(x):
        return x.get("batch_id") or x.get("id") or ""
    batch_id = id_batch(batch_list[0]) if batch_list else ""
    batch_ids = [id_batch(x) for x in batch_list if id_batch(x)][:10]

    today = date.today().isoformat()
    start = (date.today() - timedelta(days=14)).isoformat()

    def common_paths(loc: str) -> list[str]:
        paths = [
            "/auth/me",
            "/kpi?periode=today",
            "/kpi?periode=7d",
            "/kpi?periode=1bulan",
            "/decisions",
            "/decisions?status=waiting",
            "/decisions?status=executed",
            "/batches?limit=500",
            "/suppliers?limit=200",
            "/supplier-routes?limit=200",
            "/price/monitor",
            "/waste/summary?days=30",
            "/receipts/menunggu",
            "/receipts/riwayat",
            f"/receipts/checklist?batch_id={batch_id}&location={loc}",
            "/sap/purchase-orders",
            "/sap/purchase-orders/summary",
            "/procurement/summary?periode=today",
            "/integrations/status",
            "/ledger/verify",
            f"/agenda?start={start}&end={today}",
            "/demo/data-status",
            "/demo/session",
            "/demo/agent/commodities",
            "/demo/agent/last-run",
            "/agent/supervisor/health",
            "/events/price-anomaly",
            "/events/safety-disruption",
        ]
        for commodity in commodities:
            paths += [
                f"/balance/map?commodity={commodity}",
                f"/balance/{loc}/{commodity}",
                f"/surplus/regions?commodity={commodity}&limit=6",
                f"/surplus/allocations?commodity={commodity}&limit=6",
                f"/supply/{loc}/{commodity}",
                f"/demand/{loc}/{commodity}",
                f"/demand/forecast/{loc}/{commodity}?horizon_days=7",
                f"/price/quotes/{loc}/{commodity}",
                f"/suppliers?limit=200&commodity={commodity}",
            ]
        paths += ["/supplier-exclusions"]
        for b in batch_ids:
            paths.append(f"/receipts?batch_id={b}&limit=50")
        for decision_id in decision_ids:
            paths += [
                f"/decisions/{decision_id}",
                f"/decisions/{decision_id}/chain",
                f"/decisions/{decision_id}/ledger",
                f"/decisions/{decision_id}/traces",
                f"/decisions/{decision_id}/dossier",
                f"/decisions/{decision_id}/packet",
                f"/decisions/{decision_id}/review",
                f"/decisions/{decision_id}/approval-summary",
                f"/decisions/{decision_id}/compliance",
                f"/supplier-exclusions/context/{decision_id}",
            ]
        return paths

    fixtures: dict[str, dict] = {}
    ringkasan: list[str] = []
    for role, token in tokens.items():
        _, me = call("/auth/me", token=token)
        loc = me["location_name"] if me.get("location_name") else locations[0]
        scope = locations if role == "bgn_monitor" else [loc]
        paths = set(common_paths(scope[0]))
        if role == "bgn_monitor":
            paths |= {"/admin/locations", "/admin/users"}
            for other in scope:
                paths |= {f"/supply/{other}/{c}" for c in commodities}
                paths |= {f"/demand/{other}/{c}" for c in commodities}
                paths |= {f"/demand/forecast/{other}/{c}?horizon_days=7" for c in commodities}
                paths |= {f"/price/quotes/{other}/{c}" for c in commodities}
        data: dict[str, dict] = {}
        gagal = 0
        for path in sorted(paths):
            status, body = call(path, token=token)
            if status >= 400:
                gagal += 1
            data[f"GET {path}"] = {"status": status, "body": body}
        fixtures[role] = data
        ringkasan.append(f"{role}: {len(data)} kunci, {gagal} berstatus >=400")

    OUT_SUMBER = OUT.parent
    OUT_SUMBER.mkdir(parents=True, exist_ok=True)
    total = 0
    for peran, data in fixtures.items():
        berkas = OUT_SUMBER / f"api-{peran}.json"
        berkas.write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
        total += berkas.stat().st_size
        print(f"ditulis: {berkas.name} ({berkas.stat().st_size / 1048576:.2f} MB, {len(data)} kunci)")
    print(f"total {total / 1048576:.2f} MB")


if __name__ == "__main__":
    main()
