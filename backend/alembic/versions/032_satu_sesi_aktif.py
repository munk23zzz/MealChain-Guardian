"""Satu sesi demo aktif — dijamin database, bukan hanya kunci satu proses.

Latar (25 Okt 2026): `services/demo_session.mulai()` sudah menutup sesi lama
sebelum membuka yang baru, dan endpoint start/end memakai `asyncio.Lock`. Dua
pengaman itu hanya berlaku DI DALAM satu proses: begitu uvicorn dijalankan
dengan lebih dari satu worker — atau dua proses (backend + skrip pemeliharaan)
menyentuh DB yang sama — dua baris `status='active'` bisa hidup bersamaan.
Akibatnya "sesi mana yang sedang berjalan" jadi ambigu: countdown di layar
membaca baris terbaru, sementara penyapu sesi dan pembersihan memakai baris lain.

Perbaikan: unique partial index pada `demo_sessions(status) WHERE status='active'`.
Constraint ini tidak menyentuh riwayat (`expired`/`ended` boleh berapa pun).

Revision ID: 032_satu_sesi_aktif
Revises: 031_ledger_generation
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "032_satu_sesi_aktif"
down_revision = "031_ledger_generation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Data lama bisa memuat lebih dari satu baris aktif (persis kasus yang
    # ditutup migrasi ini). Sisakan yang PALING BARU, tutup sisanya sebagai
    # `expired` — jangan dihapus: riwayat sesi adalah jejak audit.
    op.execute(
        sa.text(
            "UPDATE demo_sessions AS d SET status = 'expired', "
            "ended_at = COALESCE(d.ended_at, now()) "
            "WHERE d.status = 'active' AND d.id <> ("
            "  SELECT id FROM demo_sessions WHERE status = 'active' "
            "  ORDER BY started_at DESC, id DESC LIMIT 1"
            ")"
        )
    )
    op.create_index(
        "uq_demo_sessions_satu_aktif",
        "demo_sessions",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("uq_demo_sessions_satu_aktif", table_name="demo_sessions")
