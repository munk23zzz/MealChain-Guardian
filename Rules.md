# Rules.md — MealChain Guardian

Berlaku untuk semua kontributor: manusia maupun AI agent (Hermes, atau tools lain). Tool-agnostic
— tidak mengasumsikan format tool tertentu.

---

## 1. Batasan yang TIDAK BOLEH dilanggar (hard rules)

1. **LLM tidak pernah menghitung angka safety-critical.** Safe Delivered Cost, scoring,
   constraint check = kode deterministik di `backend/app/core/*`, selalu unit-tested. Kalau
   ada kode yang meminta LLM "hitung biaya ini" secara langsung di teks bebas — itu bug, bukan
   fitur.
2. **Tidak ada auto-execute untuk aksi berisiko tinggi.** Setiap yang menulis ke SAP (mock)
   atau mengeksklusi supplier WAJIB lewat tabel `approvals` dengan `approved = true` dulu.
3. **Safety status tidak pernah di-override oleh agent.** Kalau `safety.evaluate()` return
   FAIL, tidak ada kode/prompt manapun yang boleh menyatakan batch itu "aman".
4. **Jangan mengarang data SAP/AWS sebagai data asli.** Semua yang dari mock SAP harus jelas
   ditandai (`X-Data-Source: MOCK`, badge UI). Jangan sampai demo terlihat mengklaim SAP nyata
   padahal simulasi.
5. **Jangan ubah `Architecture.md` atau `Schema.md` tanpa flag ke Roy.** Dua dokumen ini adalah
   kontrak antara Roy dan temannya — perubahan struktural harus direview, bukan langsung commit.
6. **Setiap perubahan status task WAJIB update `TODO.md`.** Ini "memory" proyek — kalau tidak
   diupdate, progress hilang dan pekerjaan bisa terulang/konflik.

## 2. Konvensi kode — Python (backend, agent)

- Format: **Black** + **Ruff** (lint), type hints wajib untuk fungsi publik
- Naming: `snake_case` untuk fungsi/variabel, `PascalCase` untuk class
- Domain logic (`core/`) tidak boleh import apapun dari `api/` (arah dependency satu arah:
  api → core, bukan sebaliknya)
- Setiap fungsi di `core/` yang menghitung angka wajib punya unit test dengan minimal 1 contoh
  numerik konkret (lihat `docs/Skill.md` §7 untuk contoh)

## 3. Konvensi kode — TypeScript/React (frontend)

- Format: **Prettier** + **ESLint**
- Functional components + hooks, tidak ada class component
- Nama file component: `PascalCase.tsx`; hooks: `useSomething.ts`
- Semua data-fetching lewat React Query, jangan `fetch` manual di dalam component

## 4. Git & commit

- Branch naming: `feature/<nama>`, `fix/<nama>`, `chore/<nama>`
- Commit message: format `type: deskripsi singkat` (`feat:`, `fix:`, `docs:`, `test:`, `chore:`)
- Tidak ada commit langsung ke `main` — selalu lewat branch, walau kerja solo (memudahkan
  review dengan teman)

## 5. Testing

- TDD untuk semua logic di `backend/app/core/*` — tulis test dulu sebelum implementasi
  (pakai skill `test-driven-development`)
- Minimum: setiap hard constraint (safety, freshness, capacity, delivery window) punya test
  case yang membuktikan constraint itu benar-benar menggagalkan kandidat saat harus gagal
- UI flow kritis (3 skenario demo) wajib dites end-to-end sebelum dianggap selesai (pakai
  skill `webapp-testing`)

## 6. Dokumentasi

- Endpoint baru → update kontrak tool di `docs/Skill.md` §5 di commit yang sama
- Perubahan schema → update `docs/Schema.md` di commit yang sama, sertakan migration file
- Jangan biarkan dokumentasi "menyusul" — kalau kode berubah, dokumen berubah di PR yang sama

## 7. Keamanan

- Tidak ada secret di kode — semua lewat `.env`, `.env.example` selalu up to date (tanpa
  value asli)
- Kredensial AWS (Bedrock/AgentCore) milik kompetisi — jangan commit, jangan share di luar tim
- Mock SAP tidak butuh kredensial nyata; kalau ada placeholder, beri nilai jelas-jelas palsu
  (`MOCK_SAP_KEY=not-a-real-key`)

## 8. Kolaborasi duo (Roy + teman)

- Sebelum mulai task besar, cek `TODO.md` — jangan kerjakan task yang sudah "In Progress"
  oleh orang lain tanpa koordinasi
- Review kode teman sebelum merge (`requesting-code-review`/`receiving-code-review`), walau
  ringkas — minimal cek: apakah melanggar hard rules di §1
- Kalau tools teman beda dengan Hermes, dokumen ini tetap berlaku sama — aturan bukan
  spesifik-tool
