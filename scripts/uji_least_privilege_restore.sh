#!/usr/bin/env bash
# Uji backup/restore TANPA memutus rantai bukti (Fase 11 MG, butir 3).
#
# Yang dibuktikan:
#   1. `pg_dump`/`pg_restore` dijalankan role berwenang (pemilik DB) dan berhasil.
#   2. Isi hasil restore sama: jumlah blok, tinggi maksimum, jumlah keputusan.
#   3. Rantai hash di hasil restore tetap VALID dan cangkupan blok tetap terbaca
#      (dijalankan lewat tes pytest pada DB hasil restore, bukan diklaim).
#   4. Hak minimum tetap berlaku sesudah restore: akun aplikasi bisa membaca,
#      tidak bisa mengubah riwayat (trigger + grant ikut terbawa dump).
#
# Pemakaian (dari root repo):
#   bash scripts/uji_least_privilege_restore.sh [SUMBER] [TUJUAN]
# Default: SUMBER=mealchain (DB demo), TUJUAN=mealchain_uji_restore.
#
# Tidak mencetak kata sandi: semua akses psql memakai socket di dalam container
# postgres, dan DSN tes dibentuk dari env container (bukan dari .env repo).
set -euo pipefail

SUMBER="${1:-mealchain}"
TUJUAN="${2:-mealchain_uji_restore}"
PG="${PG_CONTAINER:-mealchain-postgres}"
BACKEND_IMAGE="${BACKEND_IMAGE:-mealchain-guardian-backend}"
NETWORK="${NETWORK:-mealchain-guardian_mealchain-network}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
# Docker Desktop di Windows butuh path gaya `E:/...`, bukan `/e/...` milik MSYS.
REPO_NATIVE="$(cygpath -m "$REPO" 2>/dev/null || echo "$REPO")"
DUMP="/tmp/${SUMBER}-ke-${TUJUAN}.dump"

langkah() { printf '\n== %s ==\n' "$1"; }

langkah "0. Prasyarat"
docker inspect "$PG" >/dev/null
PGUSER="$(docker exec "$PG" printenv POSTGRES_USER)"
PGPASS="$(docker exec "$PG" printenv POSTGRES_PASSWORD)"
echo "container   : $PG"
echo "sumber      : $SUMBER"
echo "tujuan      : $TUJUAN"

langkah "1. pg_dump (role pemilik)"
docker exec "$PG" pg_dump -U "$PGUSER" -d "$SUMBER" -Fc -f "$DUMP"
docker exec "$PG" sh -lc "ls -l $DUMP"

langkah "2. pg_restore ke DB tujuan"
docker exec "$PG" psql -U "$PGUSER" -d postgres -q \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$TUJUAN' AND pid<>pg_backend_pid();" \
  -c "DROP DATABASE IF EXISTS $TUJUAN;" \
  -c "CREATE DATABASE $TUJUAN OWNER $PGUSER;"
docker exec "$PG" pg_restore -U "$PGUSER" -d "$TUJUAN" --no-owner "$DUMP"

langkah "3. Bandingkan isi"
for q in \
  "SELECT count(*) FROM ledger_blocks" \
  "SELECT coalesce(max(height),0) FROM ledger_blocks" \
  "SELECT count(*) FROM decisions"; do
  a="$(docker exec "$PG" psql -U "$PGUSER" -d "$SUMBER" -tAc "$q")"
  b="$(docker exec "$PG" psql -U "$PGUSER" -d "$TUJUAN" -tAc "$q")"
  printf '  %-45s sumber=%-8s restore=%-8s %s\n' "$q" "$a" "$b" \
    "$([ "$a" = "$b" ] && echo SAMA || echo BEDA)"
  [ "$a" = "$b" ] || { echo "GAGAL: isi restore berbeda"; exit 1; }
done

langkah "4. Versi migrasi di hasil restore"
docker exec "$PG" psql -U "$PGUSER" -d "$TUJUAN" -tAc "SELECT version_num FROM alembic_version"

langkah "5. Tes rantai pada DB hasil restore (bukan klaim)"
DSN="postgresql+asyncpg://${PGUSER}:${PGPASS}@postgres:5432/${TUJUAN}"
docker run --rm --network "$NETWORK" --env-file "$REPO_NATIVE/.env" -e DATABASE_URL="$DSN" \
  -v "$REPO_NATIVE/backend:/app" -w /app "$BACKEND_IMAGE" \
  python -m pytest -q tests/test_ledger_linkage.py tests/test_ledger_immutability.py \
  tests/test_least_privilege_app_role.py

langkah "6. Hak minimum sesudah restore"
docker exec "$PG" psql -U "$PGUSER" -d "$TUJUAN" -tAc \
  "SELECT 'app UPDATE ledger_blocks=' || has_table_privilege('mealchain_app','ledger_blocks','UPDATE')
        || ', app INSERT=' || has_table_privilege('mealchain_app','ledger_blocks','INSERT')
        || ', app SELECT decisions=' || has_table_privilege('mealchain_app','decisions','SELECT')"

if [ "${KEEP:-0}" = "1" ]; then
  echo
  echo "DB $TUJUAN dipertahankan (KEEP=1)."
else
  langkah "7. Bersihkan"
  docker exec "$PG" psql -U "$PGUSER" -d postgres -q -c "DROP DATABASE IF EXISTS $TUJUAN;"
  docker exec "$PG" sh -lc "rm -f $DUMP"
fi

echo
echo "SELESAI: dump/restore mempertahankan rantai dan hak minimum."
