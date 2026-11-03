#!/usr/bin/env bash
# Menyambungkan ULANG jembatan Joule di Cloud Foundry ke backend MealChain di laptop.
#
# Kenapa ada: tunnel quick Cloudflare (`*.trycloudflare.com`) mati setiap kali mesin tidur atau
# `cloudflared` berhenti, dan URL-nya BERGANTI setiap dijalankan ulang. Gejalanya di Joule:
#
#   "Data MealChain Guardian untuk permintaan `supply_situation` belum bisa diambil.
#    Penyebab: backend MealChain tidak bisa dihubungi (...) [Errno -2] Name or service not known"
#
# Perintah ini memperbaikinya dalam satu jalan: tunnel baru → uji dari luar → set env CF →
# restage → uji `/health` jembatan sampai `reachable: true`.
#
# Pakai:
#   bash sap-joule/scripts/tunnel-untuk-cf.sh
#   # opsi: APP=<nama-app-cf> MEALCHAIN_API_URL_INTERNAL=http://localhost:8000
#
# Prasyarat: stack demo hidup (`docker compose up -d`), `cloudflared` terpasang, `cf` sudah login.
set -u

APP="${APP:-mealchain-joule-bridge-4sehat3trio}"
BACKEND="${MEALCHAIN_API_URL_INTERNAL:-http://localhost:8000}"
CF_BIN="${CF_BIN:-cf}"
CLOUDFLARED="${CLOUDFLARED:-cloudflared}"
LOG="${TMPDIR:-/tmp}/cloudflared-mealchain.log"

if ! curl -sf -m 5 "$BACKEND/health" >/dev/null; then
  echo "GAGAL: backend $BACKEND tidak menjawab. Jalankan dulu: docker compose up -d" >&2
  exit 2
fi

echo "1/5 menjalankan tunnel ke $BACKEND ..."
: > "$LOG"
"$CLOUDFLARED" tunnel --url "$BACKEND" --no-autoupdate > "$LOG" 2>&1 &
TUNNEL_PID=$!
trap 'kill $TUNNEL_PID 2>/dev/null' EXIT

URL=""
for _ in $(seq 1 40); do
  URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" | head -1)
  [ -n "$URL" ] && break
  sleep 0.5
done
if [ -z "$URL" ]; then
  echo "GAGAL: cloudflared tidak memberi URL. Log: $LOG" >&2
  tail -5 "$LOG" >&2
  exit 1
fi
echo "    URL baru: $URL"

echo "2/5 menguji URL dari internet ..."
SEHAT=""
for _ in $(seq 1 30); do
  SEHAT=$(curl -sf -m 10 "$URL/health" || true)
  [ -n "$SEHAT" ] && break
  sleep 1
done
case "$SEHAT" in
  *'"healthy"'*) echo "    OK: $SEHAT" ;;
  *) echo "GAGAL: $URL/health belum menjawab. Log: $LOG" >&2; exit 1 ;;
esac

echo "3/5 mengarahkan jembatan CF ($APP) ke URL itu ..."
"$CF_BIN" set-env "$APP" MEALCHAIN_API_URL "$URL" >/dev/null || exit 1

echo "4/5 restage jembatan (butuh ~1-2 menit) ..."
"$CF_BIN" restage "$APP" >/dev/null || exit 1

echo "5/5 memeriksa jembatan benar-benar mencapai backend ..."
DOMAIN=$("$CF_BIN" app "$APP" 2>/dev/null | grep -oE '[a-z0-9.-]+\.cfapps\.[a-z0-9.]+' | head -1)
if [ -z "$DOMAIN" ]; then
  echo "LEWAT: domain app tidak terbaca dari \`cf app $APP\`; periksa manual" >&2
  exit 1
fi
for _ in $(seq 1 30); do
  JEMBATAN=$(curl -sf -m 15 "https://$DOMAIN/health" || true)
  case "$JEMBATAN" in
    *'"reachable":true'*) echo "    OK: https://$DOMAIN/health -> $JEMBATAN"; break ;;
  esac
  sleep 2
done
case "${JEMBATAN:-}" in
  *'"reachable":true'*)
    echo
    echo "SIAP. Joule chat sekarang membaca backend MealChain lewat $URL"
    echo "Kalau mesin ini tidur / cloudflared berhenti, jalankan perintah ini lagi."
    ;;
  *)
    echo "GAGAL: jembatan belum melaporkan reachable:true -> ${JEMBATAN:-kosong}" >&2
    echo "Periksa: $CF_BIN logs $APP --recent" >&2
    exit 1
    ;;
esac
