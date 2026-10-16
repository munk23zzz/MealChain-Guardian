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
