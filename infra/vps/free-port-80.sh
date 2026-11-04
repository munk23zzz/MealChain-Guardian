#!/usr/bin/env bash
# =============================================================================
# free-port-80.sh — hentikan apa pun yang memegang :80/:443, lalu laporkan
# =============================================================================
#
# Kenapa ada skrip ini: di VPS demo, Caddy lama berjalan dengan `--network host`.
# Kontainer seperti itu TIDAK menampilkan pemetaan port di `docker ps`, sehingga
# pemeriksaan berbasis `docker ps --format {{.Ports}}` menganggap port bebas.
# Akibatnya stack baru gagal bind dan pengunjung tetap dilayani Caddy lama yang
# membalas 308 ke https — padahal 443 ditutup firewall, jadi halaman tampak
# "tidak muncul".
#
# Pemakaian:
#   curl -fsSL https://raw.githubusercontent.com/munk23zzz/MealChain-Guardian/vps-deploy/infra/vps/free-port-80.sh | sudo bash
#
# Aman diulang: kontainer milik stack ini (mealchain-vps-*) dilewati.
# =============================================================================
set -uo pipefail

langkah() { printf '\n==> %s\n' "$*"; }
info()    { printf '    %s\n' "$*"; }

[ "$(id -u)" -eq 0 ] || { echo "jalankan sebagai root" >&2; exit 1; }

# PID yang mendengarkan :80 atau :443 (TCP)
pemegang() {
  { ss -ltnpH 'sport = :80' 2>/dev/null; ss -ltnpH 'sport = :443' 2>/dev/null; } \
    | grep -o 'pid=[0-9]*' | cut -d= -f2 | sort -u
}

langkah "Sebelum: pendengar :80/:443"
ss -ltnpH 'sport = :80 or sport = :443' 2>/dev/null | sed 's/^/    /' || true

langkah "Membebaskan port"
for pid in $(pemegang); do
  [ -r "/proc/$pid/cgroup" ] || continue
  cid="$(grep -oE '[0-9a-f]{64}' "/proc/$pid/cgroup" | head -1)"
  [ -n "$cid" ] || cid="$(grep -oE 'docker-[0-9a-f]{12,}' "/proc/$pid/cgroup" | head -1 | sed 's/^docker-//')"
  if [ -n "$cid" ] && command -v docker >/dev/null 2>&1; then
    cname="$(docker inspect -f '{{.Name}}' "$cid" 2>/dev/null || echo '')"
    case "$cname" in
      *mealchain-vps*)
        info "dilewati: $cname (milik stack ini)"
        ;;
      "")
        info "kill PID $pid (bukan kontainer yang dikenal)"
        kill "$pid" 2>/dev/null || true; sleep 1; kill -9 "$pid" 2>/dev/null || true
        ;;
      *)
        info "docker stop $cname; restart=no"
        docker stop "$cid" >/dev/null 2>&1 || true
        docker update --restart=no "$cid" >/dev/null 2>&1 || true
        ;;
    esac
  else
    info "kill PID $pid ($(ps -o comm= -p "$pid" 2>/dev/null || echo proses))"
    kill "$pid" 2>/dev/null || true; sleep 1; kill -9 "$pid" 2>/dev/null || true
  fi
done

for svc in caddy nginx apache2 httpd; do
  if systemctl is-active --quiet "$svc" 2>/dev/null; then
    info "systemctl stop $svc"
    systemctl stop "$svc" || true
    systemctl disable "$svc" >/dev/null 2>&1 || true
  fi
done

sleep 2
langkah "Sesudah: pendengar :80/:443"
if ss -ltnpH 'sport = :80 or sport = :443' 2>/dev/null | grep -q .; then
  ss -ltnpH 'sport = :80 or sport = :443' 2>/dev/null | sed 's/^/    /'
  info "MASIH ADA pemegang port (lihat baris di atas)"
else
  info "port 80/443 bebas"
fi

langkah "Status stack MealChain"
if command -v docker >/dev/null 2>&1; then
  docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null \
    | awk 'NR==1 || /mealchain/' | sed 's/^/    /'
  info ""
  info "Uji lokal: curl -s -o /dev/null -w '%{http_code}\\n' http://127.0.0.1/api/health"
  info "Kalau bukan 200, lihat log: docker logs --tail=60 mealchain-vps-caddy"
fi
