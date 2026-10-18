"""Satu-satunya pembentuk nomor PO yang diterbitkan sistem.

Kenapa ada modul ini (audit 18 Okt 2026): nomor PO dibuat di dua tempat dengan
dua gaya berbeda — `POST /actions/execute` memakai `MC-<12 hex>` sementara seed
aktivitas demo memakai `DEMO-PO-<KOTA>-<KOMODITAS>`. Keduanya sama-sama PO
yang lahir dari keputusan (`decision_id` terisi), jadi panel melaporkan
keduanya `origin=execution`, tetapi nomornya tidak bisa dibaca dengan satu
aturan. Sekarang keduanya memakai fungsi ini.

Baris impor SAP (tanpa `decision_id`, mis. `4500000001`) TIDAK memakai fungsi
ini: itu objek lain — PO yang diimpor, bukan diterbitkan aplikasi — dan panel
menandainya `origin=demo`.
"""

import uuid

PREFIX = "MC-"


def nomor_po(decision_id: uuid.UUID | str) -> str:
    """`MC-` + 12 hex pertama id keputusan (huruf besar).

    Deterministik: keputusan yang sama selalu menghasilkan nomor yang sama,
    jadi menjalankan ulang eksekusi tidak pernah membuat nomor kedua. Nilai
    yang bukan UUID ditolak — nomor PO yang dikarang lebih buruk daripada
    galat yang jelas.
    """
    if not isinstance(decision_id, uuid.UUID):
        decision_id = uuid.UUID(str(decision_id))
    return f"{PREFIX}{decision_id.hex[:12].upper()}"
