#!/usr/bin/env bash
# =============================================================================
# reset-demo.sh — segarkan dataset demo di antara sesi juri
# =============================================================================
#
# Yang dilakukan:
#   1. (opsional) migrasi skema — no-op bila sudah head
#   2. jalankan ulang seed referensi (akun + lokasi/komoditas; idempoten)
#   3. jalankan ulang `app.seed.demo_template` — membangun ulang seluruh dataset
#      demo dan membuka sesi demo baru (sesi lama kedaluwarsa/berakhir)
#   4. cetak jumlah baris per tabel + revisi skema + sesi demo aktif
#
# Aman dijalankan berulang dan di tengah hari. TIDAK menyentuh .env, TIDAK
# me-restart kontainer, TIDAK menghapus volume.
#
# Pemakaian:
#   bash infra/vps/reset-demo.sh
#
# Durasi wajar: 60-90 detik (seed menulis ratusan baris + memanggil OSRM untuk
# rute; bila OSRM tidak terjangkau, laporan seed memuat peringatan rute dan
# seeding tetap selesai).
# =============================================================================
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$DIR/.env"

[ -f "$ENV_FILE" ] || {
  echo "GAGAL: $ENV_FILE belum ada. Jalankan deploy.sh lebih dulu." >&2
  exit 1
}

COMPOSE=(docker compose -f "$DIR/docker-compose.vps.yml" --env-file "$ENV_FILE")

langkah() { printf '\n==> %s\n' "$*"; }

command -v docker >/dev/null 2>&1 || { echo "GAGAL: docker tidak ada di PATH." >&2; exit 1; }

# Pastikan backend benar-benar siap sebelum menyemai (bukan hanya "running").
status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
  mealchain-vps-backend 2>/dev/null || echo 'tidak-ada')"
[ "$status" = "healthy" ] || {
  echo "GAGAL: kontainer backend berstatus '$status' (butuh 'healthy')." >&2
  echo "  Nyalakan/perbaiki dulu: bash $DIR/deploy.sh" >&2
  exit 1
}

nilai_env() {
  grep -E "^$1=" "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- \
    | tr -d '\r' | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//"
}
PG_USER="$(nilai_env POSTGRES_USER)"
PG_DB="$(nilai_env POSTGRES_DB)"
PG_USER="${PG_USER:-mealchain}"
PG_DB="${PG_DB:-mealchain}"

langkah "Migrasi skema (no-op bila sudah head)"
"${COMPOSE[@]}" exec -T backend alembic upgrade head

langkah "Seed referensi (akun, lokasi, komoditas)"
"${COMPOSE[@]}" exec -T backend python -m app.seed.reference

langkah "Bangun ulang dataset demo"
# Keluaran = JSON laporan seed (termasuk hitungan). Disimpan supaya bisa
# diperiksa walau terminal terputus.
laporan="$("${COMPOSE[@]}" exec -T backend python -m app.seed.demo_template)"
printf '%s\n' "$laporan"
printf '%s\n' "$laporan" > "$DIR/.last-seed.json"
echo "    laporan lengkap: $DIR/.last-seed.json"

langkah "Jumlah baris per tabel"
"${COMPOSE[@]}" exec -T postgres psql -U "$PG_USER" -d "$PG_DB" -v ON_ERROR_STOP=1 <<'SQL'
\pset pager off
SELECT 'users'            AS tabel, count(*) FROM users
UNION ALL SELECT 'locations',      count(*) FROM locations
UNION ALL SELECT 'commodities',    count(*) FROM commodities
UNION ALL SELECT 'suppliers',      count(*) FROM suppliers
UNION ALL SELECT 'supply_records', count(*) FROM supply_records
UNION ALL SELECT 'demand_records', count(*) FROM demand_records
UNION ALL SELECT 'price_signals',  count(*) FROM price_signals
UNION ALL SELECT 'batches',        count(*) FROM batches
UNION ALL SELECT 'decisions',      count(*) FROM decisions
UNION ALL SELECT 'approvals',      count(*) FROM approvals
UNION ALL SELECT 'batch_receipts', count(*) FROM batch_receipts
UNION ALL SELECT 'ledger_blocks',  count(*) FROM ledger_blocks
UNION ALL SELECT 'agent_traces',   count(*) FROM agent_traces
ORDER BY tabel;
SQL

langkah "Revisi skema & sesi demo"
"${COMPOSE[@]}" exec -T postgres psql -U "$PG_USER" -d "$PG_DB" -v ON_ERROR_STOP=1 <<'SQL'
\pset pager off
SELECT version_num AS alembic_version FROM alembic_version;
SELECT status, mode, started_at, expires_at
FROM demo_sessions
ORDER BY started_at DESC
LIMIT 3;
SQL

langkah "Selesai"
cat <<'EOF'
Data demo sudah dibangun ulang. Sesi demo baru dibuka oleh seed; bila UI
menampilkan tombol "Mulai sesi demo", menekannya TIDAK merusak data template
(hanya membuka jendela kerja).

Bila ada panel yang masih kosong: cek laporan seed di .last-seed.json dan
pastikan backend sehat (docker compose ... ps).
EOF
