"""Chain default per agent dari env registry (permintaan Roy).

Menyambungkan model_registry → callers nyata:
- ModelRef bedrock  → app.ai_providers.bedrock_caller.build_model_caller
- ModelRef inferhub → app.ai_providers.inferhub_caller.build_caller
- ModelRef agentcore → stub eksplisit yang melempar NotImplementedError
  (honest-unavailable sampai AgentCore Runtime benar-benar disiapkan)

`build_default_callers(agent)` adalah SATU-SATUNYA pintu env → callable;
verifier/forecast/supervisor client memakainya sebagai default bila
pemanggil tidak menyuntik provider eksplisit.
"""

from __future__ import annotations

from typing import Callable

from app.ai_providers.model_registry import (
    ModelRef,
    get_agent_chain,
)


def _build_ref_caller(ref: ModelRef) -> Callable[[str], str]:
    if ref.kind == "bedrock":
        from app.ai_providers.bedrock_caller import build_model_caller

        return build_model_caller(ref)
    if ref.kind == "inferhub":
        from app.ai_providers.inferhub_caller import build_caller

        try:
            return build_caller(ref.model_id)
        except RuntimeError as exc:
            # env Inferhub belum lengkap: slot jadi "mati" — gagal saat
            # dipanggil, chain lanjut ke slot berikutnya (jujur di attempts)
            message = str(exc)

            def _dead_slot(prompt: str) -> str:
                raise RuntimeError(message)

            return _dead_slot
    if ref.kind == "agentcore":
        # O-AI (S4-00): caller invoke runtime NYATA — bukan stub lagi.
        from app.ai_providers.agentcore_caller import build_runtime_caller

        return build_runtime_caller(ref.agentcore_arn)
    raise ValueError(f"kind model tidak dikenal: {ref.kind}")


def build_default_callers(agent: str) -> list[tuple[str, Callable[[str], str], str]]:
    """Rantai callable default agent dari env: [(label, fn, kind), ...]."""
    chain = get_agent_chain(agent)
    return [
        (f"{slot}:{ref.kind}", _build_ref_caller(ref), ref.kind)
        for slot, ref in zip(
            ("primary", *(f"fallback_{i}" for i in range(1, len(chain)))),
            chain,
        )
    ]
