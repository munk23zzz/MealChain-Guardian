"""Membangun TEMPLATE data demo (satu kali, lalu beku).

Tujuan: satu dataset yang memuat SEMUA kasus yang akan didemokan, dengan
keadaan awal yang selalu sama setiap kali dibangun ulang.

Beda dengan `POST /demo/session/start`:
- sesi demo menandai baris `origin='demo'` + `demo_session_id` sehingga baris
  itu dibuang saat sesi berakhir;
- template membalik tanda itu menjadi `origin='seed'` dan melepas stempel,
  sehingga "Akhiri sesi" TIDAK menghapusnya (lihat aturan 21 Okt 2026 di
  `app/services/demo_session.py`).

Karena itu: template boleh dibangun kapan pun, dan sesi demo menjadi lapisan
kerja di atasnya — persis pola "cetakan vs adonan" (docs/demo/ide-sesi-demo).

Memuat:
1. Snapshot kanonik (`load_seed`) — pasokan/permintaan/harga/menu/kiriman.
2. Aktivitas demo: kiriman di seluruh lokasi (belum berangkat / di jalan /
   sudah tiba) + 3 barang datang.
3. Keputusan selesai + limbah hari ini + harga harian → supaya KPI tidak
   "belum ada data".
4. Empat kasus skrip untuk Jakarta, Bandung, dan Surabaya (peran lain bisa
   menyetujui kartunya sendiri).
5. Tambahan untuk tab yang biasanya kosong: 2 penerimaan menunggu, 1 eksklusi
   pemasok aktif + 1 proposal menunggu, 2 batch karantina, 1 batch gagal uji,
   1 batch butuh verifikasi.

Jalankan di dalam kontainer backend:

    python -m app.seed.demo_template            # bangun template
    python -m app.seed.demo_template --dry-run  # hitung tanpa menulis
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.po_number import nomor_po
from app.db import create_engine, create_session_maker
from app.models import (
    AgentTrace,
    Approval,
    Batch,
    BatchReceipt,
    Commodity,
    Decision,
    Location,
    SapMockPurchaseOrder,
    Supplier,
    SupplierExclusion,
    User,
)
from app.seed.demo_kasus_bukti import semai_kasus_bukti_hari_ini
from app.seed.demo_kpi_riwayat import geser_aksi_ke_riwayat
from app.services import demo_session as sesi

KOTA_TEMPLATE = ("Jakarta", "Bandung", "Surabaya")


def _uid(*bagian: str) -> uuid.UUID:
    """Id deterministik supaya template bisa dibangun ulang tanpa menggandakan."""
    return uuid.uuid5(uuid.NAMESPACE_URL, "mcg:template:" + ":".join(bagian))


async def _lokasi(db: AsyncSession, nama: str) -> Location | None:
    return (
        await db.execute(select(Location).where(Location.name == nama))
    ).scalar_one_or_none()


async def _user(db: AsyncSession, email: str) -> User | None:
    return (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()


async def _semai_inti(db: AsyncSession, now: datetime) -> dict:
    """Snapshot kanonik + aktivitas demo + KPI hari ini + harga harian."""
    from app.api.demo import _sync_routes_aman
    from app.seed.demo_activity import (
        seed_demo_activity,
        seed_demo_completed_decisions,
        seed_demo_daily_prices,
    )
    from app.seed.seed_data import load_seed

    rows = await load_seed(now)
    aktivitas = await seed_demo_activity(db, now)
    selesai = await seed_demo_completed_decisions(db, now)
    harga = await seed_demo_daily_prices(db, now)
    rute, rute_error = await _sync_routes_aman(now)
    return {"seed": rows, "aktivitas": aktivitas, "kpi": selesai, "harga": harga,
            "rute": rute, "rute_error": rute_error}


async def _semai_kasus(db: AsyncSession) -> dict:
    """Empat kasus skrip untuk tiap kota demo (kartu bisa disetujui peran kota itu)."""
    from app.api.demo import _seed_demo_cases

    hasil = {}
    for nama in KOTA_TEMPLATE:
        kota = await _lokasi(db, nama)
        if kota is None:
            hasil[nama] = "lokasi tidak ada"
            continue
        hasil[nama] = await _seed_demo_cases(db, force=True, target=kota)
    return hasil


async def _semai_karantina(db: AsyncSession, now: datetime) -> dict:
    """Tiga keadaan keamanan pangan yang harus terlihat di papan: karantina,
    gagal uji (excursion > 30 menit), dan butuh verifikasi (log tidak lengkap).

    Ditulis lewat Core UPDATE, bukan mutasi objek ORM: penyemai lain memakai
    Core/bulk dengan id deterministik, dan objek ORM yang dibaca sebelum itu
    bisa "hilang" di flush (StaleDataError 0 baris cocok).
    """
    jakarta = await _lokasi(db, "Jakarta")
    if jakarta is None:
        return {"dilewati": "Jakarta tidak ada"}

    # Pemilihan batch TIDAK boleh "tiga batch pertama": dulu batch terbesar
    # Jakarta kebetulan beras, sehingga beras menghabiskan kuota gagal+karantina
    # dan tidak menyisakan satu pun batch `pass` — panel pasokan menampilkan
    # "0 kg layak" untuk beras meski 900 kg tercatat. Sekarang peran tiap batch
    # ditetapkan per komoditas sesuai naskah demo:
    #   beras terbesar  -> gagal uji (babak Keamanan Pangan)
    #   beras kedua     -> karantina (babak Keamanan Pangan)
    #   beras ketiga    -> pass, log lengkap (pasokan beras tetap punya angka layak)
    #   ayam terbesar   -> butuh verifikasi (log bolong)
    beras_id = (
        await db.execute(select(Commodity.id).where(Commodity.name == "beras"))
    ).scalar_one_or_none()
    ayam_id = (
        await db.execute(select(Commodity.id).where(Commodity.name == "ayam"))
    ).scalar_one_or_none()

    async def _tiga(komoditas_id):
        if komoditas_id is None:
            return []
        return list(
            (
                await db.execute(
                    select(Batch.id)
                    .where(
                        Batch.location_id == jakarta.id,
                        Batch.commodity_id == komoditas_id,
                    )
                    .order_by(Batch.quantity_kg.desc(), Batch.id)
                    .limit(3)
                )
            ).scalars()
        )

    beras_ids = await _tiga(beras_id)
    ayam_ids = await _tiga(ayam_id)
    if len(beras_ids) < 3 or not ayam_ids:
        return {"dilewati": f"batch beras {len(beras_ids)}, ayam {len(ayam_ids)}"}

    gagal_id, karantina_id, layak_id = beras_ids[0], beras_ids[1], beras_ids[2]
    verifikasi_id = ayam_ids[0]

    # 1. Gagal uji: suhu 9,5 C selama ~80 menit (ambang FAIL 30 menit).
    await db.execute(
        update(Batch)
        .where(Batch.id == gagal_id)
        .values(
            temperature_log=[
                {
                    "timestamp": (now - timedelta(minutes=80 - 10 * i)).isoformat(),
                    "temperature_c": 9.5,
                }
                for i in range(8)
            ],
            safety_status="fail",
            freshness_score=Decimal("0.42"),
        )
    )
    # 2. Karantina: alasan nyata, belum diputuskan.
    await db.execute(
        update(Batch)
        .where(Batch.id == karantina_id)
        .values(
            quarantine_status="quarantined",
            quarantine_reason="Kemasan penyok pada 3 dus; menunggu pemeriksaan gudang.",
            quarantined_at=now - timedelta(hours=2),
            quarantine_updated_at=now - timedelta(hours=2),
            safety_status="needs_verification",
        )
    )
    # 3. Batch beras yang lolos: log suhu lengkap 8 titik, 4,2 C (di bawah 5 C).
    await db.execute(
        update(Batch)
        .where(Batch.id == layak_id)
        .values(
            temperature_log=[
                {
                    "timestamp": (now - timedelta(minutes=60 - 7 * i)).isoformat(),
                    "temperature_c": 4.2,
                }
                for i in range(8)
            ],
            safety_status="pass",
            quarantine_status="none",
        )
    )
    # 4. Butuh verifikasi: log suhu bolong (hanya satu titik) pada batch ayam.
    await db.execute(
        update(Batch)
        .where(Batch.id == verifikasi_id)
        .values(
            temperature_log=[
                {"timestamp": (now - timedelta(hours=3)).isoformat(), "temperature_c": 3.4}
            ],
            safety_status="needs_verification",
        )
    )
    await db.commit()
    return {
        "gagal": str(gagal_id),
        "karantina": str(karantina_id),
        "layak": str(layak_id),
        "butuh_verifikasi": str(verifikasi_id),
    }


async def _semai_penerimaan(db: AsyncSession, now: datetime) -> dict:
    """Dua penerimaan 'menunggu' — bahan angka bergerak di tab Keamanan Pangan."""
    jakarta = await _lokasi(db, "Jakarta")
    kepala = await _user(db, "sppg.head@demo.local")
    if jakarta is None or kepala is None:
        return {"dilewati": "Jakarta / akun kepala tidak ada"}

    siap = list(
        (
            await db.execute(
                select(Batch)
                .where(Batch.location_id == jakarta.id, Batch.safety_status == "pending")
                .order_by(Batch.id)
                .limit(2)
            )
        ).scalars()
    )
    if not siap:
        # Tidak ada batch pending: pakai dua batch apa pun milik Jakarta.
        siap = list(
            (
                await db.execute(
                    select(Batch).where(Batch.location_id == jakarta.id).order_by(Batch.id).limit(2)
                )
            ).scalars()
        )

    dibuat = []
    for b in siap:
        kunci = _uid("terima", str(b.id))
        ada = await db.get(BatchReceipt, kunci)
        if ada is not None:
            dibuat.append(str(kunci))
            continue
        db.add(
            BatchReceipt(
                id=kunci,
                batch_id=b.id,
                checked={"suhu": True, "kemasan": True, "jumlah": b.quantity_kg is not None},
                other_note=None,
                recorded_by=kepala.id,
                recorded_at=now - timedelta(minutes=35),
                status="menunggu",
            )
        )
        dibuat.append(str(kunci))
    await db.flush()
    return {"dibuat": dibuat}



async def _rapikan_kiriman_jakarta(db: AsyncSession, now: datetime) -> dict:
    """Jakarta: maksimal 3 kiriman hidup per komoditas (permintaan pemilik).

    Dijalankan PALING AKHIR: batch keamanan pangan (gagal uji 800 kg, karantina
    540 kg, penerimaan 90/300 kg) baru lahir pada langkah setelah kasus, jadi
    membatasi lebih awal tidak berpengaruh (terukur 21 Okt 2026: batch gagal
    800 kg masih terhitung "sedang mengirim").

    1. Batch `fail` tidak sedang dikirim — barangnya dibuang; masa layaknya
       dimundurkan. Kartu Keamanan Pangan tetap menampilkannya sebagai temuan.
    2. Sisanya: yang terkecil dihapus lebih dulu supaya yang tampil di peta
       adalah kiriman nyata.
    """
    jakarta = await _lokasi(db, "Jakarta")
    if jakarta is None:
        return {"dilewati": "Jakarta tidak ada"}

    gagal = list(
        (
            await db.execute(
                select(Batch).where(
                    Batch.location_id == jakarta.id,
                    Batch.safety_status == "fail",
                )
            )
        ).scalars()
    )
    for batch in gagal:
        batch.usable_until = now - timedelta(hours=1)

    dipangkas = 0
    komoditas = list(
        (
            await db.execute(
                select(Batch.commodity_id).where(Batch.location_id == jakarta.id).distinct()
            )
        ).scalars()
    )
    for komoditas_id in komoditas:
        hidup = list(
            (
                await db.execute(
                    select(Batch)
                    .where(
                        Batch.location_id == jakarta.id,
                        Batch.commodity_id == komoditas_id,
                        Batch.usable_until >= now,
                        Batch.supplier_id.is_not(None),
                    )
                    .order_by(Batch.quantity_kg.desc(), Batch.id)
                )
            ).scalars()
        )
        # Pastikan tiap komoditas punya kiriman yang MASIH DI JALAN saat juri melihat
    # peta. Status perjalanan = dispatched_at + durasi rute, jadi kiriman dari
    # pemasok dekat (beras 12 menit, telur 21 menit) sudah "tiba" sebelum demo
    # dimulai — terukur 21 Okt 2026 10.28 UTC: hanya wortel (rute 94 menit) yang
    # masih bergerak. Dua langkah:
    #   1. bila rute terpanjang komoditas < 40 menit, pindahkan batch itu ke
    #      pemasok sejenis yang jauhnya 40-160 km (masih satu wilayah, masuk akal);
    #   2. tarik jam berangkatnya ke 35% perjalanan, supaya sisa waktunya panjang.
    from app.core.geo import haversine_km
    from app.core.road_route import route_key
    from app.models.road_routes import RoadRoute

    def _kunci(supplier, lokasi) -> str:
        return route_key(
            float(supplier.latitude), float(supplier.longitude),
            float(lokasi.latitude), float(lokasi.longitude),
        )

    durasi: dict = {}
    async def _muat_durasi() -> None:
        kunci_semua = set()
        for komoditas_id in komoditas:
            baris = list(
                (
                    await db.execute(
                        select(Batch).where(
                            Batch.location_id == jakarta.id,
                            Batch.commodity_id == komoditas_id,
                            Batch.usable_until >= now,
                        )
                    )
                ).scalars()
            )
            for b in baris:
                pemasok = await db.get(Supplier, b.supplier_id) if b.supplier_id else None
                if pemasok is not None:
                    kunci_semua.add(_kunci(pemasok, jakarta))
        if not kunci_semua:
            return
        rows = (
            await db.execute(select(RoadRoute).where(RoadRoute.route_key.in_(kunci_semua)))
        ).scalars()
        for r in rows:
            durasi[r.route_key] = float(r.duration_s or 0)

    await _muat_durasi()

    dipindah = 0
    pindahan: dict = {}
    for komoditas_id in komoditas:
        hidup = list(
            (
                await db.execute(
                    select(Batch).where(
                        Batch.location_id == jakarta.id,
                        Batch.commodity_id == komoditas_id,
                        Batch.usable_until >= now,
                        Batch.supplier_id.is_not(None),
                    )
                )
            ).scalars()
        )
        if not hidup:
            continue
        pilihan = None
        lama_durasi = 0.0
        for b in hidup:
            pemasok = await db.get(Supplier, b.supplier_id)
            if pemasok is None:
                continue
            d = durasi.get(_kunci(pemasok, jakarta), 0.0)
            if d > lama_durasi:
                pilihan, lama_durasi = b, d

        if pilihan is not None and lama_durasi < 40 * 60:
            # Hanya pindah bila rute pasangan baru SUDAH ada di cache. Tanpa
            # OSRM hidup, pasangan baru tidak punya geometri/durasi sehingga
            # batch-nya jatuh ke "Perjalanan belum bisa dipastikan" — lebih
            # buruk daripada tetap di pemasok dekat (terukur 21 Okt 2026:
            # OSRM mati, dua batch jadi tidak_diketahui).
            pengganti = None
            jarak_terjauh = 0.0
            for s2 in (
                await db.execute(
                    select(Supplier).where(Supplier.commodity_id == komoditas_id)
                )
            ).scalars():
                if s2.location_id == jakarta.id:
                    continue
                if durasi.get(_kunci(s2, jakarta), 0.0) <= 0:
                    continue
                d_km = haversine_km(
                    float(s2.latitude), float(s2.longitude),
                    float(jakarta.latitude), float(jakarta.longitude),
                )
                if 40 <= d_km <= 160 and d_km > jarak_terjauh:
                    pengganti, jarak_terjauh = s2, d_km
            if pengganti is not None:
                pilihan.supplier_id = pengganti.id
                pindahan[komoditas_id] = pilihan
                dipindah += 1

    if dipindah:
        await db.flush()
        # Rute untuk pasangan baru belum ada di cache -> ambil sekali lagi.
        from app.api.demo import _sync_routes_aman
        try:
            await _sync_routes_aman(now)
        except Exception:
            pass
        durasi.clear()
        await _muat_durasi()

    diberangkatkan = 0
    for komoditas_id in komoditas:
        hidup = list(
            (
                await db.execute(
                    select(Batch).where(
                        Batch.location_id == jakarta.id,
                        Batch.commodity_id == komoditas_id,
                        Batch.usable_until >= now,
                        Batch.supplier_id.is_not(None),
                        # Karantina/gagal uji tidak mungkin sedang dikirim.
                        Batch.quarantine_reason.is_(None),
                        Batch.safety_status != "fail",
                    )
                )
            ).scalars()
        )
        calon = []
        for b in hidup:
            pemasok = await db.get(Supplier, b.supplier_id)
            if pemasok is None:
                continue
            d = durasi.get(_kunci(pemasok, jakarta), 0.0)
            if d > 0:
                calon.append((d, b))
        if not calon:
            continue
        # Utamakan batch yang baru dipindah ke pemasok jauh: itulah yang
        # rutenya panjang. Tanpa ini batch beras 12 menit kembali terpilih
        # (terukur: sisa 7 menit, tidak berguna untuk demo).
        pindah = pindahan.get(komoditas_id)
        cocok = [c for c in calon if pindah is not None and c[1].id == pindah.id]
        d, batch = (cocok[0] if cocok else max(calon, key=lambda x: x[0]))
        batch.dispatched_at = now - timedelta(seconds=d * 0.35)
        diberangkatkan += 1

    # Pemangkasan dijalankan LAGI setelah pemberangkatan: batch "pending" wortel
    # (120 kg) baru dianggap layak pada titik ini, sehingga pemeriksaan pertama
    # tidak melihatnya dan wortel menyisakan 4 garis di peta (batas 3).
    for komoditas_id in komoditas:
        hidup = list(
            (
                await db.execute(
                    select(Batch)
                    .where(
                        Batch.location_id == jakarta.id,
                        Batch.commodity_id == komoditas_id,
                        Batch.usable_until >= now,
                        Batch.supplier_id.is_not(None),
                    )
                    .order_by(Batch.quantity_kg.desc(), Batch.id)
                )
            ).scalars()
        )
        for lebih in hidup[3:]:
            await db.delete(lebih)
            dipangkas += 1

    # Beras: DUA kiriman berjalan dari DUA pemasok berbeda (permintaan pemilik
    # 21 Okt 2026). Satu batch beras Jakarta masih memakai pemasok yang sama
    # dengan batch lain (CV Cipinang); batch itu dipindah ke pemasok beras lain
    # yang rutenya sudah ada di cache (UD Rorotan, 24 menit), lalu diberangkatkan.
    diberangkatkan_beras = 0
    beras_id = (
        await db.execute(select(Commodity.id).where(Commodity.name == "beras"))
    ).scalar_one_or_none()
    if beras_id is not None:
        beras_hidup = list(
            (
                await db.execute(
                    select(Batch)
                    .where(
                        Batch.location_id == jakarta.id,
                        Batch.commodity_id == beras_id,
                        Batch.usable_until >= now,
                        Batch.supplier_id.is_not(None),
                        # Karantina tidak mungkin sedang dikirim; yang dipakai
                        # batch pass/pending saja.
                        Batch.quarantine_reason.is_(None),
                    )
                    .order_by(Batch.dispatched_at.is_not(None), Batch.quantity_kg.desc())
                )
            ).scalars()
        )
        # `dispatched_at` dari seed lama tidak dipakai sebagai patokan: yang
        # penting dua batch beras BERANGKAT dan pemasoknya berbeda. Terukur
        # 21 Okt 2026: 360 dan 300 kg sudah punya jam berangkat lama, sehingga
        # pemeriksaan "belum berangkat" membuat blok ini tidak berbuat apa-apa.
        calon = list(beras_hidup)
        pemasok_terpakai: set = set()
        for batch in calon:
            if batch.supplier_id in pemasok_terpakai:
                pengganti = None
                for s2 in (
                    await db.execute(
                        select(Supplier).where(Supplier.commodity_id == beras_id)
                    )
                ).scalars():
                    # Lokasi pemasok TIDAK disaring: pemasok beras yang
                    # rutenya sudah di-cache justru berada di Jakarta
                    # (UD Rorotan). Menyaring lokasi membuat blok ini tidak
                    # pernah menemukan pengganti (terukur: beras_berjalan 1).
                    if s2.id in pemasok_terpakai:
                        continue
                    if durasi.get(_kunci(s2, jakarta), 0.0) <= 0:
                        continue
                    pengganti = s2
                    break
                if pengganti is None:
                    continue
                batch.supplier_id = pengganti.id
            d = durasi.get(_kunci(await db.get(Supplier, batch.supplier_id), jakarta), 0.0)
            if d <= 0:
                continue
            batch.dispatched_at = now - timedelta(seconds=d * 0.35)
            pemasok_terpakai.add(batch.supplier_id)
            diberangkatkan_beras += 1
            if len(pemasok_terpakai) >= 2:
                break

    await db.flush()
    return {
        "gagal_dimundurkan": len(gagal),
        "batch_dipangkas": dipangkas,
        "beras_berjalan": diberangkatkan_beras,
        "pemasok_dipindah": dipindah,
        "kiriman_berjalan": diberangkatkan,
    }


async def _perkaya_kasus_jakarta(db: AsyncSession, now: datetime) -> dict:
    """Jakarta saja: satu contoh KEDUA untuk tiap kasus skrip + perbaikan data kiriman.

    Alasan (permintaan pemilik 21 Okt 2026): demo dijalankan sebagai SPPG Jakarta.
    Satu kartu per kasus terlihat seperti kebetulan; dua kartu membuat pola
    "berulang" terbaca. Kota lain sengaja TIDAK disentuh supaya angka yang sudah
    dihafal untuk Bandung/Surabaya tidak bergeser.

    Contoh kedua dibuat sebagai keputusan tersendiri (id deterministik, kuantitas
    70% dari aslinya, tenggat lebih panjang) — bukan duplikat identik, supaya juri
    melihat variasi dan bukan salinan.
    """
    from app.api.demo import _add_trace, _ikat_sumber, _seed_demo_cases

    jakarta = await _lokasi(db, "Jakarta")
    if jakarta is None:
        return {"dilewati": "Jakarta tidak ada"}

    # Bangun ulang kasus Jakarta dari nol (force) sebelum menggandakan.
    # Tanpa ini, setiap build menumpuk satu set lagi: seeder kasus memakai id
    # acak, jadi baris lama tidak tertimpa. Terukur 21 Okt 2026: dua build
    # membuat kasus ditolak berlipat 1 -> 2 -> 4 dan total keputusan melonjak.
    await _seed_demo_cases(db, True, jakarta)
    await db.flush()

    telur_id = (
        await db.execute(
            select(Commodity.id).where(Commodity.name == "telur")
        )
    ).scalar_one_or_none()

    hidup = list(
        (
            await db.execute(
                select(Decision).where(
                    Decision.target_location_id == jakarta.id,
                    Decision.demo_case.is_not(None),
                    Decision.status.in_(("pending_approval", "verifier_flagged")),
                    Decision.origin != "seed",
                )
            )
        ).scalars()
    ) or list(
        (
            await db.execute(
                select(Decision).where(
                    Decision.target_location_id == jakarta.id,
                    Decision.demo_case.is_not(None),
                    Decision.status.in_(("pending_approval", "verifier_flagged")),
                )
            )
        ).scalars()
    )

    ditambah = 0
    for d in hidup:
        kunci = _uid("kasus2", str(d.id))
        if await db.get(Decision, kunci) is not None:
            continue
        kuantitas = (d.quantity_kg or Decimal("600")) * Decimal("0.7")
        biaya = (d.safe_delivered_cost or Decimal("0")) * Decimal("0.7")
        # Kasus anomali harga tetap "ditandai verifikator", bukan menunggu
        # approval: menyalinnya sebagai pending_approval mengubah cerita kasus
        # (agent berhenti sendiri vs manusia yang memutuskan).
        status_salinan = (
            "verifier_flagged" if d.decision_type == "price_anomaly" else "pending_approval"
        )
        salinan = Decision(
            id=kunci,
            decision_type=d.decision_type,
            status=status_salinan,
            proposed_by=d.proposed_by or "supervisor_agent",
            verified_by="verifier_agent",
            verifier_note="flagged" if status_salinan == "verifier_flagged" else "consistent",
            iteration=(d.iteration or 1) + 10,
            demo_case=d.demo_case,
            source_location_id=d.source_location_id,
            target_location_id=d.target_location_id,
            supplier_id=d.supplier_id,
            commodity_id=d.commodity_id,
            quantity_kg=kuantitas,
            safe_delivered_cost=biaya,
            cost_breakdown=d.cost_breakdown,
            expires_at=now + timedelta(hours=8),
            origin="demo",
            generated_at=now,
            created_at=now - timedelta(minutes=12),
        )
        db.add(salinan)
        await db.flush()
        await _add_trace(
            db, salinan.id, "DETECT", 18, "demand.snapshot",
            {"location": "Jakarta", "ulangan": True},
            {"catatan": "kejadian kedua hari ini", "shortage_kg": float(kuantitas)},
        )
        await _add_trace(
            db, salinan.id, "DECIDE", 15, "supply_balance.propose",
            {"source_location_id": str(d.source_location_id), "qty": float(kuantitas)},
            {"catatan": "skema bertahap, mengacu kejadian sebelumnya",
             "sdc": float(biaya)},
        )
        if telur_id is not None and d.commodity_id == telur_id:
            await _ikat_sumber(db, salinan, now)
        ditambah += 1

    # Perbaikan data: batch beras Jakarta pernah terikat ke pemasok TELUR
    # ("CV Barokah Telur Cianjur"), sehingga peta menampilkan pemasok telur
    # mengirim beras. Ikat ulang ke pemasok beras yang satu hub.
    salah = (
        await db.execute(
            select(Batch, Supplier.commodity_id)
            .join(Supplier, Supplier.id == Batch.supplier_id)
            .where(
                Batch.location_id == jakarta.id,
                Supplier.commodity_id != Batch.commodity_id,
            )
        )
    ).all()
    diperbaiki = 0
    for batch, _ in salah:
        pengganti = (
            await db.execute(
                select(Supplier)
                .where(
                    Supplier.location_id == batch.location_id,
                    Supplier.commodity_id == batch.commodity_id,
                )
                .order_by(Supplier.name)
                .limit(1)
            )
        ).scalars().first()
        if pengganti is not None:
            batch.supplier_id = pengganti.id
            diperbaiki += 1

    return {"contoh_kedua": ditambah, "pemasok_diperbaiki": diperbaiki}


async def _approver_lokasi(
    db: AsyncSession, lokasi_id: uuid.UUID
) -> tuple[User | None, User | None]:
    """Kepala SPPG + ahli gizi milik lokasi itu (None bila belum ada akunnya)."""
    baris = (
        await db.execute(
            select(User).where(
                User.location_id == lokasi_id,
                User.role.in_(("sppg_head", "sppg_nutritionist")),
            )
        )
    ).scalars().all()
    kepala = next((u for u in baris if u.role == "sppg_head"), None)
    gizi = next((u for u in baris if u.role == "sppg_nutritionist"), None)
    return kepala, gizi


async def _pastikan_jejak_putusan(
    db: AsyncSession,
    putusan: Decision,
    *,
    peran: str,
    kepala: User,
    gizi: User | None,
    now: datetime,
) -> None:
    """Template wajib membawa jejak — dan approval — seperti alur nyata.

    Audit 21 Okt 2026: dua keputusan `supplier_exclusion` dibuat tanpa satu pun
    baris `agent_traces` (Agent Log kosong), dan yang berstatus `executed` tanpa
    baris `approvals`, padahal Rules.md §1.2 mewajibkan approval manusia sebelum
    aksi berisiko tinggi dieksekusi. Data contoh yang mengajarkan aturan berbeda
    dari sistemnya sendiri adalah cacat: juri bisa membukanya.

    Idempoten: hanya menambah langkah/approval yang belum ada, sehingga baris
    lama dari seed sebelumnya juga ikut tertambal.
    """
    langkah = [("DETECT", "detection_agent"), ("DECIDE", "supervisor_agent")]
    if peran == "aktif":
        langkah.append(("ACT", "sap_agent"))

    ada_langkah = set(
        (
            await db.execute(
                select(AgentTrace.step_name).where(AgentTrace.decision_id == putusan.id)
            )
        ).scalars()
    )
    dasar = putusan.created_at or now
    for urutan, (nama, agen) in enumerate(langkah):
        if nama in ada_langkah:
            continue
        db.add(
            AgentTrace(
                id=_uid("jejak-putusan", str(putusan.id), nama),
                decision_id=putusan.id,
                step_name=nama,
                agent_name=agen,
                tool_called=None,
                input_summary={"decision_type": putusan.decision_type},
                output_summary={
                    "catatan": (
                        f"Langkah {nama} untuk keputusan eksklusi ({peran}); "
                        "dibuat oleh template demo."
                    )
                },
                step_at=dasar + timedelta(minutes=urutan * 2),
            )
        )

    if peran != "aktif":
        return

    jumlah_appr = int(
        (
            await db.execute(
                select(func.count())
                .select_from(Approval)
                .where(Approval.decision_id == putusan.id, Approval.approved.is_(True))
            )
        ).scalar_one()
    )
    if jumlah_appr or gizi is None:
        return
    for urutan, (pengguna, komentar) in enumerate(
        (
            (kepala, "Disetujui setelah inspeksi suhu dan sertifikasi kedaluwarsa."),
            (gizi, "Diverifikasi ahli gizi: risiko keamanan pangan tidak dapat diterima."),
        )
    ):
        db.add(
            Approval(
                id=_uid("approval-putusan", str(putusan.id), str(pengguna.id)),
                decision_id=putusan.id,
                approved_by=pengguna.id,
                approved=True,
                approved_at=now - timedelta(days=2, minutes=-urutan * 10),
                comment=komentar,
            )
        )


async def _semai_eksklusi(db: AsyncSession, now: datetime) -> dict:
    """Satu eksklusi AKTIF (riwayat) + satu proposal MENUNGGU (bisa diputuskan live)."""
    jakarta = await _lokasi(db, "Jakarta")
    kepala = await _user(db, "sppg.head@demo.local")
    if jakarta is None or kepala is None:
        return {"dilewati": "Jakarta / akun kepala tidak ada"}

    pemasok = list(
        (
            await db.execute(
                select(Supplier)
                .where(Supplier.certification_status != "haccp")
                .order_by(Supplier.name)
                .limit(2)
            )
        ).scalars()
    )
    if len(pemasok) < 2:
        return {"dilewati": "pemasok tidak cukup"}

    hasil = {}
    putusan_by_peran: dict[str, Decision] = {}
    for peran, nama_status, aktor in (
        ("aktif", "active", kepala),
        ("menunggu", "proposed", kepala),
    ):
        p = pemasok[0] if peran == "aktif" else pemasok[1]
        kunci_putusan = _uid("putusan-eksklusi", peran, str(p.id))
        putusan = await db.get(Decision, kunci_putusan)
        if putusan is None:
            putusan = Decision(
                id=kunci_putusan,
                decision_type="supplier_exclusion",
                status="executed" if peran == "aktif" else "pending_approval",
                proposed_by="sppg_head",
                verified_by="verifier_agent",
                verifier_note="consistent",
                source_location_id=jakarta.id,
                target_location_id=jakarta.id,
                quantity_kg=None,
                safe_delivered_cost=None,
                expires_at=now + timedelta(days=30),
                created_at=now - timedelta(days=2 if peran == "aktif" else 0, hours=3),
                origin="seed",
                supplier_id=p.id,
            )
            db.add(putusan)
            await db.flush()

        putusan_by_peran[peran] = putusan
        hasil[f"putusan_{peran}"] = str(putusan.id)

        kunci_eks = _uid("eksklusi", peran, str(p.id))
        eks = await db.get(SupplierExclusion, kunci_eks)
        if eks is None:
            eks = SupplierExclusion(
                id=kunci_eks,
                supplier_id=p.id,
                scope_location_id=jakarta.id,
                status=nama_status,
                reason=(
                    "Dua kiriman telur berturut-turut datang di atas ambang suhu; "
                    "sertifikasi HACCP belum diperbarui."
                    if peran == "aktif"
                    else "Kemasan retak pada pengiriman terakhir; menunggu klarifikasi pemasok."
                ),
                evidence_refs=[{"type": "human_inspection", "ref": f"inspeksi-{peran}"}],
                source_decision_id=putusan.id,
                proposed_by=aktor.id,
                approved_at=now - timedelta(days=2) if peran == "aktif" else None,
                activated_at=now - timedelta(days=2, hours=-1) if peran == "aktif" else None,
                created_at=now - timedelta(days=3 if peran == "aktif" else 0, hours=4),
            )
            db.add(eks)
        hasil[peran] = str(kunci_eks)

    gizi = await _user(db, "sppg.nutritionist@demo.local")
    for peran, putusan in putusan_by_peran.items():
        await _pastikan_jejak_putusan(
            db, putusan, peran=peran, kepala=kepala, gizi=gizi, now=now
        )
    await db.flush()
    return hasil


async def _semai_status_tambahan(db: AsyncSession, now: datetime) -> dict:
    """Dua status yang belum terwakili di template (audit 21 Okt 2026, P4).

    DB mengizinkan tujuh status, template hanya memuat lima. Layar `approved`
    (sudah disetujui, belum dieksekusi) dan `review_only` (temuan tanpa jumlah,
    tidak bisa dieksekusi) tidak pernah bisa diperlihatkan — padahal keduanya
    jalur nyata: `approved` adalah jeda antara persetujuan dan eksekusi, dan
    `review_only` adalah bentuk terminal Event 2 (temuan harga).

    Kedua baris membawa jejak; yang `approved` juga membawa dua approval (aturan
    dua peran) tanpa PO, karena eksekusinya memang belum dijalankan.
    """
    bandung = await _lokasi(db, "Bandung")
    cianjur = await _lokasi(db, "Cianjur")
    beras = (
        await db.execute(select(Commodity).where(Commodity.name.ilike("beras")).limit(1))
    ).scalar_one_or_none()
    kepala = await _user(db, "sppg.head@demo.local")
    gizi = await _user(db, "sppg.nutritionist@demo.local")
    if bandung is None or cianjur is None or beras is None or kepala is None:
        return {"dilewati": "lokasi/komoditas/akun kepala tidak lengkap"}

    # Approver mengikuti lokasi TUJUAN, bukan Jakarta. Audit 21 Okt 2026:
    # keputusan target Bandung disetujui akun Jakarta, sehingga layar persetujuan
    # menunjukkan approver dari kota yang tidak berwenang (dan tes
    # `test_semua_approval_sesuai_lokasi_target` merah).
    kepala_bandung, gizi_bandung = await _approver_lokasi(db, bandung.id)
    kepala = kepala_bandung or kepala
    gizi = gizi_bandung or gizi

    async def jejak(putusan: Decision, langkah: tuple[tuple[str, str], ...]) -> None:
        ada = set(
            (
                await db.execute(
                    select(AgentTrace.step_name).where(AgentTrace.decision_id == putusan.id)
                )
            ).scalars()
        )
        dasar = putusan.created_at or now
        for urutan, (nama, agen) in enumerate(langkah):
            if nama in ada:
                continue
            db.add(
                AgentTrace(
                    id=_uid("jejak-status", str(putusan.id), nama),
                    decision_id=putusan.id,
                    step_name=nama,
                    agent_name=agen,
                    input_summary={"decision_type": putusan.decision_type},
                    output_summary={"catatan": f"Langkah {nama} (template status demo)."},
                    step_at=dasar + timedelta(minutes=2 * urutan),
                )
            )

    hasil: dict[str, str] = {}

    # (1) approved — dua approval lengkap, eksekusi belum dijalankan.
    kunci = _uid("status", "approved")
    siap = await db.get(Decision, kunci)
    if siap is None:
        siap = Decision(
            id=kunci,
            decision_type="regional_balance",
            status="approved",
            proposed_by="sppg_head",
            verified_by="verifier_agent",
            verifier_note="consistent",
            source_location_id=cianjur.id,
            target_location_id=bandung.id,
            commodity_id=beras.id,
            quantity_kg=Decimal("120"),
            safe_delivered_cost=Decimal("1440000"),
            cost_breakdown={"catatan": "sudah disetujui, eksekusi belum dijalankan"},
            expires_at=now + timedelta(hours=6),
            created_at=now - timedelta(minutes=45),
            origin="seed",
        )
        db.add(siap)
        await db.flush()
    hasil["approved"] = str(siap.id)
    await jejak(siap, (("DETECT", "detection_agent"), ("DECIDE", "supervisor_agent")))
    jumlah = int(
        (
            await db.execute(
                select(func.count())
                .select_from(Approval)
                .where(Approval.decision_id == siap.id, Approval.approved.is_(True))
            )
        ).scalar_one()
    )
    if jumlah == 0:
        for urutan, (pengguna, komentar) in enumerate(
            (
                (kepala, "Disetujui; menunggu eksekusi ke SAP simulasi."),
                (gizi, "Diverifikasi gizinya; jumlah dan tujuan sesuai kebutuhan."),
            )
        ):
            if pengguna is None:
                continue
            db.add(
                Approval(
                    id=_uid("approval-status", str(siap.id), str(pengguna.id)),
                    decision_id=siap.id,
                    approved_by=pengguna.id,
                    approved=True,
                    approved_at=now - timedelta(minutes=20 - urutan * 5),
                    comment=komentar,
                )
            )

    # (2) review_only — temuan harga tanpa jumlah; tidak ada jalur eksekusi.
    kunci = _uid("status", "review_only")
    tinjau = await db.get(Decision, kunci)
    if tinjau is None:
        tinjau = Decision(
            id=kunci,
            decision_type="price_anomaly",
            status="review_only",
            proposed_by="event2_pipeline",
            source_location_id=cianjur.id,
            target_location_id=bandung.id,
            commodity_id=beras.id,
            quantity_kg=None,
            expires_at=now + timedelta(hours=3),
            created_at=now - timedelta(minutes=25),
            cost_breakdown={
                "reference_price_per_kg": "12000",
                "quoted_price_per_kg": "13680",
                "deviation_pct": "14.0",
                "classification": "above_band",
            },
            origin="seed",
        )
        db.add(tinjau)
        await db.flush()
    hasil["review_only"] = str(tinjau.id)
    await jejak(tinjau, (("DETECT", "detection_agent"), ("DECIDE", "supervisor_agent")))

    # (3) proposed — pengadaan dari pemasok (supplier_procurement) yang belum
    # diputuskan. Ini satu-satunya status `proposed` di template: jalur "usulan
    # baru masuk, belum diverifikasi" harus bisa diperlihatkan.
    pemasok = (
        await db.execute(select(Supplier).order_by(Supplier.name).limit(1))
    ).scalar_one_or_none()
    if pemasok is not None:
        kunci = _uid("status", "proposed_procurement")
        usul = await db.get(Decision, kunci)
        if usul is None:
            usul = Decision(
                id=kunci,
                decision_type="supplier_procurement",
                status="proposed",
                proposed_by="sppg_head",
                target_location_id=bandung.id,
                supplier_id=pemasok.id,
                commodity_id=beras.id,
                quantity_kg=Decimal("200"),
                safe_delivered_cost=Decimal("2480000"),
                cost_breakdown={
                    "quote_price_per_kg": "12400",
                    "catatan": "usulan pengadaan baru; belum diverifikasi",
                },
                expires_at=now + timedelta(hours=8),
                created_at=now - timedelta(minutes=12),
                origin="seed",
            )
            db.add(usul)
            await db.flush()
        hasil["proposed"] = str(usul.id)
        await jejak(usul, (("DETECT", "detection_agent"), ("DECIDE", "supervisor_agent")))

    # (4) supplier_exclusion_restoration — usul memulihkan pemasok yang sedang
    # dikecualikan. Tipe ini ada di DB dan di alur `/supplier-exclusions/{id}/restore`,
    # tetapi tidak pernah muncul di data demo.
    eksklusi = (
        await db.execute(
            select(SupplierExclusion).order_by(SupplierExclusion.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if eksklusi is not None:
        kunci = _uid("status", "restoration")
        pulih = await db.get(Decision, kunci)
        if pulih is None:
            pulih = Decision(
                id=kunci,
                decision_type="supplier_exclusion_restoration",
                status="pending_approval",
                proposed_by="sppg_head",
                target_location_id=eksklusi.scope_location_id,
                supplier_id=eksklusi.supplier_id,
                cost_breakdown={
                    "catatan": "pemasok memperbaiki temuan; usul pemulihan menunggu keputusan",
                    "exclusion_id": str(eksklusi.id),
                },
                expires_at=now + timedelta(hours=12),
                created_at=now - timedelta(minutes=18),
                origin="seed",
            )
            db.add(pulih)
            await db.flush()
        hasil["restoration"] = str(pulih.id)
        await jejak(
            pulih, (("DETECT", "detection_agent"), ("DECIDE", "supervisor_agent"))
        )
    return hasil


async def _pengguna_lokasi(db: AsyncSession, lokasi, peran: str) -> User | None:
    """Akun DEMO pertama untuk satu lokasi+peran.

    Kegagalan 21 Okt 2026: suite tes meninggalkan belasan `sppg_head-*@test.local`
    di Jakarta. Query `location_id + role` lalu `scalar_one_or_none()` melempar
    MultipleResultsFound dan MEMATIKAN seluruh bangun-ulang. Penyemai template
    tidak boleh bergantung pada kebersihan akun, jadi akun uji disaring keluar
    dan hasilnya dibatasi satu baris.
    """
    hasil = await db.execute(
        select(User)
        .where(
            User.location_id == lokasi,
            User.role == peran,
            User.email.not_like("%@test.local"),
        )
        .order_by(User.email)
        .limit(1)
    )
    return hasil.scalar_one_or_none()


async def _semai_bukti_dan_rantai(db: AsyncSession, now: datetime) -> dict:
    """Lengkapi dua hal yang membuat tab audit & KPI "hidup" sejak awal:

    1. Rantai ledger dibangun ulang dari keputusan yang ADA (bukan sisa entitas
       yang sudah dihapus). Tanpa ini `GET /ledger/verify` melaporkan 570 blok
       yatim: hash-nya benar, tetapi tidak satu pun menunjuk entitas nyata.
    2. Approval + dua jenis bukti untuk keputusan yang sudah dieksekusi, supaya
       metrik "Evidence Completeness" berhenti `no_data` dan punya angka yang
       bisa bergerak saat demo (setujui satu keputusan baru -> penyebut naik).
    """
    from app.models import Approval, DecisionEvidence
    from app.services.ledger_service import append_block, bump_generation

    # Residu audit N3 (24 Okt 2026): dulu baris ini mengosongkan tabel ledger,
    # sehingga "Siapkan data demo" menghapus SELURUH jejak audit — termasuk arsip
    # generasi lama yang justru bukti bahwa data pernah ada. Sekarang cukup
    # naikkan generasi: blok lama tetap tersimpan (dilaporkan `archived_blocks`),
    # dan blok baru ditulis di atas rantai yang sama sehingga `prev_hash` tetap
    # nyambung.
    await bump_generation(db)
    keputusan = list(
        (await db.execute(select(Decision).order_by(Decision.created_at))).scalars()
    )
    blok = 0
    for d in keputusan:
        await append_block(
            db, action="decision.created", entity_id=d.id, actor_id=None,
            payload={"decision_id": str(d.id), "decision_type": d.decision_type,
                     "status_at_creation": "proposed"},
        )
        blok += 1
        if d.verified_by:
            await append_block(
                db, action="verify", entity_id=d.id, actor_id=None,
                payload={"decision_id": str(d.id), "verdict": d.verifier_note or "unknown"},
            )
            blok += 1
        if d.status == "executed":
            await append_block(
                db, action="execute", entity_id=d.id, actor_id=None,
                payload={"decision_id": str(d.id), "decision_type": d.decision_type},
            )
            blok += 1
        elif d.status == "rejected":
            await append_block(
                db, action="reject", entity_id=d.id, actor_id=None,
                payload={"decision_id": str(d.id), "reason": d.rejection_reason or ""},
            )
            blok += 1

    # Approval + bukti untuk keputusan operasional yang sudah dieksekusi.
    ditambah_approval = 0
    ditambah_bukti = 0
    ditambah_po = 0
    for d in keputusan:
        if d.status != "executed" or d.decision_type != "regional_balance":
            continue
        target = d.target_location_id
        if target is None:
            continue
        kepala = await _pengguna_lokasi(db, target, "sppg_head")
        gizi = await _pengguna_lokasi(db, target, "sppg_nutritionist")
        if kepala is None or gizi is None:
            continue
        ada = (
            await db.execute(
                select(func.count()).select_from(Approval).where(Approval.decision_id == d.id)
            )
        ).scalar_one()
        kapan = (d.created_at or now) + timedelta(minutes=4)
        if not ada:
            for u in (kepala, gizi):
                db.add(
                    Approval(
                        id=_uid("approval", str(d.id), u.role),
                        decision_id=d.id,
                        approved_by=u.id,
                        approved=True,
                        comment="Disetujui setelah bukti dicek ulang.",
                        approved_at=kapan,
                    )
                )
                ditambah_approval += 1
        for jenis, isi in (
            ("sap_purchase_order", {"po_number": f"MC-TEMPLATE-{str(d.id)[:8].upper()}"}),
            ("human_inspection", {"inspeksi": "gudang", "hasil": "sesuai"}),
        ):
            kunci = _uid("bukti", str(d.id), jenis)
            if await db.get(DecisionEvidence, kunci) is None:
                db.add(
                    DecisionEvidence(
                        id=kunci,
                        decision_id=d.id,
                        evidence_type=jenis,
                        payload=isi,
                        is_consistent=True,
                        recorded_at=kapan - timedelta(minutes=5),
                    )
                )
                ditambah_bukti += 1

        # PO untuk tab SAP. `GET /sap/purchase-orders` menyaring lewat
        # keputusan → target lokasi, jadi PO tanpa `decision_id` tidak pernah
        # terlihat oleh kepala SPPG (terukur 21 Okt 2026: 0 baris untuk Jakarta
        # meski tabel berisi 16 PO impor). Baris di sini adalah PO yang LAHIR
        # dari keputusan, jadi nomornya memakai `nomor_po` yang sama dengan
        # eksekusi nyata.
        if d.supplier_id is not None:
            nama_komoditas = (
                await db.execute(
                    select(Commodity.name).where(Commodity.id == d.commodity_id)
                )
            ).scalar_one_or_none()
            kuantitas = d.quantity_kg or Decimal("0")
            harga = (
                (d.safe_delivered_cost / kuantitas)
                if kuantitas and d.safe_delivered_cost
                else Decimal("24900")
            )
            kunci_po = _uid("po", str(d.id))
            # Idempotensi dicek lewat NOMOR, bukan id: baris PO bisa sudah ada
            # dengan id lain tetapi nomor yang sama (mis. sisa builder versi
            # sebelumnya), dan `po_number` unik — menyisipkan ulang membuat
            # seluruh bangun-ulang gagal dengan UniqueViolation.
            nomor = nomor_po(d.id)
            sudah = (
                await db.execute(
                    select(SapMockPurchaseOrder.id).where(
                        SapMockPurchaseOrder.po_number == nomor
                    )
                )
            ).scalar_one_or_none()
            if sudah is None:
                db.add(
                    SapMockPurchaseOrder(
                        id=kunci_po,
                        po_number=nomor,
                        supplier_id=d.supplier_id,
                        material_number=f"MAT-{(nama_komoditas or 'UMUM').upper()[:4]}",
                        ordered_quantity=kuantitas,
                        price=harga,
                        decision_id=d.id,
                        status="confirmed",
                        origin="demo",
                        created_at=kapan + timedelta(minutes=2),
                    )
                )
                ditambah_po += 1
    await db.flush()
    return {
        "blok_ledger": blok,
        "approval": ditambah_approval,
        "bukti": ditambah_bukti,
        "po": ditambah_po,
    }



async def _lengkapi_bukti_kasus(db: AsyncSession, now: datetime) -> dict:
    """Beri bukti pada keputusan yang tampil di layar tetapi belum punya bukti.

    Audit 21 Okt 2026: di Jakarta, delapan keputusan (anomali harga, dua
    `supplier_exclusion` yang dieksekusi/diusulkan, satu restorasi, dan tiga
    keputusan yang ditolak) tidak punya satu pun baris `decision_evidence`.
    Panel "Decision & Evidence" lalu kosong untuk kasus yang justru dipakai
    bercerita tentang pemasok berisiko — data yang mengajar aturan berbeda dari
    sistemnya sendiri.

    Bukti di sini adalah catatan kasus (bukan verdict verifier): payload-nya
    menyebut jenis pemeriksaan dan ringkasan temuan, deterministik per keputusan
    sehingga menyemai ulang tidak menggandakan baris.
    """
    from app.models import DecisionEvidence

    # NIlai `evidence_type` DIBATASI constraint DB (`decision_evidence_type_check`):
    # sap_purchase_order | sap_goods_receipt | gps | temperature | human_inspection |
    # market_price. Jenis karangan seperti "inspeksi_pemasok" ditolak Postgres dan
    # menggagalkan seluruh build (terukur 21 Okt 2026: build berhenti di 25 keputusan).
    jenis_bukti = {
        "supplier_exclusion": (
            "human_inspection",
            "Dua kiriman berturut-turut di atas ambang suhu.",
        ),
        "supplier_exclusion_restoration": (
            "human_inspection",
            "Pemeriksaan ulang: suhu dan kemasan kembali normal.",
        ),
        "price_anomaly": ("market_price", "Harga kutipan 32% di atas median pemasok sekitarnya."),
        "regional_balance": ("human_inspection", "Pasokan, kebutuhan, dan jarak dihitung ulang."),
        "safety_disruption": ("temperature", "Log suhu dan hasil uji laboratorium diperiksa."),
    }
    keputusan = list(
        (
            await db.execute(
                select(Decision)
                .where(
                    Decision.status.in_(("executed", "approved", "verifier_flagged"))
                    | Decision.decision_type.like("supplier_exclusion%")
                )
                .order_by(Decision.created_at)
            )
        ).scalars()
    )
    ditambah = 0
    for d in keputusan:
        ada = (
            await db.execute(
                select(func.count())
                .select_from(DecisionEvidence)
                .where(DecisionEvidence.decision_id == d.id)
            )
        ).scalar_one()
        if ada:
            continue
        jenis, catatan = jenis_bukti.get(
            d.decision_type, ("human_inspection", "Kasus diperiksa manual oleh supervisor.")
        )
        db.add(
            DecisionEvidence(
                id=_uid("bukti-kasus", str(d.id)),
                decision_id=d.id,
                evidence_type=jenis,
                payload={"catatan": catatan, "jenis_kasus": d.decision_type, "demo": True},
                is_consistent=True,
                recorded_at=d.created_at or now,
            )
        )
        ditambah += 1
    await db.flush()
    return {"bukti_ditambah": ditambah}


async def _bekukan(db: AsyncSession) -> dict:
    """Balik semua baris demo menjadi template yang tidak ikut dibuang."""
    total = 0
    for model in sesi.model_bersesi():
        nilai = {"demo_session_id": None}
        if "origin" in model.__table__.columns:
            nilai["origin"] = "seed"
        hasil = await db.execute(
            update(model).values(**nilai).execution_options(synchronize_session=False)
        )
        total += int(hasil.rowcount or 0)
    await db.commit()
    return {"baris_dibekukan": total}


async def _bersihkan_sisa(db: AsyncSession) -> dict:
    """Hapus akun uji dan sesi demo lama supaya daftar tidak penuh residu.

    Enam tabel merujuk `users`; empat di antaranya tanpa ON DELETE, jadi baris
    turunannya dibersihkan lebih dulu. Yang dihapus hanya milik akun uji —
    approval/receipt milik akun demo tidak disentuh.
    """
    from app.models import Approval

    uji = select(User.id).where(
        (User.email.like("%@test.local")) | (User.email.like("%@uji-peran.local"))
    )
    ids = list((await db.execute(uji)).scalars())
    if not ids:
        return {"user_uji_dihapus": 0, "sesi_dihapus": 0}

    await db.execute(delete(Approval).where(Approval.approved_by.in_(ids)))
    await db.execute(delete(BatchReceipt).where(BatchReceipt.recorded_by.in_(ids)))
    await db.execute(delete(SupplierExclusion).where(SupplierExclusion.proposed_by.in_(ids)))
    await db.execute(
        update(Batch)
        .where(Batch.quarantine_actor_id.in_(ids))
        .values(quarantine_actor_id=None)
        .execution_options(synchronize_session=False)
    )
    await db.execute(
        update(sesi.DemoSession)
        .where(sesi.DemoSession.created_by.in_(ids))
        .values(created_by=None)
        .execution_options(synchronize_session=False)
    )
    user = await db.execute(delete(User).where(User.id.in_(ids)))
    # JANGAN hapus sesi AKTIF. Versi sebelumnya `delete(DemoSession)` tanpa
    # syarat mematikan sesi yang baru dibuat `pastikan_sesi` di awal build;
    # akibatnya build selesai dalam keadaan "tanpa sesi", lalu permintaan baca
    # berikutnya menyapu/menyegarkan data dan 43 batch hilang (terukur
    # 21 Okt 2026: 121 -> 78 dalam 30 detik).
    sesi_lama = await db.execute(
        delete(sesi.DemoSession).where(sesi.DemoSession.status != "active")
    )
    await db.commit()
    return {
        "user_uji_dihapus": int(user.rowcount or 0),
        "sesi_dihapus": int(sesi_lama.rowcount or 0),
    }


async def hitung(db: AsyncSession) -> dict:
    async def satu(model) -> int:
        return int((await db.execute(select(func.count()).select_from(model))).scalar_one())

    asal = {}
    for model in sesi.model_bersesi():
        if "origin" not in model.__table__.columns:
            continue
        hasil = await db.execute(
            select(model.__table__.c.origin, func.count()).group_by(model.__table__.c.origin)
        )
        for o, n in hasil.all():
            asal[f"{model.__tablename__}.{o}"] = int(n)
    return {
        "batches": await satu(Batch),
        "decisions": await satu(Decision),
        "receipts": await satu(BatchReceipt),
        "eksklusi": await satu(SupplierExclusion),
        "users": await satu(User),
        # Tiga angka ini dipakai layar setelah "bangun ulang": tanpa mereka,
        # operator hanya melihat batch/keputusan dan mengira pesanan atau rantai
        # bukti hilang padahal ada.
        # `ledger_blocks` sengaja tidak punya model ORM (append-only lewat SQL
        # mentah di ledger_service), jadi dihitung langsung.
        "ledger": int(
            (await db.execute(text("SELECT count(*) FROM ledger_blocks"))).scalar_one()
        ),
        "traces": await satu(AgentTrace),
        "po": await satu(SapMockPurchaseOrder),
        "origin": asal,
    }


async def pastikan_sesi(db: AsyncSession):
    """Pastikan ada sesi demo aktif sebelum menyemai template.

    Kenapa wajib (audit 21 Okt 2026): baris hasil semai ber-`origin='demo'` dan
    belum ber-stempel sampai `_bekukan` selesai. Selama celah itu, aplikasi yang
    sedang hidup (polling 5 detik) memanggil `sapu_tanpa_sesi` dan MENGHAPUS baris
    yang baru lahir — build berakhir dengan 0 batch meski log terlihat sukses.
    Dengan sesi aktif, penyapu menolak bekerja (`_sesi_aktif_terakhir` tidak None)
    dan UI sekaligus menampilkan data begitu build selesai.
    """
    aktif = await sesi.aktif(db)
    if aktif is not None:
        return aktif
    jakarta = await _lokasi(db, "Jakarta")
    kepala = await _pengguna_lokasi(db, jakarta.id, "sppg_head") if jakarta else None
    return await sesi.mulai(db, created_by=kepala.id if kepala else None)


async def build_into(db: AsyncSession, *, purge: bool = True, freeze: bool = True,
                     bersihkan_sisa: bool = True) -> dict:
    """Bangun template di sesi DB yang sudah ada (dipakai CLI dan endpoint sesi)."""
    now = datetime.now(timezone.utc)
    laporan: dict = {}
    if purge:
        laporan["dibersihkan"] = await sesi.kosongkan_kecuali(db, None)
    laporan["inti"] = await _semai_inti(db, now)
    laporan["kasus"] = await _semai_kasus(db)
    laporan["kasus_jakarta"] = await _perkaya_kasus_jakarta(db, now)
    laporan["karantina"] = await _semai_karantina(db, now)
    laporan["penerimaan"] = await _semai_penerimaan(db, now)
    laporan["eksklusi"] = await _semai_eksklusi(db, now)
    laporan["status_tambahan"] = await _semai_status_tambahan(db, now)
    laporan["bukti"] = await _semai_bukti_dan_rantai(db, now)
    laporan["bukti_tambahan"] = await _lengkapi_bukti_kasus(db, now)
    laporan["kiriman_jakarta"] = await _rapikan_kiriman_jakarta(db, now)
    # KPI 24 jam dimulai dari "belum ada aksi hari ini": jejak aksi (keputusan,
    # bukti, approval, PO, trace) digeser ke riwayat, sedangkan fakta hari ini
    # (menu plan, kiriman, limbah, kutipan harga) tetap. Lihat
    # `app/seed/demo_kpi_riwayat.py` untuk alasan pembagiannya.
    laporan["kpi_riwayat"] = await geser_aksi_ke_riwayat(db, now)
    # Satu kasus sengaja TIDAK digeser: keputusan menunggu persetujuan dengan
    # dua jenis bukti, supaya operator bisa menyalakan "Kelengkapan Bukti"
    # dengan satu approval tanpa mengubah rumus KPI. Lihat
    # `app/seed/demo_kasus_bukti.py`.
    laporan["kasus_bukti"] = await semai_kasus_bukti_hari_ini(db, now)
    await db.commit()
    if freeze:
        laporan["beku"] = await _bekukan(db)
    if bersihkan_sisa:
        laporan["bersih"] = await _bersihkan_sisa(db)
    laporan["hitung"] = await hitung(db)
    return laporan


async def build(dry_run: bool = False) -> dict:
    eng = create_engine(settings.database_url)
    maker = create_session_maker(eng)
    laporan: dict = {}
    try:
        async with maker() as db:
            if dry_run:
                return {"dry_run": True, "isi_sekarang": await hitung(db)}

            # Sesi aktif melindungi baris 'demo' dari penyapu di proses aplikasi.
            await pastikan_sesi(db)
            laporan = await build_into(db)
    finally:
        await eng.dispose()
    return laporan


def main() -> None:
    parser = argparse.ArgumentParser(description="Bangun template data demo MealChain Guardian")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    hasil = asyncio.run(build(dry_run=args.dry_run))
    import json

    print(json.dumps(hasil, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
