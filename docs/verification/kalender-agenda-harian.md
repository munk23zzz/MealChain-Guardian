# Kalender agenda harian — langkah 1: endpoint `GET /agenda` (2026-10-16)

## Kenapa halaman "Hari Ini"

Enam kandidat diperiksa dengan data nyata, bukan selera:

| tabel | rentang | baris | sifat |
|---|---|---|---|
| `menu_plans` | 1 Sep → 5 Nov 2026 | 660 | RENCANA, 10 baris SETIAP hari |
| `supply_records` | 1 Sep → 8 Okt | 2220 | realisasi |
| `price_signals` | 1 Sep → 8 Okt | 2318 | realisasi |
| `delivery_events` | 1 Okt → 7 Okt | 70 | realisasi (≈12.000 porsi/hari) |
| `disposal_events` | 4 Okt → 7 Okt | 20 | limbah |
| `decisions` | 6 Okt → 16 Okt | 191 | aktivitas agen |
| `batches.usable_until` | 10 Sep → 2 Nov | 7 | kedaluwarsa |

Tab **"Hari Ini"** dipilih karena tiga alasan yang bisa diperiksa:

1. Halaman itu **mengklaim harian tetapi tak punya pemilih hari** — lima kartunya
   ("Menunggu tindakan", "Batch mendekati kedaluwarsa", "Lokasi shortage", "KPI 24
   jam", "Rantai audit") semuanya dihitung dari *sekarang*.
2. Ada **10 baris rencana menu setiap hari** (1 Sep–5 Nov) yang selama ini hanya
   dipakai satu angka KPI dan tak pernah tampil sebagai agenda.
3. Di endpoint, **tak ada satu pun yang menerima tanggal tunggal** sebelum ini;
   `/kpi?start&end` dan `/demo/preview|timeseries` hanya menerima rentang, dan
   pemilih tanggal satu-satunya di UI ada di panel Demo Control.

Ditolak dengan alasan: Keamanan Pangan (7 batch → kalender hampir kosong),
Surplus & Limbah (limbah hanya 4–7 Okt), Pemasok (`reference_time` ada, jadwal
harian tidak), Overview/Agent Log/Decision & Evidence (dimensi tanggalnya tipis:
191 keputusan mayoritas di hari yang sama).

## Kontrak `GET /agenda`

- `start`/`end` = tanggal ISO (YYYY-MM-DD), inklusif, diartikan sebagai **hari WIB**
  (Asia/Jakarta, UTC+7) — bukan hari UTC. Kiriman pukul 00:30 WIB masuk hari WIB-nya.
- Rentang maksimum 62 hari; `end < start`, tanggal tak sah, atau rentang kelewat
  panjang → 422; tanpa token → 401.
- 200: `period`, `scope`, `computed_at`, `days` — **satu entri per hari, tanpa
  lubang** (kalender butuh deret utuh). Per hari: `menu`, `delivery`, `disposal`,
  `supply`, `price`, `batches_expiring`, `decisions`, plus `activity` (jumlah
  bagian berisi) untuk titik penanda.
- **Bagian tanpa catatan menulis `available: false`**, bukan nol yang tampak
  terukur (aturan repo anti-angka-palsu).
- Cakupan mengikuti `app/core/scope.py`: rencana/kiriman/limbah/pasokan/harga
  ikut scope user; **keputusan memakai `target_location_id`** (aturan yang sama
  dengan `GET /decisions`, bukan menebak kolom `location_id` yang tidak ada);
  **batch lintas lokasi** seperti `GET /batches` (sisi SUMBER, bukan target SPPG).
- Read murni + idempoten (kecuali `computed_at`): 62 hari = 7 kueri agregat
  (GROUP BY hari), bukan 62×7.

## Bukti

Kode: `app/api/agenda.py` (baru, terdaftar di `app/main.py`),
`app/services/agenda_service.py` (baru).

Tes: `tests/test_agenda_api.py` — **8 uji RED → GREEN**, mencakup: deret hari tanpa
lubang, hitungan benar pada hari berdata, `available: false` pada hari tanpa
catatan, **batas hari WIB diuji dengan baris kiriman pukul 00:30 WIB** (bocor ke
hari UTC = gagal), scope SPPG sempit vs monitor luas, 422 (terbalik/kelewat
panjang/tanggal tak sah), 401, dan idempotensi. `ruff check` bersih.

Live (SPPG Head, `localhost:8000`): `GET /agenda?start=2026-10-01&end=2026-10-08`
→ tiap hari 1 rencana menu (1200 porsi), 1 kiriman (1200 porsi), 6 baris pasokan,
6–7 harga; limbah 4 kg pada 4 Okt dan 6 kg pada 7 Okt; 12 keputusan pada 7 Okt,
44 pada 8 Okt. `activity` 4–6 → titik penanda kalender terisi.

## Dua temuan samping (bukan dari kode agenda)

### 1. Deret waktu kanonik sempat terhapus — sudah dipulihkan
`GET /demo/data-status` menunjukkan `demo: 0` untuk supply/price/menu: baris
`origin='demo'` (1 Sep–5 Nov; supply 2190 · price 2274 · menu 590) hilang sehingga
KPI 30 hari dan puluhan tes kehilangan dasarnya. Penyebabnya kelas tes di
`tests/test_timeseries_db.py` + `tests/test_demo_timeseries_api.py` yang memanggil
`purge_demo_rows()` (menghapus SEMUA baris demo, bukan hanya milik tes itu) dan,
bila gagal di tengah, tidak menjalankan pemulihannya.

Dipulihkan lewat jalur resmi `POST /demo/timeseries` body `{}` (idempoten) →
kembali **persis** ke angka semula: total supply 2220 · price 2318 · menu 660
(seed 30/44/70 utuh). KPI 30 hari kembali 7/7 `available` (Meal 23,70% ·
Food Loss 0,02% · Price 3,39%).

### 2. Suite penuh belum hijau karena satu berkas tes — bukan karena agenda
Tiga run penuh berturut-turut: 81, 87, 97 gagal. Dilokalisasi:

- berkas yang "gagal" (scope_matrix 36, supplier_routes 17, sprint1_acceptance 8,
  receipts 7, tool_contracts 6, ledger 2, dossier 2) **lulus saat dijalankan
  sendiri** (52 passed) dan **lulus saat dijalankan bersama tanpa satu berkas**
  (100 passed);
- gejala terulang: `401 {"detail":"token tidak valid"}` di teardown fixture
  `demo_state` (`test_demo_timeseries_api.py:50-51`) — token yang dipakai untuk
  memulihkan DB sudah tidak sah pada saat teardown, sehingga pemulihan tak jalan;
- `test_demo_timeseries_api.py` juga berkas yang menyentuh `purge_demo_rows()`.

Kesimpulan: kegagalan massal itu **isolasi tes**, bukan regresi kode aplikasi dan
bukan berasal dari `GET /agenda`. Perbaikan yang tepat (belum dikerjakan, menunggu
keputusan): jangan pernah mem-purge deret kanonik dari tes — sisipkan penanda tes
pada rentang/milik sendiri, atau bangun ulang deret kanonik di teardown yang
dijamin jalan.

## Langkah 2 — kalender di tab "Hari Ini" (UI)

Berkas baru: `frontend/lib/agenda.ts` (fungsi murni), `frontend/lib/hooks/useAgenda.ts`,
`frontend/components/TodayAgendaCalendar.tsx`. Diubah: `lib/api.ts` (`fetchAgenda`),
`lib/query.ts` (`queryKeys.agenda`), `components/TodayDashboard.tsx`, `app/page.tsx`,
`app/globals.css`, `next.config.js` (`API_ROOTS`).

Keputusan yang dipegang:

1. **Fungsi murni dulu.** Semua aritmetika kalender (grid 42 sel mulai Senin,
   rentang, pindah bulan lintas tahun, "hari ini" menurut WIB, baris ringkasan
   hari) ada di `lib/agenda.ts` dan diuji tanpa DOM. Komponen tinggal merender.
2. **Bulan & hari terpilih dimiliki HALAMAN**, bukan komponen — kalau state ada di
   komponen, hook tak bisa menerimanya dan penanda hari aktif bisa berasal dari
   sumber berbeda dengan yang diminta ke server (dipaku `tests/agenda-wiring.test.ts`).
3. **Komponen tidak memanggil API.** Data masuk lewat props; hanya
   `lib/hooks/useAgenda.ts` yang memanggil `fetchAgenda` (Rules.md §3).
4. **Rentang yang diminta = rentang grid yang terlihat** (42 hari, di bawah batas
   62 hari kontrak API), jadi tidak ada bulan yang menampilkan hari tanpa catatan
   karena datanya tidak diambil.
5. **Bagian tanpa catatan menulis "tidak ada catatan"**, bukan "0 porsi"/"0 kg" —
   aturan anti-angka-palsu repo; diuji dengan batas kata, karena `"1.200 porsi"`
   MENGANDUNG teks `"0 porsi"`.
6. **`API_ROOTS` di `next.config.js` wajib ditambah.** Tanpa akar `agenda`, request
   jatuh ke router Next sendiri dan membalas 404 HTML (bukan JSON) — inilah yang
   terjadi saat verifikasi hidup pertama, dan sudah diperbaiki.
7. **Celah UX ditemukan lewat verifikasi hidup, bukan tes:** klik "Hari ini" dari
   bulan lain memilih 17 Okt tetapi grid tetap di bulan lama, sehingga hari aktif
   tak terlihat. Diperbaiki: memilih hari ikut memindahkan bulan.

Bukti tes: 15 uji baru (8 `tests/agenda.test.ts`, 5
`tests/today-agenda-calendar.test.tsx`, 7 asersi wiring di
`tests/agenda-wiring.test.ts`), semuanya RED lebih dulu. Gerbang frontend akhir:
**73 berkas / 854 uji hijau**, `tsc` 0 error, `next lint` bersih.

Bukti di browser hidup (`localhost:3010`, SPPG Head, tab "Hari Ini", kalender
berada tepat di bawah header halaman):

- grid 42 sel, header "Oktober 2026", 40 sel punya titik penanda (activity 1–6),
  hari aktif 2026-10-17 (WIB) — tepat satu sel ber-`aria-current`;
- panel 17 Okt: Rencana menu **1.115 porsi · 1 lokasi merencanakan**; Kiriman
  tiba / Limbah dibuang / Pasokan tercatat / Harga tercatat / Batch kedaluwarsa →
  "tidak ada catatan"; Keputusan agen **18 (11 diusulkan, 3 ditolak, 3 menunggu
  persetujuan, 1 ditandai verifikator)**;
- klik sel **2 Okt**: Rencana menu 1.200 porsi · Kiriman tiba 1.200 porsi (1
  kiriman) · Pasokan tercatat 6 baris · Harga tercatat 6 baris;
- tombol ‹ → **September 2026**, grid 31 Agu–11 Okt, panel 1 Sep (rencana 1.217
  porsi, pasokan 6 baris) — rentang baru benar-benar dimuat, bukan data lama;
- klik "Hari ini" dari bulan lain → grid kembali ke Oktober 2026 dengan 17 Okt
  bertanda (perbaikan celah UX di atas).

Angka itu **dicocokkan ke DB**, bukan ke fixture: `menu_plans` Jakarta
17 Okt = 1115; `decisions` target Jakarta tanggal WIB 17 Okt = 11 `proposed`,
3 `rejected`, 3 `pending_approval`, 1 `verifier_flagged` (total 18);
2 Okt = rencana 1200 / kiriman 1200.

Gerbang suite BACKEND masih berstatus sama seperti temuan 2 di atas (isolasi
`test_demo_timeseries_api.py`), bukan efek langkah ini: endpoint agenda 8/8 hijau,
dan 100 uji lintas-berkas lulus saat berkas bermasalah itu dikecualikan.

