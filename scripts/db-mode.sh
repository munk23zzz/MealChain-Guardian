#!/usr/bin/env bash
# db-mode.sh — satu pintu untuk mengelola mode database MealChain Guardian.
#
#   bash scripts/db-mode.sh status
#   bash scripts/db-mode.sh init-default
#   bash scripts/db-mode.sh init-demo [--refresh]
#   bash scripts/db-mode.sh reset-demo --yes
#
# Variabel lingkungan:
#   DB_NAME  nama database di kontainer postgres (default: mealchain)
#   DB_MODE  default | demo — mode yang DIHARAPKAN aplikasi (default: default)
#
# Skrip ini hanya meneruskan ke `python -m app.seed.db_mode` di dalam kontainer
# backend, dengan DSN yang menunjuk database pilihan. Logika mode, pengaman,
# dan idempotensinya ada di modul itu (bukan di bash), supaya bisa diuji.
set -euo pipefail

akar="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$akar"

perintah="${1:-status}"
shift || true

DB_NAME="${DB_NAME:-mealchain}"
# DB_MODE TIDAK diberi nilai bawaan: `status` harus bisa membedakan "operator
# tidak menyetel mode" dari "operator mengharapkan default". Nilai bawaan di
# sini dulu membuat database DEMO yang sehat terbaca "cocok: false".

# Password Postgres dibaca dari .env tanpa mencetaknya ke layar/log.
sandi="$(
  grep -E '^POSTGRES_PASSWORD=' .env 2>/dev/null \
    | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'"
)"
sandi="${sandi:-mealchain_local}"

DSN="postgresql+asyncpg://mealchain:${sandi}@postgres:5432/${DB_NAME}"

# Teruskan DB_MODE hanya bila disetel, supaya modul bisa melaporkan mode_env
# sebagai null alih-alih membandingkan dengan nilai bawaan.
tambahan=()
if [[ -n "${DB_MODE:-}" ]]; then
  tambahan+=(-e "DB_MODE=${DB_MODE}")
fi

echo "== db-mode: ${perintah} (database=${DB_NAME}, DB_MODE=${DB_MODE:-<tidak disetel>}) =="
docker compose exec -T \
  -e DATABASE_URL="$DSN" \
  -e PYTHONPATH=/app \
  "${tambahan[@]}" \
  backend python -m app.seed.db_mode "$perintah" "$@"
