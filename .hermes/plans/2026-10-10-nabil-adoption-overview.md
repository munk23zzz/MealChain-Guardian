# Plan adopsi selektif Nabil dan polish Overview

> Untuk pelaksana, gunakan `executing-plans` atau `subagent-driven-development` setelah Roy menyetujui plan. Dokumen ini belum memberi izin implementasi, commit, deploy, atau perubahan database.

**Tujuan:** Mengambil pola Nabil yang membantu operator membaca kondisi lokasi, meninjau bukti, dan mengendalikan pemasok. Pertahankan desain Overview kita serta tiga role yang ada.

**Arsitektur:** Repository MealChain kita tetap canonical. Adopsi pola secara selektif, bukan merge frontend/backend Nabil. Adapter data SAP terpisah dari client model SAP AI Core.

**Stack:** FastAPI, SQLAlchemy async, PostgreSQL, Next.js, TypeScript, MapLibre, Recharts, Vitest dan pytest. Tidak ada upgrade framework dalam pekerjaan ini.

**Status (diperbarui 2026-10-15):** **A, B, C, D1, D2 selesai diimplementasikan** — lihat TODO.md `S4-09d`
(schema exclusion lokal per SPPG + restorasi berbukti dengan approval baru; migrasi `011_supplier_exclusions`;
bukti `docs/verification/sprint-4.md` + `docs/verification/sprint-0-2-cross-sprint-audit.md`). Status TODO tetap
`In Progress` HANYA karena Sprint 4 ditandai Done oleh Roy, bukan oleh agent.

Catatan historis: **Status (saat ditulis 2026-10-10):** Eksekusi parsial — Paket A dan B diimplementasikan,
Paket C berhenti pada proposal schema karena migration memerlukan review Roy.

## 1. Scope yang dipakai

1. Perkuat adapter data SAP yang sudah ada menggunakan pola kontrak dan provenance Nabil. Kaitannya dengan S4-10 terbatas pada pola konfigurasi dan penanganan kegagalan. Adapter stok/PO bukan client RPT-1.6.
2. Rencanakan supplier exclusion dengan approval manusia. Role tetap `sppg_head`, `sppg_nutritionist`, `bgn_monitor`. Tidak menambahkan `sppg_staff` atau `dinas_admin`.
3. Adopsi ide fitur Nabil secara bertahap. Compliance berbasis bukti nyata dan export read-only masuk paket lanjutan. Offline dibatasi draft lokal, tidak boleh antrean approve/execute otomatis.
4. Pertahankan shell, login, RoleHero, KPI strip, filter komoditas, peta, chart, panel gelap, dan token Stitch yang ada. Gabungkan pola hierarki lokasi dan badge Nabil pada daftar lokasi saja.

Tidak termasuk merge massal, ganti routing seluruh aplikasi, role baru, provisioning SAP nyata, aktivasi OData baru, deploy VPS, atau mengaktifkan kembali akun legacy.

## 2. Koreksi analisis sebelumnya dan bukti sumber

- Kita sudah punya `SAPDataProvider` pada `backend/app/sap_integration/provider_interface.py:6` dan factory pada `factory.py:14`. Gap-nya bukan ketiadaan adapter.
- Interface kita mengembalikan dictionary. Interface Nabil memakai record bertipe dan capability. Jangan menyatakan record bertipe Nabil sudah ada di repository kita.
- `backend/app/ai_providers/forecast_client.py:26` mendefinisikan `ForecastResult`. Client AI ini harus tetap terpisah dari adapter material stock dan PO.
- `backend/app/api/actions.py:318-417` mengecek verifier, expiry, baris approval, safety, lalu menulis PO dan ledger. Tidak boleh menyalin asumsi Nabil bahwa `status == approved` sudah cukup.
- `backend/app/models/suppliers.py:12-33` belum memiliki status exclusion. Implementasi exclusion membutuhkan desain persistensi dan review schema, bukan hanya tombol baru.
- Teks lokasi yang Roy tunjuk berada di `frontend/components/SupplyMap.tsx:116-145`. Komponen memakai kelas `map-side`, `map-list`, `map-row`, dan `map-legend`. Pencarian stylesheet saat penyusunan plan tidak menemukan definisi kelas-kelas itu. Ini temuan statis, belum pembuktian layout browser.
- `frontend/app/page.tsx` juga memiliki tabel breakdown lokasi. Hindari membuat daftar ketiga atau dua sumber data yang saling berbeda.
- Referensi Nabil `frontend/components/locations/location-card.tsx` memisahkan nama, badge, dan angka. Ambil hierarkinya, bukan import shadcn, alias `@/`, atau model `usableStockKg` tanpa mapping.
- Referensi Nabil `frontend/components/compliance/ccp-board.tsx` memanggil `evaluateCcp` di frontend dan mengimpor tipe dari `mock-compliance`. Jangan port kalkulasi safety atau dataset tersebut.
- Data mock yang berlabel jelas diperbolehkan oleh Rules.md. Yang dilarang adalah menyajikan mock sebagai data nyata, fallback diam-diam, dan angka live karangan.
- Jumlah test antar repository bukan ukuran kedalaman atau kualitas yang setara. Hasil test lama bukan gate implementasi berikutnya.
- Kedua explorer gagal karena HTTP 502. Plan ini memakai inspeksi langsung parent, bukan klaim completion subagent.

## 3. Sumber kebenaran dan batasan

Baca `IDEA.md`, `TODO.md`, `Rules.md`, `workflows.md`, `Roadmap.md`, lalu PRD/Architecture/Schema/Skill yang berlaku sebelum implementasi. Cocokkan salinan root dan `docs/` bila keduanya ada. Jangan menyelaraskan perbedaan kontrak secara diam-diam.

- Warna, font, radius dan panel mengikuti `mockupui/cold_chain_integrity_console/DESIGN.md` serta desain Overview kita. Login tidak disentuh.
- LLM tidak menghitung safety-critical values. Frontend hanya memformat fakta backend.
- Tidak override PASS/FAIL/NEEDS_VERIFICATION. Status surplus bukan klaim bahwa pangan aman.
- Monitor tetap read-only. Scope lokasi dan kebutuhan approval mengikuti server kita, bukan role helper Nabil.
- Jangan ganti fakta yang hilang menjadi nol. Nol yang benar-benar dikirim backend tetap ditampilkan sebagai nol.
- Secrets hanya `.env`. Tidak membuat `.env.example`. Catatan lama di Rules.md tentang example perlu dibahas sebagai drift, bukan diikuti melawan arahan Roy.
- Perubahan Architecture/Schema harus direview Roy. Jangan menambahkan migration sebelum persetujuan tersebut.
- Sprint tetap In Progress sampai Roy menyatakan selesai. Saat eksekusi dimulai, update TODO.md per unit; planning ini tidak menandai implementasi Done.

## 4. Pilihan desain Overview

Opsi yang dipertimbangkan adalah mengganti Overview dengan dashboard Nabil, membuat grid kartu besar untuk semua lokasi, atau memperbaiki daftar di dalam desain sekarang.

Pilih opsi terakhir. Grid kartu besar akan memanjangkan layar dan menggeser peta/chart. Penggantian penuh bertentangan dengan permintaan Roy.

### Tampilan daftar lokasi

- Judul tetap berada di panel sekarang. Nama lokasi tegas, badge status di sampingnya.
- Desktop memakai kolom berlabel `Lokasi`, `Status`, `Pasokan`, `Kebutuhan`, `Selisih`.
- Angka rata kanan dengan tabular numerals. Satuan kg dan format id-ID konsisten.
- Contoh dari data yang diberikan Roy, bukan data runtime baru.

| Lokasi | Status | Pasokan | Kebutuhan | Selisih |
|---|---|---:|---:|---|
| Bandung | Surplus | 400 kg | 0 kg | Lebih 400 kg |
| Jakarta | Shortage | 300 kg | 1.080 kg | Kurang 780 kg |

- Di panel sempit dan mobile, setiap lokasi menjadi kartu ringkas. Baris pertama nama dan badge. Baris berikutnya pasokan/kebutuhan dengan label eksplisit. Selisih mendapat baris sendiri.
- Shortage, Surplus, Seimbang menggunakan teks plus indikator warna. Tidak mengandalkan warna saja. Jangan mewarnai surplus dengan label PASS.
- Semua sepuluh lokasi tetap tersedia. Jangan hardcode nama, jumlah lokasi, atau angka di kode produksi.
- Legenda menjadi kelompok label yang terpisah dan dapat membungkus. Bila dijadikan filter, harus ada Semua, state terpilih, keyboard support, dan target 44px.
- Prioritas pertama adalah spacing, alignment, wrapping dan contrast. Sorting/filter tambahan hanya setelah tampilan dasar lolos, bukan syarat memperbaiki teks menempel.
- Daftar di SupplyMap dan tabel di page tetap mendapat data yang sama. Pertahankan keduanya dulu untuk menghindari penghapusan bagian desain tanpa persetujuan. Gunakan formatter/presentation contract yang sama bila perlu, bukan fetch kedua.
- Loading, data kosong, error, dan data lama memiliki pesan berbeda. Jangan menandai empty sebagai loading terus-menerus.

## 5. Urutan kerja dan throughput checkpoint

Kerjakan Overview dulu agar Roy memperoleh perbaikan terlihat tanpa menunggu schema atau kredensial SAP. Lanjut adapter, lalu exclusion setelah gate kontrak, kemudian compliance/export. Offline draft tetap paket terpisah.

Bottleneck adalah kontrak exclusion dan ketersediaan bukti compliance, bukan kapasitas coding. Jangan memparalelkan penulis `page.tsx`, `globals.css`, atau `actions.py`. Explorer boleh paralel read-only. Satu penulis per file bersama dan parent mereview hasil gabungan.

Setiap unit di bawah memakai urutan RED, implementasi minimum, GREEN, lalu pemeriksaan browser/API yang relevan. Maksimal beberapa file produksi per unit; pecah unit yang membesar. Jangan mengubah test hanya agar markup baru lolos tanpa mempertahankan semantik.

### A1. Kontrak tampilan lokasi

File existing `frontend/components/SupplyMap.tsx`, `frontend/tests/supply-map.test.tsx`. File baru yang diusulkan `frontend/tests/overview-location-breakdown.test.tsx`.

Data existing adalah lokasi dengan `location`, `status`, `supply_kg`, `demand_kg`, `shortage_kg`, `surplus_kg`, koordinat. Tipe baru yang diusulkan `BalanceMapLocation` harus diturunkan dari respons backend yang diperiksa, bukan dari model Nabil.

- [ ] Rekam screenshot baseline Overview di desktop, tablet, mobile menggunakan data dan role yang sama. Browser automation terpisah gagal start; browser pane live hanya mencapai halaman login.
- [ ] Tulis test label kolom dan pemisahan angka. Fixture mencakup seluruh sepuluh lokasi dari contoh Roy, termasuk shortage dan surplus, ditambah kasus balanced.
- [ ] Test data kosong dan missing field terpisah dari nol valid.
- [ ] Jalankan focused Vitest dan pastikan RED terjadi pada perilaku yang diminta.

### A2. Perbaikan CSS dan markup terarah

File `frontend/components/SupplyMap.tsx`, `frontend/app/globals.css`, test A1.

- [ ] Tambahkan kelas yang benar-benar dipakai komponen. Scope style pada panel peta agar tidak mengubah kartu KPI/login.
- [ ] Terapkan layout kolom di lebar cukup dan kartu ringkas di panel sempit.
- [ ] Pertahankan marker, popup, chart, komoditas dan semua lokasi. Tidak perlu library UI baru.
- [ ] Verifikasi browser pada 375, 768, dan 1440px. Tidak ada teks bertumpuk atau overflow halaman. Belum terbukti karena browser automation gagal start.
- [ ] Bandingkan screenshot sebelum/sesudah. Perubahan visual harus terbatas pada daftar/legenda yang ditargetkan.

### A3. Konsistensi Overview

File `frontend/app/page.tsx`, `frontend/components/StockChart.tsx`, tests `sidebar-wiring.test.tsx` dan `stock-chart.test.tsx`.

- [ ] Cocokkan angka peta, daftar, tabel dan chart dengan respons `/balance/map` pada komoditas yang sama.
- [ ] Pastikan pergantian komoditas tidak menampilkan respons lama sebagai hasil terbaru.
- [ ] Jika formatter bersama diperlukan, buat satu modul kecil, tidak framework komponen baru.
- [ ] Test dan browser check untuk semua tiga role. Tidak menambah scope akses baru. API login terverifikasi HTTP 200 untuk SPPG Head; browser role walkthrough belum selesai.

### B1. Contract tests adapter SAP yang ada

File `backend/app/sap_integration/provider_interface.py`, `backend/tests/test_sap_integration_contract.py`. Test factory baru yang diusulkan `backend/tests/test_sap_provider_factory.py`.

- [x] Dokumentasikan lima operasi existing dan shape dictionary setiap operasi.
- [x] Uji unknown plant, provenance MOCK, mode tidak dikenal, dan kemampuan write tanpa approval.
- [ ] Jangan mengganti nama field dictionary dengan nama field Nabil tanpa mapping dan migrasi caller.
- [ ] Keputusan awal mempertahankan signature publik. Typed records boleh ditambahkan di boundary jika memberikan validasi nyata.

### B2. Mode dan provenance yang fail-closed

File `backend/app/sap_integration/factory.py`, `mock_provider.py`, test factory B1.

- [x] Pertahankan mock sebagai default. Pemilihan real yang belum tersedia harus error, bukan diam-diam kembali mock.
- [ ] Pastikan label berasal dari sumber sebenarnya. Test timeout/malformed response memakai fixture eksplisit, bukan mengklaim koneksi SAP live.
- [ ] Tidak menyentuh jalur SQL penulisan PO existing tanpa unit migrasi transaksi tersendiri. Saat ini `actions.py` menulis PO langsung; mengubah factory saja belum membuktikan seluruh aksi provider-switchable.
- [ ] Gate API read-only dan regression PO memastikan perilaku lama tetap utuh.

### B3. Batas SAP AI Core dan S4-10

File existing `backend/app/ai_providers/forecast_client.py`, `verifier_client.py`, `ai_provider_chain.py`.

- [x] Susun mapping terpisah antara adapter data SAP dan provider model AI. Jangan mengimpor SAPDataProvider ke client forecast hanya demi keseragaman.
- [ ] Pertahankan label fallback dan ForecastResult existing.
- [ ] Aktivasi HTTP SAP AI Core tetap task S4-10 tersendiri, memerlukan deployment dan kredensial nyata. Tidak ditandai selesai oleh refactor adapter.

### C0. Integrasi safety exclusion dan supplier exclusion

Supplier exclusion masuk lingkup implementasi wajib paket C sesuai arahan Roy. Paket ini menggabungkan pemeriksaan eligibility dengan safety exclusion existing, bukan mengganti safety rule. Perubahan ini masih plan, bukan izin menjalankan migration atau mengubah aplikasi.

File acuan existing `backend/app/services/event3_service.py`, `backend/app/api/actions.py`, dan `backend/app/models/suppliers.py`. Telusuri candidate builder serta relasi batch ke supplier sebelum implementasi. Jangan menebak supplier dari lokasi jika ada beberapa pemasok di lokasi yang sama.

Data kontrak yang diusulkan adalah hasil eligibility dengan `eligible`, daftar alasan penolakan, referensi batch, referensi supplier bila diketahui, scope, dan referensi bukti. Status safety tetap field terpisah dari status administratif supplier.

| Kondisi | Perilaku yang wajib |
|---|---|
| Batch FAIL, supplier belum excluded | Batch langsung tidak eligible. Tidak menunggu proposal atau approval supplier. |
| Batch PASS, supplier excluded dalam scope | Kandidat tetap tidak eligible karena exclusion supplier. PASS tidak membatalkan exclusion. |
| Batch FAIL dan supplier excluded | Simpan kedua alasan. Jangan menimpa bukti safety dengan alasan administratif. |
| Safety NEEDS_VERIFICATION | Pertahankan aturan eligibility existing. Jangan dianggap PASS karena supplier aktif. |
| Proposal exclusion pending atau ditolak | Tidak mengaktifkan exclusion supplier. Batch FAIL tetap diblokir. |
| Supplier aktif dan safety lolos | Masih wajib melewati freshness, kapasitas, delivery window, dan seluruh constraint existing. |

- [ ] Reuse hasil evaluasi safety existing. Jangan membuat formula safety kedua atau mengubah threshold Event 3.
- [ ] Insiden Event 3 dapat dipakai sebagai bukti pada usulan supplier exclusion melalui tindakan eksplisit approver. Insiden tunggal tidak otomatis memblokir seluruh pemasok.
- [ ] Link usulan ke incident/decision dan batch asal beserta bukti yang persisten. Jika relasi supplier tidak diketahui, tampilkan alasan tidak dapat mengusulkan; jangan mengarang asosiasi.
- [ ] Terapkan pemeriksaan gabungan pada pembentukan kandidat, reroute Event 3, reproposal, dan revalidasi tepat sebelum eksekusi. Jalur transaksi mencegah exclusion bersamaan dengan eksekusi meloloskan pemasok yang sudah diblokir.
- [ ] Reroute mencari alternatif yang lolos kedua pemeriksaan serta constraint existing. Bila tidak ada alternatif, pertahankan hasil tidak tersedia; jangan melonggarkan safety atau memakai supplier excluded.
- [ ] Review durasi exclusion dan proses pemulihan pada C1. Tidak ada auto-unblock karena batch baru PASS. Pembatalan exclusion administratif tidak pernah mengubah batch FAIL menjadi PASS.

Verifikasi RED/GREEN dilakukan dengan matriks kondisi di atas. Tambahkan uji reroute ke pemasok excluded, supplier tidak teridentifikasi, proposal ditolak, keputusan lama, dan race exclusion/execute. Jalankan regression Event 3 untuk membuktikan persistensi FAIL tetap terjadi sekalipun proposal administratif atau pencarian alternatif gagal.

### C1. Gate kontrak supplier exclusion

File review `backend/app/models/suppliers.py`, `backend/app/api/actions.py`, serta model Decision/Approval dan schema canonical yang harus ditelusuri sebelum edit.

- [x] Tulis proposal schema additive berisi target supplier, scope lokasi, reason, evidence reference, decision reference, actor dan waktu eksekusi. Proposal berada di `.hermes/plans/2026-10-10-supplier-exclusion-schema.md`.
- [x] Ruling Roy: exclusion lokal per SPPG sesuai scope approval, bukan seluruh jaringan.
- [x] Ruling Roy: exclusion berlaku sampai dicabut melalui keputusan pemulihan berbukti dan approval baru. Tidak ada auto-unblock dan status FAIL batch tetap berlaku.
- [ ] Review dampak constraint decision_type, field wajib quantity/commodity, dan approval-summary. Jangan membuat quantity/biaya palsu agar exclusion muat ke keputusan transfer.
- [ ] Minta persetujuan Roy atas scope dan perubahan Architecture/Schema sebelum migration.

### C2. Domain dan persistensi exclusion setelah C1 disetujui

File baru yang diusulkan `backend/app/core/supplier_exclusion.py`, `backend/app/services/supplier_exclusion_service.py`, `backend/tests/test_supplier_exclusion.py`. Migration dibuat di direktori Alembic aktual setelah head diperiksa.

- [ ] RED untuk reason kosong, supplier tidak dikenal, evidence tidak valid, dan scope tidak berwenang.
- [ ] Persist proposal tanpa menonaktifkan pemasok.
- [ ] Eksekusi memakai verifier, expiry, dan evaluasi baris Approval existing. Tidak memperkenalkan state approved dari Nabil.
- [ ] Transaksi mencakup perubahan exclusion, status keputusan dan ledger. Dua eksekusi bersamaan tidak boleh menghasilkan efek ganda.
- [ ] Exclusion tidak menghapus data historis dan tidak mengubah safety FAIL menjadi PASS.

### C3. Integrasi kandidat dan API

File existing `backend/app/api/actions.py`; candidate generator dan supplier lookup ditelusuri dari caller sebelum ditentukan dalam subplan C1. Test baru `backend/tests/test_supplier_exclusion_api.py`.

- [ ] Pemasok yang sudah dikecualikan tidak masuk kandidat baru dalam scope yang berlaku.
- [ ] Revalidasi keputusan lama saat eksekusi agar approval lama tidak mem-bypass exclusion terbaru.
- [ ] Test monitor 403, approver salah lokasi 403, expired/rejected/unverified ditolak, retry aman, dan ledger bertambah tepat sekali.
- [ ] Bedakan exclusion supplier dengan eliminasi batch FAIL pada Event 3. Batch tidak aman tetap dieliminasi oleh rule safety tanpa menunggu workflow administratif supplier.

### C4. UI exclusion

File `frontend/components/ApprovalModal.tsx`, `frontend/lib/api.ts`; komponen baru yang diusulkan `frontend/components/SupplierExclusionPanel.tsx`.

- [ ] Tampilkan supplier, scope, alasan, bukti, expiry dan konsekuensi sebelum confirm.
- [ ] Pada detail insiden safety, sediakan tindakan eksplisit mengusulkan exclusion supplier jika identitas pemasok diketahui dan user berwenang. Tampilkan terpisah status batch dan status supplier. Monitor hanya melihat bukti serta riwayat.
- [ ] Gunakan approval-summary backend. Jangan frontend menghitung kelayakan sendiri.
- [ ] Monitor dapat membaca, tidak mengusulkan/approve/execute.
- [ ] Browser flow proposal, review, approve/reject dan refresh harus cocok dengan read-back backend.

### D1. Compliance read-only berbasis bukti

Komponen baru yang diusulkan `frontend/components/ComplianceEvidencePanel.tsx`, test `frontend/tests/compliance-evidence.test.tsx`. Integrasi di detail keputusan, bukan tab baru otomatis.

- [ ] Inventaris bukti dari endpoint decision, dossier dan safety yang ada. Setiap field UI harus memiliki sumber nyata.
- [ ] Tampilkan status backend, hasil pengukuran, sumber dan timestamp yang benar-benar tersedia.
- [ ] Untuk CCP/hazard/sample-bank yang belum memiliki model data, tampilkan belum tersedia atau tunda panel. Jangan menyalin mock-compliance atau label kepatuhan resmi tanpa rule yang disetujui.
- [ ] Backend read model baru hanya jika endpoint existing tidak cukup. Buat subplan schema/rule sebelum menambah pengukuran atau threshold.
- [ ] Test PASS/FAIL/NEEDS_VERIFICATION, bukti kosong, timestamp tidak ada, dan provenance mock.

### D2. Export read-only

Modul baru yang diusulkan `frontend/lib/export.ts`, test `frontend/tests/export.test.ts`. Reuse dossier existing melalui `frontend/components/IntegrityPanel.tsx`.

- [ ] Export hanya data yang sudah diizinkan server untuk user, termasuk scope dan provenance.
- [ ] Escape CSV dan cegah formula injection. Jangan menulis token, credential atau data lintas scope ke file.
- [ ] Hash/signature hanya diexport jika tersedia. Unsigned tetap unsigned.
- [ ] Verifikasi file unduhan dengan membukanya kembali dan mencocokkan data respons.

### D3. Offline draft sebagai paket opsional

Tidak diperlukan untuk menyelesaikan Overview, SAP adapter atau exclusion. Perlu persetujuan terpisah setelah manfaat operasional dinilai.

- [ ] Jika diambil, simpan draft teks saja, terikat user/scope, TTL terbatas dan dibersihkan saat logout.
- [ ] Dilarang menyimpan approval/execute untuk replay otomatis.
- [ ] Setelah koneksi kembali wajib refresh bukti, expiry dan authorization, lalu meminta konfirmasi manusia lagi.

## 6. Gate verifikasi

Jalankan setiap command secara terpisah atau dengan `&&`. Jangan pipe ke tail/grep sehingga exit code kegagalan tertutup.

```bash
docker compose exec -T backend pytest
docker compose exec -T backend ruff check .
docker compose exec -T frontend npm run test
docker compose exec -T frontend npx tsc --noEmit
docker compose exec -T frontend npm run lint
docker compose exec -T frontend npm run build
```

- Rekam hasil aktual dan skip beserta alasannya. Jangan memakai total test lama sebagai syarat tetap.
- Probe tiga role dan read-back target setelah setiap mutasi uji. Gunakan dataset terisolasi, bukan mengubah data operasional tanpa kontrol.
- Jalankan tiga skenario demo existing sebagai regression setelah backend berubah.
- Periksa mount Compose sebelum restart/rebuild. Build berhasil belum berarti browser memakai bundle baru.
- Responsif dan visual wajib dibuktikan screenshot dengan browser/control-ui. SSR/string test saja tidak membuktikan jarak antar angka.
- Tidak ada jaminan bebas seluruh bug. Done berarti acceptance criteria yang tercantum sudah diuji.

## 7. Panduan pelaksana dan keputusan yang menunggu Roy

Gunakan `how` untuk menelusuri subsystem, `architect` sebelum boundary baru, `test-driven-development`, `control-ui`/`webapp-testing`, `verification-before-completion`, dan `show-me-your-work` untuk bukti per fase. Gunakan `interrogate` bila desain diperdebatkan. `deslop` sebelum commit hanya setelah Roy mengizinkan commit. `unslop` untuk dokumen. PR dan babysitting CI tidak dijalankan tanpa permintaan PR.

Prinsip **Laziness Protocol** memilih perbaikan lokal daftar daripada transplant frontend Nabil. Pilihan ini mengurangi perubahan yang harus dirawat Nabil dan Roy.

Paket C termasuk pekerjaan yang diminta Roy, dengan integrasi safety exclusion pada C0. Urutan tetap A+B lalu C; review scope/schema pada C1 tetap wajib sebelum migration. D1+D2 adalah paket lanjutan. D3 tidak dieksekusi otomatis. Seluruh desain Overview di luar daftar/legenda tetap dipertahankan. Persetujuan pelaksanaan plan belum diberikan melalui perubahan dokumen ini.
