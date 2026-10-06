"""Registry konfigurasi model per agent (backend = sumber konfigurasi).

Permintaan Roy (S3-16+): tiap agent punya rantai TEPAT 3 model — primary +
fallback_1 + fallback_2 — sehingga satu model mati masih ada 2 backup.
Backend adalah satu-satunya tempat env dibaca; frontend hanya menampilkan
identitas model/provider dari trace (display-only).

Format ref di env:
- prefix Inferhub: `cc/`, `cb/`, `cbcn/`, `ali/` (katalog valid, lihat
  probe 2026-10-06 — model truncated/unknown ditolak API Inferhub)
- ARN AgentCore: `arn:aws:bedrock:...:agent-runtime/...` → slot AgentCore
- selain itu: model Bedrock (inference profile us./global., dsb.)

Prioritas: AgentCore Runtime ARN (bila terisi) jadi primary agent dan
menggeser slot env — total rantai tetap 3 (kontrak plan Sprint 3).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

INFERHUB_PREFIXES = ("cc/", "cb/", "cbcn/", "ali/")
AGENT_PREFIX_ENV = {
    "supervisor": {
        "primary": "SUPERVISOR_MODEL_PRIMARY",
        "fallback_1": "SUPERVISOR_MODEL_FALLBACK_1",
        "fallback_2": "SUPERVISOR_MODEL_FALLBACK_2",
    },
    "verifier": {
        "primary": "VERIFIER_MODEL_PRIMARY",
        "fallback_1": "VERIFIER_MODEL_FALLBACK_1",
        "fallback_2": "VERIFIER_MODEL_FALLBACK_2",
    },
    "forecast": {
        "primary": "FORECAST_MODEL",
        "fallback_1": "FORECAST_MODEL_FALLBACK_1",
        "fallback_2": "FORECAST_MODEL_FALLBACK_2",
    },
}
AGENTCORE_ARN_ENV = "AGENTCORE_RUNTIME_ARN"

ModelKind = Literal["bedrock", "inferhub", "agentcore"]


@dataclass(frozen=True)
class ModelRef:
    """Satu slot model dalam rantai agent."""

    kind: ModelKind
    model_id: str = ""
    agentcore_arn: str = ""


def parse_model_ref(raw: str | None) -> ModelRef | None:
    """Parse satu nilai env menjadi ModelRef; kosong → None (jujur)."""
    value = (raw or "").strip()
    if not value:
        return None
    if value.startswith("arn:"):
        return ModelRef(kind="agentcore", agentcore_arn=value)
    if any(value.startswith(p) for p in INFERHUB_PREFIXES):
        return ModelRef(kind="inferhub", model_id=value)
    return ModelRef(kind="bedrock", model_id=value)


def _agent_env_keys(agent: str) -> dict[str, str]:
    if agent not in AGENT_PREFIX_ENV:
        raise ValueError(f"agent tidak dikenal: {agent}")
    return AGENT_PREFIX_ENV[agent]


def get_agent_chain(agent: str) -> list[ModelRef]:
    """Rantai model agent dari env: maksimal 3 slot, AgentCore menggeser.

    - slot env kosong → dilewati (rantai bisa < 3; pemanggil yang memutuskan
      UNAVAILABLE bila kosong)
    - SUPERVISOR_MODEL_FALLBACK (legacy, tanpa angka) dipakai sebagai
      fallback_1 bila slot bernomor tidak diisi
    - AGENTCORE_RUNTIME_ARN terisi → jadi primary, slot env bergeser satu
      posisi (kontrak: AgentCore dulu, fallback env tetap dipertahankan)
    """
    keys = _agent_env_keys(agent)
    slots: list[ModelRef] = []

    primary = parse_model_ref(os.environ.get(keys["primary"]))
    f1_raw = os.environ.get(keys["fallback_1"])
    f1 = parse_model_ref(f1_raw) if f1_raw and f1_raw.strip() else None
    if f1 is None and agent == "supervisor":
        # kompatibilitas nama legacy SUPERVISOR_MODEL_FALLBACK
        legacy = parse_model_ref(os.environ.get("SUPERVISOR_MODEL_FALLBACK"))
        if legacy is not None and legacy.kind != "agentcore":
            f1 = legacy
    f2 = parse_model_ref(os.environ.get(keys["fallback_2"]))

    arn = parse_model_ref(os.environ.get(AGENTCORE_ARN_ENV))
    if arn is not None:
        slots.append(arn)
        for ref in (primary, f1, f2):
            if ref is not None and len(slots) < 3:
                slots.append(ref)
    else:
        for ref in (primary, f1, f2):
            if ref is not None:
                slots.append(ref)

    return slots[:3]
