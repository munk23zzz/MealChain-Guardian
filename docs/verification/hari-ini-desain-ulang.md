# Verifikasi — desain ulang halaman "Hari Ini" (2026-10-17)

Permintaan pemilik (verbatim):

> berati hapus untuk kelender agenda yang yang bukan pop up namun untuk informasi nya tetap
> di pakai, berati anda harus menggunakn skill ui ux untuk meperbaikinya dan 1 page hari ini
> harus di desain ulang ui ux nya anda harus mencari reverensi lalu anda bisa terapkan namun
> utnuk fitur tetap yang saat ini hnay perlu redesign dari segala hal supaya lebih mudah di
> gunakan oleh user

Ringkasnya: **konversi kartu "Kalender agenda" jadi "Agenda harian"** (grid bulan besar di
kartu dihapus, info harinya tetap dipakai) **+ redesain seluruh halaman "Hari Ini"** dengan
referensi yang dicari lebih dulu, **tanpa mengubah fitur**.

## 1. Bentuk yang dipilih pemilik (via pertanyaan beropsi, semua opsi rekomendasi)

1. `‹` `›` di kepala kartu bergeser **satu hari** (bukan satu bulan) + pil "Hari ini";
   lompat ke tanggal jauh lewat **popup pemilih tanggal** (ikon kalender).
2. **Strip ringkasan 5 tile** di atas; tile bisa diklik → lompat ke kartunya.
3. Urutan: **"Perlu tindakan" dulu**, lalu agenda harian.
4. Empat kartu rincian **tampil semua** dalam **bento 2 kolom** (bentuk dirapikan, tidak
   ada yang dilipat secara bawaan).

## 2. Referensi yang dipakai (dan yang ditolak)

- **Agenda hybrid** — uxpatterns.dev, pola *Calendar View*: daftar agenda disusun mengikuti
  tanggal terpilih, panah menggeser satu langkah kecil, pemilih besar hanya saat diminta.
- **Compact date picker** — Apple Human Interface Guidelines: pemicu kecil (ikon) yang
  membuka pemilih; grid sebulan penuh tidak perlu menetap di halaman.
- **Progressive disclosure** — Nielsen Norman Group + Interaction Design Foundation: status
  dulu, rincian belakangan; yang jarang dipakai disembunyikan di balik satu interaksi.
- **Redesain dashboard operasional** — shieldthemes.com (31 Jul 2025) & studi kasus Voyager
  Health (2025): buang grafik pasif, sisakan 4–5 indikator status + daftar pengecualian;
  temukan hal berisiko dalam hitungan detik, bukan menelusuri seluruh halaman.
- **Ditolak**: keluaran `ui-ux-pro-max` `--design-system` (pola LANDING, palet oranye, font
  Fira Sans/Fira Code) — tidak cocok untuk konsol internal dan bentrok dengan token repo.
  Palet & skala tipe tetap milik repo (Bumi Modern: `--ink`/`--surface`/`--accent`,
  `--fs-1..8`); yang diadopsi hanya aturan lintas-produknya (kontras 4.5:1, target sentuh
  44 px, focus terlihat, breakpoint 375/768/1024/1440).

## 3. Perubahan berkas

Baru: `frontend/components/TodaySummary.tsx`, `frontend/tests/today-summary.test.ts`,
`frontend/tests/agenda-day-step.test.ts`, `frontend/tests/today-summary-strip.test.tsx`.

Diubah: `frontend/components/TodayAgendaCalendar.tsx` (grid dibuang, kepala hari),
`frontend/components/TodayDashboard.tsx` (strip + urutan + bento + id kartu),
`frontend/app/page.tsx` (state hari), `frontend/app/globals.css` (gaya strip/agenda/bento),
`frontend/lib/agenda.ts` (`agendaGroups`, `clampDayStep`, `dayOf`),
`frontend/lib/today.ts` (`summaryTiles`, `updatedLabel`, `kpiPeriodLabel`),
`frontend/tests/{today-agenda-calendar,today-dashboard,agenda-wiring}.test.*`.

## 4. Gerbang

| Gerbang | Hasil |
|---|---|
| Vitest (6 berkas fokus) | **85 uji hijau** |
| Vitest (seluruh suite) | **1031 lolos / 1032**; 1 merah = `tests/sidebar-wiring.test.tsx` milik **sesi lain** (`components/DecisionEvidence.tsx` sedang mereka sunting: `<RecommendationCard` dihapus di working tree, tesnya belum ikut) — bukan dari perubahan ini |
| `npx tsc --noEmit` | **0 error** |
| `npm run lint` (next lint) | **0 warning / 0 error** |

TDD: 5 berkas tes ditulis lebih dulu dan dijalankan **RED** (gagal karena implementasi belum
ada), baru implementasi ditulis.

## 5. Verifikasi di browser hidup (SPPG Head, `localhost:3010`, viewport 1262 px)

- Urutan elemen DOM: `page-header → .today-summary → .today-grid → #today-action →
  #today-agenda → .today-detail-grid`.
- Strip: **5 tile × 181 px** dengan nilai yang sama seperti kartunya — *Menunggu tindakan 14*,
  *Batch <48 jam 2*, *Lokasi shortage 1*, *KPI terisi 5/7*, *Rantai audit: Rantai utuh*.
- Kartu agenda: **0 elemen `.agenda-cell`** (dulu grid bulan besar), judul hari
  "**Sabtu, 17 Oktober 2026**", tiga kelompok ("Rencana & pasokan", "Limbah & kedaluwarsa",
  "Keputusan agen", masing-masing 289,7 px), tombol hari `‹ Oktober 2026 › Hari ini`,
  baris tanpa data tetap menulis "tidak ada catatan".
- Bento rincian: `grid-template-columns` = **2 × 465,5 px**; tinggi kartu **257 / 184 / 498 /
  145 px** (tidak direntangkan sama tinggi).
- Kepala halaman menambah pil nyata "**Diperbarui 02.14 WIB**".
- **Luapan horizontal 0 px**; tinggi dokumen 2162 px.

### Probe lebar sempit (bukan viewport 375 px — lihat catatan jujur di bawah)

Kartu agenda dan strip dipaksa selebar **331 px** (≈375 px viewport − padding halaman):

| Elemen | Lebar | Luapan | Anak keluar | Tinggi |
|---|---|---|---|---|
| `#today-agenda` | 331 px | **0** | tidak ada | 566 px |
| `.today-summary` | 331 px | **0** | tidak ada | 413 px |

`.agenda-head` terhitung `flex-wrap: wrap` → keempat kontrolnya membungkus, bukan menghimpit
judul.

## 6. Bug yang ditemukan saat verifikasi hidup (dan diperbaiki)

Kartu agenda terukur **64 px** setelah redesign: aturan `grid-column: span 12` untuk
`.agenda-calendar` hilang saat aturan bobot 7/5 dibuang, jadi kartu jatuh ke 1 kolom dari 12
bento. Diperbaiki (`.today-pending, .agenda-calendar, .today-detail-grid { grid-column: span 12 }`
+ di daftar media query ≤1180 px); sesudahnya terukur **947 px** dan luapan tetap 0.
Ini persis jenis cacat yang tidak akan tertangkap tes jsdom — karena itu pengukuran di
browser tetap dilakukan walau tes sudah hijau.

## 7. Catatan jujur tentang pengukuran lebar

Pengukuran **nyata** dilakukan pada lebar yang memang dimiliki jendela browser
(**1262 px**), sama seperti pengukuran halaman lain di repo ini, plus probe 331 px di atas.
Pengukuran di viewport **375/768/1440 px yang sebenarnya belum dilakukan** untuk halaman ini:
jendela browser di lingkungan ini tidak bisa diubah ukurannya (`window.resizeTo` tidak
mengubah `innerWidth`; `body.offsetWidth` 390 px vs viewport 1262 px) dan memuat halaman ini
di dalam `<iframe>` selebar 375 px tidak menghidrasi aplikasi (isinya kosong), sehingga
"luapan 0 px di 375 px" tidak bisa saya klaim. Yang bisa diklaim: dua blok baru **tidak
meluap dan tidak mengeluarkan anaknya** saat disempitkan ke 331 px, dan aturan pembungkusnya
(`auto-fit minmax(168px/240px, 1fr)`, `wrap`, `.today-detail-grid` → 1 kolom ≤1180 px) membuat
lebar itu terpenuhi secara aritmetika. Bila pemilik ingin angka 375/768/1440 px yang nyata,
itu perlu dijalankan di browser dengan jendela yang bisa diperkecil (mis. DevTools device
toolbar) — saya tidak bisa melakukannya dari sini.

## 8. Langkah 2 — perapian strip ringkasan (keluhan pemilik, 2026-10-17)

Keluhan: *"masih kurang di ukuran font bagian 5 informasi singkat di bawah judul dan
ukuran shape nya kurang pas dan ukuran shape text terlalu besar"*.

Dipandu skill `ui-ux-pro-max` (pencarian `--domain ux` "compact stat tile label value
density" → aturan *Compact Label Overflow*: label pendek tidak boleh membungkus ke baris
kedua, pakai `min-width: 0` + `nowrap`/ellipsis; `--domain typography` → pasangan
"Dashboard Data" Fira Code/Fira Sans = yang sudah dipakai repo; skala tipe dashboard
memakai label 12 px dan angka satu langkah di atasnya).

Terukur SEBELUM (1262 px, SPPG Head) → SESUDAH:

| Ukuran | Sebelum | Sesudah |
|---|---|---|
| Tinggi strip | 89 px | **70 px** (−21%) |
| Bentuk tile | 181×89 px | **183×70 px** |
| Padding / radius / gap | 10px 12px / 12px / 10px | **8px 10px / 10px / 8px** |
| Angka (`.today-tile-value`) | `--fs-5` 18px | **`--fs-4` 16px, bobot 600** |
| Label & keterangan | 12px (keterangan tile 2 membungkus 2 baris) | **12px, semua 1 baris** |
| Kolom | `auto-fit minmax(168px,1fr)` | **5 kolom sama lebar**, ladder 5/3/2 pada ≥1181 / 768–1180 / ≤767 px |

Alasan tiap angka: angka 18 px di bentuk selebar 181 px terbaca seperti judul, bukan
status — turun satu langkah ke 16 px dan bobotnya dinaikkan 600 supaya tidak jadi lemah;
padding/radius/gap dirapatkan karena isinya hanya tiga baris pendek; kolom dibuat
eksplisit agar kelima bentuk identik dan tidak ada bentuk kelima yang jatuh ke baris
kedua; label diberi `min-width: 0` + line-height 1.3 mengikuti aturan *Compact Label
Overflow*. Luapan horizontal tetap 0 px dan tidak ada teks yang terpotong (dicek
`scrollWidth > clientWidth` per baris keterangan: semua `false`).

## 9. Langkah 3 — nilai 5 tile & lencana "Lewat …" (keluhan pemilik, 2026-10-17)

Keluhan: *"untuk bagian 15, 2, 1, 5/7, dan rantai utuh menurut saya itu masih kurang pass
dilihat tampilannya dan bagian informasi 'lewat jam/hari' itu masih terlalu kebesaran"*.

Diperiksa dulu di browser dengan strip dizoom 3× supaya tipografinya benar-benar terlihat.
Temuan: (a) nilai "Rantai utuh" dirender dengan font DATA (Fira Code) — frasa dalam font kode
di bentuk 183 px terbaca seperti potongan kode dan menjadikan satu tile berbeda dari empat
lainnya; (b) warnanya campur — dua tile merah + dua kuning + satu hitam, sementara nada yang
sama sudah dibawa garis kiri, jadi barisnya terbaca gelisah; (c) lencana `.today-due`
terukur **176×26 px** (mono 12px + padding 3px 10px) sehingga satu lencana memakan hampir
seperlima lebar baris dan tampak lebih penting daripada judul keputusannya.

| Ukuran | Sebelum | Sesudah |
|---|---|---|
| Font nilai angka | Fira Code 16px | Fira Code 16px + `font-variant-numeric: tabular-nums` |
| Font nilai frasa ("Rantai utuh") | Fira Code | **Fira Sans** (kelas `.today-tile-value--teks`), 1 baris |
| Warna nilai | 2×`--danger-ink`, 2×`--warn-ink`, 1×`--ink` | **seragam `--ink`**; nada hanya di garis kiri |
| Lencana `.today-due` | 176×26 px, mono, padding 3px 10px | **131–138×24 px**, Fira Sans, padding 2px 8px |

Keputusan "angka vs frasa" tidak ditulis di JSX sebagai `if` ad-hoc, melainkan sebagai fungsi
murni `nilaiAngka()` di `lib/today.ts` (nilai dianggap angka bila tidak memuat huruf sama
sekali) dengan dua uji murni + satu uji markup. Urutannya TDD: tiga uji ditulis lebih dulu,
dijalankan **RED** (`nilaiAngka is not a function`, kelas `--teks` belum ada), baru
implementasi. Lencana mengikuti standar label repo yang sudah ada (docs/design.md §3.8:
12 px, padding 2px 8px, tinggi ±22 px). Tinggi strip tetap 70 px, luapan horizontal 0 px.

## 10. Langkah 4 — nilai tile dipindah ke KANAN (permintaan pemilik, 2026-10-17)

Permintaan: *"atau bagian ini taruh di kanan saja 15, 2, 1, 5/7, dan rantai utuh — ini
−765,8 kg pada halaman overview"*.

Acuan diambil dari halaman **Overview** yang sudah dipakai pemilik: baris `.node-gauge`
(label di kiri, nilai di kolom kanan pada tepi baris — terukur label 12px `--ink-muted`,
nilai 13px Fira Code, `gap: 2px 10px`).

Dua percobaan, dan yang PERTAMA gagal (dicatat supaya tidak diulang):

1. **Label dan nilai berbagi satu baris** (`grid-template-columns: minmax(0,1fr) auto`).
   Terukur: kolom label menyusut jadi **126 px** sedangkan "MENUNGGU TINDAKAN" butuh
   **143 px** (dan "RANTAI AUDIT" butuh 88 px di kolom 65 px karena nilai "Rantai utuh"
   84 px) → **dua label membungkus jadi dua baris** dan baseline nilai tidak lagi sebaris
   dengan baris pertama label. Ditolak.
2. **Label selebar bentuk, nilai menempati barisnya sendiri rata kanan.** Ini yang
   dipakai: label `grid-column: 1 / -1`, nilai `grid-column: 2; text-align: right`,
   keterangan `grid-column: 1 / -1` di baris bawah.

Terukur sesudah (1262 px, SPPG Head):

| Ukuran | Hasil |
|---|---|
| Kelima label | **satu baris** (lebar 159 px, tidak ada yang membungkus) |
| Nilai | rata kanan, jarak ke tepi kanan bentuk **11 px** (= padding 10 px + garis 1 px) di kelima tile, sebaris sempurna (`top` 26 px, `bottom` 44 px untuk semuanya) |
| Keterangan | baris bawah, selebar bentuk (159 px) |
| Bentuk | 183×70 px (tidak berubah), tinggi strip 70 px, luapan horizontal 0 px |

Nilai kini sejajar sebagai satu kolom angka di tepi kanan kelima bentuk — sejalan dengan
pola Overview yang diminta pemilik, dan label tetap utuh tanpa pemotongan (`ellipsis`)
maupun pembungkusan.
