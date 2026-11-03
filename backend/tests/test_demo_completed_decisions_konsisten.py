"""Keputusan "selesai" hasil penyemai KPI harus KOheren, bukan cuma berstatus executed.

Latar (temuan 17 Okt 2026): `seed_demo_completed_decisions` menulis keputusan
`executed` untuk mengisi kartu KPI "hari ini" (tiga kota demo bergilir komoditas,
ditambah beras untuk Jakarta), tetapi bukti yang menyertainya tidak
cukup untuk membenarkan status itu. Saat ringkasan persetujuannya dibuka, layar
menampilkan penghalang yang mustahil pada keputusan yang sudah dieksekusi:

    supplier_unknown: keputusan lama perlu binding batch eksplisit
    approval belum memenuhi requirement (missing/rejected)
    safety revalidation gagal: tidak ada batch sumber

Sebabnya tiga, semuanya di penyemai:
1. hanya SATU approval (kepala SPPG) padahal `regional_balance` operasional wajib
   dua role (`dua_role_wajib`);
2. tidak ada `decision_evidence.payload.allocation_binding`, sehingga pemasok
   tidak bisa dipastikan;
3. tidak ada batch sumber untuk pasangan (lokasi, komoditas) itu, sehingga
   revalidasi keamanan melaporkan "tidak ada batch sumber".

Tes ini mengunci janji bahwa penyemai menghasilkan riwayat yang utuh: dua
approval dari dua role, binding eksplisit ke batch yang benar-benar ada, dan
satu-satunya alasan penghalang yang tersisa adalah "decision sudah dieksekusi"
(kenyataan, bukan cacat).

Penyemai bersifat idempoten (id deterministik), jadi tes ini aman dijalankan
berulang dan tidak perlu membersihkan barisnya: baris yang ia buat justru yang
dipakai layar demo.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from app.core.config import settings
from app.db import create_engine, create_session_maker
from app.models import Approval, Batch, Decision, DecisionEvidence, DemoSession, User
from app.seed.demo_activity import (
    KOTA_DEMO,
    demo_decision_id,
    seed_demo_completed_decisions,
)
from app.services.approval_summary import build_approval_summary

ROLE_WAJIB = {"sppg_head", "sppg_nutritionist"}


async def _jalankan() -> tuple[dict, list[Decision], dict]:
    """Jalankan penyemai, lalu baca kembali keputusan selesai + ringkasannya."""
    sekarang = datetime.now(UTC)  # jam nyata, sama seperti tombol "Segarkan"
    engine = create_engine(settings.database_url)
    maker = create_session_maker(engine)
    try:
        async with maker() as sesi:
            hasil = await seed_demo_completed_decisions(sesi, sekarang)
            await sesi.commit()

        async with maker() as sesi:
            # Cakup HANYA baris yang lahir dari penyemai KPI ini. `jakarta_lengkap`
            # juga menulis keputusan `origin='demo'`/`demo_case IS NULL`/`executed`
            # (riwayat umum, bukan kasus penyemai ini), dan baris itu tidak punya
            # jaminan dua approval + allocation_binding. Id penyemai deterministik
            # (`demo_decision_id`), jadi himpunannya bisa dihitung tanpa menebak.
            id_penyemai = {
                demo_decision_id(nama, komoditas)
                for nama in KOTA_DEMO
                for komoditas in ("telur", "ayam", "wortel", "beras")
            }
            keputusan = list(
                (
                    await sesi.execute(
                        select(Decision)
                        .where(
                            Decision.id.in_(id_penyemai),
                            Decision.origin == "demo",
                            Decision.demo_case.is_(None),
                            Decision.status == "executed",
                        )
                        .order_by(Decision.id)
                    )
                ).scalars()
            )
            ringkasan = {
                d.id: await build_approval_summary(sesi, d) for d in keputusan
            }
        return hasil, keputusan, ringkasan
    finally:
        await engine.dispose()


async def _peta_nama() -> tuple[dict, dict]:
    from app.models import Commodity, Location

    engine = create_engine(settings.database_url)
    maker = create_session_maker(engine)
    try:
        async with maker() as sesi:
            lokasi = {
                lok.id: lok.name
                for lok in (await sesi.execute(select(Location))).scalars()
            }
            komoditas = {
                c.id: c.name for c in (await sesi.execute(select(Commodity))).scalars()
            }
        return lokasi, komoditas
    finally:
        await engine.dispose()


async def test_penyemai_menghasilkan_satu_keputusan_per_pasangan_kota_komoditas() -> None:
    """Jumlah kota demo boleh berubah; yang dikunci adalah SATU baris per pasangan.

    Sebelumnya tes ini menuntut tepat 3 baris, lalu merah ketika penyemai mulai
    menyemai beras untuk Jakarta secara eksplisit (permintaan pemilik 18 Okt:
    panel Decision & Evidence perlu baris beras). Asersi yang benar bukan
    "3", melainkan "tidak ada pasangan ganda" + pasangan wajib ada.
    """
    _, keputusan, _ = await _jalankan()
    pasangan = {(d.target_location_id, d.commodity_id) for d in keputusan}
    assert len(pasangan) == len(keputusan), (
        "penyemai membuat lebih dari satu keputusan untuk pasangan lokasi×komoditas "
        f"yang sama: {len(keputusan)} baris, {len(pasangan)} pasangan"
    )
    assert len(keputusan) >= 3, (
        "penyemai KPI harus mengisi minimal tiga kota demo; "
        f"dapat {len(keputusan)}"
    )

    nama_lokasi, nama_komoditas = await _peta_nama()
    berpasangan = {
        (nama_lokasi.get(d.target_location_id), nama_komoditas.get(d.commodity_id))
        for d in keputusan
    }
    assert ("Jakarta", "beras") in berpasangan, (
        "beras Jakarta disemai eksplisit supaya panel Decision & Evidence punya "
        f"baris beras; pasangan yang ada: {sorted(map(str, berpasangan))}"
    )


async def test_setiap_keputusan_selesai_punya_dua_approval_dua_role() -> None:
    _, keputusan, _ = await _jalankan()

    engine = create_engine(settings.database_url)
    maker = create_session_maker(engine)
    try:
        async with maker() as sesi:
            for d in keputusan:
                baris = list(
                    (
                        await sesi.execute(
                            select(Approval).where(Approval.decision_id == d.id)
                        )
                    ).scalars()
                )
                assert baris, f"keputusan {d.id} tidak punya satu pun approval"
                assert all(a.approved for a in baris), (
                    f"keputusan selesai {d.id} punya approval yang menolak"
                )
                user_ids = {a.approved_by for a in baris}
                peran = set(
                    (
                        await sesi.execute(
                            select(User.role).where(User.id.in_(user_ids))
                        )
                    ).scalars()
                )
                assert peran >= ROLE_WAJIB, (
                    f"keputusan {d.id} hanya disetujui {sorted(peran)}; "
                    f"regional_balance operasional wajib {sorted(ROLE_WAJIB)}"
                )
    finally:
        await engine.dispose()


async def test_binding_menunjuk_batch_sumber_yang_benar_benar_ada() -> None:
    _, keputusan, _ = await _jalankan()

    engine = create_engine(settings.database_url)
    maker = create_session_maker(engine)
    try:
        async with maker() as sesi:
            for d in keputusan:
                bukti = list(
                    (
                        await sesi.execute(
                            select(DecisionEvidence).where(
                                DecisionEvidence.decision_id == d.id
                            )
                        )
                    ).scalars()
                )
                binding = [
                    e.payload
                    for e in bukti
                    if (e.payload or {}).get("allocation_binding") is True
                ]
                assert len(binding) == 1, (
                    f"keputusan {d.id} harus punya tepat satu allocation_binding; "
                    f"dapat {len(binding)}"
                )
                ids = binding[0]["batch_ids"]
                assert ids, f"binding keputusan {d.id} tidak menyebut batch"

                batch = list(
                    (
                        await sesi.execute(
                            select(Batch).where(
                                Batch.id.in_([uuid.UUID(b) for b in ids])
                            )
                        )
                    ).scalars()
                )
                assert batch, f"binding keputusan {d.id} menunjuk batch yang tidak ada"
                for b in batch:
                    assert b.location_id == d.source_location_id
                    assert b.commodity_id == d.commodity_id
                    assert b.safety_status == "pass", (
                        f"batch sumber {b.id} berstatus {b.safety_status}; "
                        "keputusan selesai tidak boleh bersandar pada batch gagal"
                    )
    finally:
        await engine.dispose()


async def test_menyemai_ulang_menyembuhkan_binding_yang_menunjuk_batch_hilang() -> None:
    """Batch demo bisa hilang (Bersihkan data demo / tes yang membersihkan kiriman).

    Binding yang tetap menunjuk baris yang sudah tidak ada membuat resolusi gagal
    ("binding batch/supplier berubah") pada keputusan yang statusnya `executed`.
    Menyemai ulang harus MENULIS ULANG payload-nya, bukan melewatinya karena id-nya
    sudah ada.
    """
    _, keputusan, _ = await _jalankan()
    assert keputusan, "penyemai tidak membuat keputusan selesai"
    target = keputusan[0]

    engine = create_engine(settings.database_url)
    maker = create_session_maker(engine)
    try:
        async with maker() as sesi:
            bukti = list(
                (
                    await sesi.execute(
                        select(DecisionEvidence).where(
                            DecisionEvidence.decision_id == target.id
                        )
                    )
                ).scalars()
            )
            ids = [
                uuid.UUID(b)
                for e in bukti
                if (e.payload or {}).get("allocation_binding") is True
                for b in e.payload["batch_ids"]
            ]
            await sesi.execute(delete(Batch).where(Batch.id.in_(ids)))
            await sesi.commit()

        # Semai ulang: harus menyembuhkan, bukan melempar atau membiarkan rusak.
        async with maker() as sesi:
            await seed_demo_completed_decisions(sesi, datetime.now(UTC))
            await sesi.commit()

        async with maker() as sesi:
            d = await sesi.get(Decision, target.id)
            r = await build_approval_summary(sesi, d)
        assert r["supplier"] is not None, (
            f"pemasok masih tidak terbaca: {r['blocking_reasons']}"
        )
        assert r["blocking_reasons"] == ["decision sudah dieksekusi"], (
            f"penghalang sisa setelah penyemaian ulang: {r['blocking_reasons']}"
        )
    finally:
        await engine.dispose()


async def _batch_terikat(decision_id: uuid.UUID) -> list[uuid.UUID]:
    """Id batch yang disebut `allocation_binding` milik satu keputusan."""
    engine = create_engine(settings.database_url)
    maker = create_session_maker(engine)
    try:
        async with maker() as sesi:
            bukti = list(
                (
                    await sesi.execute(
                        select(DecisionEvidence).where(
                            DecisionEvidence.decision_id == decision_id
                        )
                    )
                ).scalars()
            )
            return [
                uuid.UUID(b)
                for e in bukti
                if (e.payload or {}).get("allocation_binding") is True
                for b in e.payload["batch_ids"]
            ]
    finally:
        await engine.dispose()


async def _ringkasan(decision_id: uuid.UUID) -> dict:
    engine = create_engine(settings.database_url)
    maker = create_session_maker(engine)
    try:
        async with maker() as sesi:
            d = await sesi.get(Decision, decision_id)
            assert d is not None, f"keputusan {decision_id} hilang dari DB"
            return await build_approval_summary(sesi, d)
    finally:
        await engine.dispose()


async def _kedaluwarsakan(
    batch_ids: list[uuid.UUID], acuan: datetime | None = None
) -> dict:
    """Paksa batch sumber lewat masa layaknya; kembalikan nilai aslinya.

    27 Okt 2026: keputusan demo dievaluasi pada JANGKAR sesinya (replay = 8 Okt),
    jadi "kedaluwarsa" harus dihitung terhadap jangkar itu — bukan jam dinding.
    Memakai jam dinding membuat batch yang sudah lewat masa layak pada jangkar
    justru terlihat masih berlaku, dan tes ini gagal karena gate-nya benar.
    """
    asli: dict = {}
    engine = create_engine(settings.database_url)
    maker = create_session_maker(engine)
    try:
        async with maker() as sesi:
            for bid in batch_ids:
                b = await sesi.get(Batch, bid)
                assert b is not None, f"batch {bid} tidak ada"
                asli[bid] = b.usable_until
                # Acuan = jangkar sesi keputusan (diberikan pemanggil) atau
                # jangkar sesi batch; jam dinding hanya bila keduanya tidak ada.
                saat = acuan
                if saat is None and b.demo_session_id is not None:
                    dari_sesi = await sesi.get(DemoSession, b.demo_session_id)
                    saat = getattr(dari_sesi, "evaluation_anchor", None)
                if saat is None:
                    saat = datetime.now(UTC)
                b.usable_until = saat - timedelta(hours=1)
            await sesi.commit()
        return asli
    finally:
        await engine.dispose()


async def _jangkar_keputusan(keputusan) -> datetime | None:
    """Jangkar evaluasi sesi milik satu keputusan (None bila tanpa sesi)."""
    if getattr(keputusan, "demo_session_id", None) is None:
        return None
    engine = create_engine(settings.database_url)
    maker = create_session_maker(engine)
    try:
        async with maker() as sesi:
            baris = await sesi.get(DemoSession, keputusan.demo_session_id)
            return getattr(baris, "evaluation_anchor", None)
    finally:
        await engine.dispose()


async def _pulihkan(batch_ids: list[uuid.UUID], asli: dict) -> None:
    engine = create_engine(settings.database_url)
    maker = create_session_maker(engine)
    try:
        async with maker() as sesi:
            for bid, nilai in asli.items():
                b = await sesi.get(Batch, bid)
                if b is not None:
                    b.usable_until = nilai
            await sesi.commit()
    finally:
        await engine.dispose()


async def _semai_ulang() -> None:
    engine = create_engine(settings.database_url)
    maker = create_session_maker(engine)
    try:
        async with maker() as sesi:
            await seed_demo_completed_decisions(sesi, datetime.now(UTC))
            await sesi.commit()
    finally:
        await engine.dispose()


async def _hitung_anak(decision_id: uuid.UUID) -> dict:
    """Jumlah baris yang menemani satu keputusan demo (untuk uji idempotensi)."""
    engine = create_engine(settings.database_url)
    maker = create_session_maker(engine)
    try:
        async with maker() as sesi:
            bukti = (
                await sesi.execute(
                    select(DecisionEvidence).where(
                        DecisionEvidence.decision_id == decision_id
                    )
                )
            ).scalars()
            approval = (
                await sesi.execute(
                    select(Approval).where(Approval.decision_id == decision_id)
                )
            ).scalars()
            d = await sesi.get(Decision, decision_id)
            assert d is not None, f"keputusan {decision_id} hilang dari DB"
            batch = (
                await sesi.execute(
                    select(Batch).where(
                        Batch.location_id == d.source_location_id,
                        Batch.commodity_id == d.commodity_id,
                    )
                )
            ).scalars()
            return {
                "bukti": len(list(bukti)),
                "approval": len(list(approval)),
                "batch": len(list(batch)),
            }
    finally:
        await engine.dispose()


async def test_menyemai_ulang_menyembuhkan_sumber_yang_sudah_kedaluwarsa() -> None:
    """Akar gate (27 Okt 2026): batch sumber ADA, `pass`, tetapi sudah kedaluwarsa.

    Penyemai lama hanya menyaring `safety_status == "pass"`, tanpa melihat
    `usable_until`. Akibatnya keputusan `executed` bisa menunjuk batch yang masa
    layaknya sudah lewat (batch kanonik 8 Okt yang tergeser ke "hari ini", atau
    batch demo yang tinggal beberapa menit lagi layak) — `penghalang_sumber`
    lalu memblokirnya dan ringkasan memuat "safety revalidation gagal" pada
    riwayat yang katanya sudah selesai.

    Menyemai ulang wajib MEMINDAHKAN binding ke batch yang masih layak; gate
    tidak boleh dilonggarkan (lihat tes "tetap_diblokir" di bawah).
    """
    _, keputusan, _ = await _jalankan()
    assert keputusan, "penyemai tidak membuat keputusan selesai"
    target = keputusan[0]
    terikat = await _batch_terikat(target.id)
    assert terikat, f"keputusan {target.id} tidak punya allocation_binding"

    asli = await _kedaluwarsakan(terikat, acuan=await _jangkar_keputusan(target))
    try:
        sebelum = await _ringkasan(target.id)
        assert sebelum["blocking_reasons"] != [], (
            "prasyarat tes tidak terpenuhi: batch kedaluwarsa seharusnya terbaca "
            "memblokir"
        )

        await _semai_ulang()

        sesudah = await _ringkasan(target.id)
        assert not [
            r for r in sesudah["blocking_reasons"] if "safety revalidation gagal" in r
        ], (
            "penyemai ulang membiarkan keputusan selesai bersandar pada batch "
            f"kedaluwarsa: {sesudah['blocking_reasons']}"
        )
        assert sesudah["blocking_reasons"] == ["decision sudah dieksekusi"], (
            f"penghalang sisa setelah penyemaian ulang: {sesudah['blocking_reasons']}"
        )
        # Penyembuhan boleh lewat dua jalan: binding dipindah ke batch lain, atau
        # batch sumber milik penyemai ini disegarkan. Yang WAJIB benar adalah
        # hasilnya: batch yang terikat sekarang benar-benar lolos gerbang
        # keselamatan (bukan cuma "tidak dilaporkan").
        baru = await _batch_terikat(target.id)
        assert baru, f"keputusan {target.id} kehilangan allocation_binding"
        engine = create_engine(settings.database_url)
        maker = create_session_maker(engine)
        try:
            async with maker() as sesi:
                for bid in baru:
                    b = await sesi.get(Batch, bid)
                    assert b is not None, f"binding menunjuk batch hilang {bid}"
                    assert b.safety_status == "pass", (
                        f"batch sumber {bid} berstatus {b.safety_status} setelah semai ulang"
                    )
                    assert b.usable_until is not None and b.usable_until > datetime.now(
                        UTC
                    ), f"batch sumber {bid} masih kedaluwarsa setelah semai ulang"
        finally:
            await engine.dispose()
    finally:
        await _pulihkan(terikat, asli)


async def test_penyemai_ulang_idempoten_tidak_menggandakan_baris_anak() -> None:
    """Menyegarkan demo dua kali tidak boleh menambah baris apa pun."""
    _, keputusan, _ = await _jalankan()
    assert keputusan, "penyemai tidak membuat keputusan selesai"
    target = keputusan[0]

    pertama = await _hitung_anak(target.id)
    terikat_pertama = await _batch_terikat(target.id)
    await _semai_ulang()
    kedua = await _hitung_anak(target.id)
    terikat_kedua = await _batch_terikat(target.id)

    assert kedua == pertama, (
        f"penyemaian ulang menggandakan baris anak: {pertama} → {kedua}"
    )
    assert terikat_kedua == terikat_pertama, (
        f"binding berpindah tanpa sebab: {terikat_pertama} → {terikat_kedua}"
    )


async def test_sumber_hilang_tanpa_semai_ulang_tetap_diblokir() -> None:
    """Perbaikan penyemai TIDAK boleh melonggarkan gate.

    Batch sumber kedaluwarsa/terhapus harus tetap terbaca memblokir selama
    penyemai belum dijalankan: bukti yang tidak ada bukan berarti aman.
    """
    _, keputusan, _ = await _jalankan()
    assert keputusan, "penyemai tidak membuat keputusan selesai"
    target = keputusan[0]
    terikat = await _batch_terikat(target.id)
    assert terikat, f"keputusan {target.id} tidak punya allocation_binding"

    # Kedaluwarsa HARUS dihitung terhadap jangkar keputusan. Tanpa `acuan`,
    # helper memakai jam dinding: batch jadi "kedaluwarsa kemarin" menurut jam
    # nyata tetapi masih berlaku pada jangkar 8 Okt, sehingga ringkasan menjawab
    # blocked=false dan tes gagal padahal gate produknya benar (terukur 28 Okt
    # 2026; probe dengan acuan=jangkar memberi block_code=batch_expired).
    asli = await _kedaluwarsakan(terikat, acuan=await _jangkar_keputusan(target))
    try:
        r = await _ringkasan(target.id)
        assert r["safety"]["blocked"] is True, (
            "gate dilonggarkan: batch sumber kedaluwarsa tidak lagi memblokir"
        )
        assert [
            alasan
            for alasan in r["blocking_reasons"]
            if "safety revalidation gagal" in alasan
        ], f"alasan safety hilang dari ringkasan: {r['blocking_reasons']}"
    finally:
        await _pulihkan(terikat, asli)


async def test_ringkasan_hanya_menyisakan_alasan_yang_nyata() -> None:
    _, keputusan, ringkasan = await _jalankan()

    assert keputusan, "penyemai tidak membuat keputusan selesai"
    for d in keputusan:
        r = ringkasan[d.id]
        assert r["supplier"] is not None, (
            f"keputusan {d.id}: pemasok tidak terbaca — {r['blocking_reasons']}"
        )
        # `verifier_note` dibaca read model sebagai verdict; kalimat naratif di
        # kolom itu membuat layar menulis "tidak dapat dievaluasi".
        assert r["verifier"]["verdict"] == "consistent", (
            f"keputusan {d.id}: verdict terbaca {r['verifier']['verdict']!r}, "
            "padahal buktinya sendiri tercatat konsisten"
        )
        assert r["blocking_reasons"] == ["decision sudah dieksekusi"], (
            f"keputusan {d.id} yang sudah dieksekusi masih memikul penghalang lain: "
            f"{r['blocking_reasons']}"
        )
