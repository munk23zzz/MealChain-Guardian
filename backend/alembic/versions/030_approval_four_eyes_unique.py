"""Four-eyes ditegakkan database pada `approvals` (23 Okt 2026).

Latar (audit adaptasi verifier agent): quorum dihitung dari BARIS approval, bukan
dari user unik. Tanpa kunci unik, satu akun yang mengirim dua permintaan
approve bisa memenuhi syarat "dua approver role berbeda" — syarat empat mata
runtuh tanpa satu pun kode yang salah.

Sebelum indeks dibuat:
1. Baris duplikat (decision_id, approved_by) dirapikan — disisakan yang paling
   akhir (approved_at terbaru, tie-break id terbesar) supaya jejak audit yang
   dipakai adalah keputusan terakhir orang itu.
2. Indeks unik parsial tidak dipakai di sini: aturannya berlaku untuk SEMUA
   baris, termasuk penolakan (satu akun tetap hanya boleh memberi satu
   keputusan per usulan).

Catatan API: perubahan ini mengubah kemungkinan 500 menjadi 409. Endpoint
approve menolak lebih awal bila akun itu sudah punya baris, dan menangkap
IntegrityError untuk balapan dua request bersamaan.

Revision ID: 030_approval_four_eyes_unique
Revises: 029_kpi_writeback_ref
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "030_approval_four_eyes_unique"
down_revision = "029_kpi_writeback_ref"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM approvals a USING approvals b "
            "WHERE a.decision_id = b.decision_id "
            "AND a.approved_by = b.approved_by "
            "AND (a.approved_at, a.id) < (b.approved_at, b.id)"
        )
    )
    op.create_index(
        "uq_approvals_decision_user",
        "approvals",
        ["decision_id", "approved_by"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_approvals_decision_user", table_name="approvals")
