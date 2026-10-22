#!/usr/bin/env bash
# Satu perintah untuk memulihkan jembatan Joule setelah tunel mati.
#
#   bash scripts/joule-perbaiki.sh
#
# Skrip ini:
#   1. memeriksa sesi Cloud Foundry; kalau kedaluwarsa, meminta login SSO di
#      terminal INI (kode sekali pakai dari browser — memang harus diketik manusia);
#   2. menyalakan tunel baru ke backend lokal dan menguji/menyalakan ulang
#      tunel lama bila URL-nya sudah mati;
#   3. `cf set-env MEALCHAIN_API_URL` + `cf restage`;
#   4. memverifikasi `/health` lewat route CF sampai `"reachable":true`.
set -uo pipefail

DIR=$(cd "$(dirname "$0")" && pwd)
CF_API=${CF_API:-https://api.cf.ap10.hana.ondemand.com}

if ! cf apps >/dev/null 2>&1; then
  echo "Sesi Cloud Foundry tidak aktif. Login SSO dulu:"
  echo "  1) perintah di bawah mencetak kode sementara + URL;"
  echo "  2) buka URL itu di browser, setujui, salin kodenya;"
  echo "  3) tempel kodenya di prompt ini."
  echo
  cf login -a "$CF_API" --sso || { echo "login gagal/dibatalkan."; exit 2; }
fi

exec bash "$DIR/joule-perbaiki-tunnel.sh"
