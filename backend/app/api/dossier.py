"""Endpoint P2/P3 (paket 1-6): dossier konten-addressed + ECDSA signing.

GET /decisions/{id}/dossier → bundle bukti + content address + signature.
Read-only, semua role terautentikasi.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.dependencies import get_db
from app.models.users import User
from app.services.dossier_service import build_dossier, content_address
from app.services.ledger_service import _canonical
from app.services.signing_service import sign_payload, verify_signature

router = APIRouter(prefix="", tags=["dossier"])


@router.get("/decisions/{decision_id}/dossier")
async def decision_dossier(
    decision_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Dossier bukti keputusan: address konten + tanda tangan ECDSA.

    - address  : hash konten (ala-CID, offline) — isi berubah → address berubah
    - signature: ECDSA-secp256k1 atas dossier; unsigned jujur bila kunci
                 SIGNING_KEY_HEX belum diset di .env
    - verify   : verifikasi mandiri signature (True/False)
    """
    dossier = await build_dossier(db, decision_id)
    if not dossier:
        raise HTTPException(status_code=404, detail="decision tidak ditemukan")
    payload = _canonical(dossier).encode()
    address = content_address(dossier)
    sig = sign_payload(payload)
    result = {
        "decision_id": str(decision_id),
        "content_address": address,
        "signature": sig,
        "verify": None,
    }
    if sig.get("state") == "signed":
        result["verify"] = verify_signature(
            payload, sig["signature"], sig["public_key"]
        )
    return result
