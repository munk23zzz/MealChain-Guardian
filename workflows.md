# workflows.md — Cara Hermes (atau AI agent lain) Bekerja di Proyek Ini

Dokumen ini menghubungkan aturan proyek (`Rules.md`) dengan skill yang sudah terinstall di
Hermes agent. Kalau kamu AI agent lain yang tidak punya skill-skill ini, baca versi "manual"
di tiap langkah.

---

## 0. Di awal setiap sesi

1. Baca urutan ini: `AGENTS.md` → `IDEA.md` → `TODO.md` (cek status terkini) → `Rules.md` →
   dokumen relevan lain (`docs/PRD.md`, `docs/Architecture.md`, dst. sesuai task)
2. Jangan asumsikan progress dari sesi sebelumnya kalau tidak tercermin di `TODO.md` —
   `TODO.md` adalah satu-satunya sumber kebenaran status.

## 1. Alur kerja per sprint

1. Buka `Roadmap.md`, cari sprint yang aktif
2. Pakai skill **`writing-plans`** untuk mengubah goal sprint jadi rencana eksekusi detail
   (task-by-task, dengan urutan dependency)
3. **Tampilkan plan ke Roy untuk direview SEBELUM eksekusi** — ini bukan opsional. Roy secara
   eksplisit minta model kerja: dia review plan, baru approve, baru Hermes eksekusi mandiri
4. Setelah disetujui, pakai skill **`executing-plans`** untuk menjalankan
5. Kalau ada bagian yang bisa dikerjakan paralel (misal backend vs frontend), pertimbangkan
   **`dispatching-parallel-agents`** / **`subagent-driven-development`**
6. Update `TODO.md` setelah SETIAP unit kerja selesai — bukan di akhir sprint

## 2. Alur kerja per task/fitur

1. Cek `docs/Skill.md` untuk formula/kontrak yang relevan sebelum mulai coding
2. Untuk logic di `backend/app/core/*`: **`test-driven-development`** — test dulu, baru kode
3. Kalau ada bug/perilaku tidak terduga: **`systematic-debugging`** — jangan tebak-tebak,
   ikuti proses sistematis
4. Sebelum mengklaim task selesai: **WAJIB jalankan `verification-before-completion`** — cek
   ulang terhadap acceptance criteria di `TODO.md`/`Roadmap.md`, bukan cuma "kelihatannya jalan"
5. Untuk perubahan UI: **`webapp-testing`** sebelum ditandai selesai
6. Update baris terkait di `TODO.md` (status + catatan singkat)

## 3. Kolaborasi dengan teman (dev kedua)

1. Task selesai → **`requesting-code-review`** sebelum merge ke `main`
2. Menerima review dari teman → **`receiving-code-review`**, address feedback, jangan skip
3. Setelah approved → **`finishing-a-development-branch`** (merge + cleanup branch)
4. Kalau ada perubahan di `Architecture.md`/`Schema.md` — flag eksplisit ke Roy di luar alur
   biasa (lihat `Rules.md` §1.5)

## 4. Desain & frontend

- Pakai `docs/design.md` sebagai source of truth untuk token warna/komponen
- Untuk styling/layout baru: skill **`frontend-design`**, **`ui-ux-pro-max`**,
  **`design-taste-frontend`**, referensi **`popular-web-designs`** kalau butuh inspirasi pola UI
  yang sudah terbukti
- Diagram arsitektur tambahan (kalau `docs/Architecture.md` perlu visual baru): skill
  **`architecture-diagram`**

## 5. Dokumentasi & knowledge management

- Kalau ada insight/keputusan baru yang perlu diingat lintas sesi dan relevan untuk
  knowledge graph pribadi Roy: sinkronkan ke Obsidian lewat skill **`obsidian`** /
  **`obsidian-graph-linking`** (opsional, bukan wajib untuk progress tracking proyek —
  `TODO.md` tetap primary)
- Kalau butuh audit menyeluruh kesehatan kode vs `Rules.md`/`Architecture.md`: skill
  **`technical-audit`**

## 6. Checklist rehearsal demo (WAJIB sebelum hari-H ke juri)

1. Jalankan Event 1, 2, 3 end-to-end minimal **3x berturut-turut** tanpa gagal
2. Verifikasi Agent Activity Log menampilkan trace asli dari AgentCore Observability (bukan
   data kosong/error)
3. Rekam 1 video fallback lengkap (jaga-jaga kalau live call Bedrock gagal/lambat saat demo)
4. Cek semua badge "Data Simulasi"/mock tampil dengan benar — jangan sampai terlihat mengklaim
   data SAP asli
5. Siapkan jawaban singkat untuk pertanyaan juri yang mungkin muncul: "bagian mana yang
   benar-benar AWS/SAP agentic AI, bagian mana yang deterministik?" — jawabannya ada di
   `docs/Architecture.md` §1 dan §5

## 7. Kalau butuh skill yang belum terinstall

Jangan improvisasi diam-diam. Pakai **`find-skills`** untuk cari dulu; kalau memang tidak ada,
laporkan eksplisit ke Roy apa yang dibutuhkan dan kenapa, biar dia yang install.

## 8. Prioritas kalau waktu mepet (3-4 minggu, urutan pemotongan scope)

Kalau di tengah jalan waktu tidak cukup, potong dalam urutan ini (dari yang paling boleh
dipotong duluan): AgentCore Identity → KPI Dashboard polish → Settings/Admin screen →
notifikasi non-esensial. **JANGAN PERNAH** potong: 3 skenario demo interaktif, Agent Activity
Log, human approval flow — tiga ini adalah inti yang dinilai juri (lihat `docs/PRD.md` §7).
