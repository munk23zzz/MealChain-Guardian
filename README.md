# MealChain Guardian 2.0

Lapisan **agentic decision intelligence** yang menyeimbangkan pasokan pangan dan kebutuhan
institusional lintas lokasi, dengan keamanan pangan dan kesegaran sebagai *hard constraint* —
bukan pertimbangan tambahan. Dibangun untuk kompetisi **Sokrates x SAP x AWS AI Agent**, dengan
Program Makan Bergizi Gratis (MBG) Indonesia sebagai use case utama.

SAP adalah *system of record* dan eksekusi. AWS Bedrock AgentCore adalah infrastruktur agentic AI.
MealChain Guardian adalah lapisan keputusan yang menggabungkan sinyal pasokan, permintaan, harga,
kesegaran, keamanan, logistik, dan bukti pendukung menjadi satu rekomendasi yang bisa dieksekusi —
selalu dengan persetujuan manusia untuk aksi berisiko.

## Repo dan demo

| Branch | Isi | Cara pakai |
|---|---|---|
| `main` | kode aplikasi penuh: FastAPI + Postgres + Next.js (server mode) + agen AgentCore + jembatan SAP Joule | `docker compose up -d` (lihat di atas) |
| `demo` | ekspor statis Next.js dengan data mock (`STATIC_EXPORT=true`, `NEXT_PUBLIC_USE_MOCK=true`) | GitHub Pages: https://munk23zzz.github.io/MealChain-Guardian/ |

Demo di GitHub Pages sengaja statis: tidak ada backend, tidak ada database, tidak ada panggilan API —
angkanya data contoh. Untuk demo yang benar-benar menjalankan agen dan menulis ke database, jalankan
`main` secara lokal atau di server.

## Yang dikerjakan sistem ini

- **Deteksi ketidakseimbangan lintas wilayah** — surplus di satu kota, kekurangan di kota lain,
  beserta biaya angkut (tarif per km/ton, kaki pertama + linehaul) sebagai bagian biaya keputusan.
- **Rekomendasi dengan bukti** — setiap keputusan membawa jejak bukti (batch, kesegaran, safety
  status, kandidat yang dievaluasi, alasan peringkat) yang bisa ditelusuri di UI.
- **Tata kelola persetujuan** — usul/eksekusi hanya peran kepala SPPG, transfer dana butuh dua
  persetujuan peran berbeda, dan review agen bersifat *advisory* (tidak boleh mengubah status).
- **Batas keras yang tidak bisa di-override** — LLM tidak pernah menghitung angka *safety-critical*;
  status keselamatan (PASS/FAIL/NEEDS_VERIFICATION) tidak dapat ditimpa.

## Tumpukan

| Lapisan | Teknologi |
|---|---|
| Frontend | Next.js 14.2 (App Router) + React 18, CSS modul, Vitest |
| Backend | FastAPI 0.115, SQLAlchemy 2, Postgres 16, Alembic |
| Agen | supervisor + worker deterministik, AWS Bedrock AgentCore (Runtime/Gateway/Memory) |
| SAP | SAP AI Core (peramalan RPT-1.6), jembatan A2A untuk SAP Joule, layanan `mock-sap` untuk demo lokal |
| Infra | Docker Compose (postgres, backend, frontend, mock-sap), skrip gerbang di `scripts/`, `verify/`, `infra/` |

## Menjalankan lokal

```bash
cp .env.example .env          # isi nilai rahasia di .env (JANGAN commit .env)
docker compose up -d
docker compose exec backend alembic upgrade head
bash scripts/db-mode.sh init-demo --refresh   # siapkan data demo
```

- Frontend: http://localhost:3000 · Backend/OpenAPI: http://localhost:8000/docs · mock-sap: :8001
- `.env.example` memuat 111 kunci beserta komentar artinya. Nilai asli tidak pernah ada di repo.

### Akun demo

| Akun | Peran |
|---|---|
| `sppg.head@demo.local` | Kepala SPPG — mengusulkan & mengeksekusi |
| `sppg.nutritionist@demo.local` | Ahli gizi SPPG — memverifikasi & menyetujui |
| `bgn.monitor@demo.local` | Monitor BGN — baca-saja, tanpa aksi tulis |

Kata sandi akun demo ada di `.env` lokal, bukan di repo.

## Gerbang mutu

```bash
# backend — pytest HANYA pada DB klon, bukan DB demo
bash scripts/gerbang-db-terpisah.sh

# frontend
cd frontend && npm run test && npm run typecheck && npm run lint
```

Suite backend penuh butuh belasan menit dan memakai CPU + Postgres yang sama: hentikan sebelum
demo atau rekaman. Tes backend menulis dan mem-purge baris demo, jadi jangan dijalankan pada DB demo.

## Struktur repo

```
backend/     FastAPI: API, model, migrasi Alembic, seed demo, tes (326 berkas tes)
frontend/    Next.js: halaman per peran, komponen, tes Vitest (298 berkas tes)
agent/       supervisor + worker, klien AgentCore, watchdog tunnel
sap-joule/   jembatan A2A ke SAP Joule + server capability, tes kontrak
scripts/     gerbang DB terpisah, snapshot keadaan, mode database, deploy manual
verify/      spesifikasi invarian & harness verifikasi (JSON spec + skrip)
infra/       kebijakan IAM AgentCore, aset Docker
docs/        arsitektur, PRD, skema, desain, runbook demo, catatan verifikasi
```

## Dokumen

| Berkas | Isi |
|---|---|
| `IDEA.md` | kenapa proyek ini ada, batas yang tidak dilanggar |
| `Rules.md` | aturan kerja & larangan (rahasia, DB demo, peran) |
| `AGENTS.md` | urutan baca dokumen, perintah penting, saklar environment |
| `Roadmap.md`, `TODO.md` | status sprint dan status task |
| `docs/Architecture.md` | arsitektur & alur keputusan |
| `docs/PRD.md` | ringkasan kebutuhan produk |
| `docs/Schema.md` | skema database & invarian |
| `docs/design.md` | token warna, komponen, aturan tampilan |
| `docs/DemoRunbook.md`, `docs/demo/` | alur demo untuk juri |
| `docs/verification/` | catatan verifikasi bertanggal (bukti, bukan klaim) |
| `docs/verification/AGENTCORE_STATUS.md` | status integrasi AWS AgentCore apa adanya |

## Keamanan dan data

- Rahasia hanya di `.env` lokal (di-ignore). Repo memuat templat `.env.example` tanpa nilai.
- Dump database, sertifikat, kunci, dan laporan audit DB tidak dilacak git.
- Data demo bersifat sintetis; angka di dokumen verifikasi adalah hasil ukur pada tanggalnya
  masing-masing, bukan janji keadaan sekarang.
- Operasi tulis pada DB demo dilarang saat audit atau pengujian.

## Lisensi

Lihat `sap-joule/LICENSE` dan `sap-joule/NOTICE` untuk komponen jembatan SAP.
