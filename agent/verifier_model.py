"""Model callable untuk Verifier Agent — OPSIONAL dan eksplisit.

Independensi yang wajib dipenuhi verifier (AUD-9A-03) ada pada dua hal:
**system prompt sendiri** (`agent/prompts/verifier_system_prompt.md`) dan
**sumber fakta sendiri** (`GET /decisions/{id}/audit-facts`). Runtime/model boleh
sama dengan supervisor — itu keputusan owner — tetapi prompt supervisor TIDAK
boleh dipakai di sini, dan verifier tidak menerima narasi sebagai data.

Resolusi model memakai pintu yang SAMA dengan sembilan agent lain
(`agent/workers/reasoner.py`): rantai provider backend → boto3
`bedrock-runtime.converse` → `strands` → `None` (27 Okt 2026). Sebelumnya hanya
`strands` yang bisa dipakai, dan SDK itu tidak terpasang di image backend —
akibatnya verifier selalu `unavailable` walau backend punya kredensial. System
prompt yang ditempel tetap prompt VERIFIER, tidak pernah prompt supervisor.

Tanpa model (kredensial/runtime tidak ada), verifier tetap berjalan:
cek deterministik tetap dijalankan, `flagged` tetap bisa terbit, dan `consistent`
tidak pernah dikarang — hasilnya `unavailable` (fail-closed).

Konfigurasi:

- `VERIFIER_AGENT_MODEL` — model id khusus verifier (utama).
- `SUPERVISOR_MODEL_PRIMARY` — cadangan supaya runtime yang sudah punya
  kredensial tidak perlu konfigurasi baru.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache

ModelCallable = Callable[[str], str]

ENV_MODEL_ID = "VERIFIER_AGENT_MODEL"
ENV_MODEL_CADANGAN = "SUPERVISOR_MODEL_PRIMARY"
ENV_REGION = "AWS_REGION"
AGENT_VERIFIER = "verifier"


@lru_cache(maxsize=1)
def model_dari_env() -> ModelCallable | None:
    """Bangun callable model dari environment; `None` bila tidak memungkinkan."""
    from .workers.reasoner import reasoner_dari_env

    return reasoner_dari_env(agent=AGENT_VERIFIER)
