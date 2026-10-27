"""Model callable untuk Verifier Agent — OPSIONAL dan eksplisit.

Independensi yang wajib dipenuhi verifier (AUD-9A-03) ada pada dua hal:
**system prompt sendiri** (`agent/prompts/verifier_system_prompt.md`) dan
**sumber fakta sendiri** (`GET /decisions/{id}/audit-facts`). Runtime/model boleh
sama dengan supervisor — itu keputusan owner — tetapi prompt supervisor TIDAK
boleh dipakai di sini, dan verifier tidak menerima narasi sebagai data.

Tanpa model (kredensial/runtime tidak ada), verifier tetap berjalan:
cek deterministik tetap dijalankan, `flagged` tetap bisa terbit, dan `consistent`
tidak pernah dikarang — hasilnya `unavailable` (fail-closed).

Konfigurasi:

- `VERIFIER_AGENT_MODEL` — model id khusus verifier (utama).
- `SUPERVISOR_MODEL_PRIMARY` — cadangan supaya runtime yang sudah punya
  kredensial tidak perlu konfigurasi baru.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from functools import lru_cache

ENV_MODEL_ID = "VERIFIER_AGENT_MODEL"
ENV_MODEL_CADANGAN = "SUPERVISOR_MODEL_PRIMARY"
ENV_REGION = "AWS_REGION"

ModelCallable = Callable[[str], str]


@lru_cache(maxsize=1)
def model_dari_env() -> ModelCallable | None:
    """Bangun callable model dari environment; `None` bila tidak memungkinkan."""
    model_id = (os.environ.get(ENV_MODEL_ID) or os.environ.get(ENV_MODEL_CADANGAN) or "").strip()
    if not model_id:
        return None
    try:  # pragma: no cover - bergantung runtime AgentCore/Bedrock
        import strands
    except Exception:  # noqa: BLE001 - tanpa SDK, audit tetap deterministik
        return None

    model_kwargs: dict[str, object] = {"model_id": model_id}
    region = (os.environ.get(ENV_REGION) or "").strip()
    if region:
        model_kwargs["region_name"] = region
    try:  # pragma: no cover
        agent = strands.Agent(
            model=strands.models.BedrockModel(**model_kwargs),
            tools=[],
            system_prompt=_system_prompt_verifier(),
        )
    except Exception:  # noqa: BLE001 - kredensial tidak ada ≠ audit gagal
        return None

    def _panggil(prompt: str) -> str:  # pragma: no cover
        return str(agent(prompt))

    return _panggil


def _system_prompt_verifier() -> str:
    from .workers.verifier import load_system_prompt

    return load_system_prompt()
