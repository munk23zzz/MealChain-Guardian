# Audit angka frontend vs database — 18 Okt 2026

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
