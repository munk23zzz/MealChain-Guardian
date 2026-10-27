"""Mode sesi demo + jangkar evaluasi (Fase 2 MG, migrasi 040).

Latar: `demo_sessions` sejak migrasi 024 hanya menyimpan jendela waktu
(`started_at`, `expires_at`, `anchor_now`). Tidak ada kolom yang menyatakan
**cara kerja** sesi, sehingga replay dan realtime mustahil dibedakan setelah
sesi ditutup; dan tidak ada jangkar evaluasi, sehingga satu-satunya waktu acuan
yang ada adalah tanggal global (8 Okt 2026) yang dipakai semua jalur.

Kolom baru (semua nullable / berdefault aman — tidak ada backfill paksa):

- ``mode``             — ``replay`` | ``realtime``. Default ``replay`` untuk
  baris lama: satu-satunya data historis yang ada memang replay kanonik, dan
  default itu membuat kode lama (yang belum menulis mode) tetap terbaca.
- ``evaluation_anchor``— jangkar waktu EVALUASI (freshness, umur dataset,
  timestamp simulasi). BUKAN waktu kejadian operator: approval/PO/penerimaan
  tetap jam dinding. Default ``2026-10-08T12:00:00+00:00`` (jangkar kanon) agar
  baris lama langsung punya acuan yang sama dengan dataset kanon.
- ``dataset_version``  — identitas versi dataset. NULL untuk baris lama: nilai
  itu tidak bisa diturunkan tanpa mengarang, dan resolver memperlakukannya
  sebagai "versi kanon" (`REPLAY_DATASET_VERSION`).

Nomor: rencana menyebut 034, tetapi 034–038 sudah dipesan pekerjaan lain dan
``039_agent_trace_parent_run_id`` sudah menjadi head. Migrasi ini memakai
**040** supaya tidak bertabrakan.

Revision ID: 040_session_modes_and_ownership
Revises: 039_agent_trace_parent_run_id

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "040_session_modes_and_ownership"
down_revision: Union[str, None] = "039_agent_trace_parent_run_id"
branch_labels: Union[str, Sequence[str]] = None
depends_on: Union[str, Sequence[str]] = None

#: Jangkar evaluasi kanon (sama dengan `app.seed.timeseries.CANONICAL_REF`).
ANCHOR_KANON = "2026-10-08T12:00:00+00:00"

#: Anak yang WAJIB bisa menyebut sesi pemiliknya walau keputusan induknya
#: sudah dihapus (`delivery_events.decision_id` bisa NULL lewat
#: `ON DELETE SET NULL`). Dua nama ini sudah punya kolomnya sejak migrasi 025;
#: daftar di sini dipakai untuk MEMBUKTIKAN keberadaannya di downgrade/upgrade
#: (bukan menambah kolom baru).
ANAK_BERPENANDA = ("delivery_events", "sap_mock_purchase_orders")


def upgrade() -> None:
    op.add_column(
        "demo_sessions",
        sa.Column(
            "mode",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'replay'"),
        ),
    )
    op.add_column(
        "demo_sessions",
        sa.Column(
            "evaluation_anchor",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text(f"'{ANCHOR_KANON}'::timestamptz"),
        ),
    )
    op.add_column(
        "demo_sessions",
        sa.Column("dataset_version", sa.Text(), nullable=True),
    )
    # CHECK, bukan enum: nilai yang sah dijaga di API (`Literal`) DAN di DB,
    # supaya baris yang ditulis jalur lain (seeder/psql) tidak lolos.
    op.create_check_constraint(
        "demo_sessions_mode_check",
        "demo_sessions",
        "mode IN ('replay','realtime')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "demo_sessions_mode_check", "demo_sessions", type_="check"
    )
    op.drop_column("demo_sessions", "dataset_version")
    op.drop_column("demo_sessions", "evaluation_anchor")
    op.drop_column("demo_sessions", "mode")
