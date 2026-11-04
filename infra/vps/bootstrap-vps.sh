#!/usr/bin/env bash
# =============================================================================
# bootstrap-vps.sh — pasang MealChain Guardian sekali jalan di VPS Ubuntu
# =============================================================================
#
# Untuk: VPS Tencent Lighthouse, 2 vCPU / 2 GB RAM, Ubuntu 22/24, akses root.
# Domain memakai sslip.io (DNS publik otomatis menunjuk ke IP server).
#
# Pemakaian (di terminal VPS, sebagai root):
#   curl -fsSL https://raw.githubusercontent.com/munk23zzz/MealChain-Guardian/vps-deploy/infra/vps/bootstrap-vps.sh | sudo bash
#
# Yang dilakukan:
#   1. pasang Docker Engine + compose v2 (bila belum ada)
#   2. buat swap 2 GB (bila belum ada) supaya build tidak OOM
#   3. ambil kode cabang vps-deploy ke /opt/mealchain
#   4. buat infra/vps/.env dengan sandi DB + JWT acak (dibuat di server ini)
#   5. jalankan deploy.sh (compose up, migrasi, seed demo)
#
# Idempoten: aman diulang. .env yang sudah ada TIDAK ditimpa.
# =============================================================================
set -euo pipefail

REPO="${REPO:-https://github.com/munk23zzz/MealChain-Guardian.git}"
BRANCH="${BRANCH:-vps-deploy}"
APP_DIR="${APP_DIR:-/opt/mealchain}"
DOMAIN="${DOMAIN:-43-129-50-209.sslip.io}"
ACME_EMAIL="${ACME_EMAIL:-admin@${DOMAIN}}"

langkah() { printf '\n==> %s\n' "$*"; }
gagal()   { printf '\nGAGAL: %s\n' "$*" >&2; exit 1; }
info()    { printf '    %s\n' "$*"; }

[ "$(id -u)" -eq 0 ] || gagal "jalankan sebagai root: curl ... | sudo bash"

# -----------------------------------------------------------------------------
# 0. Dasar
# -----------------------------------------------------------------------------
langkah "Sistem"
info "$(sed -n 's/^PRETTY_NAME="\(.*\)"/\1/p' /etc/os-release)"
info "IP publik: $(curl -fsS -m 8 https://api.ipify.org || echo '?')"
ocpud="$(nproc)"; memmb="$(free -m | awk '/^Mem:/{print $2}')"
info "CPU ${ocpud} core, RAM ${memmb} MB"

# -----------------------------------------------------------------------------
# 1. Swap
# -----------------------------------------------------------------------------
if [ "$(free -m | awk '/^Swap:/{print $2}')" -lt 1024 ]; then
  langkah "Membuat swap 2 GB (build Next.js butuh memori lebih dari RAM fisik)"
  fallocate -l 2G /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=2048 status=none
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  info "swap aktif: $(free -m | awk '/^Swap:/{print $2" MB"}')"
else
  langkah "Swap sudah ada"
  info "$(free -m | awk '/^Swap:/{print $2" MB"}')"
fi

# -----------------------------------------------------------------------------
# 2. Docker
# -----------------------------------------------------------------------------
langkah "Docker"
if ! command -v docker >/dev/null 2>&1; then
  info "memasang Docker Engine + compose plugin"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq ca-certificates curl gnupg git >/dev/null
  curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
  sh /tmp/get-docker.sh >/tmp/docker-install.log 2>&1 || {
    tail -20 /tmp/docker-install.log >&2
    gagal "pemasangan Docker gagal (lihat /tmp/docker-install.log)"
  }
  systemctl enable --now docker >/dev/null 2>&1 || true
else
  info "docker sudah terpasang: $(docker --version)"
fi
docker compose version >/dev/null 2>&1 || gagal "docker compose v2 tidak tersedia"
info "$(docker compose version)"

# -----------------------------------------------------------------------------
# 3. Kode
# -----------------------------------------------------------------------------
langkah "Kode aplikasi ($BRANCH)"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch --depth 1 origin "$BRANCH" -q
  git -C "$APP_DIR" checkout -q -B "$BRANCH" FETCH_HEAD
  info "diperbarui: $(git -C "$APP_DIR" log --oneline -1)"
else
  mkdir -p "$(dirname "$APP_DIR")"
  git clone --depth 1 -b "$BRANCH" "$REPO" "$APP_DIR" -q
  info "dikloning: $(git -C "$APP_DIR" log --oneline -1)"
fi

# -----------------------------------------------------------------------------
# 4. .env
# -----------------------------------------------------------------------------
ENV_FILE="$APP_DIR/infra/vps/.env"
if [ -f "$ENV_FILE" ]; then
  langkah ".env sudah ada — tidak ditimpa"
  info "$ENV_FILE"
else
  langkah "Membuat .env (sandi dan kunci dibuat acak di server ini)"
  PW="$(openssl rand -hex 24)"
  JWT="$(openssl rand -hex 32)"
  cp "$APP_DIR/infra/vps/.env.vps.example" "$ENV_FILE"
  sed -i \
    -e "s|^DOMAIN=.*|DOMAIN=${DOMAIN}|" \
    -e "s|^ACME_EMAIL=.*|ACME_EMAIL=${ACME_EMAIL}|" \
    -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${PW}|" \
    -e "s|^DATABASE_URL=.*|DATABASE_URL=postgresql+asyncpg://mealchain:${PW}@postgres:5432/mealchain|" \
    -e "s|^JWT_SECRET=.*|JWT_SECRET=${JWT}|" \
    "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  info "$ENV_FILE (chmod 600)"
fi

# -----------------------------------------------------------------------------
# 5. Deploy
# -----------------------------------------------------------------------------
langkah "Menjalankan deploy.sh (build bisa 5–10 menit pada 2 vCPU)"
cd "$APP_DIR"
bash infra/vps/deploy.sh

# -----------------------------------------------------------------------------
# 6. Ringkasan
# -----------------------------------------------------------------------------
IP="$(curl -fsS -m 8 https://api.ipify.org || echo '<IP-VPS>')"
DOMAIN_SEBENAR="$(grep -E '^DOMAIN=' "$ENV_FILE" | tail -1 | cut -d= -f2-)"
langkah "Selesai"
info "UI  : https://${DOMAIN_SEBENAR}"
info "API : https://api.${DOMAIN_SEBENAR}"
info "Uji : curl -fsS https://api.${DOMAIN_SEBENAR}/health"
info ""
info "Akun demo (sandi: lihat infra/vps/README.md):"
info "  sppg.head@demo.local · sppg.nutritionist@demo.local · bgn.monitor@demo.local"
info ""
info "Reset data antar-juri : sudo bash ${APP_DIR}/infra/vps/reset-demo.sh"
info "Log                  : cd ${APP_DIR} && docker compose -f infra/vps/docker-compose.vps.yml logs -f backend"
info "IP publik saat ini    : ${IP}"
