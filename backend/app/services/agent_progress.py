"""Saluran kemajuan putaran agent — dipakai Demo Control untuk log langsung.

Masalah yang dijawab (29 Okt 2026): pipeline agent menulis seluruh jejak langkah
saat putaran SELESAI, sehingga tombol "Jalankan agent" hanya memperlihatkan
"tunggu…" selama puluhan detik dan langkah-langkahnya muncul sekaligus. Pemilik
meminta log proses pengambilan data terlihat seperti terminal: baris datang satu
per satu.

Bentuk yang dipilih: **pub/sub dalam proses**, bukan SSE yang menjalankan ulang
pipeline. Alasannya:

- jalur penulisan (POST /demo/agent/run) TIDAK berubah perilakunya — ia hanya
  menerima `run_token` opsional dan memanggil callback setiap langkah selesai;
- tidak ada logika bisnis yang digandakan di endpoint streaming (menggandakan
  putaran berarti dua keputusan lahir dari satu klik);
- kalau peramban tidak bisa streaming, tombol tetap bekerja seperti dulu.

Batas jujur yang dipegang: kanal ini hanya membawa APA YANG SUDAH DIHITUNG
pipeline (`_TraceStep`). Ia tidak menghitung ulang, tidak mengarang langkah
tambahan, dan kehilangan siaran tidak pernah menggagalkan putaran.

Utas: pipeline berjalan di threadpool (punya event loop sendiri lewat
`asyncio.run`), sedangkan endpoint SSE hidup di event loop FastAPI. Karena itu
antrean yang dipakai adalah `queue.Queue` (aman antar-utas), bukan `asyncio.Queue`.
"""

from __future__ import annotations

import queue
import threading
import time
from typing import Any, Callable

#: Umur maksimum sebuah kanal tanpa pembaca. Mencegah kebocoran bila peramban
#: menutup tab di tengah putaran tanpa pernah membuka stream.
UMUR_MAKS_DETIK = 300.0

_KUNCI = threading.Lock()
_KANAL: dict[str, tuple[queue.Queue, float]] = {}


def _bersihkan() -> None:
    """Buang kanal yang sudah terlalu tua (dipanggil saat token baru dibuka)."""
    batas = time.monotonic() - UMUR_MAKS_DETIK
    for token, (_, dibuat) in list(_KANAL.items()):
        if dibuat < batas:
            _KANAL.pop(token, None)


def buka(token: str) -> queue.Queue:
    """Buat (atau ganti) kanal untuk satu token dan kembalikan antreannya."""
    antrean: queue.Queue = queue.Queue(maxsize=512)
    with _KUNCI:
        _bersihkan()
        _KANAL[token] = (antrean, time.monotonic())
    return antrean


def tutup(token: str) -> None:
    with _KUNCI:
        _KANAL.pop(token, None)


def ringkas(nilai: Any, maks: int = 4, panjang: int = 60) -> str:
    """`output_summary` → satu baris `k=v · k=v` untuk log.

    Hanya nilai skalar yang dicetak. Daftar/dict tidak diratakan menjadi JSON
    panjang: log ini untuk dibaca sekilas, dan struktur bersarang sudah bisa
    dilihat utuh di tab Agent Log.
    """
    if not isinstance(nilai, dict):
        return ""
    bagian: list[str] = []
    for kunci, isi in nilai.items():
        if len(bagian) >= maks:
            break
        if isinstance(isi, bool):
            teks = "ya" if isi else "tidak"
        elif isinstance(isi, (int, float)):
            teks = f"{isi:g}" if isinstance(isi, float) else str(isi)
        elif isinstance(isi, str):
            teks = isi.strip().replace("\n", " ")
        else:
            continue
        if not teks:
            continue
        if len(teks) > panjang:
            teks = teks[: panjang - 1] + "…"
        bagian.append(f"{kunci}={teks}")
    return " · ".join(bagian)


def penerbit(token: str | None) -> Callable[[Any], None] | None:
    """Callback `on_step` yang menyiarkan satu langkah ke kanal `token`.

    `None` bila klien tidak meminta streaming: pipeline berjalan tanpa biaya
    tambahan. Kesalahan siaran (antrean penuh, kanal ditutup) ditelan — telemetri
    tidak boleh menggagalkan putaran yang sedang menulis keputusan.
    """
    if not token:
        return None

    def kirim(langkah: Any) -> None:
        data = {
            "step": str(getattr(langkah, "step_name", "") or ""),
            "tool": getattr(langkah, "tool_called", None),
            "ringkas": ringkas(getattr(langkah, "output_summary", None)),
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        with _KUNCI:
            pasangan = _KANAL.get(token)
        if pasangan is None:
            return
        antrean = pasangan[0]
        try:
            antrean.put_nowait(data)
        except queue.Full:  # pragma: no cover — 512 langkah tidak realistis
            pass

    return kirim
