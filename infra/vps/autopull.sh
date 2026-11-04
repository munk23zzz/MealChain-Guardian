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
#   * setiap perintah jaringan/build diberi batas waktu, supaya proses yang
#     menggantung tidak memegang flock dan membekukan SEMUA autopull berikutnya
#   * image terakhir yang terbukti sehat disimpan sebagai tag `autopull-prev`
#     (titik balik satu perintah bila commit baru bikin layanan rusak)
#   * semua aksi dicatat ke /var/log/mealchain-autopull.log (0600, root saja —
#     keluarannya memuat perintah build, URL remote, dan nama variabel)
#
# BATAS KEAMANAN YANG HARUS DISADARI: skrip ini menjalankan KODE DARI CABANG
# `vps-deploy` SEBAGAI ROOT. Siapa pun yang bisa push ke cabang itu (akun
# GitHub yang di-compromise, kolaborator, atau token yang bocor) dapat
# menjalankan perintah apa pun di host ini lewat `Dockerfile`/`docker-compose`
# di commit tersebut. Tidak ada verifikasi tanda tangan commit di sini. Karena
# itu: cabang `vps-deploy` WAJIB dilindungi branch protection (wajib PR +
# review) dan kredensial push-nya jangan pernah ada di VPS ini. Rincian dan
# mitigasinya: `infra/vps/SECURITY.md` §6.
#
# Pasang:
#   sudo bash infra/vps/autopull.sh --pasang
# Hentikan:
#   sudo rm -f /opt/mealchain/.autopull-enabled
# =============================================================================
set -uo pipefail

# Berkas yang dibuat skrip ini (log, status) hanya untuk root: keluaran build
# bisa memuat URL remote dan nama variabel lingkungan.
umask 077

APP_DIR="${APP_DIR:-/opt/mealchain}"
BRANCH="${BRANCH:-vps-deploy}"
ENV_FILE="$APP_DIR/infra/vps/.env"
COMPOSE=(docker compose -f "$APP_DIR/infra/vps/docker-compose.vps.yml" --env-file "$ENV_FILE")
LOG="/var/log/mealchain-autopull.log"
PENANDA="$APP_DIR/.autopull-enabled"
KUNCI="/var/lock/mealchain-autopull.lock"
STATUS="$APP_DIR/.autopull-status"

# Batas waktu per tahap. Tanpa ini, `git fetch`/`docker build` yang menggantung
# memegang flock selamanya: setiap timer berikutnya langsung `exit 0` dan
# autopull berhenti bekerja tanpa satu pun pesan galat.
BATAS_FETCH="${BATAS_FETCH:-120}"
BATAS_BUILD="${BATAS_BUILD:-1800}"
BATAS_UP="${BATAS_UP:-300}"
BATAS_MIGRASI="${BATAS_MIGRASI:-180}"

# Siapkan log dengan izin 0600 (umask di atas hanya berlaku untuk berkas baru;
# log lama dari versi sebelumnya mungkin masih 0644).
: >>"$LOG" 2>/dev/null || true
chmod 600 "$LOG" 2>/dev/null || true

terbatas() {
  local detik="$1"
  shift
  if command -v timeout >/dev/null 2>&1; then
    timeout "$detik" "$@"
  else
    "$@"
  fi
}

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
# Batas keras systemd: `timeout` di dalam skrip sudah membatasi tiap tahap,
# ini jaring terakhir supaya unit tidak menggantung selamanya.
TimeoutStartSec=2400
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
if ! terbatas "$BATAS_FETCH" git fetch --depth 1 origin "$BRANCH" -q 2>>"$LOG"; then
  catat "GAGAL fetch $BRANCH (kode $?)"
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
# Bila `git diff` gagal (mis. riwayat shallow terpotong), JANGAN diam-diam
# melewatkan build: dulu fallback-nya string "semua" yang tidak cocok dengan
# grep mana pun, sehingga skrip mencatat commit baru tanpa membangun apa pun.
if ! BERUBAH="$(git diff --name-only "$SEBELUM" "$SESUDAH" 2>/dev/null)"; then
  catat "PERINGATAN diff $SEBELUM..$SESUDAH gagal — semua layanan dibangun ulang"
  # Satu path per baris: pola di bawah berjangkar `^`, jadi daftar satu baris
  # ("backend/ frontend/ ...") hanya akan cocok dengan pola pertama.
  BERUBAH="$(printf '%s\n' 'backend/.semua' 'frontend/.semua' 'infra/vps/Caddyfile')"
fi
LAYANAN=()
grep -qE '^(backend/|agent/|infra/vps/backend\.Dockerfile)' <<<"$BERUBAH" && LAYANAN+=(backend)
grep -qE '^(frontend/)' <<<"$BERUBAH" && LAYANAN+=(frontend)
grep -qE '^(infra/vps/Caddyfile)' <<<"$BERUBAH" && LAYANAN+=(caddy)

# Titik balik: simpan image yang SEDANG berjalan sebagai `autopull-prev` sebelum
# `build` menimpa tag `:latest`. Tanpa ini tidak ada image lama yang bisa
# dihidupkan kembali ketika commit baru lolos build tetapi merusak layanan.
for img in backend frontend; do
  docker tag "mealchain-vps-$img:latest" "mealchain-vps-$img:autopull-prev" 2>/dev/null || true
done

if [ "${#LAYANAN[@]}" -gt 0 ]; then
  catat "build: ${LAYANAN[*]}"
  if ! terbatas "$BATAS_BUILD" "${COMPOSE[@]}" build "${LAYANAN[@]}" >>"$LOG" 2>&1; then
    catat "GAGAL build ${LAYANAN[*]} — commit ${SESUDAH:0:7} tidak diterapkan"
    echo "gagal-build ${SESUDAH:0:7}" >"$STATUS"
    exit 0
  fi
  if ! terbatas "$BATAS_UP" "${COMPOSE[@]}" up -d --no-deps "${LAYANAN[@]}" >>"$LOG" 2>&1; then
    catat "GAGAL up ${LAYANAN[*]}"
    echo "gagal-up ${SESUDAH:0:7}" >"$STATUS"
    exit 0
  fi
fi

# Migrasi skema WAJIB dijalankan setelah backend baru hidup: commit yang
# menambah migrasi akan membuat endpoint 500 di tengah demo sementara /health
# tetap 200 (temuan T-2 audit keamanan). deploy.sh sudah melakukannya; autopull
# dulu tidak, jadi jalur otomatis ini bisa diam-diam melewatkan skema.
if [[ " ${LAYANAN[*]:-} " == *" backend "* ]]; then
  if terbatas "$BATAS_MIGRASI" "${COMPOSE[@]}" exec -T backend alembic upgrade head >>"$LOG" 2>&1; then
    catat "migrasi alembic: ok"
  else
    catat "PERINGATAN ${SESUDAH:0:7} — alembic upgrade head gagal; skema mungkin tertinggal"
    echo "migrasi-gagal ${SESUDAH:0:7}" >"$STATUS"
  fi
fi

# Tunggu backend sehat (maks 120 detik).
for _ in $(seq 1 24); do
  KODE="$(curl -s -o /dev/null -w '%{http_code}' -m 5 http://127.0.0.1/api/health || echo 000)"
  [ "$KODE" = "200" ] && break
  sleep 5
done

# Commit yang hanya menyentuh Caddyfile/frontend tidak akan pernah terlihat
# lewat /api/health: Caddy rusak = seluruh UI mati, backend tetap 200. Karena
# itu rute UI diuji juga — tetapi hanya bila caddy/frontend memang dibangun
# ulang, supaya probe ini tidak memutus deploy backend saat Caddy sedang mati
# karena sebab lain.
KODE_UI="-"
if [[ " ${LAYANAN[*]:-} " == *" caddy "* || " ${LAYANAN[*]:-} " == *" frontend "* ]]; then
  for _ in $(seq 1 12); do
    KODE_UI="$(curl -s -o /dev/null -w '%{http_code}' -m 5 http://127.0.0.1/ || echo 000)"
    [ "$KODE_UI" = "200" ] && break
    sleep 5
  done
fi

if [ "$KODE" = "200" ] && [ "$KODE_UI" != "000" ] && [ "$KODE_UI" != "500" ]; then
  catat "OK ${SESUDAH:0:7} — health 200, UI $KODE_UI (layanan: ${LAYANAN[*]:-tidak ada})"
  echo "ok ${SESUDAH:0:7}" >"$STATUS"
else
  catat "PERINGATAN ${SESUDAH:0:7} — health $KODE, UI $KODE_UI"
  catat "  balik ke image sebelumnya (bila perlu): docker tag mealchain-vps-backend:autopull-prev mealchain-vps-backend:latest && docker compose -f $APP_DIR/infra/vps/docker-compose.vps.yml --env-file $ENV_FILE up -d --no-deps backend"
  catat "  catatan: migrasi skema TIDAK dijalankan skrip ini — commit yang menambah migrasi butuh 'bash $APP_DIR/infra/vps/deploy.sh'"
  echo "health-$KODE ${SESUDAH:0:7}" >"$STATUS"
fi
