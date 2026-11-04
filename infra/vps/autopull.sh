#!/usr/bin/env bash
# =============================================================================
# autopull.sh — terapkan perubahan cabang vps-deploy secara otomatis (aman)
# =============================================================================
#
# Dipakai di VPS demo supaya perbaikan bisa diterapkan tanpa membuka SSH:
# skrip ini dipanggil systemd timer tiap beberapa menit, menarik commit baru
# dari cabang `vps-deploy`, membangun ulang layanan yang berubah, menyalakan
# ulang, lalu MENGUJI /health. Bila health gagal, skrip mencatatnya dan tidak
# mengulang build terus-menerus (menunggu commit berikutnya).
#
# Kunci pengaman:
#   * hanya jalan bila ada penanda /opt/mealchain/.autopull-enabled
#   * hanya cabang vps-deploy, hanya repo yang sudah ada di /opt/mealchain
#   * satu kunci (flock) supaya tidak ada dua proses build bersamaan
#   * tidak pernah menulis .env, tidak menyentuh database di luar build/up
#   * semua aksi dicatat ke /var/log/mealchain-autopull.log
#
# Pasang:
#   sudo bash infra/vps/autopull.sh --pasang
# Hentikan:
#   sudo rm -f /opt/mealchain/.autopull-enabled
# =============================================================================
set -uo pipefail

APP_DIR="${APP_DIR:-/opt/mealchain}"
BRANCH="${BRANCH:-vps-deploy}"
ENV_FILE="$APP_DIR/infra/vps/.env"
COMPOSE=(docker compose -f "$APP_DIR/infra/vps/docker-compose.vps.yml" --env-file "$ENV_FILE")
LOG="/var/log/mealchain-autopull.log"
PENANDA="$APP_DIR/.autopull-enabled"
KUNCI="/var/lock/mealchain-autopull.lock"
STATUS="$APP_DIR/.autopull-status"

catat() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG"; }

pasang() {
  [ "$(id -u)" -eq 0 ] || { echo "jalankan sebagai root" >&2; exit 1; }
  install -m 0755 "$(realpath "$0")" /usr/local/bin/mealchain-autopull
  cat >/etc/systemd/system/mealchain-autopull.service <<'UNIT'
[Unit]
Description=MealChain Guardian — tarik & terapkan commit vps-deploy
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/mealchain-autopull --jalan
UNIT
  cat >/etc/systemd/system/mealchain-autopull.timer <<'UNIT'
[Unit]
Description=MealChain Guardian — autopull tiap 3 menit

[Timer]
OnBootSec=2min
OnUnitActiveSec=3min
AccuracySec=30s
Unit=mealchain-autopull.service

[Install]
WantedBy=timers.target
UNIT
  touch "$PENANDA"
  systemctl daemon-reload
  systemctl enable --now mealchain-autopull.timer >/dev/null 2>&1
  echo "autopull aktif. Cek: journalctl -u mealchain-autopull -n 20 --no-pager"
  echo "Log berkas: $LOG"
  echo "Matikan: sudo rm -f $PENANDA"
  exit 0
}

[ "${1:-}" = "--pasang" ] && pasang

# --- satu proses saja ------------------------------------------------------
exec 9>"$KUNCI" || exit 0
flock -n 9 || exit 0

[ -f "$PENANDA" ] || exit 0
[ -d "$APP_DIR/.git" ] || { catat "LEWATI: $APP_DIR bukan repo git"; exit 0; }
[ -f "$ENV_FILE" ] || { catat "LEWATI: $ENV_FILE tidak ada"; exit 0; }

cd "$APP_DIR" || exit 0

SEBELUM="$(git rev-parse HEAD 2>/dev/null || echo '')"
if ! git fetch --depth 1 origin "$BRANCH" -q 2>>"$LOG"; then
  catat "GAGAL fetch $BRANCH"
  exit 0
fi
SESUDAH="$(git rev-parse FETCH_HEAD 2>/dev/null || echo '')"

if [ -z "$SESUDAH" ] || [ "$SEBELUM" = "$SESUDAH" ]; then
  exit 0
fi

catat "commit baru ${SESUDAH:0:7} (dari ${SEBELUM:0:7})"

if ! git checkout -q -B "$BRANCH" FETCH_HEAD 2>>"$LOG"; then
  catat "GAGAL checkout ${SESUDAH:0:7}"
  exit 0
fi

# Bangun ulang hanya bila berkas yang memengaruhi image berubah.
BERUBAH="$(git diff --name-only "$SEBELUM" "$SESUDAH" 2>/dev/null || echo 'semua')"
LAYANAN=()
grep -qE '^(backend/|agent/|infra/vps/backend\.Dockerfile)' <<<"$BERUBAH" && LAYANAN+=(backend)
grep -qE '^(frontend/)' <<<"$BERUBAH" && LAYANAN+=(frontend)
grep -qE '^(infra/vps/Caddyfile)' <<<"$BERUBAH" && LAYANAN+=(caddy)

if [ "${#LAYANAN[@]}" -gt 0 ]; then
  catat "build: ${LAYANAN[*]}"
  if ! "${COMPOSE[@]}" build "${LAYANAN[@]}" >>"$LOG" 2>&1; then
    catat "GAGAL build ${LAYANAN[*]} — commit ${SESUDAH:0:7} tidak diterapkan"
    echo "gagal-build ${SESUDAH:0:7}" >"$STATUS"
    exit 0
  fi
  if ! "${COMPOSE[@]}" up -d --no-deps "${LAYANAN[@]}" >>"$LOG" 2>&1; then
    catat "GAGAL up ${LAYANAN[*]}"
    echo "gagal-up ${SESUDAH:0:7}" >"$STATUS"
    exit 0
  fi
fi

# Tunggu backend sehat (maks 120 detik).
for _ in $(seq 1 24); do
  KODE="$(curl -s -o /dev/null -w '%{http_code}' -m 5 http://127.0.0.1/api/health || echo 000)"
  [ "$KODE" = "200" ] && break
  sleep 5
done

if [ "$KODE" = "200" ]; then
  catat "OK ${SESUDAH:0:7} — health 200 (layanan: ${LAYANAN[*]:-tidak ada})"
  echo "ok ${SESUDAH:0:7}" >"$STATUS"
else
  catat "PERINGATAN ${SESUDAH:0:7} — health $KODE"
  echo "health-$KODE ${SESUDAH:0:7}" >"$STATUS"
fi
