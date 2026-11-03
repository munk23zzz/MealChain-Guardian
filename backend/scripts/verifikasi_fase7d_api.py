"""Bukti Fase 7d di jalur API NYATA (bukan unit test): kaki pertama masuk biaya.

Urutan yang diuji = urutan yang dipakai UI:
  login → /auth/me → POST /balance/analyze → POST /decisions → GET /decisions/{id}

Yang diperiksa (dan dicetak apa adanya):
1. `/balance/analyze` mengirim `supplier_leg` + pecahan `transport_supplier_leg` /
   `transport_linehaul` / `supplier_leg_km` / `supplier_leg_reference`;
2. jumlah komponen SDC = `safe_delivered_cost` (breakdown tetap auditable);
3. keputusan yang dibuat dari rekomendasi itu MENYIMPAN pecahannya di DB
   (`cost_breakdown`), jadi bukti biaya tidak hilang setelah approve.

Kata sandi TIDAK pernah ditulis di sini: diambil dari `app.seed.seed_data.DEMO_USERS`
(akun demo lokal) dan tidak pernah dicetak.

Jalankan di kontainer: `docker compose exec -T backend python scripts/verifikasi_fase7d_api.py`
"""

import json
import os
import sys
import urllib.error
import urllib.request
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.seed.seed_data import DEMO_USERS  # noqa: E402

BASE = os.environ.get("VERIFY_BASE_URL", "http://localhost:8000")
KOMODITAS = "telur"
TUJUAN = "Jakarta"


def _call(method: str, path: str, token: str | None = None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode() or "{}")


def main() -> None:
    user = next(u for u in DEMO_USERS if u["role"] == "sppg_head")
    status, login = _call(
        "POST", "/auth/login", body={"email": user["email"], "password": user["password"]}
    )
    assert status == 200, f"login gagal: {status}"
    token = login["access_token"]
    status, me = _call("GET", "/auth/me", token)
    print(f"akun demo          : {me['role']} @ {me.get('location') or '-'} (login {status})")

    status, analyzed = _call("POST", "/balance/analyze", token, {"commodity": KOMODITAS})
    assert status == 200, f"/balance/analyze gagal: {status} {analyzed}"
    recs = [
        r
        for r in analyzed["recommendations"]
        if r["candidate"]["destination_location"] == TUJUAN
    ]
    assert recs, "tidak ada kandidat menuju Jakarta"
    rec = recs[0]
    bd = rec["cost_breakdown"]
    leg = rec["supplier_leg"]
    print(f"kandidat teratas   : {rec['candidate']['source_location']}→{TUJUAN} "
          f"{rec['candidate']['quantity_kg']} kg (rank {rec['rank']})")
    print(f"supplier_leg       : km={leg['km']} cost={leg['cost']} reference={leg['reference']}")
    print(f"pecahan angkut     : kaki={bd['transport_supplier_leg']} "
          f"linehaul={bd['transport_linehaul']} "
          f"total(transport)={bd['transport']} alias(logistics)={bd['logistics']}")
    komponen = (
        "purchase", "transport", "handling",
        "expected_loss", "freshness_risk", "safety_penalty",
    )
    jumlah = sum((Decimal(bd[k]) for k in komponen), Decimal("0"))
    print(f"jumlah komponen    : {jumlah} vs safe_delivered_cost {rec['safe_delivered_cost']} "
          f"→ {'SAMA' if jumlah == Decimal(rec['safe_delivered_cost']) else 'BERBEDA'}")

    status, created = _call(
        "POST",
        "/decisions",
        token,
        {"decision_type": "regional_balance", "ttl_minutes": 60, "recommendation": rec},
    )
    print(f"POST /decisions    : {status}")
    assert status == 201, f"gagal membuat keputusan: {status} {created}"
    decision_id = created.get("decision_id") or created.get("id")
    status, stored = _call("GET", f"/decisions/{decision_id}", token)
    stored_bd = stored.get("cost_breakdown") or {}
    print(f"GET /decisions/{{id}}: {status} — cost_breakdown tersimpan: "
          f"kaki={stored_bd.get('transport_supplier_leg')} "
          f"linehaul={stored_bd.get('transport_linehaul')} "
          f"km={stored_bd.get('supplier_leg_km')} "
          f"ref={stored_bd.get('supplier_leg_reference')}")
    ok = (
        stored_bd.get("transport_supplier_leg") == bd["transport_supplier_leg"]
        and stored_bd.get("supplier_leg_reference") == bd["supplier_leg_reference"]
    )
    print("KESIMPULAN         :", "jalur API & DB menyimpan jarak pemasok" if ok
          else "TIDAK konsisten — periksa lagi")
    print(f"decision_id        : {decision_id}")


if __name__ == "__main__":
    main()
