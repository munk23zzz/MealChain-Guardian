#!/usr/bin/env bash
# Bagian 2 investigasi (c): apakah frontend bisa mati SENDIRI (exit 0) tanpa diperintah?
# S1: touch-storm (memicu watcher polling di bind mount exFAT) + request storm
# S2: next build di dalam kontainer saat next dev hidup (hazard yang ditulis di memory repo)
set -u
cd "E:/hackathon/HackathonAWS/mealchain-guardian" || exit 1
C=mcg-mut-frontend-1
LOG=verify/frontend-exit0-stress.log
: > "$LOG"
say() { echo "== $*" | tee -a "$LOG"; }
st() { docker inspect "$C" --format 'status={{.State.Status}} exit={{.State.ExitCode}} restartCount={{.RestartCount}} finished={{.State.FinishedAt}}' 2>&1 | tee -a "$LOG"; }

docker start "$C" >/dev/null 2>&1
for i in $(seq 1 30); do
  [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:13010/)" = "200" ] && break
  sleep 5
done
say "siap"; st

say "S1: 30x (GET / + sentuh 1 berkas) - watcher polling harus rekompilasi"
ok=0; bad=0
for i in $(seq 1 30); do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 http://127.0.0.1:13010/)
  [ "$code" = "200" ] && ok=$((ok+1)) || bad=$((bad+1))
  docker exec "$C" sh -c 'touch /app/app/page.tsx' 2>/dev/null
  st_now=$(docker inspect "$C" --format '{{.State.Status}}')
  if [ "$st_now" != "running" ]; then say "BERHENTI di iterasi $i ($code)"; st; break; fi
  sleep 1
done
say "S1 selesai: http200=$ok, bukan200=$bad"; st
say "S1 log kontainer: pola galat"
docker logs --tail 200 "$C" 2>&1 | grep -Ei "error|fatal|killed|SIGTERM|shutting" | tail -12 | tee -a "$LOG"

say "S2: npm run build di dalam kontainer saat next dev hidup (hazard di memory/global/active_context.md)"
timeout 420 docker exec "$C" npm run build > /tmp/build-in-container.log 2>&1
say "S2 build exit=$?"
tail -6 /tmp/build-in-container.log | tee -a "$LOG"
sleep 5
say "S2 setelah build"; st
for i in 1 2 3; do
  echo "GET / => $(curl -s -o /dev/null -w '%{http_code}' --max-time 30 http://127.0.0.1:13010/)" | tee -a "$LOG"
  sleep 3
done
say "S2 log dev setelah build (30 baris terakhir)"
docker logs --tail 30 "$C" 2>&1 | tail -30 | tee -a "$LOG"
