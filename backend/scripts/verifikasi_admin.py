"""Verifikasi /admin/* dengan akun demo NYATA (S4-11).

Dibuktikan lewat HTTP: login sungguhan (bukan override dependency), lalu
- bgn_monitor  → 200 (boleh kelola pengguna & lokasi)
- sppg_head    → 403 (tidak boleh)
- tanpa token  → 401

Password demo dibaca dari `app.seed.seed_data`
(daftar `DEMO_USERS`; nilainya TIDAK dicetak) dan TIDAK pernah dicetak.
Jalankan dari dalam kontainer backend: `python scripts/verifikasi_admin.py`.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from app.seed.seed_data import DEMO_USERS

BASE = "http://127.0.0.1:8000"


def _panggil(method: str, path: str, token: str | None = None, body: dict | None = None):
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
        return exc.code, (exc.read().decode("utf-8", "replace")[:120])


def _obj(body) -> dict:
    """Badan respons sebagai dict (jalur error mengembalikan teks)."""
    return body if isinstance(body, dict) else {}


def _akun(role: str) -> dict:
    """Temukan email demo untuk sebuah peran (bentuk apa pun dari seeder)."""
    kandidat = DEMO_USERS.values() if isinstance(DEMO_USERS, dict) else DEMO_USERS
    for item in kandidat:
        if isinstance(item, dict) and item.get("role") == role:
            return item
    raise SystemExit(f"akun demo {role} tidak ditemukan")


def _login(akun: dict) -> str:
    pw = akun["password"]
    status, body = _panggil("POST", "/auth/login", body={"email": akun["email"], "password": pw})
    isi = _obj(body)
    token = isi.get("token") or isi.get("access_token")
    if status != 200 or not token:
        raise SystemExit(
            f"login {akun['email']} gagal: HTTP {status}; kunci respons: {sorted(isi) or body!r}"
        )
    print(f"  login {akun['email']:<28} -> HTTP 200")
    return token


def main() -> int:
    print("1) Akun bgn_monitor")
    monitor = _login(_akun("bgn_monitor"))
    status, users = _panggil("GET", "/admin/users", monitor)
    print(f"  GET /admin/users     -> HTTP {status} ({len(_obj(users).get('users', []))} pengguna)")
    status, locs = _panggil("GET", "/admin/locations", monitor)
    jumlah_lokasi = len(_obj(locs).get("locations", []))
    print(f"  GET /admin/locations -> HTTP {status} ({jumlah_lokasi} lokasi)")

    uji = _obj(users)["users"][0]
    status, ubah = _panggil("PATCH", f"/admin/users/{uji['id']}", monitor, {"role": "admin"})
    print(f"  PATCH role 'admin'   -> HTTP {status} (harus 422)")

    print("2) Akun sppg_head (tidak boleh mengelola)")
    head = _login(_akun("sppg_head"))
    status, _ = _panggil("GET", "/admin/users", head)
    print(f"  GET /admin/users     -> HTTP {status} (harus 403)")

    print("3) Tanpa token")
    status, _ = _panggil("GET", "/admin/users")
    print(f"  GET /admin/users     -> HTTP {status} (harus 401)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
