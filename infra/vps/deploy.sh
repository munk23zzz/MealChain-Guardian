#!/usr/bin/env bash
# =============================================================================
# deploy.sh — pasang / perbarui MealChain Guardian di satu VPS (Ubuntu 22/24)
# =============================================================================
#
# Idempoten: aman dijalankan berulang. Yang dilakukan, berurutan:
#   1. cek docker + docker compose v2 + daemon hidup
#   2. siapkan infra/vps/.env dari templat bila belum ada (lalu BERHENTI)
#   3. tolak placeholder yang belum diganti (DOMAIN/JWT_SECRET/sandi DB)
#   4. docker compose pull + build + up -d
#   5. tunggu backend benar-benar sehat (GET /health, bukan cek port)
#   6. alembic upgrade head (skema) + seed referensi (akun & lokasi)
#   7. seed dataset demo SEKALI, dijaga berkas penanda .seed-done
#   8. cetak URL dan langkah verifikasi
#
# Pemakaian:
#   bash infra/vps/deploy.sh              # pasang/perbarui
#   bash infra/vps/deploy.sh --reseed     # paksa seed ulang (abaikan penanda)
#
# Tidak menyentuh host selain Docker: tidak memasang paket, tidak mengubah
# firewall, tidak menulis di luar direktori ini (kecuali volume Docker).
# =============================================================================
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$DIR/.env"
ENV_CONTOH="$DIR/.env.vps.example"
MARKER="$DIR/.seed-done"
COMPOSE=(docker compose -f "$DIR/docker-compose.vps.yml" --env-file "$ENV_FILE")
RESEED=0

for arg in "$@"; do
  case "$arg" in
    --reseed) RESEED=1 ;;
    -h|--help)
      sed -n '2,25p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "argumen tidak dikenal: $arg (pakai --reseed atau --help)" >&2
      exit 2
      ;;
  esac
done

langkah() { printf '\n==> %s\n' "$*"; }
gagal()  { printf '\nGAGAL: %s\n' "$*" >&2; exit 1; }

# Nilai dari .env tanpa mengeksekusinya (tidak ada `source`) dan tanpa
# mencetaknya ke layar/log.
nilai_env() {
  grep -E "^$1=" "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- \
    | tr -d '\r' | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//"
}

# -----------------------------------------------------------------------------
# 1. Alat dasar
# -----------------------------------------------------------------------------
langkah "Cek Docker"
command -v docker >/dev/null 2>&1 || gagal "docker tidak ada di PATH.
  Ubuntu: curl -fsSL https://get.docker.com | sh
  lalu:   sudo usermod -aG docker \$USER  &&  newgrp docker"

docker compose version >/dev/null 2>&1 || gagal "plugin 'docker compose' (v2) tidak ada.
  Ubuntu: sudo apt-get install -y docker-compose-v2
  (perintah lama 'docker-compose' TIDAK dipakai skrip ini)"

docker info >/dev/null 2>&1 || gagal "daemon Docker tidak berjalan / tidak bisa diakses user ini.
  Coba: sudo systemctl enable --now docker   (dan pastikan \$USER ada di grup docker)"
echo "    docker $(docker version --format '{{.Server.Version}}' 2>/dev/null || echo '?') / $(docker compose version --short 2>/dev/null || echo '?')"

# -----------------------------------------------------------------------------
# 2. .env
# -----------------------------------------------------------------------------
langkah "Berkas konfigurasi: $ENV_FILE"
if [ ! -f "$ENV_FILE" ]; then
  [ -f "$ENV_CONTOH" ] || gagal "templat $ENV_CONTOH tidak ada — repo tidak lengkap."
  cp "$ENV_CONTOH" "$ENV_FILE"
  chmod 600 "$ENV_FILE" 2>/dev/null || true
  cat <<EOF

.env BELUM ADA. Templat sudah disalin ke:
    $ENV_FILE

Isi dulu nilai berikut, lalu jalankan skrip ini lagi:

  1) DOMAIN            domain UI, mis. demo.mealchain.id (tanpa https://)
  2) ACME_EMAIL        email pendaftaran sertifikat
  3) JWT_SECRET        openssl rand -hex 32
  4) POSTGRES_PASSWORD openssl rand -hex 24

Opsional: DEMO_MODE, LOGIN_RATE_LIMIT, NEXT_PUBLIC_API_URL.

Sunting:  nano $ENV_FILE
Skrip ini SENGAJA berhenti sekarang supaya tidak pernah menyalakan stack
dengan kunci contoh.

EOF
  exit 1
fi

chmod 600 "$ENV_FILE" 2>/dev/null || true
[ -r "$ENV_FILE" ] || gagal "$ENV_FILE tidak bisa dibaca."

# -----------------------------------------------------------------------------
# 3. Placeholder = berhenti (fail-closed)
# -----------------------------------------------------------------------------
langkah "Validasi nilai wajib"
DOMAIN="$(nilai_env DOMAIN)"
JWT_SECRET="$(nilai_env JWT_SECRET)"
POSTGRES_PASSWORD="$(nilai_env POSTGRES_PASSWORD)"

[ -n "$DOMAIN" ] || gagal "DOMAIN kosong di $ENV_FILE."
case "$DOMAIN" in
  *example.com*|*localhost*) gagal "DOMAIN masih '$DOMAIN' (placeholder). Isi domain sungguhan." ;;
  *://*) gagal "DOMAIN tidak boleh memuat skema. Pakai 'demo.mealchain.id', bukan 'https://...'." ;;
esac

[ -n "$JWT_SECRET" ] || gagal "JWT_SECRET kosong. Buat: openssl rand -hex 32"
case "$JWT_SECRET" in
  GANTI*|changeme*|secret) gagal "JWT_SECRET masih placeholder. Buat: openssl rand -hex 32" ;;
esac
[ "${#JWT_SECRET}" -ge 32 ] || gagal "JWT_SECRET terlalu pendek (${#JWT_SECRET} karakter, minimum 32). Pakai: openssl rand -hex 32"

[ -n "$POSTGRES_PASSWORD" ] || gagal "POSTGRES_PASSWORD kosong. Buat: openssl rand -hex 24"
case "$POSTGRES_PASSWORD" in
  GANTI*|changeme*|postgres) gagal "POSTGRES_PASSWORD masih placeholder. Buat: openssl rand -hex 24" ;;
esac

echo "    DOMAIN=$DOMAIN  (JWT_SECRET ${#JWT_SECRET} karakter, sandi DB ${#POSTGRES_PASSWORD} karakter)"

# -----------------------------------------------------------------------------
# 4. Bangun & jalankan
# -----------------------------------------------------------------------------
langkah "Tarik image dasar"
# --ignore-buildable: postgres/caddy ditarik, backend/frontend dibangun lokal.
"${COMPOSE[@]}" pull --ignore-buildable

langkah "Bangun image backend, mock-sap, frontend"
# NEXT_PUBLIC_* masuk ke bundel klien saat build → perubahan .env pada variabel
# itu butuh build ulang, dan itulah yang dilakukan di sini.
"${COMPOSE[@]}" build

langkah "Nyalakan stack"
"${COMPOSE[@]}" up -d --remove-orphans

# -----------------------------------------------------------------------------
# 5. Tunggu backend sehat
# -----------------------------------------------------------------------------
langkah "Tunggu backend sehat (GET /health)"
tunggu=0
status="tidak-ada"
while [ "$tunggu" -lt 300 ]; do
  status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
    mealchain-vps-backend 2>/dev/null || echo 'tidak-ada')"
  case "$status" in
    healthy) break ;;
    exited|dead)
      "${COMPOSE[@]}" logs --tail 80 backend >&2 || true
      gagal "kontainer backend '$status'. Lihat log di atas."
      ;;
  esac
  sleep 5
  tunggu=$((tunggu + 5))
done
[ "$status" = "healthy" ] || {
  "${COMPOSE[@]}" logs --tail 80 backend >&2 || true
  gagal "backend tidak sehat setelah 300 detik (status: $status)."
}
echo "    backend healthy setelah ~${tunggu}s"

# -----------------------------------------------------------------------------
# 6. Skema + akun referensi (idempoten, selalu dijalankan)
# -----------------------------------------------------------------------------
# App TIDAK membuat tabel saat boot; skema datang dari Alembic. Tanpa langkah
# ini seed akan gagal pada VPS baru dengan "relation ... does not exist".
langkah "Migrasi skema (alembic upgrade head)"
"${COMPOSE[@]}" exec -T backend alembic upgrade head

# Akun (sppg.head@demo.local dkk) + lokasi/komoditas. demo_template memakai
# akun itu sebagai aktor; tanpa mereka seed demo berhenti.
langkah "Seed referensi (akun demo, lokasi, komoditas)"
"${COMPOSE[@]}" exec -T backend python -m app.seed.reference

# -----------------------------------------------------------------------------
# 7. Seed dataset demo — SEKALI, dijaga penanda
# -----------------------------------------------------------------------------
# Penanda sengaja disimpan di host (bukan di dalam DB): tujuan tunggalnya
# "jangan ulangi seed 70 detik setiap deploy", bukan catatan keadaan data.
# Untuk menyegarkan data antar sesi juri pakai reset-demo.sh.
if [ "$RESEED" -eq 1 ] || [ ! -f "$MARKER" ]; then
  langkah "Seed dataset demo (sekitar 60-90 detik)"
  if "${COMPOSE[@]}" exec -T backend python -m app.seed.demo_template; then
    date -u +"%Y-%m-%dT%H:%M:%SZ" > "$MARKER"
    echo "    penanda ditulis: $MARKER"
  else
    gagal "seed demo gagal. Stack tetap hidup; perbaiki penyebabnya lalu jalankan:
    bash $DIR/deploy.sh --reseed
  Log: docker compose -f $DIR/docker-compose.vps.yml --env-file $ENV_FILE logs backend"
  fi
else
  langkah "Seed demo dilewati (penanda ada: $(cat "$MARKER"))"
  echo "    Untuk menyemai ulang: bash $DIR/reset-demo.sh"
fi

# -----------------------------------------------------------------------------
# 8. Ringkasan
# -----------------------------------------------------------------------------
langkah "Status kontainer"
"${COMPOSE[@]}" ps

API_URL="https://api.$DOMAIN"
UI_URL="https://$DOMAIN"

cat <<EOF

=============================================================================
Selesai.

  UI    : $UI_URL
  API   : $API_URL/health

Akun demo (DEMO_MODE=$(nilai_env DEMO_MODE)):
  sppg.head@demo.local        / (lihat backend/app/seed/demo_credentials.py)
  sppg.nutritionist@demo.local
  bgn.monitor@demo.local

Verifikasi cepat:
  curl -fsS $API_URL/health
  curl -sI $UI_URL | head -n 5

Sertifikat Let's Encrypt butuh DNS sudah menunjuk ke VPS DAN port 80/443
terbuka. Bila UI belum bisa dibuka, cek:
  docker compose -f $DIR/docker-compose.vps.yml --env-file $ENV_FILE logs caddy

=============================================================================
EOF
