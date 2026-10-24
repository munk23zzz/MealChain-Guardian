"""Satu kasus "bukti lengkap" yang sengaja tinggal di jendela 24 jam.

Permintaan pemilik demo (23 Okt 2026): keadaan awal KPI 24 jam Jakarta harus
"belum ada aksi hari ini" (3/7), lalu menyala bertahap saat operator bekerja.
Tiga metrik fakta tersemai; empat metrik aksi kosong. Saat rehearsal penuh,
tiga dari empat metrik aksi terisi dari Event 1 -> approve -> execute, tetapi
Kelengkapan Bukti berhenti di 0,00% karena keputusan pengadaan hanya membawa
SATU jenis bukti konsisten sebelum approval (human_inspection), sedangkan
metriknya menuntut >= 2 jenis berbeda. Keputusan Event 3 punya dua jenis
(human_inspection + temperature) tetapi verifier menandainya FLAGGED karena
batch FAIL adalah blocker absolut — jalur itu memang tertutup oleh aturan.

Berkas ini menutup celah itu dengan DATA DEMO saja, tanpa mengubah rumus KPI
dan tanpa mengarang angka: satu kasus skrip ditandai `demo_case`, punya dua
jenis bukti konsisten yang direkam sebelum approval, dan dibiarkan MENUNGGU
PERSETUJUAN (tanpa approval, tanpa purchase order). Konsekuensinya:

  - `Imbalance` dan `Decision Time` mengabaikan baris `demo_case`, jadi
    keadaan awal tetap 3/7;
  - `Safe Delivered Cost` butuh purchase order — kasus ini tidak punya;
  - `Kelengkapan Bukti` hanya menghitung keputusan yang SUDAH disetujui,
    jadi kasus ini baru menyalakan kartunya setelah operator menyetujui.

Saat "Siapkan data demo" / "Segarkan ke hari ini" dijalankan ulang, approval
dan PO milik kasus ini dihapus lebih dulu supaya cerita demo kembali ke awal.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AgentTrace,
    Approval,
    Commodity,
    Decision,
    DecisionEvidence,
    Location,
    SapMockPurchaseOrder,
)
from app.seed.seed_data import stable_uuid

#: Penanda baris; dipakai juga oleh tes supaya dapat dicari kembali.
DEMO_CASE = "bukti-hari-ini"
#: Lokasi yang dilihat juri pada demo ini.
LOKASI_TUJUAN = "Jakarta"
#: SPPG asal pasokan supaya keputusan ini punya arah (bukan pengadaan pemasok).
LOKASI_ASAL = "Bandung"
#: Selisih waktu dari `now`: kasus lahir pagi ini, approval menyusul saat demo.
UMUR_MENIT = 20
#: Dua jenis bukti konsisten; metrik menuntut >= 2 jenis berbeda.
JENIS_BUKTI: tuple[str, ...] = ("human_inspection", "gps")


async def _lokasi(session: AsyncSession, nama: str) -> Location | None:
    return (
        await session.execute(select(Location).where(Location.name == nama))
    ).scalar_one_or_none()


async def semai_kasus_bukti_hari_ini(
    db: AsyncSession,
    now: datetime | None = None,
    *,
    nama_lokasi: str = LOKASI_TUJUAN,
    lokasi_asal: str = LOKASI_ASAL,
) -> dict[str, int]:
    """Semai (atau segarkan) satu kasus siap-setuju dengan dua jenis bukti.

    Idempoten: baris dicari lewat `stable_uuid`, bukan lewat isi. Approval dan
    purchase order milik kasus ini dihapus supaya menjalankan ulang penyemai
    mengembalikan cerita ke "menunggu persetujuan".
    """

    now = now or datetime.now(timezone.utc)
    tujuan = await _lokasi(db, nama_lokasi)
    asal = await _lokasi(db, lokasi_asal)
    if tujuan is None or asal is None:
        raise RuntimeError(
            f"semai_kasus_bukti_hari_ini butuh lokasi {nama_lokasi!r} dan "
            f"{lokasi_asal!r}; jalankan init-demo dari database bermigrasi"
        )

    komoditas = (
        await db.execute(select(Commodity).order_by(Commodity.name))
    ).scalars().first()

    # Lahir pagi ini: di dalam jendela 24 jam, setelah menu/kiriman hari ini.
    lahir = now - timedelta(minutes=UMUR_MENIT)
    keputusan_id = stable_uuid("kasus-bukti", DEMO_CASE, nama_lokasi)

    # Cerita demo harus bisa diulang: bersihkan jejak persetujuan & PO lama.
    await db.execute(delete(Approval).where(Approval.decision_id == keputusan_id))
    await db.execute(
        delete(SapMockPurchaseOrder).where(
            SapMockPurchaseOrder.decision_id == keputusan_id
        )
    )

    nilai: dict[str, Any] = dict(
        decision_type="regional_balance",
        status="pending_approval",
        proposed_by="supervisor_agent",
        verified_by="verifier_agent",
        verifier_note="consistent",
        iteration=1,
        demo_case=DEMO_CASE,
        source_location_id=asal.id,
        target_location_id=tujuan.id,
        commodity_id=komoditas.id if komoditas is not None else None,
        quantity_kg=Decimal("300.00"),
        safe_delivered_cost=Decimal("9750000.00"),
        cost_breakdown={"harga": 28500, "angkut": 1800, "risiko": 950},
        expires_at=now + timedelta(hours=6),
        origin="demo",
        generated_at=lahir,
        created_at=lahir,
    )

    keputusan = await db.get(Decision, keputusan_id)
    if keputusan is None:
        keputusan = Decision(id=keputusan_id, **nilai)
        db.add(keputusan)
    else:
        for kunci, isi in nilai.items():
            setattr(keputusan, kunci, isi)

    # Tiga langkah agent yang membuat kasus ini terlihat "hidup" di log agen.
    langkah = (
        (
            "DETECT",
            "orchestrator",
            {"sinyal": "selisih pasokan Jakarta-Bandung"},
            {"catatan": "Selisih pasokan terdeteksi pada menu hari ini."},
        ),
        (
            "DECIDE",
            "supervisor_agent",
            {"decision_type": "regional_balance"},
            {"alokasi_kg": 300, "asal": lokasi_asal, "tujuan": nama_lokasi},
        ),
        (
            "VERIFY",
            "verifier",
            {"decision_type": "regional_balance"},
            {"verdict": "consistent", "catatan": "Tiga angka saling cocok."},
        ),
    )
    for urutan, (nama, agen, masukan, keluaran) in enumerate(langkah):
        jejak_id = stable_uuid("kasus-bukti-jejak", DEMO_CASE, str(urutan))
        jejak = await db.get(AgentTrace, jejak_id)
        isian = dict(
            decision_id=keputusan_id,
            step_name=nama,
            agent_name=agen,
            tool_called=None,
            input_summary=masukan,
            output_summary=keluaran,
            step_at=lahir + timedelta(minutes=urutan),
        )
        if jejak is None:
            db.add(AgentTrace(id=jejak_id, **isian))
        else:
            for kunci, isi in isian.items():
                setattr(jejak, kunci, isi)

    # Dua jenis bukti berbeda, keduanya konsisten, direkam SEBELUM approval.
    bukti = (
        (
            "human_inspection",
            {
                "demo": True,
                # BUKAN `allocation_binding`: kasus ini pemindahan antar-SPPG
                # tanpa batch/pemasok terikat. Menandainya sebagai binding
                # membuat `resolve_binding` mengira ada ikatan pemasok padahal
                # payload-nya tidak memuat `batch_ids`/`supplier_id`.
                "allocation_note": True,
                "asal": lokasi_asal,
                "tujuan": nama_lokasi,
                "catatan": "Pemeriksaan gudang: alokasi 300 kg sesuai permintaan.",
            },
        ),
        (
            "gps",
            {
                "demo": True,
                "asal": lokasi_asal,
                "tujuan": nama_lokasi,
                "rute": f"{lokasi_asal} -> {nama_lokasi}",
            },
        ),
    )
    for urutan, (jenis, muatan) in enumerate(bukti):
        bukti_id = stable_uuid("kasus-bukti-bukti", DEMO_CASE, jenis)
        baris = await db.get(DecisionEvidence, bukti_id)
        isian = dict(
            decision_id=keputusan_id,
            evidence_type=jenis,
            payload=muatan,
            is_consistent=True,
            recorded_at=lahir + timedelta(minutes=3 + urutan),
        )
        if baris is None:
            db.add(DecisionEvidence(id=bukti_id, **isian))
        else:
            for kunci, isi in isian.items():
                setattr(baris, kunci, isi)

    await db.flush()
    return {"decisions": 1, "agent_traces": len(langkah), "decision_evidence": len(bukti)}
