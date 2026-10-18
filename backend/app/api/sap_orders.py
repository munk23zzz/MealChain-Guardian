"""Purchase order mock SAP — sisi BACA yang selama ini tidak ada.

Latar (17 Okt 2026): `api/actions.py` sudah lama menulis baris ke
`sap_mock_purchase_orders` setiap kali sebuah keputusan dieksekusi (PO `MC-*`
berstatus `submitted`), dan seed menambahkan tiga PO `DEMO-PO-*` berstatus
`confirmed`. Tetapi **tidak ada satu rute pun yang membacanya**: satu-satunya
jejak di layar adalah toast sesaat di `DecisionActions.tsx`, sedangkan
`services/kpi_service.py` hanya memakai tabel ini sebagai agregat. Akibatnya
klaim "dua approval → PO terbit di SAP" tidak bisa ditunjukkan ke siapa pun.

Modul ini menutup celah itu dengan tiga aturan:

1. **Sumber data adalah TABEL DB**, bukan `MockSAPProvider.get_purchase_orders()`.
   Provider itu mengembalikan dict `_POS` yang di-hardcode di modulnya sendiri —
   daftar statis yang isinya TIDAK sama dengan baris yang benar-benar ditulis
   eksekusi. Memakai provider di sini akan menghasilkan pembaca palsu: layar
   menampilkan PO yang tidak pernah diterbitkan dan menyembunyikan yang nyata.
   Adapter (`SAPDataProvider`) tetap jalur yang benar untuk `SAP_MODE=aws_mcp`
   nanti, karena di mode itu sumbernya memang SAP, bukan tabel kita.
2. **Read-only, tanpa perhitungan ulang.** `ordered_quantity` dan `price` dibaca
   apa adanya; `total_value = price × qty` hanya untuk kenyamanan tampilan.
   Tidak ada penulisan, tidak ada status yang diubah, tidak ada PO yang dibuat.
3. **Cakupan mengikuti `core/scope.py`** (Ruling 2026-10-14): peran SPPG hanya
   melihat PO untuk keputusan bertarget lokasinya; `bgn_monitor` lintas lokasi.
   PO tanpa keputusan (mis. baris seed/adapter) tidak punya lokasi, jadi **tidak
   pernah** terlihat oleh peran SPPG — hanya monitor nasional.
4. **Asal baris dikirim eksplisit** (`origin`): `execution` bila PO punya
   `decision_id` (lahir dari `POST /actions/execute`), `demo` bila baris seed.
   Panel memakainya supaya PO `DEMO-PO-*` tidak tampil seolah terbit dari
   eksekusi yang belum pernah terjadi.
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.dependencies import get_db
from app.core.scope import is_national_scope, scope_location_id
from app.models import User

router = APIRouter()

#: Label sumber yang ikut dikirim ke klien. Panel memakainya untuk menyebut
#: asal data apa adanya: tabel transaksi mock di DB demo, BUKAN SAP S/4HANA.
SUMBER = "mock_sap_table"

#: Batas kewarasan satu permintaan. Nilai lebih besar dijepit, bukan ditolak —
#: klien yang mengirim `limit=10000` tetap mendapat jawaban yang bisa dipakai.
BATAS_MAKS = 200
BATAS_DEFAULT = 50

STATUS_SAH = ("draft", "submitted", "confirmed")

_SELECT = (
    "SELECT po.po_number, po.status, po.created_at, po.decision_id, "
    "d.status AS decision_status, d.target_location_id AS location_id, "
    "l.name AS location_name, po.supplier_id, s.name AS supplier_name, "
    "po.material_number, po.ordered_quantity, po.price "
    "FROM sap_mock_purchase_orders po "
    "LEFT JOIN decisions d ON d.id = po.decision_id "
    "LEFT JOIN locations l ON l.id = d.target_location_id "
    "LEFT JOIN suppliers s ON s.id = po.supplier_id "
)


def _baris(row) -> dict:
    """Satu PO → bentuk kabel. Nilai dibaca apa adanya dari kolom."""
    qty = float(row["ordered_quantity"])
    harga = float(row["price"])
    return {
        "po_number": row["po_number"],
        "status": row["status"],
        "created_at": row["created_at"].isoformat(),
        "decision_id": str(row["decision_id"]) if row["decision_id"] else None,
        "decision_status": row["decision_status"],
        "location_id": str(row["location_id"]) if row["location_id"] else None,
        "location_name": row["location_name"],
        "supplier_id": str(row["supplier_id"]) if row["supplier_id"] else None,
        "supplier_name": row["supplier_name"],
        "material_number": row["material_number"],
        "ordered_quantity_kg": qty,
        "price_per_kg": harga,
        "total_value": round(harga * qty, 2),
        "source": SUMBER,
        # Fakta turunan, bukan label seragam: hanya baris yang lahir dari
        # eksekusi keputusan punya decision_id. Baris seed (DEMO-PO-*,
        # 4500000001) tidak pernah melewati approval, jadi tidak boleh tampil
        # seolah "terbit dari eksekusi".
        "origin": "execution" if row["decision_id"] else "demo",
    }


@router.get("/sap/purchase-orders")
async def daftar_purchase_order(
    status: Literal["draft", "submitted", "confirmed"] | None = Query(
        None, description="Saring satu status PO"
    ),
    decision_id: uuid.UUID | None = Query(None, description="PO milik satu keputusan"),
    limit: int = Query(BATAS_DEFAULT, ge=1, description="Dijepit ke 200"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Daftar PO mock SAP yang boleh dibaca user ini (read-only)."""
    lokasi = scope_location_id(user)
    jepit = min(limit, BATAS_MAKS)

    sql = _SELECT
    syarat: list[str] = []
    params: dict = {"limit": jepit}
    if lokasi is not None:
        # Peran SPPG: hanya PO bertarget lokasinya. Baris tanpa keputusan
        # (decision_id NULL) otomatis gugur karena target_location_id NULL.
        syarat.append("d.target_location_id = :lokasi")
        params["lokasi"] = str(lokasi)
    if status is not None:
        syarat.append("po.status = :status")
        params["status"] = status
    if decision_id is not None:
        syarat.append("po.decision_id = :keputusan")
        params["keputusan"] = str(decision_id)
    if syarat:
        sql += "WHERE " + " AND ".join(syarat) + " "
    sql += "ORDER BY po.created_at DESC, po.po_number ASC LIMIT :limit"

    rows = (await db.execute(text(sql), params)).mappings().all()
    items = [_baris(r) for r in rows]
    return {
        "items": items,
        "count": len(items),
        "limit": jepit,
        "scope": "nasional" if is_national_scope(user) else "lokasi",
        "source": SUMBER,
    }


@router.get("/sap/purchase-orders/summary")
async def ringkas_purchase_order(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Jumlah per status + total nilai, dengan cakupan yang sama seperti daftar."""
    lokasi = scope_location_id(user)

    sql = (
        "SELECT po.status, COUNT(*) AS jumlah, "
        "COALESCE(SUM(po.price * po.ordered_quantity), 0) AS nilai "
        "FROM sap_mock_purchase_orders po "
        "LEFT JOIN decisions d ON d.id = po.decision_id "
    )
    params: dict = {}
    if lokasi is not None:
        sql += "WHERE d.target_location_id = :lokasi "
        params["lokasi"] = str(lokasi)
    sql += "GROUP BY po.status"

    rows = (await db.execute(text(sql), params)).mappings().all()
    by_status = {k: 0 for k in STATUS_SAH}
    total = 0.0
    for row in rows:
        by_status[row["status"]] = int(row["jumlah"])
        total += float(row["nilai"])
    return {
        "by_status": by_status,
        "count": sum(by_status.values()),
        "total_value": round(total, 2),
        "scope": "nasional" if is_national_scope(user) else "lokasi",
        "source": SUMBER,
    }
