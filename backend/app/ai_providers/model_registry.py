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
# Slot fallback bernomor (permintaan Roy: chain sepanjang model yang ada)
MAX_FALLBACK_SLOTS = 9
AGENT_FALLBACK_TEMPLATE = {
    "supervisor": "SUPERVISOR_MODEL_FALLBACK_{}",
    "verifier": "VERIFIER_MODEL_FALLBACK_{}",
    "forecast": "FORECAST_MODEL_FALLBACK_{}",
}

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
    """Rantai model agent dari env: satu slot per env terisi, tanpa cap 3.

    - slot fallback bernomor `*_MODEL_FALLBACK_1..9` dikumpulkan berurutan;
      gap pertama menghentikan koleksi (slot setelah gap diabaikan)
    - SUPERVISOR_MODEL_FALLBACK (legacy, tanpa angka) dipakai sebagai
      fallback_1 bila tidak ada slot bernomor
    - AGENTCORE_RUNTIME_ARN terisi → jadi primary, slot env bergeser satu
      posisi (kontrak: AgentCore dulu, fallback env tetap dipertahankan)
    """
    keys = _agent_env_keys(agent)
    template = AGENT_FALLBACK_TEMPLATE[agent]

    primary = parse_model_ref(os.environ.get(keys["primary"]))
    numbered: list[ModelRef] = []
    for index in range(1, MAX_FALLBACK_SLOTS + 1):
        ref = parse_model_ref(os.environ.get(template.format(index)))
        if ref is None:
            break
        numbered.append(ref)
    if not numbered and agent == "supervisor":
        # kompatibilitas nama legacy SUPERVISOR_MODEL_FALLBACK
        legacy = parse_model_ref(os.environ.get("SUPERVISOR_MODEL_FALLBACK"))
        if legacy is not None and legacy.kind != "agentcore":
            numbered.append(legacy)

    env_slots = [primary, *numbered]
    env_slots = [ref for ref in env_slots if ref is not None]

    arn = parse_model_ref(os.environ.get(AGENTCORE_ARN_ENV))
    if arn is not None:
        return [arn, *env_slots]
    return env_slots
