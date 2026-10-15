# Plan — Gabung halaman KPI + Kualitas Agen (2026-10-15)

Status: **SELESAI 2026-10-15** (6a–6d) — bukti: `docs/verification/fase-8.md`
Dasar: permintaan pemilik 2026-10-15 ("gabungkan page kualitas agent dan page kpi lalu buat nama baru
untuk di sidebar"), menyusul penghapusan strip Target KPI di halaman KPI (hari yang sama).

> Konvensi plan ini sama dengan plan lain di `.hermes/plans/`: setiap klaim teknis punya alamat berkas
> yang bisa diperiksa, dan yang belum diputuskan ditulis sebagai pertanyaan — bukan asumsi.

## 1. Tujuan & alasan

Dua tab sidebar berdiri sendiri padahal menjawab dua sisi dari SATU pertanyaan yang sama — "bagaimana
kinerja sistem ini?": **KPI** mengukur HASIL (7 indikator kontinuitas pangan, dihitung backend atas
jendela 24 jam), **Kualitas Agen** mengukur CARA (mutu kerja agen pada 8 keputusan terakhir: skor
agregat, putusan verifikator, rincian per run). Setelah strip Target KPI dihapus, halaman KPI hanya
berisi satu grid 7 kartu — terlalu tipis untuk satu tab, sementara halaman Kualitas Agen memuat satu
tabel panjang. Digabung: satu tab, urutan cerita "hasil → cara", dan sidebar lebih pendek.

Yang TIDAK berubah: angka, sumber data, dan perhitungan di kedua halaman. Ini pekerjaan
informasi-arsitektur, bukan perubahan logika bisnis.

## 2. Fakta yang sudah diperiksa (inventaris, 2026-10-15)

| Hal | Kenyataan di repo | Berkas |
|---|---|---|
| Tab KPI | id `"kpi"`, label `"KPI"`, tanpa batasan peran | `app/page.tsx:158, 484, 849` |
| Tab Kualitas Agen | id `"quality"`, label `"Kualitas Agen"`, tanpa batasan peran | `app/page.tsx:165, 483, 1173` |
| Isi halaman KPI | `KPIDashboard` (226 baris): header + grid 7 kartu `.kpi-card` + status per kartu | `components/KPIDashboard.tsx` |
| Isi halaman Kualitas Agen | `AgentQualityBoard` (478 baris): Skor agregat · Putusan verifikator · Rincian per run | `components/AgentQualityBoard.tsx:227, 314, 357` |
| Sumber data KPI | `GET /kpi` → `useKpi(token, scope)`, **tanpa gerbang tab** (dimuat di SEMUA tab) | `lib/hooks/useKpi.ts` |
| Pemakai lain `kpi` | tab **Hari Ini** (`TodayDashboard kpi={kpi}`) — jadi KPI TIDAK boleh digerbangi hanya ke tab gabungan | `app/page.tsx:630` |
| Sumber data Kualitas | `useQualitySample(...)`: gerbang `tab === "quality" || tab === "suppliers"`, sampel 8 keputusan | `lib/hooks/useQualitySample.ts:28` |
| Tab di sidebar | daftar `navItems` + penyaring peran; rail bisa dilipat jadi 68px | `app/page.tsx:469-495` |
| Dokumen acuan layar | KPI = screen 7 (`/kpi`), Kualitas Agen = screen "Langkah 5" (`/quality`) | `docs/design.md:65, 68` |
| Tes yang memaku tab | `prd-nav`, `kpi-wiring`, `agent-quality-board`, `agent-quality`, `query`, `supplier-pins`, `supplier-exclusions` | `frontend/tests/` |

## 3. Keputusan pemilik (DIKUNCI 2026-10-15)

| # | Pertanyaan | **Keputusan** |
|---|---|---|
| 1 | **Nama tab baru** | **"KPI & Kualitas Agen"** — eksplisit; dipilih pemilik dari 4 usulan ("Kinerja & Mutu", "Kinerja & Mutu Agen", "Hasil & Mutu", "KPI & Kualitas Agen") |
| 2 | Urutan bagian | **KPI dulu (hasil), lalu mutu agen (cara kerja)** |
| 3 | "Rincian per run" | **tetap tampil penuh** (perilaku sekarang, tanpa `<details>`) |
| 4 | Gerbang muat KPI | **digerbangi** ke `today` + tab gabungan (usulan asisten, tidak dipertanyakan pemilik) — sekarang `useKpi` dimuat di semua tab |

Konsekuensi label: rail bisa dilipat jadi 68px, jadi tab ini WAJIB diperiksa pada keadaan terlipat
(elipsis + `title`/`aria-label` penuh) — label 18 karakter lebih panjang dari "Kualitas Agen".

## 4. Nama & id teknis

- **Label sidebar**: `KPI & Kualitas Agen` (keputusan #1).
- **id tab**: `"kpi-kualitas"` (satu id baru menggantikan `"kpi"` + `"quality"`; dipilih agar sejalan
  dengan label dan mudah dicari di grep).
- **Judul halaman** (`PageHeader` di dalam halaman): sama dengan label sidebar, plus subjudul yang
  menyebut dua bagiannya, mis. "Tujuh indikator kontinuitas pangan institusional, plus mutu kerja
  agen pada sampel keputusan terakhir."
- Tab TIDAK punya URL (state React, tanpa routing) → mengganti id tidak memecahkan tautan/penanda
  yang dipakai user. Yang harus diperbarui hanya kode + tes.

## 5. Susunan halaman gabungan

```text
KPI & Kualitas Agen                              (PageHeader + pill: periode · scope · ukuran sampel)
├─ Bagian 1 — KPI kontinuitas pangan             (KPIDashboard, apa adanya: 7 kartu + status)
└─ Bagian 2 — Mutu kerja agen (sampel N terakhir)
   ├─ Skor agregat                               (AgentQualityBoard, apa adanya)
   ├─ Putusan verifikator
   └─ Rincian per run
```

Alasan urutan: kartu KPI ringkas dan menjawab "apakah tujuannya tercapai"; mutu agen adalah penjelasan
pendukung di baliknya. Pembatas visual antar-bagian memakai pola yang sudah ada (`.board-page` +
kartu), tanpa permukaan desain baru.

## 6. Rencana bertahap

- **6a — Plumbing tab (½ hari).** [SELESAI] Satu id `"kpi-kualitas"` di union `Tab`, `navItems`, dan blok render
  (label sidebar `KPI & Kualitas Agen`); `useQualitySample` `tabRelevan` → `"kpi-kualitas" || "suppliers"`;
  gerbang baru `shouldLoadKpi(tab)` = `today || kpi-kualitas` di `lib/kpi.ts` + `useKpi` menerimanya
  (keputusan #4).
  Tes: label sidebar baru ada; tidak ada lagi id `"kpi"`/`"quality"` di sumber; gerbang KPI murni.
- **6b — Komposisi halaman (½ hari).** [SELESAI] Komponen tipis `components/KpiQualityBoard.tsx` yang menerima
  `kpi` + `kualitas` dan merender kedua bagian berurutan (di dalamnya `KPIDashboard` dan
  `AgentQualityBoard` TIDAK diubah isinya). `app/page.tsx` menyusut: satu blok `<KinerjaMutuBoard …>`.
  Tes markup: kedua bagian ada di SATU halaman, urutannya benar, state loading/error/galat masing-masing
  bagian tidak saling menutupi (KPI gagal ≠ sembunyikan mutu agen, dan sebaliknya).
- **6c — Bukti & dokumen (¼ hari).** [SELESAI] `docs/verification/fase-8.md` (angka DOM: 7 kartu
  KPI + 3 bagian mutu + hitungan sampel; 2 peran: SPPG Head & BGN Monitor), `docs/design.md`
  (screen 7 + Langkah 5 → satu layar; tabel sumber data), `docs/PRD.md` (catatan penyimpangan
  alignment PRD 2.4 dengan alasan), `TODO.md`, `memory/global/decisions.md`.
- **6d — Gate.** [SELESAI] pytest tidak tersentuh (backend tidak berubah) → cukup vitest + tsc + lint + build
  (build dijalankan dengan `next dev` DIMATIKAN lebih dulu, lalu kontainer dev dinyalakan lagi), plus
  pemeriksaan hidup: klik tab gabungan, pastikan kedua bagian terisi dari API.

Perkiraan total: **±1 hari kerja bertahap**.

## 7. Berkas & tes yang tersentuh (blast radius, sudah diperiksa)

- Sumber: `app/page.tsx` (union Tab, navItems, blok render), `lib/hooks/useQualitySample.ts`,
  `components/KpiQualityBoard.tsx` (baru), `lib/kpi.ts` (baru) + `lib/hooks/useKpi.ts`,
  `components/NavIcon.tsx` (union `NavId` — ikon gauge milik tab lama dipakai ulang).
- **Tidak disentuh**: `components/KPIDashboard.tsx`, `components/AgentQualityBoard.tsx`,
  `lib/agent-quality.ts` (isi & perhitungan kedua halaman tetap), seluruh backend.
- Tes yang HARUS diperbarui (memaku id tab lama): `tests/prd-nav.test.tsx`,
  `tests/kpi-wiring.test.tsx`, `tests/agent-quality-board.test.tsx`, `tests/agent-quality.test.ts`,
  `tests/query.test.ts`, `tests/supplier-pins.test.ts`, `tests/supplier-exclusions.test.ts`.
- Tes baru: `tests/kpi-quality-board.test.tsx` (komposisi + urutan + kemandirian galat, 7 tes) dan
  `tests/kpi.test.ts` (gerbang `shouldLoadKpi`, 3 tes) — keduanya sudah dibuat dan lulus.
- CSS: kemungkinan hanya penyesuaian jarak antar-bagian; **tanpa token baru, tanpa hex mentah**
  (aturan mengikat `docs/design.md` §4). Label sidebar yang lebih panjang harus diperiksa pada rail
  68px (elipsis/`title`, bukan terpotong tanpa penjelasan).

## 8. Risiko

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Id tab lama masih terpakai di kode lain | Tab gabungan tidak memuat data / gerbang salah | grep `"kpi"`/`"quality"` sebagai langkah pertama 6a; tes gerbang murni |
| Label 18 karakter di rail terlipat (68px) | Teks terpotong tanpa penjelasan | periksa `.side-*` pada keadaan terlipat; sediakan `title`/`aria-label` penuh; sesuaikan CSS bila perlu |
| KPI tergerbangi padahal tab "Hari Ini" memakainya | Angka KPI "Hari Ini" kosong tanpa error | fakta §2 sudah mencatat pemakai kedua; gerbangnya menyertakan `today` + tes khusus |
| Halaman gabungan terasa panjang | Bagian mutu agen tidak terbaca di demo | keputusan #3; bila perlu, `<details>` pada "Rincian per run" |
| Penyimpangan dari alignment PRD 2.4 (7 screen) | Klaim `prd-nav.test.tsx` & dokumen jadi tidak konsisten | catatan ruling di `docs/PRD.md` + `docs/design.md` + `memory/global/decisions.md` pada 6c |
| Label sidebar lebih panjang di rail 68px | Teks terpotong tanpa penjelasan | periksa CSS rail + `title`/`aria-label` penuh; uji tampilan terlipat |

## 9. Bukti yang akan dibuat (bukan klaim)

1. `vitest`/`tsc`/`lint`/`build` hasil nyata (angka lulus, exit code).
2. DOM halaman gabungan: jumlah kartu KPI (7), tiga judul bagian mutu agen, jumlah baris sampel,
   dan **kontrol negatif** — teks "Target KPI" 0 kemunculan (regresi penghapusan hari ini).
3. Dua peran (SPPG Head, BGN Monitor) — memastikan tab terlihat sama dan datanya sesuai cakupan.
4. `git status`/`git diff --stat` ringkas: berkas yang benar-benar berubah.

## 10. Yang TIDAK termasuk di sini

- Mengubah isi/kartu/perhitungan KPI atau mutu agen (mis. menambah metrik baru).
- Menggabungkan tab lain (Hari Ini, Pemasok, Agent Log) — di luar permintaan.
- Mengubah backend atau menambah endpoint agregat baru (kalau nanti diinginkan satu endpoint
  "kinerja", itu fase tersendiri dengan konsekuensi ruling).
