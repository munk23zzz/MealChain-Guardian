#!/usr/bin/env bash
# Perbaiki jembatan Joule: tunel baru -> set-env -> restage -> verifikasi.
#
# Gejala yang diperbaiki: chat Joule menjawab
#   "backend MealChain tidak bisa dihubungi (https://<lama>.trycloudflare.com) …
#    Name or service not known"
# Itu artinya URL backend di aplikasi Cloud Foundry menunjuk tunel quick Cloudflare
# yang sudah mati, BUKAN destination atau DA yang salah.
#
# Pakai: bash scripts/joule-perbaiki-tunnel.sh
# Syarat: sudah `cf login -a https://api.cf.ap10.hana.ondemand.com --sso`
#         (login SSO tidak bisa diotomasi — butuh browser + kode sekali pakai).
set -uo pipefail

APP=${APP:-mealchain-joule-bridge-4sehat3trio}
BACKEND_LOCAL=${BACKEND_LOCAL:-http://localhost:8000}
CF_API=${CF_API:-https://api.cf.ap10.hana.ondemand.com}
LOG=${LOG:-$LOCALAPPDATA/Temp/joule-tunnel.log}
CLOUDFLARED=${CLOUDFLARED:-"C:/Program Files (x86)/cloudflared/cloudflared.exe"}

echo "== [1/6] backend lokal =="
curl -s --max-time 10 -o /dev/null -w "localhost:8000/health -> %{http_code}\n" "$BACKEND_LOCAL/health" || {
  echo "backend lokal tidak menjawab. Nyalakan dulu (docker compose up -d backend)."; exit 1; }

echo "== [2/6] sesi Cloud Foundry =="
if ! cf target >/dev/null 2>&1 || ! cf apps >/dev/null 2>&1; then
  echo "Sesi cf kedaluwarsa. Jalankan dulu:"
  echo "  cf login -a $CF_API --sso"
  exit 2
fi
cf target | sed -n '1,5p'

echo "== [3/6] tunel =="
URL=$(grep -ohE "https://[a-z0-9-]+\.trycloudflare\.com" "$LOG" 2>/dev/null | tail -1 || true)
if [ -z "${URL:-}" ] || ! curl -s --max-time 15 -o /dev/null "${URL}/health"; then
  echo "menyalakan tunel baru…"
  "$CLOUDFLARED" tunnel --url "$BACKEND_LOCAL" --no-autoupdate > "$LOG" 2>&1 &
  for i in $(seq 1 20); do
    sleep 3
    URL=$(grep -ohE "https://[a-z0-9-]+\.trycloudflare\.com" "$LOG" 2>/dev/null | tail -1 || true)
    [ -n "${URL:-}" ] && curl -s --max-time 10 -o /dev/null "${URL}/health" && break
  done
fi
[ -n "${URL:-}" ] || { echo "tunel gagal: tidak ada URL. Lihat $LOG"; exit 3; }
echo "URL backend: $URL"

echo "== [4/6] uji dari internet =="
curl -s --max-time 20 -o /dev/null -w "  /health     -> %{http_code}\n" "$URL/health"
curl -s --max-time 20 -o /dev/null -w "  /openapi.json -> %{http_code}\n" "$URL/openapi.json"

echo "== [5/6] arahkan aplikasi CF ke URL ini =="
cf set-env "$APP" MEALCHAIN_API_URL "$URL"
cf restage "$APP" | tail -5

echo "== [6/6] verifikasi lewat route CF =="
APP_URL=$(cf app "$APP" 2>/dev/null | grep -oE "https://[a-z0-9.-]*cfapps[a-z0-9.-]*" | head -1)
if [ -z "$APP_URL" ]; then echo "route CF tidak terbaca; cek 'cf app $APP'"; exit 4; fi
for i in $(seq 1 20); do
  BODY=$(curl -s --max-time 20 "$APP_URL/health" || true)
  echo "$BODY" | grep -q '"reachable":true' && { echo "OK  $APP_URL/health -> $BODY"; break; }
  sleep 6
done
echo "$BODY" | grep -q '"reachable":true' || { echo "GAGAL: /health masih $BODY"; exit 5; }

echo
echo "Uji jalur nyata (JSON-RPC) — kirim satu pertanyaan gaya Joule:"
echo "  curl -s -X POST $APP_URL/ -H 'Content-Type: application/json' \\"
echo "    -d '{\"jsonrpc\":\"2.0\",\"id\":\"1\",\"method\":\"message/send\",\"params\":{\"message\":{\"role\":\"user\",\"kind\":\"message\",\"messageId\":\"1\",\"parts\":[{\"kind\":\"text\",\"text\":\"bagaimana kondisi pasokan?\"}]}}}'"
