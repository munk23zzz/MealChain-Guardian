"""Penerimaan manusia atas bukti batch (Fase 6 butir 3 & 5).

Rencana (`MG/overview.md` §"Gerbang kelayakan dan penerimaan") menuntut:

> Human review dapat memperbaiki status hanya dengan bukti, identitas reviewer,
> waktu, alasan, dan referensi `DecisionEvidence`. Tombol terima yang hanya
> mengandalkan nilai ambigu tidak boleh mengubah batch menjadi aman.

Modul ini satu-satunya jalur untuk itu, dan aturannya:

1. **Review = aksi, bukan evaluasi.** Reviewer tidak menulis status. Ia
   menambahkan bukti (sampel suhu) + alasan + rujukan; lalu evaluator
   deterministik (`core.safety.evaluate_safety` dengan profil komoditas)
   MENGHITUNG ULANG status. Jadi `pass` tidak pernah berasal dari teks reviewer.
2. **Fail-closed.** Bila bukti sesudah review masih tidak cukup, status TIDAK
   berubah dan respons menyebut `evidence_state` + langkah berikutnya.
3. **`fail` tidak dapat direview menjadi aman.** Kegagalan uji adalah hasil
   mesin; membalikkannya dengan alasan manusia sama dengan menutupi kegagalan.
4. **Setiap review meninggalkan `DecisionEvidence`** bertipe `human_inspection`
   berisi reviewer, waktu, alasan, rujukan, sampel yang ditambahkan, dan status
   sebelum/sesudah. Verdict LLM tidak menulis payload seperti ini, sehingga ia
   tidak dapat menggantikan bukti manusia.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.policy_store import profil_untuk_komoditas
from app.core.safety import evaluate_safety
from app.models import Batch, Commodity, Decision, DecisionEvidence, User
from app.services.batch_eligibility_service import NEXT_STEP

__all__ = ["REVIEWABLE_STATUS", "merge_temperature_samples", "review_batch"]

#: Status yang masih boleh ditinjau. `pass` tidak perlu ditinjau (sudah aman),
#: `fail` TIDAK boleh dibalik oleh review manusia.
REVIEWABLE_STATUS = ("needs_verification", "pending")

#: Toleransi jam untuk sampel "masa depan" (klok perangkat vs server).
TOLERANSI_MASA_DEPAN = timedelta(minutes=5)


def _parse_waktu(nilai: Any) -> datetime:
    if isinstance(nilai, datetime):
        return nilai if nilai.tzinfo else nilai.replace(tzinfo=timezone.utc)
    teks = str(nilai or "").strip()
    try:
        parsed = datetime.fromisoformat(teks.replace("Z", "+00:00"))
    except ValueError as galat:
        raise HTTPException(
            status_code=422, detail=f"timestamp sampel tidak terbaca: {nilai!r}"
        ) from galat
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def merge_temperature_samples(
    log: list[dict] | None, samples: list[dict], *, sekarang: datetime | None = None
) -> list[dict]:
    """Gabungkan sampel review ke log batch (urut waktu, tanpa duplikat).

    Duplikat dinilai dari (timestamp, suhu): dua entri identik membuat parser
    menandai bukti `ambiguous`, dan itu kegagalan yang lahir dari review itu
    sendiri — bukan dari datanya.
    """
    waktu_sekarang = sekarang or datetime.now(timezone.utc)
    hasil: list[dict] = []
    terlihat: set[tuple[str, str]] = set()
    for entri in [*(log or []), *samples]:
        try:
            waktu = _parse_waktu(entri.get("timestamp"))
        except HTTPException:
            # Entri lama yang rusak dibiarkan apa adanya: parser punya jalur
            # `malformed` sendiri, dan menghapusnya di sini menyembunyikan bukti.
            hasil.append(dict(entri))
            continue
        if waktu > waktu_sekarang + TOLERANSI_MASA_DEPAN:
            raise HTTPException(
                status_code=422,
                detail=(
                    "sampel suhu tidak boleh bertimestamp masa depan "
                    f"({waktu.isoformat()} > {waktu_sekarang.isoformat()})"
                ),
            )
        try:
            suhu = float(entri.get("temperature_c"))
        except (TypeError, ValueError) as galat:
            raise HTTPException(
                status_code=422,
                detail=f"suhu sampel bukan angka: {entri.get('temperature_c')!r}",
            ) from galat
        if not math.isfinite(suhu):
            raise HTTPException(status_code=422, detail="suhu sampel tidak hingga")
        kunci = (waktu.isoformat(), f"{suhu}")
        if kunci in terlihat:
            continue
        terlihat.add(kunci)
        hasil.append({"timestamp": waktu.isoformat(), "temperature_c": suhu})
    hasil.sort(key=lambda e: str(e.get("timestamp") or ""))
    return hasil


async def _nama_komoditas(db: AsyncSession, decision: Decision) -> str | None:
    if decision.commodity_id is None:
        return None
    return (
        await db.execute(
            select(Commodity.name).where(Commodity.id == decision.commodity_id)
        )
    ).scalar_one_or_none()


async def review_batch(
    db: AsyncSession,
    decision: Decision,
    payload: Any,
    user: User,
    *,
    sekarang: datetime | None = None,
) -> dict:
    """Tinjau satu batch terikat; status hanya berubah bila bukti mencukupi."""
    from app.services.supplier_eligibility import batch_sumber_transfer

    waktu = sekarang or datetime.now(timezone.utc)
    terikat = await batch_sumber_transfer(db, decision)
    kandidat = [b for b in terikat if str(b.id) == str(payload.batch_id)]
    if not kandidat:
        raise HTTPException(
            status_code=409,
            detail=(
                "batch bukan bagian dari keputusan ini — review hanya untuk batch "
                "yang terikat pada keputusan (binding tidak berubah)"
            ),
        )
    batch: Batch = kandidat[0]
    sebelum = (batch.safety_status or "").strip().lower()
    if sebelum not in REVIEWABLE_STATUS:
        raise HTTPException(
            status_code=409,
            detail=(
                f"batch berstatus {sebelum or 'tidak dikenal'} — hanya "
                "needs_verification/pending yang dapat ditinjau; "
                "`pass` sudah aman dan `fail` tidak dapat dibalik oleh review"
            ),
        )

    nama_komoditas = await _nama_komoditas(db, decision)
    try:
        policy, asal_profil = await profil_untuk_komoditas(db, decision.commodity_id)
    except KeyError as galat:
        raise HTTPException(status_code=422, detail=str(galat)) from galat

    sampel = [
        s if isinstance(s, dict) else s.model_dump() for s in payload.temperature_samples
    ]
    log_baru = merge_temperature_samples(batch.temperature_log or [], sampel, sekarang=waktu)
    hasil = evaluate_safety(log_baru, policy=policy, evaluation_time=waktu)
    evidence_state = str(hasil["evidence_state"])
    status_hitung = str(hasil["safety_status"]).strip().lower()

    berubah = False
    if evidence_state == "sufficient":
        batch.safety_status = status_hitung
        berubah = status_hitung != sebelum
    # Selain `sufficient`: status dibiarkan. Bukti yang belum cukup tidak boleh
    # menghasilkan `pass` hanya karena reviewer menulis alasannya.

    batch.temperature_log = log_baru
    bukti = DecisionEvidence(
        decision_id=decision.id,
        evidence_type="human_inspection",
        payload={
            "review_reason": payload.reason,
            "reviewed_by_user_id": str(user.id),
            "reviewed_by_role": user.role,
            "reviewed_at": waktu.isoformat(),
            "evidence_refs": list(payload.evidence_refs),
            "batch_id": str(batch.id),
            "commodity": nama_komoditas,
            "temperature_samples_added": len(sampel),
            "temperature_samples_total": len(log_baru),
            "safety_status_before": sebelum,
            "safety_status_after": batch.safety_status,
            "status_changed": berubah,
            "evidence_state": evidence_state,
            "temperature_observation": hasil["temperature_observation"],
            "excursion_minutes": float(hasil["excursion_minutes"]),
            "policy_version": policy.policy_version,
            "policy_source": asal_profil,
            "policy_kind": policy.policy_kind,
            "source": "human_review",
        },
        # Konsistensi payload review tidak dinilai fungsi evidence_consistency
        # (yang menilai binding/harga/suhu mesin); NULL berarti "belum dinilai",
        # bukan "konsisten".
        is_consistent=None,
    )
    db.add(bukti)
    # TIDAK menulis `agent_traces`: kosakata `step_name` adalah langkah AGENT
    # (CHECK DB: DETECT/VERIFY/TRACE/PREDICT/OPTIMIZE/DECIDE/SUPERVISE/ACT/
    # LEARN). Review manusia bukan langkah agent, dan menambah nilai baru ke
    # kosakata itu mengubah semua konsumen jejak (KPI, roster worker, UI).
    # Jejak audit review hidup di `DecisionEvidence` di atas dan dibaca sebagai
    # `review.human_reviews` pada paket keputusan.
    await db.commit()

    return {
        "decision_id": str(decision.id),
        "batch_id": str(batch.id),
        "safety_status_before": sebelum,
        "safety_status_after": batch.safety_status,
        "status_changed": berubah,
        "evidence_state": evidence_state,
        "temperature_observation": hasil["temperature_observation"],
        "sample_count": int(hasil["sample_count"]),
        "excursion_minutes": float(hasil["excursion_minutes"]),
        "blocking_reasons": (
            [] if batch.safety_status == "pass" else _alasan(evidence_state)
        ),
        "next_step": (
            None
            if batch.safety_status == "pass"
            else NEXT_STEP.get("temperature_evidence_incomplete")
        ),
        "reviewed_by_user_id": str(user.id),
        "reviewed_at": waktu.isoformat(),
        "evidence_refs": list(payload.evidence_refs),
        "policy_version": policy.policy_version,
        "policy_source": asal_profil,
    }


def _alasan(evidence_state: str) -> list[str]:
    """Kode alasan untuk UI — kosakata yang SAMA dengan gerbang kelayakan."""
    if evidence_state == "sufficient":
        return []
    return ["temperature_evidence_incomplete"]
