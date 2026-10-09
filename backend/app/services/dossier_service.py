"""P2 dossier konten-addressed + P3 ECDSA signing (paket 1-6, keputusan
Roy 2026-10-09).

Dossier  : bundle JSON seluruh bukti keputusan (decision + evidence +
           approvals + traces), di-address dengan hash ala-CID lokal
           (b36 hash sha256 — pengganti IPFS offline, tanpa jaringan).
Signing  : tanda tangan ECDSA secp256k1 atas payload dossier; kunci
           privat di .env (SIGNING_KEY_HEX) — TANPA kunci → state
           `unsigned` jujur (bukan tanda tangan palsu).
"""

import hashlib

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ledger_service import _canonical


def content_address(payload: dict) -> str:
    """Alamat konten ala-CID: base36(sha256(canonical)) + prefix 'mc1-'."""
    digest = hashlib.sha256(_canonical(payload).encode()).digest()
    n = int.from_bytes(digest, "big")
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = ""
    while n:
        n, r = divmod(n, 36)
        out = alphabet[r] + out
    return f"mc1-{out}"


async def build_dossier(db: AsyncSession, decision_id) -> dict:
    """Kumpulkan decision + evidence + approvals + traces jadi satu dict."""
    dec = (
        await db.execute(
            text(
                "SELECT id, decision_type, status, quantity_kg, safe_delivered_cost, "
                "cost_breakdown, created_at, expires_at, iteration, supersedes_id, "
                "rejection_reason, proposed_by, source_location_id, target_location_id, "
                "commodity_id FROM decisions WHERE id = :d"
            ),
            {"d": decision_id},
        )
    ).mappings().first()
    if dec is None:
        return {}
    evidence = (
        await db.execute(
            text(
                "SELECT id, evidence_type, payload, is_consistent, recorded_at "
                "FROM decision_evidence WHERE decision_id = :d ORDER BY recorded_at"
            ),
            {"d": decision_id},
        )
    ).mappings().all()
    approvals = (
        await db.execute(
            text(
                "SELECT a.id, a.approved, a.comment, a.approved_at, u.role "
                "FROM approvals a JOIN users u ON u.id = a.approved_by "
                "WHERE a.decision_id = :d ORDER BY a.approved_at"
            ),
            {"d": decision_id},
        )
    ).mappings().all()
    traces = (
        await db.execute(
            text(
                "SELECT id, step_name, tool_called, input_summary, output_summary, "
                "step_at FROM agent_traces WHERE decision_id = :d ORDER BY step_at"
            ),
            {"d": decision_id},
        )
    ).mappings().all()
    return {
        "decision": dict(dec),
        "evidence": [dict(e) for e in evidence],
        "approvals": [dict(a) for a in approvals],
        "traces": [dict(t) for t in traces],
    }
