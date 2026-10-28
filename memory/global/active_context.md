## Kondisi saat ini (2026-10-27, Fase 12 MG)
- Dokumentasi Fase 12 diselaraskan: `docs/DemoRunbook.md` (baru), `docs/Architecture.md`,
  `docs/Schema.md`, `docs/Skill.md`, `docs/PRD.md`, `sap-joule/docs/peta-skill-joule.md`,
  `sap-joule/docs/runbook-cf-joule.md`, `docs/verification/AGENTCORE_STATUS.md`.
- Geladi tiga mode dijalankan pada DB klon `mealchain_r12` + stack `mcg-f12`
  (backend 18100, frontend 13110): replay 22/22, realtime (lihat `_qa/f12/out/`),
  operasional 6/6. Joule lima skill diuji pada jembatan lokal 18091.
- Gate suite penuh pada DB terpisah: 50 gagal / 2077 lulus / 31 skip — sebab dianalisis di
  `MG/phase-12-docs-rehearsal.md` (batch REF basi + `fuse_evidence` konservatif), bukan
  regresi kode demo. Butir 7 Fase 12 masih `OPEN`.
- Jembatan CF hidup tetapi backend tidak resolve; **tidak** dipush ulang (menunggu izin).
- JANGAN: menyimpulkan "suite hijau" dari laporan lama, atau mengklaim Joule/AgentCore live
  tanpa bukti baru.

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

## 2026-10-16 — Supervisor Agent Strands + Event 1 penuh dari UI (Hermes)

- **Pertanyaan pemilik:** "apakah supervisor agent sudah terimplementasi??" → jawabannya dua entitas berbeda:
  (1) tahap narasi supervisor di backend (`supervisor_client.run_supervisor`, sudah jalan) dan
  (2) **Supervisor Agent Strands SDK** — yang ini dulu **tidak ada** meski dokumen menyebut "BLOCKED live".
- **Sekarang (1) + (2) dua-duanya ada.** Berkas baru: `agent/supervisor_agent.py`, `agent/prompts/supervisor_system_prompt.md`, `agent/requirements.txt`.
  Hello-world LIVE ke Bedrock `us.anthropic.claude-haiku-4-5-20251001-v1:0` **3,4 dtk** (akun 624606539664); tes kontrak (Strands di-mock) **4 passed**.
- **Masih Blocked:** deploy agent ke AgentCore Runtime (`AGENTCORE_RUNTIME_ARN`/`AGENTCORE_GATEWAY_URL` = 0 char) dan penyambungan agent ke orkestrator Event 1 (orkestrasi masih di `backend/app/services/event1_orchestrator.py` + klien REST).
- **Event 1 bisa dipicu aplikasi:** `POST /demo/event1` + tombol "Jalankan Event 1 penuh" (OpsConsole, tab Demo Control) → **201 dalam 26,2 dtk**, supervisor `narrated` (`primary:sap_ai_core`), 7 langkah DETECT→…→SUPERVISE.
- **`frontend/next.config.js`**: `experimental.proxyTimeout: 180000` (bawaan Next memutus di 30 dtk → pipeline bisa terlihat "gagal" di UI walau keputusan sudah tertulis).
- **Gerbang 2026-10-16:** backend `863 passed / 3 skipped` + ruff bersih; frontend `736 passed / 67 berkas` + `tsc --noEmit` 0 + `next lint` 0 — semua hijau (kegagalan kontrak `proxy-roots` sudah ditutup dengan mendaftarkan root `/safety` & `/freshness`, lihat butir Fase 11 di bawah). **Terbaru (17 Okt, setelah opsi "Lainnya"):** frontend **800 lulus / 68 berkas** · `tsc` 0 · `next lint` 0 · backend 7 tes baru `/receipts` hijau (lihat butir terakhir).
- **Fase 11 — Keamanan Pangan ber-cakupan (16 Okt, permintaan pemilik "terapkan semua, fitur harus jalan dengan backend & database"):** tab Keamanan Pangan tidak lagi menampilkan daftar lintas lokasi sebagai default peran SPPG. (1) cakupan "Lokasi saya — Jakarta" jadi default + chip "Semua lokasi (pengawasan)" di kepala kartu tabel; (2) kartu **"Pasokan masuk menuju …"** dari `GET /supplier-routes` + satu kalimat cakupan dari `GET /balance/map` (terukur di Jakarta: "Kebutuhan 1.080 kg · tersedia 300 kg → kurang 780 kg; kiriman 800 kg menutup kekurangan (+20 kg)"; Supplier A Cianjur · 110,4 km jalan · ±84 menit); (3) kolom LOKASI → **ASAL** saat ber-scope sendiri; (4) masa layak diterjemahkan jadi chip keadaan (Kedaluwarsa / ≤48 jam / ≤7 hari), bukan cuma "kesegaran 0%"; (5) kartu **"Keputusan keamanan lokasi ini"** dari feed ber-scope + tombol buka Decision & Evidence.
- **Fase 11 — dua jalur tulis yang hidup (bukti DB, bukan pratinjau):** "Periksa kiriman"/"Uji ulang" → `POST /freshness/evaluate` + `POST /safety/evaluate` → DB `freshness_score 0,90 → 0,66`, `usable_until 2026-11-07 → 2026-10-25`, dan pesan di layar "Hasil periksa dari server: keamanan PASS · kesegaran 66% · layak s/d 25 Okt". "Ajukan ulang" → `POST /actions/repropose` 201 → keputusan baru (iterasi 2, `supersedes_id` terisi), jumlah keputusan 183 → 184.
- **Fase 11 — akar yang wajib diingat:** (a) `/actions/repropose` (backend `app/api/actions.py:541`) menolak **409** kecuali `status == "rejected"` DAN ada `rejection_reason` — jadi tombol itu HANYA untuk keputusan ditolak, bukan yang kedaluwarsa; (b) setiap path API baru wajib didaftarkan di DUA tempat: `frontend/lib/api.ts` DAN `API_ROOTS` di `frontend/next.config.js` — tanpa itu tombol membalas 404 HTML dari Next sendiri ("Tidak bisa memeriksa: HTTP 404: /freshness/evaluate"); tes kontrak `tests/proxy-roots.test.ts` menjaga keduanya tetap sinkron; (c) `useSupplierRoutes` menerima `forceEnabled` supaya tab Keamanan Pangan ikut memuat rute kiriman TANPA menambah tab ke `shouldLoadSuppliers` (daftar itu mengatur pin peta di `lib/supplier-pins.ts` — jangan diubah).
- **Fase 12 — kotak "Info map" + perjalanan kiriman ber-estimasi tiba (16 Okt, permintaan pemilik "untuk teks legenda map ganti menjadi info map … ketika mengaktifkan jalur kiriman tampilkan juga waktu estimasi sampai … pastikan sinkron dengan database").** Temuan SEBELUM: `batch_id` dikirim `"None"` untuk semua rute (identitas kiriman hilang), `harvested_at` tak pernah dikirim, dan **DB tidak punya jam keberangkatan** → ETA apa pun = angka karangan; isi legenda juga tidak mengikuti lapisan yang hidup. Perubahan: (1) DB — migrasi `015_batch_dispatch` (`batches.dispatched_at` TIMESTAMPTZ NULL = belum berangkat, CHECK `dispatched_at >= harvested_at`) + seed `dispatch_offset_hours` per batch (Jakarta −1 j → tiba +24,3 mnt dari REF = di jalan; Surabaya −5 j → tiba +4 j; Cianjur/Bogor sudah tiba; Bandung NULL = belum berangkat); (2) API — `journey` (`state`/`eta_at`/`travel_min`/`remaining_min`/`progress`/`arrives_before_usable_until`) + `summary.journey_states` di `/supplier-routes`, `batch_id` asli, `route_key`, `harvested_at`; modul murni `app/core/journey.py`. (3) UI — chip & `aria-label` "Info map"; isi mengikuti lapisan hidup; entri "gagal uji" hanya bila ada kiriman bergaris gagal; blok "Perjalanan kiriman" (maks 3 baris + "+N kiriman lain"); tag bilah `2 jalur kiriman · 1 di jalan · tiba terdekat ± 22.54`; popup garis menambah jam berangkat/ETA/sisa/batas layak. Gerbang: backend 900 passed/3 skipped, frontend 736 passed/67 berkas, `tsc` 0, `next lint` 0.
- **Fase 12 — akar yang wajib diingat:** (a) **jam tiba TIDAK pernah dihitung di peramban** — angka datang utuh dari `journey`; kalau jam berangkat NULL, estimasi tidak dibuat (keadaan jujurnya `belum_berangkat`) dan kalau waktu tempuh belum ada, keadaannya `tidak_diketahui` (jangan pernah merendernya sebagai "sudah tiba"); (b) **estimasi tiba tidak disimpan di DB** — dihitung saat baca supaya tidak ada dua sumber kebenaran; (c) dengan **REF kanonik 8 Okt 12:00 UTC**, semua perjalanan hari ini terbaca "sudah tiba" (jujur, bukan bug) — untuk demo hidup tekan **"Segarkan ke hari ini"** di Demo Control (seeder menaruh ulang seluruh offset relatif `now`); (d) 2 tes merah `test_kpi_act_trace` & `test_kpi_safe_delivered_cost` = **residu data demo** (1 keputusan `status='executed'` sisa sesi sebelumnya membuat metrik sah-sah saja `available`); bersihkan lewat "Bersihkan data demo", bukan dengan melonggarkan tes; (e) `harvested_at`/`dispatched_at` yang baru dibuka di payload diuji dengan **membandingkan langsung ke baris DB** (`read + assert`), jadi kalau ada yang mengubah query tanpa update payload, tesnya merah.
- **Fase 12 — tiga baris popup dibuang (16 Okt, permintaan pemilik lanjutan):** *"Jarak lurus: 78,4 km, Tiba sebelum batas layak (25 Okt 2026) dan ini Jalur jalan 1,41× jarak lurus (jalan berkelok, bukan garis lurus) hapus saja."* Yang hilang dari popup klik garis: `Jarak lurus: …`, rasio `1,41×`, dan kalimat `Tiba sebelum batas layak (…)`. Yang tetap: `Jalur jalan (OSRM): 110,4 km · ± 84 menit`, `Berangkat: …`, `Estimasi tiba: ± 22.54 WIB · 24 menit lagi`, `Layak dipakai s/d 7 Nov 2026` (tanggal layak pakai ditulis SEKALI — jadi tidak ada fakta yang hilang), dan `Mutu kiriman: GAGAL UJI …`. **Peringatan `Estimasi tiba melewati batas layak pakai` SENGAJA dipertahankan** (itu menandai masalah nyata; yang dibuang cuma kalimat yang menenangkan) — tawarkan hapus kalau pemilik minta. `straightKm`/`ratioVsStraight` tetap dikirim server (halaman Keamanan Pangan + kartu Kiriman masih memakai). Tes: di tingkat POPUP yang dirender (klik garis palsu → periksa `.map-popup-line`), bukan hanya fungsi murni — tiruan `FakePopup` di `tests/supply-map-layer.test.tsx` kini punya `setLngLat`/`addTo` + `popupLog`, dan `FakeMap.fire(event, payload)` meneruskan event.
- **Fase 11 — opsi "Lainnya" di kartu "Penerimaan barang" (17 Okt, permintaan pemilik "jika bagian Penerimaan barang di tambah lainnya yang dapat di isi manual bagaimana?" → diklarifikasi "maksud saya ada opsi 'Lainnya' jadi user dapat mengisi sesuai keadaannya walau tidak ada kondisi yang sesuai dengan ceklis").** Sebelum menulis kode, skema diperiksa: `batches` TIDAK punya kolom catatan (hanya `temperature_log` JSONB untuk suhu) → menyimpan tanpa tabel = mengarang. Hasil: (1) migrasi `016_batch_receipts` — tabel `batch_receipts` (id uuid, `batch_id` FK cascade, `checked` JSONB = snapshot titik periksa, `other_note` TEXT NULL, `recorded_by` FK users NOT NULL, `recorded_at` timestamptz default now(), indeks `(batch_id, recorded_at DESC)`); (2) router baru `backend/app/api/receipts.py` — `POST /receipts` 201 + `GET /receipts?batch_id=&limit=5` (terbaru dulu, tiap baris membawa `checked_count` yang dihitung server); (3) UI — `RECEIVING_OTHER` (label + contoh) + `<textarea>` 500 karakter, BUKAN titik periksa ke-6 sehingga "N dari 5 titik" tidak berubah arti; `checkedForReceipt()` mengirim snapshot LENGKAP lima titik; `receiptRows()` menormalkan balasan; riwayat "Catatan penerimaan tersimpan (dari database)" dimuat lewat prop `loadReceipts` (efek per batch, hasil terlambat dibuang). **Aturan yang dipegang:** mencatat = `MUTATING_ROLES` **dan** `assert_in_scope(user, batch.location_id)` → batch lokasi lain = **403** (barang diterima di dapur sendiri; terbukti di tes), membaca bebas semua peran terautentikasi (pengawas nasional membaca ✓, mencatat ✗ 403); catatan berisi spasi saja disimpan **NULL** (layar bisa bilang "tidak ada catatan"); akar `receipts` ditambahkan ke `API_ROOTS` (kontrak `proxy-roots` hijau). **Bukti hidup (SPPG Head, Jakarta):** catatan 102 karakter "Karung lapis kedua basah kena hujan, isi masih kering. Timbangan gudang rusak, berat ikut surat jalan." + 2 titik dicentang → layar "Catatan penerimaan tersimpan. 2 dari 5 titik periksa sudah ditandai… Hasil dari server: keamanan PASS · kesegaran 65% · layak s/d 25 Okt, 13.59."; **setelah halaman dimuat ulang, kedua catatan tetap tampil** (dibaca ulang dari `GET /receipts`); DB diperiksa langsung dengan psql: 2 baris, `kemasan=true, suhu=true, warna=false`, `recorded_by` = SPPG Head Demo.
- **Fase 11 — dua butir lanjutan (16 Okt, "sekarang lanjutkan"):** (6) kartu **"Penerimaan barang"** — lima titik periksa petugas (kemasan/suhu/bau-warna/timbang ulang/lot) + pemilih batch (default = kiriman yang sedang datang bila bisa dipasangkan) + tombol "Catat hasil terima & hitung ulang"; daftar periksa waktu itu TIDAK dipersistensikan (backend belum punya kolomnya) — sejak migrasi `016` justru DISIMPAN (lihat butir opsi "Lainnya" di atas); terukur: menandai 2 → kalimat "2 dari 5 titik periksa sudah ditandai — tandai sisanya sebelum barang dipakai.", klik → DB `freshness_score 0,90 → 0,65`, `usable_until 2026-11-07 → 2026-10-25`, pesan "Hasil dari server: keamanan PASS · kesegaran 65% · layak s/d 25 Okt, 14.56". (7) tombol **"Ajukan keputusan"** per baris (hanya baris GAGAL UJI) → `POST /events/safety-disruption` (Event 3): server menilai ulang dari log suhu; batch gagal → 201 keputusan `safety_disruption` + bukti suhu + jejak, batch aman → 200 `no_disruption` (layar bilang "tidak ada keputusan baru"). Terukur di Jakarta: klik pada baris gagal Surabaya → "Keputusan penanganan dibuat: 0f230339 (status: diusulkan) — menyasar Jakarta", keputusan 188 → 189 dan kartu keputusan 85 → 86. **Aturan Event 3 yang dipegang komponen:** `operation_key` = kunci idempotensi per batch (dibuat sekali di komponen, dikirim ulang saat mengulang → server melayani dari catatan, bukan keputusan kembar); `target_location_id` WAJIB lokasi pemakai sendiri (ruling 2026-10-14) jadi diambil dari `/auth/me`, BUKAN dari baris yang diklik; batch pemicu boleh milik lokasi lain (sisi sumber). Kelas CSS baru: `.safety-pick`, `.safety-checks` (matikan `::before` titik amber milik `.board-list` — titik itu berarti "mendesak", bukan "diperiksa"), `.safety-row-actions`. (Kalimat "tandai sisanya sebelum barang dipakai" dihapus 20 Okt 2026 — lihat decisions.md; kartu sekarang menulis "… belum diperiksa. Boleh disimpan sebagian." dan pesan sesudah simpan memakai bentuk lampau.)
- **17 Okt — kerapian halaman Decision & Evidence (keluhan user: "tampilannya sangat kurang"):**
  pemilih keputusan kini punya label terlihat + "N menunggu tindakan · M keputusan tersedia" (`countActionable`,
  satu sumber dengan lonceng); `FactList` menerima prop `collapseEmpty` sehingga baris fakta "—" masuk
  `<details class="fact-more">` ("N rincian belum ada datanya") — **kartu Governance sengaja TIDAK di-collapse**
  (di sana "—" = tidak ada penghalang); strip **"Langkah berikutnya"** (`.evidence-next`) dari `nextStep()` di
  `lib/evidence.ts` (peran pengawas dapat kalimat "bersifat pengawasan"). Kartu gelap `.integrity-trust` tetap
  gelap — itu keputusan desain, bukan kelalaian. Kelas CSS baru: `.evidence-picker*`, `.evidence-next*`,
  `.fact-more`, `.fact-list-empty`. Tinggi halaman contoh 2004px → 1772px. Gate: `tsc=0`, `next lint=0`,
  `tests/evidence-summary.test.ts` 40 + `tests/decision-evidence.test.tsx` 23 lulus (2 gagal di suite penuh =
  tes BARU sesi paralel `tests/board-scroll-hint.test.ts` + `scroll-hint-component.test.tsx`, berkas `??` milik mereka).
- **17 Okt — kalender agenda langkah 3: pemicu ikon + popup pemilih tanggal (permintaan pemilik).**
  Judul bulan di header kartu "Hari Ini" dulu `<span>` mati dengan navigasi hanya ‹ › (melompat setahun = 12 klik).
  Sekarang judul bulan = tombol ber-ikon kalender (`aria-haspopup="dialog"`) yang membuka **popup pemilih tanggal**:
  dropdown **Bulan** (12 nama Indonesia) + **Tahun** (2026–2027 dari `RANGE_MIN/RANGE_MAX` di `lib/demo-data.ts`,
  selalu menyertakan tahun yang tampil) + grid hari berpenanda catatan + "Hari ini"/"Tutup". Tombol ‹ › dan grid besar
  TETAP. Berkas baru: `components/AgendaDatePicker.tsx`, `components/AgendaMonthGrid.tsx` (grid dipakai bersama kartu &
  popup); diubah: `lib/agenda.ts` (`monthChoices`, `pickerYears`), `lib/hooks/useAgenda.ts` (saklar `enabled` kelima),
  `TodayAgendaCalendar`, `TodayDashboard` (satu prop `agendaPicker`), `app/page.tsx` (bulan DRAFT), `NavIcon`
  (`CalendarIcon`), `app/globals.css`. **Aturan:** bulan draft TIDAK menimpa bulan kartu; rentang draft hanya diambil
  saat popup terbuka; bulan yang belum termuat = status MEMUAT (bukan grid kosong); fokus kembali ke pemicu saat tutup;
  memilih tanggal hanya memberi tahu halaman (`onSelect`). **Gate:** 25 uji baru RED→GREEN → frontend **80 berkas / 945
  uji hijau**, `tsc` 0, `next lint` 0. **Live (SPPG Head):** draft September mengisi titik September sementara kartu tetap
  Oktober; klik 1 Sep → panel "Selasa, 1 September 2026" 1.217 porsi · pasokan 6 baris (cocok langkah 2); Tahun 2027 →
  0 hari bercatatan; Escape → fokus kembali ke pemicu; 0 galat JS baru. Detail: `docs/verification/kalender-pemilih-tanggal.md`.
- **17 Okt — DESAIN BARU halaman Decision & Evidence (riset pola + referensi, atas permintaan user):**
  urutan region berubah dari urutan tabel → urutan keputusan manusia: `evidence-hero` (kepala keputusan:
  status berkata-kata, jendela berlaku, judul AKSI `decisionHeadline`, strip metrik `decisionMetrics`,
  "Perlu diperhatikan (N)" `attentionFlags`, "Langkah berikutnya" `nextStep` (kini biru accent-soft —
  instruksi bukan bahaya), "Kalau disetujui/ditolak" `consequences`) → `evidence-route` (`approvalRoute`:
  4 langkah Diajukan→Verifikasi→Persetujuan→Eksekusi dengan "siapa/apa berikutnya", keadaan punya teks
  `.sr-only`) → `evidence-decide` `#zona-keputusan` (tombol persetujuan NAIK ke atas; `DecisionActions`
  & gating 1b/2b/3b TIDAK diubah) → `evidence-grid` (Biaya | Keamanan & pemasok | Identitas & tenggat)
  → `evidence-bottom`. `RecommendationCard` dilepas dari halaman ini (tetap dipakai di feed).
  Rencana + rujukan riset: `_qa/rencana-decision-evidence-v2.md`. Tes baru: 13 murni
  (`tests/evidence-summary.test.ts` 53 total) + 6 markup (`tests/decision-evidence.test.tsx` 29 total).
  Kelas CSS baru: `.evidence-hero*`, `.evidence-metric*`, `.evidence-flag*`, `.evidence-consequence*`,
  `.evidence-route-*`, `.evidence-decide`. Ukuran judul 24px; tinggi halaman 2030→2813px (konten lebih
  informatif). Catatan mesin: `search.py --design-system --persist` gagal di drive E: (exFAT tanpa hard link).
- **17 Okt — Decision & Evidence LANJUTAN 2: lini masa audit + umur jujur + ekspor satu tombol** (murni `auditTimeline`/`windowUsage`/`catatanUnik` di `lib/evidence.ts`).
  Kartu "Riwayat iterasi" DIGANTI **"Jejak & riwayat"** (`components/DecisionAudit.tsx`): satu lini masa bercerita — iterasi keluarga (`/decisions/{id}/chain`) → pengajuan (+`proposed_by`) → verifikasi (waktu TIDAK ada di DB → "waktu tidak tercatat") → tiap baris `/approval-summary` (label peran manusia, waktu, komentar).
  Baris approval tanpa `approved: true|false` TIDAK lagi jadi "Ditolak" (klaim palsu yang ketangkap dari dump markup); catatan verifier yang cuma salinan huruf-kecil putusan ("consistent") tidak diulang. Umur jendela = chip "Jendela terpakai N%"/"Jendela lewat" (`windowUsage`) — SENGAJA tanpa ember karangan (tidak ada target waktu-ke-keputusan di data).
  Ekspor: `downloadDossier()`/`dossierFileName()` (lib/export.ts) → tombol "Unduh bukti (JSON)" di kepala keputusan, umpan balik `role="status"`; terverifikasi hidup ("Bukti terunduh sebagai dossier-3860992a-….json"). Badge kasus demo dikembalikan ke kepala keputusan via `caseLabelOf()` yang kini DIEKSPOR dari `RecommendationCard` (kelas `.rec-case` dipakai ulang).
  Kontrak komposisi `tests/sidebar-wiring.test.tsx` disesuaikan (`<DecisionAudit` + `caseLabelOf` menggantikan `<RecommendationCard`). Tes: evidence-summary + decision-evidence = **95 lulus**; gate tsc=0, lint=0; sisa merah hanya `tests/supply-map-layer.test.tsx` (milik sesi paralel: "baris legenda ringkas tidak ada"). Docs: `docs/design.md` bagian "Langkah 2", skill `references/merapikan-halaman-bukti.md`.
- **17 Okt — Decision & Evidence LANGKAH 3 selesai: bahasa, tautan bersama, sentuh.**
  `frontend/lib/bahasa.ts` (BARU, 13 tes): humanizeBlocker/blockingReasons/safetyLabel/agentLabel/executionTargetLabel/roleList — memetakan kalimat yang BENAR-BENAR dikirim approval_summary.py + actions.py (termasuk yang terbungkus pesan galat); string tak dikenal dikembalikan apa adanya. Dipakai di nextStep, consequences, approvalFacts (Alasan tertahan + Peran penyetuju), safetyFacts (status keamanan/Verifikator/Target eksekusi), decisionFacts, approvalRoute, auditTimeline, dan pesan dialog DecisionActions.
  Deep link ?keputusan=<id> (frontend/lib/decision-link.ts, 9 tes): dibaca sekali saat mount -> tab + keputusan; pilihan berikutnya menulis URL; pindah tab melepas param. Tautan di luar cakupan peran -> keadaan "Keputusan itu tidak ada di cakupan akun ini"; selama data diambil -> "Memuat keputusan..." (prop loading baru, decisionsQuery.isPending).
  375px terukur via iframe same-origin: luapan horizontal 0px, tombol Unduh 138x44, tautan "Ke zona keputusan" 121x24 (min-height 24 + 44 di pointer coarse), kepala 134px, aria-label "Jejak keputusan" pada <ol>. aria-sort TIDAK dipasang (halaman ini tidak punya tabel); pintasan j/k/a/r juga bukan milik halaman ini.
  Sisa kebocoran yang ikut dibersihkan saat verifikasi layar: approvalRoute/consequences ("target MOCK") -> executionTargetLabel; ComplianceEvidencePanel ("PASS n - FAIL n - NEEDS_VERIFICATION n") -> safetyLabel; SupplierExclusionPanel ("LOCAL . SPPG", UUID mentah, "Batch FAIL tetap tidak eligible") -> Lingkup lokal / #id pendek / kalimat manusia; ApprovalModal ("Batch FAIL tetap diblokir", "EXCLUDED (FAIL)", worst_status mentah, target LOCAL) -> gagal pemeriksaan / safetyLabel / `Lokal (tanpa PO)`.
  Pemindaian teks layar final (keputusan pengecualian pemasok): LOCAL/FAIL/MOCK/PASS/NEEDS_VERIFICATION/requirement/sppg_head/eligible = 0 kemunculan; "target Lokal (tanpa PO)" terbaca.
  Gate final: tsc=0, 93 berkas / **1131 tes lulus, 0 gagal**, next lint=0. Tes yang sengaja diubah (label enum -> bahasa manusia): evidence-summary, decision-evidence, supplier-exclusion-panel (3), supplier-governance-ui (1). Docs: docs/design.md LANGKAH 3 + skill references/merapikan-halaman-bukti.md.

- **17 Okt — desain ulang "Hari Ini" selesai** (pemilik: hapus grid bulan di kartu, info tetap dipakai, redesain 1 halaman, fitur tetap).
  Kartu "Kalender agenda" → **"Agenda harian"**: grid bulan besar tidak lagi dirender di kartu (terukur 0 `.agenda-cell`), judul = hari terpilih,
  `‹`/`›` = **satu hari** (mati di tepi `RANGE_MIN`/`RANGE_MAX`), pil "Hari ini", ikon kalender = popup pemilih tanggal.
  Tambah **strip ringkasan 5 tile tombol** + urutan status→pengecualian→agenda→rincian dan bento **2 kolom** untuk 4 kartu rincian.
  Murni baru: `summaryTiles`, `updatedLabel`, `kpiPeriodLabel` (lib/today.ts), `agendaGroups`/`clampDayStep`/`dayOf` (lib/agenda.ts).
  Gerbang: **85 uji fokus hijau**, tsc 0, next lint 0 (suite penuh 1031/1032 — 1 merah milik sesi lain di DecisionEvidence/sidebar-wiring).
  Verifikasi hidup 1262 px: 5 tile @181 px, bento 2×465,5 px, kartu agenda 947 px, luapan 0; probe 331 px: 0 luapan.
  Bug tertangkap saat pengukuran (bukan oleh tes): kartu agenda sempat 64 px karena `span 12` hilang → diperbaiki.
- **Menunggu pemilik:** (a) deploy agent ke AgentCore (butuh ARN/Gateway), (b) perbaikan `.env` yang belum dieksekusi: `INFERHUB_URL` kurang suffix `/chat/completions` (25 slot 404), model id verifier `cb/gpt-6-astra` → `cx/gpt-6-astra`, supervisor `fallback_1` Bedrock `claude-sonnet-4` (Legacy/mati), serta 4 tes host-only yang merah (`test_verify_agentcore_access.py`, `test_verify_bedrock_access.py`, `test_compose_contract.py`, `test_environment_contract.py`), (c) commit/push Fase 11 & Fase 12 (belum ada commit).


- **19 Okt — popup "Governance & persetujuan" di-restyle (permintaan pemilik).**
  Latar `.popup-backdrop`: `rgba(248,250,252,.2)` + `backdrop-filter: blur(8px)` (tanpa saturasi; diturunkan bertahap 20→15→8 karena pemilik ingin latar masih samar-samar) —
  menggantikan kabut 66% + saturasi dari keputusan pagi hari yang sama; tes CSS diperbarui ke kontrak
  baru. Isi: ringkasan bukti jadi kartu fakta `<dl>` (10 baris), chip status jadi strip + meter 240 px,
  tiap pilihan tindakan jadi kartu ber-stripe sesuai dampak, emoji ⛔ → ikon SVG, kaki sticky dengan
  hint Esc. Hanya dialog ini yang berubah (`Popup` dapat prop `className="popup-governance"`);
  pemilih tanggal & karantina tetap. Gerbang: vitest 1359/119, tsc 0, build 0; diukur di :3010.
  Rincian + angka terukur: `docs/design.md` §17.

- **19 Okt — dock "Ke zona keputusan" di-redesign** (permintaan pemilik). Pil 720 px radius 999 →
  dock 560 px radius 14 dengan titik nada keadaan, hierarki dua baris (keadaan → hitungan approval),
  CTA "↓" sepadan dengan tautan kepala keputusan, safe-area iOS, animasi 240 ms (dimatikan
  `prefers-reduced-motion`), cetak disembunyikan, ≤560 px memadatkan tanpa membuang informasi.
  Posisi TETAP DI TENGAH (sempat dicoba full-width mengikuti sidebar, dikoreksi pemilik).
  Gerbang: vitest 120/1368, tsc 0, build 0. Rincian: `docs/design.md` §18.

- **19 Okt — sesi demo langkah 2 selesai: jam sistem terpusat.** `app/core/clock.py`
  (murni) + `demo_clock_service.py` (DB) + `ClockMiddleware` (header `X-Sim-As-Of`/
  `X-Sim-Mode`) + tabel `demo_clock`/`demo_session` (migrasi `023_demo_clock_session`).
  25 situs `datetime.now(timezone.utc)` → `clock.now()`; body enam endpoint gerbang
  membawa `sim_as_of`. Gate: lihat laporan langkah. Berikutnya: generator + skrip
  timeline (langkah 3 rencana di `E:\hackathon\HackathonAWS\_qa\rencana-sesi-demo-1jam.md`).

- **19 Okt — sesi demo langkah 3 selesai.** Kolom `session_id` di 12 tabel
  (migrasi `024_session_scope`), generator deterministik
  `app/seed/demo_session_seed.py` (1.454 baris/sesi, 0,40 s, idempoten), skrip
  `app/seed/data/demo_timeline.json` + validator `demo_timeline.py`. Gate di klon
  `mealchain_sim`: 15 tes lulus, sidik data reguler identik, klon sudah di-drop.
  Berikutnya: tick engine (langkah 4).

- **20 Okt (malam) — R29 nav "lompat ke bagian" jadi komponen bersama.** `SectionJump` +
  `useActiveSection` + `lib/section-jump.ts`; dipasang di **Keamanan Pangan** dan **Overview**,
  sengaja TIDAK di halaman lain (alasan per halaman: `docs/design.md` §24). Gaya
  `.section-jump`/`.jump-target` sekarang di `globals.css` (bukan `evidence-dossier.css` lagi).
  Gerbang frontend: 150 berkas / 1.671 tes lulus, `tsc` 0, `next lint` 0 error. Verifikasi live di
  :3010 (SPPG Head). Berikutnya: tidak ada yang menggantung dari pekerjaan ini.

- **28 Okt — Overview: panel "Monitor harga komoditas" menggantikan tiga bagian lama.** Sumber
  nyata PIHPS Bank Indonesia (harian, Pasar Tradisional, Rp/kg): tarik dengan
  `cd backend && python scripts/tarik_harga_pihps.py --days 30 --provinsi demo --komoditas all`
  (±5 menit, 168 permintaan, ~8.500 baris, snapshot 2 MB di `data/harga_pihps/`). Panel membaca
  `GET /price/monitor`; logika potong jendela ada di `backend/app/core/harga_monitor.py`, logika
  tampilan di `frontend/lib/price-monitor.ts`. Yang dilepas dari Overview (komponennya TETAP ada):
  `ShipmentCard`, `NodeTelemetry`, `StatusLocationList`. Jebakan yang sudah terbukti: (a) permintaan
  ke bi.go.id dari TLS Python direset server → transport memakai `curl` bila ada; (b) endpoint grid
  menolak tanpa cookie sesi halaman + `X-Requested-With`; (c) filter komoditas dulu salah petakan
  (`_KE_KODE_PROYEK` dibaca sebagai nama proyek) sehingga filter tidak berlaku — sekarang
  `KOMODITAS_PROYEK[nama]`; (d) jendela hari harus dibatasi DUA ujung, kalau tidak baris bertanggal
  masa depan ikut terkirim. Pergerakan antar wilayah dihitung SERVER (`movers`) karena jendela satu
  wilayah tidak cukup untuk membandingkan.

- **28 Okt — Kartu feed Recommendations diringkas.** Permintaan pemilik: "shape rekomendasi diperkecil
  dan hapus informasi konsisten, supplier, dan kasus". Kartu sekarang = judul (+badge versi) + satu
  baris meta (kg · SDC · waktu) + status & masa berlaku sebaris di kanan + ajakan klik; tinggi terukur
  188 → 113-114 px (padding 14 px, jarak ajakan 18 px). Yang dilepas: baris "Rencana kirim dari pemasok …" (`routeLineOf()` dihapus beserta
  tesnya), badge "Kasus: …" (`caseLabelOf()` tetap hidup untuk kepala Decision & Evidence, pencarian
  feed tetap mencocokkan `demo_case`), dan narasi `verifier_note` yang mencetak verdict mentah
  "consistent"/"flagged". `rejection_reason` tetap dicetak sebagai satu baris bergaris kiri. Kalau nanti
  ada yang ingin baris pengirim kembali di feed: bangun ulang di kartu, JANGAN menghidupkan lagi
  `routeLineOf()` sebagai helper tanpa pemakai. Gerbang: 191 berkas / 2.128 tes, tsc 0, lint 0,
  gate token hijau.
  Popup detail & jejak agen (28 Okt 2026): kartu feed + antrean Hari Ini membuka `DecisionDetailPopup`
  (isi = `DecisionDetail`, dipindah dari `DecisionEvidence`) dengan dua tampilan "Detail & bukti" / "Jejak agen";
  deep link, PO, dan sidebar TETAP pindah tab. Jangan kembalikan `setTab("evidence")` ke dalam kartu feed:
  tes `tests/decision-detail-popup.test.tsx` mengunci kontrak itu. Kalau butuh navigasi antar-bagian di dalam
  popup, buat bilah sendiri — `SectionJump` menunjuk jangkar halaman.

  Popup "Detail Keputusan" (28 Okt 2026, revisi): permintaan pemilik "tetap pop up di tengah, design layout
  dan isinya yang diubah". `components/DecisionDrawer.tsx` sekarang panel TENGAH 920 px dengan isi dua kolom
  dan tiga bagian dilipat; panel samping 520 px sudah dibuang, jangan dihidupkan lagi. Kepala popup memakai
  slot `eyebrow`/`meta` milik `Popup.tsx`. Isi & angka mengikuti `D:\Downloads\01-detail-keputusan.md`
  (acuan desain, bukan kode untuk disalin). Kalau menambah bagian: taruh di grid, tandai `.detail-sec--full`
  hanya bila perlu selebar panel, dan lipat kalau isinya arsip. Tes kontrak: `tests/decision-drawer.test.tsx`
  + `tests/detail-keputusan.test.ts`.

### Modul Location Network + pop-up Pasokan & permintaan (28 Okt 2026, dokumen 03 §6)

- Tab baru **Location Network** di `frontend/app/page.tsx` (setelah Overview): `components/LocationNetworkBoard.tsx`
  = kalimat ringkasan (§6.3) + empat angka + peta `SupplyMap` dengan koridor + tabel 6 kolom + panel lokasi
  terpilih + chip kelengkapan (§6.5).
- Data: `GET /balance/map` (lokasi, `supply_state`/`demand_state`, `*_recorded_at`) dan **endpoint baru**
  `GET /balance/flows` (agregat `decisions`: sumber→tujuan, kg, status per lane, koordinat). Pop-up memakai
  `/balance/{lok}/{kom}` + `/supply/...` + `/demand/...` + `/batches`, dan **akar proxy `supply`/`demand`
  ditambahkan ke `next.config.js`** — tanpa itu Next menjawab 404 HTML sendiri.
- Aturan yang jangan dilanggar: `tidak_ada_baris` = "tidak ada catatan", bukan 0 kg; `Number(null) === 0`
  tidak boleh dipakai untuk cek koordinat; koridor hanya untuk lane yang benar-benar ada dan menyentuh
  lokasi dalam cakupan peran.
- Tes kontrak: `tests/location-network.test.ts`, `tests/location-network-board.test.tsx`
  (+ kasus pembawa-jam di `tests/food-safety.test.ts`). Bukti lengkap: `docs/verification/location-network-supply-demand.md`.
- Jangan menambah `NODE_OPTIONS=--require` saat build: `npm run build` repo sudah memuat
  `scripts/exfat-readlink-patch.cjs`; menambahkannya lagi membuat build gagal.
- **Location Network = halaman GABUNGAN, tanpa peta (Ronde 43).** Tab `location-network`:
  kalimat ringkasan §6.3 → baris angka → pemilih lokasi (`aria-pressed`, urut terparah,
  auto-pilih yang paling kekurangan) → `SupplyDemandPanel` **inline** (4 kartu + tabel batch)
  → chip kelengkapan. Peta/koridor/`GET /balance/flows`/`useBalanceFlows` sudah DIHAPUS
  (S4-60); jangan menghidupkannya lagi tanpa keputusan pemilik. Nutritionist melihat tab &
  judul "Pasokan & Kebutuhan" (peran lain "Location Network") — jangan hilangkan: itu
  memperbaiki regresi §5 dokumen 03.
- **Location Network (Ronde 44)**: bentuk final = satu kartu ringkasan → TABEL lokasi → baris
  terbuka berisi `SupplyDemandPanel` (4 kartu + batch). Tanpa peta, tanpa chip, tanpa popup.
  Kontrak yang dijaga tes: jumlah 0 tanpa "kg", data kosong ≠ "tidak ada kekurangan", nada
  lewat `data-tone` (BUKAN kelas global — CSS module me-hash), batch ditahan berlabel "Ditahan".
  Catatan: sesi lain menulis berkas sama dengan bentuk popup (TODO S4-61); pemilik perlu
  memilih satu bentuk sebelum pekerjaan dianggap selesai.

## 2026-10-29 — Popup Recommendations
- `DecisionDrawer.tsx`: blok JSX bernama (`blokFakta`, `blokBiaya`, `blokPo`, `blokAksi(utama)`,
  `blokKewajiban(terbuka)`, …) disusun ulang per mode; `modeAksi` menambah kelas
  `.popup-keputusan--aksi`.
- `DecisionActions`: pemicu disembunyikan saat panel terbuka, gulir hanya bila kepala panel
  di luar layar, fokus balik ke pemicu.
- CSS baru di ujung `app/globals.css`: `.detail-kpi*`, `.detail-aksi--utama`, `.detail-setelah`,
  `.detail-konteks`, `.detail-jejak-kepala`, `.popup-keputusan--aksi`, `.aksi-panel .approval-menu-foot`.

## 2026-10-29 — Location Network: Langkah 3 (copy & keadaan) selesai
- Rencana `docs/plans/location-network-page-plan.md` §11 kini Langkah 1–3 SELESAI; tidak ada
  langkah lain di rencana itu (sisa = keputusan pemilik §12: nama menu, angka kolom Rekomendasi).
- Kontrak copy yang dijaga tes (`frontend/tests/location-network-langkah3.test.tsx`): satu baris
  filter + satu pil tanggal, tidak ada `<p>` > 120 karakter, memuat = 3 baris kerangka tanpa
  pil jumlah, galat total tanpa angka, kosong = satu kalimat, catatan basi menyebut jumlahnya.
- Kalimat kepala kini hanya ada di `components/LocationNetworkBoard.tsx`; jangan menyalinnya
  lagi ke `app/page.tsx` (dua salinan pernah menyimpang).

## 2026-10-29 — Decision & Evidence: bukti pemasok hidup lagi, batch ditahan terbaca

- `lib/supplier-exclusions.ts` sekarang `process.env.NEXT_PUBLIC_API_URL ?? ""` (relatif).
  Jangan kembalikan ke `|| "http://localhost:8000"`: CSP `connect-src 'self'` memblokir
  lintas-origin dan kegagalannya SENYAP (tidak ada log backend, hanya banner
  "Sebagian bukti gagal dibaca"). Gejala turunannya: panel "Supplier governance" tidak
  dirender sama sekali karena `supplierContext` null.
- `components/DecisionActions.tsx` mengekspor `ringkasanBatchPo()` (murni, diuji di
  `tests/po-dispatch-summary.test.ts`) dan `reviewPo` memakainya untuk mengucapkan
  `dikirim`/`ditahan` dari respons backend. Jangan menghapus lagi: tanpa itu keputusan bisa
  `executed` + PO `submitted` walau batch terikat ditahan dan tidak ada truk bergerak.
- Keadaan data lokal saat ini: sesi demo aktif (mode realtime, dibangun 03.46 WIB), approval
  dan timestamp template disegarkan; `375c831b` dan `bef077a8` sudah `executed` dengan PO
  `MC-375C831B78CA` / `MC-BEF077A8A935` berstatus `submitted`; tidak ada PO draft tersisa.
- Mengukur lebar sempit TIDAK perlu playwright: `_qa/ukur-viewport.cjs` (CDP + Edge headless,
  memakai `ws` dari `frontend/node_modules`). Contoh: `NODE_PATH=<repo>/frontend/node_modules
  UKUR_LEBAR=390 UKUR_AKUN="BGN Monitor" UKUR_OUT=<folder> node _qa/ukur-viewport.cjs`.
  Halaman menolak iframe (`X-Frame-Options: DENY`), jadi harness iframe TIDAK bisa dipakai.

## 2026-10-29 — Pemasok: riwayat penerimaan barang (Dok 05 §8.5)

- Kartu **Riwayat penerimaan** di tab Pemasok (`components/SupplierReceipts.tsx`), di antara
  "Daftar pemasok" dan "Register eksklusi". Sumber: `GET /receipts/riwayat` lewat
  `useReceiptHistory` (hanya dimuat saat tab Pemasok/Overview aktif).
- Logika murni di `lib/supplier-receipts.ts`. Aturan yang tidak boleh diubah tanpa membaca
  komentarnya: `ditolak` → nilai "—"; tanpa PO → "tidak tercatat"; `received_kg` null sampai
  `disetujui`; kg dipesan & diterima DUA baris, tidak dikurangkan di klien.
- Ringkasan (tiga angka di kepala kartu) datang dari server dan mencakup SELURUH cakupan; jangan
  menjumlah ulang di klien saat penyaring aktif.
- CSS di `app/supplier-receipts.css` (berkas sendiri, diimpor `app/layout.tsx`), bukan tambahan
  `globals.css`. Tabel memakai `table-layout: fixed` + lima lebar kolom; tanpa itu tabel melebar
  melewati kartu dan kolom Nilai terpotong.
- **Jangan jalankan `pytest` backend lalu mengukur/demo tanpa seed ulang**: fixture tes memakai DB
  dev yang sama dan mereset catatan penerimaan. Pemulihan:
  `docker compose exec -T backend python -m app.seed.demo_template`.
- Data demo terakhir (setelah seed): 5 catatan penerimaan — 3 `menunggu`, 1 `disetujui`
  (beras 540 kg, Rp 8.100.000, PO `MC-38D418FCB776`), 1 `ditolak` (beras 360 kg, alasan kemasan
  bocor). Dua catatan `menunggu` tanpa PO → kolom nilai "tidak tercatat" (contoh jujur, sengaja).
