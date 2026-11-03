"""Purchase order mock SAP — sisi BACA yang selama ini tidak ada.

Latar (17 Okt 2026): `api/actions.py` sudah lama menulis baris ke
`sap_mock_purchase_orders` setiap kali sebuah keputusan dieksekusi (PO `MC-*`
berstatus `submitted`), dan seed aktivitas demo menambahkan PO `MC-*` juga
berstatus
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
   `decision_id` (lahir dari `POST /actions/execute` atau seed aktivitas demo),
   `demo` bila baris impor SAP tanpa keputusan (mis. `4500000001`).
   Sejak audit M8 (18 Okt 2026) semua PO yang lahir dari keputusan memakai
   `MC-<12 hex id keputusan>` — satu aturan, satu pembentuk (`core/po_number`).
"""

import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.dependencies import get_db
from app.core.approval_matrix import evaluate_approvals
from app.core.commercial_cost import commercial_cost, commercial_cost_payload
from app.core.scope import is_national_scope, scope_location_id
from app.models import Decision, User
from app.services import po_document
from app.services.approval_summary import syarat_persetujuan
from app.services.po_realization import realisasi_po

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
    "po.material_number, po.ordered_quantity, po.price, "
    "d.quantity_kg AS decision_quantity, d.cost_breakdown AS cost_breakdown, "
    "d.safe_delivered_cost AS decision_sdc, "
    # Nama bahan dari keputusan (relasi commodities). Baris impor SAP tanpa
    # keputusan memang tidak punya nama — frontend menulis "bahan tidak
    # tercatat", bukan menebak dari kode `MAT-BERA`.
    "c.name AS commodity_name "
    "FROM sap_mock_purchase_orders po "
    "LEFT JOIN decisions d ON d.id = po.decision_id "
    "LEFT JOIN locations l ON l.id = d.target_location_id "
    "LEFT JOIN suppliers s ON s.id = po.supplier_id "
    "LEFT JOIN commodities c ON c.id = d.commodity_id "
)


def _breakdown(row) -> dict | None:
    """`cost_breakdown` dari SELECT mentah: jsonb bisa datang sebagai dict atau str.

    Query di modul ini memakai `text()`, jadi tipenya tidak dikenali driver dan
    asyncpg bisa mengembalikan JSON mentah. Keduanya diterima; yang tidak bisa
    diartikan diperlakukan sebagai "tidak tercatat", bukan sebagai nol.
    """
    mentah = row["cost_breakdown"] if "cost_breakdown" in row.keys() else None
    if isinstance(mentah, dict):
        return mentah
    if isinstance(mentah, str) and mentah.strip():
        try:
            dibaca = json.loads(mentah)
        except ValueError:
            return None
        return dibaca if isinstance(dibaca, dict) else None
    return None


def cost_legacy_of(row) -> str:
    """Basis harga satu baris PO: komersial, lama, atau tidak berlaku.

    Tiga nilai (kontrak `GET /sap/purchase-orders`):

    - ``not_applicable`` — tidak ada keputusan/rincian biaya, jadi tidak ada
      yang bisa dibandingkan (mis. baris impor SAP tanpa keputusan).
    - ``legacy_unmigrated`` — rincian ada tetapi harga tersimpan BUKAN harga
      invoice (masih `sdc / qty`), atau rincian belum lengkap sehingga invoice
      tidak bisa diturunkan. Angkanya TIDAK diubah: menulis ulang dokumen
      historis butuh keputusan pemilik (rencana Fase 5 butir 8).
    - ``migrated`` — harga tersimpan sama dengan harga satuan komersial
      (`bahan + transportasi + penanganan`) untuk rincian yang sama.

    Label ini fakta terukur (perbandingan angka), bukan penanda yang disetel
    saat menulis: baris lama tidak bisa mengaku berkontrak baru.
    """
    breakdown = _breakdown(row)
    qty = row["decision_quantity"] if "decision_quantity" in row.keys() else None
    if not breakdown or qty is None:
        return "not_applicable"
    biaya = commercial_cost(qty, breakdown)
    if biaya is None:
        return "legacy_unmigrated"
    tersimpan = Decimal(str(row["price"])).quantize(Decimal("0.01"))
    dasar = biaya.invoice_unit_price.quantize(Decimal("0.01"))
    return "migrated" if tersimpan == dasar else "legacy_unmigrated"


COST_LEGACY_LABEL = {
    "legacy_unmigrated": "format biaya lama (belum dimigrasi)",
    "migrated": "basis komersial (bahan + transportasi + penanganan)",
    "not_applicable": "tidak berlaku (tanpa rincian biaya)",
}


def invoice_total_of(row) -> float:
    """Total invoice satu baris PO; `price × qty` bila invoice tidak dapat diturunkan.

    `price` di tabel sudah dibulatkan per kg (2 desimal, HALF_UP), jadi
    `qty × price` bisa berbeda dari total invoice sebesar paling banyak
    setengah sen per kg — mis. invoice 11,00 untuk 3 kg menghasilkan harga
    satuan 3,67 dan tagihan baris 11,01. Field `invoice_total` mencantumkan
    total invoice yang dapat diturunkan dari rincian biaya, sedangkan
    `total_value` tetap fakta tabel SAP (`price × qty`); keduanya dikirim
    supaya selisih pembulatan itu terbaca, bukan tersembunyi di satu angka.

    Baris legacy tanpa rincian lengkap tidak punya invoice yang dapat
    diturunkan, jadi yang dipakai adalah angka yang benar-benar tertagih di
    tabel (`price × qty`) — dan barisnya tetap ditandai `legacy_unmigrated`.
    """
    qty = row["ordered_quantity"]
    breakdown = _breakdown(row)
    if breakdown:
        biaya = commercial_cost(qty, breakdown)
        if biaya is not None:
            return float(biaya.invoice_total)
    return round(float(row["price"]) * float(qty), 2)


def _baris(row, realisasi: dict | None = None) -> dict:
    """Satu PO → bentuk kabel. Nilai dibaca apa adanya dari kolom.

    `realisasi` = hasil `po_realization.realisasi_po` untuk halaman ini. Bila PO
    tidak punya ikatan bukti, angka barang masuk dikirim `None` — bukan 0 — supaya
    panel bisa menulis "belum ada barang tercatat" alih-alih "Rp 0".
    """
    qty = float(row["ordered_quantity"])
    harga = float(row["price"])
    cost_legacy = cost_legacy_of(row)
    total = round(harga * qty, 2)
    masuk = (realisasi or {}).get(row["po_number"])
    received_kg = float(masuk["received_kg"]) if masuk else None
    received_value = round(harga * received_kg, 2) if received_kg is not None else None
    variance = (
        round(received_value - total, 2) if received_value is not None else None
    )
    variance_pct = (
        round(variance / total * 100, 2) if (variance is not None and total) else None
    )
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
        "commodity_name": row["commodity_name"],
        "ordered_quantity_kg": qty,
        # Dua nama untuk SATU arti: `price` di tabel ini adalah harga yang
        # ditagihkan (sejak Fase 5 = harga satuan invoice). Nama lama
        # `price_per_kg` dipertahankan karena panel/tes lama memakainya, tetapi
        # artinya sekarang dinamai eksplisit supaya klien tidak menebak.
        "price_per_kg": harga,
        "invoice_unit_price": harga,
        # `invoice_total` = total invoice (bahan + transportasi + penanganan)
        # yang bisa diturunkan dari rincian. `total_value` tetap fakta tabel
        # SAP (`price × qty`); selisih keduanya adalah pembulatan per kg dan
        # sengaja dikirim sebagai dua angka, bukan disamarkan jadi satu.
        "invoice_total": invoice_total_of(row),
        "cost_legacy": cost_legacy,
        "cost_legacy_label": COST_LEGACY_LABEL[cost_legacy],
        # SDC analitis keputusan (pembanding internal, BUKAN tagihan). `None`
        # untuk PO tanpa keputusan — pembaca harus melihat absennya, bukan nol.
        "sdc_total": (
            float(row["decision_sdc"])
            if "decision_sdc" in row.keys() and row["decision_sdc"] is not None
            else None
        ),
        "total_value": total,
        # ---- realisasi (Dok 05 §9 butir 3): nilai PO vs nilai barang masuk ----
        # Dihitung server dari ikatan bukti (`human_inspection` → `batch_ids`),
        # jalur yang sama dengan nilai penerimaan. `None` = belum ada barang
        # tercatat untuk PO ini; `0.0` hanya sah bila memang ada batch 0 kg.
        "received_kg": received_kg,
        "received_value_idr": received_value,
        "variance_idr": variance,
        "variance_pct": variance_pct,
        "received_batch_count": int(masuk["received_batch_count"]) if masuk else 0,
        "received_basis": masuk["received_basis"] if masuk else None,
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
    # Satu kueri realisasi untuk seluruh halaman (bukan per baris).
    realisasi = await realisasi_po(db, [r["po_number"] for r in rows])
    items = [_baris(r, realisasi) for r in rows]
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


# ── Dokumen PO (PDF) ────────────────────────────────────────────────────────
# Hanya untuk PO yang LAHIR DARI KEPUTUSAN YANG SUDAH DISETUJUI. Alasannya
# bukan teknis: PDF adalah dokumen yang dibawa keluar aplikasi dan diserahkan
# ke orang lain, jadi ia hanya boleh ada untuk pembelian yang approval-nya
# benar-benar tercatat. PO impor tanpa keputusan dan PO dari keputusan yang
# masih menunggu ditolak 409 dengan alasan — bukan diberi dokumen kosong.

_SELECT_SATU = (
    "SELECT po.po_number, po.status, po.created_at, po.ordered_quantity, po.price, "
    "po.decision_id, po.material_number, "
    "d.quantity_kg AS decision_quantity, d.cost_breakdown AS cost_breakdown, "
    "l.name AS location_name, s.name AS supplier_name, c.name AS commodity_name "
    "FROM sap_mock_purchase_orders po "
    "LEFT JOIN decisions d ON d.id = po.decision_id "
    "LEFT JOIN locations l ON l.id = d.target_location_id "
    "LEFT JOIN suppliers s ON s.id = po.supplier_id "
    "LEFT JOIN commodities c ON c.id = d.commodity_id "
    "WHERE po.po_number = :nomor"
)

_SELECT_PERSETUJUAN = (
    "SELECT a.approved, a.comment, a.approved_at, u.name, u.role "
    "FROM approvals a JOIN users u ON u.id = a.approved_by "
    "WHERE a.decision_id = :keputusan "
    "ORDER BY a.approved_at ASC, a.id ASC"
)


async def _dokumen_po(db: AsyncSession, row) -> dict:
    """Isi dokumen satu PO — satu sumber untuk PDF dan JSON detail (29 Okt 2026).

    Sebelumnya dict dokumen hanya hidup di dalam rute PDF, jadi jembatan A2A
    (yang hanya bicara JSON) tidak bisa menjawab "isi PO MC-…" selengkap
    dokumennya. Dua pemakai, satu bentuk data: kalau PDF berubah, JSON ikut.
    """
    qty = float(row["ordered_quantity"])
    harga = float(row["price"])
    dokumen: dict = {
        "po_number": row["po_number"],
        "status": row["status"],
        "created_at": row["created_at"],
        "ordered_quantity": qty,
        "price": harga,
        # Satu aturan dengan endpoint daftar: total = harga × kuantitas.
        "total": round(harga * qty, 2),
        "material_number": row["material_number"],
        "commodity_name": row["commodity_name"],
        "location_name": row["location_name"],
        "supplier_name": row["supplier_name"],
        # Dua arti biaya dipisah: `commercial_cost` (bahan/transportasi/
        # penanganan + SDC analitis) dan `cost_legacy` (harga tersimpan masih
        # basis lama). `None` = tidak tercatat, bukan nol.
        "commercial_cost": None,
        "cost_legacy": cost_legacy_of(row),
        "keputusan": None,
        "persetujuan": [],
        "syarat": {"min_approvals": None, "required_roles": [], "satisfied": False},
        "boleh_pdf": False,
    }
    if row["decision_id"] is None:
        return dokumen

    keputusan = (
        await db.execute(select(Decision).where(Decision.id == row["decision_id"]))
    ).scalar_one_or_none()
    if keputusan is None:
        return dokumen

    persetujuan = [
        {
            "role": r["role"],
            "name": r["name"],
            "approved": bool(r["approved"]),
            "comment": r["comment"],
            "approved_at": r["approved_at"],
        }
        for r in (await db.execute(text(_SELECT_PERSETUJUAN), {"keputusan": str(keputusan.id)}))
        .mappings()
        .all()
    ]
    syarat = syarat_persetujuan(keputusan)
    hasil = evaluate_approvals(
        syarat, [{"role": b["role"], "approved": b["approved"]} for b in persetujuan]
    )
    dokumen.update(
        {
            "commercial_cost": commercial_cost_payload(
                keputusan.quantity_kg, keputusan.cost_breakdown
            ),
            "keputusan": {
                "id": str(keputusan.id),
                "jenis": keputusan.decision_type,
                "status": keputusan.status,
                "iteration": keputusan.iteration,
                "proposed_by": keputusan.proposed_by,
                "created_at": keputusan.created_at,
                "expires_at": keputusan.expires_at,
            },
            "persetujuan": persetujuan,
            "syarat": {
                "min_approvals": syarat.get("min_approvals"),
                "required_roles": syarat.get("required_roles"),
                "satisfied": hasil["satisfied"],
            },
            "boleh_pdf": po_document.boleh_pdf(keputusan.status),
        }
    )
    return dokumen


def _basis_publik(request: Request) -> str:
    """Basis URL absolut untuk tautan PDF yang dikirim ke Joule.

    Di belakang tunnel, `request.base_url` sudah memuat host yang dijangkau
    klien. `PUBLIC_BASE_URL` menimpanya untuk pemasangan di belakang proxy yang
    menulis ulang skema/host (mis. Cloud Foundry + tunnel).
    """
    return (os.environ.get("PUBLIC_BASE_URL") or str(request.base_url)).rstrip("/")


@router.get("/sap/purchase-orders/{po_number}/detail")
async def detail_purchase_order(
    po_number: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Isi satu purchase order sebagai JSON — bahan yang sama dengan PDF PO.

    Dipakai jembatan A2A (Joule) yang hanya bisa membaca JSON: rincian biaya,
    siapa menyetujui dan komentarnya, syarat persetujuan, serta keputusan asal.
    Cakupan sama dengan daftar/PDF: PO lokasi lain dijawab 404, bukan 403.
    """
    lokasi = scope_location_id(user)
    sql = _SELECT_SATU
    params: dict = {"nomor": po_number}
    if lokasi is not None:
        sql += " AND d.target_location_id = :lokasi"
        params["lokasi"] = str(lokasi)

    row = (await db.execute(text(sql), params)).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="purchase order tidak ditemukan")

    dokumen = await _dokumen_po(db, row)
    return {
        "po_number": dokumen["po_number"],
        "status": dokumen["status"],
        "created_at": dokumen["created_at"],
        "material_number": dokumen["material_number"],
        "commodity_name": dokumen["commodity_name"],
        "location_name": dokumen["location_name"],
        "supplier_name": dokumen["supplier_name"],
        "ordered_quantity": dokumen["ordered_quantity"],
        "price": dokumen["price"],
        "total": dokumen["total"],
        "commercial_cost": dokumen["commercial_cost"],
        "keputusan": dokumen["keputusan"],
        "persetujuan": dokumen["persetujuan"],
        "syarat": dokumen["syarat"],
        "boleh_pdf": dokumen["boleh_pdf"],
        # Tautan berumur pendek supaya Joule bisa menyebut PDF yang sedang
        # dibacanya (chat tidak membawa token login dan tidak bisa melampirkan
        # berkas). `None` bila PO belum boleh punya PDF — jembatan lalu tidak
        # menjanjikan tautan yang akan ditolak.
        "pdf_url": (
            po_document.link_pdf_publik(po_number, _basis_publik(request))
            if dokumen["boleh_pdf"]
            else None
        ),
        "source": SUMBER,
    }


@router.get("/sap/purchase-orders/{po_number}/pdf")
async def unduh_purchase_order_pdf(
    po_number: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """Unduh satu purchase order sebagai PDF, lengkap dengan dasar persetujuannya.

    Cakupan sama dengan daftar (`core/scope.py`): PO di luar lokasi peran SPPG
    dijawab 404 — sama seperti daftar yang tidak memuatnya, supaya keberadaan
    PO lokasi lain tidak bocor lewat pesan galat.
    """
    lokasi = scope_location_id(user)
    sql = _SELECT_SATU
    params: dict = {"nomor": po_number}
    if lokasi is not None:
        sql += " AND d.target_location_id = :lokasi"
        params["lokasi"] = str(lokasi)

    row = (await db.execute(text(sql), params)).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="purchase order tidak ditemukan")

    if row["decision_id"] is None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"PO {row['po_number']} tidak lahir dari keputusan — PDF hanya "
                "diterbitkan untuk PO yang sudah disetujui"
            ),
        )

    keputusan = (
        await db.execute(select(Decision).where(Decision.id == row["decision_id"]))
    ).scalar_one_or_none()
    if keputusan is None:
        raise HTTPException(status_code=404, detail="purchase order tidak ditemukan")
    if not po_document.boleh_pdf(keputusan.status):
        raise HTTPException(
            status_code=409,
            detail=(
                f"keputusan {po_document.status_keputusan_label(keputusan.status).lower()} "
                "— PDF PO diterbitkan setelah keputusan disetujui"
            ),
        )

    # Isi dokumen dibangun satu kali di `_dokumen_po` (dipakai juga oleh JSON
    # detail), supaya PDF dan JSON tidak bisa berbeda isi.
    dokumen = await _dokumen_po(db, row)
    dokumen["dibuat_pada"] = datetime.now(timezone.utc)
    pdf = po_document.bangun_pdf(dokumen)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{po_document.nama_berkas(row["po_number"])}"'
            ),
            # Dokumen dibuat per permintaan dari baris DB terbaru; cache bisa
            # menyajikan PDF lama setelah status PO/approval berubah.
            "Cache-Control": "no-store",
        },
    )


@router.get("/public/purchase-orders/{po_number}/pdf")
async def unduh_pdf_publik(
    po_number: str,
    t: str = Query("", description="token tautan berumur pendek dari Joule"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """PDF PO lewat tautan bertanda tangan — tanpa token login.

    Joule hanya bisa mengirim teks dan tidak membawa token pengguna, jadi tautan
    berumur pendek adalah satu-satunya cara juri membuka dokumen yang sedang
    dibacanya. Pagar yang dijaga tetap sama dengan rute ber-token:

    * token harus menyebut nomor PO yang sama (bukan nomor lain),
    * token kedaluwarsa → 401, bukan dokumen,
    * PO harus lahir dari keputusan `approved`/`executed` → 409 bila belum,
    * isi dokumen dibangun dari baris DB saat diminta (`no-store`).
    """
    nomor = po_document.nomor_dari_token_pdf(t)
    if nomor is None or nomor != po_number:
        raise HTTPException(
            status_code=401,
            detail="tautan PDF tidak sah atau sudah kedaluwarsa",
        )

    row = (
        await db.execute(text(_SELECT_SATU), {"nomor": po_number})
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="purchase order tidak ditemukan")

    if row["decision_id"] is None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"PO {row['po_number']} tidak lahir dari keputusan — PDF hanya "
                "diterbitkan untuk PO yang sudah disetujui"
            ),
        )

    keputusan = (
        await db.execute(select(Decision).where(Decision.id == row["decision_id"]))
    ).scalar_one_or_none()
    if keputusan is None:
        raise HTTPException(status_code=404, detail="purchase order tidak ditemukan")
    if not po_document.boleh_pdf(keputusan.status):
        raise HTTPException(
            status_code=409,
            detail=(
                f"keputusan {po_document.status_keputusan_label(keputusan.status).lower()} "
                "— PDF PO diterbitkan setelah keputusan disetujui"
            ),
        )

    dokumen = await _dokumen_po(db, row)
    dokumen["dibuat_pada"] = datetime.now(timezone.utc)
    pdf = po_document.bangun_pdf(dokumen)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{po_document.nama_berkas(row["po_number"])}"'
            ),
            "Cache-Control": "no-store",
            # Tautan tidak boleh tertinggal di riwayat/proxy perantara.
            "Referrer-Policy": "no-referrer",
        },
    )
