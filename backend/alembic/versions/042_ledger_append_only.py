"""Ledger append-only ditegakkan DATABASE, bukan konvensi (Fase 11 MG).

Latar (audit rencana-vs-kode 26 Okt 2026, temuan no. 11): `ledger_blocks` sudah
append-only secara KONVENSI di `ledger_service`, tetapi role yang dipakai
aplikasi masih pemilik tabel sekaligus superuser — ia bisa `UPDATE`, `DELETE`,
dan `TRUNCATE`. Klaim "append-only" karena itu belum punya penegak.

Migrasi ini memasang tiga lapis penegakan yang masing-masing bisa diuji:

1. **Trigger `prevent_ledger_mutation()`** — menolak `UPDATE`, `DELETE`, dan
   `TRUNCATE` pada `ledger_blocks` untuk SEMUA role, termasuk pemilik tabel.
   Trigger PostgreSQL berjalan juga untuk superuser, jadi satu-satunya jalan
   memutar balik riwayat adalah `ALTER TABLE ... DISABLE TRIGGER` (DDL, hanya
   role migrasi, tercatat di log database) — bukan operasi DML biasa.
2. **Pintu pemeliharaan eksplisit** — blok hanya boleh diubah/dihapus bila
   sesi menyatakan `SET LOCAL mealchain.ledger_maintenance = 'on'` DAN role
   sesi itu anggota `mealchain_migrator`. Dua syarat, bukan satu: pengaturan
   GUC sendirian tidak cukup bagi aplikasi, dan keanggotaan role sendirian
   tidak cukup bagi sesi yang lupa menyatakan niat. Dipakai jalur pemeliharaan
   (uji yang memotong ujung rantai, rebuild seed) dan TIDAK dipakai jalur kerja.
3. **Hak minimum untuk role aplikasi** — `mealchain_app` hanya `SELECT` dan
   `INSERT` pada `ledger_blocks`; `UPDATE`/`DELETE`/`TRUNCATE` dicabut dari
   `PUBLIC` dan tidak pernah diberikan. `ledger_meta` (penanda generasi) tetap
   boleh `UPDATE` karena ia bukan riwayat, hanya penunjuk generasi aktif.

Konsekuensi teknis yang ikut diperbaiki di `ledger_service`: `SELECT ... FOR
UPDATE` menuntut hak `UPDATE` pada tabel, sehingga role baca-tulis-minimum akan
GAGAL menambah blok. Penguncian baris terakhir diganti `pg_advisory_xact_lock`
yang hanya butuh `SELECT` — sifat anti-race-nya sama, haknya lebih kecil.

Koreksi luar biasa DILAYANI DENGAN MENAMBAH BLOK, bukan menulis ulang:
`ledger_append_correction(target_height, reason)` menulis blok
`ledger.correction` yang menunjuk tinggi+hash blok yang dikoreksi. Hanya
anggota `mealchain_migrator` yang memegang `EXECUTE`, dan hanya bisa berjalan
di bawah pintu pemeliharaan di atas. Rantai lama tidak pernah diputus.

Catatan nomor berkas: rencana menyebut `038_ledger_append_only.py`, tetapi 038
sudah dipakai pekerjaan lain (audit menetapkan 034-038 untuk fase sebelumnya).
Pekerjaan ini memakai nomor berikutnya yang bebas, **042**, dan merantai ke
revisi 041.

Role TIDAK dihapus pada `downgrade()`: role adalah objek klaster yang mungkin
sudah dipakai database lain, dan menghapusnya justru memutus sesi yang sedang
berjalan. `downgrade()` mencabut trigger, fungsi, dan hak — cukup untuk kembali
ke keadaan "append-only secara konvensi".

Revision ID: 042_ledger_append_only
Revises: 041_commodity_policies

"""

from typing import Sequence, Union

from alembic import op

revision: str = "042_ledger_append_only"
down_revision: Union[str, None] = "041_commodity_policies"
branch_labels: Union[str, Sequence[str]] = None
depends_on: Union[str, Sequence[str]] = None


ROLE_APP = "mealchain_app"
ROLE_MIGRATOR = "mealchain_migrator"


def upgrade() -> None:
    # --- 1. Role: aplikasi (tanpa DDL, tanpa ubah riwayat) vs migrasi ---------
    # NOLOGIN: role ini adalah WADAH HAK, bukan akun. Saat pemilik memutuskan
    # memindahkan koneksi aplikasi (butir 3), ia membuat akun login lalu
    # `GRANT mealchain_app TO <akun>`. Membuat akun login ber-password di dalam
    # migrasi akan menaruh kredensial di berkas yang dilacak git.
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROLE_APP}') THEN
                CREATE ROLE {ROLE_APP} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
                    NOINHERIT NOBYPASSRLS;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROLE_MIGRATOR}') THEN
                CREATE ROLE {ROLE_MIGRATOR} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
                    NOBYPASSRLS;
            END IF;
        END
        $$;
        """
    )

    # --- 2. Trigger penolak mutasi ------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_ledger_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            pintu text := coalesce(current_setting('mealchain.ledger_maintenance', true), '');
        BEGIN
            IF pintu = 'on'
               AND pg_has_role(current_user, 'mealchain_migrator', 'member') THEN
                IF TG_OP = 'TRUNCATE' THEN
                    RETURN NULL;
                ELSIF TG_OP = 'DELETE' THEN
                    RETURN OLD;
                END IF;
                RETURN NEW;
            END IF;

            RAISE EXCEPTION
                'ledger_append_only: % ditolak pada ledger_blocks (blok %). '
                'Riwayat audit tidak boleh diubah atau dihapus; koreksi lewat blok baru.',
                TG_OP, coalesce(OLD.height::text, NEW.height::text, 'semua')
                USING ERRCODE = 'insufficient_privilege',
                      HINT = 'Role migrasi saja: SET LOCAL mealchain.ledger_maintenance = ''on''.';
        END
        $$;
        """
    )
    # Satu pernyataan per op.execute: asyncpg menolak beberapa perintah dalam
    # satu prepared statement ("cannot insert multiple commands into a prepared
    # statement"), dan itu menggagalkan seluruh migrasi.
    op.execute("DROP TRIGGER IF EXISTS ledger_blocks_no_mutation ON ledger_blocks;")
    op.execute(
        """
        CREATE TRIGGER ledger_blocks_no_mutation
            BEFORE UPDATE OR DELETE ON ledger_blocks
            FOR EACH ROW EXECUTE FUNCTION prevent_ledger_mutation();
        """
    )
    op.execute("DROP TRIGGER IF EXISTS ledger_blocks_no_truncate ON ledger_blocks;")
    op.execute(
        """
        CREATE TRIGGER ledger_blocks_no_truncate
            BEFORE TRUNCATE ON ledger_blocks
            FOR EACH STATEMENT EXECUTE FUNCTION prevent_ledger_mutation();
        """
    )

    # --- 3. Prosedur admin yang disetujui: koreksi dengan MENAMBAH blok ------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION ledger_append_correction(
            p_target_height bigint,
            p_reason text,
            p_actor uuid DEFAULT NULL
        ) RETURNS bigint
        LANGUAGE plpgsql AS $$
        DECLARE
            v_pintu text := coalesce(current_setting('mealchain.ledger_maintenance', true), '');
            v_prev text;
            v_height bigint;
            v_target_hash text;
            v_generation integer;
            v_payload text;
            v_hash text;
        BEGIN
            IF NOT (v_pintu = 'on'
                    AND pg_has_role(current_user, 'mealchain_migrator', 'member')) THEN
                RAISE EXCEPTION
                    'ledger_append_only: prosedur koreksi hanya untuk role migrasi '
                    'di bawah pintu pemeliharaan'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF p_reason IS NULL OR btrim(p_reason) = '' THEN
                RAISE EXCEPTION 'ledger_append_only: alasan koreksi wajib diisi'
                    USING ERRCODE = 'invalid_parameter_value';
            END IF;

            SELECT payload_hash INTO v_target_hash
              FROM ledger_blocks WHERE height = p_target_height;
            IF v_target_hash IS NULL THEN
                RAISE EXCEPTION 'ledger_append_only: blok % tidak ada', p_target_height
                    USING ERRCODE = 'no_data_found';
            END IF;

            -- Kunci rantai tanpa hak UPDATE (advisory lock hanya butuh SELECT).
            PERFORM pg_advisory_xact_lock(hashtext('ledger_blocks_append'));

            SELECT height, payload_hash INTO v_height, v_prev
              FROM ledger_blocks ORDER BY height DESC LIMIT 1;
            v_prev := coalesce(v_prev, repeat('0', 64));
            v_height := coalesce(v_height, 0) + 1;

            SELECT coalesce((SELECT generation FROM ledger_meta WHERE id = 1), 1)
              INTO v_generation;

            v_payload := jsonb_build_object(
                'action', 'ledger.correction',
                'target_height', p_target_height,
                'target_hash', v_target_hash,
                'reason', p_reason,
                'at', to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
            )::text;
            v_hash := encode(sha256((v_prev || v_payload)::bytea), 'hex');

            INSERT INTO ledger_blocks
                (height, prev_hash, payload_hash, action, entity_id, actor_id,
                 payload, generation)
            VALUES (v_height, v_prev, v_hash, 'ledger.correction', NULL, p_actor,
                    v_payload, v_generation);

            RETURN v_height;
        END
        $$;
        """
    )

    # --- 4. Hak minimum ------------------------------------------------------
    # PUBLIC tidak boleh mewarisi hak apa pun pada riwayat.
    op.execute("REVOKE ALL ON ledger_blocks FROM PUBLIC;")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {ROLE_APP};")
    op.execute(f"GRANT SELECT, INSERT ON ledger_blocks TO {ROLE_APP};")
    op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON ledger_blocks FROM {ROLE_APP};")
    # Penanda generasi bukan riwayat: aplikasi menaikkannya saat reset demo.
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON ledger_meta TO {ROLE_APP};")
    op.execute(f"REVOKE DELETE, TRUNCATE ON ledger_meta FROM {ROLE_APP};")
    op.execute(
        "REVOKE ALL ON FUNCTION ledger_append_correction(bigint, text, uuid) FROM PUBLIC;"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION ledger_append_correction(bigint, text, uuid) "
        f"TO {ROLE_MIGRATOR};"
    )


def downgrade() -> None:
    """Kembali ke keadaan lama: penegakan dicabut, role dibiarkan hidup."""
    op.execute(
        "REVOKE EXECUTE ON FUNCTION ledger_append_correction(bigint, text, uuid) "
        f"FROM {ROLE_MIGRATOR};"
    )
    op.execute("DROP FUNCTION IF EXISTS ledger_append_correction(bigint, text, uuid);")
    op.execute("DROP TRIGGER IF EXISTS ledger_blocks_no_mutation ON ledger_blocks;")
    op.execute("DROP TRIGGER IF EXISTS ledger_blocks_no_truncate ON ledger_blocks;")
    op.execute("DROP FUNCTION IF EXISTS prevent_ledger_mutation();")
    op.execute(f"REVOKE ALL ON ledger_meta FROM {ROLE_APP};")
    op.execute(f"REVOKE ALL ON ledger_blocks FROM {ROLE_APP};")
