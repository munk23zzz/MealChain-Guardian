"""Least privilege untuk role aplikasi, tanpa memutus backup/restore (Fase 11 butir 3).

Latar: migrasi 042 membuat `mealchain_app` hanya punya `SELECT`/`INSERT` pada
`ledger_blocks`, tetapi role itu belum punya hak kerja sama sekali pada tabel
lain — sehingga koneksi aplikasi belum bisa dipindahkan ke sana. Migrasi ini
melengkapinya tanpa menyentuh riwayat audit:

- `mealchain_app` dapat `SELECT, INSERT, UPDATE, DELETE` pada SEMUA tabel yang
  ada sekarang, plus `USAGE, SELECT` pada semua sequence (wajib untuk kolom
  serial/identity).
- Hak itu DICABUT kembali pada `ledger_blocks` (`UPDATE`, `DELETE`, `TRUNCATE`)
  dan pada `ledger_meta` (`DELETE`, `TRUNCATE`) — penanda generasi boleh naik,
  tetapi tidak boleh dihapus.
- `ALTER DEFAULT PRIVILEGES` memasang hak yang sama untuk tabel/sequence BARU
  yang dibuat role migrasi (`mealchain`), supaya migrasi berikutnya tidak
  diam-diam membuat tabel yang tidak bisa dipakai aplikasi.
- Migrasi dan `pg_dump`/restore tetap dijalankan role pemilik (`mealchain`),
  yang juga satu-satunya anggota `mealchain_migrator`. Aplikasi tidak pernah
  memegang DDL: tidak bisa `CREATE`, `ALTER`, `TRUNCATE`, atau `DROP`.

Role login (`mealchain_app_login`) TIDAK dibuat di sini: kata sandi tidak boleh
masuk berkas migrasi yang dilacak git. Pembuatannya ada di
`scripts/siapkan_role_app.py` yang membaca `APP_DB_PASSWORD` dari env.

Catatan nomor: 041 dipakai fase sebelumnya; berkas ini memakai 043 (lewat dari
042 milik fase yang sama) agar rantai revisi tetap satu garis.

Revision ID: 043_least_privilege_app
Revises: 042_ledger_append_only

"""

from typing import Sequence, Union

from alembic import op

revision: str = "043_least_privilege_app"
down_revision: Union[str, None] = "042_ledger_append_only"
branch_labels: Union[str, Sequence[str]] = None
depends_on: Union[str, Sequence[str]] = None

ROLE_APP = "mealchain_app"
ROLE_MIGRATOR = "mealchain_migrator"
ROLE_OWNER = "mealchain"


def upgrade() -> None:
    op.execute(f"GRANT USAGE ON SCHEMA public TO {ROLE_APP};")
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public "
        f"TO {ROLE_APP};"
    )
    op.execute(
        f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {ROLE_APP};"
    )

    # Riwayat audit tetap tidak dapat diubah aplikasi, walau tabel lain boleh.
    op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON ledger_blocks FROM {ROLE_APP};")
    op.execute(f"REVOKE DELETE, TRUNCATE ON ledger_meta FROM {ROLE_APP};")

    # Hak untuk objek yang lahir SESUDAH migrasi ini — hanya untuk objek yang
    # dibuat role migrasi/pemilik, supaya tidak memberi hak atas objek role lain.
    op.execute(
        f"ALTER DEFAULT PRIVILEGES FOR ROLE {ROLE_OWNER} IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {ROLE_APP};"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES FOR ROLE {ROLE_OWNER} IN SCHEMA public "
        f"GRANT USAGE, SELECT ON SEQUENCES TO {ROLE_APP};"
    )


def downgrade() -> None:
    op.execute(
        f"ALTER DEFAULT PRIVILEGES FOR ROLE {ROLE_OWNER} IN SCHEMA public "
        f"REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM {ROLE_APP};"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES FOR ROLE {ROLE_OWNER} IN SCHEMA public "
        f"REVOKE USAGE, SELECT ON SEQUENCES FROM {ROLE_APP};"
    )
    op.execute(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {ROLE_APP};")
    op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {ROLE_APP};")
