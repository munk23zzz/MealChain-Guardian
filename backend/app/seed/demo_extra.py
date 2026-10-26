"""Pelengkap data DEMO — menutup baris matriks yang belum dibuktikan seed.

`seed_data` + `timeseries` + `demo_activity` sudah mengisi deret waktu, KPI, dan
kasus per kota. Yang belum tentu ada sesudahnya: satu keputusan untuk SETIAP
`decision_type` dan SETIAP `decision.status`, bukti keputusan yang konsisten dan
tidak konsisten, jejak pipeline lengkap, PO yang lahir dari keputusan, penerimaan
barang berstatus `menunggu`/`ditolak`, batch karantina, eksklusi pemasok yang
masih aktif maupun sudah dicabut, limbah dengan dan tanpa mitra, serta teks
panjang/Unicode dan angka ekstrem untuk menguji tampilan.

Semua baris di sini:
* deterministik — id = `stable_uuid("extra", ...)`, waktu relatif ke `now`;
* bertanda `origin='demo'` sehingga `reset-demo` membersihkannya;
* idempoten — `merge` pada id tetap, jadi aman dijalankan berulang.

Tidak menyentuh tabel referensi (commodities, locations, users).
"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.models import (
    AgentTrace,
    Approval,
    Batch,
    BatchReceipt,
    Commodity,
    Decision,
    DecisionEvidence,
    DemoSession,
    DisposalEvent,
    Location,
    MenuPlan,
    PriceSignal,
    SapMockPurchaseOrder,
    Supplier,
    SupplierExclusion,
    User,
)
from app.seed.seed_data import stable_uuid

# Cakupan enum: 6 decision_type x 7 status disusun supaya SETIAP nilai muncul
# minimal sekali tanpa membuat 42 keputusan yang isinya mengulang.
KOMBINASI_KEPUTUSAN: tuple[tuple[str, str], ...] = (
    ("regional_balance", "proposed"),
    ("regional_balance", "verifier_flagged"),
    ("price_anomaly", "pending_approval"),
    ("price_anomaly", "approved"),
    ("safety_disruption", "rejected"),
    ("safety_disruption", "executed"),
    ("supplier_exclusion", "review_only"),
    ("supplier_exclusion_restoration", "executed"),
    ("supplier_procurement", "executed"),
    ("supplier_procurement", "pending_approval"),
)

TIPE_BUKTI = (
    "sap_purchase_order",
    "sap_goods_receipt",
    "gps",
    "temperature",
    "human_inspection",
    "market_price",
)

LANGKAH_PIPELINE = ("DETECT", "VERIFY", "PREDICT", "OPTIMIZE", "DECIDE", "SUPERVISE")

CATATAN_PANJANG = (
    "Pemeriksaan ulang oleh ahli gizi: suhu ruang penyimpanan sempat naik di atas "
    "ambang aman selama pengiriman, tetapi sensor kedua menunjukkan angka normal — "
    "bukti suhu perlu diverifikasi manual sebelum batch dinyatakan layak. "
    "Catatan lapangan: “sudah dicek dua kali, segel utuh” — 25 °C, kelembapan 78%."
)

PEMASOK_UNICODE = "Koperasi Tani Makmur — Cianjur (Unit SPPG)"


async def _konteks(session) -> dict:
    lokasi = {x.name: x for x in (await session.execute(select(Location))).scalars()}
    komoditas = {
        c.name: c for c in (await session.execute(select(Commodity))).scalars()
    }
    pemasok = list((await session.execute(select(Supplier))).scalars())
    pengguna = list((await session.execute(select(User))).scalars())
    sppg = [x for x in lokasi.values() if (x.role_hint or "sppg") == "sppg"]
    return {
        "lokasi": lokasi,
        "komoditas": komoditas,
        "pemasok": pemasok,
        "pengguna": pengguna,
        "sppg": sppg or list(lokasi.values()),
    }


async def _ambil_atau_buat(session, model, key: str, nilai: dict):
    """Merge deterministik: baris diambil dari id stable_uuid, bukan dari isi."""
    kunci = stable_uuid("extra", key)
    ada = await session.get(model, kunci)
    if ada is None:
        session.add(model(id=kunci, **nilai))
        return kunci, True
    # Idempoten: segarkan kolom yang dikelola builder agar angka relatif ikut
    # bergeser saat builder dijalankan ulang di hari lain.
    for k, v in nilai.items():
        if hasattr(ada, k):
            setattr(ada, k, v)
    return kunci, False


async def pastikan_pemasok_unicode(session, pemasok: list) -> str | None:
    """Penjaga: nama ber-em dash milik berkas demo, bukan ditanam saat build.

    Riwayat: helper ini dulu MENGGANTI NAMA satu pemasok terpilih agar UI punya
    contoh em dash. Akibatnya direktori demo berubah setiap build (nama hilang
    dari berkas, baris baru lahir saat seed berikutnya) dan dua pemasok bisa
    berbagi koordinat yang sama sehingga pin peta bertumpuk.

    Kontrak sekarang: master data tidak disentuh. Bila direktori sudah memuat
    nama ber-em dash (dari `data/seed/suppliers_demo.json`), id-nya
    dikembalikan; kalau tidak, None. Tidak ada baris dibuat, diubah, atau
    dihapus di sini.
    """
    del session  # sengaja tanpa I/O: fungsi ini hanya membaca daftar di memori
    sudah = next((s for s in pemasok if " — " in (s.name or "")), None)
    return str(sudah.id) if sudah else None


async def build_demo_extra(session, now: datetime | None = None) -> dict[str, int]:
    now = now or datetime.now(timezone.utc)
    ctx = await _konteks(session)
    sppg = ctx["sppg"]
    komoditas = list(ctx["komoditas"].values())
    pemasok = ctx["pemasok"]
    pengguna = ctx["pengguna"]
    if not (sppg and komoditas and pemasok and pengguna):
        raise RuntimeError(
            "build_demo_extra butuh data referensi + pemasok; "
            "jalankan init-demo dari database bermigrasi"
        )

    kepala = next((u for u in pengguna if u.role == "sppg_head"), pengguna[0])
    gizzi = next((u for u in pengguna if u.role == "sppg_nutritionist"), pengguna[-1])
    jumlah: Counter[str] = Counter()

    # ---------------------------------------------------------------- keputusan
    id_keputusan: list[tuple[str, str, uuid.UUID]] = []
    for indeks, (tipe, status) in enumerate(KOMBINASI_KEPUTUSAN):
        lok = sppg[indeks % len(sppg)]
        kom = komoditas[indeks % len(komoditas)]
        nilai = dict(
            decision_type=tipe,
            status=status,
            proposed_by=f"agent:{tipe}",
            verified_by="verifier:otomatis" if status != "proposed" else None,
            verifier_note=(
                CATATAN_PANJANG if indeks == 0 else "Sesuai ambang."
            ),
            rejection_reason=(
                "Harga kuotasi tidak dapat diverifikasi ulang." if status == "rejected" else None
            ),
            iteration=1 + (indeks % 3),
            demo_case=f"extra:{tipe}",
            source_location_id=lok.id,
            target_location_id=sppg[(indeks + 1) % len(sppg)].id,
            supplier_id=pemasok[indeks % len(pemasok)].id,
            commodity_id=kom.id,
            quantity_kg=Decimal("150.50") + Decimal(indeks * 25),
            safe_delivered_cost=Decimal("12345.67"),
            cost_breakdown={"harga": 11000, "angkut": 900, "risiko": 445.67},
            expires_at=now + timedelta(days=14 - indeks),
            generated_at=now - timedelta(hours=indeks + 1),
            created_at=now - timedelta(hours=indeks + 1),
            origin="demo",
        )
        did, _ = await _ambil_atau_buat(
            session, Decision, f"decision:{tipe}:{status}", nilai
        )
        id_keputusan.append((tipe, status, did))
        jumlah["decisions"] += 1

    # ------------------------------------------------- approval + bukti + trace
    for tipe, status, did in id_keputusan:
        if status in {"approved", "executed", "rejected"}:
            await _ambil_atau_buat(
                session,
                Approval,
                f"approval:{did}",
                dict(
                    decision_id=did,
                    approved_by=kepala.id,
                    approved=status != "rejected",
                    comment=(
                        "Disetujui untuk pengadaan besok."
                        if status != "rejected"
                        else "Ditolak: jalur pasokan alternatif sudah tersedia."
                    ),
                    approved_at=now - timedelta(hours=2),
                ),
            )
            jumlah["approvals"] += 1

    sudah_bukti: set[uuid.UUID] = set()
    for indeks, tipe_bukti in enumerate(TIPE_BUKTI):
        _, _, did = id_keputusan[indeks % len(id_keputusan)]
        sudah_bukti.add(did)
        await _ambil_atau_buat(
            session,
            DecisionEvidence,
            f"evidence:{tipe_bukti}",
            dict(
                decision_id=did,
                evidence_type=tipe_bukti,
                payload={
                    "ref": f"EXTRA-{indeks}",
                    "nilai": "0" if indeks == 0 else str(indeks * 100),
                    "catatan": CATATAN_PANJANG if indeks == 5 else "terverifikasi",
                },
                is_consistent=(False if indeks == 5 else True),
                recorded_at=now - timedelta(minutes=30 * (indeks + 1)),
            ),
        )
        jumlah["decision_evidence"] += 1

    # Setiap keputusan demo wajib punya bukti — kartu tanpa bukti membuat tab
    # Decision & Evidence kosong dan Evidence Completeness tidak bisa dihitung.
    # `_ambil_atau_buat` idempoten, jadi aman dijalankan tiap build.
    for indeks, (tipe, _status, did) in enumerate(id_keputusan):
        if did in sudah_bukti:
            continue
        tipe_bukti = TIPE_BUKTI[indeks % len(TIPE_BUKTI)]
        await _ambil_atau_buat(
            session,
            DecisionEvidence,
            f"evidence-pelengkap:{did}",
            dict(
                decision_id=did,
                evidence_type=tipe_bukti,
                payload={
                    "ref": f"EXTRA-{tipe}-{indeks}",
                    "nilai": str(100 + indeks * 10),
                    "catatan": "bukti pelengkap demo",
                },
                is_consistent=True,
                recorded_at=now - timedelta(minutes=20 * (indeks + 1)),
            ),
        )
        jumlah["decision_evidence"] += 1

    # Jejak pipeline lengkap untuk tiga keputusan (dipakai panel jejak agen dan
    # tes yang mensyaratkan DETECT + DECIDE + PREDICT/OPTIMIZE/SUPERVISE).
    for urut in range(3):
        _, _, did = id_keputusan[urut]
        run_id = stable_uuid("extra", "run", str(urut))
        for langkah in LANGKAH_PIPELINE:
            await _ambil_atau_buat(
                session,
                AgentTrace,
                f"trace:{did}:{langkah}",
                dict(
                    decision_id=did,
                    step_name=langkah,
                    tool_called=f"tool_{langkah.lower()}",
                    input_summary={"komoditas": komoditas[urut].name},
                    output_summary={"hasil": "ok", "catatan": CATATAN_PANJANG[:120]},
                    duration_ms=850 + urut * 120,
                    run_id=run_id,
                    agent_name=None,
                    confidence=0.82 + urut * 0.03,
                    citations=[{"source": "extra", "ref": f"trace-{urut}"}],
                    step_at=now - timedelta(minutes=10 * (6 - LANGKAH_PIPELINE.index(langkah))),
                ),
            )
            jumlah["agent_traces"] += 1

    # Jejak BER-AGEN (agent_name terisi) — dipakai panel "bukti pipeline" di
    # Demo Control, yang menyaring `agent_name is not null`. Jejak pipeline di
    # atas sengaja tanpa agen (itu putaran orkestrasi), jadi tanpa blok ini
    # panel itu selalu kosong walau datanya ada (matriks §5.1, 22 Okt 2026).
    for urut in range(2):
        _, _, did = id_keputusan[urut]
        for langkah, agen in (
            ("PREDICT", "agent:demand-forecaster"),
            ("OPTIMIZE", "agent:allocation-optimizer"),
            ("SUPERVISE", "agent:safety-supervisor"),
        ):
            await _ambil_atau_buat(
                session,
                AgentTrace,
                f"trace-agen:{did}:{langkah}",
                dict(
                    decision_id=did,
                    step_name=langkah,
                    tool_called=f"tool_{langkah.lower()}",
                    input_summary={"komoditas": komoditas[urut].name},
                    output_summary={"hasil": "ok", "agen": agen},
                    duration_ms=1200 + urut * 150,
                    run_id=stable_uuid("extra", "run-agen", str(urut)),
                    agent_name=agen,
                    confidence=0.88,
                    citations=[{"source": "extra", "ref": f"agen-{urut}"}],
                    step_at=now - timedelta(minutes=5 * (3 - urut)),
                ),
            )
            jumlah["agent_traces"] += 1

    # Setiap keputusan wajib punya minimal satu langkah jejak. Tanpa ini, 9 dari
    # 12 keputusan `extra:*` tampil sebagai kartu tanpa jejak dan gate
    # `verify/invariants.spec.json` menolaknya (terukur 26 Okt 2026: 9 yatim).
    # Yang sudah punya jejak (tiga di atas) dilewati supaya tidak dobel DETECT.
    sudah = set(
        (
            await session.execute(
                select(AgentTrace.decision_id).where(
                    AgentTrace.decision_id.in_([did for _, _, did in id_keputusan])
                )
            )
        ).scalars()
    )
    for tipe, status, did in id_keputusan:
        if did in sudah:
            continue
        await _ambil_atau_buat(
            session,
            AgentTrace,
            f"trace-dasar:{did}",
            dict(
                decision_id=did,
                step_name="DETECT",
                tool_called="demand.snapshot",
                input_summary={"komoditas": tipe, "status": status},
                output_summary={"hasil": "terdeteksi", "catatan": "kasus cakupan"},
                duration_ms=700,
                run_id=stable_uuid("extra", "run-dasar", str(did)),
                agent_name=None,
                confidence=0.80,
                citations=[{"source": "extra", "ref": "dasar"}],
                step_at=now - timedelta(hours=2),
            ),
        )
        jumlah["agent_traces"] += 1

    # ------------------------------------------------------------------- PO
    # Satu PO untuk setiap keputusan berstatus executed: inilah bukti bahwa
    # "dua approval -> PO terbit" bisa ditunjukkan di UI dan dijawab Joule.
    status_po = ("confirmed", "submitted", "draft")
    for urut, (tipe, status, did) in enumerate(
        [k for k in id_keputusan if k[1] == "executed"]
    ):
        kom = komoditas[urut % len(komoditas)]
        await _ambil_atau_buat(
            session,
            SapMockPurchaseOrder,
            f"po:{did}",
            dict(
                po_number=f"MC-EXTRA{urut:03d}",
                supplier_id=pemasok[urut % len(pemasok)].id,
                material_number=f"MAT-{kom.name.upper()}",
                ordered_quantity=Decimal("250.00") + Decimal(urut * 150),
                price=Decimal("13500.00"),
                decision_id=did,
                status=status_po[urut % len(status_po)],
                origin="demo",
                created_at=now - timedelta(hours=urut + 1),
            ),
        )
        jumlah["sap_mock_purchase_orders"] += 1

    # PO dengan angka ekstrem (uji format rupiah/kuantitas di UI).
    await _ambil_atau_buat(
        session,
        SapMockPurchaseOrder,
        "po:ekstrem",
        dict(
            po_number="MC-EXTREME01",
            supplier_id=pemasok[0].id,
            material_number=f"MAT-{komoditas[0].name.upper()}",
            ordered_quantity=Decimal("99999.50"),
            price=Decimal("999999.99"),
            decision_id=None,
            status="draft",
            origin="demo",
            created_at=now,
        ),
    )
    jumlah["sap_mock_purchase_orders"] += 1

    # ------------------------------------------------------- batch + penerimaan
    lok = sppg[0]
    kom = komoditas[0]
    sup = pemasok[0]
    varian_batch = (
        ("quarantined", "needs_verification", Decimal("0.42")),
        ("released", "pass", Decimal("0.98")),
        ("failed", "fail", Decimal("0.10")),
        ("none", "pending", None),
    )
    id_batch: list[uuid.UUID] = []
    for urut, (karantina, safety, fresh) in enumerate(varian_batch):
        bid, _ = await _ambil_atau_buat(
            session,
            Batch,
            f"batch:{karantina}",
            dict(
                commodity_id=komoditas[urut % len(komoditas)].id,
                location_id=sppg[urut % len(sppg)].id,
                supplier_id=pemasok[urut % len(pemasok)].id,
                quantity_kg=Decimal("180.00") + Decimal(urut * 40),
                harvested_at=now - timedelta(days=1, hours=urut),
                temperature_log=[
                    {"at": (now - timedelta(hours=6)).isoformat(), "celsius": 4.5},
                    {"at": (now - timedelta(hours=3)).isoformat(), "celsius": 11.0},
                ],
                certification_status=("haccp", "hygiene", "none")[urut % 3],
                freshness_score=fresh,
                safety_status=safety,
                usable_until=now + timedelta(days=2 + urut),
                dispatched_at=now - timedelta(hours=8),
                quarantine_status=karantina,
                quarantine_reason=("Suhu keluar rentang aman" if karantina != "none" else None),
                quarantined_at=(now - timedelta(hours=5) if karantina != "none" else None),
                quarantine_updated_at=now - timedelta(hours=1),
                quarantine_actor_id=gizzi.id if karantina != "none" else None,
                origin="demo",
                generated_at=now - timedelta(hours=9),
                created_at=now - timedelta(hours=9),
            ),
        )
        id_batch.append(bid)
        jumlah["batches"] += 1

    status_terima = ("menunggu", "menunggu", "menunggu", "disetujui", "ditolak")
    for urut, status in enumerate(status_terima):
        await _ambil_atau_buat(
            session,
            BatchReceipt,
            f"receipt:{urut}",
            dict(
                batch_id=id_batch[urut % len(id_batch)],
                checked={"suhu": 4.0 + urut, "segel": urut % 2 == 0},
                other_note=(CATATAN_PANJANG if urut == 4 else "Kondisi baik."),
                recorded_by=kepala.id,
                recorded_at=now - timedelta(hours=urut + 1),
                status=status,
                reviewed_by=(kepala.id if status != "menunggu" else None),
                reviewed_at=(now - timedelta(hours=urut) if status != "menunggu" else None),
                # urut==4 sengaja memakai catatan panjang ber-Unicode: satu-satunya
                # kolom teks bebas yang dibaca layar Penerimaan. Tanpa ini state
                # "catatan sangat panjang / karakter non-ASCII" tidak pernah terlihat.
                review_note=(
                    None
                    if status == "menunggu"
                    else (CATATAN_PANJANG if urut == 4 else "Sesuai catatan lapangan.")
                ),
            ),
        )
        jumlah["batch_receipts"] += 1

    # ------------------------------------------------------- eksklusi pemasok
    for urut, status in enumerate(("proposed", "active", "rejected", "revoked")):
        await _ambil_atau_buat(
            session,
            SupplierExclusion,
            f"exclusion:{status}",
            dict(
                supplier_id=pemasok[urut % len(pemasok)].id,
                scope_location_id=sppg[urut % len(sppg)].id,
                status=status,
                reason=(
                    CATATAN_PANJANG
                    if urut == 1
                    else "Keterlambatan berulang di atas 6 jam."
                ),
                evidence_refs=[{"ref": f"EXTRA-EX-{urut}"}],
                source_decision_id=id_keputusan[urut][2],
                restoration_decision_id=(
                    id_keputusan[7][2] if status == "revoked" else None
                ),
                proposed_by=kepala.id,
                approved_at=(now - timedelta(days=3) if status in {"active", "revoked"} else None),
                activated_at=(now - timedelta(days=3) if status in {"active", "revoked"} else None),
                revoked_at=(now - timedelta(days=1) if status == "revoked" else None),
                revocation_reason=("Pemasok memperbaiki SLA." if status == "revoked" else None),
                created_at=now - timedelta(days=4),
                updated_at=now - timedelta(days=1),
            ),
        )
        jumlah["supplier_exclusions"] += 1

    # ----------------------------------------------------------------- limbah
    for urut, mitra in enumerate((None, "Bank Pangan Nusantara", "Kompos Bersama")):
        await _ambil_atau_buat(
            session,
            DisposalEvent,
            f"disposal:{urut}",
            dict(
                location_id=sppg[urut % len(sppg)].id,
                commodity_id=komoditas[urut % len(komoditas)].id,
                quantity_kg=Decimal("12.50") + Decimal(urut * 7),
                reason=("Susut sortir" if mitra else "Tidak ada mitra pengolah"),
                partner_name=mitra,
                origin="demo",
                generated_at=now - timedelta(days=1),
                disposed_at=now - timedelta(hours=urut + 2),
            ),
        )
        jumlah["disposal_events"] += 1

    # ----------------------------------------- menu masa depan + harga anomali
    # Menu masa depan. Tanggal +5 hari (bukan besok): deret waktu sudah mengisi
    # besok untuk semua lokasi, dan `uq_menu_plans_loc_date` akan menolak
    # duplikat (location_id, plan_date).
    tanggal_menu = date.today() + timedelta(days=5)
    ada_menu = await session.scalar(
        select(MenuPlan).where(
            MenuPlan.location_id == lok.id, MenuPlan.plan_date == tanggal_menu
        )
    )
    if ada_menu is None:
        session.add(
            MenuPlan(
                id=stable_uuid("extra", "menu:masa-depan"),
                location_id=lok.id,
                plan_date=tanggal_menu,
                planned_portions=520,
                origin="demo",
                generated_at=now,
            )
        )
        jumlah["menu_plans"] += 1

    await _ambil_atau_buat(
        session,
        PriceSignal,
        "price:anomali",
        dict(
            location_id=lok.id,
            commodity_id=kom.id,
            price_per_kg=Decimal("87500.00"),
            supplier_id=sup.id,
            recorded_at=now - timedelta(hours=2),
            source="supplier_quote",
            origin="demo",
            generated_at=now,
        ),
    )
    jumlah["price_signals"] += 1

    # ------------------------------------------------------------ sesi demo
    for urut, status in enumerate(("ended", "expired")):
        await _ambil_atau_buat(
            session,
            DemoSession,
            f"session:{status}",
            dict(
                status=status,
                started_at=now - timedelta(days=2 + urut, hours=1),
                expires_at=now - timedelta(days=2 + urut),
                anchor_now=now - timedelta(days=2 + urut),
                ended_at=now - timedelta(days=2 + urut, minutes=-120),
                template_version="extra",
                created_by=kepala.id,
            ),
        )
        jumlah["demo_sessions"] += 1

    # ------------------------------------- pemasok demo ber-Unicode (nama panjang)
    # Nama ber-em dash ini ada untuk menguji kolom sempit di UI. Dulu baris ini
    # MENAMBAH pemasok ke-61: direktori demo berubah 60 -> 61 setelah "Siapkan
    # data demo", padahal `suppliers` tidak punya kolom `origin` dan tidak ikut
    # dibersihkan purge — baris itu menetap selamanya, sehingga angka di
    # runbook (60 pemasok) tidak cocok dengan layar. Sekarang nama itu
    # dipasang pada salah satu pemasok yang SUDAH ada; jumlah tidak berubah.
    await pastikan_pemasok_unicode(session, pemasok)

    # --------------------------------------------- kapasitas pemasok (kolom UI)
    # Kolom "Kapasitas/minggu" di direktori hanya terisi untuk 1 pemasok, sisanya
    # "—" walau panel mengklaim kapasitas tersedia. Diisi bervariasi; dua pemasok
    # sengaja DIBIARKAN kosong supaya state "—" tetap punya bukti.
    semua_pemasok = sorted(
        (await session.execute(select(Supplier))).scalars().all(), key=lambda x: str(x.id)
    )
    for urut, s in enumerate(semua_pemasok):
        if s.capacity_kg_per_week is not None:
            continue
        s.capacity_kg_per_week = Decimal(800 + (urut % 7) * 350)
        jumlah["suppliers_capacity"] += 1
    # Dua pemasok pertama (urut id, jadi deterministik antar-run) dikosongkan lagi
    # sebagai bukti state "—". Tanpa penegasan ini, run berikutnya mengisi sisa
    # baris dan bukti state kosong ikut hilang (terukur: 60 -> 61).
    for s in semua_pemasok[:2]:
        s.capacity_kg_per_week = None

    # ------------------------------------------- keputusan lama (riwayat/audit)
    # Seluruh keputusan demo jatuh dalam 2 hari terakhir, sehingga filter tanggal
    # "minggu lalu" dan panel riwayat tidak punya baris. Dua keputusan ditambah
    # ke masa lalu; keduanya sudah dieksekusi sehingga aman dilihat sebagai audit.
    for urut, (umur, status) in enumerate(((12, "executed"), (21, "approved"))):
        lok = sppg[urut % len(sppg)]
        kom = komoditas[urut % len(komoditas)]
        did, _ = await _ambil_atau_buat(
            session,
            Decision,
            f"decision:histori:{umur}",
            dict(
                decision_type="regional_balance",
                status=status,
                proposed_by="agent:regional_balance",
                verified_by="verifier:otomatis",
                verifier_note="Audit berkala: selisih stok antar-SPPG masih dalam ambang.",
                iteration=1,
                demo_case="extra:histori",
                source_location_id=lok.id,
                target_location_id=sppg[(urut + 2) % len(sppg)].id,
                supplier_id=pemasok[urut % len(pemasok)].id,
                commodity_id=kom.id,
                quantity_kg=Decimal("310.00"),
                safe_delivered_cost=Decimal("9876.54"),
                cost_breakdown={"harga": 9000, "angkut": 700, "risiko": 176.54},
                expires_at=now + timedelta(days=30),
                generated_at=now - timedelta(days=umur),
                created_at=now - timedelta(days=umur),
                origin="demo",
            ),
        )
        jumlah["decisions"] += 1
        await _ambil_atau_buat(
            session,
            Approval,
            f"approval:histori:{umur}",
            dict(
                decision_id=did,
                approved_by=kepala.id,
                approved=status == "executed",
                approved_at=now - timedelta(days=umur, hours=2),
                comment=(
                    "Disetujui; pengiriman sudah diterima SPPG tujuan."
                    if status == "executed"
                    else "Disetujui dengan catatan: pantau susulan minggu depan."
                ),
            ),
        )
        jumlah["approvals"] += 1
        # Jejak untuk keputusan historis: tanpa ini dua baris `extra:histori`
        # tampil tanpa penalaran dan gate invariant menolaknya (2 yatim).
        await _ambil_atau_buat(
            session,
            AgentTrace,
            f"trace-histori:{umur}",
            dict(
                decision_id=did,
                step_name="DETECT",
                tool_called="demand.snapshot",
                input_summary={"komoditas": kom.name, "hari_lalu": umur},
                output_summary={"hasil": "terdeteksi", "catatan": "audit berkala"},
                duration_ms=650,
                run_id=stable_uuid("extra", "run-histori", str(umur)),
                agent_name=None,
                confidence=0.78,
                citations=[{"source": "extra", "ref": "histori"}],
                step_at=now - timedelta(days=umur, hours=3),
            ),
        )
        jumlah["agent_traces"] += 1

    # ------------------------------- kiriman yang SEDANG DI JALAN (lapisan peta)
    # Jalur "Siapkan data demo" (demo_template) memberangkatkan sebagian batch
    # memakai durasi rute dari cache OSRM, sehingga peta menampilkan truk yang
    # bergerak. Jalur `init-demo` tidak melakukannya: terukur 124 kiriman aktif
    # tetapi journey `di_jalan` = 0, jadi selama demo tidak ada satu pun truk
    # bergerak walau 114 rute sudah punya geometri. Di sini aturan yang sama
    # diterapkan memakai cache yang sudah ada (tanpa memanggil OSRM).
    # Cache rute dibersihkan bersama tabel bisnis lain di awal init-demo, jadi
    # tanpa langkah ini peta kehilangan SELURUH garis jalur (terukur: road 114
    # -> 0 setelah init-demo, hanya tombol "Siapkan data demo" yang menyinkronkan
    # ulang). Sinkronisasi memakai fungsi yang sama dengan tombol itu; kalau OSRM
    # mati, init-demo tetap lanjut tanpa garis dan alasannya tercatat.
    from app.api.demo import _sync_routes_aman
    from app.core.road_route import route_key
    from app.models.road_routes import RoadRoute

    _, galat_rute = await _sync_routes_aman(now)
    if galat_rute:
        jumlah["rute_galat"] = 1

    kandidat = (
        await session.execute(
            select(Batch)
            .where(
                Batch.usable_until >= now,
                Batch.supplier_id.is_not(None),
                Batch.location_id.is_not(None),
                Batch.quarantine_reason.is_(None),
                Batch.safety_status != "fail",
            )
            .order_by(Batch.quantity_kg.desc())
        )
    ).scalars().all()

    kunci: dict[str, bool] = {}
    for b in kandidat:
        pemasok = await session.get(Supplier, b.supplier_id)
        lokasi = await session.get(Location, b.location_id)
        if pemasok is None or lokasi is None:
            continue
        if pemasok.latitude is None or lokasi.latitude is None:
            continue
        kunci[
            route_key(
                float(pemasok.latitude), float(pemasok.longitude),
                float(lokasi.latitude), float(lokasi.longitude),
            )
        ] = True

    durasi: dict[str, float] = {}
    if kunci:
        for r in (
            await session.execute(select(RoadRoute).where(RoadRoute.route_key.in_(list(kunci))))
        ).scalars():
            durasi[r.route_key] = float(r.duration_s or 0)

    # Urutkan menurut DURASI rute terpanjang, bukan berat: kiriman 5-15 menit
    # sudah "tiba" sebelum juri sempat melihat peta (terukur: 8 truk di jalan
    # saat semai, tinggal 1 beberapa jam kemudian — dan per komoditas 0). Rute
    # antarkota (1-3 jam) membuat truk tetap bergerak sepanjang sesi demo.
    calon_berangkat: list[tuple[float, Batch]] = []
    for b in kandidat:
        pemasok = await session.get(Supplier, b.supplier_id)
        lokasi = await session.get(Location, b.location_id)
        if pemasok is None or lokasi is None:
            continue
        if pemasok.latitude is None or lokasi.latitude is None:
            continue
        d = durasi.get(
            route_key(
                float(pemasok.latitude), float(pemasok.longitude),
                float(lokasi.latitude), float(lokasi.longitude),
            ),
            0.0,
        )
        if d <= 0:
            continue
        calon_berangkat.append((d, b))

    calon_berangkat.sort(key=lambda pasangan: pasangan[0], reverse=True)
    diberangkatkan = 0
    for d, b in calon_berangkat:
        if diberangkatkan >= 8:
            break
        # 35% perjalanan sudah ditempuh: truk terlihat di tengah rute, bukan
        # menempel di titik asal, dan masih "di jalan" saat layar dibuka.
        b.dispatched_at = now - timedelta(seconds=d * 0.35)
        diberangkatkan += 1
    jumlah["batches_diberangkatkan"] = diberangkatkan

    await session.commit()
    return dict(jumlah)
