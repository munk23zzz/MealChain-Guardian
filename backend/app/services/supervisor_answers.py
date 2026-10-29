"""Kalimat jawaban tool supervisor untuk agregasi status keputusan.

Kenapa dipisah dari router: kalimat ini pernah menjumlah ke 43 padahal total 49
(hanya empat status yang dihitung), dan kesalahan seperti itu tidak bisa diuji
selama ia hidup di dalam handler HTTP. Ambangnya sederhana — **angka yang
disebut harus menjumlah ke total, dan setiap status yang ada harus disebut atau
diringkas eksplisit**.
"""

from __future__ import annotations

from typing import Mapping


def ringkas_keputusan_per_status(hitung: Mapping[str, int]) -> dict:
    """Susun jawaban + data untuk pertanyaan "berapa keputusan per status".

    `hitung` = peta status → jumlah, apa adanya dari database. Tidak ada status
    yang dibuang dan tidak ada yang dikarang: status tak dikenal tetap disebut
    supaya angka di layar selalu bisa dijumlahkan pembaca.
    """
    bersih = {str(k): int(v) for k, v in (hitung or {}).items() if int(v) > 0}
    total = sum(bersih.values())
    if total == 0:
        return {
            "answer": "Belum ada keputusan tercatat.",
            "data": {"total": 0, "per_status": {}},
        }
    rincian = ", ".join(f"{k} {v}" for k, v in sorted(bersih.items()))
    return {
        "answer": f"Keputusan per status: {rincian} (total {total}).",
        "data": {"total": total, "per_status": dict(sorted(bersih.items()))},
    }
