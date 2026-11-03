"""Kontrak context Supervisor (Task 12 Sprint 2) — assembler murni.

Tidak menghitung/menafsirkan ulang apa pun: hanya menyusun field yang
diizinkan dari output service rekomendasi menjadi struktur JSON
deterministik untuk Supervisor (satu-satunya agent LLM). Kunci di luar
allowlist dibuang (anti-kebocoran secret). Field wajib yang hilang
ditolak (ValueError), bukan diasumsikan.
"""

import json
from typing import Any

__all__ = ["build_supervisor_context"]

_TOP_REQUIRED = ("generated_at", "facts", "recommendations")
_REC_REQUIRED = (
    "candidate_id",
    "score",
    "safe_delivered_cost",
    "price_anomaly",
    "evidence",
    "candidate",
)
_CAND_STATUS_REQUIRED = ("freshness_status", "safety_status")
_EMBEDDED_CANDIDATE_KEYS = (
    "source_location",
    "destination_location",
    "commodity",
    "quantity_kg",
)


def _require(container: dict, key: str) -> Any:
    if key not in container:
        raise ValueError(f"context wajib punya '{key}'")
    return container[key]


def _clean_candidate(rec: dict) -> dict:
    missing = [k for k in _REC_REQUIRED if k not in rec]
    if missing:
        raise ValueError(
            "kandidat wajib punya field: " + ", ".join(missing)
        )
    cand = rec["candidate"]
    if not isinstance(cand, dict):
        raise ValueError("candidate wajib dict")
    missing_status = [k for k in _CAND_STATUS_REQUIRED if k not in cand]
    if missing_status:
        raise ValueError(
            "candidate wajib punya status: " + ", ".join(missing_status)
        )
    price = cand.get("price") or {}
    return {
        "candidate_id": rec["candidate_id"],
        "rank": rec.get("rank"),
        "score": rec["score"],
        "safe_delivered_cost": rec["safe_delivered_cost"],
        "cost_breakdown": rec.get("cost_breakdown"),
        "freshness_status": cand["freshness_status"],
        "safety_status": cand["safety_status"],
        "price_anomaly": rec["price_anomaly"],
        "logistics": {
            "feasible": cand.get("logistics_feasible"),
            "distance_km": cand.get("logistics_distance_km"),
            "time_min": cand.get("logistics_time_min"),
        },
        "supplier_id": price.get("supplier_id"),
        "evidence": rec["evidence"],
        "candidate": {
            k: cand[k] for k in _EMBEDDED_CANDIDATE_KEYS if k in cand
        },
    }


def build_supervisor_context(service_output: dict) -> dict:
    if not isinstance(service_output, dict):
        raise ValueError("service_output wajib dict")
    generated_at = _require(service_output, "generated_at")
    facts = _require(service_output, "facts")
    recommendations = _require(service_output, "recommendations")

    return {
        "generated_at": generated_at,
        "facts": {
            "supply": dict(facts.get("supply", {})),
            "demand": dict(facts.get("demand", {})),
        },
        "candidates": [_clean_candidate(r) for r in recommendations],
    }


def canonical_context_json(service_output: dict) -> str:
    """Serialisasi kanonik deterministik (sort_keys, pemisah rapat)."""
    return json.dumps(
        build_supervisor_context(service_output),
        sort_keys=True,
        separators=(",", ":"),
    )
