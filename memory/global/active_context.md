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
- Sprint 4 IN PROGRESS — Roy yang menandai DONE, jangan ditandai agent.

## Next step (urutan eksekusi)

➡️ **Track rencana 2026-10-14 TUNTAS** — Fase 0–8 termasuk **Fase 7d** (jarak pemasok masuk
   biaya SDC, `docs/ruling-2026-10-15-jarak-pemasok-biaya.md`, bukti `docs/verification/fase-7d.md`):
   transport = kaki pertama (pemasok → SPPG sumber, dari koordinat) + linehaul, tarif 300 Rp/km/ton;
   skor/eligibilitas tidak bergeser; koordinat kosong → biaya 0 + label, tidak ditebak.

➡️ Kandidat penyempurnaan berikutnya (belum diminta pemilik):
   header tunggal untuk halaman gabungan KPI & Kualitas Agen (sekarang tiap bagian masih membawa
   `PageHeader` sendiri), dan keputusan atas **fixture 4 kasus skrip** yang angka SDC-nya sudah
   berbeda dari mesin bahkan sebelum 7d (DB 16.206.000 vs mesin ±14.169.953).

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
