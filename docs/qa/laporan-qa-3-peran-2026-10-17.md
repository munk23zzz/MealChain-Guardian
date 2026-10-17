# Laporan QA 3 Peran — MealChain Guardian

Tanggal: 17 Oktober 2026 · Lingkungan: `http://localhost:3010` (docker compose: frontend, backend, mock-sap, postgres) · Metode: skill `dogfood` (exploratory QA) + `ui-copy-hygiene` (kebersihan teks UI)
Akun demo: `sppg.head@demo.local` (SPPG Head), `sppg.nutritionist@demo.local` (Nutritionist), akun BGN Monitor — login lewat tombol demo di halaman masuk.

Cakupan: **29 halaman** (10 tab SPPG Head, 10 tab Nutritionist, 9 tab BGN Monitor), seluruh kontrol yang terlihat diklik atau diperiksa, pemantauan `console`, `fetch` (status + URL), dan struktur aksesibilitas.
**Tidak ada data yang diubah**: alur setujui/tolak, muat kasus demo, dan pembersihan data **tidak** dijalankan supaya state demo tetap utuh.

---

## 1. Ringkasan eksekutif

- **Tidak ada halaman yang gagal render** (teks tiap tab 981–23.215 karakter — kontrol positif terpenuhi).
- **Tidak ada satu pun `console.error` / exception** di ketiga peran.
- **Tidak ada permintaan yang gagal selain 404 keputusan tak dikenal** (temuan #1).
- **18 temuan**: 1 High, 1 High-Menengah, 6 Medium, 8 Low, 2 Informasi.
- Tiga kelompok besar: **(A) teks teknis di layar** (paling banyak), **(B) informasi mengulang di halaman yang sama**, **(C) beberapa cacat fitur/aksesibilitas**.

Semua fitur utama yang diuji berfungsi (lihat §5).

---

## 2. Temuan — Fitur & fungsional

### #1 · HIGH · Functional — 404 untuk keputusan yang tidak ada
- **Di mana:** permintaan latar `GET /decisions/<id>/approval-summary` dan `/decisions/<id>/traces`.
- **Bukti (log jaringan sesi ini):**
  - `404 /decisions/5fe24703-e492-483b-93a3-1756b2e27811/traces`
  - `404 /decisions/5fe24703-e492-483b-93a3-1756b2e27811/approval-summary`
  - `404 /decisions/2e24446f-255a-42c6-af80-f5ebf45f2f19/approval-summary` (2×, sesi BGN Monitor)
- **Reproduksi:** buka **Decision & Evidence**, lalu pindah ke **Pemasok** (atau muat ulang data demo sehingga id keputusan berganti) → app tetap meminta ringkasan keputusan id lama.
- **Dampak:** panel jejak/persetujuan kosong tanpa pesan; di konsol pengguna muncul 404. Kalau id lama disimpan (localStorage/state), ini akan selalu terjadi setelah "Muat kasus demo".
- **Usul:** saat 404 → kosongkan pilihan keputusan + tampilkan satu pesan manusia ("Keputusan ini sudah tidak ada, pilih keputusan lain"), dan jangan ulangi permintaan untuk id yang sudah 404.

### #2 · HIGH-MENENGAH · Content — Teks teknis & enum mentah di layar
Semua ini terbaca pengguna/juri sebagai "aplikasi belum selesai" (aturan `ui-copy-hygiene`).

| Halaman | Yang tampil (verbatim) | Kelas elemen |
|---|---|---|
| Overview, Recommendations, notifikasi, 3 peran | `PENDING APPROVAL` (23× di feed) | badge status |
| Demo Control | `PROPOSED` (2×), `thermal excursion`, `price anomaly`, `pass`/`fail` di opsi batch ("telur · Surabaya · 600 kg · fail") | heading & option |
| KPI & Kualitas Agen | `scope 23e6e766… (sppg_head)`, `supply_balance.propose` (4×), `rejection_loop.repropose` (4×) | `.commodity-pill`, `.quality-chip` |
| Pemasok | "…tidak dipilih lagi untuk purchase order oleh **backend**" | `.evidence-note` |
| Agent Log | `Sumber: backend/app/sap_integration/mock_service.py`, `Sumber: docs/verification/fase-12.md`, `Sumber: agent/README-deploy.md`, "PO ditulis ke **mock**, bukan S/4HANA nyata", "kontrak pemanggil diuji di backend/tests" | `.integration-artifact`, `.integration-note` |
| Decision & Evidence | "target Simulasi (**mock**)"; fakta "Simulasi (mock)" | `.evidence-route-detail`, `.fact-value` |
| Demo Control | "Seeder relatif… **tes backend** yang memaku 8 Okt 12.00 tidak lagi cocok", "Snapshot kanonik: 362 baris (per 8 Okt 2026 12.00 UTC)", "tanpa **mock**", "dijalankan lewat **API resmi**" | paragraf & `.demo-data-warning` |

**Usul:** pakai satu modul terjemahan (`lib/bahasa.ts` sudah ada polanya) untuk `PENDING APPROVAL → Menunggu persetujuan`, `PROPOSED → Diusulkan`, `pass/fail → lolos/gagal`; sembunyikan path berkas & nama fungsi internal dari layar (pindahkan ke atribut `title` atau halaman "bukti teknis" khusus), dan buang UUID scope dari chip KPI.

### #3 · MEDIUM · UX — Enam keputusan identik tanpa pembeda
- **Di mana:** Hari Ini (daftar "Menunggu tindakan") dan Recommendations.
- **Bukti:** `6x Alokasi regional direkomendasikan` + `6x 500 kg · Menunggu persetujuan` di halaman yang sama; feed menampilkan `18x Alokasi regional direkomendasikan`, `10x 500 kg`.
- **Dampak:** pengguna tidak bisa membedakan kartu mana yang harus disetujui lebih dulu; judul + nominal sama, hanya "SDC Rp15…/Rp14…" yang beda tipis.
- **Usul:** tampilkan pembeda nyata (asal → tujuan, waktu usul, agen pemicu) di baris judul kartu; atau dedupe di seed demo.

### #4 · MEDIUM · UX — Nama peran tidak konsisten (satu peran, tiga nama)
| Tombol login | Identitas di konsol | Email |
|---|---|---|
| SPPG Head | **SPPG Operations Lead** | sppg.head@demo.local |
| Nutritionist | **Food Safety Officer** | sppg.nutritionist@demo.local |
| BGN Monitor | **National Inspector** | (BGN) |
- **Dampak:** pengguna demo tidak yakin sedang memakai peran yang mana; label persetujuan di Decision & Evidence menyebut "Kepala SPPG atau Ahli Gizi" (nama keempat & kelima).
- **Usul:** satu daftar nama peran (`ROLE_LABEL`) dipakai di login, side-nav, top bar, dan kalimat kewenangan.

### #5 · MEDIUM · Functional/UX — Gating Demo Control tidak konsisten
- Nutritionist (peran yang di Decision & Evidence dinyatakan **"Tampilan ini hanya baca"**) tetap melihat **Demo Control** + tombol sidebar **"Muat kasus demo"**, termasuk **Bersihkan data demo**, **Buat/perbarui data**, **Picu Event 3**.
- BGN Monitor **tidak** melihat Demo Control maupun "Muat kasus demo" ✓.
- **Usul:** putuskan siapa yang boleh menjalankan skenario demo (idealnya satu peran operator/demo), lalu sembunyikan sisanya — atau beri label jelas "khusus demo".

---

## 3. Temuan — Informasi mengulang di halaman yang sama

Angka = jumlah kemunculan baris identik di `.app-content` halaman itu.

| Halaman | Yang mengulang | Catatan |
|---|---|---|
| **Hari Ini** | `18 sudah lewat tenggat` di catatan tile **dan** di `.today-card-note` kepala kartu ("Agenda terdekat kurang dari 1 mnt lagi · 18 sudah lewat tenggat"); `Total kekurangan 801,02 kg` di catatan tile **dan** ("Total kekurangan 801,02 kg (komoditas telur)") di kartu "Lokasi shortage"; `Sabtu, 17 Oktober 2026` 2× | tile ringkasan & kartu detail menyampaikan angka yang sama (#6) |
| **Overview** | `−765,8 kg` **4×** (KPI hero, pin peta, Telemetri Node, "Selisih: kurang 765,8 kg" di Status Lokasi); `Rincian kiriman` 3×; `PENDING APPROVAL` 3× | (#7) |
| **Recommendations** | petunjuk `Klik untuk rincian & jejak agen` **24×** (satu per kartu); `PENDING APPROVAL` 23×; judul keputusan 18× | petunjuk seharusnya sekali di kepala feed (#8) |
| **KPI & Kualitas Agen** | `makin rendah makin baik` 4×, `makin tinggi makin baik` 3× | jadikan legenda sekali + tanda ↑/↓ per metrik (#9) |
| **Pemasok** | `di luar jangkauan` 13×; BGN: `HACCP — Aktif —` 9×, `Higienis — Aktif —` 8×, `Tidak bersertifikat — Aktif —` 5× | kolom sertifikasi banyak "—" (#10) |
| **Agent Log** | `tidak tersedia` 3×, `Sumber: …` berulang | wajar untuk log, tapi path berkas harus hilang (#2) |

**Usul umum:** tile ringkasan cukup menyebut keadaan tanpa mengulang angka yang sudah ada di kartu di bawahnya (mis. tile → "12 keputusan menunggu", kartu → rincian); atau tile jadi tombol lompat tanpa catatan angka.

---

## 4. Temuan — Aksesibilitas & konsistensi kecil

| # | Tingkat | Temuan | Bukti |
|---|---|---|---|
| #11 | MEDIUM | Pemilih "Cakupan lokasi yang ditampilkan" di top bar **disabled** dan hanya punya satu opsi (`Jakarta`, juga disabled) — terlihat seperti kontrol, tidak bisa dipakai | `combobox [disabled]`, 1 `option [disabled]` |
| #12 | MEDIUM | Kontrol peta memakai nama aksesibilitas **Inggris** di UI Indonesia: `Zoom in`, `Zoom out`; toggle `Info map` tanpa aria-label | kelas `maplibregl-ctrl-zoom-in/out`, `map-legend-toggle` |
| #13 | MEDIUM | Input pencarian feed hanya punya placeholder (`Jenis, status, kasus, atau ID keputusan…`), tanpa label | elemen `input` tanpa `aria-label`/`<label>` |
| #14 | MEDIUM | Label combobox Demo Control berupa kalimat panjang → nama kontrol yang dibacakan screen reader satu paragraf: "Lokasi Terkunci ke SPPG Anda (cakupan lokasi 2026-10-14).", "Batch Keputusan dari event ini menyasar SPPG Anda (Jakarta). Batch boleh berasal dari lokasi sumber mana pun." | aksesibilitas tree |
| #15 | LOW | Tiga tombol ekspor berdampingan dengan bahasa campur: `Unduh bukti (JSON)`, `Export JSON dossier`, `Export CSV bukti` | Decision & Evidence |
| #16 | LOW | Judul menu Inggris di antara menu Indonesia: `Recommendations (8)`, judul halaman `Recommendation Feed`, `Agent Activity Log`, `Demo Control Panel` | side-nav & h1 |
| #17 | LOW | Hitungan chip filter tidak jelas asalnya: `diusulkan 241`, `ditandai verifier 1`, sementara daftar hanya 24 kartu + `Tampilkan 24 lagi` | feed |
| #18 | LOW | Performa: tiap keputusan = 2 permintaan (`/traces` + `/approval-summary`); sekali buka tab tercatat 8 permintaan beruntun untuk beberapa keputusan sekaligus (pola N+1) | log jaringan |

Positif yang perlu dipertahankan: tombol ikon (`Keluar`, `‹`/`›`, ikon kalender) **punya aria-label** (`Keluar`, `Hari sebelumnya`, `Hari berikutnya`, `Pilih tanggal`); toggle `Hanya dalam jangkauan` memakai `aria-pressed`; catatan "Tampilan ini hanya baca" menjelaskan kewenangan peran; halaman KPI & Agent Log menyatakan data yang tidak tersedia apa adanya (tidak mengarang status hijau).

---

## 5. Fitur yang diuji dan hasilnya

| Peran | Fitur | Hasil |
|---|---|---|
| ketiga | Login tombol demo 3 peran | ✅ masuk sesuai peran |
| ketiga | Keluar (`aria-label="Keluar"`) | ✅ token `mealchain.token` dihapus, kembali ke form masuk (catatan: tanpa panggilan server — token JWT hanya dibuang di klien) |
| ketiga | Navigasi semua tab | ✅ 29/29 halaman render, tanpa console error |
| SPPG Head, Nutritionist | 10 tab yang sama | ✅ |
| BGN Monitor | 9 tab (tanpa **Surplus & Limbah**, tanpa **Demo Control**, + **Pengaturan**) | ✅ sesuai pembatasan peran; cakupan lokasi "Semua lokasi SPPG (10 lokasi)" |
| Hari Ini | `‹` / `›` (geser satu hari) | ✅ 17 → 18 → 17 Oktober |
| Hari Ini | Pil "Hari ini" | ✅ kembali ke 17 Oktober |
| Hari Ini | Ikon kalender → popup | ✅ dialog terbuka; `<select>` Bulan (12 opsi) & Tahun (2026–2027); klik `[data-date="2026-10-23"]` → agenda "Jumat, 23 Oktober 2026", popup tertutup |
| Hari Ini | 5 tile ringkasan | ✅ dapat diklik, memindahkan fokus ke kartu tujuan |
| Overview | Chip komoditas (`telur/ayam/beras/wortel`) | ✅ data berubah saat chip diganti |
| Overview | Bel notifikasi | ✅ panel berisi daftar keputusan + hitungan ("8 keputusan menunggu tindakan · 18 lewat tenggat") |
| Overview | Kontrol peta (zoom, `Info map`), legenda | ✅ ada & dapat diklik |
| Recommendations | Kotak cari | ✅ daftar menyaring saat diisi "pengalihan" |
| Recommendations | `Tampilkan 24 lagi` | ✅ tombol 32 → 56, tombol muat lagi tetap tersedia |
| Recommendations | Klik kartu | ✅ pindah ke **Decision & Evidence** dengan keputusan itu terpilih |
| Decision & Evidence | `Unduh bukti (JSON)`, `Export CSV bukti` | ✅ tanpa galat/permintaan gagal (berkas dibuat di sisi klien — artefak unduhan tidak diverifikasi) |
| Decision & Evidence | `Buka jejak agen →` | ✅ label berubah (bagian jejak terbuka) |
| Decision & Evidence | Catatan kewenangan per peran | ✅ Nutritionist: "Hanya Kepala SPPG atau Ahli Gizi pada SPPG tujuan yang berwenang mengusulkan. Tampilan ini hanya baca." |
| Pemasok | `Hanya dalam jangkauan (22)` ⇄ `Tampilkan semua pemasok` | ✅ isi menyusut 5.879 → 4.625 karakter, `aria-pressed="true"` |
| Demo Control | Tombol skenario | ⏸ **sengaja tidak dijalankan** (mengubah data demo) |

**Tidak diuji (batas jujur):**
- Setujui / tolak / verifikasi ulang (mengubah state demo) — hanya elemen & catatan kewenangannya diperiksa.
- Isi berkas hasil unduhan (JSON/CSV) — hanya dipastikan tidak ada galat.
- Pembaca layar nyata & uji kontras terukur (hanya atribut aksesibilitas yang diperiksa).
- Perilaku saat backend mati/timeout.

---

## 6. Urutan perbaikan yang disarankan

1. **#2 teks teknis & enum mentah** — paling banyak, paling merusak kesan "siap demo"; sebagian besar hanya pemetaan label.
2. **#1 404 keputusan tak dikenal** — perbaiki penanganan pilihan yang sudah tidak ada.
3. **#3 keputusan identik** — beri pembeda pada kartu (asal→tujuan, waktu).
4. **#6–#10 pengulangan informasi** — tile ringkasan tidak mengulang angka kartu; petunjuk feed sekali saja; legenda KPI sekali.
5. **#4 nama peran, #5 gating Demo Control, #11–#14 aksesibilitas** — pekerjaan setengah hari.
6. **#15–#18** — polesan & performa (batching `/traces` + `/approval-summary`).

## 7. Catatan metode

- Penyapuan: per tab, teks `.app-content` diambil, baris ≥14 karakter dihitung untuk mendeteksi pengulangan; `fetch` dibungkus untuk mencatat status non-2xx; `console.error`/`window.onerror` dipantau sepanjang sesi.
- Audit klik otomatis hanya untuk tombol berteks; tombol ikon (Keluar, ‹ ›, ikon kalender) diperiksa lewat **nama aksesibilitas** — pelajaran dari sesi ini: tombol ber-`aria-label` tidak tertangkap pencarian teks, dan kegagalan "tidak ada perubahan" pada awalnya **bukan** bukti tombol mati (terbukti Keluar bekerja).
- Angka pengulangan bisa memuat positif palsu (mis. `SPPG Operations Lead` 2× karena top bar + sidebar); temuan #6–#10 hanya memuat baris yang isinya memang informasi, bukan nama peran.
- Angka nominal pada laporan ini adalah cuplikan saat pengujian; data demo dibangun ulang oleh sesi lain sehingga nilai bisa bergeser (mis. `765,8 kg` → `801,02 kg`) — **pola pengulangannya** yang jadi temuan, bukan angkanya.

---

## 8. Perbaikan ronde 1 (dikerjakan setelah laporan ini)

Yang dikerjakan — temuan **#2 (teks teknis & enum mentah)** dan bagian mekanismenya:

| Sebelum (di layar) | Sesudah | Di mana |
|---|---|---|
| `PENDING APPROVAL` (23× di feed), `NEEDS VERIFICATION`, `PROPOSED`, `VERIFIER_FLAGGED`, `APPROVED/REJECTED/EXECUTED` | `Menunggu persetujuan`, `Perlu verifikasi`, `Diusulkan`, `Ditandai verifikator`, `Disetujui/Ditolak/Dieksekusi` | `components/StatusBadge.tsx` + `statusLabel()` di `lib/bahasa.ts` (satu modul, bukan peta kedua) |
| `scope 23e6e766… (sppg_head)` | `Cakupan: Kepala SPPG` (UUID dipindah ke `title`) | `components/KPIDashboard.tsx` |
| `supply_balance.propose`, `demand.snapshot`, `POST /decisions`, `fallback ×2` | `Neraca pasokan · usulkan`, `Potret permintaan`, `Buat keputusan`, `langkah cadangan ×2` (aslinya tetap di `title`) | `components/AgentQualityBoard.tsx` + `toolLabel()` di `lib/bahasa.ts` |
| `Sumber: backend/app/sap_integration/mock_service.py` (dan path lain) | path **hilang dari layar**, tetap ada sebagai `title` pada "Bukti: …" | `components/IntegrationStatusPanel.tsx` |
| "…tidak dipilih lagi untuk purchase order oleh **backend**" | "…tidak dipilih lagi saat sistem menyusun pesanan pembelian" | `components/SupplierBoard.tsx` |
| "Deviasi dihitung deterministik oleh **backend**" | "Deviasi dihitung otomatis oleh sistem" | `components/Event2Panel.tsx` |
| "target Simulasi (**mock**)" | "Simulasi" | `executionTargetLabel()` di `lib/bahasa.ts` |
| `telur · Surabaya · 600 kg · fail` | `telur · Surabaya · 600 kg · Gagal` | `batchLabel()` di `lib/chaos-scope.ts` (memakai `safetyLabel`) |
| "Skenario deterministik… API resmi (tanpa mock)… price anomaly… thermal excursion" | "Skenario uji untuk hari demo — semuanya lewat layanan aplikasi yang sebenarnya (bukan tiruan)… harga melonjak… suhu kiriman menyimpang" | deskripsi Demo Control (`app/page.tsx`) |
| "Chaos Skenario — Event 3 (thermal excursion)" | "Skenario uji — Event 3 (suhu kiriman menyimpang)" | `components/ChaosPanel.tsx` |

Bukti:
- TDD: `statusLabel`/`toolLabel` + `tests/status-badge.test.tsx` (baru) ditulis dan dijalankan **merah** lebih dulu (`statusLabel is not a function`), lalu hijau. Tes lama yang memaku teks Inggris dibalik dengan **niat tes yang sama** (`agent-flow`, `decision-loop`, `chaos-scope`, `evidence-summary`, `integration-status`).
- `integration-status`: assertion diubah menjadi "path TIDAK lagi sebagai teks" + "path masih ada di `title`" — bukti tidak dihapus, hanya tidak mengotori layar.
- Verifikasi di peramban, **ketiga peran**: SPPG Head 10 tab, Nutritionist (Overview/Recommendations/KPI), BGN Monitor (Overview/Recommendations/KPI/Pengaturan) — token `PENDING APPROVAL`/`NEEDS VERIFICATION`/`PROPOSED`/`Proposed` = **0**, lencana terbaca `Menunggu persetujuan` / `Ditandai verifikator`.
- Gerbang: seluruh suite lulus; `tsc` 0 error **di berkas yang disentuh** (2 error yang muncul di `tests/supply-map-layer.test.tsx` milik sesi paralel, bukan dari perubahan ini — dihitung terpisah: `error_berkas_saya=0`); `next lint` bersih.

Masih terbuka (bukan frontend): beberapa kalimat teknis di Demo Control **datang dari server** ("Seeder relatif… tes backend yang memaku 8 Okt 12.00", "Snapshot kanonik: 362 baris…"), jadi perbaikannya di backend, bukan di komponen. Begitu juga "Bukti: layanan mock-sap + tes kontrak PO" (teks `evidence` dari API).

Sisa temuan #1, #3–#18 belum dikerjakan.
