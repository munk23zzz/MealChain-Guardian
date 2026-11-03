"""Probe baca-saja: bentuk payload nyata endpoint yang BELUM dipakai jembatan A2A.

Langkah 1 peta cakupan data MealChain Guardian (lihat docs/peta-cakupan-data.md).
Tidak menulis apa pun ke backend: hanya GET, ditambah POST /auth/login.

Jalankan dari sap-joule/:
    ./.venv/Scripts/python.exe scripts/probe-cakupan-data.py

Keluaran: _qa/cakupan-data/<tanggal>/<nama>.json  (satu berkas per endpoint)
           _qa/cakupan-data/<tanggal>/ringkasan.txt (tabel status + kunci envelope)
Tidak pernah mencetak kata sandi atau token.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

BASE = os.environ.get("MEALCHAIN_API_URL", "http://localhost:8000").rstrip("/")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_qa" / "cakupan-data" / datetime.now(timezone.utc).strftime("%Y-%m-%d")
VERBOSE_KEYS = ("password", "token", "secret", "authorization", "api_key")


def login_read_only(client: httpx.Client) -> str:
    """Token akun baca-saja lewat autofill demo lokal; tanpa mencetak sandi."""
    r = client.get(f"{BASE}/auth/demo-login")
    r.raise_for_status()
    data = r.json()
    if not data.get("enabled"):
        sys.exit(
            "autofill akun demo tidak aktif (DEMO_MODE / DEMO_LOGIN_AUTOFILL / bukan loopback). "
            "Set kredensial baca lewat env, jangan tempel sandi di perintah."
        )
    akun = data.get("accounts") or []
    pilih = None
    for a in akun:
        peran = json.dumps(a.get("roles") or a.get("role") or "").lower()
        if "bgn_monitor" in peran or "monitor" in peran:
            pilih = a
            break
    pilih = pilih or akun[0]
    email = pilih.get("email") or pilih.get("username")
    sandi = pilih.get("password")
    r = client.post(f"{BASE}/auth/login", json={"email": email, "password": sandi})
    r.raise_for_status()
    body = r.json()
    print(f"login OK: {email} (peran {pilih.get('roles') or pilih.get('role')})")
    return body.get("access_token") or body.get("token")


def ringkas(payload, kedalaman=0):
    """Bentuk payload: kunci + tipe + jumlah baris, tanpa isi panjang."""
    if isinstance(payload, dict):
        hasil = {}
        for k, v in payload.items():
            if any(s in k.lower() for s in VERBOSE_KEYS):
                hasil[k] = "<disembunyikan>"
            else:
                hasil[k] = ringkas(v, kedalaman + 1)
        return hasil
    if isinstance(payload, list):
        return {"_list": len(payload), "_contoh": ringkas(payload[0], kedalaman + 1) if payload else None}
    if isinstance(payload, str) and len(payload) > 60:
        return payload[:60] + "…"
    if isinstance(payload, list) is False and isinstance(payload, (int, float, bool)) or payload is None:
        return payload
    return payload


def panggil(client, headers, nama, path, params=None):
    berkas = OUT / f"{nama}.json"
    try:
        r = client.get(f"{BASE}{path}", params=params or {}, headers=headers)
    except httpx.HTTPError as exc:
        berkas.write_text(json.dumps({"error": str(exc)}), encoding="utf-8")
        return nama, path, "ERROR", str(exc)[:90]
    try:
        body = r.json()
    except ValueError:
        body = {"_mentah": r.text[:400]}
    berkas.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    bentuk = json.dumps(ringkas(body), ensure_ascii=False)
    return nama, path, r.status_code, bentuk[:220]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    client = httpx.Client(timeout=40.0)
    token = login_read_only(client)
    headers = {"Authorization": f"Bearer {token}"}

    # id nyata untuk endpoint per-entitas, diambil dari sistem yang hidup
    keputusan = client.get(f"{BASE}/decisions", headers=headers).json()
    items = keputusan.get("items") if isinstance(keputusan, dict) else keputusan
    decision_id = (items or [{}])[0].get("id") or (items or [{}])[0].get("decision_id")
    lokasi_rows = client.get(f"{BASE}/admin/locations", headers=headers).json().get("locations") or []
    lokasi = (lokasi_rows or [{}])[0].get("id")
    surplus = client.get(f"{BASE}/surplus/regions", headers=headers).json()
    komoditas = (surplus.get("commodities") or [None])[0]
    hari_ini = datetime.now(timezone.utc).astimezone().date().isoformat()

    rencana = [
        ("procurement_summary", "/procurement/summary", {"periode": "today"}),
        ("receipts_riwayat", "/receipts/riwayat", {"limit": 5}),
        ("receipts_checklist", "/receipts/checklist", None),
        ("surplus_regions", "/surplus/regions", None),
        ("surplus_allocations", "/surplus/allocations", {"commodity": komoditas, "limit": 5}),
        ("agenda", "/agenda", {"start": hari_ini, "end": hari_ini}),
        ("balance_pair", f"/balance/{lokasi}/{komoditas}", None),
        ("decision_audit_facts", f"/decisions/{decision_id}/audit-facts", None),
        ("decision_dossier", f"/decisions/{decision_id}/dossier", None),
        ("decision_ledger", f"/decisions/{decision_id}/ledger", None),
        ("admin_locations", "/admin/locations", None),
        ("admin_users", "/admin/users", None),
    ]

    hasil = []
    for nama, path, params in rencana:
        hasil.append(panggil(client, headers, nama, path, params))

    lebar = max(len(h[0]) for h in hasil)
    lines = [
        f"Probe cakupan data — {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"backend {BASE} | pasangan uji {lokasi} / {komoditas} | decision {decision_id}",
        "",
    ]
    for nama, path, status, bentuk in hasil:
        lines.append(f"{nama.ljust(lebar)}  {str(status):>5}  {path}")
        lines.append(f"{'':{lebar}}  {'':>5}  {bentuk}")
    teks = "\n".join(lines)
    (OUT / "ringkasan.txt").write_text(teks, encoding="utf-8")
    print(teks)
    print(f"\nberkas: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
