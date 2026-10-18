"""Status terminal `review_only` untuk temuan (price anomaly).

Audit 18 Okt 2026 (M6): keputusan `price_anomaly` dari Event 2 lahir tanpa
`quantity_kg`, sehingga `/actions/execute` selalu menolaknya (422) dan
`/actions/propose` tetap menawarkannya sebagai usulan transfer. Keputusan itu
tidak punya jalan keluar: tidak bisa dieksekusi, tidak bisa ditutup, dan terus
menggantung di antrean "menunggu tindakan".

`review_only` = temuan yang memang hanya untuk ditinjau. Ia TIDAK menuntut
approval dan TIDAK bisa dieksekusi; ia tetap terbaca (feed, bukti, jejak) dan
tetap terhubung ke ledger lewat blok pembuatan Event 2.

Revision ID: 020_review_only_status
Revises: 019_batch_quarantine
"""

from alembic import op

revision = "020_review_only_status"
down_revision = "019_batch_quarantine"
branch_labels = None
depends_on = None

STATUS_LAMA = (
    "status IN ('proposed','verifier_flagged','pending_approval',"
    "'approved','rejected','executed')"
)
STATUS_BARU = (
    "status IN ('proposed','verifier_flagged','pending_approval',"
    "'approved','rejected','executed','review_only')"
)


def upgrade() -> None:
    op.execute("ALTER TABLE decisions DROP CONSTRAINT decisions_status_check")
    # Backfill SEBELUM constraint baru: keputusan price_anomaly yang masih
    # `proposed` memang tidak pernah bisa dieksekusi (tanpa kuantitas), jadi
    # memindahkannya ke status terminal adalah koreksi, bukan perubahan arti.
    # Baris yang sudah masuk alur manusia (pending_approval/verifier_flagged/
    # approved) TIDAK disentuh — ada approval tercatat di sana.
    op.execute(
        "UPDATE decisions SET status = 'review_only' "
        "WHERE decision_type = 'price_anomaly' AND status = 'proposed'"
    )
    op.execute(f"ALTER TABLE decisions ADD CONSTRAINT decisions_status_check CHECK ({STATUS_BARU})")


def downgrade() -> None:
    op.execute("ALTER TABLE decisions DROP CONSTRAINT decisions_status_check")
    op.execute("UPDATE decisions SET status = 'proposed' WHERE status = 'review_only'")
    op.execute(f"ALTER TABLE decisions ADD CONSTRAINT decisions_status_check CHECK ({STATUS_LAMA})")
