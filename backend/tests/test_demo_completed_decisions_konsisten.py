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
from datetime import UTC, datetime

from sqlalchemy import delete, select

from app.core.config import settings
from app.db import create_engine, create_session_maker
from app.models import Approval, Batch, Decision, DecisionEvidence, User
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
