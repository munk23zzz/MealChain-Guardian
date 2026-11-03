# Status keamanan — 26 Oktober 2026

Dokumen ini mencatat **status nyata** temuan keamanan yang dibuka pada audit
sebelumnya, termasuk yang sengaja belum dikerjakan. Jangan membaca "tertutup"
untuk temuan yang masih terbuka.

| ID | Temuan | Status 26 Okt 2026 | Bukti / alasan |
|---|---|---|---|
| SEC-01 | Kredensial `.env` pernah terekspos (repo sudah publik sejak klon demo) | **TERBUKA — tindakan pemilik** | Rotasi kata sandi Postgres, `DEMO_PASSWORD*`, dan kunci agen hanya bisa dilakukan di mesin/akun pemilik. `.env` tidak pernah di-track (`git check-ignore .env` → cocok), tetapi nilainya harus dianggap bocor. |
| SEC-02 | Kata sandi akun demo ditulis di bundel klien / endpoint demo terbuka | **DITUTUP (kode), pintu demo terkunci dua kunci (27 Okt 2026)** | `frontend/app/page.tsx` tidak memuat literal kata sandi. Halaman login publik memakai `GET /auth/demo-login`, yang TANPA token tetapi hanya terbuka bila `DEMO_MODE` **dan** `DEMO_LOGIN_AUTOFILL` aktif; selain itu → `{"enabled": false, "accounts": []}`. `GET /auth/demo-accounts` tetap ber-token admin (`bgn_monitor`): tanpa token → 401, token non-admin → 403. Sumber sandi tetap sisi server (`backend/app/seed/demo_credentials.py` / `DEMO_PASSWORD_<ROLE>`). Verifikasi: `grep -c "<DEMO_PASSWORD>" frontend/app/page.tsx frontend/lib/*.ts` → 0; `pytest tests/test_demo_accounts_browser.py` → 8 lulus; `GET /auth/demo-accounts` tanpa token → 401. |
| SEC-04 | CVE dependensi frontend: `next` (critical), `maplibre-gl` (critical), `postcss` (high), `eslint-config-next`/`glob` (high), `vitest`/`esbuild` (moderate, dev) | **TERBUKA — butuh migrasi mayor** | `npm audit fix` tanpa `--force` tidak mengubah apa pun (15 temuan tetap: 4 critical, 5 high, 6 moderate). Perbaikan menuntut Next 14 → 16 dan maplibre-gl 4 → 6, keduanya breaking. |
| AUD-TEST-02 | Perintah `pytest` di DB kerja mem-purge baris demo | **DIMITIGASI** | `AGENTS.md` melarangnya; tes berat dijalankan pada DB klon (`mealchain_gate`, `mealchain_idem2`, `mealchain_suite`). |

## Kenapa SEC-04 tidak "diperbaiki cepat"

Upgrade `next@14.2.14 → 16.x` dan `maplibre-gl@4.7.1 → 6.x` bukan bump versi:
keduanya mengubah API yang dipakai (`app/` router, hooks, layer map, ekspresi
style), dan repo ini punya 1.818 tes frontend + 11 tab yang harus diregresi
visual. Mengerjakannya beberapa hari sebelum penjurian berisiko merusak demo
yang sudah terverifikasi.

**Rencana yang disarankan (branch terpisah, bukan `main` demo):**
1. `git switch -c chore/upgrade-next16`; naikkan `next`, `eslint-config-next`,
   `vitest`, `maplibre-gl` sekaligus; `npm install` lalu `npx tsc --noEmit`.
2. Jalankan `npx vitest run` sampai 1.818 tes hijau; perbaiki pemakaian API yang
   berubah (React 19 + Next 16 menghapus beberapa default).
3. `npm run build` (ingat jebakan exFAT: preload `scripts/exfat-readlink-patch.cjs`).
4. Bandingkan visual 11 tab dengan `_qa/design-consistency/*` sebelum merge.
5. `npm audit` harus 0 critical sebelum dianggap selesai.

## Mitigasi yang berlaku sekarang

- Aplikasi demo tidak menerima input pengguna yang tidak tepercaya: seluruh
  GeoJSON, kutipan harga, dan batch berasal dari seed internal; tidak ada unggah
  berkas atau URL yang dipantulkan ke map.
- Jalur yang dieksploitasi CVE Next (Server Actions DoS, origin check dev server)
  tidak dipakai pada demo produksi (`next start`, tanpa Server Actions).
- Kata sandi demo tidak ada di bundel (SEC-02): tombol login mengambilnya dari
  `GET /auth/demo-login` — pintu tanpa token yang hanya terbuka bila `DEMO_MODE`
  dan `DEMO_LOGIN_AUTOFILL` sama-sama aktif. `GET /auth/demo-accounts` tetap
  ber-token admin (`bgn_monitor`).
