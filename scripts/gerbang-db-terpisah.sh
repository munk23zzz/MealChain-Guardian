#!/usr/bin/env bash
# Gerbang backend pada DATABASE TERPISAH (`mealchain_gate`).
#
# Kenapa: suite backend memakai DB kerja bersama dan mem-purge baris
# `origin='demo'`. Dijalankan berulang di DB demo, hasilnya bergeser sendiri
# (terukur 21 Okt 2026: run yang sama menghasilkan 2, 4, 35, dan 38 kegagalan
# hanya karena keadaan awal DB berbeda). Skrip ini menyiapkan DB sendiri,
# menyemainya dengan pipeline resmi yang sama (`semai-demo.sh`), lalu menjalankan
# suite di sana — DB demo tidak disentuh.
#
# Pemakaian:
#   bash scripts/gerbang-db-terpisah.sh              # bangun ulang + suite
#   bash scripts/gerbang-db-terpisah.sh --pakai-ulang  # pakai DB gate yang ada
#
# Hasil ditulis ke _qa/gerbang-db-terpisah-<tanggal>.txt.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

DB=mealchain_gate
# Kata sandi dibaca dari .env (tidak pernah ditulis di berkas ini). Dulu DSN
# beserta sandi tertulis literal di sini — audit lineage F-01.
sandi="$(
  grep -E '^POSTGRES_PASSWORD=' .env 2>/dev/null \
    | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'"
)"
sandi="${sandi:-mealchain_local}"
DSN="postgresql+asyncpg://mealchain:${sandi}@postgres:5432/${DB}"
OUT="_qa/gerbang-db-terpisah-$(date +%Y-%m-%d).txt"
PAKAI_ULANG=0
[[ "${1:-}" == "--pakai-ulang" ]] && PAKAI_ULANG=1

mkdir -p _qa

if [[ $PAKAI_ULANG -eq 0 ]]; then
  echo "== [1/5] siapkan DB $DB (putuskan sesi lama, buat ulang) =="
  docker exec mealchain-postgres psql -U mealchain -d postgres -v ON_ERROR_STOP=1 -c \
    "select pg_terminate_backend(pid) from pg_stat_activity where datname='${DB}' and pid <> pg_backend_pid();" \
    >/dev/null || exit 1
  docker exec mealchain-postgres sh -lc "dropdb -U mealchain --if-exists ${DB} && createdb -U mealchain ${DB}" || exit 1

  echo "== [2/5] migrasi ke head =="
  docker compose exec -T -e DATABASE_URL="$DSN" backend alembic upgrade head 2>&1 | tail -2 || exit 1

  # Urutan penting dan bertingkat:
  #   3a. canonical + akun demo  → template butuh user (kepala/ahli gizi) untuk
  #       membuat penerimaan, eksklusi, dan status tambahan. Tanpa ini template
  #       melaporkan "Jakarta / akun kepala tidak ada", receipts 0, eksklusi 0
  #       (terukur pada rebuild pertama: 6 gagal vs 4 pada DB yang sudah berisi user).
  #   3b. template ("Siapkan data demo") → membersihkan 13.384 baris operasional.
  #   3c. semai penuh → mengembalikan deret demo 1 Sep–5 Nov + 4 kasus per kota.
  echo "== [3a/5] canonical + akun demo (tanpa deret waktu) =="
  DATABASE_URL="$DSN" bash scripts/semai-demo.sh --canonical 2>&1 | tail -2 || exit 1

  # Template ("Siapkan data demo") MEMBERSIHKAN baris operasional
  # lebih dulu (terukur: 13.384 baris), jadi ia harus jalan SEBELUM semai; kalau
  # dibalik, deret demo 1 Sep–5 Nov hilang dan puluhan tes kehilangan data.
  # Terukur: template saja → batch 120 tapi supply demo 0; template lalu semai →
  # batch 120 + supply demo 5.160 + 4 kasus per kota (sama seperti DB demo).
  echo "== [3/5] bangun template demo (jalur tombol 'Siapkan data demo') =="
  docker compose exec -T -e DATABASE_URL="$DSN" -e PYTHONPATH=/app backend python -c "
import asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.core.config import settings
from app.seed.demo_template import build_into

async def main():
    e = create_async_engine(settings.database_url)
    m = async_sessionmaker(e, expire_on_commit=False)
    async with m() as db:
        laporan = await build_into(db, purge=True, freeze=True, bersihkan_sisa=False)
        await db.commit()
        print('template:', {k: v for k, v in laporan.items() if k != 'rincian'})
    await e.dispose()

asyncio.run(main())
" 2>&1 | tail -2 || exit 1

  echo "== [3c/5] semai penuh (deret waktu + aktivitas + kasus) =="
  DATABASE_URL="$DSN" bash scripts/semai-demo.sh 2>&1 | tail -3 || exit 1
else
  echo "== [1-3/5] memakai DB $DB yang sudah ada =="
fi

echo "== [4/5] ringkas isi DB gate =="
docker exec mealchain-postgres psql -U mealchain -d "$DB" -At -F ' | ' \
  -c "select 'supply:'||origin||'='||count(*) from supply_records group by origin" \
  -c "select 'decisions:'||origin||'='||count(*) from decisions group by origin" \
  -c "select 'batch='||count(*) from batches" \
  -c "select 'menu='||count(*) from menu_plans"

echo "== [5/5] suite penuh di DB gate =="
docker compose exec -T -e DATABASE_URL="$DSN" -e DEMO_SESSION_ENFORCE=false backend \
  python -m pytest -q -p no:cacheprovider > "$OUT" 2>&1
KODE=$?
echo "EXIT=$KODE  (0 = semua lulus)"
tail -5 "$OUT"
echo "log: $OUT"
echo
echo "DB demo TIDAK disentuh. Untuk menyemai ulang DB demo setelah eksperimen:"
echo "  bash scripts/semai-demo.sh"
