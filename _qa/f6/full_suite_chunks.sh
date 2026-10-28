#!/usr/bin/env bash
# Suite backend PENUH, dipecah 4 bagian — masing-masing pada KLON BARU dari DB
# gerbang `mealchain_f6_gate` (bukan DB demo). Alasan pemecahan: satu proses
# penuh pernah dibunuh OOM (exit 137) di mesin ini; klon per bagian juga
# menghilangkan pengaruh urutan antar-berkas (test-gate-hygiene aturan 6).
#
# Pemakaian: bash _qa/f6/full_suite_chunks.sh [jumlah_bagian]
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1

BAGIAN="${1:-4}"
SUMBER="mealchain_f6_gate"
OUT="_qa/f6/full-suite-chunks.log"
DSN_APP="$(docker compose exec -T backend printenv DATABASE_URL | tr -d '\r')"
: > "$OUT"

mapfile -t FILES < <(ls backend/tests/test_*.py | sed 's#^backend/##' | sort)
TOTAL=${#FILES[@]}
echo "jumlah berkas tes: $TOTAL, dibagi $BAGIAN bagian" | tee -a "$OUT"

for i in $(seq 1 "$BAGIAN"); do
  DB="mealchain_f6_chunk${i}"
  CHUNK=()
  for ((k=i-1; k<TOTAL; k+=BAGIAN)); do CHUNK+=("${FILES[$k]}"); done
  echo "===== BAGIAN $i/$BAGIAN — db=$DB, ${#CHUNK[@]} berkas ($(date '+%H:%M:%S'))" | tee -a "$OUT"

  docker exec mealchain-postgres psql -U mealchain -d postgres -v ON_ERROR_STOP=1 -c \
    "select pg_terminate_backend(pid) from pg_stat_activity where datname='${DB}' and pid <> pg_backend_pid();" >/dev/null 2>&1
  docker exec mealchain-postgres sh -lc "dropdb -U mealchain --if-exists ${DB} && createdb -U mealchain ${DB}" || { echo "BAGIAN $i: gagal buat DB" | tee -a "$OUT"; continue; }
  docker exec mealchain-postgres sh -lc "pg_dump -U mealchain -d ${SUMBER} --no-owner --no-privileges | psql -q -U mealchain -d ${DB}" >/dev/null 2>&1 || { echo "BAGIAN $i: gagal dump" | tee -a "$OUT"; continue; }
  echo "  isi klon: $(docker exec mealchain-postgres psql -U mealchain -d "$DB" -tAc 'select count(*) from batches') batch" | tee -a "$OUT"

  DSN="$(echo "$DSN_APP" | sed -E "s#/[A-Za-z0-9_]+(\\?|$)#/${DB}\\1#")"
  docker compose exec -T -e DATABASE_URL="$DSN" -e DEMO_SESSION_ENFORCE=false backend \
    python -m pytest "${CHUNK[@]}" -q --tb=line -p no:cacheprovider > "_qa/f6/chunk-${i}.log" 2>&1
  KODE=$?
  echo "  PYTEST_EXIT=$KODE  $(tail -1 _qa/f6/chunk-${i}.log)" | tee -a "$OUT"
done
echo "SELESAI $(date '+%H:%M:%S')" | tee -a "$OUT"
