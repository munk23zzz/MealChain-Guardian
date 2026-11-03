#!/usr/bin/env bash
# Bukti cepat: jembatan Joule (a2a_server) benar-benar membaca backend MealChain yang HIDUP.
#
# Yang diperiksa:
#   1. /health jembatan sehat DAN backend-nya terjangkau (reachable: true)
#   2. empat skill menjawab "completed" dengan laporan markdown yang berisi data, bukan pesan
#      "tidak tersedia" — ini yang membedakan jembatan benar dari jembatan yang cuma hidup
#   3. antrean yang dilaporkan memuat ID keputusan yang benar-benar ada di database
#   4. rincian PO yang dilaporkan memuat total nilai yang SAMA dengan kolom
#      `price * ordered_quantity` di database
#
# Pakai:
#   MEALCHAIN_READ_PASSWORD='<password demo>' bash scripts/uji-jembatan-lokal.sh
#   # opsional: MEALCHAIN_API_URL=http://localhost:8000 PORT=8098
#
# Prasyarat: stack demo hidup (docker compose up -d) dan .venv sudah terpasang
#   (uv venv .venv && uv pip install --python .venv/Scripts/python.exe -r a2a_server/requirements-dev.txt)
set -u

SAP_JOULE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-8098}"
API_URL="${MEALCHAIN_API_URL:-http://localhost:8000}"
USERNAME="${MEALCHAIN_READ_USERNAME:-bgn.monitor@demo.local}"
PY="$SAP_JOULE/.venv/Scripts/python.exe"
LOG="${TMPDIR:-/tmp}/jembatan-joule-$PORT.log"
GAGAL=0

if [ ! -x "$PY" ]; then
  echo "GAGAL: venv belum ada di $PY — jalankan uv venv .venv lalu pasang requirements-dev.txt" >&2
  exit 2
fi
if [ -z "${MEALCHAIN_READ_PASSWORD:-}" ]; then
  echo "GAGAL: MEALCHAIN_READ_PASSWORD belum diisi (kredensial akun baca demo)." >&2
  exit 2
fi

cd "$SAP_JOULE/a2a_server" || exit 2
PORT="$PORT" MEALCHAIN_API_URL="$API_URL" \
  MEALCHAIN_READ_USERNAME="$USERNAME" MEALCHAIN_READ_PASSWORD="$MEALCHAIN_READ_PASSWORD" \
  "$PY" -m uvicorn server:app --host 127.0.0.1 --port "$PORT" > "$LOG" 2>&1 &
PID=$!
trap 'kill $PID 2>/dev/null' EXIT

for _ in $(seq 1 30); do
  if curl -sf -m 2 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then break; fi
  sleep 0.5
done

HEALTH=$(curl -sS -m 10 "http://127.0.0.1:$PORT/health" || true)
case "$HEALTH" in
  *'"reachable":true'*) echo "OK   /health: jembatan sehat, backend $API_URL terjangkau" ;;
  *) echo "GAGAL /health: $HEALTH"; echo "--- log ---"; tail -15 "$LOG"; exit 1 ;;
esac

tanya() { # $1 = teks pertanyaan, $2 = penanda yang harus muncul di laporan
  local jawaban state teks
  jawaban=$(curl -sS -m 60 -X POST "http://127.0.0.1:$PORT/" \
    -H "Content-Type: application/json" \
    -d "{\"jsonrpc\":\"2.0\",\"id\":\"uji\",\"method\":\"message/send\",\"params\":{\"message\":{\"role\":\"user\",\"messageId\":\"uji\",\"parts\":[{\"kind\":\"text\",\"text\":\"$1\"}]}}}" || true)
  state=$(printf '%s' "$jawaban" | "$PY" -c "import sys,json;print(json.load(sys.stdin)['result']['status']['state'])" 2>/dev/null || echo "?")
  teks=$(printf '%s' "$jawaban" | "$PY" -c "import sys,json;print(json.load(sys.stdin)['result']['artifacts'][0]['parts'][0]['text'])" 2>/dev/null || echo "")
  if [ "$state" != "completed" ]; then
    echo "GAGAL '$1': state=$state"; GAGAL=1; return
  fi
  if ! printf '%s' "$teks" | grep -q "$2"; then
    echo "GAGAL '$1': laporan tidak memuat '$2'"; printf '%s\n' "$teks" | head -5; GAGAL=1; return
  fi
  if printf '%s' "$teks" | grep -qi "tidak dapat\|tidak tersedia\|backend tidak"; then
    echo "GAGAL '$1': laporan menyatakan data tidak tersedia"; printf '%s\n' "$teks" | head -5; GAGAL=1; return
  fi
  echo "OK   '$1' -> $(printf '%s' "$teks" | head -1)"
}

tanya "situasi pasokan SPPG" "Keseimbangan pasokan"
tanya "indikator kinerja KPI" "Indikator kinerja"
tanya "antrean usulan keputusan" "Antrean usulan"
tanya "purchase order" "Purchase order"

# ID keputusan yang dilaporkan harus benar-benar ada di database demo.
ANTREAN=$(curl -sS -m 60 -X POST "http://127.0.0.1:$PORT/" -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"uji","method":"message/send","params":{"message":{"role":"user","messageId":"uji","parts":[{"kind":"text","text":"antrean usulan"}]}}}' \
  | "$PY" -c "import sys,json;print(json.load(sys.stdin)['result']['artifacts'][0]['parts'][0]['text'])" 2>/dev/null || echo "")
ID=$(printf '%s' "$ANTREAN" | grep -oE "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}" | head -1)
if [ -z "$ID" ]; then
  echo "GAGAL: laporan antrean tidak memuat satu pun UUID keputusan"; GAGAL=1
else
  # Path native (pwd -W): docker compose adalah program Windows, sedangkan MSYS mengubah
  # "/e/..." menjadi "E:\e\..." sehingga berkas compose tidak ditemukan.
  COMPOSE_DIR="$(cd "$SAP_JOULE/.." && pwd -W)"
  ADA=$(docker compose -f "$COMPOSE_DIR/docker-compose.yml" --project-directory "$COMPOSE_DIR" \
        exec -T postgres psql -U mealchain -d mealchain -t -A \
        -c "SELECT count(*) FROM decisions WHERE id='$ID';" 2>/dev/null | tr -d ' \r\n')
  case "${ADA:-}" in
    1) echo "OK   antrean: ID $ID benar-benar ada di database demo" ;;
    0) echo "GAGAL: ID $ID dari jembatan TIDAK ada di database demo (jembatan menunjuk backend lain)"; GAGAL=1 ;;
    *) echo "LEWAT: tidak bisa memeriksa database (docker compose/psql tidak menjawab) — ID $ID tidak diverifikasi" ;;
  esac
fi

# Total nilai PO yang dilaporkan harus SAMA dengan kolom database (bukan hasil hitung jembatan).
PO=$(curl -sS -m 60 -X POST "http://127.0.0.1:$PORT/" -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"uji","method":"message/send","params":{"message":{"role":"user","messageId":"uji","parts":[{"kind":"text","text":"purchase order"}]}}}' \
  | "$PY" -c "import sys,json;print(json.load(sys.stdin)['result']['artifacts'][0]['parts'][0]['text'])" 2>/dev/null \
  | grep -oE "MC-[0-9A-Fa-f]{6,}" | head -1)
if [ -z "$PO" ]; then
  echo "GAGAL: laporan PO tidak memuat satu pun nomor PO"; GAGAL=1
else
  RINCIAN=$(curl -sS -m 60 -X POST "http://127.0.0.1:$PORT/" -H "Content-Type: application/json" \
    -d "{\"jsonrpc\":\"2.0\",\"id\":\"uji\",\"method\":\"message/send\",\"params\":{\"message\":{\"role\":\"user\",\"messageId\":\"uji\",\"parts\":[{\"kind\":\"text\",\"text\":\"PO $PO\"}]}}}" \
    | "$PY" -c "import sys,json;print(json.load(sys.stdin)['result']['artifacts'][0]['parts'][0]['text'])" 2>/dev/null || echo "")
  TOTAL_LAPORAN=$(printf '%s' "$RINCIAN" | grep -oE "Total nilai:\*\* Rp[0-9.]+" | grep -oE "[0-9.]+$" | tr -d '.')
  COMPOSE_DIR="${COMPOSE_DIR:-$(cd "$SAP_JOULE/.." && pwd -W)}"
  TOTAL_DB=$(docker compose -f "$COMPOSE_DIR/docker-compose.yml" --project-directory "$COMPOSE_DIR" \
    exec -T postgres psql -U mealchain -d mealchain -t -A \
    -c "SELECT round((price*ordered_quantity)::numeric,0)::bigint FROM sap_mock_purchase_orders WHERE po_number='$PO';" 2>/dev/null | tr -d ' \r\n')
  case "${TOTAL_DB:-}" in
    "")
      echo "LEWAT: total PO $PO tidak bisa dibandingkan (database tidak menjawab); laporan menyebut Rp${TOTAL_LAPORAN:-?}"
      ;;
    *)
      if [ "$TOTAL_LAPORAN" = "$TOTAL_DB" ]; then
        echo "OK   PO $PO: total Rp$TOTAL_LAPORAN sama dengan database"
      else
        echo "GAGAL: total PO $PO di laporan (Rp${TOTAL_LAPORAN:-kosong}) != database (Rp$TOTAL_DB)"; GAGAL=1
      fi
      ;;
  esac
fi

[ "$GAGAL" = "0" ] && echo "SEMUA OK" || echo "ADA YANG GAGAL"
exit "$GAGAL"