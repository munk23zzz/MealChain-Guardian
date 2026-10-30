# Verifikasi Location Network — L5, L6, L7 (30 Okt 2026)

Halaman: tab `location-network` (`components/LocationNetworkBoard.tsx`).
Rencana: `_qa/rencana-redesign-location-network-2026-10-29.md` §L5–L7.
Pratinjau: `_qa/preview/location-network.html` (360 · 760 · 1247 · 1440 px,
`renderToStaticMarkup` + `globals.css`/`theme-ext.css` asli di iframe).

## L5 — Rencana alih & Limbah: satu keluarga bentuk

| Yang diminta | Bukti |
|---|---|
| Kepala dua kartu sama: judul + pil jumlah + satu kalimat | `board-card-head` + `count-pill` (`2 pasangan`, `30 hari`) + `board-card-sentence`; terlihat di pratinjau |
| Limbah: tiga angka sejajar, satuan + jendela | `FactList` sudah dilepas; `card-figures` dengan `data-figure="tercatat|dialihkan|tanpa-mitra"`, "belum dicatat" tetap `—` |
| Rencana alih jadi kartu berlabel ≤760 px | `data-label` pada 5 sel × 2 baris; mode kartu di blok `@media (max-width: 760px)` tersendiri (lihat catatan di bawah) |
| Baris tujuan yang dibuka ditandai teks | `sedang dibuka` muncul sekali, di baris `highlight`; tidak muncul saat tidak ada rincian terbuka |

Catatan desain: aturan mode kartu tabel alih **tidak** ditempel di blok media
papan lokasi. Tes L3 (`location-network-kartu.test.tsx` → "tabel lain tidak ikut
jadi kartu") menjaga isi blok itu tetap ber-scope `.network-table*`; menumpang
di sana membuat tabel lain ikut berubah. Blok media kedua, di akhir berkas,
memuat `.allocation-table*` + `.board-table-wrap.allocation-table-wrap`.

## L6 — Responsif, aksesibilitas, gerak

Diukur dari DOM hidup di dalam pratinjau (`getBoundingClientRect`,
`getComputedStyle`), bukan disimpulkan dari CSS:

| Lebar | `scrollWidth − clientWidth` | Target < 44 px | Teks < 12 px |
|---|---|---|---|
| 360 px | **0** (345 = 345) | **0** | 0 |
| 760 px | **0** (745 = 745) | 4 — semua tautan nav bagian (30 px), di luar daftar kontrol L6 | 0 |
| 1247 px | **0** (1232 = 1232) | 12 — pil komoditas 32 px + nav 30 px (batas 44 px hanya untuk perangkat sentuh) | 0 |
| 1440 px | **0** (1425 = 1425) | idem | 0 |

- Target 44 px dipatok di `@media (pointer: coarse), (max-width: 760px)` untuk
  empat kontrol yang diminta: pil komoditas, tombol baris, tombol tutup rincian,
  tombol "Coba lagi" (kelas baru `.location-retry`).
- Cincin fokus: `outline: 2px solid var(--ink)` + `outline-offset: 2px` untuk
  keempat kontrol; tidak ada `outline: none`.
- Gerak: `@media (prefers-reduced-motion: reduce)` mematikan transisi baris,
  sel, dossier, dan baris yang bisa diklik.
- Disclosure: satu tombol pembuka per baris, `aria-expanded` + `aria-controls="rincian-lokasi"`.

Tes baru: `tests/location-network-akses.test.ts` (4 tes),
`tests/location-network-alih-kartu.test.tsx` (4 tes).

## L7 — Verifikasi penutup

| Gerbang | Hasil |
|---|---|
| `tsc --noEmit` | 0 galat |
| Vitest lingkup Location Network | **146 lulus / 146** (13 berkas) |
| `next lint` | tidak ada peringatan/galat |
| `next build` | sukses · **BUILD_ID `PGF50HyQ9W827Ltkhij2B`** (build ulang setelah blok CSS tabel alih dipindah ke blok media sendiri) |
| Pratinjau statis | `_qa/preview/location-network.html` (360/760/1247/1440) |

Gerbang selesai §5 rencana: (1) satu filter, satu pil tanggal, 4 tujuan nav ✓
(2) angka jaringan sekali ✓ (tes neraca) (3) tidak ada paragraf > 120 karakter ✓
(4) `scrollWidth − clientWidth = 0` pada 360/760/1247 ✓ (diukur) (5) tidak ada
target < 44 px & teks < 12 px pada 360 px ✓ (6) `aria-expanded`/`aria-controls`
benar, satu tombol pembuka per baris ✓ (7) tsc 0 · vitest hijau · build sukses ✓.

## Yang tidak dikerjakan (sengaja)

- Peta/garis koridor — keputusan pemilik 28 Okt 2026.
- Tautan nav bagian (30 px) dan pil komoditas di desktop: batas 44 px hanya
  berlaku di perangkat sentuh; menaikkannya di desktop akan menambah tinggi
  baris kendali tanpa manfaat jari.
- Data dossier di pratinjau memakai `detail={null}` sehingga kartu rincian
  menampilkan "Belum ada lokasi yang dipilih." — bentuk dan ukurannya tetap
  terukur, isinya bukan bagian dari L5–L7.
