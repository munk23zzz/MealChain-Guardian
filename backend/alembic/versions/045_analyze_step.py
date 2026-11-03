"""Langkah ANALYZE diwhitelist di `agent_traces` (29 Okt 2026).

Langkah `ANALYZE` adalah hipotesis sebab + rekomendasi dari LLM, dijalankan SESUDAH
angka deterministik (DETECT/OPTIMIZE/PREDICT) selesai dan SEBELUM DECIDE. Sifatnya
advisory: tidak mengubah verdict verifier, status keputusan, maupun angka.

Check constraint DB diupdate bersamaan dengan model (`AgentTrace.__table_args__`) supaya
tidak ada drift model ↔ migration — tanpa ini, insert baris ANALYZE ditolak database
walaupun whitelist Python sudah menerimanya.

Revision ID: 045_analyze_step
Revises: 044_receipt_scoring
Create Date: 2026-10-29
"""

from typing import Sequence, Union

from alembic import op

revision: str = "045_analyze_step"
down_revision: Union[str, None] = "044_receipt_scoring"
branch_labels: Union[str, Sequence[str]] = None
depends_on: Union[str, Sequence[str]] = None


def upgrade() -> None:
    op.drop_constraint(
        "agent_traces_step_name_check", "agent_traces", type_="check"
    )
    op.create_check_constraint(
        "agent_traces_step_name_check",
        "agent_traces",
        "step_name IN ('DETECT','VERIFY','TRACE','PREDICT','OPTIMIZE',"
        "'ANALYZE','DECIDE','SUPERVISE','ACT','LEARN')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "agent_traces_step_name_check", "agent_traces", type_="check"
    )
    op.create_check_constraint(
        "agent_traces_step_name_check",
        "agent_traces",
        "step_name IN ('DETECT','VERIFY','TRACE','PREDICT','OPTIMIZE',"
        "'DECIDE','SUPERVISE','ACT','LEARN')",
    )
