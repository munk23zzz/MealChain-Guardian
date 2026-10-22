#!/usr/bin/env bash
# Perbaiki jembatan Joule: tunel baru -> set-env -> restage -> verifikasi.
#
# Gejala yang diperbaiki: chat Joule menjawab
#   "backend MealChain tidak bisa dihubungi (https://<lama>.trycloudflare.com) …
#    Name or service not known"
# Itu berarti URL backend di aplikasi Cloud Foundry menunjuk tunel quick Cloudflare
# yang sudah mati, BUKAN destination atau DA yang salah.
#
# Pakai: bash scripts/joule-perbaiki.sh          (sekaligus menangani login SSO)
#        bash scripts/joule-perbaiki-tunnel.sh   (kalau sesi cf sudah aktif)
set -uo pipefail

APP=${APP:-mealchain-joule-bridge-4sehat3trio}
BACKEND_LOCAL=${BACKEND_LOCAL:-http://localhost:8000}
CF_API=${CF_API:-https://api.cf.ap10.hana.ondemand.com}
LOG=${LOG:-$LOCALAPPDATA/Temp/joule-tunnel.log}
CLOUDFLARED=${CLOUDFLARED:-"C:/Program Files (x86)/cloudflared/cloudflared.exe"}

# Kode HTTP tanpa CR/LF. Jangan memakai status keluar curl: di Windows/MSYS
# `curl -o /dev/null` kadang keluar 23 (gagal menulis body) walau server balas 200,
# sehingga penjaga `||` memutus alur padahal backend sehat.
kode_http() { curl -s --max-time "${2:-15}" -o /dev/null -w "%{http_code}" "$1" | tr -d '\r\n'; }

echo "== [1/6] backend lokal =="
KODE=$(kode_http "$BACKEND_LOCAL/health" 10)
echo "  localhost:8000/health -> $KODE"
if [ "$KODE" != "200" ]; then
  echo "backend lokal tidak menjawab ($KODE). Nyalakan dulu: docker compose up -d backend"
  exit 1
fi

echo "== [2/6] sesi Cloud Foundry =="
if ! cf apps >/dev/null 2>&1; then
  echo "Sesi cf tidak aktif. Jalankan dulu: cf login -a $CF_API --sso"
  exit 2
fi
cf target | sed -n '1,5p'

echo "== [3/6] tunel =="
URL=$(grep -ohE "https://[a-z0-9-]+\.trycloudflare\.com" "$LOG" 2>/dev/null | tail -1 || true)
SEHAT=""
[ -n "${URL:-}" ] && SEHAT=$(kode_http "$URL/health" 15)
if [ "$SEHAT" != "200" ]; then
  echo "  menyalakan tunel baru…"
  "$CLOUDFLARED" tunnel --url "$BACKEND_LOCAL" --no-autoupdate > "$LOG" 2>&1 &
  for _ in $(seq 1 20); do
    sleep 3
    URL=$(grep -ohE "https://[a-z0-9-]+\.trycloudflare\.com" "$LOG" 2>/dev/null | tail -1 || true)
    [ -n "${URL:-}" ] || continue
    [ "$(kode_http "$URL/health" 10)" = "200" ] && break
  done
fi
[ -n "${URL:-}" ] || { echo "tunel gagal: tidak ada URL (lihat $LOG)"; exit 3; }
echo "  URL backend: $URL"

echo "== [4/6] uji dari internet =="
echo "  /health       -> $(kode_http "$URL/health" 20)"
echo "  /openapi.json -> $(kode_http "$URL/openapi.json" 20)"

echo "== [5/6] arahkan aplikasi CF ke URL ini =="
cf set-env "$APP" MEALCHAIN_API_URL "$URL" >/dev/null 2>&1
echo "  set-env selesai; restage…"
cf restage "$APP" 2>&1 | tail -3

echo "== [6/6] verifikasi lewat route CF =="
APP_URL="https://${APP}.cfapps.ap10.hana.ondemand.com"
BODY=""
for _ in $(seq 1 25); do
  BODY=$(curl -s --max-time 20 "$APP_URL/health" || true)
  echo "$BODY" | grep -q '"reachable":true' && break
  sleep 6
done
echo "  $BODY"
echo "$BODY" | grep -q '"reachable":true' || { echo "GAGAL: /health belum reachable"; exit 5; }

echo
echo "OK. Uji jalur nyata (JSON-RPC seperti yang dipanggil Joule):"
echo "  curl -s -X POST $APP_URL/ -H 'Content-Type: application/json' \\"
echo "    -d '{\"jsonrpc\":\"2.0\",\"id\":\"1\",\"method\":\"message/send\",\"params\":{\"message\":{\"role\":\"user\",\"kind\":\"message\",\"messageId\":\"1\",\"parts\":[{\"kind\":\"text\",\"text\":\"bagaimana kondisi pasokan?\"}]}}}'"
