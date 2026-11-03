#!/usr/bin/env python3
"""Shim untuk AgentCore Gateway: meneruskan permintaan ke backend + Bearer token.

Kenapa ada: backend deterministik menolak permintaan tanpa Bearer token, sedangkan
target Gateway tidak bisa menyimpan header statis pada `authorization` (header itu
dibatasi AWS). Gateway hanya bisa meneruskan header lain. Jadi permintaan Gateway
masuk ke shim ini, shim menambahkan Authorization, lalu meneruskannya ke backend.

Sifat:
- Hanya meneruskan; tidak punya logika domain dan tidak menyimpan data.
- Token dibuat ulang dari JWT_SECRET (HS256) memakai identitas user demo yang
  diberikan lewat env: SHIM_USER_ID, SHIM_USER_ROLE, SHIM_USER_LOC.
- Header Authorization yang SUDAH dikirim pemanggil tidak ditimpa, supaya klien
  ber-token sendiri tetap memakai identitasnya.
- Tidak mencetak token; hanya mencetak kode status per permintaan.

Jalankan:
  SHIM_PORT=18300 BACKEND_URL=http://127.0.0.1:8000 \
  JWT_SECRET=... SHIM_USER_ID=... SHIM_USER_ROLE=sppg_head SHIM_USER_LOC=... \
  python infra/gateway-shim/shim.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BACKEND = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
PORT = int(os.environ.get("SHIM_PORT", "18300"))
_RAHASIA = os.environ.get("JWT_SECRET", "")
_UID = os.environ.get("SHIM_USER_ID", "")
_ROLE = os.environ.get("SHIM_USER_ROLE", "sppg_head")
_LOC = os.environ.get("SHIM_USER_LOC", "")
_token_nilai = ""
_token_dibuat = 0.0

DILEWATI = {"host", "content-length", "connection", "accept-encoding"}


def token() -> str:
    """Token HS256; dibuat ulang tiap 50 menit (JWT_EXPIRE dijepit backend)."""
    global _token_nilai, _token_dibuat
    if _token_nilai and time.time() - _token_dibuat < 3000:
        return _token_nilai
    import jwt as pyjwt

    sekarang = int(time.time())
    nilai = pyjwt.encode(
        {"sub": _UID, "role": _ROLE, "loc": _LOC, "iat": sekarang, "exp": sekarang + 5400},
        _RAHASIA,
        algorithm="HS256",
    )
    _token_nilai = nilai
    _token_dibuat = time.time()
    return nilai


class Shim(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args) -> None:
        sys.stderr.write("[shim] %s\n" % (format % args))

    def _teruskan(self, metode: str) -> None:
        panjang = int(self.headers.get("Content-Length") or 0)
        isi = self.rfile.read(panjang) if panjang else None
        header = {k: v for k, v in self.headers.items() if k.lower() not in DILEWATI}
        if "Authorization" not in header:
            header["Authorization"] = f"Bearer {token()}"
        req = urllib.request.Request(f"{BACKEND}{self.path}", data=isi, headers=header, method=metode)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                kode, badan, jenis = resp.status, resp.read(), resp.headers.get("Content-Type", "application/json")
        except urllib.error.HTTPError as exc:
            kode, badan, jenis = exc.code, exc.read(), exc.headers.get("Content-Type", "application/json")
        except Exception as exc:  # noqa: BLE001
            kode, badan, jenis = 502, json.dumps({"detail": f"shim gagal: {type(exc).__name__}"}).encode(), "application/json"
        self.send_response(kode)
        self.send_header("Content-Type", jenis)
        self.send_header("Content-Length", str(len(badan)))
        self.end_headers()
        self.wfile.write(badan)

    def do_GET(self) -> None:
        self._teruskan("GET")

    def do_POST(self) -> None:
        self._teruskan("POST")

    def do_PUT(self) -> None:
        self._teruskan("PUT")

    def do_DELETE(self) -> None:
        self._teruskan("DELETE")


def main() -> int:
    if not (_RAHASIA and _UID):
        print("JWT_SECRET dan SHIM_USER_ID wajib diisi", file=sys.stderr)
        return 2
    print(f"[shim] {BACKEND} di :{PORT} (identitas {_ROLE})", file=sys.stderr)
    ThreadingHTTPServer(("0.0.0.0", PORT), Shim).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
