"""Data demo LENGKAP untuk Jakarta (permintaan pemilik 19 Okt 2026).

Latar: akun demo Jakarta punya celah indikator — review 7 agen "tidak tersedia"
(`agent_traces.agent_name` NULL), tidak ada pemasok yang dieksklusi, seluruh
ledger orphan ("0 dari 2350 blok masih tertaut"), beberapa metrik KPI 24 jam
`no_data`, dan volume data terlalu tipis untuk terlihat seperti konsol nyata.

Aturan modul ini (sengaja sama dengan `demo_activity.py`):

1. **Semua baris ber-`origin='demo'`** dan ber-Id DETERMINISTIK (UUID5), jadi
   menjalankan ulang tidak menggandakan apa pun. Baris kanonik (`origin='seed'`)
   tidak disentuh — tes yang memaku seed tetap sah.
2. **Relatif ke `now`**, bukan tanggal tetap: turunkan tanggal dari jam sekarang
   supaya metrik "hari ini"/24 jam benar-benar berisi.
3. **Tidak mengarang di luar skema**: nilai status/tipe mengikuti CHECK constraint
   (`decisions.status`, `safety_status`, `certification_status`, dst.).
4. **Ledger dibangun ulang dari keputusan yang benar-benar ada**, bukan dibiarkan
   menunjuk entitas yang sudah hilang. Rantai hash tetap utuh karena setiap blok
   ditulis lewat `append_block`.

Jalankan: `python -m app.seed.jakarta_lengkap`
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import create_engine, create_session_maker
from app.models import (
    AgentTrace,
    Approval,
    Batch,
    BatchReceipt,
    Commodity,
    Decision,
    DecisionEvidence,
    DeliveryEvent,
    DemandRecord,
    DisposalEvent,
    Location,
    MenuPlan,
    PriceSignal,
    SapMockPurchaseOrder,
    Supplier,
    SupplierExclusion,
    SupplyRecord,
    User,
)
from app.seed.seed_data import _seed_database_url

WIB = timezone(timedelta(hours=7))
TAG = "jakarta-lengkap"

#: Kota yang diberi pasokan berlebih supaya ada pasangan surplus→kekurangan.
KOTA_SURPLUS = ("Cianjur", "Bandung", "Bogor")

#: Kebutuhan harian per komoditas (kg) untuk SPPG Jakarta 1.200 porsi.
DEMAND_HARIAN = {
    "telur": Decimal("1060"),
    "ayam": Decimal("720"),
    "wortel": Decimal("480"),
    "beras": Decimal("950"),
}

#: Pasokan harian per komoditas (kg) di Jakarta — sedikit di bawah kebutuhan,
#: jadi status lokasi tetap "warning" sesuai aturan `location_status`.
SUPPLY_HARIAN = {
    "telur": Decimal("288"),
    "ayam": Decimal("203"),
    "wortel": Decimal("154"),
    "beras": Decimal("410"),
}

#: Harga acuan PIHPS & deviasi kutipan pemasok (bukan nol: metrik deviasi butuh
#: selisih yang terukur, bukan kesempurnaan).
HARGA = {
    "telur": (Decimal("30500"), Decimal("0.010")),
    "ayam": (Decimal("41500"), Decimal("0.004")),
    "wortel": (Decimal("23500"), Decimal("0.014")),
    "beras": (Decimal("13400"), Decimal("0.006")),
}

UMUR_SIMPAN = {"telur": 28, "ayam": 5, "wortel": 21, "beras": 180}

#: Tujuh worker + supervisor untuk panel review 7 agen (lib/agent-swarm.ts).
PEKERJA = (
    ("supply", "DETECT", "supply_agent"),
    ("demand", "PREDICT", "demand_agent"),
    ("freshness", "VERIFY", "freshness_agent"),
    ("safety", "VERIFY", "safety_agent"),
    ("price", "OPTIMIZE", "price_agent"),
    ("logistics", "OPTIMIZE", "logistics_agent"),
    ("evidence", "TRACE", "evidence_agent"),
)

MITRA_LIMBAH = ("Bank Sampah Melati", "Komposter Komunitas Cakung", "PT Biogas Nusantara")


#: Kata kunci nama pemasok per komoditas. Pemasok "Ayam Segar" yang mengirim
#: beras terbaca sebagai data salah, bukan variasi — pasangan ini dipilih dari
#: nama, bukan dari urutan daftar.
KATA_PEMASOK = {
    "telur": ("telur",),
    "ayam": ("ayam",),
    "beras": ("beras",),
    "wortel": ("sayur", "wortel"),
}


def _pemasok_untuk(komoditas: str, pemasok: list, indeks: int):
    """Pemasok yang namanya cocok dengan komoditas.

    Urutan pilihan: (a) nama memuat kata komoditas; (b) nama TIDAK memuat kata
    komoditas lain (pemasok umum, mis. "CV Sumber Rejeki"); (c) daftar penuh.
    Tanpa (b), "CV Sayur Berastagi" bisa mengirim beras karena hanya jatuh ke
    daftar penuh saat tidak ada kata "beras" — dan itu terbaca sebagai salah data.
    """
    kata = KATA_PEMASOK.get(str(komoditas).lower(), ())
    lain = {k for nama, daftar in KATA_PEMASOK.items() if nama != komoditas for k in daftar}
    cocok = [p for p in pemasok if any(k in p.name.lower() for k in kata)]
    netral = [
        p
        for p in pemasok
        if not any(k in p.name.lower() for k in kata) and not any(k in p.name.lower() for k in lain)
    ]
    daftar = cocok or netral or pemasok
    return daftar[indeks % len(daftar)] if daftar else None


def _id(*bagian: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"mcg:{TAG}:" + ":".join(bagian))


def _hari(now: datetime) -> date:
    return now.astimezone(WIB).date()


def _jam(now: datetime, hari: date, jam: int, menit: int = 0) -> datetime:
    """Titik waktu WIB pada tanggal tertentu, dikembalikan sebagai UTC."""
    return datetime(hari.year, hari.month, hari.day, jam, menit, tzinfo=WIB).astimezone(
        timezone.utc
    )


async def _peta(session: AsyncSession) -> tuple[dict, dict, list, dict]:
    lokasi = {loc.name: loc for loc in (await session.execute(select(Location))).scalars()}
    komoditas = {c.name: c for c in (await session.execute(select(Commodity))).scalars()}
    pemasok = list((await session.execute(select(Supplier).order_by(Supplier.name))).scalars())
    pengguna = {u.email: u for u in (await session.execute(select(User))).scalars()}
    return lokasi, komoditas, pemasok, pengguna


# ---------------------------------------------------------------------------
# 1. Permintaan (semua lokasi) — "kebutuhan jaringan belum lengkap" hilang
# ---------------------------------------------------------------------------
async def seed_demand(session: AsyncSession, now: datetime) -> dict:
    lokasi, komoditas, _, _ = await _peta(session)
    hari = _hari(now)
    jumlah = 0
    for nama_lokasi, loc in lokasi.items():
        for nama_komoditas, com in komoditas.items():
            dasar = DEMAND_HARIAN.get(nama_komoditas)
            if dasar is None:
                continue
            # Skala per kota: Jakarta 100%, kota lain 35–70% (deterministik).
            faktor = Decimal(100 if nama_lokasi == "Jakarta" else 35 + (len(nama_lokasi) * 7) % 36)
            for mundur in range(0, 15):
                tanggal = hari - timedelta(days=mundur)
                kunci = _id("demand", nama_lokasi, nama_komoditas, tanggal.isoformat())
                ada = await session.get(DemandRecord, kunci)
                nilai = (dasar * faktor / 100).quantize(Decimal("0.01"))
                if ada is None:
                    session.add(
                        DemandRecord(
                            id=kunci,
                            location_id=loc.id,
                            commodity_id=com.id,
                            quantity_kg=nilai,
                            needed_by=_jam(now, tanggal, 18, 0),
                            recorded_at=_jam(now, tanggal, 6, 0),
                            origin="demo",
                            generated_at=now,
                        )
                    )
                else:
                    # Tanggal digeser supaya "hari ini" tetap berisi setelah hari berganti.
                    ada.needed_by = _jam(now, tanggal, 18, 0)
                    ada.recorded_at = _jam(now, tanggal, 6, 0)
                    ada.quantity_kg = nilai
                    ada.generated_at = now
                jumlah += 1
    await session.flush()
    return {"demand": jumlah}


# ---------------------------------------------------------------------------
# 2. Pasokan harian (Jakarta + kota surplus)
# ---------------------------------------------------------------------------
async def seed_supply(session: AsyncSession, now: datetime) -> dict:
    lokasi, komoditas, _, _ = await _peta(session)
    hari = _hari(now)
    jumlah = 0
    for mundur in range(0, 21):
        tanggal = hari - timedelta(days=mundur)
        for nama_komoditas, dasar in SUPPLY_HARIAN.items():
            com = komoditas.get(nama_komoditas)
            if com is None:
                continue
            for slot, (jam, pengali) in enumerate(((6, Decimal("1.0")), (14, Decimal("0.45")))):
                for nama_lokasi, loc in lokasi.items():
                    if nama_lokasi != "Jakarta" and nama_lokasi not in KOTA_SURPLUS:
                        continue
                    skala = Decimal("1") if nama_lokasi == "Jakarta" else Decimal("2.6")
                    kunci = _id(
                        "supply", nama_lokasi, nama_komoditas, tanggal.isoformat(), str(slot)
                    )
                    nilai = (dasar * pengali * skala).quantize(Decimal("0.01"))
                    ada = await session.get(SupplyRecord, kunci)
                    waktu = _jam(now, tanggal, jam, 20)
                    if ada is None:
                        session.add(
                            SupplyRecord(
                                id=kunci,
                                location_id=loc.id,
                                commodity_id=com.id,
                                quantity_kg=nilai,
                                recorded_at=waktu,
                                source="mock_sap",
                                origin="demo",
                                generated_at=now,
                            )
                        )
                    else:
                        ada.quantity_kg = nilai
                        ada.recorded_at = waktu
                        ada.generated_at = now
                    jumlah += 1
    await session.flush()
    return {"supply": jumlah}


# ---------------------------------------------------------------------------
# 3. Batch: 40 baris Jakarta dengan tiga keadaan + suhu + kedaluwarsa
# ---------------------------------------------------------------------------
async def seed_batches(session: AsyncSession, now: datetime) -> dict:
    lokasi, komoditas, pemasok, _ = await _peta(session)
    jakarta = lokasi["Jakarta"]
    hari = _hari(now)
    if not pemasok:
        return {"batch": 0, "alasan": "pemasok belum ada"}

    jumlah = 0
    for indeks in range(40):
        nama_komoditas = ("telur", "ayam", "wortel", "beras")[indeks % 4]
        com = komoditas.get(nama_komoditas)
        if com is None:
            continue
        # Batch WAJIB dipasok pemasok di hub yang SAMA dan komoditas yang SAMA.
        # Memilih berdasarkan nama saja (perilaku lama) bisa mengirim telur
        # Surabaya ke Jakarta — melanggar aturan jangkauan pemasok→SPPG.
        # Utamakan pemasok yang SUDAH punya batch kanonik untuk pasangan ini;
        # menambah pemasok kedua ke pasangan bersupplier tunggal melanggar
        # kontrak `resolve_binding` (lihat test_demo_batch_pemasok_tunggal).
        kanonik_tersedia = set(
            (
                await session.execute(
                    select(Batch.supplier_id).where(
                        Batch.location_id == jakarta.id,
                        Batch.commodity_id == com.id,
                        Batch.origin != "demo",
                    )
                )
            ).scalars()
        )
        # Urutkan kandidat agar penugasan sama di setiap seed (dulu mengandalkan
        # urutan SELECT yang bisa berubah setelah delete/reseed).
        kandidat = sorted(
            [
                p
                for p in pemasok
                if p.location_id == jakarta.id and p.commodity_id == com.id
            ],
            key=lambda p: p.name,
        )
        if kanonik_tersedia:
            kandidat = [p for p in kandidat if p.id in kanonik_tersedia]
        # Rotasi per KEMUNCULAN komoditas (`indeks // 4`), bukan indeks global:
        # semua batch telur berindeks genap, sehingga `indeks % len` selalu
        # memilih pemasok pertama dan pemasok lain tidak pernah mendapat batch.
        sup = kandidat[(indeks // 4) % len(kandidat)] if kandidat else None
        if sup is None:
            continue
        mundur = indeks % 18
        tanggal = hari - timedelta(days=mundur)
        panen = _jam(now, tanggal, 4 + (indeks % 4), 30)
        # Sebaran keadaan: 1 dari 7 gagal, 1 dari 6 needs_verification, sisanya
        # pass. `pending` ("Belum diuji") TIDAK dibuat di sini: barang pending
        # khusus berasal dari blok "baru datang" di bawah, supaya kartu
        # Penerimaan hanya berisi kedatangan yang memang belum dinilai.
        if indeks % 7 == 3:
            safety = "fail"
        elif indeks % 6 == 4:
            safety = "needs_verification"
        else:
            safety = "pass"
        segar = Decimal("0.62") + Decimal(indeks % 35) / 100
        if segar > Decimal("0.98"):
            segar = Decimal("0.98")
        umur = UMUR_SIMPAN.get(nama_komoditas, 14)
        # Batch paling baru sengaja kedaluwarsa HARI INI (agenda "batch kedaluwarsa").
        sisa_hari = 0 if indeks % 9 == 0 else (umur - mundur / 2)
        sisa_hari = max(0.0, float(sisa_hari))
        usable = now + timedelta(days=sisa_hari)
        suhu = [
            {"at": panen.isoformat(), "temperature_c": 3.8 + (indeks % 3)},
            {"at": (panen + timedelta(hours=3)).isoformat(), "temperature_c": 4.2},
            {
                "at": (panen + timedelta(hours=6)).isoformat(),
                # Satu batch ayam sengaja menyimpang (> 8 °C) — kasus merah narasi.
                "temperature_c": 12.5 if (indeks == 5 and nama_komoditas == "ayam") else 4.6,
            },
        ]
        kunci = _id("batch", str(indeks))
        ada = await session.get(Batch, kunci)
        nilai = dict(
            commodity_id=com.id,
            location_id=jakarta.id,
            supplier_id=sup.id,
            quantity_kg=Decimal(60 + (indeks * 17) % 240),
            harvested_at=panen,
            temperature_log=suhu,
            certification_status=("haccp", "hygiene", "none")[indeks % 3],
            freshness_score=segar,
            safety_status=safety,
            usable_until=usable,
            origin="demo",
            generated_at=now,
            dispatched_at=panen + timedelta(hours=2),
        )
        if ada is None:
            session.add(Batch(id=kunci, **nilai))
        else:
            for k, v in nilai.items():
                setattr(ada, k, v)
        jumlah += 1

    # Barang baru datang TIDAK dibuat di sini: jalur yang dipakai "Siapkan
    # data demo" adalah `seed/demo_activity.py` (punya namespace id sendiri).
    # Blok serupa di sini dulu membuat enam batch pending (dua namespace) dan
    # memicu duplikat saat sesi disiapkan.
    await session.flush()
    return {"batch": jumlah}


async def seed_receipts(session: AsyncSession, now: datetime) -> dict:
    jakarta_kepala = (await session.execute(
        select(User).where(User.email == "sppg.head@demo.local")
    )).scalar_one_or_none()
    if jakarta_kepala is None:
        return {"receipt": 0}
    batch = list(
        (
            await session.execute(
                select(Batch).where(Batch.origin == "demo", Batch.safety_status == "pass").limit(12)
            )
        ).scalars()
    )
    jumlah = 0
    for indeks, b in enumerate(batch):
        kunci = _id("receipt", str(b.id))
        ada = await session.get(BatchReceipt, kunci)
        nilai = dict(
            batch_id=b.id,
            checked={
                "suhu": 4.2,
                "kemasan": "utuh",
                "berat_kg": float(b.quantity_kg),
                "catatan": "sesuai spesifikasi terima",
            },
            other_note=None,
            recorded_by=jakarta_kepala.id,
            recorded_at=now - timedelta(hours=6 + indeks),
        )
        if ada is None:
            session.add(BatchReceipt(id=kunci, **nilai))
        else:
            for k, v in nilai.items():
                setattr(ada, k, v)
        jumlah += 1
    await session.flush()
    return {"receipt": jumlah}


# ---------------------------------------------------------------------------
# 4. Harga harian: acuan LEBIH DULU, kutipan sesudahnya (urutan penting)
# ---------------------------------------------------------------------------
async def seed_prices(session: AsyncSession, now: datetime) -> dict:
    lokasi, komoditas, pemasok, _ = await _peta(session)
    jakarta = lokasi["Jakarta"]
    hari = _hari(now)
    jumlah = 0
    for mundur in range(0, 21):
        tanggal = hari - timedelta(days=mundur)
        for nama_komoditas, (acuan, deviasi) in HARGA.items():
            com = komoditas.get(nama_komoditas)
            if com is None:
                continue
            kunci_acuan = _id("harga", nama_komoditas, tanggal.isoformat(), "acuan")
            waktu_acuan = _jam(now, tanggal, 5, 30)
            ada = await session.get(PriceSignal, kunci_acuan)
            nilai = dict(
                location_id=jakarta.id,
                commodity_id=com.id,
                price_per_kg=acuan,
                recorded_at=waktu_acuan,
                source="pihps_reference",
                origin="demo",
                generated_at=now,
            )
            if ada is None:
                session.add(PriceSignal(id=kunci_acuan, **nilai))
            else:
                for k, v in nilai.items():
                    setattr(ada, k, v)
            jumlah += 1

            kutipan = (
                (7, pemasok[0] if pemasok else None),
                (11, pemasok[1] if len(pemasok) > 1 else None),
            )
            for slot, (jam, sup) in enumerate(kutipan):
                if sup is None:
                    continue
                kunci = _id("harga", nama_komoditas, tanggal.isoformat(), f"kutipan-{slot}")
                harga = (acuan * (1 + deviasi + Decimal(slot) / 200)).quantize(Decimal("0.01"))
                ada = await session.get(PriceSignal, kunci)
                nilai = dict(
                    location_id=jakarta.id,
                    commodity_id=com.id,
                    price_per_kg=harga,
                    recorded_at=_jam(now, tanggal, jam, 15),
                    source="supplier_quote",
                    supplier_id=sup.id,
                    origin="demo",
                    generated_at=now,
                )
                if ada is None:
                    session.add(PriceSignal(id=kunci, **nilai))
                else:
                    for k, v in nilai.items():
                        setattr(ada, k, v)
                jumlah += 1
    await session.flush()
    return {"harga": jumlah}


# ---------------------------------------------------------------------------
# 5. Rencana menu + kiriman (agenda "Hari Ini")
# ---------------------------------------------------------------------------
async def seed_menu(session: AsyncSession, now: datetime) -> dict:
    lokasi, _, _, _ = await _peta(session)
    jakarta = lokasi["Jakarta"]
    hari = _hari(now)
    rencana = 0
    kiriman = 0
    for geser in range(-7, 15):
        tanggal = hari + timedelta(days=geser)
        porsi = 1180 + (geser + 7) * 7
        # Kunci alami (lokasi, tanggal) — seed kanonik sudah punya baris untuk
        # sebagian tanggal, dan id-nya bukan milik modul ini.
        menu = (
            await session.execute(
                select(MenuPlan).where(
                    MenuPlan.location_id == jakarta.id, MenuPlan.plan_date == tanggal
                )
            )
        ).scalar_one_or_none()
        kunci = menu.id if menu is not None else _id("menu", tanggal.isoformat())
        if menu is None:
            session.add(
                MenuPlan(
                    id=kunci,
                    location_id=jakarta.id,
                    plan_date=tanggal,
                    planned_portions=porsi,
                    origin="demo",
                    generated_at=now,
                )
            )
        else:
            menu.planned_portions = porsi
            menu.generated_at = now
        rencana += 1

        # Kiriman hanya untuk hari yang sudah/sedang berjalan.
        if geser <= 0:
            kunci_kirim = _id("kiriman", tanggal.isoformat())
            kiriman_ada = await session.get(DeliveryEvent, kunci_kirim)
            nilai = dict(
                menu_plan_id=kunci,
                delivered_portions=porsi - (12 if geser == 0 else 6),
                status="delivered",
                delivered_at=_jam(now, tanggal, 10, 30),
                origin="demo",
                generated_at=now,
            )
            if kiriman_ada is None:
                session.add(DeliveryEvent(id=kunci_kirim, **nilai))
            else:
                for k, v in nilai.items():
                    setattr(kiriman_ada, k, v)
            kiriman += 1
    await session.flush()
    return {"menu": rencana, "kiriman": kiriman}


async def seed_disposal(session: AsyncSession, now: datetime) -> dict:
    lokasi, komoditas, _, _ = await _peta(session)
    jakarta = lokasi["Jakarta"]
    hari = _hari(now)
    jumlah = 0
    for mundur in range(0, 21):
        tanggal = hari - timedelta(days=mundur)
        for slot, nama_komoditas in enumerate(("wortel", "ayam")):
            com = komoditas.get(nama_komoditas)
            if com is None:
                continue
            kunci = _id("limbah", tanggal.isoformat(), nama_komoditas)
            nilai = dict(
                location_id=jakarta.id,
                commodity_id=com.id,
                quantity_kg=Decimal("4.20") + Decimal((mundur + slot) % 9),
                reason=("kedaluwarsa" if slot == 0 else "rusak saat pengiriman"),
                disposed_at=_jam(now, tanggal, 16, 45),
                origin="demo",
                generated_at=now,
                partner_name=MITRA_LIMBAH[(mundur + slot) % len(MITRA_LIMBAH)],
            )
            ada = await session.get(DisposalEvent, kunci)
            if ada is None:
                session.add(DisposalEvent(id=kunci, **nilai))
            else:
                for k, v in nilai.items():
                    setattr(ada, k, v)
            jumlah += 1
    await session.flush()
    return {"limbah": jumlah}


# ---------------------------------------------------------------------------
# 6. Keputusan lengkap: approval, bukti konsisten, jejak 7 agen, PO
# ---------------------------------------------------------------------------
STATUS_RENCANA = (
    ["proposed"] * 8
    + ["pending_approval"] * 7
    + ["approved"] * 4
    + ["executed"] * 7
    + ["rejected"] * 3
    + ["verifier_flagged"] * 1
)

TIPE_RENCANA = (
    "regional_balance",
    "regional_balance",
    "regional_balance",
    "safety_disruption",
    "price_anomaly",
)


async def seed_decisions(session: AsyncSession, now: datetime) -> dict:
    lokasi, komoditas, pemasok, pengguna = await _peta(session)
    jakarta = lokasi["Jakarta"]
    kepala = pengguna.get("sppg.head@demo.local")
    gizi = pengguna.get("sppg.nutritionist@demo.local")
    if kepala is None or gizi is None:
        return {"keputusan": 0, "alasan": "akun demo Jakarta tidak ada"}

    sumber = lokasi.get("Cianjur") or jakarta
    jumlah = {"keputusan": 0, "approval": 0, "bukti": 0, "jejak": 0, "po": 0}

    for indeks, status in enumerate(STATUS_RENCANA):
        nama_komoditas = ("telur", "ayam", "wortel", "beras")[indeks % 4]
        com = komoditas.get(nama_komoditas)
        if com is None:
            continue
        kunci = _id("keputusan", str(indeks))
        dibuat = now - timedelta(hours=(indeks * 3) % 48 + 1)
        tipe = TIPE_RENCANA[indeks % len(TIPE_RENCANA)]
        kuantitas = Decimal(120 + (indeks * 37) % 700)
        biaya = (kuantitas * Decimal("25600")).quantize(Decimal("0.01"))
        aktif = status in ("proposed", "pending_approval", "approved", "verifier_flagged")
        nilai = dict(
            decision_type=tipe,
            status=status,
            proposed_by="supervisor_agent",
            verified_by="verifier_agent" if status != "proposed" else None,
            verifier_note="consistent" if status != "proposed" else None,
            source_location_id=sumber.id,
            target_location_id=jakarta.id,
            commodity_id=com.id,
            quantity_kg=kuantitas,
            safe_delivered_cost=biaya,
            cost_breakdown={"harga_beli": str(biaya), "logistik": "486000"},
            expires_at=(
                now + timedelta(hours=6 + (indeks % 30))
                if aktif
                else dibuat + timedelta(hours=8)
            ),
            created_at=dibuat,
            rejection_reason="melebihi tenggat jendela" if status == "rejected" else None,
            iteration=1,
            origin="demo",
            generated_at=now,
        )
        ada = await session.get(Decision, kunci)
        if ada is None:
            session.add(Decision(id=kunci, **nilai))
        else:
            for k, v in nilai.items():
                setattr(ada, k, v)
        jumlah["keputusan"] += 1
        # FK ditulis tanpa relationship, jadi keputusan harus sudah ada di DB
        # sebelum approval/bukti/PO menunjuknya.
        await session.flush()

        # ------------------------------------------------ approvals
        if status in ("approved", "executed", "rejected"):
            for urut, penyetuju in enumerate((kepala, gizi)):
                kunci_ap = _id("approval", str(indeks), str(urut))
                setuju = not (status == "rejected" and urut == 1)
                waktu = dibuat + timedelta(minutes=25 + urut * 10)
                ada_ap = await session.get(Approval, kunci_ap)
                nilai_ap = dict(
                    decision_id=kunci,
                    approved_by=penyetuju.id,
                    approved=setuju,
                    comment=None if setuju else "harga di atas acuan pasar",
                    approved_at=waktu,
                )
                if ada_ap is None:
                    session.add(Approval(id=kunci_ap, **nilai_ap))
                else:
                    for k, v in nilai_ap.items():
                        setattr(ada_ap, k, v)
                jumlah["approval"] += 1

        # ------------------------------------------------ bukti (3 jenis, konsisten)
        for urut, jenis in enumerate(("sap_purchase_order", "temperature", "market_price")):
            kunci_ev = _id("bukti", str(indeks), jenis)
            ada_ev = await session.get(DecisionEvidence, kunci_ev)
            nilai_ev = dict(
                decision_id=kunci,
                evidence_type=jenis,
                payload={
                    "decision_id": str(kunci),
                    "sumber": "demo-jakarta",
                    "komoditas": nama_komoditas,
                    "kuantitas_kg": str(kuantitas),
                },
                # is_consistent WAJIB True: metrik Evidence Completeness membacanya.
                is_consistent=True,
                recorded_at=dibuat + timedelta(minutes=5 + urut * 2),
            )
            if ada_ev is None:
                session.add(DecisionEvidence(id=kunci_ev, **nilai_ev))
            else:
                for k, v in nilai_ev.items():
                    setattr(ada_ev, k, v)
            jumlah["bukti"] += 1

        # ------------------------------------------------ jejak 7 agen + supervisor
        run_id = _id("run", str(indeks))
        # `agent_name` HARUS kunci worker apa adanya ("supply", "demand", …):
        # `lib/agent-swarm.ts` mencocokkan nama itu untuk delapan kartu. Memakai
        # "supply_agent" membuat panel berkata "Belum ada review 7 agen" walau
        # barisnya ada (dan itu yang terjadi sebelum perbaikan ini).
        urutan = [("supervisor", "DECIDE", "supervisor", 0)]
        urutan += [(k, s, k, i) for i, (k, s, a) in enumerate(PEKERJA)]
        # ACT wajib ada untuk keputusan yang sudah dieksekusi: metrik Decision
        # Time membaca rentang DETECT..ACT + PO terbit. Tanpa baris ini kartu itu
        # hanya punya dua sampel lama.
        if status in ("executed", "approved"):
            urutan.append(("act", "ACT", "supervisor", 8))
        for key, tahap, agen, urut in urutan:
            kunci_tr = _id("jejak", str(indeks), key)
            ada_tr = await session.get(AgentTrace, kunci_tr)
            nilai_tr = dict(
                decision_id=kunci,
                step_name=tahap,
                tool_called=f"{key}_tool",
                input_summary={"decision_id": str(kunci), "agen": agen},
                output_summary={
                    "status": "ok",
                    "agent": key,
                    "ringkas": f"{agen.replace('_agent', '')} selesai memeriksa {nama_komoditas}",
                },
                duration_ms=900 + (indeks * 137 + urut * 313) % 5200,
                step_at=dibuat + timedelta(minutes=2 + urut * 2),
                run_id=run_id,
                agent_name=agen,
                confidence=round(0.72 + ((indeks + urut) % 20) / 100, 2),
                citations=[
                    {"source": "sap_mock", "ref": f"PO-{indeks}-{urut}"},
                    {"source": "sensor_suhu", "ref": f"batch-{indeks % 40}"},
                ],
            )
            if ada_tr is None:
                session.add(AgentTrace(id=kunci_tr, **nilai_tr))
            else:
                for k, v in nilai_tr.items():
                    setattr(ada_tr, k, v)
            jumlah["jejak"] += 1

        # ------------------------------------------------ PO untuk keputusan dieksekusi
        if status == "executed":
            from app.core.po_number import nomor_po

            kunci_po = _id("po", str(indeks))
            harga = HARGA.get(nama_komoditas, (Decimal("20000"), Decimal("0")))[0]
            ada_po = await session.get(SapMockPurchaseOrder, kunci_po)
            nilai_po = dict(
                po_number=nomor_po(kunci),
                supplier_id=(
                    _pemasok_untuk(nama_komoditas, pemasok, indeks).id
                    if pemasok
                    else None
                ),
                material_number=f"MAT-{nama_komoditas.upper()}",
                ordered_quantity=kuantitas,
                price=harga,
                decision_id=kunci,
                status="submitted",
                created_at=now - timedelta(hours=indeks % 6 + 1),
            )
            # Rapikan PO yang lahir sebelum perbaikan: kode bahan terpotong
            # (`MAT-BERA`) atau pemasok tidak sesuai komoditas.
            if ada_po is not None and nilai_po["supplier_id"] is not None:
                if ada_po.material_number != nilai_po["material_number"]:
                    ada_po.material_number = nilai_po["material_number"]
                if ada_po.supplier_id != nilai_po["supplier_id"]:
                    ada_po.supplier_id = nilai_po["supplier_id"]

            if nilai_po["supplier_id"] is not None:
                if ada_po is None:
                    session.add(SapMockPurchaseOrder(id=kunci_po, **nilai_po))
                    jumlah["po"] += 1
                else:
                    for k, v in nilai_po.items():
                        setattr(ada_po, k, v)

    # PO lama (dibuat lewat aksi manual sebelum perbaikan) bisa membawa kode
    # bahan terpotong `MAT-BERA`/`MAT-TELU` dan pemasok lintas komoditas.
    # Ratakan dari komoditas keputusan, bukan dari tebakan material.
    for po, nama in await session.execute(
        select(SapMockPurchaseOrder, Commodity.name)
        .join(Decision, Decision.id == SapMockPurchaseOrder.decision_id)
        .join(Commodity, Commodity.id == Decision.commodity_id)
        .where(SapMockPurchaseOrder.decision_id.isnot(None))
    ):
        bahan = f"MAT-{nama.upper()}"
        if po.material_number != bahan:
            po.material_number = bahan
        sup = _pemasok_untuk(nama, pemasok, abs(hash(po.po_number)) % len(pemasok))
        if sup is not None and po.supplier_id != sup.id:
            po.supplier_id = sup.id

    await session.flush()
    return jumlah


async def seed_exclusions(session: AsyncSession, now: datetime) -> dict:
    """Tiga riwayat eksklusi: dua aktif, satu sudah dicabut (bukan nol semua).

    Pemilihan pemasok DETERMINISTIK dan SESUAI ALASAN (20 Okt 2026): slot pertama
    harus pemasok AYAM Jakarta (alasan "batch ayam gagal uji antibiotik"), bukan
    pemasok sembarang yang kebetulan menempati urutan alfabet. Sebelumnya urutan
    alfabet dipakai apa adanya sehingga alasan ayam bisa menunjuk pemasok beras.
    """
    lokasi, komoditas, pemasok, pengguna = await _peta(session)
    jakarta = lokasi["Jakarta"]
    kepala = pengguna.get("sppg.head@demo.local")
    if kepala is None or len(pemasok) < 3:
        return {"eksklusi": 0}

    ayam = komoditas.get("ayam")
    jakarta_suppliers = [s for s in pemasok if s.location_id == jakarta.id]
    ayam_jakarta = [
        s for s in jakarta_suppliers if ayam is not None and s.commodity_id == ayam.id
    ]
    lain_jakarta = [
        s for s in jakarta_suppliers if ayam is None or s.commodity_id != ayam.id
    ]
    pilihan = list(ayam_jakarta[:1]) + lain_jakarta
    # Jaring pengaman: DB demo minimal punya cukup pemasok untuk tiga slot.
    for s in pemasok:
        if len(pilihan) >= 3:
            break
        if s not in pilihan:
            pilihan.append(s)
    if len(pilihan) < 3:
        return {"eksklusi": 0}

    rencana = (
        ("active", "batch ayam gagal uji antibiotik", 0),
        ("active", "suhu kiriman menyimpang 12,5 °C", 1),
        ("revoked", "tuduhan awal tidak terbukti setelah audit", 2),
    )
    jumlah = 0
    for urut, (status, alasan, slot) in enumerate(rencana):
        kunci_dec = _id("keputusan-eksklusi", str(urut))
        tipe = "supplier_exclusion" if status != "revoked" else "supplier_exclusion_restoration"
        dibuat = now - timedelta(days=3 + urut)
        ada_dec = await session.get(Decision, kunci_dec)
        nilai_dec = dict(
            decision_type=tipe,
            status="executed",
            proposed_by="supervisor_agent",
            verified_by="verifier_agent",
            verifier_note="consistent",
            source_location_id=jakarta.id,
            target_location_id=jakarta.id,
            commodity_id=None,
            quantity_kg=None,
            safe_delivered_cost=None,
            cost_breakdown={"alasan": alasan},
            expires_at=dibuat + timedelta(days=7),
            created_at=dibuat,
            iteration=1,
            origin="demo",
            generated_at=now,
        )
        if ada_dec is None:
            session.add(Decision(id=kunci_dec, **nilai_dec))
        else:
            for k, v in nilai_dec.items():
                setattr(ada_dec, k, v)
        await session.flush()

        kunci = _id("eksklusi", str(urut))
        ada = await session.get(SupplierExclusion, kunci)
        nilai = dict(
            supplier_id=pilihan[slot].id,
            scope_location_id=jakarta.id,
            status=status,
            reason=alasan,
            evidence_refs=[{"ref": f"batch-{slot}", "jenis": "uji_lab"}],
            source_decision_id=kunci_dec,
            proposed_by=kepala.id,
            approved_at=dibuat + timedelta(hours=2),
            activated_at=dibuat + timedelta(hours=2),
            revoked_at=dibuat + timedelta(hours=30) if status == "revoked" else None,
            revocation_reason="audit ulang membatalkan tuduhan" if status == "revoked" else None,
            created_at=dibuat,
            updated_at=now,
        )
        if ada is None:
            session.add(SupplierExclusion(id=kunci, **nilai))
        else:
            for k, v in nilai.items():
                setattr(ada, k, v)
        jumlah += 1
    await session.flush()
    return {"eksklusi": jumlah}


# ---------------------------------------------------------------------------
# 7. Ledger: bangun ulang dari keputusan yang BENAR-BENAR ada
# ---------------------------------------------------------------------------
async def rebuild_ledger(session: AsyncSession, now: datetime) -> dict:
    """Hapus blok yang menunjuk entitas hilang, lalu tulis ulang dari data nyata.

    Ledger demo sebelumnya berisi 2.350 blok sisa pengujian yang menunjuk
    keputusan yang sudah dihapus → panel integritas melaporkan "0 dari 2350 blok
    masih tertaut". Menambal `entity_id` akan mengarang tautan, jadi rantai
    dibangun ulang dari keputusan/PO yang ada. Hash tetap valid karena setiap
    blok ditulis berurutan lewat `append_block`.
    """
    from app.services.ledger_service import append_block

    await session.execute(text("DELETE FROM ledger_blocks"))
    await session.flush()

    keputusan = list(
        (
            await session.execute(
                select(Decision).where(Decision.target_location_id.is_not(None)).order_by(Decision.created_at)
            )
        ).scalars()
    )
    jumlah = 0
    for dec in keputusan:
        await append_block(
            session,
            action="decision.created",
            entity_id=dec.id,
            actor_id=None,
            payload={"decision_id": str(dec.id), "status": dec.status, "jenis": dec.decision_type},
        )
        jumlah += 1
        if dec.status in ("approved", "executed", "rejected"):
            await append_block(
                session,
                action="decision.approved",
                entity_id=dec.id,
                actor_id=None,
                payload={"decision_id": str(dec.id), "status": dec.status},
            )
            jumlah += 1
    po = list((await session.execute(select(SapMockPurchaseOrder))).scalars())
    for baris in po:
        # PO impor tanpa keputusan tidak punya entitas keputusan untuk ditautkan;
        # menulisnya menghasilkan blok orphan yang membuat rasio tautan < 100%.
        if baris.decision_id is None:
            continue
        await append_block(
            session,
            action="po.issued",
            entity_id=baris.decision_id or baris.id,
            actor_id=None,
            payload={"po_number": baris.po_number, "decision_id": str(baris.decision_id)},
        )
        jumlah += 1
    await session.flush()
    return {"blok_ledger": jumlah}


async def seed_all(session: AsyncSession, now: datetime) -> dict:
    hasil: dict = {}
    hasil |= await seed_demand(session, now)
    hasil |= await seed_supply(session, now)
    hasil |= await seed_batches(session, now)
    hasil |= await seed_receipts(session, now)
    hasil |= await seed_prices(session, now)
    hasil |= await seed_menu(session, now)
    hasil |= await seed_disposal(session, now)
    hasil |= await seed_decisions(session, now)
    hasil |= await seed_exclusions(session, now)
    await session.commit()
    hasil |= await rebuild_ledger(session, now)
    await session.commit()
    return hasil


async def main() -> None:
    now = datetime.now(timezone.utc)
    engine = create_engine(_seed_database_url())
    try:
        maker = create_session_maker(engine)
        async with maker() as session:
            hasil = await seed_all(session, now)
        print(f"jakarta_lengkap selesai pada {now.isoformat()}: {hasil}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
