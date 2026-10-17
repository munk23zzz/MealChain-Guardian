"""Approval matrix (S3-01) — kontrak verifikasi Roy, murni deterministik.

- CONSISTENT  → 1 approval: sppg_head ATAU sppg_nutritionist.
- FLAGGED     → 2 approval: sppg_head DAN sppg_nutritionist.
- UNAVAILABLE → 2 approval: sppg_head DAN sppg_nutritionist.
- bgn_monitor read-only: tidak pernah dihitung sebagai approver.

required_roles berupa daftar grup; tiap grup harus terpenuhi oleh >=1
approval (approved=True) dari role dalam grup itu. Untuk CONSISTENT satu
grup berisi dua role (cukup salah satu). Untuk FLAGGED/UNAVAILABLE dua
grup terpisah (keduanya wajib).
"""

VALID_VERIFIER_VERDICTS = frozenset({"consistent", "flagged", "unavailable"})
APPROVER_ROLES = frozenset({"sppg_head", "sppg_nutritionist"})

_DUAL = [["sppg_head"], ["sppg_nutritionist"]]


def approval_requirement(verdict: str, *, dua_role_wajib: bool = False) -> dict:
    """Requirement approval untuk verdict verifier (lowercase).

    `dua_role_wajib=True` dipakai keputusan OPERASIONAL (transfer): dua
    approval dari dua role berbeda wajib, apa pun verdict verifier-nya.
    Keputusan administrasi (supplier exclusion) tetap mengikuti verdict.
    """
    v = (verdict or "").strip().lower()
    if v not in VALID_VERIFIER_VERDICTS:
        raise ValueError(f"verdict verifier tidak dikenal: {verdict!r}")
    if v == "consistent" and not dua_role_wajib:
        return {
            "verdict": "consistent",
            "min_approvals": 1,
            "required_roles": [["sppg_head", "sppg_nutritionist"]],
        }
    return {
        "verdict": v,
        "min_approvals": 2,
        "required_roles": [list(g) for g in _DUAL],
    }


def evaluate_approvals(requirement: dict, approval_rows: list[dict]) -> dict:
    """Hitung pemenuhan requirement terhadap baris approvals.

    approval_rows: [{"role": <str>, "approved": <bool>}, ...]
    Role di luar APPROVER_ROLES (mis. bgn_monitor) diabaikan.
    Rejection (approved=False) dari approver mana pun menggugurkan.
    """
    relevant = [
        r
        for r in approval_rows
        if r.get("role") in APPROVER_ROLES
    ]
    rejected = any(r.get("approved") is False for r in relevant)
    approved_roles = {
        r.get("role") for r in relevant if r.get("approved") is True
    }
    missing = [
        group for group in requirement["required_roles"]
        if not (set(group) & approved_roles)
    ]
    return {
        "satisfied": (not rejected) and not missing,
        "rejected": rejected,
        "missing": missing,
        "approved_roles": sorted(approved_roles),
    }
