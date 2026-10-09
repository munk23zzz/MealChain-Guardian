"""S4-00 O-DATA-2: alignment CHECK ORM AgentTrace ↔ migration 007.

Drift terverifikasi (plan §12): migration `007_supervise_step` memuat
SUPERVISE di whitelist `agent_traces_step_name_check` DB, dan
`trace_persistence._VALID_STEPS` juga menerimanya — tetapi CHECK di ORM
`AgentTrace` tidak. Akibatnya fresh DB via `create_all()` menolak langkah
SUPERVISE (mismatch fresh-vs-migrated). Kontrak: whitelist ORM = migration.
"""

from app.db import Base
from app.models.decisions import AgentTrace

MIGRATION_007_STEPS = (
    "DETECT",
    "VERIFY",
    "TRACE",
    "PREDICT",
    "OPTIMIZE",
    "DECIDE",
    "SUPERVISE",
    "ACT",
    "LEARN",
)


def _check_text(model) -> str | None:
    for c in model.__table__.constraints:
        name = getattr(c, "name", None)
        if name == "agent_traces_step_name_check":
            return str(getattr(c, "sqltext", "")).upper()
    return None


def test_orm_agent_trace_check_menyertakan_semua_langkah_migration_007():
    text = _check_text(AgentTrace)
    assert text is not None, "CHECK agent_traces_step_name_check tidak ditemukan"
    for step in MIGRATION_007_STEPS:
        assert f"'{step}'" in text, f"langkah {step} absen di CHECK ORM: {text}"


def test_orm_agent_trace_check_tanpa_langkah_di_luar_whitelist():
    """Whitelist ORM TIDAK melebar melebihi migration 007 (anti-drift dua arah)."""
    text = _check_text(AgentTrace)
    assert text is not None
    for raw in text.split("'"):
        token = raw.strip().strip(",")
        if token and token.isalpha():
            assert token in MIGRATION_007_STEPS, f"langkah liar {token} di CHECK ORM"


def test_semua_langkah_whitelist_diterima_metadata_metadata_check():
    """Sanity: constraint benar-benar terdaftar di metadata create_all()."""
    table = Base.metadata.tables["agent_traces"]
    names = {c.name for c in table.constraints}
    assert "agent_traces_step_name_check" in names
