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
DB_MODE="${DB_MODE:-default}"

# Password Postgres dibaca dari .env tanpa mencetaknya ke layar/log.
sandi="$(
  grep -E '^POSTGRES_PASSWORD=' .env 2>/dev/null \
    | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'"
)"
sandi="${sandi:-mealchain_local}"

DSN="postgresql+asyncpg://mealchain:${sandi}@postgres:5432/${DB_NAME}"

echo "== db-mode: ${perintah} (database=${DB_NAME}, DB_MODE=${DB_MODE}) =="
docker compose exec -T \
  -e DATABASE_URL="$DSN" \
  -e DB_MODE="$DB_MODE" \
  -e PYTHONPATH=/app \
  backend python -m app.seed.db_mode "$perintah" "$@"
