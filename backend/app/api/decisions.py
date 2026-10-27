"""Router decisions (Task 10 Sprint 2): persist + validity endpoint.

- POST /decisions: simpan recommendation terpilih + expires_at (wajib).
  TIDAK mengeksekusi PO, TIDAK approve otomatis (Rules.md).
- GET /decisions/{id}: status + validitas terhitung (now < expires_at).
"""

from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import get_current_user
from app.api.dependencies import get_db
from app.core.commercial_cost import commercial_cost_payload
from app.core.recommendation_numbers import (
    InvalidRecommendationNumbers,
    validasi_angka_rekomendasi,
)
from app.core.scope import apply_location_scope, assert_in_scope
from app.core.window import window_start
from app.models import (
    AgentTrace,
    Commodity,
    Decision,
    DecisionEvidence,
    Location,
    PriceSignal,
    Supplier,
    User,
)
from app.services.approval_summary import build_approval_summary
from app.services.audit_facts import build_audit_facts
from app.services.decision_packet import build_decision_packet
from app.services.decision_time import decision_now

router = APIRouter()

DEFAULT_TTL_MINUTES = 30

# bgn_monitor read-only (PRD §77): tidak boleh membuat/mengubah keputusan.
# PLAN.md §13.1/§13.3 (keputusan owner 2026-10-17): membuat draf keputusan
# operasional = mengusulkan, jadi Head saja. Nutritionist tetap boleh
# memverifikasi dan memberi approval pada keputusan yang sudah ada.
DECISION_MUTATING_ROLES = ("sppg_head",)


class DecisionCreate(BaseModel):
    recommendation: dict
    ttl_minutes: int = Field(default=DEFAULT_TTL_MINUTES, ge=1, le=1440)
    # 22 Okt 2026: disamakan dengan CHECK constraint `decisions_decision_type_check`.
    # Sebelumnya API hanya menerima 3 dari 6 nilai yang sah di skema, sehingga
    # keputusan eksklusi/pemulihan pemasok dan pengadaan tidak bisa dibuat lewat
    # endpoint walau DB mengizinkannya (matriks §3: Literal vs CHECK).
    decision_type: Literal[
        "regional_balance",
        "price_anomaly",
        "safety_disruption",
        "supplier_exclusion",
        "supplier_exclusion_restoration",
        "supplier_procurement",
    ] = "regional_balance"


async def _assert_target_location_allowed(db: AsyncSession, user: User, target_location_id) -> None:
    """O-SEC-2: SPPG hanya boleh menyasar lokasi miliknya.

    bgn_monitor read-only sehingga tak pernah sampai sini via create.
    Source lokasi bebas (regional balancing lintas daerah).
    """
    if user.role == "bgn_monitor":
        raise HTTPException(status_code=403, detail="role tidak diizinkan")
    if user.location_id is None:
        raise HTTPException(
            status_code=403,
            detail="user belum terikat lokasi — tidak bisa membuat decision",
        )
    if target_location_id is None:
        raise HTTPException(
            status_code=422,
            detail="lokasi tujuan decision tidak dikenal",
        )
    if user.location_id != target_location_id:
        raise HTTPException(
            status_code=403,
            detail="decision hanya boleh menyasar lokasi milik SPPG Anda",
        )


async def _assert_decision_readable(db: AsyncSession, user: User, row: Decision) -> None:
    """Ruling 2026-10-14: SPPG hanya membaca keputusan ber-TARGET lokasinya.

    Menggantikan pengecualian ruling 2026-10-08 (S4-05 p10) yang membiarkan
    VERIFIER_ROLES membaca lintas lokasi. Alasan pencabutan ada di
    `docs/ruling-2026-10-14-scope-lokasi.md`: jalur tulis sudah dikunci ke
    lokasi sendiri sejak awal, jadi jalur baca kini simetris; matriks AND dua
    verifier tetap berlaku tetapi di dalam satu SPPG.

    bgn_monitor (read-only nasional) tidak dibatasi. Lokasi SUMBER tetap
    lintas daerah — yang dikunci hanya lokasi tujuan.
    """
    assert_in_scope(user, row.target_location_id, what="keputusan")


def _validity(expires_at: datetime) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "valid": now < expires_at,
        "seconds_remaining": max(0, int((expires_at - now).total_seconds())),
    }


def _extract(recommendation: dict):
    """Ambil field terstruktur dari snapshot rekomendasi.

    Angka TIDAK disalin apa adanya: `quantity_kg` dan `safe_delivered_cost`
    divalidasi di sini (temuan F-09/A-02, 25 Okt 2026) karena nilainya kelak
    dipakai untuk menerbitkan purchase order. Nilai bukan angka/negatif/
    mustahil ditolak sebelum menyentuh database.
    """
    cand = recommendation.get("candidate") or {}
    breakdown = recommendation.get("cost_breakdown")
    qty, sdc = validasi_angka_rekomendasi(
        cand.get("quantity_kg"),
        recommendation.get("safe_delivered_cost"),
        breakdown,
    )
    return {
        "source_location": cand.get("source_location"),
        "target_location": cand.get("destination_location"),
        "commodity": cand.get("commodity"),
        "quantity_kg": qty,
        "safe_delivered_cost": sdc,
        "cost_breakdown": breakdown,
    }


@router.post("/decisions", status_code=201)
async def create_decision(
    payload: DecisionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role not in DECISION_MUTATING_ROLES:
        raise HTTPException(status_code=403, detail="role tidak diizinkan")
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=payload.ttl_minutes)
    try:
        fields = _extract(payload.recommendation or {})
    except InvalidRecommendationNumbers as exc:
        raise HTTPException(
            status_code=422, detail=f"angka rekomendasi tidak sah: {exc}"
        ) from exc

    async def _loc_id(name):
        if not name:
            return None
        row = (await db.execute(select(Location).where(Location.name == name))).scalar_one_or_none()
        return row.id if row else None

    async def _com_id(name):
        if not name:
            return None
        row = (
            await db.execute(select(Commodity).where(Commodity.name == name))
        ).scalar_one_or_none()
        return row.id if row else None

    decision = Decision(
        id=uuid4(),
        decision_type=payload.decision_type,
        status="proposed",
        proposed_by="supervisor_agent",
        source_location_id=await _loc_id(fields["source_location"]),
        target_location_id=await _loc_id(fields["target_location"]),
        commodity_id=await _com_id(fields["commodity"]),
        quantity_kg=fields["quantity_kg"],
        safe_delivered_cost=fields["safe_delivered_cost"],
        cost_breakdown=fields["cost_breakdown"],
        expires_at=expires_at,
    )
    # O-SEC-2: scope server-side SEBELUM persist.
    await _assert_target_location_allowed(db, user, decision.target_location_id)
    db.add(decision)
    await db.flush()
    from app.services.supplier_eligibility import persist_binding

    await persist_binding(db, decision, payload.recommendation.get("candidate", {}))
    await db.commit()
    return {
        "decision_id": str(decision.id),
        "status": "proposed",
        "valid": True,
        "expires_at": expires_at.isoformat(),
        "created_at": now.isoformat(),
        "ttl_minutes": payload.ttl_minutes,
    }


@router.get("/decisions")
async def list_decisions(
    limit: int | None = Query(default=None, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    window: Literal["24h", "7d", "30d"] | None = Query(
        default=None,
        description=(
            "Jendela waktu menurut `created_at`: 24h (hari ini), 7d, 30d "
            "(bulan berjalan WIB). Tanpa parameter = seluruh riwayat."
        ),
    ),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Feed keputusan (S3-12): baris aktual, terbaru dulu, tanpa karangan.

    Ruling 2026-10-14: peran SPPG hanya melihat keputusan yang menyasar
    lokasinya; `bgn_monitor` melihat semuanya (read-only nasional).

    Paginasi (audit 21 Okt 2026, P6): `limit`/`offset` dulu diterima lalu
    diabaikan tanpa galat, dan tidak ada `total` — pemanggil tidak bisa tahu
    berapa baris yang belum tampil. Sekarang bentuknya sama dengan `/batches`:
    `count` (panjang halaman), `total` (seluruh baris pada cakupan pengguna),
    `offset`. Tanpa `limit`, perilaku lama dipertahankan (seluruh baris).
    """
    dasar = apply_location_scope(
        select(Decision).order_by(Decision.created_at.desc(), Decision.id.desc()),
        Decision.target_location_id,
        user,
    )
    # Jendela waktu (permintaan pemilik 24 Okt 2026): feed bisa dipersempit ke
    # hari ini / 7 hari / bulan berjalan. `total` ikut jendela supaya angka di
    # layar dan jumlah baris yang bisa dicapai tidak bertentangan.
    awal = window_start(window)
    if awal is not None:
        dasar = dasar.where(Decision.created_at >= awal)
    total = int(
        (
            await db.execute(select(func.count()).select_from(dasar.order_by(None).subquery()))
        ).scalar_one()
    )
    kueri = dasar.offset(offset)
    if limit is not None:
        kueri = kueri.limit(limit)
    rows = (await db.execute(kueri)).scalars().all()
    # P4: tandai keputusan yang benar-benar punya jejak 7 worker (agent_name terisi).
    # Dihitung sekali untuk semua baris (bukan satu query per keputusan) supaya
    # halaman Agent Log bisa memilih default tanpa N permintaan.
    ids = [row.id for row in rows]
    dengan_review: set = set()
    if ids:
        dengan_review = set(
            (
                await db.execute(
                    select(AgentTrace.decision_id)
                    .where(
                        AgentTrace.decision_id.in_(ids),
                        AgentTrace.agent_name.is_not(None),
                    )
                    .distinct()
                )
            )
            .scalars()
            .all()
        )

    items = []
    # Identitas pengirim (permintaan pemilik 24 Okt 2026): kartu di layar hanya
    # memperlihatkan WILAYAH, sehingga pengguna tidak tahu siapa yang mengirim —
    # pemasok atau SPPG lain. Nama pemasok diambil dari `decisions.supplier_id`;
    # untuk baris lama yang kolomnya kosong dipakai `supplier_id` di payload
    # bukti (satu-satunya jejak yang memang tersimpan). Tidak ada tebakan: kalau
    # dua-duanya kosong, `pengirim` = None dan UI menulis apa adanya.
    nama_pemasok: dict = {}
    target_nama: dict = {}
    dari_bukti: dict = {}
    jenis = {row.id: row.decision_type for row in rows}
    if ids:
        for decision_id, payload in (
            await db.execute(
                select(DecisionEvidence.decision_id, DecisionEvidence.payload)
                .where(DecisionEvidence.decision_id.in_(ids))
                .order_by(DecisionEvidence.recorded_at.desc())
            )
        ).all():
            if decision_id in dari_bukti:
                continue
            sid = (payload or {}).get("supplier_id")
            if sid:
                try:
                    # Kunci peta = UUID keputusan; nilainya juga UUID supaya
                    # pencocokan nama pemasok tidak bergantung pada string.
                    dari_bukti[decision_id] = UUID(str(sid))
                except (ValueError, TypeError):
                    continue
        kandidat: set = {row.supplier_id for row in rows if row.supplier_id}
        for sid in dari_bukti.values():
            try:
                kandidat.add(UUID(str(sid)))
            except (ValueError, TypeError):
                continue
        if kandidat:
            nama_pemasok = {
                sid: nama
                for sid, nama in (
                    await db.execute(
                        select(Supplier.id, Supplier.name).where(Supplier.id.in_(kandidat))
                    )
                ).all()
            }
        target_ids = {row.target_location_id for row in rows if row.target_location_id}
        if target_ids:
            target_nama = {
                loc_id: nama
                for loc_id, nama in (
                    await db.execute(
                        select(Location.id, Location.name).where(Location.id.in_(target_ids))
                    )
                ).all()
            }

    for row in rows:
        validity = _validity(row.expires_at)
        sid = row.supplier_id or dari_bukti.get(row.id)
        # "antar_sppg" hanya untuk jenis yang memang memindahkan stok antar
        # lokasi; selain itu None (tidak diketahui) — bukan tebakan.
        pengirim = (
            "pemasok"
            if sid
            else (
                "antar_sppg"
                if jenis.get(row.id) in ("regional_balance", "surplus_redistribution")
                else None
            )
        )
        items.append(
            {
                "decision_id": str(row.id),
                "decision_type": row.decision_type,
                "status": row.status,
                "proposed_by": row.proposed_by,
                "quantity_kg": (float(row.quantity_kg) if row.quantity_kg is not None else None),
                "safe_delivered_cost": (
                    float(row.safe_delivered_cost) if row.safe_delivered_cost is not None else None
                ),
                "expires_at": row.expires_at.isoformat(),
                "created_at": row.created_at.isoformat(),
                "valid": validity["valid"],
                "seconds_remaining": validity["seconds_remaining"],
                "rejection_reason": row.rejection_reason,
                "iteration": row.iteration or 1,
                "supersedes_id": (str(row.supersedes_id) if row.supersedes_id else None),
                "demo_case": row.demo_case,
                # Konteks verifikasi — UI pakai ini untuk menandai kartu
                # yang butuh langkah Verifikasi sebelum bisa dieksekusi.
                "verified_by": row.verified_by,
                "verifier_note": row.verifier_note,
                # True hanya bila ada baris trace worker (agent_name terisi).
                "has_agent_review": row.id in dengan_review,
                # Identitas pengirim + tujuan (24 Okt 2026). `pengirim`:
                # "pemasok" | "antar_sppg" | None (tidak diketahui) — UI tidak
                # boleh menebak, jadi nilai null ditulis apa adanya.
                "supplier_id": (str(sid) if sid else None),
                "supplier_name": (nama_pemasok.get(sid) if sid else None),
                "pengirim": pengirim,
                "target_location_name": target_nama.get(row.target_location_id),
            }
        )
    return {
        "items": items,
        "count": len(items),
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/decisions/{decision_id}/chain")
async def get_decision_chain(
    decision_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Timeline keluarga iterasi (rejection loop): v1 → v2 → v3...

    Jalur supersedes_id ditelusuri dua arah dari keputusan mana pun
    dalam keluarga; urutan akhir by iteration lalu created_at.
    """
    anchor = (
        await db.execute(select(Decision).where(Decision.id == decision_id))
    ).scalar_one_or_none()
    if anchor is None:
        raise HTTPException(status_code=404, detail="decision tidak ditemukan")
    await _assert_decision_readable(db, user, anchor)

    async def _parent_of(row: Decision):
        if not row.supersedes_id:
            return None
        return (
            await db.execute(select(Decision).where(Decision.id == row.supersedes_id))
        ).scalar_one_or_none()

    async def _children_of(row: Decision):
        return (
            (
                await db.execute(
                    select(Decision)
                    .where(Decision.supersedes_id == row.id)
                    .order_by(Decision.iteration.asc(), Decision.created_at.asc())
                )
            )
            .scalars()
            .all()
        )

    # Naik ke root, lalu turun seluruh cabang utama.
    root = anchor
    while True:
        p = await _parent_of(root)
        if p is None:
            break
        root = p
    family: list[Decision] = []
    current = root
    while current is not None:
        family.append(current)
        kids = await _children_of(current)
        current = kids[0] if kids else None
    chain = [
        {
            "decision_id": str(r.id),
            "iteration": r.iteration or 1,
            "status": r.status,
            "rejection_reason": r.rejection_reason,
            "quantity_kg": (float(r.quantity_kg) if r.quantity_kg is not None else None),
            "safe_delivered_cost": (
                float(r.safe_delivered_cost) if r.safe_delivered_cost is not None else None
            ),
            "created_at": r.created_at.isoformat(),
            "demo_case": r.demo_case,
        }
        for r in family
    ]
    return {"anchor_id": str(anchor.id), "chain": chain}


@router.get("/decisions/{decision_id}/traces")
async def get_decision_traces(
    decision_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Timeline AgentTrace aktual (S3-12): urutan langkah asli dari DB."""
    decision = (
        await db.execute(select(Decision).where(Decision.id == decision_id))
    ).scalar_one_or_none()
    if decision is None:
        raise HTTPException(status_code=404, detail="decision tidak ditemukan")
    await _assert_decision_readable(db, user, decision)
    from app.models import AgentTrace

    rows = (
        (
            await db.execute(
                select(AgentTrace)
                .where(AgentTrace.decision_id == decision_id)
                .order_by(AgentTrace.step_at.asc(), AgentTrace.id.asc())
            )
        )
        .scalars()
        .all()
    )
    steps = [
        {
            "step_name": row.step_name,
            "tool_called": row.tool_called,
            "input_summary": row.input_summary,
            "output_summary": row.output_summary,
            "duration_ms": row.duration_ms,
            "run_id": str(row.run_id) if row.run_id else None,
            "agent_name": row.agent_name,
            "confidence": row.confidence,
            "citations": row.citations,
            "step_at": row.step_at.isoformat(),
        }
        for row in rows
    ]
    return {"decision_id": str(decision_id), "steps": steps}


@router.get("/decisions/{decision_id}/approval-summary")
async def get_approval_summary(
    decision_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """S4-04: read model kanonik approval — modal UI tidak menghitung apa pun.

    Scope: SPPG hanya target lokasinya (O-SEC-2); bgn_monitor read-only
    boleh membaca semua. Tanpa mutation, tanpa call provider.
    """
    row = (
        await db.execute(select(Decision).where(Decision.id == decision_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="decision tidak ditemukan")
    await _assert_decision_readable(db, user, row)
    return await build_approval_summary(
        db,
        row,
        viewer_id=user.id,
        viewer_role=user.role,
        viewer_location_id=user.location_id,
    )


@router.get("/decisions/{decision_id}/packet")
async def get_decision_packet(
    decision_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Fase 6 butir 4: SATU paket bukti keputusan untuk semua tampilan.

    Biaya, approval, trace, dan Joule membaca bentuk ini — bukan merakit ulang
    evaluasi batch di klien. Cakupan baca sama dengan keputusan lain
    (SPPG = lokasi tujuan; bgn_monitor read-only nasional).
    """
    row = (
        await db.execute(select(Decision).where(Decision.id == decision_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="decision tidak ditemukan")
    await _assert_decision_readable(db, user, row)
    return await build_decision_packet(db, row)


@router.get("/decisions/{decision_id}/audit-facts")
async def get_audit_facts(
    decision_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Fakta audit deterministik untuk Verifier Agent (AUD-9A-03).

    Verifier agent (agent ke-8) tidak boleh menerima narasi supervisor sebagai
    sumber data. Endpoint ini adalah alat bacanya sendiri: SDC vs rincian,
    batch sumber + gerbang kesegaran, bukti keputusan, exclusion yang berlaku,
    dan blok ledger — semuanya dihitung fungsi domain yang sudah ada.

    Read-only: tidak ada mutation, tanpa panggilan model. Semua angka lahir
    dari kode; klien (termasuk agent) tidak memasok angka apa pun.
    """
    row = (
        await db.execute(select(Decision).where(Decision.id == decision_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="decision tidak ditemukan")
    await _assert_decision_readable(db, user, row)
    return await build_audit_facts(db, row)


@router.get("/decisions/{decision_id}")
async def get_decision(
    decision_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = (
        await db.execute(
            select(Decision)
            .where(Decision.id == decision_id)
            # Fase 2 MG: RELASI sesi dimuat di sini, sekali, untuk satu baris.
            # `Decision.demo_session` memakai `lazy="raise_on_sql"`; tanpa
            # selectinload, `decision_now()` jatuh ke jam dinding dan jam
            # evaluasi replay hilang dari halaman bukti.
            .options(selectinload(Decision.demo_session))
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="decision tidak ditemukan")
    await _assert_decision_readable(db, user, row)
    validity = _validity(row.expires_at)
    # Nama manusiawi + pemasok: halaman bukti tidak boleh menebak rute dari id.
    # Pengadaan pemasok punya `source_location_id = NULL` (barang datang dari
    # pemasok, bukan dari stok SPPG lain), jadi asal yang benar adalah pemasok.
    sumber = (
        await db.get(Location, row.source_location_id)
        if row.source_location_id
        else None
    )
    tujuan = (
        await db.get(Location, row.target_location_id)
        if row.target_location_id
        else None
    )
    komoditas = (
        await db.get(Commodity, row.commodity_id) if row.commodity_id else None
    )
    pemasok = (
        await db.get(Supplier, row.supplier_id) if row.supplier_id else None
    )
    # Referensi pasar untuk pembanding HARGA BAHAN (Fase 5 butir 5). Sumbernya
    # `price_signals` PIHPS — bukan biaya PO: baris ini hanya menjawab "harga
    # bahan keputusan ini mahal atau tidak", dan tidak boleh masuk deviasi
    # harga bahan bersama logistik. Tidak ada baris → `null` (bukan 0).
    referensi_pasar = None
    if row.target_location_id and row.commodity_id:
        ref = (
            await db.execute(
                select(PriceSignal.price_per_kg, PriceSignal.recorded_at)
                .where(
                    PriceSignal.source == "pihps_reference",
                    PriceSignal.location_id == row.target_location_id,
                    PriceSignal.commodity_id == row.commodity_id,
                )
                .order_by(PriceSignal.recorded_at.desc())
                .limit(1)
            )
        ).first()
        if ref is not None:
            referensi_pasar = {
                "source": "pihps_reference",
                "price_per_kg": float(ref[0]),
                "recorded_at": ref[1].isoformat(),
            }
    return {
        "decision_id": str(row.id),
        "decision_type": row.decision_type,
        "status": row.status,
        "proposed_by": row.proposed_by,
        "source_location_id": str(row.source_location_id) if row.source_location_id else None,
        "target_location_id": str(row.target_location_id) if row.target_location_id else None,
        "commodity_id": str(row.commodity_id) if row.commodity_id else None,
        # Nama (bukan id) supaya UI tidak perlu menebak; null tetap null.
        "source_location": sumber.name if sumber is not None else None,
        "target_location": tujuan.name if tujuan is not None else None,
        "commodity": komoditas.name if komoditas is not None else None,
        "supplier_id": str(row.supplier_id) if row.supplier_id else None,
        "supplier": (
            {"id": str(pemasok.id), "name": pemasok.name}
            if pemasok is not None
            else None
        ),
        "quantity_kg": float(row.quantity_kg) if row.quantity_kg is not None else None,
        "safe_delivered_cost": (
            float(row.safe_delivered_cost) if row.safe_delivered_cost is not None else None
        ),
        "cost_breakdown": row.cost_breakdown,
        # Biaya komersial: invoice (bahan+transport+handling) dan SDC analitis
        # dipisah di satu tempat. `null` = keputusan administratif tanpa biaya
        # transfer; UI wajib menulis "tidak berlaku", bukan Rp 0.
        "commercial_cost": commercial_cost_payload(
            row.quantity_kg,
            row.cost_breakdown if isinstance(row.cost_breakdown, dict) else None,
        ),
        # Pembanding harga bahan (PIHPS terakhir pada lokasi tujuan + komoditas).
        # `null` = tidak ada acuan; UI menulis "tidak tercatat", bukan Rp 0.
        "market_reference": referensi_pasar,
        "expires_at": row.expires_at.isoformat(),
        "created_at": row.created_at.isoformat(),
        "valid": validity["valid"],
        "seconds_remaining": validity["seconds_remaining"],
        "rejection_reason": row.rejection_reason,
        "iteration": row.iteration or 1,
        "supersedes_id": str(row.supersedes_id) if row.supersedes_id else None,
        "demo_case": row.demo_case,
        # Fase 2 MG: jam evaluasi yang dipakai keputusan ini + sesi pemiliknya.
        # Dibaca dari relasi yang sudah dimuat (bukan lazy-load): replay selalu
        # menjawab jangkar kanon, realtime menjawab jangkar sesi itu.
        "demo_session_id": str(row.demo_session_id) if row.demo_session_id else None,
        "session_mode": (
            row.demo_session.mode if row.demo_session is not None else None
        ),
        "evaluation_anchor": decision_now(row).isoformat(),
    }
