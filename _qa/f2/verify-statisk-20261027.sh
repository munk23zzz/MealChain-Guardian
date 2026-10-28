#!/usr/bin/env bash
# Butir 9 + 10 Fase 2: verifikasi statis/seam + drift OpenAPI.
# DB: clone sekali-pakai mealchain_f2_verif (bukan DB demo).
set -uo pipefail
REPO=/e/hackathon/HackathonAWS/mealchain-guardian
cd "$REPO" || exit 1
LOG=_qa/f2/verify-statisk-20261027.txt
DSN="postgresql+asyncpg://mealchain:$(grep -E '^POSTGRES_PASSWORD=' .env | head -1 | cut -d= -f2- | tr -d '"'"'"'"'"'"'"')@postgres:5432/mealchain_f2_verif"

{
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') ==="
  echo "db        : mealchain_f2_verif (klon sekali-pakai)"
  echo "head      : $(git rev-parse --short HEAD)"
  echo "kotor     : $(git status --porcelain | wc -l) berkas"
  echo "pytest lain: $(docker exec mealchain-backend sh -lc 'for p in /proc/[0-9]*; do tr "\0" " " < $p/cmdline 2>/dev/null | grep -q "py""test" && echo x; done | wc -l' 2>/dev/null)"
} | tee "$LOG"

echo "--- pytest subset Fase 2 + drift ---" | tee -a "$LOG"
docker compose exec -T -e DATABASE_URL="$DSN" backend python -m pytest \
  tests/test_session_modes.py tests/test_demo_seed.py tests/test_demo_seed_binding.py \
  tests/test_openapi_artifact_drift.py -q -p no:cacheprovider 2>&1 | tee -a "$LOG"
echo "PYTEST_EXIT=${PIPESTATUS[0]}" | tee -a "$LOG"

{
  echo "--- sesudah ---"
  echo "waktu     : $(date '+%Y-%m-%d %H:%M:%S')"
  echo "head      : $(git rev-parse --short HEAD)"
  echo "sisa sesi uji: $(docker exec mealchain-postgres psql -U mealchain -d mealchain_f2_verif -At -c "select count(*) from demo_sessions where template_version='uji-fase2'")"
} | tee -a "$LOG"
