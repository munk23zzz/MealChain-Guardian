"""Kegiatan demo: banyak kiriman berjalan di seluruh lokasi (permintaan pemilik).

Latar: pemilik ingin aplikasi "terlihat aktif" saat mencoba semua fitur di setiap
peran. Seed kanonik hanya memuat 9 batch (Jakarta), sehingga peta, papan kiriman,
dan pemilih kiriman terasa kosong walau angkanya benar.

Aturan yang dipegang:
1. Semua baris di sini ber-``origin='demo'`` — snapshot kanonik (origin='seed')
   tidak berubah, sehingga tes yang memaku seed tetap sah.
2. Id DETERMINISTIK (UUID5 dari lokasi+pemasok+komoditas) sehingga menyegarkan
   dua kali tidak menggandakan kiriman.
3. Tiga keadaan perjalanan tersedia merata: belum berangkat, di jalan, sudah tiba —
   supaya garis peta (padat/putus-putus) dan kartu kiriman punya bahan nyata.
4. Tidak ada angka karangan di UI: seluruh kolom diisi dari data yang memang
   dipakai server (jam panen/berangkat, masa layak, mutu, sertifikasi).
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.po_number import nomor_po
from app.models import (
    Batch,
    Commodity,
    DisposalEvent,
    Location,
    PriceSignal,
    Supplier,
)

DEMO_TAG = "demo-aktivitas"

#: Umur simpan per komoditas (hari) — dipakai menghitung `usable_until`.
SHELF_LIFE_HARI = {"telur": 28, "ayam": 5, "beras": 180, "wortel": 21}

#: Empat keadaan rotasi: 0 = di jalan, 1 = sudah tiba, 2 = belum berangkat,
#: 3 = di jalan (variasi jam) — supaya tiap lokasi punya campuran.
ROTASI = (
    {"state": "di_jalan", "berangkat_menit": -35, "panen_jam": -26},
    {"state": "sudah_tiba", "berangkat_menit": -300, "panen_jam": -34},
    {"state": "belum_berangkat", "berangkat_menit": None, "panen_jam": -5},
    {"state": "di_jalan", "berangkat_menit": -12, "panen_jam": -20},
)

MUTU = ("pass", "pass", "pending", "needs_verification")
SERTIFIKASI = ("haccp", "hygiene", "none")

#: Harga PO demo per komoditas (Rp/kg). Satu angka untuk semua komoditas membuat
#: beras tercatat Rp25.132/kg — 89% di atas pasar — dan itu terbaca sebagai
#: kesalahan data, bukan variasi.
HARGA_PO = {
    "telur": Decimal("25132.39"),
    "ayam": Decimal("41500"),
    "wortel": Decimal("23500"),
    "beras": Decimal("13300"),
}

#: Acuan harga demo harian: (acuan PIHPS Rp/kg, deviasi kutipan pemasok).
#: Deviasi sengaja kecil tapi tidak nol: 0% membuat metrik deviasi harga
#: selalu "sempurna" dan tidak informatif.
HARGA_HARIAN = {
    "telur": (Decimal("30500"), Decimal("0.010")),
    "ayam": (Decimal("41500"), Decimal("0.004")),
    "wortel": (Decimal("23500"), Decimal("0.014")),
    "beras": (Decimal("13400"), Decimal("0.006")),
}


def demo_batch_id(lokasi: str, pemasok: str, komoditas: str) -> uuid.UUID:
    """Id deterministik: menyegarkan dua kali tidak menggandakan kiriman."""
    return uuid.uuid5(uuid.NAMESPACE_URL, f"mcg:{DEMO_TAG}:{lokasi}:{pemasok}:{komoditas}")


def _pemasok_untuk_pasangan(
    kanonik: set[uuid.UUID] | None, slot: uuid.UUID
) -> uuid.UUID:
    """Pemasok batch demo: ikuti kanonik bila ada, selain itu pemasok slot.

    Deterministik (id terkecil) supaya menyegarkan demo tidak menggeser pemasok
    dari satu pemasok kanonik ke pemasok kanonik lain.
    """
    if kanonik:
        return min(kanonik)
    return slot


def _slot(nama_lokasi: str, index_lokasi: int, semua_pemasok: list[Supplier]):
    """Empat pemasok bergilir per lokasi — cukup beragam, tanpa penugasan acak."""
    awal = (index_lokasi * 4) % max(1, len(semua_pemasok))
    return [semua_pemasok[(awal + i) % len(semua_pemasok)] for i in range(4)]


async def seed_demo_activity(session: AsyncSession, now: datetime) -> dict:
    """Buat/perbarui kiriman demo untuk SEMUA lokasi. Idempoten."""
    lokasi = list((await session.execute(select(Location).order_by(Location.name))).scalars())
    pemasok = list((await session.execute(select(Supplier).order_by(Supplier.name))).scalars())
    komoditas = {
        c.name: c.id for c in (await session.execute(select(Commodity))).scalars()
    }
    tersedia = [nama for nama in SHELF_LIFE_HARI if nama in komoditas]
    if not lokasi or not pemasok or not tersedia:
        return {"batch_demo": 0, "dilewati": "data dasar belum ada"}

    # Audit M10 (18 Okt 2026): pemasok kanonik per pasangan (lokasi, komoditas).
    # Seed demo TIDAK boleh menambah pemasok kedua untuk pasangan yang kanoniknya
    # tunggal: `resolve_binding` lalu menolak menyimpulkan pemasok
    # ("supplier_unknown") untuk keputusan tanpa `allocation_binding`, dan pagar
    # yang benar itu jadi dipicu oleh data demo kita sendiri.
    kanonik: dict[tuple[uuid.UUID, uuid.UUID], set[uuid.UUID]] = {}
    for loc_id, com_id, sup_id in (
        await session.execute(
            select(Batch.location_id, Batch.commodity_id, Batch.supplier_id).where(
                Batch.origin != "demo"
            )
        )
    ).all():
        kanonik.setdefault((loc_id, com_id), set()).add(sup_id)

    dibuat = 0
    dihapus = 0
    id_dipakai: list[uuid.UUID] = []
    for i, loc in enumerate(lokasi):
        for j, sup in enumerate(_slot(loc.name, i, pemasok)):
            nama_komoditas = tersedia[(i + j) % len(tersedia)]
            rotasi = ROTASI[(i + j) % len(ROTASI)]
            id_batch = demo_batch_id(loc.name, sup.name, nama_komoditas)
            id_dipakai.append(id_batch)
            panen = now + timedelta(hours=rotasi["panen_jam"])
            berangkat = (
                None
                if rotasi["berangkat_menit"] is None
                else now + timedelta(minutes=rotasi["berangkat_menit"])
            )
            if berangkat is not None and berangkat < panen:
                berangkat = panen + timedelta(minutes=30)
            nilai = {
                "id": id_batch,
                "commodity_id": komoditas[nama_komoditas],
                "location_id": loc.id,
                # Pemasok slot dipakai HANYA bila pasangan ini belum punya
                # batch kanonik sama sekali. Kalau sudah ada, batch demo ikut
                # salah satu pemasok kanonik (yang terkecil id-nya, supaya
                # deterministik) — jangan menambah pemasok baru ke pasangan.
                "supplier_id": _pemasok_untuk_pasangan(
                    kanonik.get((loc.id, komoditas[nama_komoditas])), sup.id
                ),
                "quantity_kg": Decimal(200 + ((i * 7 + j * 13) % 9) * 100),
                "harvested_at": panen,
                "temperature_log": [],
                "certification_status": SERTIFIKASI[(i + j) % len(SERTIFIKASI)],
                "freshness_score": Decimal("0.82"),
                "safety_status": MUTU[(i + j) % len(MUTU)],
                "usable_until": panen + timedelta(days=SHELF_LIFE_HARI[nama_komoditas]),
                "dispatched_at": berangkat,
                "origin": "demo",
                "generated_at": now,
            }
            ada = await session.get(Batch, id_batch)
            if ada is None:
                session.add(Batch(**nilai))
                dibuat += 1
            else:
                for k, v in nilai.items():
                    setattr(ada, k, v)
    # Buang kiriman demo yang tidak lagi punya slot (mis. lokasi/pemasok berubah).
    usang = delete(Batch).where(
        Batch.origin == "demo", Batch.id.notin_(id_dipakai)
    )
    hasil_usang = await session.execute(usang)
    dihapus = hasil_usang.rowcount or 0
    await session.flush()
    return {"batch_demo": dibuat, "diperbarui": len(id_dipakai) - dibuat, "dibuang": dihapus}

# --------------------------------------------------------------------------
# Keputusan demo yang SUDAH SELESAI + limbah hari ini
# --------------------------------------------------------------------------
# Kenapa: panel KPI menjawab "belum ada data" untuk 4 dari 7 metrik ketika
# periode = HARI INI, karena seed kanonik berhenti di 8 Okt. Yang dibutuhkan
# bukan angka karangan di klien, melainkan baris yang MEMANG dipakai server:
#   - Avoidable Food Loss  : disposal_events hari ini (dibagi supply hari ini)
#   - Safe Delivered Cost  : PO mock hari ini + decisions.safe_delivered_cost
#   - Decision Time        : trace DETECT..ACT hari ini + PO committed
#   - Evidence Completeness: keputusan hari ini, approval hari ini, >=2 jenis
#                            bukti konsisten SEBELUM approval
# Semua baris demo, id deterministik (idempoten), dan ikut terhapus saat
# "Bersihkan data demo" (CASCADE dari decisions).

from app.models import (  # noqa: E402  (impor di bawah agar blok ini mandiri)
    AgentTrace,
    Approval,
    Decision,
    DecisionEvidence,
    SapMockPurchaseOrder,
    User,
)

#: Tiga kota cukup untuk memperagakan metrik lintas-lokasi tanpa membanjiri UI.
KOTA_DEMO = ("Jakarta", "Bandung", "Surabaya")
#: Menit relatif awal keputusan untuk satu jalur agent yang lengkap.
JALUR_KEPUTUSAN = (("DETECT", 0), ("VERIFY", 4), ("DECIDE", 10), ("ACT", 20))
#: Bukti harus TEREKAM SEBELUM approval (menit 12) agar dihitung "lengkap".
BUKTI_SEBELUM_APPROVAL = (("market_price", 6), ("gps", 8))


def demo_decision_id(lokasi: str, komoditas: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"mcg:{DEMO_TAG}:keputusan:{lokasi}:{komoditas}")


async def seed_demo_completed_decisions(db: AsyncSession, now: datetime) -> dict:
    """Lengkapi KPI "hari ini": keputusan selesai + limbah. Idempoten."""
    lokasi = {
        loc.name: loc
        for loc in (await db.execute(select(Location))).scalars()
        if loc.name in KOTA_DEMO
    }
    komoditas = {c.name: c.id for c in (await db.execute(select(Commodity))).scalars()}
    pemasok = list((await db.execute(select(Supplier).order_by(Supplier.name))).scalars())
    #: Approval demo harus berasal dari approver KOTA ITU SENDIRI. Scope backend
    #: menolak approve lintas SPPG (403), jadi menyemai approval dari Jakarta
    #: untuk keputusan Bandung/Surabaya menghasilkan riwayat yang tidak mungkin
    #: terjadi lewat alur — persis yang diperbaiki 18 Okt (keputusan produk 3A).
    approver = {
        (u.location_id, u.role): u
        for u in (
            await db.execute(
                select(User).where(
                    User.role.in_(("sppg_head", "sppg_nutritionist"))
                )
            )
        ).scalars()
    }
    if not lokasi or not komoditas or not pemasok or not approver:
        return {
            "keputusan_demo": 0,
            "limbah_demo": 0,
            "dilewati": "data dasar belum ada (butuh lokasi, komoditas, pemasok, "
            "user sppg_head dan sppg_nutritionist)",
        }

    #: Komoditas yang BENAR-BENAR ada di DB, urut stabil. Daftar tetap berisi
    #: "beras" pernah membuat Jakarta tidak kebagian keputusan (beras tidak ada),
    #: sehingga KPI ber-scope Jakarta tetap kosong walau baris lain terbuat.
    urut_komoditas = [nama for nama in ("telur", "ayam", "wortel") if nama in komoditas]
    if not urut_komoditas:
        return {"keputusan_demo": 0, "limbah_demo": 0, "dilewati": "komoditas kosong"}

    dibuat = 0
    dilewati_kota: list[str] = []
    # Daftar pekerjaan dibangun dulu, lalu dieksekusi: rotasi 3 kota hanya
    # memilih telur/ayam/wortel, sehingga beras tidak pernah kebagian. Beras
    # disemai EKSPLISIT untuk Jakarta supaya panel Decision & Evidence punya
    # baris beras yang bisa dibuka (permintaan pemilik 18 Okt 2026).
    pekerjaan: list[tuple[str, object, str]] = []
    for i, (nama_kota, loc) in enumerate(sorted(lokasi.items())):
        kepala_kota = approver.get((loc.id, "sppg_head"))
        nutrisi_kota = approver.get((loc.id, "sppg_nutritionist"))
        if kepala_kota is None or nutrisi_kota is None:
            # Jangan menyemai riwayat yang tidak mungkin lahir dari alur: kota
            # tanpa approver sendiri dilewati, bukan di-approve dari SPPG lain.
            dilewati_kota.append(nama_kota)
            continue
        pekerjaan.append((nama_kota, loc, urut_komoditas[i % len(urut_komoditas)]))
    jakarta = lokasi.get("Jakarta")
    if (
        jakarta is not None
        and "beras" in komoditas
        and approver.get((jakarta.id, "sppg_head")) is not None
        and approver.get((jakarta.id, "sppg_nutritionist")) is not None
    ):
        pekerjaan.append(("Jakarta", jakarta, "beras"))

    for nama_kota, loc, nama_komoditas in pekerjaan:
        kepala_kota = approver[(loc.id, "sppg_head")]
        nutrisi_kota = approver[(loc.id, "sppg_nutritionist")]
        sup = pemasok[pekerjaan.index((nama_kota, loc, nama_komoditas)) % len(pemasok)]
        if nama_komoditas == "beras":
            # Pemasok beras dulu; kalau tidak ada, jatuh ke pemasok rotasi.
            sup = next((p for p in pemasok if p.name.startswith("Beras")), sup)
        did = demo_decision_id(nama_kota, nama_komoditas)
        mulai = now - timedelta(minutes=44)
        nilai = {
            "id": did,
            "decision_type": "regional_balance",
            "status": "executed",
            "proposed_by": "supervisor_agent",
            "verified_by": "verifier_agent",
            # `verifier_note` BUKAN kalimat bebas: read model membacanya sebagai
            # verdict (`_verdict_of` di approval_summary). Kalimat naratif di sini
            # membuat verdict jatuh ke "unavailable", sehingga layar menulis
            # "aturan persetujuan: tidak dapat dievaluasi" untuk keputusan yang
            # buktinya sendiri tercatat konsisten.
            "verifier_note": "consistent",
            "iteration": 1,
            "demo_case": None,
            "source_location_id": loc.id,
            "target_location_id": loc.id,
            "commodity_id": komoditas[nama_komoditas],
            "quantity_kg": Decimal(600),
            "safe_delivered_cost": Decimal("15079436.39"),
            #: Baris ini RIWAYAT yang sudah dieksekusi, bukan pekerjaan tertunda.
            #: Tenggat 2 jam dulu membuatnya tampil "decision expired" dua jam
            #: setelah disemai — penghalang palsu pada keputusan yang sudah tutup.
            "expires_at": now + timedelta(days=30),
            "origin": "demo",
            "generated_at": now,
            "created_at": mulai,
        }
        ada = await db.get(Decision, did)
        if ada is None:
            db.add(Decision(**nilai))
            dibuat += 1
        else:
            for k, v in nilai.items():
                setattr(ada, k, v)

        # Batch sumber untuk pasangan (lokasi, komoditas) ini. Tanpa baris ini
        # `revalidate_transfer` melaporkan "tidak ada batch sumber" dan
        # `resolve_binding` tidak bisa memastikan pemasok — dua penghalang yang
        # tidak masuk akal pada keputusan yang statusnya sudah `executed`.
        # Batch yang SUDAH ada dipakai lebih dulu (jangan menambah kiriman yang
        # tidak perlu); batch baru hanya dibuat untuk pasangan yang kosong, dan
        # id-nya memakai `demo_batch_id` yang sama dengan penyemai kiriman demo.
        batch_sumber = (
            await db.execute(
                select(Batch)
                .where(
                    Batch.location_id == loc.id,
                    Batch.commodity_id == komoditas[nama_komoditas],
                    # Keputusan "selesai" tidak boleh bersandar pada batch yang
                    # belum lolos mutu. Tanpa filter ini seeder mengambil batch
                    # pertama (bisa `needs_verification`) sehingga riwayat demo
                    # memuat eksekusi di atas bahan yang belum lulus audit.
                    Batch.safety_status == "pass",
                )
                .order_by(Batch.id)
            )
        ).scalars().first()
        if batch_sumber is None:
            panen = mulai - timedelta(hours=26)
            batch_sumber = Batch(
                id=demo_batch_id(nama_kota, sup.name, nama_komoditas),
                commodity_id=komoditas[nama_komoditas],
                location_id=loc.id,
                supplier_id=sup.id,
                quantity_kg=Decimal(800),
                harvested_at=panen,
                dispatched_at=panen + timedelta(hours=6),
                usable_until=panen
                + timedelta(days=SHELF_LIFE_HARI.get(nama_komoditas, 7)),
                safety_status="pass",
                certification_status="haccp",
                freshness_score=Decimal("0.92"),
                origin="demo",
                generated_at=now,
                temperature_log=[],
            )
            db.add(batch_sumber)

        for etype, menit in BUKTI_SEBELUM_APPROVAL:
            bukti_id = uuid.uuid5(did, f"bukti:{etype}")
            kapan = mulai + timedelta(minutes=menit)
            ada_bukti = await db.get(DecisionEvidence, bukti_id)
            if ada_bukti is None:
                db.add(
                    DecisionEvidence(
                        id=bukti_id,
                        decision_id=did,
                        evidence_type=etype,
                        payload={"demo": True, "kota": nama_kota},
                        is_consistent=True,
                        recorded_at=kapan,
                    )
                )
            else:
                # Tanggal ikut bergeser: bukti yang tertinggal di hari kemarin
                # membuat Evidence Completeness & Decision Time kosong besok.
                ada_bukti.recorded_at = kapan
                ada_bukti.payload = {"demo": True, "kota": nama_kota}
                ada_bukti.is_consistent = True

        # Binding eksplisit: menyebut pemasok DAN batch yang dipakai. Tanpa ini
        # `resolve_binding` harus menyimpulkan dari seluruh batch pasangan itu,
        # dan pada pasangan dengan lebih dari satu pemasok hasilnya
        # "supplier_unknown" (409) — layar lalu menampilkan alasan itu untuk
        # keputusan yang sudah dieksekusi.
        bind_id = uuid.uuid5(did, "bukti:allocation_binding")
        binding_payload = {
            "allocation_binding": True,
            "supplier_id": str(batch_sumber.supplier_id),
            "batch_ids": [str(batch_sumber.id)],
            "demo": True,
        }
        bukti_binding = await db.get(DecisionEvidence, bind_id)
        if bukti_binding is None:
            db.add(
                DecisionEvidence(
                    id=bind_id,
                    decision_id=did,
                    evidence_type="human_inspection",
                    payload=binding_payload,
                    is_consistent=True,
                    recorded_at=mulai + timedelta(minutes=9),
                )
            )
        else:
            # DITULIS ULANG, bukan sekali tulis. Batch demo bisa hilang oleh
            # "Bersihkan data demo" atau oleh tes yang membersihkan kiriman;
            # binding yang menunjuk batch hilang membuat resolusi gagal
            # ("binding batch/supplier berubah") untuk keputusan yang sudah
            # dieksekusi. Menyemai ulang harus menyembuhkannya.
            bukti_binding.payload = binding_payload
            bukti_binding.is_consistent = True
            bukti_binding.recorded_at = mulai + timedelta(minutes=9)

        acc_id = uuid.uuid5(did, "approval")
        acc = await db.get(Approval, acc_id)
        if acc is None:
            db.add(
                Approval(
                    id=acc_id,
                    decision_id=did,
                    approved_by=kepala_kota.id,
                    approved=True,
                    comment="Disetujui untuk demo lintas lokasi.",
                    approved_at=mulai + timedelta(minutes=12),
                )
            )
        else:
            # Reparasi: baris lama (sebelum 18 Okt) memakai approver Jakarta.
            # Seed bersifat idempoten, jadi ia harus menyembuhkan riwayatnya.
            acc.approved_by = kepala_kota.id
            acc.approved_at = mulai + timedelta(minutes=12)

        # Approval kedua: ahli gizi. `regional_balance` operasional wajib dua
        # role berbeda (`dua_role_wajib`), jadi satu approval saja membuat
        # riwayat "diekskusi" ini melanggar matriksnya sendiri.
        acc2_id = uuid.uuid5(did, "approval:nutrisi")
        acc2 = await db.get(Approval, acc2_id)
        if acc2 is None:
            db.add(
                Approval(
                    id=acc2_id,
                    decision_id=did,
                    approved_by=nutrisi_kota.id,
                    approved=True,
                    comment="Disetujui ahli gizi untuk demo lintas lokasi.",
                    approved_at=mulai + timedelta(minutes=14),
                )
            )
        else:
            acc2.approved_by = nutrisi_kota.id
            acc2.approved_at = mulai + timedelta(minutes=14)

        for step, menit in JALUR_KEPUTUSAN:
            trace_id = uuid.uuid5(did, f"trace:{step}")
            kapan = mulai + timedelta(minutes=menit)
            ada_jejak = await db.get(AgentTrace, trace_id)
            if ada_jejak is None:
                db.add(
                    AgentTrace(
                        id=trace_id,
                        decision_id=did,
                        step_name=step,
                        tool_called=f"demo.{step.lower()}",
                        input_summary={"demo": True},
                        output_summary={"ok": True},
                        duration_ms=800 + menit * 40,
                        step_at=kapan,
                    )
                )
            else:
                # Decision Time = DETECT..ACT di jendela; jejak yang tertinggal
                # di hari kemarin membuat metrik itu kehilangan sampelnya.
                ada_jejak.step_at = kapan
                ada_jejak.duration_ms = 800 + menit * 40

        po_id = uuid.uuid5(did, "po")
        harga_po = HARGA_PO.get(nama_komoditas, Decimal("25132.39"))
        po_kapan = now - timedelta(minutes=18)
        ada_po = await db.get(SapMockPurchaseOrder, po_id)
        if ada_po is None:
            db.add(
                SapMockPurchaseOrder(
                    id=po_id,
                    # Audit M8: PO demo lahir dari keputusan yang sama seperti
                    # eksekusi nyata, jadi nomornya memakai aturan yang sama.
                    po_number=nomor_po(did),
                    supplier_id=sup.id,
                    material_number=f"MAT-{nama_komoditas.upper()[:4]}",
                    ordered_quantity=Decimal(600),
                    price=harga_po,
                    decision_id=did,
                    status="confirmed",
                    created_at=po_kapan,
                )
            )
        else:
            # Safe Delivered Cost berjangkar pada PO.created_at; PO yang tetap
            # di hari kemarin mengosongkan metrik itu besok pagi.
            ada_po.created_at = po_kapan
            ada_po.price = harga_po
            ada_po.supplier_id = sup.id

    # Limbah hari ini: dua kejadian kecil di Jakarta (alasan dari data kanonik).
    limbah = 0
    jakarta = lokasi.get("Jakarta")
    if jakarta is not None and "telur" in komoditas:
        #: Satu kejadian dialihkan ke mitra, satu dibuang tanpa mitra: dua
        #: keadaan itu HARUS terlihat berbeda di panel, bukan sama-sama "—".
        mitra_hari_ini = ("Bank Sampah Melati", None)
        for n, (menit, kg) in enumerate(((-150, Decimal("12.5")), (-90, Decimal("8")))):
            dis_id = uuid.uuid5(uuid.NAMESPACE_URL, f"mcg:{DEMO_TAG}:limbah:jakarta:{n}")
            kapan = now + timedelta(minutes=menit)
            mitra = mitra_hari_ini[n]
            ada_limbah = await db.get(DisposalEvent, dis_id)
            if ada_limbah is None:
                db.add(
                    DisposalEvent(
                        id=dis_id,
                        location_id=jakarta.id,
                        commodity_id=komoditas["telur"],
                        quantity_kg=kg,
                        reason="spoilage_cold_chain",
                        origin="demo",
                        generated_at=now,
                        disposed_at=kapan,
                        partner_name=mitra,
                    )
                )
                limbah += 1
            else:
                # Avoidable Food Loss memakai jendela hari ini; limbah yang
                # tertinggal sehari membuat metriknya kosong besok.
                ada_limbah.disposed_at = kapan
                ada_limbah.generated_at = now
                ada_limbah.partner_name = mitra
    await db.flush()
    return {
        "keputusan_demo": dibuat,
        "limbah_demo": limbah,
        "dilewati_kota": dilewati_kota,
    }

async def seed_demo_daily_prices(session: AsyncSession, now: datetime) -> dict:
    """Harga demo HARI INI: acuan PIHPS + kutipan pemasok, berpasangan.

    Metrik "Procurement Price Deviation" memasangkan `supplier_quote` dengan
    `pihps_reference` TERAKHIR SEBELUM kutipan itu, di lokasi+komoditas yang
    sama. Seed kanonik berhenti di 8 Okt dan deret waktu demo berhenti di hari
    penenunannya, jadi setiap hari baru metrik itu menjawab "tidak ada record
    pada periode ini" — padahal datanya ada di hari-hari sebelumnya.

    Baris ditulis untuk kota yang punya keputusan demo (Jakarta, Bandung,
    Surabaya) dan semua komoditas yang ada di DB, termasuk beras. Id
    deterministik per (tanggal, kota, komoditas, jenis), sehingga menyegarkan
    dua kali pada hari yang sama memperbarui baris yang sama.
    """
    kota = ("Jakarta", "Bandung", "Surabaya")
    lokasi = {
        loc.name: loc
        for loc in (await session.execute(select(Location))).scalars()
        if loc.name in kota
    }
    komoditas = {c.name: c.id for c in (await session.execute(select(Commodity))).scalars()}
    pemasok = list((await session.execute(select(Supplier).order_by(Supplier.name))).scalars())
    if not lokasi or not pemasok:
        return {"harga_demo": 0, "dilewati": "lokasi/pemasok belum ada"}

    hari = now.date()
    dibuat = 0
    for nama_kota, loc in sorted(lokasi.items()):
        # Kutipan datang dari pemasok KOTA ITU; tanpa pemasok lokal, kutipan
        # tetap sah tetapi jaraknya tidak masuk akal — jadi kota dilewati.
        sup = next((p for p in pemasok if p.location_id == loc.id), None)
        if sup is None:
            continue
        for nama, (acuan, deviasi) in HARGA_HARIAN.items():
            if nama not in komoditas:
                continue
            kutipan = (acuan * (Decimal(1) + deviasi)).quantize(Decimal("0.01"))
            rencana = (
                ("acuan", acuan, now - timedelta(hours=4), "pihps_reference", None),
                ("kutipan", kutipan, now - timedelta(hours=3), "supplier_quote", sup.id),
            )
            for jenis, harga, kapan, sumber, supplier_id in rencana:
                pid = uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"mcg:{DEMO_TAG}:harga:{hari}:{nama_kota}:{nama}:{jenis}",
                )
                baris = await session.get(PriceSignal, pid)
                if baris is None:
                    session.add(
                        PriceSignal(
                            id=pid,
                            location_id=loc.id,
                            commodity_id=komoditas[nama],
                            supplier_id=supplier_id,
                            price_per_kg=harga,
                            source=sumber,
                            recorded_at=kapan,
                            origin="demo",
                            generated_at=now,
                        )
                    )
                    dibuat += 1
                else:
                    baris.price_per_kg = harga
                    baris.recorded_at = kapan
                    baris.supplier_id = supplier_id
                    baris.generated_at = now
    await session.flush()
    return {"harga_demo": dibuat}


