#!/usr/bin/env bash
# Secrets scan p11 (S4-06 evidence) — run dari D:/Projects/Mealchain
cd /d/Projects/Mealchain || exit 1
echo "== .env ignored =="; git check-ignore .env && echo ".env IGNORED OK"
echo "== .env.example =="; ls .env.example 2>/dev/null || echo "tidak ada (by design)"
echo "== tracked files w/ secret patterns =="
git ls-files | while read -r f; do
  grep -l -E "Demo#[A-Za-z0-9]{6,}|AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY|Bearer eyJ|postgresql\+psycopg://[^\" ]*:[^\" ]*@|sk-[A-Za-z0-9]{20,}" "$f" 2>/dev/null
done | tee /tmp/s4_secret_hits.txt
echo "== hits =="; wc -l < /tmp/s4_secret_hits.txt
echo "== demo creds by-design check =="
grep -rl "Demo#" backend/tests backend/app/seed 2>/dev/null | sort
