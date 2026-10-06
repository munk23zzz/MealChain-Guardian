"""SUPERVISE step diwhitelist di agent_traces (permintaan Roy).

Langkah narasi supervisor (`SUPERVISE`) sah sebagai langkah trace terakhir —
narasi TIDAK safety-critical (tidak mengubah verdict/rekomendasi/angka).
Check constraint DB diupdate agar drift model↔migration tidak terjadi.

Revision ID: 007_supervise_step
Revises: 006_decision_persistence
Create Date: 2026-10-06
"""

from typing import Sequence, Union

from alembic import op

revision: str = "007_supervise_step"
down_revision: Union[str, None] = "006_decision_persistence"
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
        "'DECIDE','SUPERVISE','ACT','LEARN')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "agent_traces_step_name_check", "agent_traces", type_="check"
    )
    op.create_check_constraint(
        "agent_traces_step_name_check",
        "agent_traces",
        "step_name IN ('DETECT','VERIFY','TRACE','PREDICT','OPTIMIZE',"
        "'DECIDE','ACT','LEARN')",
    )
