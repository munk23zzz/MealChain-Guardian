"""Pembatas laju sederhana untuk endpoint yang bisa disalahgunakan (SEC-03).

Konteks audit 24 Okt 2026: `/auth/login` tidak punya pembatas apa pun, sehingga
satu skrip bisa mencoba ribuan kata sandi tanpa jeda. Untuk demo satu-proses ini
pembatas berbasis memori sudah memadai; bila backend dijalankan multi-worker,
pindahkan penghitungnya ke Redis/Postgres (lihat catatan di bawah).

Desain yang dipilih:
- Kunci = kombinasi IP + email (bukan IP saja): satu kantor/NAT dengan banyak
  pengguna sah tidak saling memblokir, sementara satu akun tetap dibatasi.
- Hanya percobaan GAGAL yang dihitung; login berhasil menghapus riwayat kunci itu
  sehingga pengguna sah tidak pernah terkena batas karena salah ketik sekali.
- Jendela geser (sliding window): daftar waktu percobaan disimpan, bukan
  penghitung yang di-reset tiap menit — batas tidak bisa "ditunggu" di detik
  pergantian menit.
"""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque

#: Batas bawaan: 20 percobaan gagal per 60 detik per (IP, email).
BATAS_BAWAAN = 20
JENDELA_BAWAAN = 60.0

_kunci = threading.Lock()
_riwayat: dict[str, deque[float]] = defaultdict(deque)


def batas() -> int:
    """Batas percobaan gagal per jendela (bisa diatur lewat env)."""
    try:
        return max(1, int(os.environ.get("LOGIN_RATE_LIMIT", str(BATAS_BAWAAN))))
    except ValueError:
        return BATAS_BAWAAN


def jendela() -> float:
    try:
        return max(1.0, float(os.environ.get("LOGIN_RATE_WINDOW", str(JENDELA_BAWAAN))))
    except ValueError:
        return JENDELA_BAWAAN


def sisa_tunggu(kunci: str, sekarang: float | None = None) -> float:
    """Detik yang harus ditunggu sebelum kunci ini boleh mencoba lagi (0 = bebas)."""
    kini = time.monotonic() if sekarang is None else sekarang
    with _kunci:
        waktu = _riwayat.get(kunci)
        if not waktu:
            return 0.0
        _pangkas(waktu, kini)
        if len(waktu) < batas():
            return 0.0
        return max(0.0, jendela() - (kini - waktu[0]))


def catat_gagal(kunci: str, sekarang: float | None = None) -> None:
    """Catat satu percobaan gagal untuk kunci ini."""
    kini = time.monotonic() if sekarang is None else sekarang
    with _kunci:
        waktu = _riwayat[kunci]
        _pangkas(waktu, kini)
        waktu.append(kini)


def lupakan(kunci: str) -> None:
    """Hapus riwayat kunci (dipanggil setelah login berhasil)."""
    with _kunci:
        _riwayat.pop(kunci, None)


def reset_semua() -> None:
    """Kosongkan seluruh penghitung — hanya untuk tes."""
    with _kunci:
        _riwayat.clear()


def _pangkas(waktu: deque[float], kini: float) -> None:
    batas_waktu = kini - jendela()
    while waktu and waktu[0] <= batas_waktu:
        waktu.popleft()
