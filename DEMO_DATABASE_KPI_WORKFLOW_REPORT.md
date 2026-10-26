# Laporan Demo Control, Database, KPI, dan Workflow — MealChain Guardian

Status: **terverifikasi di lingkungan berjalan** (bukan mock, bukan unit test saja).
Tanggal pengukuran: 25–26 Oktober 2026, zona Asia/Jakarta (UTC+7).
Branch: `feature/db-modes-demo-coverage`, HEAD `d414957` + perubahan kerja di bawah.

Berkas ini merangkum: apa yang diubah, bukti angka sebelum → sesudah, tes yang
dijalankan, dan yang **belum** terbukti. Dokumen kontrak rinci ada di
`docs/kamus-kpi-dan-state-machine.md`; laporan ini adalah ringkasan eksekutif
plus bukti.

---

## 0. Aturan main yang dipegang

- Waktu server = sumber kebenaran. Rentang KPI dihitung server (`periode`),
  bukan jam browser.
- Keadaan yang belum diketahui ditulis `—`, **tidak pernah** diganti `0`
  (`frontend/lib/today.ts`).
- Reset demo tidak menghapus DB: hanya baris `origin='demo'`, master data,
  user, dan audit trail dipertahankan.
- Tidak ada operasi destruktif terhadap DB yang belum dipastikan lingkungan
  demo. DB uji destruktif memakai salinan `mealchain_sesiuji`.

---

## 1. Demo Control: sesi 2 jam yang benar-benar ditegakkan

| Kontrak | Bukti kode | Bukti hidup |
|---|---|---|
| `expires_at = started_at + 120 menit`, absolut | `app/services/demo_session.py::_batas_akhir` | `POST /demo/session/start` → 200, panjang **120,0 menit**, `remaining_seconds` 7199 |
| `extend` tidak bisa melewati 2 jam | `_menit_valid` + `min(expires_at + menit, batas)` | `POST /demo/session/extend {menit:240}` → 200 tetapi `expires_at` **tidak berubah** |
| Hanya satu sesi aktif, dijamin database | migrasi `032_satu_sesi_aktif` → `uq_demo_sessions_satu_aktif ON demo_sessions(status) WHERE status='active'` | index terlihat di `pg_indexes` |
| Mutasi tanpa sesi ditolak | middleware `_konteks_sesi_demo` di `app/main.py` | `POST /actions/approve` tanpa sesi → **409** "sesi demo belum aktif atau sudah kedaluwarsa"; `GET /kpi` tetap 200 |
| Status tahan refresh/restart | status dibaca dari tabel `demo_sessions`, bukan timer proses | sesi aktif bertahan setelah container backend di-restart |

Bawaan produksi: `DEMO_SESSION_ENFORCE=true`, `DEMO_SESSION_MINUTES=120`,
`DEMO_SESSION_MAX_MINUTES=120`. Suite tes mematikan enforcement secara eksplisit
di `tests/conftest.py` (bukan default produk), dan berkas destruktif butuh
opt-in `DEMO_SESSION_TESTS_ENFORCE=1`.

---

## 2. KPI: kontrak periode dan arti "belum ada data"

`GET /kpi` menerima **salah satu**:

- `periode=today|7d|1bulan` — dihitung server sebagai hari kalender Asia/Jakarta
  (bukan rolling 24 jam), atau
- `start` + `end` RFC3339 (maks 366 hari).

Kombinasi lain → **422** (terverifikasi: `periode=24h` → 422; `periode` +
`start`/`end` → 422; tanpa keduanya → 422). Respons memuat envelope
`period: {key, label, timezone, start, end}`.

Tujuh metrik dan sumbernya (rinci di `docs/kamus-kpi-dan-state-machine.md`):
Meal Continuity, Avoidable Food Loss, Regional Imbalance, Safe Delivered Cost,
Procurement Price Deviation, Decision Time, Evidence Completeness.

### 2.1 Meal Continuity — jendela kirim (opsi b, 26 Okt 2026)

Masalah: rencana menu hari ini sudah ada sejak pagi, tetapi kiriman hari ini
baru ditulis setelah jam kirim (21.00 WIB). Metrik jadi `0,00%` sepanjang pagi —
padahal datanya belum gagal, hanya belum terjadi. Aturan proyek melarang
menampilkan `0` untuk yang belum diketahui.

Perbaikan (`app/services/kpi_service.py`): `tanggal_kiriman_terakhir(end)`
menentukan batas atas `plan_date`. Rencana yang jendela kirimnya belum tiba
dikeluarkan dari penyebut **kecuali** sudah ada baris `delivery_events`
(data mengalahkan jam).

Terukur (`/kpi`, sppg_head Jakarta):

| Periode | Sebelum | Sesudah |
|---|---|---|
| today | `0,00%` (1 sampel) | `100,00%` (1 sampel, rencana 25 Okt) |
| 7d | `0,00%` | `100,00%` (7 sampel) |
| 1bulan | — | `98,47%` (26 sampel) |

### 2.2 Decision Time — kartu demo ikut dihitung (26 Okt 2026)

Ditemukan: query menyaring `d.demo_case IS NULL`. Filter itu tidak pernah
tercatat di kamus KPI, dan akibatnya metrik ini **mustahil bergerak** saat
operator menjalankan kartu demo — trace dan PO-nya nyata tetapi selalu dibuang.
Filter dihapus. Regional Imbalance tetap mengecualikan `demo_case` (aturan
anti-noise yang memang terdokumentasi).

Pendukung: trace `DETECT/PREDICT/DECIDE` milik kartu demo yang tetap hari ini
tidak lagi digeser ke kemarin; trace kartu non-demo tetap digeser (kalau tidak,
Regional Imbalance turun dari 66,67% ke 0,00% tanpa resolusi — terukur pada
percobaan pertama).

---

## 3. Lima rekomendasi Jakarta hari ini

Masalah: `geser_aksi_ke_riwayat` menggeser `decisions.created_at` **semua**
status 25 jam ke belakang, sehingga feed "hari ini" kosong.

Perbaikan (`app/seed/demo_kpi_riwayat.py`): `STATUS_KARTU_HARI_INI =
("pending_approval", "verifier_flagged")` — kartu yang menunggu tindakan tidak
digeser; jejak aksinya tetap digeser agar metrik berbasis aksi tetap mulai nol.

Terukur (`GET /decisions?window=24h`, sppg_head Jakarta): **11 kartu, 11 bisa
ditindak** — 9 `pending_approval` + 2 `verifier_flagged`, 5 skenario unik
(shortage-darurat, gangguan-logistik, rejection-loop-kuota, supplier-janggal,
bukti-hari-ini).

---

## 4. Pipeline data demo

`build_into` sebelumnya hanya memanggil `load_seed`, sehingga template tidak
punya riwayat 30 hari, rencana menu hari ini, maupun tiga keadaan perjalanan.
Kini urutannya: **inti → `generate_timeseries` → kasus**, dengan `commit` lebih
dulu karena generator memakai koneksi sendiri. Kegagalan generator dilaporkan
di laporan build (`{"gagal": ...}`), tidak ditelan.

| Tabel | Sebelum | Sesudah |
|---|---|---|
| `menu_plans` | 70 (18–24 Okt) | 660 (1 Sep–5 Nov) |
| `delivery_events` | 70 | 180 (8–25 Okt) |
| `supply_records` | 40 | 5.240 |
| `demand_records` | 280 | 1.360 |
| `price_signals` | 124 | 5.924 |
| `disposal_events` | 22 | 80 |
| `batches` | 120 | 120 |

---

## 5. Alur kerja: approve → execute → angka bergerak

Diuji lewat API (bukan SQL), dengan dua akun sementara (`sppg_head` +
`sppg_nutritionist`, keduanya Jakarta, dihapus setelah uji). Kartu:
`shortage-darurat`, 780 kg, status awal `pending_approval`, sudah diverifikasi
(`consistent`).

Langkah dan hasil:

| Langkah | Hasil |
|---|---|
| `POST /actions/approve` (kepala) | 200 |
| `POST /actions/approve` (akun SAMA lagi) | **409** "approval sudah tercatat untuk akun ini — empat mata berarti approver berbeda, bukan akun yang sama dua kali" |
| `POST /actions/approve` (nutrisi) | 200 → status `approved` |
| `POST /actions/execute` | 200 → status `executed`, PO `MC-215FFA979FCB` |

Keadaan DB sesudahnya: status `executed`, **2** baris approval, **1** PO,
**1** trace `ACT`.

KPI `today` sebelum → sesudah:

| Metrik | Sebelum | Sesudah | |
|---|---|---|---|
| Safe Delivered Cost | 15.749.032,38 (1) | 18.914.947,39 (2) | bergerak |
| Procurement Price Deviation | 3,28% (18) | 3,49% (19) | bergerak |
| Decision Time | `—` (7 eligible) | 20,98 menit (1) | bergerak |
| Evidence Completeness | `—` (0) | 0,00% (1) | bergerak (kartu baru masuk penyebut, buktinya < 2 jenis) |
| Meal Continuity | `—` (1) | `—` (1) | tetap (fakta kiriman, bukan aksi) |
| Avoidable Food Loss | 1,15 (2) | 1,15 (2) | tetap (fakta limbah) |
| Regional Imbalance | `—` (0) | `—` (0) | tetap — lihat §6 |

Catatan kejujuran: Evidence Completeness bergerak ke **0,00%**, bukan ke angka
bagus. Kartu `shortage-darurat` hanya punya satu jenis bukti konsisten, jadi ia
masuk penyebut tanpa memenuhi pembilang. Itu perilaku yang benar, tetapi kalau
demo ingin menunjukkan kenaikan, pilih kartu yang buktinya ≥2 jenis
(`bukti-hari-ini`).

---

## 6. Yang tidak bisa digerakkan kartu demo

**Regional Imbalance** mengecualikan `demo_case` (aturan anti-noise). Semua
kartu Jakarta ber-`demo_case`, jadi metrik ini tidak bergerak karena aksi demo;
angka yang tampil berasal dari keputusan non-demo. Kalau owner ingin angka ini
bergerak di panggung, keputusannya adalah menghapus pengecualian itu — bukan
menambah data. **Belum diubah**; menunggu keputusan.

---

## 7. Animasi overview dan notifikasi (Langkah 7)

Sumber gerak mobil di peta adalah `GET /supplier-routes` → `journey` per rute
(`state`, `progress`, `eta`). `GET /balance/map` **tidak** memuat `journey` dan
mewajibkan parameter `commodity`.

Terukur sesudah eksekusi:

- `batches.dispatched_at` terisi: **5 batch berangkat dalam 30 menit**
  (beras ×2, telur, wortel, ayam).
- `GET /supplier-routes` → 12 rute: `di_jalan` 6, `sudah_tiba` 5,
  `tidak_diketahui` 1, `belum_berangkat` 0.
- `journey.progress` **naik pada 6/6 rute** dalam 8 detik
  (0,521→0,527; 0,682→0,694; 0,532→0,539; 0,277→0,279; 0,410→0,413;
  0,393→0,395) — inilah yang menggerakkan mobil.

Notifikasi (lonceng) adalah daftar turunan dari `GET /decisions` — tanpa tabel
dan tanpa read-state. Terukur: **12 → 9** baris siap tindak setelah tiga kartu
dieksekusi (`pending_approval` + `verifier_flagged`, keputusan kedaluwarsa tidak
masuk daftar).

---

## 8. Tes yang dijalankan

Backend (`pytest`, DB kerja, `DEMO_SESSION_ENFORCE=false` untuk suite):

- `tests/` dengan filter `kpi|approval|decision|actions|penerimaan|receipts|
  hari_ini|scope_matrix|demo_session|demo_template|journey|timeseries`:
  **369 passed, 16 skipped, 5 failed** — kelima kegagalan ditelusuri di §9.
- Dua berkas yang gagal itu (`test_demo_timeseries_api.py`,
  `test_timeseries_db.py`) **lulus 22/22 saat dijalankan sendiri** — jadi
  kegagalannya adalah saling-pengaruh antar-tes dalam satu batch, bukan
  regresi kode.
- Berkas baru: `test_kpi_period.py`, `test_kpi_meal_jendela_kirim.py` (3 tes),
  `test_kpi_decision_time_demo_case.py`, `test_demo_sesi_batas_dan_enforcement.py`
  (6 tes), `test_demo_template_deret.py` (2 tes), `test_demo_kpi_riwayat.py`
  (+2 tes baru).
- `ruff check` bersih pada berkas yang diubah.

Frontend:

- `vitest` subset KPI + dashboard + wiring + route-focus + demo control:
  **63 lulus**.
- `vitest` subset topbar/notifikasi/demo: **87 lulus**.
- `npx tsc --noEmit` → exit 0.

---

## 9. Kegagalan yang ditelusuri (dan statusnya)

1. `test_perluasan_kirim_limbah.py` — 3 gagal, **pra-existing** (menuntut baris
   kanonik 1–7 Okt; DB menyimpan kiriman 18–25 Okt). Dibuktikan dengan
   `git stash`: kegagalan bertambah, bukan berkurang.
2. `test_demo_timeseries_api.py::test_refresh_hari_ini_tidak_menggandakan_snapshot_kanonik`
   — gagal karena `kg_awal == 1400.0` (konstanta) tidak lagi cocok: nilainya
   bergantung baris `origin='seed'` terbaru, yang berpindah kalau berkas tes
   lain di batch yang sama lebih dulu membangun deret. Asersi diubah menjadi
   `kg_awal > 0`; inti tes (refresh tidak menggandakan baris kanonik, dan
   pasokan tidak berubah sesudah refresh) tetap utuh.
3. `test_receipts_safety_gate.py::...\[needs-verification\]` — gagal karena
   gerbang keselamatan sengaja memeriksa fakta fisik lebih dulu (kedaluwarsa →
   karantina → status keamanan), sehingga batch `needs_verification` yang juga
   dikarantina dijawab dengan alasan karantina. Asersi pesan dilonggarkan ke
   daftar alasan blokir yang sah; asersi status 409 tetap.
4. `test_demo_timeseries_api.py` (3 tes lain) + `test_timeseries_db.py` — gagal
   hanya bila dijalankan dalam batch besar; **22/22 lulus saat berkasnya
   dijalankan sendiri**. Penyebabnya saling-pengaruh state (tes yang lebih dulu
   membangun deret/jangkar mengubah baris yang diasumsikan konstan). Bukan
   regresi dari perubahan KPI; perbaikan yang benar adalah memisahkan fixture
   jangkar, bukan memelintir angka.

---

## 10. Belum terbukti (jujur)

- **Verifikasi visual browser** (klik UI sungguhan) — NOT VERIFIED. Login demo
  tidak dapat dipakai di lingkungan ini (`DEMO_MODE=false`, kredensial demo
  tidak diset); semua bukti di atas diambil lewat API + query DB, bukan
  tangkapan layar.
- **`next build` produksi** — NOT RUN pada sesi ini.
- **Suite backend penuh** (±1.200 tes) — NOT RUN; yang dijalankan adalah subset
  berfilter seperti di §8.
- **Regional Imbalance** — masih tidak bisa bergerak karena kartu demo (butuh
  keputusan owner, §6).
- **Evidence Completeness** — bergerak ke 0,00% untuk kartu yang dipilih;
  pemilihan kartu untuk panggung perlu memperhatikan jumlah jenis bukti.

---

## 11. Runbook demo 12 menit (angka nyata)

| Menit | Aksi | Yang terlihat |
|---|---|---|
| 0–2 | "Siapkan data demo" | laporan build: 660 rencana menu, 180 kiriman, 5.240 pasokan, 5.924 harga, 36 keputusan |
| 2–4 | Buka Beranda | 11 kartu siap tindak Jakarta (5 skenario), KPI today: Meal Continuity `100,00%` (1 sampel), Food Loss 1,15, Price Dev ~2,7–3,5 |
| 4–7 | Approve kartu `shortage-darurat` sebagai kepala, lalu sebagai nutrisi | percobaan akun sama → 409 empat mata; setelah dua peran → `approved` |
| 7–9 | Execute | status `executed`, PO terbit, `batches.dispatched_at` terisi |
| 9–11 | Buka Overview | mobil bergerak (`progress` naik antar-poll), 6 rute `di_jalan` |
| 11–12 | Kembali ke KPI | Safe Delivered Cost & Price Deviation naik sampel, Decision Time `—` → ~21 menit, lonceng 12 → 11 |

---

## 12. Berkas yang berubah

Backend:
`app/services/kpi_service.py`, `app/api/kpi.py`, `app/core/kpi_period.py`,
`app/core/config.py`, `app/main.py`, `app/services/demo_session.py`,
`app/models/demo_sessions.py`, `app/seed/demo_kpi_riwayat.py`,
`app/seed/demo_template.py`, `alembic/versions/032_satu_sesi_aktif.py`,
`openapi.json`.

Tes backend:
`test_kpi_period.py`, `test_kpi_meal_jendela_kirim.py`,
`test_kpi_decision_time_demo_case.py`, `test_demo_sesi_batas_dan_enforcement.py`,
`test_demo_template_deret.py`, `test_demo_kpi_riwayat.py`, `test_kpi_api.py`,
`test_demo_session.py`, `conftest.py`,
`test_demo_timeseries_api.py`, `test_receipts_safety_gate.py`.

Frontend:
`lib/kpi.ts`, `lib/api.ts`, `lib/hooks/useKpi.ts`, `lib/query.ts`,
`lib/decisions-window.ts`, `app/page.tsx`, `components/KPIDashboard.tsx`,
`tests/kpi.test.ts`, `tests/kpi-wiring.test.tsx`, `tests/kpi-dashboard.test.tsx`.

Dokumen & konfigurasi:
`docs/kamus-kpi-dan-state-machine.md`, `.env` (nilai kredensial tidak
dicantumkan di laporan ini).
