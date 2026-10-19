#!/usr/bin/env bash
# Verifikasi detail healthcheck frontend: apakah benar mendeteksi "kontainer Up tapi tidak melayani".
set -u
cd "E:/hackathon/HackathonAWS/mealchain-guardian" || exit 1
C=mealchain-frontend
LOG=verify/fe-healthcheck-detail.log
: > "$LOG"
say() { echo "== $(date +%H:%M:%S) $*" | tee -a "$LOG"; }
hs() { docker inspect "$C" --format 'status={{.State.Status}} health={{.State.Health.Status}} failing={{.State.Health.FailingStreak}} http_ok={{.State.Health.Log}}' 2>/dev/null | cut -c1-120 | tee -a "$LOG"; }
health() { docker inspect "$C" --format '{{.State.Health.Status}}' 2>/dev/null; }
page() { curl -s -o /dev/null -w '%{http_code}' --max-time 12 http://127.0.0.1:3010/; }

say "awal: health=$(health) page=$(page)"

say "1) GET halaman langsung: bukti server benar-benar melayani"
for i in 1 2 3; do echo "   GET / => $(page)" | tee -a "$LOG"; done

say "2) simulasi hang: SIGSTOP proses next-server (PID 29) -> kontainer tetap Up, server diam"
docker exec "$C" sh -c 'kill -STOP 29' && echo "   SIGSTOP terkirim" | tee -a "$LOG"
for i in $(seq 1 16); do
  h=$(health); p=$(page)
  echo "   t+$((i*15))s health=$h page=$p" | tee -a "$LOG"
  [ "$h" = "unhealthy" ] && break
  sleep 15
done
say "status kontainer saat server dibekukan"; hs

say "3) pulihkan: SIGCONT -> harus kembali healthy tanpa restart kontainer"
docker exec "$C" sh -c 'kill -CONT 29' && echo "   SIGCONT terkirim" | tee -a "$LOG"
for i in $(seq 1 12); do
  h=$(health); p=$(page)
  echo "   t+$((i*15))s health=$h page=$p" | tee -a "$LOG"
  [ "$h" = "healthy" ] && break
  sleep 15
done
say "status akhir"; hs

say "4) docker stop -> exit code dan status health"
docker stop "$C" > /dev/null 2>&1
docker inspect "$C" --format 'status={{.State.Status}} exit={{.State.ExitCode}} health={{with .State.Health}}{{.Status}}{{end}} finished={{.State.FinishedAt}}' | tee -a "$LOG"
say "5) hidupkan lagi (docker start) dan tunggu healthy"
docker start "$C" > /dev/null 2>&1
for i in $(seq 1 12); do
  h=$(health); st=$(docker inspect "$C" --format '{{.State.Status}}')
  echo "   t+$((i*10))s status=$st health=$h" | tee -a "$LOG"
  [ "$h" = "healthy" ] && break
  sleep 10
done
say "selesai: page=$(page)"
