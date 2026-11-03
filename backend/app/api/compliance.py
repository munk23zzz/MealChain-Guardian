"""Read-only compliance dossier payload for the evidence/export surface.

The existing dossier route intentionally returns integrity metadata only. This
route exposes the already-authorized persisted bundle without adding thresholds
or frontend safety calculations. Parent router wiring is required.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.decisions import _assert_decision_readable
from app.api.dependencies import get_db
from app.models.decisions import Decision
from app.models.users import User
from app.services.dossier_service import build_dossier, content_address
from app.services.ledger_service import _canonical
from app.services.signing_service import sign_payload, verify_signature

router = APIRouter(prefix="", tags=["compliance"])


@router.get("/decisions/{decision_id}/compliance")
async def decision_compliance(
    decision_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Return persisted decision/evidence/approval/trace data plus integrity metadata."""
    decision = await db.get(Decision, decision_id)
    if decision is None:
        raise HTTPException(status_code=404, detail="decision tidak ditemukan")
    await _assert_decision_readable(db, user, decision)
    dossier = await build_dossier(db, decision_id)
    payload = _canonical(dossier).encode()
    signature = sign_payload(payload)
    result = {
        **dossier,
        "decision_id": str(decision_id),
        "content_address": content_address(dossier),
        "signature": signature,
        "verify": None,
    }
    if signature.get("state") == "signed":
        result["verify"] = verify_signature(
            payload, signature["signature"], signature["public_key"]
        )
    return result
