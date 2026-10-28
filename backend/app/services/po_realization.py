"""Realisasi PO — berapa kg barang yang benar-benar terikat ke sebuah PO.

Sisi PO (nilai dipesan) sudah dihitung di `api/sap_orders.py` dari kolom yang
ada: `price × ordered_quantity`. Sisi barang masuk memakai jalur atribusi yang
SAMA dengan nilai penerimaan (`services/receipt_value.py`): bukti
`human_inspection` yang memuat `batch_ids`. Dibaca terbalik (PO → batch), ikatan
itu memberi kg yang benar-benar terikat ke PO tersebut.

Aturan yang dijaga di sini:

- **`None` ≠ 0.** PO tanpa ikatan bukti tidak punya barang tercatat, jadi
  kg/nilai/selisihnya `None` — pembaca harus melihat absennya, bukan "Rp 0".
- **Tidak menggandakan.** Satu batch bisa muncul di beberapa bukti untuk
  keputusan yang sama; `SELECT DISTINCT` membuat kg-nya dihitung sekali.
- **Read-only.** Tidak ada tabel atau kolom baru, tidak ada tulisan apa pun.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

#: Label basis angka, dikirim ke klien supaya panel bisa menyebut asalnya.
BASIS = "inspection_binding"

#: Satu kueri untuk semua PO pada satu halaman: dedupe dulu (DISTINCT), baru
#: dijumlahkan. Tanpa dedupe, batch yang tercatat di dua bukti akan dihitung
#: dua kali dan selisihnya menjadi angka karangan.
_SQL = text(
    """
    WITH ikatan AS (
        SELECT DISTINCT po.po_number, b.id AS batch_id, b.quantity_kg
        FROM sap_mock_purchase_orders po
        JOIN decisions d ON d.id = po.decision_id
        JOIN decision_evidence e ON e.decision_id = d.id
             AND e.evidence_type = 'human_inspection'
        CROSS JOIN LATERAL jsonb_array_elements_text(
            CASE WHEN jsonb_typeof(e.payload->'batch_ids') = 'array'
                 THEN e.payload->'batch_ids' ELSE '[]'::jsonb END
        ) AS t(batch_id)
        JOIN batches b ON b.id::text = t.batch_id
        WHERE po.po_number = ANY(:nomor)
    )
    SELECT po_number,
           COUNT(*) AS jumlah_batch,
           COALESCE(SUM(quantity_kg), 0) AS kg
    FROM ikatan
    GROUP BY po_number
    """
)


async def realisasi_po(
    db: AsyncSession, po_numbers: Iterable[str]
) -> dict[str, dict]:
    """`{po_number: {received_kg, received_batch_count, received_basis}}`.

    PO yang tidak muncul di hasil berarti belum ada batch terikat — pemanggil
    harus mengirim `None`, bukan angka nol.
    """
    nomor = [n for n in po_numbers if n]
    if not nomor:
        return {}
    rows = (await db.execute(_SQL, {"nomor": nomor})).mappings().all()
    return {
        str(r["po_number"]): {
            "received_kg": float(r["kg"]),
            "received_batch_count": int(r["jumlah_batch"]),
            "received_basis": BASIS,
        }
        for r in rows
    }
