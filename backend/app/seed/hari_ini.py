"""Satu hari operasional SPPG Jakarta — bahan demo "1 hari".

Kenapa modul ini ada (permintaan pemilik 24 Okt 2026): jendela 24 jam di layar
hanya berisi SATU rekomendasi dan KPI 3/7. Yang dibutuhkan untuk demo bukan
angka tempelan, melainkan satu hari yang utuh: ada yang menunggu persetujuan,
ada yang sedang dikirim, ada yang sudah selesai — plus jalur gagal (ditolak,
lewat tenggat, ditandai verifikator) supaya pertanyaan "kalau ditolak bagaimana"
punya jawaban di layar.

Aturan yang dipegang:
- Semua baris ditulis lewat model/tabel produksi; angka KPI ditulis oleh
  `app.services.settlement` (bukan dihitung tangan di sini).
- Idempoten: id deterministik per kunci, jalan ulang menghapus miliknya sendiri.
- Jakarta saja; kota lain tidak disentuh supaya angka yang sudah dihafal stabil.
- Kartu paling atas (paling baru) = persetujuan pengiriman dari PEMASOK, dengan
  nama pemasok terisi — persis yang mau didemokan pemilik.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AgentTrace,
    Approval,
    Batch,
    BatchReceipt,
    Commodity,
    Decision,
    DecisionEvidence,
    DeliveryEvent,
    DisposalEvent,
    Location,
    PriceSignal,
    RoadRoute,
    SapMockPurchaseOrder,
    Supplier,
    SupplierExclusion,
    User,
)
from app.services import settlement

KUNCI = "hari-ini"
_KOTA = "Jakarta"


def _id(*bagian: str) -> uuid.UUID:
    """Id deterministik supaya seed bisa dijalankan ulang tanpa menumpuk baris."""
    return uuid.uuid5(uuid.NAMESPACE_URL, ":".join((KUNCI,) + bagian))


async def _lokasi(db: AsyncSession, nama: str) -> Location | None:
    return (
        await db.execute(select(Location).where(Location.name == nama))
    ).scalar_one_or_none()


async def _komoditas(db: AsyncSession, nama: str) -> Commodity | None:
    return (
        await db.execute(select(Commodity).where(Commodity.name == nama))
    ).scalar_one_or_none()


async def _pemasok(
    db: AsyncSession, lokasi_id: uuid.UUID, komoditas_id: uuid.UUID
) -> Supplier | None:
    """Pemasok komoditas ini di kota tujuan yang TIDAK sedang dikecualikan.

    Eksekusi menolak pemasok berstatus eksklusi aktif ("supplier excluded pada
    SPPG penerima"), jadi seed tidak boleh memilih yang pertama menurut abjad
    tanpa memeriksa status itu — kartu demo harus benar-benar bisa dieksekusi.
    """
    dikecualikan = select(SupplierExclusion.supplier_id).where(
        SupplierExclusion.scope_location_id == lokasi_id,
        SupplierExclusion.status == "active",
    )
    # Pemasok kanonik lebih dulu: bila pasangan (lokasi, komoditas) ini sudah
    # punya tepat satu pemasok di batch kanonik, batch demo WAJIB memakai yang
    # sama — kalau tidak, satu pasangan punya dua pemasok dan binding keputusan
    # jadi ambigu (`test_demo_batch_pemasok_tunggal`).
    kanonik = (
        await db.execute(
            select(Batch.supplier_id)
            .where(
                Batch.location_id == lokasi_id,
                Batch.commodity_id == komoditas_id,
                Batch.origin != "demo",
                Batch.supplier_id.not_in(dikecualikan),
                # Pemasok batch kanonik bisa saja salah komoditas di data lama
                # (contoh nyata: batch beras Jakarta dipasok "CV Barokah Telur
                # Cianjur"). Kandidat di sini disaring ke pemasok yang memang
                # menjual komoditas tersebut.
                Batch.supplier_id.in_(
                    select(Supplier.id).where(Supplier.commodity_id == komoditas_id)
                ),
            )
            .distinct()
        )
    ).scalars().all()
    if kanonik:
        # Dari himpunan kanonik, urut nama supaya deterministik. Memilih pemasok
        # di luar himpunan itu = pemasok "asing" yang langsung ditolak
        # `test_demo_batch_pemasok_tunggal`.
        return (
            await db.execute(
                select(Supplier)
                .where(Supplier.id.in_(kanonik))
                .order_by(Supplier.name)
                .limit(1)
            )
        ).scalars().first()
    kandidat = (
        await db.execute(
            select(Supplier)
            .where(
                Supplier.location_id == lokasi_id,
                Supplier.commodity_id == komoditas_id,
                Supplier.id.not_in(dikecualikan),
            )
            .order_by(Supplier.name)
            .limit(1)
        )
    ).scalars().first()
    return kandidat


async def _pengguna(db: AsyncSession, email: str) -> User | None:
    return (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()


def _suhu(panen: datetime, status: str) -> list[dict]:
    """Log suhu sederhana — kolomnya NOT NULL, isinya harus masuk akal."""
    return [
        {
            "jam": (panen + timedelta(minutes=15 * i)).isoformat(),
            "suhu_c": 4.0 + (i % 2) * 0.4,
            "status": status,
        }
        for i in range(4)
    ]


async def _bersihkan(db: AsyncSession) -> dict:
    """Hapus hanya baris milik modul ini (id deterministik)."""
    ids = [
        _id("b", k)
        for k in (
            "pagi-telur", "pagi-beras", "pagi-ayam", "jalan-telur",
            "jalan-wortel", "antre-ayam", "antre-telur", "selesai-beras",
        )
    ]
    keputusan = [_id("d", k) for k in (
        "pengadaan-telur", "imbang-bandung", "pengadaan-beras-lewat", "harga-ditolak",
        "ganti-sumber-flagged", "imbang-setuju", "pengadaan-telur-jalan",
        "redistribusi-wortel-jalan", "beras-selesai",
    )]
    await db.execute(delete(Approval).where(Approval.decision_id.in_(keputusan)))
    await db.execute(delete(DecisionEvidence).where(DecisionEvidence.decision_id.in_(keputusan)))
    await db.execute(delete(AgentTrace).where(AgentTrace.decision_id.in_(keputusan)))
    await db.execute(
        delete(BatchReceipt).where(
            BatchReceipt.id.in_(
                [_id("r", k) for k in ("pagi-telur", "pagi-beras", "pagi-ayam", "beras-selesai")]
            )
        )
    )
    await db.execute(delete(Decision).where(Decision.id.in_(keputusan)))
    await db.execute(delete(Batch).where(Batch.id.in_(ids)))
    await db.flush()
    return {"batch": len(ids), "keputusan": len(keputusan)}


async def susun(db: AsyncSession, now: datetime | None = None, nama_kota: str = _KOTA) -> dict:
    """Tulis satu hari operasional Jakarta. Kembalikan ringkasan apa adanya."""
    now = now or datetime.now(timezone.utc)
    jakarta = await _lokasi(db, nama_kota)
    if jakarta is None:
        return {"dilewati": f"{nama_kota} tidak ada"}

    telur = await _komoditas(db, "telur")
    beras = await _komoditas(db, "beras")
    ayam = await _komoditas(db, "ayam")
    wortel = await _komoditas(db, "wortel")
    if not all((telur, beras, ayam, wortel)):
        return {"dilewati": "komoditas inti belum ada"}

    bandung = await _lokasi(db, "Bandung")
    bogor = await _lokasi(db, "Bogor")
    kepala = await _pengguna(db, "sppg.head@demo.local")
    gizi = await _pengguna(db, "sppg.nutritionist@demo.local")
    if kepala is None or gizi is None:
        return {"dilewati": "akun kepala/gizi Jakarta belum ada"}

    sup_telur = await _pemasok(db, jakarta.id, telur.id)
    sup_beras = await _pemasok(db, jakarta.id, beras.id)
    sup_ayam = await _pemasok(db, jakarta.id, ayam.id)
    # Wortel WAJIB dari pemasok wortel: meminjam pemasok beras membuat satu
    # pasangan (lokasi, komoditas) punya dua pemasok berbeda — persis kesalahan
    # yang dikunci `test_demo_batch_pemasok_tunggal`.
    sup_wortel = await _pemasok(db, jakarta.id, wortel.id)
    if sup_telur is None or sup_beras is None or sup_ayam is None or sup_wortel is None:
        return {"dilewati": "pemasok telur/beras/ayam/wortel di Jakarta belum ada"}

    dibersihkan = await _bersihkan(db)

    # --- Kiriman (5): 3 tiba pagi, 1 jalan 4 jam, 1 jalan 2 jam, 1 antre -----
    def batch(
        kunci: str,
        komoditas,
        pemasok,
        qty: str,
        bangsa: str,
        kirim: timedelta | None,
        sisa: timedelta | None,
        status: str,
    ):
        panen = now - timedelta(hours=10)
        return Batch(
            id=_id("b", kunci),
            commodity_id=komoditas.id,
            location_id=jakarta.id,
            supplier_id=pemasok.id,
            quantity_kg=Decimal(qty),
            harvested_at=panen,
            temperature_log=_suhu(panen, status),
            certification_status="hygiene",
            freshness_score=Decimal("0.88"),
            safety_status="pass" if status != "pending" else "needs_verification",
            usable_until=(now + sisa) if sisa is not None else (now - timedelta(hours=1)),
            dispatched_at=(now - kirim) if kirim is not None else None,
            origin="demo",
            generated_at=now,
            created_at=now - timedelta(hours=11),
        )

    b_pagi = [
        batch(
            "pagi-telur", telur, sup_telur, "320", "telur",
            timedelta(hours=8), timedelta(hours=-2), "pass",
        ),
        batch(
            "pagi-beras", beras, sup_beras, "480", "beras",
            timedelta(hours=8), timedelta(hours=-2), "pass",
        ),
        batch(
            "pagi-ayam", ayam, sup_ayam, "260", "ayam",
            timedelta(hours=7), timedelta(hours=-1), "pass",
        ),
    ]
    b_jalan_telur = batch(
    "jalan-telur", telur, sup_telur, "780", "telur",
    timedelta(hours=4), timedelta(hours=2), "pass",
)
    b_jalan_wortel = batch(
    "jalan-wortel", wortel, sup_wortel, "400", "wortel",
    timedelta(hours=2), timedelta(minutes=75), "pass",
)
    b_antre = batch(
    "antre-ayam", ayam, sup_ayam, "300", "ayam",
    None, timedelta(hours=6), "pending",
)
    # Kiriman beras yang SUDAH selesai hari ini. Batch terpisah, bukan batch
    # pagi: DB hanya mengizinkan satu penerimaan disetujui per batch
    # (`uq_batch_receipts_satu_disetujui`), jadi menyatukannya akan menabrak
    # constraint — dan memang dua kejadian berbeda tidak boleh berbagi batch.
    # Batch yang MENUNGGU persetujuan kartu teratas: telur dari pemasok yang sama
    # dengan keputusannya (binding mensyaratkan supplier + komoditas + lokasi
    # cocok; memakai batch ayam membuat eksekusi ditolak 409).
    b_antre_telur = batch(
    "antre-telur", telur, sup_telur, "780", "telur",
    None, timedelta(hours=8), "pass",
)
    b_selesai = batch(
    "selesai-beras", beras, sup_beras, "480", "beras",
    timedelta(hours=6), timedelta(minutes=-20), "pass",
)
    for b in (*b_pagi, b_jalan_telur, b_jalan_wortel, b_antre, b_antre_telur, b_selesai):
        db.add(b)
    await db.flush()

    # --- Waktu berangkat diturunkan dari DURASI RUTE nyata -------------------
    # Versi pertama memakai offset tetap (4 jam dan 2 jam). Jarak Bekasi→Jakarta
    # hanya ±40 menit, jadi "truk berjalan" langsung terbaca sudah tiba: peta
    # tidak pernah menampilkannya sebagai perjalanan aktif. Setelah geometri
    # tersedia, keberangkatan dihitung mundur dari durasi rute supaya 45%
    # perjalanan sudah ditempuh dan 55% masih di depan.
    from app.core.road_route import route_key
    from app.seed.road_routes import sync_road_routes

    await sync_road_routes(db)
    for b in (b_jalan_telur, b_jalan_wortel):
        asal = await db.get(Supplier, b.supplier_id)
        tujuan = await db.get(Location, b.location_id)
        if asal is None or tujuan is None:
            continue
        kunci_rute = route_key(
            float(asal.latitude), float(asal.longitude),
            float(tujuan.latitude), float(tujuan.longitude),
        )
        rute = (
            await db.execute(select(RoadRoute).where(RoadRoute.route_key == kunci_rute))
        ).scalars().first()
        menit = (float(rute.duration_s) / 60.0) if rute and rute.duration_s else 40.0
        menit = max(12.0, menit)
        b.dispatched_at = now - timedelta(minutes=menit * 0.45)
        b.usable_until = now + timedelta(minutes=menit * 0.55)
    await db.flush()

    # --- Keputusan (9). Urutan `created_at` menentukan urutan kartu. ----------
    def keputusan(
        kunci: str,
        jenis: str,
        status: str,
        komoditas,
        qty: str,
        sdc: str,
        dibuat: timedelta,
        kedaluwarsa: timedelta,
        asal=None,
        pemasok=None,
        ditolak: str | None = None,
        catatan_verifikator: str | None = None,
        kasus: str | None = None,
    ) -> Decision:
        return Decision(
            id=_id("d", kunci),
            decision_type=jenis,
            status=status,
            proposed_by="supervisor_agent",
            verified_by="verifier_agent",
            verifier_note=catatan_verifikator,
            rejection_reason=ditolak,
            iteration=1,
            demo_case=kasus,
            source_location_id=(asal or jakarta).id,
            target_location_id=jakarta.id,
            supplier_id=pemasok.id if pemasok is not None else None,
            commodity_id=komoditas.id,
            quantity_kg=Decimal(qty),
            safe_delivered_cost=Decimal(sdc),
            expires_at=now + kedaluwarsa,
            origin="demo",
            generated_at=now,
            created_at=now - dibuat,
        )

    d_pengadaan_telur = keputusan(
        "pengadaan-telur", "supplier_procurement", "pending_approval", telur, "780", "14787096.28",
        # `asal` sengaja = Jakarta: binding batch mensyaratkan batch berada di
        # lokasi sumber, dan batch kiriman tersimpan di SPPG penerima. Rute di
        # peta tetap bergerak dari titik pemasok (Bekasi) ke SPPG Jakarta.
        timedelta(minutes=8),
        timedelta(minutes=18),
        asal=None,
        pemasok=sup_telur,
        kasus="shortage-darurat",
        # `verified_by` saja tidak cukup: tombol Eksekusi menolak (409 "belum
        # terverifikasi") bila verdict verifikator belum ditulis.
        catatan_verifikator="consistent",
    )
    d_imbang = keputusan(
        "imbang-bandung", "regional_balance", "pending_approval", beras, "450", "8260000.00",
        timedelta(hours=22), timedelta(minutes=55), asal=bandung,
    )
    d_lewat = keputusan(
        "pengadaan-beras-lewat", "supplier_procurement", "pending_approval", beras,
        "600", "9120000.00",
        # Pemasok beras ini berbasis Jakarta; sumber = kotanya, bukan Surabaya.
        timedelta(hours=20), timedelta(hours=-2), asal=None, pemasok=sup_beras,
    )
    d_ditolak = keputusan(
        "harga-ditolak", "price_anomaly", "rejected", telur, "500", "9100000.00",
        # `price_anomaly` bukan pengiriman: tidak ada asal barang, hanya harga.
        timedelta(hours=9), timedelta(hours=6), asal=None,
        ditolak="Harga acuan PIHPS untuk pekan ini belum dikonfirmasi pembandingnya.",
    )
    d_flag = keputusan(
        "ganti-sumber-flagged", "safety_disruption", "verifier_flagged", ayam, "300", "5400000.00",
        timedelta(hours=6), timedelta(hours=3), asal=None, pemasok=sup_ayam,
        catatan_verifikator="flagged", kasus="gangguan-logistik",
    )
    d_setuju = keputusan(
        "imbang-setuju", "regional_balance", "approved", wortel, "380", "4980000.00",
        # Penyeimbangan antar-SPPG: sumber harus tetangga dekat (Bandung 116 km).
        timedelta(hours=5), timedelta(hours=4), asal=bandung,
    )
    d_jalan = keputusan(
        "pengadaan-telur-jalan", "supplier_procurement", "executed", telur, "780", "14787096.28",
        timedelta(hours=4), timedelta(hours=2), asal=None, pemasok=sup_telur,
    )
    d_jalan2 = keputusan(
        "redistribusi-wortel-jalan", "regional_balance", "executed", wortel, "400", "5240000.00",
        timedelta(hours=2), timedelta(minutes=75), asal=bogor,
    )
    d_selesai = keputusan(
        "beras-selesai", "supplier_procurement", "executed", beras, "480", "7360000.00",
        timedelta(hours=7), timedelta(hours=1), asal=None, pemasok=sup_beras,
    )
    semua = [
        d_pengadaan_telur, d_imbang, d_lewat, d_ditolak, d_flag,
        d_setuju, d_jalan, d_jalan2, d_selesai,
    ]
    for d in semua:
        db.add(d)
    await db.flush()

    # --- Bukti (payload memuat supplier_id: sumber baris "Dikirim pemasok …") --
    # Kartu yang berakhir ditolak/di-flag/lewat tenggat TETAP butuh bukti: justru
    # bukti itulah alasan kartunya berstatus begitu, dan panel Decision & Evidence
    # tidak boleh kosong saat juri membukanya (audit 24 Okt 2026).
    for urut, (d, jenis_bukti) in enumerate((
        (d_pengadaan_telur, "sap_purchase_order"),
        (d_jalan, "sap_purchase_order"),
        (d_selesai, "sap_purchase_order"),
        (d_setuju, "human_inspection"),
        (d_jalan2, "human_inspection"),
        (d_imbang, "gps"),
        (d_lewat, "human_inspection"),
        (d_ditolak, "market_price"),
        (d_flag, "market_price"),
    )):
        db.add(
            DecisionEvidence(
                id=_id("e", str(d.id)),
                decision_id=d.id,
                evidence_type=jenis_bukti,
                payload={
                    "demo": True,
                    "supplier_id": str(d.supplier_id) if d.supplier_id else None,
                    "batch_ids": (
                        [str(b_antre_telur.id)] if d is d_pengadaan_telur else []
                    ),
                    "allocation_binding": d is d_pengadaan_telur,
                    "catatan": "bukti hari ini",
                },
                is_consistent=True,
                recorded_at=d.created_at + timedelta(minutes=4),
            )
        )

    # Bukti kedua dengan JENIS berbeda. Metrik Evidence Completeness menghitung
    # persentase keputusan yang punya >=2 jenis bukti; satu jenis saja membuat
    # metrik itu 0% walau buktinya ada.
    for d in (d_pengadaan_telur, d_setuju, d_jalan, d_jalan2, d_selesai):
        db.add(
            DecisionEvidence(
                id=_id("e2", str(d.id)),
                decision_id=d.id,
                # Harus BEDA dari bukti pertama (human_inspection vs sap_purchase_order),
                # kalau tidak jumlah JENIS-nya tetap 1 dan metrik membaca 0%.
                evidence_type=(
                    "human_inspection" if d.supplier_id is not None else "gps"
                ),
                payload={
                    "demo": True,
                    "supplier_id": str(d.supplier_id) if d.supplier_id else None,
                    "catatan": "pemeriksaan fisik hari ini",
                },
                is_consistent=True,
                recorded_at=d.created_at + timedelta(minutes=9),
            )
        )

    # PO di mock SAP. Metrik Safe Delivered Cost berjangkar pada baris ini.
    for d, nomor_po, harga_po, qty in (
        (d_jalan, "4500001122", Decimal("18957.81"), Decimal("780")),
        (d_selesai, "4500001123", Decimal("15333.33"), Decimal("480")),
    ):
        db.add(
            SapMockPurchaseOrder(
                id=_id("po", str(d.id)),
                po_number=nomor_po,
                supplier_id=d.supplier_id or sup_telur.id,
                material_number=f"MAT-{(d.commodity_id and 'HARI')[:4]}",
                ordered_quantity=qty,
                price=harga_po,
                decision_id=d.id,
                status="confirmed",
                origin="demo",
                created_at=d.created_at + timedelta(minutes=26),
            )
        )

    # --- Persetujuan dua orang berbeda (four-eyes) ---------------------------
    for d in (d_setuju, d_jalan, d_jalan2, d_selesai):
        for urut, orang in enumerate((kepala, gizi)):
            db.add(
                Approval(
                    id=_id("a", str(d.id), str(urut)),
                    decision_id=d.id,
                    approved_by=orang.id,
                    approved=True,
                    comment="Sesuai prosedur four-eyes.",
                    approved_at=d.created_at + timedelta(minutes=20 + urut * 3),
                )
            )

    # --- Penerimaan pagi + penerimaan selesai → delivery_events (Meal Continuity)
    for b, kunci in (
        (b_pagi[0], "pagi-telur"),
        (b_pagi[1], "pagi-beras"),
        (b_pagi[2], "pagi-ayam"),
    ):
        db.add(
            BatchReceipt(
                id=_id("r", kunci),
                batch_id=b.id,
                checked={"suhu": True, "kemasan": True, "jumlah": True},
                recorded_by=kepala.id,
                recorded_at=now - timedelta(hours=6),
                status="disetujui",
                reviewed_by=gizi.id,
                reviewed_at=now - timedelta(hours=6) + timedelta(minutes=12),
                review_note="Diterima lengkap.",
            )
        )
    db.add(
        BatchReceipt(
            id=_id("r", "beras-selesai"),
            batch_id=b_selesai.id,
            checked={"suhu": True, "kemasan": True, "jumlah": True},
            recorded_by=kepala.id,
            recorded_at=now - timedelta(minutes=30),
            status="disetujui",
            reviewed_by=gizi.id,
            reviewed_at=now - timedelta(minutes=25),
            review_note="Kiriman beras selesai.",
        )
    )
    await db.flush()

    kpi: list[dict] = []
    for b, kunci in (
        (b_pagi[0], "pagi-telur"),
        (b_pagi[1], "pagi-beras"),
        (b_pagi[2], "pagi-ayam"),
    ):
        resep = await db.get(BatchReceipt, _id("r", kunci))
        assert resep is not None  # baru saja ditambahkan di atas
        kpi.append(
            await settlement.catat_penerimaan(
                db, batch=b, receipt=resep, sekarang=now - timedelta(hours=6)
            )
        )
    resep_selesai = await db.get(BatchReceipt, _id("r", "beras-selesai"))
    assert resep_selesai is not None
    kpi.append(
        await settlement.catat_penerimaan(
            db, batch=b_selesai, receipt=resep_selesai,
            sekarang=now - timedelta(minutes=25),
        )
    )

    # --- PO terbit untuk keputusan yang dieksekusi → price_signals -----------
    for d, nomor, harga in (
        (d_jalan, "PO-HARIINI-001", "18957.81"),
        (d_selesai, "PO-HARIINI-002", "15333.33"),
    ):
        kpi.append(
            await settlement.catat_po_terbit(
                db, decision=d, po_number=nomor, supplier_id=d.supplier_id or sup_telur.id,
                harga_per_kg=Decimal(harga), sekarang=d.created_at + timedelta(minutes=25),
            )
        )

    # --- Pembuangan → disposal_events (Avoidable Food Loss) ------------------
    kpi.append(
        await settlement.catat_pembuangan(
            db, location_id=jakarta.id, commodity_id=wortel.id, quantity_kg=Decimal("12"),
            reason="rusak saat bongkar", partner_name=None, sekarang=now - timedelta(hours=3),
            kunci="hari-ini:sayur-rusak",
        )
    )
    kpi.append(
        await settlement.catat_pembuangan(
            db, location_id=jakarta.id, commodity_id=ayam.id, quantity_kg=Decimal("6"),
            reason="suhu di luar batas", partner_name=None, sekarang=now - timedelta(hours=1),
            kunci="hari-ini:ayam-suhu",
        )
    )

    # --- Origin baris KPI -----------------------------------------------------
    # `settlement._asal()` menulis 'seed' bila tidak ada sesi demo aktif. Baris
    # yang ditulis seed ini adalah data DEMO, dan invarian tabel deret waktu
    # mewajibkan baris kanonik tidak membawa `generated_at` sementara baris demo
    # wajib membawanya (`test_timeseries_db`). Jadi origin-nya diluruskan di
    # sini, bukan dengan memalsukan angka.
    await db.execute(
        update(DisposalEvent)
        .where(
            DisposalEvent.source_ref.in_(
                ["disposal:hari-ini:sayur-rusak", "disposal:hari-ini:ayam-suhu"]
            )
        )
        .values(origin="demo")
    )
    await db.execute(
        update(PriceSignal)
        .where(PriceSignal.source_ref.in_(["po:PO-HARIINI-001", "po:PO-HARIINI-002"]))
        .values(origin="demo")
    )
    await db.execute(
        update(DeliveryEvent)
        .where(
            DeliveryEvent.source_ref.in_(
                [
                    f"receipt:{_id('r', k)}"
                    for k in ("pagi-telur", "pagi-beras", "pagi-ayam", "beras-selesai")
                ]
            )
        )
        .values(origin="demo")
    )

    # --- Jejak agen (DETECT) supaya Regional Imbalance punya bahan ------------
    # ACT hanya ditulis untuk keputusan yang BENAR-BENAR dieksekusi. Sebelumnya
    # baris ACT ikut dibuat untuk semua keputusan tanpa `demo_case`, sehingga
    # keputusan `pending_approval`/`rejected` punya jejak "approval.execute" —
    # invarian `verify/invariants.spec.json` menangkapnya (8 baris) dan panel
    # Agent Log seolah melaporkan eksekusi yang tidak pernah terjadi.
    for d in semua:
        if d.demo_case is None and d.status == "executed":
            db.add(
                AgentTrace(
                    id=_id("t-act", str(d.id)),
                    decision_id=d.id,
                    step_name="ACT",
                    tool_called="approval.execute",
                    input_summary={"decision": str(d.id)},
                    output_summary={"status": d.status},
                    duration_ms=22,
                    agent_name="supervisor",
                    confidence=Decimal("0.88"),
                    step_at=d.created_at + timedelta(minutes=22),
                )
            )
        db.add(
            AgentTrace(
                id=_id("t", str(d.id)),
                decision_id=d.id,
                step_name="DETECT",
                tool_called="demand.snapshot",
                input_summary={"location": nama_kota},
                output_summary={"shortage_kg": float(d.quantity_kg or 0)},
                duration_ms=18,
                agent_name="demand",
                confidence=Decimal("0.90"),
                step_at=d.created_at,
            )
        )
    await db.flush()

    return {
        "kota": nama_kota,
        "dibersihkan": dibersihkan,
        "keputusan": len(semua),
        "ids": [str(d.id) for d in semua],
        "kiriman": 6,
        "kpi_tertulis": [k for k in kpi if k.get("ditulis")],
        "kpi_dilewati": [k for k in kpi if not k.get("ditulis")],
        "kartu_teratas": {
            "id": str(d_pengadaan_telur.id),
            "jenis": d_pengadaan_telur.decision_type,
            "pemasok": sup_telur.name if sup_telur else None,
            "kedaluwarsa": d_pengadaan_telur.expires_at.isoformat(),
        },
    }
