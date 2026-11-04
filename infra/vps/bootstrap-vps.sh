#!/usr/bin/env bash
# =============================================================================
# bootstrap-vps.sh — pasang MealChain Guardian sekali jalan di VPS Ubuntu
# =============================================================================
#
# Untuk: VPS Tencent Lighthouse, 2 vCPU / 2 GB RAM, Ubuntu 22/24, akses root.
# Domain memakai sslip.io (DNS publik otomatis menunjuk ke IP server).
# Mode bawaan: SATU PORT (80/TCP) — UI di /, API di /api, tanpa TLS, karena
# firewall VPS ini menutup 443. Lihat Caddyfile.http.
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
PUBLIC_SCHEME="${PUBLIC_SCHEME:-http}"

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
# 1. Bebaskan port 80/443 dari layanan lain (disetujui pemilik VPS)
# -----------------------------------------------------------------------------
langkah "Memeriksa pemakai port 80/443"
for svc in caddy nginx apache2 httpd; do
  if systemctl is-active --quiet "$svc" 2>/dev/null; then
    info "menghentikan systemd: $svc"
    systemctl stop "$svc" || true
    systemctl disable "$svc" >/dev/null 2>&1 || true
  fi
done

# Pemegang port dideteksi lewat ss, bukan lewat `docker ps --format {{.Ports}}`:
# kontainer dengan `--network host` (pola umum Caddy) TIDAK menampilkan pemetaan
# port sama sekali, sehingga cara lama melewatkannya (terukur 4 Nov 2026: Caddy
# lama tetap menjawab 308 di :80 dan kontainer kita gagal bind).
pemegang_port() {
  { ss -ltnpH 'sport = :80' 2>/dev/null; ss -ltnpH 'sport = :443' 2>/dev/null; } \
    | grep -o 'pid=[0-9]*' | cut -d= -f2 | sort -u
}
for pid in $(pemegang_port); do
  [ -r "/proc/$pid/cgroup" ] || continue
  cid="$(grep -oE '[0-9a-f]{64}' "/proc/$pid/cgroup" | head -1)"
  if [ -z "$cid" ]; then
    cid="$(grep -oE 'docker-[0-9a-f]{12,}' "/proc/$pid/cgroup" | head -1 | sed 's/^docker-//')"
  fi
  if [ -n "$cid" ] && command -v docker >/dev/null 2>&1; then
    cname="$(docker inspect -f '{{.Name}}' "$cid" 2>/dev/null || echo '')"
    case "$cname" in
      *mealchain-vps*)
        info "port dipegang kontainer kita sendiri ($cname) — dilewati"
        ;;
      "")
        info "menghentikan PID $pid (pemegang port, bukan kontainer yang dikenal)"
        kill "$pid" 2>/dev/null || true
        ;;
      *)
        info "menghentikan kontainer lama $cname (memegang 80/443)"
        docker stop "$cid" >/dev/null 2>&1 || true
        docker update --restart=no "$cid" >/dev/null 2>&1 || true
        ;;
    esac
  else
    info "menghentikan PID $pid ($(ps -o comm= -p "$pid" 2>/dev/null || echo proses)) di 80/443"
    kill "$pid" 2>/dev/null || true
    sleep 1
    kill -9 "$pid" 2>/dev/null || true
  fi
done
sleep 1
if [ -n "$(pemegang_port)" ]; then
  info "PERINGATAN: port 80/443 masih dipegang PID: $(pemegang_port | tr '\n' ' ')"
else
  info "port 80/443 bebas"
fi

# -----------------------------------------------------------------------------
# 2. Swap
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
export DEBIAN_FRONTEND=noninteractive
if ! command -v git >/dev/null 2>&1 || ! command -v openssl >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y -qq git openssl ca-certificates curl >/dev/null
  info "git/openssl terpasang"
fi
if ! command -v docker >/dev/null 2>&1; then
  info "memasang Docker Engine + compose plugin"
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
systemctl start docker >/dev/null 2>&1 || true
docker info >/dev/null 2>&1 || gagal "daemon docker tidak berjalan"
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
    -e "s|^CORS_ORIGINS=.*|CORS_ORIGINS=${PUBLIC_SCHEME}://${DOMAIN}|" \
    -e "s|^NEXT_PUBLIC_API_URL=.*|NEXT_PUBLIC_API_URL=/api|" \
    "$ENV_FILE"
  {
    echo ""
    echo "# --- mode satu port (443 tertutup firewall; lihat Caddyfile.http) ---"
    echo "CADDY_CONFIG=Caddyfile.http"
  } >> "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  info "$ENV_FILE (chmod 600, CADDY_CONFIG=Caddyfile.http, NEXT_PUBLIC_API_URL=/api)"
fi

# -----------------------------------------------------------------------------
# 5. Deploy
# -----------------------------------------------------------------------------
langkah "Menjalankan deploy.sh (build bisa 5–10 menit pada 2 vCPU)"
cd "$APP_DIR"
bash infra/vps/deploy.sh

# -----------------------------------------------------------------------------
# 6. Uji dari dalam server
# -----------------------------------------------------------------------------
D="$(grep -E '^DOMAIN=' "$ENV_FILE" | tail -1 | cut -d= -f2-)"
langkah "Uji dari dalam server"
code="$(curl -s -o /dev/null -w '%{http_code}' -m 10 "http://127.0.0.1/api/health" || echo 000)"
info "GET http://127.0.0.1/api/health -> ${code}"
if [ "$code" != "200" ]; then
  info "PERINGATAN: belum 200. Periksa: cd ${APP_DIR} && docker compose -f infra/vps/docker-compose.vps.yml logs --tail=80 backend"
fi

# -----------------------------------------------------------------------------
# 7. Ringkasan
# -----------------------------------------------------------------------------
langkah "Selesai"
info "UI  : ${PUBLIC_SCHEME}://${D}/"
info "API : ${PUBLIC_SCHEME}://${D}/api/health"
info ""
info "Akun demo (sandi: lihat infra/vps/README.md):"
info "  sppg.head@demo.local · sppg.nutritionist@demo.local · bgn.monitor@demo.local"
info ""
info "Reset data antar-juri : sudo bash ${APP_DIR}/infra/vps/reset-demo.sh"
info "Log                  : cd ${APP_DIR} && docker compose -f infra/vps/docker-compose.vps.yml logs -f backend"
info "Bila 443 kelak dibuka: ubah CADDY_CONFIG=Caddyfile di ${ENV_FILE}, lalu bash ${APP_DIR}/infra/vps/deploy.sh"
