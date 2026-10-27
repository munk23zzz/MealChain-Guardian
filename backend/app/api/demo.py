"""Demo seeder (permintaan Roy 2026-10-07): 4 kasus siap-demo.

POST /demo/seed — idempotent (skip bila kasus sudah ada; force=true
menghapus ulang HANYA baris ber-demo_case). Kasus:
  1. rejection-loop-kuota : v1 ditolak (kuota) → v2 ditolak (harga) →
     v3 pending_approval FRESH → approve/execute live saat demo.
  2. shortage-darurat     : shortage Jakarta 780 kg, drama safety
     window ada di trace (safety_window 30 mnt) — TTL kartu panjang
     supaya tidak EXPIRED di tengah demo.
  3. supplier-janggal     : harga supplier 40% di bawah referensi →
     verifier FLAGGED (anti-fraud).
  4. gangguan-logistik    : v1 ditolak (rute Bogor banjir) → v2
     pending_approval dengan sumber alternatif Cianjur.

Catatan (Ruling 2026-10-14): Event 3 tetap bisa dipicu kepala SPPG dengan batch
di lokasi SUMBER mana pun — yang dikunci cakupan adalah LOKASI TUJUAN keputusan
(SPPG pemakai), dan itu ditentukan pemanggil (target_location_id), bukan lokasi
batch. Panel chaos sengaja TIDAK mengirim lokasi batch sebagai target.

Demo-day guard (Roy 2026-10-07): SEMUA kasus berstatus
pending_approval/verifier_flagged dijaga TTL >= 60 menit pasca-seed
(di-guard test) — tidak ada kasus mati sebelum sempat didemokan.

Semua angka konsisten dengan seed sintetis (telur, SDC Rp16,2 jt,
freshness 0,90). Tidak ada auto-approve — loop manusia tetap wajib.
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import issue_token_for_user, require_roles
from app.api.demo_session import butuh_sesi_aktif
from app.api.dependencies import get_db
from app.core.config import settings
from app.core.scope import assert_in_scope
from app.models import (
    AgentTrace,
    Batch,
    Commodity,
    Decision,
    DecisionEvidence,
    Location,
    Supplier,
    User,
)
from app.seed.timeseries import (
    DEFAULT_END,
    DEFAULT_INTERVAL_HOURS,
    DEFAULT_START,
    demo_data_status,
    generate_timeseries,
    preview_timeseries,
    purge_demo_rows,
    validate_range,
)
from app.services import agent_review_local
from app.services.agent_review_client import AgentReviewResult, review_decision
from app.services.demo_cost import hitung_biaya_demo
from app.services.demo_procurement_orchestrator import (
    run_supplier_procurement,
)
from app.services.event1_orchestrator import run_event1
from app.services.trace_persistence import persist_agent_review

router = APIRouter()

# Tujuh worker analitik + verifier, urutan tampil di panel "Bukti agent".
# Kunci harus sama dengan agent_name yang ditulis runtime AgentCore.
SWARM_AGENTS: tuple[tuple[str, str], ...] = (
    ("supply", "Pasokan"),
    ("demand", "Permintaan"),
    ("freshness", "Kesegaran"),
    ("safety", "Keamanan Pangan"),
    ("price", "Harga"),
    ("logistics", "Logistik"),
    ("evidence", "Bukti"),
    ("verifier", "Verifikasi"),
)

DEMO_CASES = (
    "rejection-loop-kuota",
    "shortage-darurat",
    "supplier-janggal",
    "gangguan-logistik",
)


class SeedRequest(BaseModel):
    force: bool = False


class Event1Request(BaseModel):
    """Permintaan menjalankan Event 1 penuh dari panel Demo Control.

    `commodity` + `target_location` memakai NAMA (bukan id) karena itu yang
    dipakai pipeline rekomendasi deterministik; lokasinya diresolusi di sini
    supaya cakupan peran bisa ditegakkan sebelum orchestrator jalan.
    """

    commodity: str
    target_location: str
    ttl_minutes: int = Field(default=30, ge=1, le=1440)


def _loc_map(locations) -> dict:
    return {loc.name: loc.id for loc in locations}


async def _target_lokasi(db: AsyncSession, user: User) -> Location:
    """Kota tujuan kasus demo = lokasi SPPG pemanggil (audit M4).

    Kasus demo harus bisa ditindaklanjuti orang yang memuatnya; sebelumnya
    target selalu Jakarta sehingga Kepala Bandung menerima kartu yang approve-nya
    pasti 403 (scope).
    """
    if user.location_id is None:
        raise HTTPException(
            status_code=422,
            detail="akun ini tidak punya lokasi SPPG — kasus demo butuh kota tujuan",
        )
    target = await db.get(Location, user.location_id)
    if target is None:
        raise HTTPException(status_code=422, detail="lokasi SPPG akun ini tidak ditemukan")
    return target


async def _commodity_id(db: AsyncSession, name: str):
    row = (
        await db.execute(select(Commodity).where(Commodity.name == name))
    ).scalar_one_or_none()
    return row.id if row else None


async def _bukti(
    db: AsyncSession,
    decision: Decision,
    jenis: str,
    muatan: dict,
    sekarang: datetime,
    konsisten: bool = True,
) -> None:
    """Tulis satu baris bukti deterministik untuk kasus demo.

    Kenapa perlu: kasus yang berakhir `rejected`/`verifier_flagged` tetap punya
    bukti — justru bukti itulah alasan penolakan/flag-nya. Sebelum ini hanya
    versi yang masih menunggu approve yang diberi bukti, sehingga 8 kartu di
    feed punya panel Decision & Evidence kosong (audit 24 Okt 2026).
    """
    kunci = uuid.uuid5(decision.id, f"bukti:{jenis}")
    if await db.get(DecisionEvidence, kunci) is not None:
        return
    db.add(
        DecisionEvidence(
            id=kunci,
            decision_id=decision.id,
            evidence_type=jenis,
            payload=muatan,
            is_consistent=konsisten,
            recorded_at=sekarang,
        )
    )


async def _ikat_sumber(db: AsyncSession, decision: Decision, sekarang: datetime) -> bool:
    """Tulis bukti `allocation_binding` untuk satu kasus demo. True bila terikat.

    Kenapa perlu: `resolve_binding` sengaja TIDAK menebak pemasok ketika satu
    pasangan (lokasi, komoditas) punya lebih dari satu pemasok. Dataset kanonik
    19 Okt 2026 membuat pasangan seperti itu biasa (Cianjur×telur = dua
    pemasok), jadi kasus demo yang dibuat tanpa bukti binding langsung tertahan
    dengan "pemasok tidak dikenal: keputusan lama perlu binding batch eksplisit"
    — kartu unggulan demo tidak bisa dieksekusi.

    Aturan pemilihan (deterministik, bukan tebakan tersembunyi): batch di lokasi
    ASAL keputusan + komoditas yang sama, masih layak pakai (`usable_until` di
    masa depan), kuantitas TERBESAR; seri dipecah oleh id terkecil. Bila tidak
    ada batch layak, TIDAK ada binding — layar lalu menampilkan alasan sebenarnya
    alih-alih pemasok karangan.
    """
    batch = (
        await db.execute(
            select(Batch)
            .where(
                Batch.location_id == decision.source_location_id,
                Batch.commodity_id == decision.commodity_id,
                Batch.usable_until.is_not(None),
                Batch.usable_until >= sekarang,
                # Sama dengan `demo_cost._batch_terikat`: batch gagal uji tidak
                # boleh menjadi sumber alokasi (hard exclusion).
                Batch.safety_status != "fail",
            )
            .order_by(Batch.quantity_kg.desc(), Batch.id.asc())
            .limit(1)
        )
    ).scalars().first()
    if batch is None:
        return False
    db.add(
        DecisionEvidence(
            # Id deterministik: menyemai ulang tidak menggandakan bukti binding.
            id=uuid.uuid5(decision.id, "bukti:allocation_binding"),
            decision_id=decision.id,
            evidence_type="human_inspection",
            payload={
                "allocation_binding": True,
                "supplier_id": str(batch.supplier_id),
                "batch_ids": [str(batch.id)],
                "demo": True,
            },
            # Dinilai dari baris `batches` yang baru dibaca: supplier, lokasi,
            # dan komoditas diambil dari batch itu sendiri.
            is_consistent=True,
            recorded_at=sekarang,
        )
    )
    return True


async def _add_trace(
    db: AsyncSession,
    decision_id,
    step_name: str,
    minutes_ago: int,
    tool: str,
    input_summary: dict,
    output_summary: dict,
):
    db.add(
        AgentTrace(
            decision_id=decision_id,
            step_name=step_name,
            tool_called=tool,
            input_summary=input_summary,
            output_summary=output_summary,
            step_at=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
        )
    )


def _decision(
    case: str,
    iteration: int,
    status: str,
    src,
    tgt,
    commodity_id,
    qty: str,
    sdc: str,
    ttl_minutes: int,
    supersedes=None,
    rejection_reason=None,
    verifier_note=None,
    verified_by=None,
    supplier_id=None,
) -> Decision:
    return Decision(
        # rejection-loop-kuota = siklus penolakan pada PENGADAAN dari pemasok,
        # bukan pemindahan stok antar-SPPG. Versi lama memberinya tipe
        # `regional_balance`, sehingga kartunya berlabel "Penyeimbangan pasokan
        # regional" padahal baris pengirimnya menyebut nama pemasok.
        decision_type=(
            "safety_disruption"
            if case in {"shortage-darurat", "gangguan-logistik"}
            else "supplier_procurement"
            if case == "rejection-loop-kuota"
            else "price_anomaly"
        ),
        status=status,
        proposed_by="supervisor_agent",
        verified_by=verified_by,
        verifier_note=verifier_note,
        rejection_reason=rejection_reason,
        iteration=iteration,
        supersedes_id=supersedes,
        demo_case=case,
        origin="demo",
        generated_at=datetime.now(timezone.utc),
        source_location_id=src,
        target_location_id=tgt,
        supplier_id=supplier_id,
        commodity_id=commodity_id,
        quantity_kg=qty,
        # Biaya diisi sesudah baris ini ada: `_lengkapi_biaya` menghitung dari
        # batch terikat + kutipan pemasok + jarak. Angka `sdc` di sini hanya
        # cadangan bila bahan hitung tidak tersedia, dan selalu ditandai.
        safe_delivered_cost=sdc,
        cost_breakdown=None,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
    )


async def _seed_demo_cases(db: AsyncSession, force: bool, target: Location) -> dict:
    """Badan `POST /demo/seed` — dipakai juga oleh `/demo/refresh`.

    Dipisah sebagai fungsi supaya "Segarkan ke hari ini" bisa menjalankan
    seeder relatif lalu MEMUAT ULANG kasus skrip (TTL baru) tanpa menduplikasi
    logika kasus di dua tempat.

    18 Okt 2026 (audit M4): kasus ditanam untuk lokasi PEMANGGIL, bukan selalu
    Jakarta. Kepala Bandung yang menekan "Muat kasus demo" harus menerima kartu
    yang bisa ia setujui; sebelumnya ia menerima empat kartu Jakarta yang
    approve-nya pasti 403 (scope). Idempotensi juga per kota: `force=true`
    hanya menghapus baris demo kota pemanggil.
    """
    existing = (
        await db.execute(
            select(Decision).where(
                Decision.demo_case.in_(DEMO_CASES),
                Decision.target_location_id == target.id,
            )
        )
    ).scalars().all()
    if existing and not force:
        return {
            "seeded": False,
            "already": len(existing),
            "target": target.name,
            "message": "Kasus demo sudah ada — pakai force=true untuk reset.",
        }
    if force and existing:
        # Hanya baris demo (demo_case NOT NULL) kota ini yang dihapus.
        ids = [d.id for d in existing]
        await db.execute(
            delete(Decision).where(
                Decision.demo_case.in_(DEMO_CASES),
                Decision.target_location_id == target.id,
            )
        )
        await db.flush()
        # D-02: blok ledger tidak punya FK ke `decisions`, jadi keputusan yang
        # sudah berblok harus "diarsipkan" dengan menaikkan generasi. Tanpa ini
        # /ledger/verify melaporkan blok yatim di generasi aktif (terukur: 12).
        from app.services.ledger_service import bump_bila_berblok

        await bump_bila_berblok(db, ids)

    locations = (await db.execute(select(Location))).scalars().all()
    loc = _loc_map(locations)
    missing = {"Bogor", "Jakarta", "Cianjur"} - set(loc)
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"lokasi seed tidak lengkap: {sorted(missing)}",
        )
    telur = await _commodity_id(db, "telur")
    if telur is None:
        raise HTTPException(status_code=422, detail="komoditas telur tidak ada")

    # `pulau` memisahkan data demo per kepulauan: pasokan segar tidak menyeberang
    # laut dalam satu hari. Sebelumnya kandidat sumber memuat "Surabaya" sebagai
    # cadangan sehingga kartu Jakarta bisa berbunyi "Ganti pasokan 300 kg ayam:
    # Surabaya → Jakarta" (663 km) — mustahil untuk ayam segar.
    pulau = {
        "Jakarta": "jawa", "Bandung": "jawa", "Bogor": "jawa", "Cianjur": "jawa",
        "Semarang": "jawa", "Yogyakarta": "jawa", "Surabaya": "jawa",
        "Medan": "sumatera", "Palembang": "sumatera", "Makassar": "sulawesi",
    }
    maks_km = 400.0

    def _km(a: Location, b: Location) -> float:
        from math import asin, cos, radians, sin, sqrt

        dlat = radians(float(b.latitude) - float(a.latitude))
        dlon = radians(float(b.longitude) - float(a.longitude))
        h = sin(dlat / 2) ** 2 + cos(radians(float(a.latitude))) * cos(
            radians(float(b.latitude))
        ) * sin(dlon / 2) ** 2
        return 2 * 6371.0 * asin(sqrt(h))

    def _nama_sumber(kandidat: tuple[str, ...]) -> str:
        """Sumber = kota lain TERDEKAT di pulau yang sama, bukan kandidat jauh.

        `kandidat` dipertahankan sebagai urutan preferensi bila masih masuk akal
        jaraknya; kalau semua terlalu jauh, pakai tetangga terdekat. Bila kota
        itu tidak punya tetangga dalam `maks_km` (Medan, Palembang, Makassar),
        sumber = kota target sendiri: stok lokal, bukan pasokan lintas pulau.
        """
        sama_pulau = [
            lok for lok in locations
            if lok.name != target.name
            and pulau.get(lok.name) == pulau.get(target.name)
        ]
        sama_pulau.sort(key=lambda lok: _km(target, lok))
        dekat = [lok.name for lok in sama_pulau if _km(target, lok) <= maks_km]
        for nama in kandidat:
            if nama in dekat:
                return nama
        if dekat:
            return dekat[0]
        return target.name

    def _sumber(kandidat: tuple[str, ...]):
        """Lokasi sumber (id) — lihat `_nama_sumber`."""
        return loc[_nama_sumber(kandidat)]

    async def _pemasok_kasus(commodity_id, lokasi: Location):
        """Pemasok untuk kasus skrip: pemasok batch kanonik kalau ada.

        Kasus "rejection-loop-kuota" adalah siklus penolakan pada PENGADAAN,
        jadi keputusannya harus menunjuk pemasok — sama seperti kartu
        `supplier_procurement` pada umumnya. Tanpa ini, ringkasan persetujuan
        menampilkan "pemasok: —" untuk keputusan yang jelas membeli barang.
        """
        from app.models import Batch, Supplier

        baris = (
            await db.execute(
                select(Batch.supplier_id)
                .join(Supplier, Supplier.id == Batch.supplier_id)
                .where(
                    Batch.location_id == lokasi.id,
                    Batch.commodity_id == commodity_id,
                    Batch.origin != "demo",
                )
                .limit(1)
            )
        ).scalars().first()
        if baris is not None:
            return baris
        return (
            await db.execute(
                select(Supplier.id)
                .where(
                    Supplier.commodity_id == commodity_id,
                    Supplier.location_id == lokasi.id,
                )
                .order_by(Supplier.name)
                .limit(1)
            )
        ).scalars().first()

    created: list[str] = []
    sekarang = datetime.now(timezone.utc)
    sup_telur_kasus = await _pemasok_kasus(telur, target)

    # ---- Kasus 1: rejection-loop-kuota (v1 ditolak → v2 ditolak → v3 fresh)
    v1 = _decision(
        "rejection-loop-kuota", 1, "rejected",
        _sumber(("Cianjur", "Bogor", "Surabaya")), target.id, telur, "600", "16206000.00",
        supplier_id=sup_telur_kasus,
        ttl_minutes=-60,  # kedaluwarsa (sudah lewat, keputusan mati)
        rejection_reason=f"Kuota SPPG {target.name} penuh minggu ini — coba skema bertahap.",
    )
    db.add(v1)
    await db.flush()
    created.append(v1.id)
    # Bukti penolakan iterasi 1: kuota SPPG penuh. Tanpa baris ini kartu
    # `rejected` tampil dengan panel bukti kosong.
    await _bukti(
        db,
        v1,
        "human_inspection",
        {
            "allocation_note": True,
            "quota_full": True,
            "rejection_reason": f"Kuota SPPG {target.name} penuh minggu ini — coba skema bertahap.",
        },
        sekarang,
    )
    await _add_trace(db, v1.id, "DETECT", 95, "demand.snapshot",
        {"location": target.name, "window": "7d"},
        {"shortage_kg": 600, "signal": "permintaan naik"})
    await _add_trace(db, v1.id, "DECIDE", 92, "supply_balance.propose",
        {"source": "Cianjur", "target": target.name, "qty": 600},
        {"sdc": 16206000, "scenario": "regional_balance"})
    await _add_trace(db, v1.id, "LEARN", 60, "rejection_loop.repropose",
        {"parent_iteration": 1},
        {
            "parent_rejection_reason": (
                f"Kuota SPPG {target.name} penuh minggu ini — coba skema bertahap."
            ),
         "learning_note": "Iterasi berikut: skema bertahap 300 kg + 300 kg."})

    v2 = _decision(
        "rejection-loop-kuota", 2, "rejected",
        _sumber(("Cianjur", "Bogor", "Surabaya")), target.id, telur, "600", "16206000.00",
        supplier_id=sup_telur_kasus,
        ttl_minutes=-30,
        supersedes=v1.id,
        rejection_reason="Harga per kg naik 12% dari referensi — negosiasi ulang dulu.",
    )
    db.add(v2)
    await db.flush()
    created.append(v2.id)
    # Bukti penolakan: harga kutipan 12% di atas referensi — alasan kartu ini
    # ditolak, jadi panel bukti TIDAK boleh kosong.
    await _bukti(
        db,
        v2,
        "market_price",
        {
            "reference": "pihps_reference",
            "harga_per_kg_ratio": 1.12,
            "rejection_reason": "Harga per kg naik 12% dari referensi — negosiasi ulang dulu.",
        },
        sekarang,
    )
    await _add_trace(db, v2.id, "LEARN", 30, "rejection_loop.repropose",
        {"parent_iteration": 2},
        {"parent_rejection_reason": "Harga per kg naik 12% dari referensi — negosiasi ulang dulu.",
         "learning_note": "Iterasi berikut: skema bertahap 2×300 kg dengan harga terkunci."})

    v3 = _decision(
        "rejection-loop-kuota", 3, "pending_approval",
        _sumber(("Cianjur", "Bogor", "Surabaya")), target.id, telur, "600", "16206000.00",
        supplier_id=sup_telur_kasus,
        ttl_minutes=480,  # demo-day guard: jangan EXPIRED saat demo (Roy)
        supersedes=v2.id,
        verified_by="verifier_agent",
        verifier_note="consistent",
    )
    db.add(v3)
    await db.flush()
    created.append(v3.id)
    # Bukti binding: tanpa ini v3 tertahan "pemasok tidak dikenal" pada dataset
    # yang punya >1 pemasok untuk pasangan (lokasi asal, komoditas).
    await _ikat_sumber(db, v3, sekarang)
    await _add_trace(db, v3.id, "PREDICT", 25, "forecast.daily",
        {"model": "chain-11-slot", "horizon_days": 7},
        {"method": "provider_forecast", "note": "skema bertahap 2×300 kg"})
    await _add_trace(db, v3.id, "DECIDE", 24, "supply_balance.propose",
        {"source": "Cianjur", "target": target.name, "qty": 600, "scheme": "2x300"},
        {"sdc": 16206000, "learning_applied": ["kuota", "harga"]})

    # ---- Kasus 2: shortage-darurat (TTL pendek — drama safety window)
    s1 = _decision(
        "shortage-darurat", 1, "pending_approval",
        _sumber(("Bogor", "Cianjur", "Surabaya")), target.id, telur, "780", "14787096.28",
        ttl_minutes=120,  # drama tetap di trace (safety window 30 mnt);
        # TTL kartu panjang supaya kasus tidak mati saat demo (Roy)
        verified_by="verifier_agent",
        verifier_note="consistent",
    )
    db.add(s1)
    await db.flush()
    created.append(s1.id)
    await _ikat_sumber(db, s1, sekarang)
    await _add_trace(db, s1.id, "DETECT", 20, "demand.snapshot",
        {"location": target.name, "shortage": 780},
        {"severity": "CRITICAL", "safety_window_minutes": 30})
    await _add_trace(db, s1.id, "PREDICT", 19, "forecast.daily",
        {"horizon_days": 1},
        {"method": "provider_forecast", "coverage": 0.94})
    await _add_trace(db, s1.id, "DECIDE", 18, "supply_balance.propose",
        {"source": "Bogor", "target": target.name, "qty": 780},
        {"sdc": 14787096.28, "urgency": "safety_window"})

    # ---- Kasus 3: supplier-janggal (verifier FLAGGED — anti-fraud)
    j1 = _decision(
        "supplier-janggal", 1, "verifier_flagged",
        _sumber(("Cianjur", "Bogor", "Surabaya")), target.id, telur, "600", "9200000.00",
        ttl_minutes=480,  # demo-day guard (Roy)
        verified_by="verifier_agent",
        verifier_note="flagged",
    )
    db.add(j1)
    await db.flush()
    created.append(j1.id)
    # Bukti tuduhan: kutipan 40% di bawah referensi PIHPS. `konsisten=False`
    # karena bukti inilah yang MEMBANTAH kewajaran harga — bukan bukti pendukung.
    await _bukti(
        db,
        j1,
        "market_price",
        {
            "reference": "pihps_reference",
            "supplier_quote_ratio": 0.60,
            "flagged_reason": "harga 40% di bawah referensi pihps",
        },
        sekarang,
        konsisten=False,
    )
    # SENGAJA tanpa binding: kasus ini menuduh HARGA sebuah kutipan pemasok
    # janggal, dan pemasok itu tidak selalu pemilik batch terbesar di lokasi
    # asal. Mengikat batch terbesar = menampilkan pemasok yang bukan subjek
    # tuduhan (tebakan), jadi lebih jujur membiarkan `resolve_binding` menolak.
    await _add_trace(db, j1.id, "DETECT", 40, "price.signal",
        {"commodity": "telur", "source": "Cianjur"},
        {"anomaly": "harga 40% di bawah referensi pihps"})
    await _add_trace(db, j1.id, "VERIFY", 38, "evidence.crosscheck",
        {"ref_source": "pihps_reference", "supplier_quote_ratio": 0.60},
        {"verdict": "FLAGGED",
         "reason": "Harga supplier janggal — 40% di bawah referensi; minta dokumen pendukung."})

    # ---- Kasus 4: gangguan-logistik (v1 ditolak → v2 rute alternatif)
    g1 = _decision(
        "gangguan-logistik", 1, "rejected",
        _sumber(("Bogor", "Cianjur", "Surabaya")), target.id, telur, "600", "16206000.00",
        ttl_minutes=-45,
        rejection_reason=f"Rute menuju {target.name} terganggu banjir — cari sumber alternatif.",
    )
    db.add(g1)
    await db.flush()
    created.append(g1.id)
    # Bukti penolakan logistik: status rute + perkiraan tunda — kartu ini ditolak
    # karena rute terganggu, jadi alasannya harus terbaca di panel bukti.
    await _bukti(
        db,
        g1,
        "gps",
        {
            "route": f"{_nama_sumber(('Bogor', 'Cianjur', 'Surabaya'))}→{target.name}",
            "disruption": "banjir",
            "eta_delay_hours": 6,
        },
        sekarang,
    )
    await _add_trace(db, g1.id, "DETECT", 70, "logistics.status",
        {"route": f"{_nama_sumber(('Bogor', 'Cianjur', 'Surabaya'))}→{target.name}"},
        {"disruption": "banjir", "eta_delay_hours": 6})
    await _add_trace(db, g1.id, "LEARN", 45, "rejection_loop.repropose",
        {"parent_iteration": 1},
        {
            "parent_rejection_reason": (
                f"Rute menuju {target.name} terganggu banjir — cari sumber alternatif."
            ),
         "learning_note": "Iterasi berikut: sumber alternatif Cianjur."})

    g2 = _decision(
        "gangguan-logistik", 2, "pending_approval",
        _sumber(("Cianjur", "Bogor", "Surabaya")), target.id, telur, "600", "16206000.00",
        supplier_id=sup_telur_kasus,
        ttl_minutes=300,  # demo-day guard (Roy)
        supersedes=g1.id,
        verified_by="verifier_agent",
        verifier_note="consistent",
    )
    db.add(g2)
    await db.flush()
    created.append(g2.id)
    await _ikat_sumber(db, g2, sekarang)
    await _add_trace(db, g2.id, "OPTIMIZE", 40, "logistics.reroute",
        {"candidates": ["Cianjur", "Sukabumi"]},
        {"selected_source": "Cianjur", "eta_ok": True})
    await _add_trace(db, g2.id, "DECIDE", 39, "supply_balance.propose",
        {"source": "Cianjur", "target": target.name, "qty": 600},
        {"sdc": 16206000, "reroute_from": "Bogor"})

    # ---- Biaya: dihitung dari data, bukan angka tulisan tangan --------------
    for decision_id in created:
        baris = await db.get(Decision, decision_id)
        if baris is None:
            continue
        terisi = await hitung_biaya_demo(db, baris, sekarang)
        if not terisi:
            # Bahan hitung tidak ada: jangan tinggalkan rincian karangan.
            baris.cost_breakdown = {
                "note": "biaya belum bisa dihitung: harga/batch/lokasi tidak tersedia"
            }
            baris.safe_delivered_cost = None

    # Selaraskan `sdc` di jejak DECIDE dengan SDC final keputusan.
    #
    # Audit data 26 Okt 2026: jejak ditulis SEBELUM `hitung_biaya_demo` jalan,
    # jadi nilai `sdc` di trace masih angka tulisan tangan (16.206.000 /
    # 14.787.096,28) sementara keputusan sudah punya SDC hasil hitung
    # (15.739.132,38 / 22.097.242,39). Dua angka biaya untuk satu keputusan
    # membuat tab Agent Log bertentangan dengan kartu rekomendasi.
    for decision_id in created:
        baris = await db.get(Decision, decision_id)
        if baris is None or baris.safe_delivered_cost is None:
            continue
        jejak = (
            await db.execute(
                select(AgentTrace).where(
                    AgentTrace.decision_id == decision_id,
                    AgentTrace.output_summary.isnot(None),
                )
            )
        ).scalars().all()
        for langkah in jejak:
            if langkah.output_summary and "sdc" in langkah.output_summary:
                langkah.output_summary = {
                    **langkah.output_summary,
                    "sdc": float(baris.safe_delivered_cost),
                }

    await db.commit()
    return {
        "seeded": True,
        "cases": len(DEMO_CASES),
        "decisions": len(created),
        "target": target.name,
        "message": f"4 kasus demo {target.name} siap — v3 kuota & v2 logistik siap approve.",
    }


@router.post("/demo/seed", status_code=200)
async def seed_demo(
    payload: SeedRequest,
    _sesi: object = Depends(butuh_sesi_aktif),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("sppg_head", "sppg_nutritionist")),
) -> dict:
    """Muat 4 kasus skrip UNTUK KOTA PEMANGGIL. Idempoten per kota; `force=true`
    hanya menghapus ulang baris demo kota itu."""
    return await _seed_demo_cases(db, payload.force, await _target_lokasi(db, user))


# --------------------------------------------------------------------------
# Data & rentang waktu (Fase 4): generator deret waktu demo.
#
# Peran: sama dengan /demo/seed (kepala SPPG) — panel Demo Control memang
# dipakai operator demo, bukan pemantau BGN.
# --------------------------------------------------------------------------


class TimeseriesRequest(BaseModel):
    start: datetime = DEFAULT_START
    end: datetime = DEFAULT_END
    interval_hours: int = DEFAULT_INTERVAL_HOURS
    force: bool = False


def _validate_or_422(start: datetime, end: datetime) -> None:
    try:
        validate_range(start, end)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/demo/preview")
async def preview_timeseries_data(
    start: datetime = Query(default=DEFAULT_START),
    end: datetime = Query(default=DEFAULT_END),
    interval_hours: int = Query(default=DEFAULT_INTERVAL_HOURS, ge=1, le=168),
    _user: User = Depends(require_roles("sppg_head", "sppg_nutritionist")),
) -> dict:
    """Pratinjau: berapa baris yang AKAN ditambah. Tidak menulis apa pun."""
    _validate_or_422(start, end)
    return await preview_timeseries(start, end, interval_hours=interval_hours)


@router.post("/demo/hari-ini", status_code=200)
async def susun_hari_ini(
    _sesi: object = Depends(butuh_sesi_aktif),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("sppg_head", "sppg_nutritionist")),
) -> dict:
    """Tulis ulang satu hari operasional kota pemanggil (idempoten).

    Dipakai sebelum demo: kartu paling atas selalu persetujuan pengiriman dari
    pemasok, ditambah jalur gagal (ditolak / lewat tenggat / ditandai
    verifikator) dan dua kiriman yang sedang berjalan.
    """
    from app.seed.hari_ini import susun

    target = await db.get(Location, user.location_id) if user.location_id else None
    if target is None:
        raise HTTPException(status_code=409, detail="akun belum terikat lokasi SPPG")
    hasil = await susun(db, nama_kota=target.name)
    await db.commit()
    return hasil


@router.post("/demo/timeseries", status_code=200)
async def generate_timeseries_data(
    payload: TimeseriesRequest,
    _sesi: object = Depends(butuh_sesi_aktif),
    _user: User = Depends(require_roles("sppg_head", "sppg_nutritionist")),
) -> dict:
    """Buat/perbarui baris demo `origin='demo'`. Idempoten.

    `force=true` menghapus dulu baris demo (bukan baris kanonik) supaya rentang
    bisa diganti bersih — pola yang sama dengan `POST /demo/seed`.
    """
    _validate_or_422(payload.start, payload.end)
    summary: dict = {"purged": None}
    if payload.force:
        summary["purged"] = await purge_demo_rows()
    summary.update(
        await generate_timeseries(
            payload.start, payload.end, interval_hours=payload.interval_hours
        )
    )
    return summary


@router.post("/demo/timeseries/purge", status_code=200)
async def purge_timeseries_data(
    _sesi: object = Depends(butuh_sesi_aktif),
    _user: User = Depends(require_roles("sppg_head", "sppg_nutritionist")),
) -> dict:
    """Hapus HANYA baris deret waktu `origin='demo'`; snapshot kanonik tidak disentuh."""
    return await purge_demo_rows()


@router.get("/demo/data-status")
async def get_data_status(
    _user: User = Depends(require_roles("sppg_head", "sppg_nutritionist")),
) -> dict:
    """Keadaan data demo SEKARANG (baca DB, bukan ingatan klien).

    Panel Demo Control memakainya untuk baris status; kalau operator membuka
    tab baru atau kontainer di-restart, UI tetap jujur.
    """
    return await demo_data_status()


#: Peringatan yang WAJIB tampil bersama tombol "Segarkan ke hari ini".
#: Bukan basa-basi: menjalankan seeder relatif `now` memang menggeser tanggal
#: snapshot kanonik, dan itu punya konsekuensi yang harus diketahui operator.
REFRESH_WARNING = (
    "Seeder relatif menjalankan ulang snapshot kanonik pada tanggal HARI INI "
    "dan memuat ulang 4 kasus skrip dengan batas waktu baru. Nilai jangkar "
    "(4.900 kg, 3 surplus : 7 shortage, Cianjur 1.400 kg) tidak berubah karena "
    "angkanya berasal dari berkas seed yang sama — yang bergeser adalah "
    "TANGGALNYA. Akibatnya tes backend yang memaku 8 Okt 12:00 tidak lagi "
    "cocok sampai snapshot dikembalikan (lihat prosedur rollback di rencana "
    "Fase 6). Baris deret waktu demo lama tetap ada sampai Anda menekan "
    "\"Bersihkan data demo\" atau membangun ulang rentangnya."
)


async def _sync_routes_aman(now: datetime) -> tuple[dict, str | None]:
    """Sinkronkan rute jalan untuk refresh; kegagalan jaringan DILAPORKAN, bukan dilempar.

    Dipisah supaya bisa diuji tanpa DB/HTTP: perilaku yang dijanjikan tombol demo
    adalah "coba sinkronkan; kalau OSRM mati, refresh tetap jalan dan alasannya
    terlihat di respons".
    """
    from app.seed.seed_data import sync_routes_after_seed

    try:
        return await sync_routes_after_seed(now), None
    except Exception as exc:  # jaringan/OSRM di luar dugaan
        return {}, f"{type(exc).__name__}: {exc}"


async def _buang_draf_usang(db: AsyncSession, sekarang: datetime, jam: int = 1) -> dict:
    """Hapus draf `proposed` usang yang tidak pernah dimajukan.

    Syaratnya konservatif: `proposed`, tanpa `demo_case`, lebih tua dari `jam`
    (bawaan 1 jam — draf yang benar-benar ditinggalkan, bukan yang baru dibuat),
    **tidak** punya approval, **tidak** punya PO, dan **tidak** punya bukti.
    Semua itu berarti tidak ada seorang pun yang pernah menyentuhnya; keputusan
    yang sudah punya jejak apa pun TIDAK disentuh.
    """
    batas = sekarang - timedelta(hours=jam)
    hasil = await db.execute(
        text(
            """
            DELETE FROM decisions d
            WHERE d.status = 'proposed'
              AND d.demo_case IS NULL
              AND d.created_at < :batas
              AND NOT EXISTS (SELECT 1 FROM approvals a WHERE a.decision_id = d.id)
              AND NOT EXISTS (
                SELECT 1 FROM sap_mock_purchase_orders p WHERE p.decision_id = d.id
              )
              AND NOT EXISTS (
                SELECT 1 FROM decision_evidence e WHERE e.decision_id = d.id
              )
            """
        ),
        {"batas": batas},
    )
    return {"draf_usang_dihapus": getattr(hasil, "rowcount", 0) or 0}


@router.post("/demo/refresh", status_code=200)
async def refresh_to_today(
    _sesi: object = Depends(butuh_sesi_aktif),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("sppg_head", "sppg_nutritionist")),
) -> dict:
    """Tombol hari demo: seeder relatif `now` + muat ulang 4 kasus skrip.

    Akun demo TIDAK disentuh (password tidak direset) dan baris deret waktu
    demo TIDAK dihapus — keduanya punya tombol sendiri di panel.
    """
    from app.seed.demo_activity import (
        seed_demo_activity,
        seed_demo_completed_decisions,
        seed_demo_daily_prices,
    )
    from app.seed.demo_kpi_riwayat import geser_aksi_ke_riwayat
    from app.seed.seed_data import load_seed

    now = datetime.now(timezone.utc)
    # Snapshot kanonik HANYA dimuat kalau belum ada. Memuatnya ulang dengan
    # `now` hari ini memberi id baru (id diturunkan dari tanggal acuan) sementara
    # baris acuan lama tetap ada: 100 price_signals yatim, 40 pihps_reference
    # ganda, dan batch yang dipakai tes lain ikut terhapus bila dibersihkan
    # paksa. Yang bergerak ke hari ini cukup baris DEMO (kiriman, kasus skrip,
    # keputusan selesai, harga harian, seed hari-ini).
    kanonik = (
        await db.execute(
            select(func.count()).select_from(Batch).where(Batch.origin != "demo")
        )
    ).scalar() or 0
    rows = await load_seed(now) if not kanonik else {"dilewati": "snapshot kanonik sudah ada"}
    # Kiriman demo di SELURUH lokasi (origin='demo'): membuat peta, papan kiriman,
    # dan pemilih kiriman punya bahan nyata untuk dicoba di semua peran. Idempoten,
    # jadi menekan tombol dua kali tidak menggandakan kiriman.
    aktivitas = await seed_demo_activity(db, now)
    # Keputusan selesai + limbah HARI INI: tanpa ini empat kartu KPI menjawab
    # "belum ada data" pada periode hari-ini (seed kanonik berhenti di 8 Okt).
    selesai = await seed_demo_completed_decisions(db, now)
    # Harga hari ini: metrik "Procurement Price Deviation" butuh acuan PIHPS yang
    # LEBIH DULU daripada kutipan pemasok, dan keduanya bertanggal hari ini.
    # Tanpa ini kartu itu kosong setiap hari baru walau datanya ada di hari lama.
    harga = await seed_demo_daily_prices(db, now)
    # Rute jalan ikut disinkronkan: seeder memindahkan tanggal kiriman ke hari
    # ini, dan pasangan pemasok→tujuan yang BELUM ada di cache hanya punya garis
    # kalau disinkronkan di sini. Tanpa langkah ini tombol "Segarkan ke hari ini"
    # menghasilkan kiriman tanpa geometri ("belum disinkronkan") — peta kosong
    # padahal datanya ada. Gagal jaringan TIDAK menggagalkan refresh: laporannya
    # dibawa di respons supaya terlihat, bukan disembunyikan.
    routes, route_error = await _sync_routes_aman(now)
    target = await _target_lokasi(db, user)
    cases = await _seed_demo_cases(db, force=True, target=target)
    # KPI 24 jam harus mulai dari "belum ada aksi hari ini" (permintaan pemilik
    # 23 Okt 2026). Tanpa langkah ini, "Segarkan ke hari ini" kembali mengisi
    # empat metrik berbasis aksi dan panel kehilangan momen realtime-nya.
    kpi_riwayat = await geser_aksi_ke_riwayat(db, now)
    # Lihat `app/seed/demo_kasus_bukti.py`: satu kasus tinggal di jendela 24 jam
    # dengan dua jenis bukti, menunggu approval operator.
    from app.seed.demo_kasus_bukti import semai_kasus_bukti_hari_ini

    kasus_bukti = await semai_kasus_bukti_hari_ini(db, now)
    # Satu hari operasional Jakarta (24 Okt 2026). Tanpa langkah ini tombol
    # "Siapkan data demo" meninggalkan feed 24 jam berisi SATU kartu: kasus
    # skrip dihapus-lalu-dibuat-ulang dan baris aksi digeser keluar jendela,
    # sehingga komposisi "menunggu / berjalan / selesai" hilang. Seed hari-ini
    # menulisnya ulang secara deterministik supaya hasil klik selalu sama.
    from app.seed.hari_ini import susun as susun_hari_ini

    hari_ini = await susun_hari_ini(db, now=now, nama_kota=target.name)
    # Kiriman kembar: beberapa penyemai memakai rumus waktu sama dengan skema
    # id berbeda, sehingga satu kiriman muncul dua kali (dua truk identik).
    from app.seed.rapikan import rapikan_batch_ganda

    kembar = await rapikan_batch_ganda(db)
    # Draf usulan yang tidak pernah dimajukan menumpuk setiap kali ada yang
    # memanggil `POST /decisions` / `/balance/recommend`: 58 baris `proposed`
    # semuanya lewat tenggat, dan lonceng top bar berbunyi "47 lewat tenggat"
    # (audit 24 Okt 2026). Draf bukan riwayat keputusan — tidak punya approval,
    # PO, maupun bukti — jadi dibuang saat hari demo disiapkan.
    draf = await _buang_draf_usang(db, now)
    await db.commit()
    return {
        "reference_time": now.isoformat(),
        "rows": rows,
        "cases": cases,
        "activity": {**aktivitas, **selesai, **harga},
        "kpi_riwayat": kpi_riwayat,
        "kasus_bukti": kasus_bukti,
        "hari_ini": hari_ini,
        "batch_kembar_dihapus": kembar,
        "draf": draf,
        "routes": routes,
        "route_error": route_error,
        "warning": REFRESH_WARNING,
        "message": "Snapshot kanonik disegarkan ke hari ini; 4 kasus skrip dimuat ulang.",
    }


# ---------------------------------------------------------------------------
# Event 1 penuh (DETECT → … → DECIDE → SUPERVISE) dari panel Demo Control.
#
# Kenapa di sini: sebelum endpoint ini ada, `run_event1` hanya dipanggil
# berkas tes, sehingga langkah SUPERVISE (narasi supervisor) tidak pernah
# muncul di `agent_traces` pada aplikasi yang dilihat juri. Tombol ini
# menjalankan jalur NYATA (provider apa adanya, tanpa memalsukan hasil) dan
# menulis keputusan + jejaknya lewat kode yang sudah tersertifikasi
# (`tests/test_event1_supervisor_flow.py`).
#
# Batas jujur: endpoint ini TIDAK meng-approve/mengeksekusi apa pun — keputusan
# lahir berstatus `proposed` dan tetap menunggu loop approval manusia.
# ---------------------------------------------------------------------------


@router.post("/demo/event1", status_code=201)
async def run_demo_event1(
    payload: Event1Request,
    _sesi: object = Depends(butuh_sesi_aktif),
    db: AsyncSession = Depends(get_db),
    # Event 1 penuh membuat keputusan operasional → usul, jadi Head saja
    # (PLAN.md §13.3, keputusan owner 2026-10-17).
    user: User = Depends(require_roles("sppg_head")),
) -> dict:
    """Jalankan Event 1 penuh untuk satu komoditas + satu lokasi tujuan.

    Cakupan lokasi ditegakkan atas lokasi TUJUAN (Ruling 2026-10-14): kepala
    SPPG hanya boleh menjalankan Event 1 untuk SPPG-nya sendiri; `bgn_monitor`
    ditolak guard peran (read-only).

    Kegagalan karena tidak ada kandidat eligible dijawab **409**, bukan 500 —
    itu keadaan domain, bukan kerusakan server.
    """
    location = (
        await db.execute(select(Location).where(Location.name == payload.target_location))
    ).scalar_one_or_none()
    if location is None:
        raise HTTPException(
            status_code=404,
            detail=f"lokasi tujuan tidak dikenal: {payload.target_location}",
        )
    assert_in_scope(user, location.id, what="lokasi tujuan")

    try:
        # `run_event1` sinkron (membuka sesi + loop-nya sendiri) → dijalankan di
        # worker thread supaya tidak menabrak event loop request.
        outcome = await run_in_threadpool(
            run_event1,
            payload.commodity,
            payload.target_location,
            ttl_minutes=payload.ttl_minutes,
        )
    except ValueError as exc:
        # Termasuk "tidak ada kandidat eligible untuk Event 1": keadaan data,
        # bukan kerusakan server.
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    outcome["agent_review"] = await _jalankan_agent_review(db, outcome, user=user)
    return outcome


async def _jalankan_agent_review(
    db: AsyncSession, outcome: dict, *, user: User | None = None
) -> dict:
    """Review opsional setelah decision dibuat; kegagalan tidak membatalkan 201.

    Dua jalur yang benar-benar berbeda, dipilih `AGENT_REVIEW_MODE`:

    - `local`  → orkestrator IN-PROSES dari repo ini (`agent/orchestrator.py`).
      Dipakai saat runtime AgentCore yang ter-deploy bisa tertinggal dari repo;
      kode yang mengaudit adalah kode yang diuji di sini.
    - lainnya (`advisory`/`predecision`/`agentcore`/kosong) → runtime AgentCore
      lewat `AGENTCORE_RUNTIME_ARN`, yaitu perilaku lama (default aman).
    """
    disabled = {"status": "disabled", "run_id": None}
    if not settings.multi_agent_review:
        return disabled

    decision_id = outcome.get("decision_id")
    if not isinstance(decision_id, str) or not decision_id.strip():
        return {"status": "failed", "run_id": None}

    jalur = agent_review_local.transport(settings.agent_review_mode)
    if jalur == "local":
        # Review lokal membaca API dengan identitas PEMANGGIL (bukan token
        # layanan berumur panjang): cakupan peran tetap ditegakkan endpoint.
        if user is None:
            result = AgentReviewResult(
                status="unavailable",
                error="user pemanggil tidak tersedia untuk token review lokal",
            )
        else:
            try:
                token = issue_token_for_user(user)
            except Exception as exc:  # noqa: BLE001 - JWT_SECRET hilang dsb.
                result = AgentReviewResult(
                    status="unavailable",
                    error=f"token review lokal gagal dibuat: {type(exc).__name__}",
                )
            else:
                # Model berlatensi detik (verifier memanggilnya sekali); beri
                # anggaran lebih lega daripada jalur runtime, tetap berbatas.
                anggaran = float(
                    min(max(settings.agent_review_timeout_seconds, 30), 120)
                )
                result = await run_in_threadpool(
                    agent_review_local.review_decision_local,
                    decision_id,
                    token=token,
                    mode=settings.agent_review_mode,
                    timeout_seconds=anggaran,
                )
    else:
        timeout = float(min(max(settings.agent_review_timeout_seconds, 1), 45))
        try:
            result = await run_in_threadpool(
                review_decision, decision_id, timeout_seconds=timeout
            )
        except Exception:
            result = AgentReviewResult(status="failed", error="review client gagal")

    if not isinstance(result, AgentReviewResult):
        result = AgentReviewResult(status="failed", error="review client tidak valid")

    if result.completed:
        # P5: simpan 7 baris worker + SUPERVISE agar Agent Log bisa menampilkan
        # satu putaran review. Bila payload tidak lengkap, catat kegagalan —
        # jangan menulis 7 baris yang tidak berasal dari runtime.
        await _catat_review_sukses(db, decision_id, result)
    else:
        # Kegagalan/ timeout dicatat jujur sebagai SUPERVISE; tidak ada 7 row palsu.
        await _catat_review_gagal(db, decision_id, result)

    return {
        "status": result.status,
        "run_id": result.run_id,
    }


async def _catat_review_sukses(
    db: AsyncSession, decision_id: str, result: AgentReviewResult
) -> None:
    """Persist 9 baris review (7 worker + verifier + SUPERVISE) atau 8 dari runtime lama.

    Kegagalan penyimpanan tidak membatalkan Event 1.
    """
    rows = (result.payload or {}).get("trace_rows")
    if not isinstance(rows, list) or len(rows) not in (8, 9):
        await _catat_review_gagal(
            db,
            decision_id,
            AgentReviewResult(
                status="failed",
                run_id=result.run_id,
                error="payload trace review tidak lengkap (wajib 9 baris)",
            ),
        )
        return
    try:
        await persist_agent_review(
            db, decision_id=decision_id, trace_rows=rows
        )
        await db.commit()
    except Exception as exc:
        try:
            await db.rollback()
        except Exception:
            pass
        await _catat_review_gagal(
            db,
            decision_id,
            AgentReviewResult(
                status="failed",
                run_id=result.run_id,
                error=f"trace review gagal disimpan: {type(exc).__name__}",
            ),
        )


async def _catat_review_gagal(
    db: AsyncSession, decision_id: str, result: AgentReviewResult
) -> None:
    """Tulis satu baris SUPERVISE best-effort; decision tetap ada."""
    try:
        import uuid

        decision_uuid = uuid.UUID(decision_id)
        if await db.get(Decision, decision_uuid) is None:
            return
        db.add(
            AgentTrace(
                decision_id=decision_uuid,
                step_name="SUPERVISE",
                tool_called="agent.review",
                input_summary={"task": "review_decision"},
                output_summary={
                    "status": result.status,
                    "run_id": result.run_id,
                    "error": result.error,
                },
            )
        )
        await db.commit()
    except Exception:
        try:
            await db.rollback()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Demo Control sederhana (keputusan Roy 2026-10-19).
#
# Tab Demo Control dipakai untuk MEMBUKTIKAN agent berjalan, bukan untuk memilih
# skenario. Karena itu dua endpoint di bawah ini sengaja sempit:
#   POST /demo/agent/run      satu klik, tanpa payload wajib: komoditas `beras`
#                             dan lokasi SPPG milik akun sendiri (bukan lokasi
#                             yang diketik klien — cakupan peran jadi mustahil
#                             dilanggar dari UI).
#   GET  /demo/agent/last-run bukti yang dibaca dari DB: keputusan terakhir dari
#                             putaran pipeline agent (punya langkah PREDICT /
#                             OPTIMIZE / SUPERVISE tanpa agent_name — bukan
#                             baris template yang hanya menulis DETECT/DECIDE),
#                             seluruh langkahnya, provider yang benar-benar
#                             menjawab, dan status review 7-worker kalau ada.
#
# Tidak ada angka karangan: setiap field berasal dari baris DB. Bila belum ada
# jejak agent sama sekali, jawabannya `found: false` — bukan potret kosong yang
# dibuat-buat.
# ---------------------------------------------------------------------------

#: Komoditas bawaan tombol "Jalankan agent".
DEFAULT_AGENT_COMMODITY = "beras"

#: Urutan langkah pipeline. `step_at` TIDAK bisa dipakai mengurutkan: seluruh
#: langkah satu putaran ditulis dalam satu transaksi, dan Postgres `now()`
#: mengembalikan waktu MULAI transaksi — jadi semua barisnya ber-`step_at` sama.
STEP_ORDER = (
    "DETECT",
    "VERIFY",
    "TRACE",
    "PREDICT",
    "OPTIMIZE",
    "DECIDE",
    "SUPERVISE",
    "ACT",
    "LEARN",
)


class AgentRunRequest(BaseModel):
    """Payload opsional; UI sederhana cukup memanggil tanpa body."""

    commodity: str = DEFAULT_AGENT_COMMODITY
    ttl_minutes: int = Field(default=30, ge=1, le=1440)


async def _lokasi_akun(db: AsyncSession, user: User) -> Location:
    """Lokasi SPPG milik akun pemanggil — satu-satunya target yang sah."""
    if not user.location_id:
        raise HTTPException(
            status_code=400,
            detail="akun ini tidak terikat lokasi SPPG; jalankan agent dari akun kepala SPPG",
        )
    lokasi = await db.get(Location, user.location_id)
    if lokasi is None:
        raise HTTPException(
            status_code=400, detail="lokasi akun tidak ditemukan di database"
        )
    return lokasi


@router.post("/demo/agent/run", status_code=201)
async def run_demo_agent(
    payload: AgentRunRequest | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("sppg_head")),
) -> dict:
    """Jalankan pipeline agent penuh untuk lokasi akun sendiri (DETECT → SUPERVISE).

    Objek penilaian = pemasok yang SUDAH memasok SPPG akun ini: stok batch,
    penawaran harga untuk SPPG itu, jarak pemasok→SPPG, reliabilitas, dan
    status pengecualian. Tidak ada pemasok dari kota lain yang ditebak.

    Batas jujur yang sama dengan `/demo/event1`: tidak ada approve/execute.
    Keputusan lahir `proposed` dan tetap menunggu loop approval manusia.
    """
    isi = payload or AgentRunRequest()
    lokasi = await _lokasi_akun(db, user)
    try:
        # Sejak 2026-10-19 panel ini menilai PEMASOK yang memasok SPPG akun
        # sendiri (bukan surplus SPPG lain): lihat supplier_procurement.py.
        outcome = await run_in_threadpool(
            run_supplier_procurement,
            isi.commodity,
            lokasi.name,
            ttl_minutes=isi.ttl_minutes,
        )
    except ValueError as exc:
        # Tidak ada kandidat eligible = keadaan data, bukan kerusakan server.
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    outcome["commodity"] = isi.commodity
    outcome["target_location"] = lokasi.name
    outcome["agent_review"] = await _jalankan_agent_review(db, outcome, user=user)
    return outcome


def _urut_langkah(trace: AgentTrace) -> tuple[int, str]:
    posisi = (
        STEP_ORDER.index(trace.step_name)
        if trace.step_name in STEP_ORDER
        else len(STEP_ORDER)
    )
    return (posisi, str(trace.id))


def _baru(kandidat: AgentTrace, sekarang: AgentTrace | None) -> bool:
    """Baris mana yang dipakai bila satu agen punya beberapa baris."""
    if sekarang is None:
        return True
    lama = getattr(sekarang, "step_at", None)
    baru = getattr(kandidat, "step_at", None)
    if baru is None:
        return lama is None
    return lama is None or baru >= lama


def _peta_agen(
    langkah: list[AgentTrace], root: str | None
) -> dict[str, AgentTrace]:
    """`agent_name → baris trace` milik satu run (`root=None` = semua baris)."""
    peta: dict[str, AgentTrace] = {}
    for t in langkah:
        nama = (t.agent_name or "").strip().lower()
        if not nama:
            continue
        induk = str(t.parent_run_id or "")
        # Verifier adalah RUN ANAK (AUD-9A-03): barisnya boleh punya run_id
        # sendiri asalkan `parent_run_id` menunjuk run yang dipetakan.
        if root is not None and str(t.run_id or "") != root and induk != root:
            continue
        if _baru(t, peta.get(nama)):
            peta[nama] = t
    return peta


def _baris_review(
    langkah: list[AgentTrace],
) -> tuple[dict[str, AgentTrace], str | None]:
    """Peta baris review putaran ini + run id putaran yang tercatat.

    Satu putaran idealnya satu `run_id`, tetapi runtime yang menjalankan tiap
    agen sebagai invokasi sendiri menulis `run_id` BERBEDA per baris; hanya baris
    ringkasan SUPERVISE yang membawa id putaran. Versi lama memetakan hanya baris
    dengan `run_id == id putaran`, sehingga seluruh kartu agen tampak "missing"
    padahal barisnya tersimpan (regresi 27 Okt 2026).

    Aturan sekarang: coba id putaran dulu, lalu SEMUA id yang muncul, lalu
    seluruh baris keputusan ini — dan pilih peta dengan agen TERBANYAK. Dengan
    begitu run anak (verifier) atau run per-agen tidak lagi memotong pemetaan.
    """
    run_review = next(
        (
            t.run_id
            for t in langkah
            if t.step_name == "SUPERVISE" and t.agent_name == "supervisor" and t.run_id
        ),
        None,
    )
    if run_review is None:
        # Runtime lama: ringkasan SUPERVISE tanpa agent_name, run id di payload.
        run_review = next(
            (
                (t.output_summary or {}).get("run_id")
                for t in langkah
                if t.step_name == "SUPERVISE" and t.run_id
            ),
            None,
        )
    if run_review is None:
        ids = [
            t.run_id
            for t in langkah
            if t.agent_name and t.run_id and not t.parent_run_id
        ]
        run_review = max(set(ids), key=ids.count) if ids else None

    terbaik = _peta_agen(langkah, str(run_review)) if run_review is not None else {}
    for root in dict.fromkeys(
        str(t.run_id) for t in langkah if t.agent_name and t.run_id
    ):
        calon = _peta_agen(langkah, root)
        if len(calon) > len(terbaik):
            terbaik = calon
    if len(terbaik) < len(SWARM_AGENTS):
        semua = _peta_agen(langkah, None)
        if len(semua) > len(terbaik):
            terbaik = semua
    return terbaik, (str(run_review) if run_review is not None else None)


@router.get("/demo/agent/commodities")
async def list_agent_commodities(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles("sppg_head", "sppg_nutritionist")),
) -> dict:
    """Pilihan dropdown komoditas — nama yang ADA di database, bukan daftar karangan.

    Panel demo tidak boleh menawarkan komoditas yang tidak punya data: memilihnya
    hanya akan berakhir `409 tidak ada kandidat eligible`.
    """
    nama = (
        (await db.execute(select(Commodity.name).order_by(Commodity.name)))
        .scalars()
        .all()
    )
    return {"commodities": list(nama)}


@router.get("/demo/agent/last-run")
async def get_last_agent_run(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles("sppg_head", "sppg_nutritionist")),
) -> dict:
    """Bukti putaran agent terakhir, dibaca ulang dari DB (tahan reload halaman)."""
    kosong = {
        "found": False,
        "decision_id": None,
        "steps": [],
        "agents": [],
        "agents_run_id": None,
        "supervisor": {
            "status": "missing",
            "provider": None,
            "fallback_used": False,
            "summary": None,
        },
        "agent_review": {"status": "missing", "error": None, "run_id": None},
        "mode": None,
        "supplier": None,
        "supply_gap": None,
    }

    # Putaran agent yang sesungguhnya = keputusan dengan JEJAK PIPELINE LENGKAP:
    # minimal DETECT + DECIDE dan satu langkah prediksi/optimasi/supervisi, semuanya
    # tanpa `agent_name` (baris review 7 worker memakai nama agen).
    #
    # Tiga koreksi dari gerbang 21 Okt 2026 — sebelumnya endpoint hanya mencari
    # `DETECT` terakhir dan melaporkan baris hasil semai sebagai "bukti putaran
    # agent" (statusnya bukan `proposed`, `supply_gap.gap_kg` kosong):
    #   (a) `DETECT` saja bukan penanda putaran: template menulis DETECT/DECIDE/ACT
    #       untuk keputusan contohnya, dan jalur Event 3 menulis DETECT+OPTIMIZE;
    #   (b) salinan 4 kasus skrip (`demo_case` terisi) juga memuat DETECT/PREDICT/
    #       DECIDE, jadi kasus skrip dikecualikan lewat `demo_case IS NULL`;
    #   (c) urutan wajib deterministik: keputusan terbaru menang, bukan "baris
    #       mana pun yang step_at-nya sama" (satu putaran menulis semua langkahnya
    #       dalam satu transaksi sehingga `step_at` baris-barisnya identik).
    kandidat = (
        (
            await db.execute(
                select(AgentTrace.decision_id)
                .join(Decision, Decision.id == AgentTrace.decision_id)
                .where(
                    AgentTrace.step_name == "DETECT",
                    AgentTrace.agent_name.is_(None),
                    Decision.demo_case.is_(None),
                )
                .order_by(Decision.created_at.desc(), AgentTrace.step_at.desc())
                .limit(25)
            )
        )
        .scalars()
        .all()
    )
    terakhir = None
    for calon in dict.fromkeys(kandidat):
        nama_langkah = set(
            (
                await db.execute(
                    select(AgentTrace.step_name).where(
                        AgentTrace.decision_id == calon,
                        AgentTrace.agent_name.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        if {"DETECT", "DECIDE"} <= nama_langkah and nama_langkah & {
            "PREDICT",
            "OPTIMIZE",
            "SUPERVISE",
        }:
            terakhir = calon
            break
    if terakhir is None:
        return kosong

    keputusan = await db.get(Decision, terakhir)
    if keputusan is None:
        return kosong

    traces = (
        (
            await db.execute(
                select(AgentTrace).where(AgentTrace.decision_id == terakhir)
            )
        )
        .scalars()
        .all()
    )
    langkah = sorted(traces, key=_urut_langkah)

    # Tujuh worker review (advisory). Kartu di panel Demo Control selalu
    # menampilkan ketujuhnya; status per agen dibaca dari baris trace putaran
    # review yang benar-benar tersimpan (bukan ditebak dari langkah pipeline).
    baris_agen, run_review = _baris_review(langkah)
    agen = []
    for kunci, label in SWARM_AGENTS:
        baris = baris_agen.get(kunci)
        keluaran = dict(baris.output_summary or {}) if baris is not None else {}
        peringatan = keluaran.get("warnings")
        agen.append(
            {
                "key": kunci,
                "label": label,
                "status": (keluaran.get("status") or ("ok" if baris else "missing")),
                # Verdict audit (khusus kartu verifier): `consistent|flagged|unavailable`.
                # Kartu UI memakai ini untuk label DEFINITIF (Ditinjau/Diblokir),
                # bukan "Terbatas" yang juga dipakai keadaan "model tidak ada".
                "verdict": keluaran.get("audit_verdict"),
                "duration_ms": baris.duration_ms if baris is not None else None,
                "warnings": (
                    len([p for p in peringatan if isinstance(p, str)])
                    if isinstance(peringatan, list)
                    else None
                ),
                "summary": keluaran.get("summary"),
            }
        )

    narasi = next(
        (
            t
            for t in langkah
            if t.step_name == "SUPERVISE" and t.tool_called == "supervisor.narration"
        ),
        None,
    )
    review = next(
        (
            t
            for t in langkah
            if t.step_name == "SUPERVISE"
            and str(t.tool_called or "").startswith("agent.review")
        ),
        None,
    )
    if review is None:
        # Runtime yang menulis ringkasan review sebagai baris supervisor tanpa
        # `tool_called` khusus: statusnya tetap fakta DB, bukan "missing".
        review = next(
            (
                t
                for t in langkah
                if t.step_name == "SUPERVISE"
                and (t.agent_name or "").strip().lower() == "supervisor"
            ),
            None,
        )
    keluaran_narasi = dict(narasi.output_summary or {}) if narasi is not None else {}
    keluaran_review = dict(review.output_summary or {}) if review is not None else {}

    komoditas = (
        await db.get(Commodity, keputusan.commodity_id)
        if keputusan.commodity_id
        else None
    )
    sumber = (
        await db.get(Location, keputusan.source_location_id)
        if keputusan.source_location_id
        else None
    )
    tujuan = (
        await db.get(Location, keputusan.target_location_id)
        if keputusan.target_location_id
        else None
    )

    pemasok = (
        await db.get(Supplier, keputusan.supplier_id)
        if keputusan.supplier_id
        else None
    )
    # Baris review worker memakai nama langkah yang sama (agent.supply dst.),
    # jadi bukti pipeline harus diambil dari baris TANPA agent_name.
    optimasi = next(
        (t for t in langkah if t.step_name == "OPTIMIZE" and t.agent_name is None),
        None,
    )
    keluaran_optimasi = dict(optimasi.output_summary or {}) if optimasi else {}
    deteksi = next(
        (t for t in langkah if t.step_name == "DETECT" and t.agent_name is None),
        None,
    )
    keluaran_deteksi = dict(deteksi.output_summary or {}) if deteksi else {}

    return {
        "found": True,
        "decision_id": str(keputusan.id),
        "status": keputusan.status,
        "decision_type": keputusan.decision_type,
        "proposed_by": keputusan.proposed_by,
        "created_at": (
            keputusan.created_at.isoformat() if keputusan.created_at else None
        ),
        "expires_at": (
            keputusan.expires_at.isoformat() if keputusan.expires_at else None
        ),
        "quantity_kg": (
            str(keputusan.quantity_kg) if keputusan.quantity_kg is not None else None
        ),
        "commodity": komoditas.name if komoditas is not None else None,
        "mode": (
            "supplier_procurement"
            if keputusan.decision_type == "supplier_procurement"
            else "regional_balance"
        ),
        "source_location": sumber.name if sumber is not None else None,
        "target_location": tujuan.name if tujuan is not None else None,
        # Bukti pengadaan: pemasok yang DINILAI (bukan tebakan dari lokasi),
        # jarak pemasok→SPPG, harga penawaran, dan kekurangan yang dipenuhi.
        "supplier": {
            "supplier_id": str(pemasok.id) if pemasok is not None else None,
            "name": pemasok.name if pemasok is not None else None,
            "leg_km": keluaran_optimasi.get("leg_km"),
            "available_kg": keluaran_optimasi.get("available_kg"),
            "quote_price_per_kg": keluaran_optimasi.get("quote_price_per_kg"),
            "reliability": keluaran_optimasi.get("reliability"),
            "capacity_kg_per_week": keluaran_optimasi.get("capacity_kg_per_week"),
            "rank": keluaran_optimasi.get("rank"),
            "candidates_total": keluaran_optimasi.get("candidates_total"),
        },
        "supply_gap": {
            "supply_kg": keluaran_deteksi.get("supply_kg"),
            "demand_kg": keluaran_deteksi.get("demand_kg"),
            "gap_kg": keluaran_deteksi.get("gap_kg"),
            "suppliers_total": keluaran_deteksi.get("suppliers_total"),
            "suppliers_eligible": keluaran_deteksi.get("suppliers_eligible"),
        },
        "verifier_note": keputusan.verifier_note,
        "steps": [
            {
                "step_name": t.step_name,
                "tool_called": t.tool_called,
                "duration_ms": t.duration_ms,
            }
            for t in langkah
        ],
        "agents": agen,
        "agents_run_id": run_review,
        "supervisor": {
            "status": keluaran_narasi.get(
                "status", "missing" if narasi is None else "unknown"
            ),
            "provider": keluaran_narasi.get("provider"),
            "fallback_used": bool(keluaran_narasi.get("fallback_used")),
            "summary": keluaran_narasi.get("summary"),
        },
        "agent_review": {
            "status": keluaran_review.get("status", "missing"),
            "error": keluaran_review.get("error"),
            # Ringkasan review bisa tidak membawa `run_id` di payload; kolom
            # `run_id` barisnya tetap fakta yang sama.
            "run_id": keluaran_review.get("run_id")
            or (getattr(review, "run_id", None) if review is not None else None),
        },
    }
