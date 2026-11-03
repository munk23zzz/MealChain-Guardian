# Audit angka frontend vs database — 18 Okt 2026

> **Snapshot 18 Oktober 2026** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

Pertanyaan pemilik: "apakah ada angka di frontend yang tidak terhubung ke database
padahal seharusnya terhubung?" Metode: setiap angka di layar dilacak UI → API → DB,
lalu bandingkan dengan query langsung ke Postgres `mealchain` pada saat yang sama.

## Hasil audit: tidak ada angka karangan

Semua angka besar yang diperiksa cocok dengan DB:

| Angka di layar | Sumber | Bukti DB |
| --- | --- | --- |
| Pasokan per lokasi (10 nilai) + 5.019,56 kg | `GET /balance/map` → `supply_records` | 10 baris snapshot, jumlah sama |
| Kebutuhan 3.438 kg | `demand_records` (8 Okt) | jumlah sama |
| 5 lokasi shortage · 801,02 kg | turunan gap | sama dengan baris peta |
| Pemasok 35 · rata-rata 80% · 4 rendah · 35/35 titik | `suppliers` | agregat sama |
| 9 pemasok telur · 7 jalur kiriman · durasi OSRM | `suppliers` + `road_routes` | 9 pemasok, 44 rute OSRM, durasi 89 & 52 menit ada |
| Batch <48 jam: 2 kedaluwarsa (450 kg) + 1 segera (400 kg) | `batches.usable_until` | Palembang 250 (−908 j), Semarang 200 (−314 j), Bandung 400 (+17,4 j) |
| 7.195 blok rantai audit | `ledger_blocks` | 7.195 |
| 9 batch · 7 aman · 1 gagal (600 kg) · 1 ditahan (90 kg) | `batches.safety_status` + `quarantine_status` | 8 pass (1 quarantined 90 kg) + 1 fail 600 kg |
| Meal Continuity 100% (10 sampel) | `menu_plans` + `delivery_events` | 10 rencana 18 Okt, 10 delivered |
| Avoidable Food Loss 0,13% (2 sampel) | `disposal_events` | 2 event, 17,65 kg |
| Safe Delivered Cost Rp15.079.436 (3 sampel) | `decisions` × `sap_mock_purchase_orders` | rata-rata 3 baris = 15.079.436 |
| 4 menunggu tindakan · 21 rekomendasi | `decisions` | 3 `pending_approval` + 1 `verifier_flagged`; total 21 |

## Cacat yang ditemukan dan diperbaiki

### 1. Periode data tidak seragam dan tanpa label (paling serius)

`GET /balance/map` memakai baris TERBARU per lokasi tanpa batas waktu. Karena deret
demo diperluas sampai 5 Nov 2026 (`ACTUAL_REF`), layar berlabel "Hari Ini" menampilkan
pasokan snapshot **4 Nov** sementara kebutuhan berasal dari **8 Okt** — dua tanggal
berbeda, dibaca pengguna sebagai kondisi hari ini.

Perbaikan (dua lapis):

- Backend `app/api/balance.py`: parameter `as_of` (default **sekarang**) pada
  `GET /balance/map` dan `GET /balance/{location}/{commodity}`; baris hanya dipakai bila
  `recorded_at <= as_of`. Respons menyertakan `as_of`. `as_of` eksplisit tetap
  memungkinkan menelusuri snapshot lain.
- Frontend `lib/overview-format.ts::snapshotNote()`: label tanggal data yang BENAR-BENAR
  dipakai, dari `supply_recorded_at` / `demand_recorded_at` (tidak menebak dari jam
  sistem; zona Asia/Jakarta). Dirender di kartu "Pasokan terpantau".

Hasil terukur (UI hidup, BGN Monitor, 18 Okt 2026 15.46 WIB):

- sebelum: `Pasokan terpantau 5.019,56 kg · Pasokan per 4 Nov 2026 · permintaan per 8 Okt 2026`
- sesudah: `Pasokan terpantau 4.544,31 kg · Pasokan per 18 Okt 2026 · permintaan per 8 Okt 2026`
- `as_of` dari API: `2026-10-18T08:46:37Z`; Jakarta supply 270,82 kg dari baris
  `2026-10-18T00:00:00Z` (bukan lagi 314,20 kg dari 4 Nov).
- Selisih jaringan ikut menyesuaikan: +1.106,31 kg · 3 surplus · 7 shortage.

### 2. Label "N keputusan terakhir dipantau"

Feed `GET /decisions` tidak punya limit, jadi "terakhir" menyesatkan. Diganti
"`N keputusan dipantau`" (`frontend/app/page.tsx`).

### 3. Konstanta angka ajaib yang dicetak sebagai data

- `components/TodayDashboard.tsx`: `+{items.length - 6}` dipasangkan dengan
  `slice(0, 6)` → satu konstanta `MAKS_AGENDA_KEPUTUSAN`.
- `components/FoodSafetyBoard.tsx`: teks "Menampilkan 5 dari N" + `slice(0, 5)` → satu
  konstanta `MAKS_BATCH_TERLIHAT`.

## Bukan angka karangan (aturan, bukan data)

Ambang keandalan rendah 60%, jendela 48 jam, radius 150 km, zoom minimum 8 untuk pin
pemasok, skala 0–100 pada meter KPI, dan `KPI_WINDOW_MS` 24 jam.

## Perluasan deret permintaan (tindak lanjut)

Sebelumnya peta membandingkan pasokan 18 Okt dengan permintaan **8 Okt** — labelnya
jujur, tetapi dashboard "Hari Ini" jadi terasa aneh. Perbaikannya bukan menggeser
label, melainkan **melanjutkan seri permintaan** dengan aturan yang bisa diaudit:

- **Kadens**: satu observasi per hari pada 00:00 UTC (rencana menu), bukan 12 jam
  seperti telemetri pasokan — kadens dua jenis data itu tidak dicampur.
- **Nilai**: bergerak di sekitar baseline **kanonik terbaru** pasangan itu
  (baris `origin='seed'` terakhir, 8 Okt) dengan derau ±2% dan pola akhir pekan
  0,92 yang sudah dipakai seri lain. Tidak ada angka baru dari luar.
- **`needed_by`**: `recorded_at` + 3 hari, jarak yang sama dengan baris kanonik.
- **Cakupan**: hanya pasangan yang MEMANG punya permintaan kanonik → 24 pasangan ×
  27 hari (9 Okt–4 Nov) = **648 baris** `origin='demo'`. Bandung & Cianjur tetap
  `demand_state = "tidak_ada_baris"`; itu fakta yang kini tampil sebagai
  "permintaan belum ada catatan", bukan ditambal angka nol.
- **Kanonik aman**: `ON CONFLICT (lokasi, komoditas, recorded_at) DO UPDATE ...
  WHERE origin='demo'` → bentrokan dengan baris 8 Okt 12:00 tidak mengubah apa pun.
- **Bisa dibatalkan**: `DemandRecord` masuk `PURGE_MODELS`, jadi "buang data demo"
  dan `pastikan_deret_demo` ikut memulihkannya.

Hasil sesudah perluasan (`/balance/map?commodity=telur`, 18 Okt 10:06 UTC):

| | Sebelum | Sesudah |
|---|---|---|
| Tanggal pasokan | 18 Okt 00:00 | 18 Okt 00:00 |
| Tanggal permintaan | 8 Okt 12:00 | 18 Okt 00:00 |
| Pasokan 10 lokasi | 4.544,31 kg | 4.544,31 kg |
| Kebutuhan jaringan | 3.438 kg | 3.149,37 kg |
| Selisih | +1.106,31 kg | +1.394,94 kg |
| Lokasi shortage | 4 | 4 (Jakarta 707,00 · Semarang 12,05 · Makassar 12,83 · Yogyakarta 7,40) |

Nilai permintaan demo per pasangan berada pada rentang +1%…−12,5% dari baseline
kanonik (batas bawah = akhir pekan 0,92 × derau −2%), mis. Jakarta/telur 977,82–1.099,05 kg
dengan baseline 1.080 kg.

## Fakta rekomendasi ikut dibatasi `as_of` (dikerjakan)

`recommendation_service._latest_rows()` kini menerima `as_of` dan menyaring
`recorded_at <= as_of` untuk pasokan, permintaan, dan harga (`PriceSignal`).
`fetch_operational_facts()` sudah sejak awal memakai `as_of` untuk batch
(`harvested_at <= as_of`) dan kebutuhan menu; sekarang seluruh tujuh elemen facts
berbicara tentang waktu evaluasi yang sama. `as_of=None` = sekarang, bukan
"selamanya".

Buktinya bukan asersi kosong: dengan data demo yang berjalan sampai 4 Nov,
`/balance/recommend` sebelum perbaikan memakai harga 30.834,06 dan sesudahnya
30.305,95 (baris 15 Okt) untuk Jakarta/telur; pasokan 18 Okt 270,82 kg, bukan
314,20 kg dari 4 Nov.

Tes baru `tests/test_recommendation_as_of.py` (3 tes) memaku tiga hal: tidak ada
baris masa depan untuk pasokan/permintaan, snapshot historis 8 Okt memberi angka
kanonik, dan harga yang dipakai juga terbatas waktu evaluasi.

Satu tes lama perlu disesuaikan, bukan dilonggarkan: `test_decisions_persist_and_get_validity`
dulu memakai rekomendasi rank 1 global. Dengan fakta yang benar, rank 1 bisa
menuju kota di luar scope penguji (Jakarta) sehingga ditolak 403 — sesuai aturan
scope. Tes kini memilih kandidat teratas yang tujuannya Jakarta, jadi yang diuji
tetap "keputusan tersimpan dan bisa dibaca", bukan urutan ranking global.

## Gerbang

- Backend: `tests/test_balance_map.py` 9/9 (3 tes baru: peta tidak memakai baris masa
  depan, `as_of` eksplisit, panel satu lokasi memakai batas yang sama),
  `tests/test_balance_data_state.py` 5/5, `tests/test_api_decision_intelligence.py` 8/8.
- Frontend: `tests/overview-format.test.ts` 7/7; suite penuh 107 berkas / 1.262 tes;
  `tsc --noEmit` EXIT=0; `next lint` bersih.
- Rujukan yang ikut disesuaikan: helper acuan DB di `test_balance_map.py` dan
  `test_api_decision_intelligence.py` kini memakai `recorded_at <= now()` — batas yang
  sama dengan endpoint — supaya tes tidak membandingkan baris masa depan.

## Catatan lingkungan

DB dipakai bersama sesi lain: selama audit terlihat `price_signals` 4.054 baris
(harapan 4.040) dan jumlah keputusan bertambah dari 21 → 26. Angka di dokumen ini
adalah snapshot waktu pengukuran, bukan baseline baru.

## Baseline 10×4 (beras) — angka terverifikasi 2026-10-18 20.20 WIB

Komoditas keempat (beras) resmi masuk, jadi baseline kanonik menjadi 10 lokasi ×
4 komoditas (pasokan seed 40 baris, harga referensi 40, pemasok 38 = 17 kanonik +
24 baris demo − 3 overlay). Angka di bawah dibaca dari UI, lalu dicocokkan ke DB
dengan batas yang sama seperti endpoint (`recorded_at <= now()`).

**Telur, nasional (BGN Monitor):** 4.556,15 kg pasokan · 3.149,37 kg kebutuhan
jaringan · 145% · selisih +1.406,78 kg · 4 surplus / 6 shortage / 10 terpetakan ·
label satu tanggal "Data per 18 Okt 2026".
DB: `sum` pasokan pada stempel terbaru per lokasi = 4.556,15; permintaan terbaru
8 lokasi + 2 tanpa catatan = 3.149,37 (Bandung & Cianjur ditulis "permintaan
tanpa catatan", bukan nol).

**Telur, Jakarta (SPPG Head):** 288,26 kg pasokan (mock_sap, 18 Okt 12:00 UTC) ·
977,82 kg kebutuhan (demo, 18 Okt 00:00 UTC) · 29% · kurang 689,56 kg.
DB: pasokan 288,26; permintaan 977,82; selisih 689,56 — cocok sampai sen.

**Beras, nasional:** 10.744,69 kg pasokan · 10.175,02 kg kebutuhan · 106% ·
+569,67 kg · 3 surplus / 7 shortage · label "Data per 18 Okt 2026".
DB: pasokan 10.744,69; permintaan 10.175,02 dari 8 lokasi (2 tanpa catatan).
Permintaan beras hanya dibuat untuk pasangan yang punya baseline kanonik — bukan
disamakan rata, dan bukan diisi nol.

Peta tetap menampilkan satu waktu data, bukan waktu fetch: "Live Sync" hanya
menyebut jam pembaruan UI, sedangkan kartu KPI menyebut tanggal DATA.

## Gerbang setelah baseline 10×4

- Backend penuh: 1.126 passed / 3 skipped / 0 failed (EXIT=0, 658,50 s) pada DB
  sunyi; tidak ada deadlock/FK/unique violation di log.
- Frontend penuh: `tsc --noEmit` EXIT=0; vitest 108 berkas / 1.282 tes; `next lint`
  bersih; `next build` 4/4 halaman (rute `/` 401 kB).
- `ruff check` bersih untuk 10 berkas backend yang disentuh. `ruff format --check`
  TIDAK dipakai sebagai gerbang di repo ini: `core.autocrlf=true` membuat semua
  berkas CRLF sehingga ruff selalu minta reformat.

## Tiga tindak lanjut audit (dikerjakan 18 Okt 2026 malam)

**1. Label peta: jam sinkron dipisah dari tanggal data.** Dulu peta menulis
"terakhir diperbarui 20.20.22 WIB" dari jam fetch, sehingga terbaca sebagai waktu data.
Sekarang dua hal itu tegas: `Sinkron HH.MM.SS WIB` (= `syncLabel()`, jam polling) dan
`Data per 18 Okt 2026` (= `snapshotNote()`, dibaca dari `*_recorded_at`). Prop
`updatedAtLabel` di TopBar ternyata tidak pernah dirender (kode mati) dan ikut dihapus.
Bukti UI: pill "Sinkron 20.47.38 WIB" bersamaan dengan kartu "Data per 18 Okt 2026";
teks "terakhir diperbarui" = 0 kemunculan.

**2. Panel detail memakai snapshot peta (`as_of`), bukan jam sendiri.**
`GET /balance/{lokasi}/{komoditas}` sudah menerima `as_of`; kini frontend mengirimkannya
lewat `balancePath()` dari `as_of` respons `/balance/map`. Bukti: klik "Muat kondisi"
di Demo Control memicu
`/balance/Jakarta/telur?as_of=2026-10-18T13%3A48%3A38.431813%2B00%3A00`.
Yang tetap berbeda waktu secara desain: keputusan (`/decisions`), batch (`/batches`),
dan KPI 24 jam — domain lain dengan jamnya sendiri, bukan angka yang bisa dibandingkan
langsung dengan peta.

**3. Geometri rute jalan: `overview=full`, bukan `simplified`.**
`simplified` hanya ~36 titik untuk rute 110 km sehingga sudut jalan terpotong di zoom
tinggi. Cache `road_routes` disinkronkan ulang: 15 rute, rata-rata 4.166 titik
(min 72 untuk rute 2,5 km, maks 14.901), total 3.258,9 km. API `/supplier-routes`
menyajikan Cianjur→Jakarta 3.041–3.058 titik (sebelumnya 36). Cache hidup di DB,
jadi ukurannya tidak membebani repo.

Gerbang pada perubahan ini: frontend 110 berkas / 1.291 tes lulus, `tsc` EXIT=0,
`next lint` bersih, `next build` 4/4 halaman. Backend penuh: **1.134 lulus, 6 gagal**
pada run 20.30–21.02. Diagnosis awal ("aturan approve hanya setelah verdict mematahkan
tes lama") TERBUKTI SALAH: keenam tes itu lulus semua (14 passed) saat dijalankan tanpa
suite lain. Akarnya sapuan `_sapu_sisa_test()` yang menghapus SEMUA user `%@test.local`
di awal/akhir tiap sesi pytest — suite sesi lain yang berjalan bersamaan menghapus user
milik run ini, sehingga login berikutnya 401 "email atau password salah" dan terbaca
seperti regresi pagar approval. Perbaikan: sapuan dibatasi `created_at < now() - interval
'15 minutes'` (`33e74fb`), diuji dengan user `uji-baru`/`uji-lama` (yang baru HIDUP,
yang berumur satu jam HILANG).

Gerbang penuh berikutnya (00.00–00.15) tetap merah, tetapi sebabnya kini terukur:
`supply_records origin='seed'` berisi 160 baris saat run dan 80 setelahnya (kontrak 40),
`price_signals` seed 114 (kontrak 57) — penyeed dijalankan dengan acuan "sekarang" oleh
sesi lain yang masih menyunting `backend/app`. Nilai per barisnya identik dengan kanonik
(contoh: telur Jakarta 300 kg, hanya `recorded_at` bergeser), jadi angka UI tidak berubah;
yang patah adalah tes yang memaku jumlah baris. Gerbang penuh hanya sah setelah sesi itu
selesai dan baseline dipulihkan (40/57/224/70, 5.160 demo).
