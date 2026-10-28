# DemoRunbook — dua jalur demo MealChain Guardian

Dokumen ini dipakai operator yang memegang layar saat geladi atau demo. Isinya **cara
memilih mode**, **urutan klik yang harus berhasil**, **cara membaca penolakan yang
memang benar**, dan **cara mengulang tanpa merusak sesi lain**. Batas kemampuan yang
tidak boleh diklaim ada di §9.

Diperbarui: 27 Oktober 2026 (Fase 12 MG) · Bukti geladi: `MG/phase-12-docs-rehearsal.md`

---

## 1. Tiga mode yang bisa dipilih

| Mode | Cara memilih | Jangkar waktu | Yang berubah di layar |
|---|---|---|---|
| **Replay** | tombol **Muat Demo Utama** (`POST /demo/session/start {mode:"replay"}`) | kanon beku `2026-10-08T12:00:00Z`, `dataset_version=kanon-2026-10-08T12:00:00Z` | ID historis stabil; kasus Jakarta/Bandung/Surabaya siap; mengulang memberi angka yang sama |
| **Realtime** | tombol **Muat Demo Real-time** (`{mode:"realtime"}`) | jam saat sesi dibuka, `dataset_version=realtime-<stempel>Z` | semua offset kejadian diturunkan dari jangkar baru; tidak ada timestamp masa depan; dua sesi realtime berbeda |
| **Operasional** | `DEMO_MODE=false` di lingkungan, lalu **restart** backend | jam dinding | seluruh `/demo/*` menjawab **404**; tidak ada tombol muat; data demo lama tetap terlihat sebagai data historis, bukan dihapus |

Ganti mode = sesi lama ditutup (`status=expired`) lalu sesi baru dibuat. Data template
tidak ikut terhapus karena baris template dimiliki sesi sentinel `cetakan`
(lihat §7).

---

## 2. Persiapan (5 menit sebelum layar dibuka)

```bash
# 1. empat service hidup
docker compose ps                     # backend, frontend, postgres, mock-sap = healthy

# 2. head migrasi yang diharapkan (bukan 033 lagi)
docker compose exec -T backend alembic current      # -> 043_least_privilege_app (head)

# 3. backend & frontend benar-benar menjawab
curl -s localhost:8000/health                        # {"status":"healthy",...}
curl -s -o /dev/null -w "%{http_code}\n" localhost:3010/

# 4. frontend di-restart bila berkas frontend berubah (bind mount Windows)
docker compose restart frontend

# 5. jembatan Joule (bila dipakai) — lihat §8
```

Port lokal: backend `8000`, frontend `3010`, mock-sap `8001`, postgres `15432`.
Akun demo ada di `scripts/smoke_e2e.py`; **kata sandi tidak dicetak di dokumen ini**.

> Kalau `alembic current` bukan `043_least_privilege_app`, jangan demo: jalankan
> `docker compose exec -T backend alembic upgrade head` dulu.

---

## 3. Beat replay (urutan klik yang diuji 27 Okt 2026)

| # | Klik / aksi | Yang harus muncul | Angka yang wajib terbaca |
|---|---|---|---|
| 1 | **Muat Demo Utama** | sesi `replay`, jangkar `8 Okt 2026 12.00 UTC`, 7 kasus per kota | `remaining_seconds` ~7200 |
| 2 | Buka **Analisis** lalu jalankan analisis (defisit masih terbuka) | kandidat + kandidat tertahan (`held`) | `candidates_total`, `eligible`, `held_total` |
| 3 | Buka keputusan kasus **wortel-coldchain-sah** | `can_approve=true`, `can_execute=false`, `min_approvals=2`, peran `sppg_head` + `sppg_nutritionist` | blocking reason "approval belum memenuhi requirement" |
| 4 | **Setujui** sebagai kepala SPPG lalu coba **Eksekusi** | eksekusi **ditolak 409** — dua peran belum lengkap | pesan butuh dua peran |
| 5 | **Setujui** sebagai ahli gizi (nutritionist) | `can_execute=true` | `approvals` = 2 |
| 6 | **Eksekusi** | keputusan `executed` + nomor PO | `po_number` (mis. `MC-…`) |
| 7 | Buka **PO / Pengadaan** | PO tertaut keputusan, total = invoice | invoice = purchase + transport + handling |
| 8 | Buka **Peta / Kiriman** | batch "di jalan" dengan ETA dari server | `travel_min`, `eta_at`, `progress` |
| 9 | Buka **Penerimaan**, catat ceklis, setujui | status penerimaan `accepted`, pasokan lokasi bergerak | `pasokan_sebelum` → `pasokan_sesudah` |
| 10 | Buka **KPI** | 7 metrik; tiap metrik membawa state + provenance + baseline | lihat catatan cakupan di §7 |
| 11 | **Refresh browser** | sesi, mode, dan jangkar tidak berubah | `session_id` sama |

Pada replay, langkah 2–11 memakai data yang sama setiap kali: dua putaran penuh
menghasikan PO dengan nomor yang sama karena keputusan memakai UUID stabil per jangkar.

---

## 4. Beat realtime

Sama seperti §3 dengan dua perbedaan yang harus **dibuktikan**:

1. **Jangkar baru.** Setelah **Muat Demo Real-time**, jangkar = jam saat sesi dibuka (bukan
   `8 Okt 2026`), dan `dataset_version` berbentuk `realtime-<stempel>Z`.
2. **Timestamp relatif konsisten.** Tidak ada timestamp masa depan: semua kejadian
   simulasi (panen, berangkat, observasi suhu) berada pada offset dari jangkar; hanya
   **waktu aksi operator** (approval, PO) memakai jam dinding.

Ulangi langkah 2–11, lalu refresh browser: sesi harus tetap sama. Kalau jam sesi hampir
habis, tekan **Perpanjang** (`POST /demo/session/extend`), jangan memuat ulang.

---

## 5. Bukti yang kurang harus `on_hold` — cara memverifikasi

Ini bukan kegagalan; ini yang membuat demo layak dipercaya.

| Yang diperiksa | Di layar | Di API |
|---|---|---|
| Batch dengan bukti suhu tidak lengkap / log rusak | kartu penerimaan menandai `needs_verification`, tombol **Setujui penerimaan** menolak | `GET /batches/{id}` → `safety_status="needs_verification"`, `evidence.evidence_sufficient=false`, `evidence_reasons[...]` |
| Ceklis tetap boleh dicatat | form ceklis bisa disimpan (`201`) | `POST /receipts` → 201 |
| Penerimaan tetap ditolak | muncul alasan "menunggu verifikasi keamanan pangan" | `POST /receipts/{id}/approve` → **409** |
| Dua peran setuju pun tidak mengeksekusi | tombol **Eksekusi** menolak | `POST /actions/execute` → **409**, `blocking_reasons` menyebut safety/review |
| Batch kedaluwarsa | baris bertanda "sudah lewat masa layak" | `blocking_reasons` berisi `batch_expired` |

Kalau salah satu dari ini **lolos**, hentikan demo: itu regresi gerbang, bukan
kebetulan.

---

## 6. Peran dan approval

| Peran | Boleh | Tidak boleh |
|---|---|---|
| `sppg_head` (kepala SPPG) | setujui/tolak, eksekusi, bangun ulang data, akhiri sesi | membaca data di luar lokasinya; membuka `/admin/users` (403) |
| `sppg_nutritionist` (ahli gizi) | setujui/tolak (peran kedua kuorum) | eksekusi sendirian (butuh kepala); akhiri sesi |
| `bgn_monitor` (pengawas) | membaca seluruh lokasi | menulis apa pun (403) |

Kuorum: `min_approvals=2` dengan `required_roles=[["sppg_head"],["sppg_nutritionist"]]`.
Joule **tidak** bisa menyetujui — permintaan approval lewat chat dijawab dengan arahan
ke cockpit (`§8`).

---

## 7. Mengulang tanpa merusak sesi lain

| Situasi | Pakai | Kenapa |
|---|---|---|
| Ingin data kembali ke keadaan awal, sesi tetap jalan | **Bangun ulang data** (`POST /demo/template/rebuild`, hanya `sppg_head`) | mem-purge baris operasional lalu menyemai template lagi; jendela sesi tidak berubah; ~70 detik; permintaan kedua saat masih berjalan ditolak 409 |
| Ingin sesi berhenti (salah mode / selesai) | **Akhiri sesi** (`POST /demo/session/end`) | menutup sesi dan membuang baris milik sesi itu; template sisa tetap ada |
| Ingin mode lain | tombol **Muat Demo …** dengan mode berbeda | sesi lama jadi `expired`, sesi baru dibuat |

Aturan yang dipegang:

- **Satu sesi aktif pada satu waktu.** Tidak ada tombol yang menghapus sesi orang lain;
  `POST /demo/session/end` hanya mem-purge baris milik sesi itu (`purge_session(sesi_id)`).
  Isolasi antar-sesi dijaga `backend/tests/test_session_modes.py`.
- **Baris template dimiliki sesi sentinel `cetakan`**, bukan sesi operator. Akibatnya:
  - **Akhiri sesi tidak menghapus template** (itulah tujuannya), tetapi
  - **KPI dengan cakupan "Simulasi" memakai sesi operator → `no_data`**, karena tidak ada
    fakta yang ber-`demo_session_id` operator. Ini jawaban jujur, bukan nol karangan.
    Untuk angka di layar, pakai cakupan **Operasional**; kalau juri bertanya kenapa
    cakupan simulasi kosong, jawab apa adanya: data template berstempel sesi `cetakan`.
  - Perbandingan `demo_session_id` dengan Joule harus memakai id sesi yang benar-benar
    memiliki baris (sesi `cetakan`) — lihat §8.
- Jangan menekan **Siapkan data demo** dua kali di depan juri: klik kedua membangun ulang
  baris dan mengubah ID di layar.

---

## 8. Joule: apa yang diuji dan apa yang tidak

- Jembatan A2A: `sap-joule/a2a_server` (`GET /health` → `{status, service:"mealchain-joule-bridge",
  backend:{reachable,...}}`). **Tidak ada** `/ready`. `/health` tidak memuat fingerprint
  dataset — nomor PO dan id sesi dibandingkan langsung ke backend.
- Lima pertanyaan wajib: **pasokan**, **KPI**, **antrean**, **PO**, **kiriman**. Untuk setiap
  mode (replay dan realtime): cocokkan nomor PO dan `demo_session_id` dengan backend.
- Uji juga: **"setujui usulan"** → jembatan menolak dan mengarahkan ke cockpit (Joule bukan
  kanal transaksi).
- Status terukur 27 Okt 2026:
  - jembatan **lokal** (uvicorn di host, menunjuk backend sesi) → lima skill menjawab dari backend.
  - jembatan **CF** `mealchain-joule-bridge-4sehat3trio.cfapps.ap10.hana.ondemand.com` →
    `/health` hidup (`service` benar, `/ready` 404), tetapi `backend.reachable=false`:
    host backend AWS yang ditunjuk sudah tidak resolve. **Bukan** bukti integrasi hidup;
    lihat `docs/verification/AGENTCORE_STATUS.md` dan butir 5 Fase 12.
  - Tenant Joule/BTP (destination, `joule list`) **INCONCLUSIVE**: sesi CF milik operator
    masih ada, tetapi push ulang jembatan **tidak** dilakukan pada fase ini (aturan: tanpa
    izin pemilik, tanpa push).

---

## 9. Batas yang harus disebut, bukan disembunyikan

- **SAP S/4HANA / ECC tidak tersedia** — tidak ada tenant, tidak ada kredensial OData.
  `mock-sap` adalah *test double*; `AWSforSAPMCPProvider` adalah pekerjaan kontrak, bukan
  bukti koneksi. Joule membaca backend MealChain, bukan ERP.
- **Tidak ada IoT nyata.** Suhu adalah **simulasi** berlabel `simulated_policy` /
  `temperature_source=simulated_realtime`, dengan `policy_basis` yang menyatakan asumsinya
  belum divalidasi domain owner. Log yang kosong/rusak **tidak** pernah jadi `pass`.
- **AgentCore** dilaporkan per operasi (resource / target / invokasi / aplikasi), bukan
  satu status "DONE" — `docs/verification/AGENTCORE_STATUS.md`.
- **Tidak ada hasil siswa / porsi tersaji** yang dikarang: MVP berhenti pada bahan diterima
  di SPPG (`docs/PRD.md`).
- Ledger append-only **ditegakkan database** (role aplikasi hanya `INSERT`/`SELECT` +
  trigger penolak `UPDATE`/`DELETE`), bukan sekadar konvensi — `docs/Architecture.md` §12.

---

## 10. Kalau ada yang gagal di layar

| Gejala | Penyebab paling sering | Tindakan |
|---|---|---|
| Tombol muat demo menjawab 404 | backend berjalan dengan `DEMO_MODE=false` | restart backend dengan `DEMO_MODE=true` |
| Semua aksi tulis 409 "sesi demo" | sesi kedaluwarsa / belum dibuka | **Muat Demo …** sekali lagi |
| Angka KPI kosong padahal demo jalan | cakupan "Simulasi" = sesi operator (§7) | ganti cakupan ke **Operasional** |
| Kartu penerimaan tanpa batch | tab belum dimuat ulang setelah bangun ulang data | refresh browser satu kali |
| Frontend tidak memuat perubahan | bind mount Windows | `docker compose restart frontend` |
| Joule menjawab "backend tidak terjangkau" | jembatan CF menunjuk host AWS yang mati (§8) | pakai jembatan lokal, atau jawab apa adanya |
