# Active Context — MealChain Guardian

> Satu file yang dibaca PALING AWAL tiap sesi build. Update tiap akhir sesi / tiap perubahan arah.
> File ini menjawab: "sekarang lagi di mana, next step apa, jangan sentuh apa."

## Kondisi saat ini (2026-10-15)
- **Track rencana 2026-10-14 (cakupan peran · pemasok di peta · rentang data demo): Fase 0–7 SELESAI
  (7a+7b+7c).**
  Rincian + status tiap fase: `TODO.md` § "Track rencana 2026-10-14", plan di
  `.hermes/plans/2026-10-14_scope-pemasok-peta-rentang.md`.
- Yang sudah ada di kode: cakupan per peran (peran SPPG → lokasi sendiri, `403` untuk lokasi
  lain), `GET /suppliers` + migrasi `012_supplier_profile`, tab Pemasok dari endpoint nyata +
  pin pemasok di peta, `origin`/`generated_at` + kunci upsert (migrasi `013_origin_generated_at`),
  panel "Data & rentang waktu" di tab Demo Control.
- **Fase 7 SELESAI 2026-10-15 (7a data, 7b aturan tampilan, 7c bukti).** Data: 21 pemasok demo
  (12 klaster Jakarta berkoordinat absolut + 9 hub lain), DB 35 pemasok, 14 kanonik utuh. API:
  `GET /suppliers?max_distance_km=…&commodity=…` mengembalikan `distance_km`/`distance_reference`/
  `reach`; tanpa rujukan → 422. UI: peta peran SPPG hanya memasang pin dalam jangkauan 150 km +
  kalimat "N dari M … tidak dipasang di peta", halaman Pemasok punya kolom Jarak + penyaring
  "Hanya dalam jangkauan" (semua baris tetap ada, yang jauh diberi label). Bukti:
  `docs/verification/fase-7.md`.
- Alasan Fase 7: peta `telur` untuk SPPG Jakarta dulu memunculkan 10 pin termasuk Medan …
  Malang; setelah 7b pemasok jauh tidak lagi tampil sebagai pemasok Jakarta (tetap terlihat
  untuk `bgn_monitor`).
- **F8 SELESAI 2026-10-15 — tab gabungan "KPI & Kualitas Agen"** (permintaan pemilik): strip
  "Target KPI Demo Day" dihapus dari halaman KPI (`components/KpiTargets.tsx` + CSS `.kpi-target*`
  dibuang; `tests/prd-nav.test.tsx` sekarang memaku KETIADAANNYA), lalu tab **KPI** + **Kualitas Agen**
  digabung jadi satu tab ber-id `"kpi-kualitas"` (nama dipilih pemilik; urutan KPI dulu; "Rincian per
  run" tetap penuh). Komposisi: `components/KpiQualityBoard.tsx` (tipis — isi `KPIDashboard`/
  `AgentQualityBoard` tidak diubah). Gerbang muat `/kpi` dipersempit ke `today || kpi-kualitas`
  (`lib/kpi.ts::shouldLoadKpi`) — tab Hari Ini tetap terisi. Bukti: `docs/verification/fase-8.md`.
- **F7d SELESAI 2026-10-15** — jarak pemasok (kaki pertama) masuk biaya SDC. Modul murni
  `backend/app/core/supplier_leg.py`; `fetch_operational_facts` mengembalikan elemen ke-7 (peta
  `(supplier_id, lokasi) → km`) sementara 6-tuple kontrak Task 9 tetap sah; biaya angkut = kaki
  pertama + linehaul (300 Rp/km/ton); `cost_breakdown` bertambah `transport_linehaul`,
  `transport_supplier_leg`, `supplier_leg_km`, `supplier_leg_reference` + alias `logistics`. Panel
  biaya Decision & Evidence memecah baris angkut bila pecahannya ada. Gerbang: pytest 782 lulus /
  3 skip, ruff bersih, vitest 545, tsc 0, lint 0 (build tidak dijalankan — dev hidup).
- **F9 SELESAI 2026-10-16 — data pemasok: profil kanonik + "sedang mengirim"** (permintaan pemilik).
  Audit: 14/14 pemasok kanonik kosong profil; hanya 3 dipakai batch. Profil kanonik kini **diturunkan
  dari batch kiriman** (`backend/app/seed/supplier_profile.py`; komoditas = total kg terbesar, seri →
  batch terbaru, masih seri → kosong; sertifikasi = nilai terbanyak; **kapasitas tidak diturunkan**),
  seeder mengisi **hanya celah kosong** → A/B/C Cianjur = telur + HACCP, 11 kanonik tanpa batch tetap
  kosong. "Sedang mengirim" = batch **`usable_until >= sekarang`** (`app/core/supplier_shipping.py`),
  dikirim sebagai kunci `shipping` per baris `GET /suppliers`; di peta jadi **cincin** pada pin
  (`map-pin-supplier-shipping`), bukan nada kelima; tabel Pemasok menampilkan kalimat kiriman.
  Saat itu 2 pengirim aktif (A: 3 kiriman/1.400 kg telur s/d 2 Nov; B: 1 kiriman/600 kg s/d 26 Okt,
  1 gagal uji — dilaporkan). Bukti: `docs/verification/fase-9.md`, skrip
  `backend/scripts/verifikasi_pemasok_kirim.py`. Gerbang saat itu: pytest 806 lulus / 3 skip, ruff
  bersih, vitest 552 lulus/60 berkas, tsc 0, lint 0. **Angka yang bergeser di Fase 10**: A kini
  **4 kiriman/2.200 kg** (kiriman Jakarta ditambahkan), dan tanggal B→Surabaya menjadi **1 Nov 2026**
  (REF kanonik saat seeder F10 dijalankan) — silang di akhir `docs/verification/fase-9.md`.
- **F10 SELESAI 2026-10-16 — garis jalur kiriman (pemasok → tujuan) MENGIKUTI JALAN** (permintaan
  pemilik: "dimap ada seperti garis mengikuti jalur dari suplier ke tujuan"). Keputusan pemilik:
  rute **OSRM** (bukan garis lurus), geometri diambil **saat seeding/sync lalu di-cache di DB**
  (bukan saat peta dibuka → demo offline-aman & server OSRM demo tidak dibanjiri). Tabel baru
  `road_routes` (migrasi `014_road_routes`; kunci = koordinat 4 desimal → idempoten), modul murni
  `app/core/road_route.py` (urutan **lon,lat** OSRM dikunci di satu tempat), penyimpan
  `app/seed/road_routes.py` (hanya kiriman `usable_until >= now`; jaringan mati tidak menggagalkan
  seeding), CLI `scripts/sync_road_routes.py`, endpoint **`GET /supplier-routes`** (cakupan per peran
  ditegakkan server; tiap baris bawa `road` ATAU `road_missing_reason`, tidak pernah keduanya).
  Kiriman demo baru menuju Jakarta (angka dari pemilik): **A Cianjur → SPPG Jakarta, telur 800 kg,
  s/d 7 Nov 2026, pass** → sekarang **5** rute di cache (Cianjur→Jakarta **78,35 km lurus vs 110,4 km
  jalan = 1,41x**, 36 titik). Frontend: `lib/supplier-routes.ts` (murni), hook `useSupplierRoutes`,
  rewrite proxy `/supplier-routes`, layer MapLibre garis putus-putus + popup klik + sakelar
  "Tampilkan/Sembunyikan jalur kiriman (N)" (aktif bawaan) + legenda, pembukaan tampilan **sekali**
  saat jalur pertama tiba (pin Cianjur dulu di luar bingkai peta Jakarta). Kelas DOM **`ship-route`**
  (`route-line` sudah milik signature login). Bukti: `docs/verification/fase-10.md`, skrip
  `backend/scripts/verifikasi_rute_jalan.py` (API vs SQL, jarak jalan >= lurus) exit 0. Gerbang:
  pytest **851 lulus / 3 skip** (naik dari 806), ruff bersih, vitest **588 lulus/61 berkas** (naik dari 552/60: +26 peta, +10 kolom tabel), tsc 0, lint 0
  (`next build` tidak dijalankan — `next dev` hidup). **Kolom "Jalur kirim" di tabel Pemasok**
  menyusul hari yang sama (permintaan pemilik "yaudah deh tambahin saja"): baris utama = jalur
  TERPENDEK yang geometrinya sudah ada, tanpa lencana warna (lencana milik kolom Status), jarak
  lurus TIDAK diulang, dan empat keadaan dibedakan (`—` / `…` / `belum disinkronkan` / `jalur
  tidak tersedia`); ringkasan "Jalur kiriman (jalan) N dari M". Bukti layar BGN Monitor: A Cianjur
  `→ Cianjur · 3,2 km jalan · +3 tujuan`, B Cianjur `→ Surabaya · 730,8 km jalan`, 33 baris `—`,
  ringkasan `5 dari 5`. Vitest **588**. Rincian: `docs/verification/fase-10.md` §8.
- Sprint 4 IN PROGRESS — Roy yang menandai DONE, jangan ditandai agent.

## Next step (urutan eksekusi)

➡️ **Track rencana 2026-10-14 TUNTAS** — Fase 0–8 termasuk **Fase 7d** (jarak pemasok masuk
   biaya SDC, `docs/ruling-2026-10-15-jarak-pemasok-biaya.md`, bukti `docs/verification/fase-7d.md`):
   transport = kaki pertama (pemasok → SPPG sumber, dari koordinat) + linehaul, tarif 300 Rp/km/ton;
   skor/eligibilitas tidak bergeser; koordinat kosong → biaya 0 + label, tidak ditebak.

➡️ Kandidat penyempurnaan berikutnya (belum diminta pemilik):
   (a) **kiriman aktif hanya 2 pemasok** (A/B Cianjur) karena definisi "sedang mengirim" memakai batch
   yang sudah ada — kalau demo butuh lebih banyak pengirim di peta, itu keputusan data baru (angka kg +
   tujuan harus dari pemilik); (b) `capacity_kg_per_week` kanonik masih kosong (tidak ada sumber data);
   (c) 11 pemasok kanonik tanpa batch tetap tanpa komoditas/sertifikasi;
   (d) utang lama yang belum ditutup: `TEST_DATABASE_URL` (suite pytest masih menulis ke DB demo →
   residu `users`/`decisions`), fixture 4 kasus skrip di `app/api/demo.py`, rotate `SIGNING_KEY_HEX` +
   `POSTGRES_PASSWORD`, dan header tunggal halaman gabungan KPI & Kualitas Agen.

➡️ (konteks lama, sudah selesai) **Fase 7 — pemasok mock yang benar-benar terjangkau SPPG Jakarta.** Keputusan sudah dikunci
(plan §7.4, 2026-10-15): klaster Jabodetabek + penyangga Jawa Barat ≤ ~150 km, 10–12 pemasok,
jarak berjenjang 0–25 / 25–60 / 60–150 km (Bekasi, Depok, Tangerang, Bogor, Cisarua/Puncak,
Karawang, Subang, Cianjur). Alasan: peta `telur` untuk SPPG Jakarta sekarang memunculkan
**10 pin termasuk Medan … Malang** (bukti layar di TODO.md F6) — tidak masuk akal untuk demo juri.
Parameter `max_distance_km` + cakupan jarak di UI dijadikan fase tersendiri setelahnya.

1. Sesuaikan `data/seed/suppliers_demo.json` + pemuatan seeder ke klaster Jakarta.
2. Pastikan 14 pemasok kanonik (kunci 14 kutipan harga) TIDAK diganggu.
3. Perbarui tes data pemasok + `docs/Schema.md` (jumlah pemasok per hub ikut berubah).
4. Verifikasi ulang: pytest, tsc/vitest, dan bukti layar peta (jumlah + jarak pin).

## Jangan disentuh / jangan dilakukan
- Jangan tandai Sprint 4 selesai — milik Roy.
- Jangan buat `.env.example` (sudah dihapus permanen, aturan secrets).
- Jangan stop/restart container tanpa cek bind-mount dulu (app bind-mounted → restart cukup).
- Jangan ubah angka/label safety-critical di UI tanpa jalur core deterministik.
- **Jangan tekan "Segarkan ke hari ini"** di DB demo — seeder memindahkan tanggal snapshot
  kanonik (8 Okt 12.00 UTC) dan tes yang memaku tanggal itu akan gagal.
- **Jangan longgarkan cakupan per peran** tanpa ruling tertulis baru
  (`docs/ruling-2026-10-14-scope-lokasi.md`).
- **Jangan jalankan `next build` saat `next dev` hidup** di kontainer frontend: chunk jadi 404
  dan halaman kehilangan hidrasi sampai kontainer di-restart.

## Keputusan terakhir yang mengubah arah
- 2026-10-16: **Halaman Pemasok dirapikan — F12c** (permintaan pemilik *"pada halaman pemasok anda
  gunakan skill ui ux … shape teks harus enak di lihat juga tidak kebesaran maupun ke kecilan"*).
  Diukur dulu (akun SPPG Head, viewport 1262 px), bukan ditebak: tabel **1025 px di wadah 913 px**, kolom
  "Hub"+"Koordinat" 178 px, `.shipping-tag` memuat kalimat penuh → **membungkus 3 baris (186×63 px)**,
  tinggi baris 74/79 px tak rata, kartu "Ringkasan" **466 px dari 947 px**. Sesudah: tabel **7 kolom**
  ("Hub"+"Koordinat" jadi baris kedua sel Pemasok via `supplierMetaLine`) → **913 = 913 px, 0 geser**;
  **satu standar pil** untuk `.reach-tag`/`.shipping-tag`/`.shipping-tag-fail` (12 px, `2px 8px`,
  `inline-flex`, `nowrap`) → **22 px** setara pil kepala halaman, kalimat panjang pindah ke `title`;
  pil jangkauan hanya menyebut keadaan (`directoryReachTagLabel`) karena km sudah ada di kolom Jarak
  sebelahnya; "Ringkasan" jadi selebar halaman dengan fakta berkotak (`auto-fit minmax(240px,1fr)`);
  `routeCellLabel` melepas `" jalan"` (nama kolom sudah "Jalur kirim") sehingga pil status dapat 35 px
  dan berhenti turun baris. Hasil: baris **54 px (34/35)**, tabel 2386→1925 px, halaman 3669→3046 px,
  skala teks halaman 12/13/14/20 px (**tidak ada < 12 px**). Gerbang: frontend **792 lulus / 69
  berkas**, `tsc` 0, `lint` 0, live 0 error baru. Bukti `docs/verification/fase-12.md` §6; belum ada
  commit/push.
- 2026-10-16: **Peta Overview (tab Overview) — 2 sakelar lapisan diperkecil
  panel lipat + gerak UI dirapikan** (permintaan pemilik). Strip catatan dua kalimat selalu tampil →
  diganti bilah `.map-layer-info`: tombol kecil "Rincian lapisan peta" + tag angka SELALU terlihat
  ("7/9 pemasok dalam 150 km", "1 jalur kiriman · jalur jalan OSRM"), kalimat jujur penuhnya masuk
  panel lipat (isi TIDAK dihapus dari DOM → penyaringan jangkauan tidak jadi penyembunyian).
  Peringatan "perbesar peta" tetap di luar panel. Sakelar: 34→26px, pil terukur 350×42 → 203×32 px,
  teks yang terlihat jadi "Pemasok (7)"/"Jalur kiriman (1)" (state via `aria-pressed`, kalimat
  "Tampilkan/Sembunyikan…" jadi tooltip); font tetap 12px & target sentuh 44px di sentuh/mobile.
  Gerak: panel buka–tutup mulus (grid `0fr→1fr`), chevron, legenda & popup masuk, pin hover —
  semuanya mati di `prefers-reduced-motion`. Gerbang: 699 tes / 67 berkas, tsc=0, lint=0
  (build tidak dijalankan: `next dev` hidup). Belum ada commit/push. — `docs/design.md` §3.1/§4.
- 2026-10-16: **Fase 9 — rail diperkecil + panah lipat dibalik + ujung atas skala font turun.**
  Rail desktop: item 44→38px, ikon 18→16px, label 13px (batas sentuh 44px tetap dijaga di perangkat
  sentuh & mobile). Panah tombol lipat: arah ditentukan komponen, `rotate(180deg)` di CSS dibuang
  (itu yang membuat rail tertutup menampilkan `<`). Skala: page 22→20, metric 28→24, hero 44→36
  (tetap 8 langkah). Koreksi: klaim Fase 8 soal penyeragaman judul halaman tidak terbukti di dua
  selector — kini `.page-header h1`/`.overview-header-title h1`/`.settings-title` semuanya `--fs-6`.
  Gerbang: tsc=0, 667 tes, lint=0, harness 0 luapan. Belum ada commit/push.
- 2026-10-16: **Fase 8 — skala tipografi 8 langkah + rail dirapikan** (permintaan pemilik, dipandu
  skill `ui-ux-pro-max`). Token `--fs-1..--fs-8` = 12/13/14/16/18/22/28/44 + `--lh-*` + `--track-*`
  menggantikan 24 ukuran berbeda (termasuk 11px, pecahan 12,5/13,5/14,5/15,5, `0.8rem`); token lama
  `--text-micro/--text-meta` dihapus. 243 deklarasi `font-size` kini 100% token; judul halaman
  seragam 22px, angka metrik seragam 28px. Rail: brand 64px (= top bar), item 44px, ikon kotak tetap
  18×18, tombol ikon 32×32; rail terlipat 68px kini benar-benar terpusat (ikon = avatar = tombol
  lipat = 34). Dua heading yang jatuh ke bawaan peramban (21px/16,38px) dan 4 selector judul sisa
  Fase 7 ikut diperbaiki. Gerbang: tsc + 667 tes + lint + harness responsif 0 luapan. Belum ada
  commit/push. Bukti: `…\hermes\cache\scratch\fase7\` (SQL/skrip ukur + PNG rail).
- 2026-10-16: **Fase 7 (responsive + audit aksesibilitas) selesai — redesign Arah 4 TUNTAS (Fase 0–7)**.
  29 kombinasi peran×tab di 375/768/1024/1440 px: 0 luapan halaman (Pengaturan@375 dulu 10 px),
  0 fokus tanpa cincin, temuan ● axe 123 → 0. Kunci: token `--safe-ink-tint` untuk teks di atas tint
  hijau (4,49:1 → 5,19:1; `--status-safe` tidak diubah), satu h1 per halaman tanpa lompatan tingkat
  (prop `level` di `PageHeader`), `contain: paint` + hint geser untuk tabel Pengaturan (WCAG 1.4.10),
  target checkbox 295×19 → 295×44 px. Pelajaran mahal: `max-width: min(320px, 100%)` di dalam flex
  membuat induknya meluap 236 px — batasi INDUK, bukan elemennya. Sisa terbuka (keputusan pemilik):
  role pada 3 pin peta, favicon (F5 dilewati), plus temuan data Fase 4–6. Bukti + harness di
  `…\hermes\cache\scratch\fase7\`; dokumen di `_qa/rencana-redesign-ui.md` + `docs/design.md`.
- 2026-10-16: **Fase 6 redesign (Hari Ini, Demo Control, Pengaturan) selesai** — Hari Ini jadi bento
  12 kolom (Menunggu tindakan span 7 × 2 baris; batch & shortage span 5; KPI + rantai audit baris
  penuh), chip sisa waktu = pil + dot (lewat merah, ≤48 jam amber memakai `DUE_SOON_HOURS` yang ada,
  jam belum siap → tanpa klaim), sapaan "Selamat …, <peran>" lewat slot `eyebrow` baru di
  `PageHeader`, baris "kurang N kg" pindah ke kelas sendiri (`today-due-short`). Cacat ditemukan &
  diperbaiki: media query lama `@media (min-width:1080px){.today-pending{span 2}}` menimpa bento
  (kartu jadi 145 px) → aturan dihapus. Demo Control: empat blok jadi kartu ber-chip urutan
  (Langkah 1–4), `OpsConsole` naik jadi kartu, pratinjau `writes:false` berlencana "pratinjau —
  tidak menulis apa pun", baris hasil backend mono. Pengaturan: kontrol radius 10px + chip "belum
  disimpan" pada baris yang draft-nya berbeda. Gerbang: tsc + 667 tes + lint. Fase 7 (responsive +
  audit a11y) BELUM dikerjakan.
- 2026-10-16: **Fase 5 redesign (Keamanan Pangan, Surplus & Limbah, Pemasok) selesai** — Keamanan
  Pangan: 3 tile angka besar ber-tint status (tint hanya bila keadaan itu ADA — "0 gagal uji"
  tidak diberi warna bahaya), pagar bahaya 4px di kotak blokir batch gagal, titik amber di daftar
  batch mendesak. Surplus: neraca jadi aliran 2 angka besar + panah SVG; panah jadi netral lewat
  `data-kosong` bila salah satu sisi tak punya angka (tidak menggambar aliran yang tak terbukti).
  Pemasok: kolom Keandalan jadi bar mini 0–100 (`reliabilityMeter()` di lib/suppliers-board.ts,
  TDD; ambang memakai `LOW_RELIABILITY` yang ada = 0,6; skor tak ada → "—" TANPA bar),
  `SupplierExclusionPanel.module.css` pindah dari hex palet lama ke token tema. Gerbang: tsc +
  663 tes + lint. Temuan data (bukan bug): `/balance/map` peran SPPG hanya lokasi sendiri →
  rencana alokasi surplus kosong pada seed sekarang; surplus ada di Cianjur/Bogor yang hanya
  terlihat peran global (yang tak punya tab Surplus) — keputusan demo milik pemilik.
- 2026-10-16: **Fase 4 redesign (KPI & Kualitas Agen + Agent Log) selesai** — kartu KPI jadi angka
  besar mono 32px + **bullet bar** dari `bulletOf()`; **target/ambang TIDAK dikarang** karena
  envelope `/kpi` tidak mengirimnya — bar hanya untuk metrik berskala sendiri (persen) + catatan
  arah perbaikan; nilai null/teks/negatif → tanpa bar (bukan 0%). Agent Log: chip umur langkah
  terakhir dari `step_at` (`lib/agent-trace.ts`), titik berdenyut untuk langkah baru, **shimmer
  hanya bila data menyatakan berjalan** (tabel `agent_traces` tak punya kolom status), durasi
  `duration_ms` kini tampil, panel provider jadi chip (warna bukan satu-satunya pembawa makna).
  Konsol tetap terang — permukaan gelap hanya sekali di app (kartu kepercayaan Fase 3).
  Logika murni: `lib/kpi.ts` + `lib/agent-trace.ts`, 19 tes baru (TDD). Gerbang: tsc + 660 tes + lint.
- 2026-10-16: **Fase 3 redesign (Recommendations + Decision & Evidence) selesai** — kartu lewat
  tenggat diredam lewat permukaan `--surface-sunken` (bukan `opacity`: 0,7 → teks sekunder ~3:1,
  gagal AA) + lencana "Lewat tenggat"; feed masuk bertingkat (`feed-row-in`, mati pada
  reduced-motion); Decision & Evidence jadi bento (hero 2 kolom, tiga kartu fakta span 4,
  baris bawah 5fr/7fr, form supplier-exclusion jadi baris penuh setelah Governance);
  **kartu kepercayaan gelap** `.integrity-trust` (#0F172A, token `--trust-*`) khusus bukti
  kripto — daftar pengukuran & tombol ekspor tetap terang; modal approval radius 16 + aksen
  kiri 4px. Gating 1b/2b/3b tidak disentuh. Temuan yang diperbaiki: nilai rupiah terpecah di
  kartu span-4 (label pindah ke atas nilai khusus `.evidence-grid`). Gerbang: tsc + 641 tes + lint.
- 2026-10-16: **Fase 2 redesign (Overview) selesai** — strip KPI jadi bento 12 kolom berbobot
  5/3/4 (tile hero = selisih pasokan 44px bernada + baris mini lokasi), kartu "Perlu keputusan"
  di samping peta (sumber `notifList` yang sama dengan lonceng top bar), basemap redup lewat
  filter kanvas (pin DOM tetap menyala), dan grafik "Pasokan per Lokasi" **pindah ke baris
  selebar halaman** karena kolom samping peta hanya menyisakan 68px. Logika murni baru
  `lib/overview-bento.ts` (TDD, 21 tes). Gerbang: tsc bersih + **641 tes** + lint bersih.
  Catatan: `ResponsiveContainer` setinggi 0 bila tinggi datang dari `min-height`/`auto`.
- 2026-10-16: arah visual dikunci **"Bento Modern" (Arah 4)** — rail & top bar jadi TERANG fros
  (membalik "rail biru" 9 Okt), aksen biru `#2563EB`, font Fira Sans + Fira Code. Eksekusi 7
  fase bertahap; Fase 0 (token) & Fase 1 (kerangka) selesai, gerbang tiap fase = `tsc` + 620
  tes frontend + `next lint` + tangkapan layar. Rencana di `_qa/rencana-redesign-ui.md` (di luar
  repo). Warna status TIDAK dicerahkan (alasan AA).
- 2026-10-15: Fase 7 dikunci — pemasok demo dipindahkan ke klaster Jabodetabek + penyangga
  Jawa Barat; item `max_distance_km`/cakupan jarak di UI jadi fase tersendiri.
- 2026-10-15: panel "Data & rentang waktu" ditaruh SEBELUM konsol pemicu skenario di tab
  Demo Control (urutan kerja: siapkan data → picu skenario → analisis); pratinjau dipicu tombol.
- 2026-10-14: ruling cakupan lokasi per peran — peran SPPG hanya lokasi sendiri (selain data
  sumber pemasok); `bgn_monitor` read-only lintas lokasi dan TIDAK boleh menyentuh `/demo/*`.
- 2026-10-10: paket akses SAP diterima → S4-10 dibuat; SAP AI Core = jalur murah tanpa
  sewa S/4HANA (cloud ERP mahal, dikeluarkan dari rencana — "real SAP" = model AI nyata,
  data tetap mock sampai Sprint 5 ON-DEMAND).
- 2026-10-10: BL-01 naik ke Sprint 4 sebagai S4-11.
- 2026-10-09: navigasi 5 tab PRD 2.4 + MapLibre GL + paket integrity 1–6.

## Vault map
- [[project-memory]] — fakta proyek & aturan hidup-mati
- [[decisions]] — log keputusan bertanggal
- [[architecture]] — peta arsitektur & struktur folder

## Verifikasi S4-09d (2026-10-10)
- Frontend: Vitest 138 passed; TypeScript, lint, dan production build exit 0.
- Backend: pytest 595 passed; Ruff clean; Alembic current/head `011_supplier_exclusions`.
- Approval summary now shares authoritative batch→supplier binding with execute; unbound legacy decisions remain blocked. Harvests newer than captured `as_of` are excluded at the SQL boundary.
- Runtime: `/health` 200; unauthenticated compliance probe 401.
- Browser Playwright fresh: tiga role × 375/768/1440 px, 10 location rows, document width sama viewport; late commodity response tetap menampilkan wortel.
- SAP real tidak diaktifkan; mock default dan unsupported mode fail-closed.
