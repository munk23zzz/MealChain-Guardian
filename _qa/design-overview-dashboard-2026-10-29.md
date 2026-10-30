# Design Overview — Overview, Location Network, Decision & Evidence
Tanggal: 29 Okt 2026 · Basis: skill `ui-ux-pro-max` (design-system + chart + ux) · Repo: `mealchain-guardian/frontend`

## 0. Dasar desain (hasil kueri, bukan selera)

Kueri `--design-system "institutional food supply chain monitoring dashboard operational data dense"
--variance 3 --motion 3 --density 8` mengembalikan:

- **Pola:** Real-Time / Operations — telemetry hanya boleh disebut *live* kalau ada sumber + waktu pembaruan + keadaan basi.
- **Gaya:** Minimalism & Swiss — grid, hierarki tipografi, tanpa dekorasi.
- **Tipografi:** Fira Sans (UI) + Fira Code (angka) — **sudah dipakai repo**, jadi tidak ada migrasi font.
- **Warna:** hijau operasional + merah insiden + amber pemeliharaan; kontras teks ≥ 4,5:1; status tidak boleh warna saja.
- **Gerak:** 300–400 ms halus, reduced-motion menghormati `prefers-reduced-motion`.
- **Hindari:** dashboard lambat, grafik dekoratif, keadaan galat tersembunyi.

Kueri domain: `chart "horizontal bar chart supply vs demand surplus regions"` → untuk perbandingan kategori ≤ 15 gunakan **bar horizontal terurut menurun** dengan label langsung; untuk performa vs target gunakan **bullet chart**. Kueri `ux "provenance evidence audit trail trust indicators"` **tidak punya entri katalog yang cocok** (hasilnya soal required field/progress) — bagian Jejak Kepercayaan di bawah memakai aturan prioritas skill (a11y, hierarki data, keadaan eksplisit), bukan hasil pencarian. Ini dicatat supaya tidak terbaca sebagai "rekomendasi basis data".

Batasan yang dipegang dari repo: font minimum `var(--fs-1)` (12 px), token warna dari `globals.css`, angka memakai `--font-data`, tanpa emoji sebagai ikon.

---

## 1. Jejak kepercayaan (`components/TrustTrailCard.tsx`)

**Keadaan sekarang.** Empat sel 2×2; tiap sel: label, nilai + satuan, keadaan (titik + kata), dan `foot` (alasan). Kepala kartu: judul + satu lencana nada. Semua angka dari `lib/trust-trail` (murni, teruji).

**Yang membuatnya belum "rapih".**
1. Empat sel berbobot sama, padahal tiga di antaranya pendukung satu kesimpulan — mata tidak tahu mana yang harus dibaca lebih dulu.
2. Tidak ada waktu pembaruan; "77 blok tertaut" tanpa "per kapan" tidak bisa diperiksa.
3. `foot` selalu dicetak (baik, jangan diubah) tetapi tidak bisa diklik ke tempat buktinya.
4. Keadaan ditulis per sel, tetapi tidak ada keadaan halaman: "satu bukti tidak tersedia" tenggelam di antara tiga yang aman.

**Arah baru.**
- **Kepala:** judul + **kesimpulan satu kalimat** (mis. "Tiga dari empat bukti segar") + `Diperbarui 15.42 WIB`. Lencana nada tetap, tetapi nada ditentukan `trustSummary` (tidak ada logika baru di komponen).
- **Badan:** ubah 2×2 menjadi **daftar bukti 4 baris** (bukan kotak): `label · nilai (mono, rata kanan) · keadaan · sumber`. Baris = `role="listitem"`, seluruh baris fokusabel bila punya tujuan.
- **Bobot:** satu angka dipromosikan (Evidence Completeness sebagai "seberapa lengkap bukti"), tiga lain `--fs-3`; bukan empat angka besar bersaing.
- **Sumber:** tiap baris punya tautan 1 kata — `ledger`, `batch`, `eksekusi`, `node` — menuju tab/panel yang memuat buktinya. Bukti yang tidak bisa ditelusuri ditulis "tidak ada tautan", bukan dibiarkan kosong.
- **Keadaan:** kosakata tetap tiga: `SEGAR` / `PERLU DICEK` / `TIDAK TERSEDIA`; warna hanya penguat.
- **Kosong:** bila `metrics` kosong → satu kalimat "Belum ada bukti yang dilaporkan" + alasan, bukan empat sel kosong.

**Kriteria terima.** (a) waktu pembaruan terlihat; (b) setiap baris punya tujuan yang bisa dibuka; (c) 4,5:1 kontras; (d) `role="list"` + label per baris; (e) tidak ada angka dihitung di komponen.

---

## 2. Kecukupan pasokan (`SupplyAdequacyChart.tsx` / `AdequacyColumns.tsx`)

**Keadaan sekarang.** Dua komponen memakai judul sama ("Kecukupan pasokan"): satu bar horizontal per baris, satu bar vertikal 28 Okt; ada toggle "sudut pandang" (komoditas ↔ lokasi). Keduanya membaca sumber data yang sama dan dipilih di `page.tsx`.

**Yang belum rapih.**
1. Dua komponen untuk satu judul = dua tampilan yang bisa menyimpang; pengguna tidak tahu mana yang kanonik.
2. Bar menunjukkan "pasokan" dan "kebutuhan" tetapi **target 100%** tidak digambar, jadi "cukup/kurang" hanya bisa dibaca dari angka.
3. Urutan tidak dijelaskan; bar terpanjang belum tentu yang paling perlu tindakan.
4. Satuan (kg) hanya muncul di sebagian label.

**Arah baru — satu panel, bullet chart.**
- **Ringkasan 3 angka di kepala:** `n lokasi kurang · n cukup · n surplus` (dari respons, dijumlah di lib murni + tes).
- **Baris:** satu baris per kategori (komoditas di mode komoditas, lokasi di mode lokasi). Skala tunggal `0..maks(kebutuhan, pasokan)`. Bar pasokan + penanda kebutuhan (garis vertikal) → selisih terbaca tanpa membaca angka.
- **Urut menurun berdasarkan defisit absolut**, surplus di bawah; header menyebut urutannya.
- **Label langsung** di ujung bar (`780 kg kurang`) — bukan legenda warna.
- **Keadaan:** `no_data` menampilkan "belum ada catatan pasokan/permintaan" + tautan ke sumber; bukan bar nol.
- **Toggle sudut pandang** tetap, tetapi diberi satu kalimat penjelas dan disimpan di URL (`?sudut=lokasi`) supaya bisa dibagikan.
- **Konsolidasi:** `AdequacyColumns` dipensiunkan setelah paritas angka terbukti (tes membandingkan kedua keluaran sebelum dihapus).

**Kriteria terima.** (a) satu panel kanonik; (b) penanda kebutuhan terlihat; (c) satuan tercetak; (d) urutan dijelaskan; (e) tabel alternatif (sr-only atau `<details>`) untuk pembaca layar.

---

## 3. Surplus wilayah lain (`SurplusRegionPanel.tsx`)

**Keadaan sekarang.** Panel kembar kecukupan: bar horizontal per wilayah, memuat asal surplus teratas, judul berubah "Surplus per wilayah" saat tidak ada `excludedLocation`.

**Masalah.** Bentuknya identik dengan panel kecukupan sehingga dua panel bersebelahan terbaca sebagai grafik yang sama dua kali; tidak ada jarak/waktu tempuh; tidak ada jalan dari "wilayah X surplus 685 kg" ke aksi.

**Arah baru — daftar peringkat, bukan grafik kembar.**
- **Baris:** `Wilayah · surplus kg (mono) · jarak km · estimasi tiba (jam) · bisa menutup N% kekurangan Jakarta`.
- **Kemampuan menutup celah** dihitung dari `surplus_kg / gap_kg` (lib murni + tes) — ini yang mengubah "surplus di mana" jadi "surplus mana yang berguna".
- **Keadaan:** wilayah tanpa surplus tidak ditampilkan (bukan bar nol); bila semua nol → satu kalimat "Tidak ada wilayah surplus untuk komoditas ini".
- **Aksi:** satu tombol `Buat alokasi` per baris **hanya** jika pengguna berperan dan ada keputusan yang bisa dibuat; tanpa itu tombol tidak dirender (bukan disabled tanpa alasan).
- **Peta:** tidak ditambahkan di sini. Peta sudah punya tab sendiri; menaruh peta kecil di panel ini akan menduplikasi legenda dan menggeser fokus.

**Kriteria terima.** (a) angka surplus + jarak + estimasi tiba terlihat; (b) persentase penutup celah; (c) tidak ada bar nol; (d) urut menurun.

---

## 4. Location Network (`components/LocationNetworkBoard.tsx`)

**Keadaan sekarang.** Empat kartu bertumpuk: keadaan jaringan (kalimat + daftar kelengkapan), tabel lokasi (kolom kondisional `Batch ≤Xh`), rencana alih, limbah 30 hari. Filter komoditas di kepala. Ada legenda "bertanda = catatan belum lengkap".

**Masalah.**
1. Kesimpulan ("keadaan jaringan") berbentuk paragraf di kartu terpisah dari tabel yang membuktikannya — pembaca harus memindahkan sendiri kalimat ke baris.
2. Kolom tabel muncul/hilang menurut data, sehingga lebar kolom melompat antar pemuatan.
3. "Bertanda" tidak menjelaskan penanda apa; catatan kaki tidak menyebut kolom.
4. Rencana alih dan limbah berada di bawah tabel dengan bobot visual sama, padahal keduanya konsekuensi, bukan Diagnosis.

**Arah baru.**
- **Susunan:** `[3 KPI kepala] → [tabel lokasi] → [2 kolom: Rencana alih | Limbah]`.
  - KPI kepala: jumlah lokasi kurang · total defisit kg · jumlah catatan basi (>X jam). Semua dari `kelengkapan` + saldo, dihitung di `lib/` (bukan di komponen).
- **Tabel jadi bintang halaman:** header lengket, `table-layout: fixed`, kolom tetap: `Lokasi · Wilayah · Selisih (kg) · Batch ≤Xh · Tindakan`. Kolom yang datanya kosong tetap dicetak dengan "—" supaya lebar tidak melompat.
- **Selisih:** angka + tanda + nada (kurang merah, cukup netral, surplus hijau) **dan kata** ("kurang 780 kg").
- **Penanda kelengkapan:** ikon kecil + `title`/teks di kolomnya sendiri (`Catatan`), bukan bintang tanpa keterangan. Legenda dihapus bila kolomnya ada.
- **Rencana alih:** kartu, bukan tabel kedua; satu baris per pasangan sumber→tujuan dengan kg dan status.
- **Limbah:** angka 30 hari + tautan ke tab Safety untuk rincian.
- **Mobile (<760 px):** tabel berubah menjadi daftar kartu per lokasi (nama, kurang/surplus, batch, tindakan), tanpa geser horizontal.
- **Keadaan:** memuat → skeleton dengan tinggi sama (CLS < 0,1); galat → satu kalimat + tombol coba lagi; kosong → kalimat sebab, tabel tidak dirender (aturan yang sudah dipakai sekarang, dipertahankan).

**Kriteria terima.** (a) tiga angka kepala; (b) tidak ada lompatan lebar kolom; (c) penanda dijelaskan di tempatnya; (d) mobile tanpa geser horizontal; (e) angka dari satu sumber.

---

## 5. Decision & Evidence — blok "Jejak agen keputusan ini" DIHAPUS

**Keputusan pemilik (29 Okt 2026, kedua kalinya).** Blok `<article class="card"><h2>Jejak agen keputusan ini</h2>` beserta `DecisionTraceList` dilepas dari dossier.

**Yang dieksekusi.**
- `components/DecisionDetail.tsx`: artikel + impor + prop `traces` dihapus.
- `components/DecisionEvidence.tsx`: prop `traces` dan penerusannya ke detail dihapus.
- `app/page.tsx`: `traces={...}` pada `DecisionEvidence` dihapus (data `traces` tetap dipakai tab Agent Log).
- `components/DecisionTraceList.tsx` + `tests/decision-trace-list.test.tsx` dihapus (tidak ada pemakai lain).
- `app/evidence-dossier.css`: seluruh aturan `.trace-*` dihapus; sekalian ditemukan bahwa **§14–§17 tercetak dua kali** di berkas ini (218 + 242 baris) → salinan lama dibuang, sisa 601 baris, kurung kurawal seimbang.

**Yang menggantikan (bukan dibiarkan kosong).** Di kartu "Jejak & riwayat" tambahkan satu tautan teks: `Lihat langkah agen di tab Agent Log →` yang membuka tab dengan `run_id` keputusan ini. Jejak tetap ada di produk, hanya pindah ke rumahnya (Agent Log sudah menampilkannya per keputusan).

**Konsekuensi.** Dossier Decision & Evidence sekarang berbicara soal **bukti dan persetujuan** (angka, PO, tanda tangan, audit), bukan soal urutan langkah agen. Ini menghilangkan dua cerita panjang berbeda (7 tahap pipeline vs 9 baris review) di satu halaman.

---

## 6. Token & aturan bersama (tidak menambah sistem baru)

| Kebutuhan | Token/nilai |
|---|---|
| Ukuran huruf | `--fs-1` 12 px (minimum) … `--fs-8` 32 px |
| Angka | `--font-data` (Fira Code) + `font-variant-numeric: tabular-nums` |
| Jarak | kelipatan `--space-1..6` (4/8/12/16/24/32) |
| Sudut | `--radius`, `--radius-control`, `--radius-control-sm` |
| Warna status | `--status-safe`, `--status-warning`, `--status-danger`, `--ink-muted` |
| Nada sel/bar | `color-mix(...)` dengan permukaan, bukan hex baru |
| Gerak | 90/160/240 ms (`--dur-1..3`), `prefers-reduced-motion` mematikan transisi |
| Fokus | `outline: 2px solid var(--accent-strong); outline-offset: 2px` |
| Target sentuh | ≥ 44×44 px untuk tombol di baris tabel (mobile) |

**Aksesibilitas wajib:** status selalu kata + warna; tabel punya `<caption>`/`scope`; grafik punya alternatif teks; ikon dekoratif `aria-hidden`; tombol ikon punya label; tidak ada teks < 12 px.

---

## 7. Urutan eksekusi yang disarankan (satu langkah, satu verifikasi)

1. **Hapus jejak agen dari Decision & Evidence** — ✅ selesai (lihat §5), diverifikasi `tsc` + suite frontend.
2. **Jejak kepercayaan** — tata ulang jadi 4 baris bukti + waktu pembaruan + tautan sumber. Tes: `trust-trail` (lib) tetap; tambah tes render untuk waktu + tautan.
3. **Kecukupan pasokan** — konsolidasi ke satu bullet chart; tes paritas angka dengan komponen lama sebelum `AdequacyColumns` dihapus.
4. **Surplus wilayah lain** — daftar peringkat + persentase penutup celah; tes urutan dan keadaan kosong.
5. **Location Network** — 3 KPI + tabel kolom tetap + mobile kartu; tes lebar kolom stabil dan keadaan kosong.

Setiap langkah: `npx tsc --noEmit` bersih, suite frontend hijau, `tests/design-tokens-kontrak.test.ts` tetap lulus (menjaga font minimum).

## Perubahan token 29 Okt 2026 — aksen biru dilepas

Permintaan pemilik: "hapus warnanya". Aksen biru tidak lagi dipakai sebagai warna
antarmuka di dashboard mana pun. Yang berubah hanya NILAI token di `app/globals.css`
`:root`; ratusan aturan yang merujuknya tidak disentuh:

| Token | Sebelum | Sesudah |
|---|---|---|
| `--accent-strong` (aksi primer, `--primary`, `--focus-ring`) | `#2563EB` | `var(--ink)` `#0F172A` |
| `--accent` (hover aksi primer) | `#1D4ED8` | `var(--navy-700)` `#334155` |
| `--accent-soft` (rail aktif, chip peran) | `#EFF6FF` | `var(--surface-sunken)` `#F1F5F9` |
| `--trust-accent` / `--terminal-accent` | biru | `var(--ink)` |
| `--shadow-brand` (`theme-ext.css`) | `rgba(37,99,235,.28)` | `rgba(15,23,42,.18)` |

Kontras setelah perubahan: teks putih di atas `--accent-strong` 17,9:1; cincin fokus
(alias token yang sama) tetap terlihat di atas `--surface` maupun `--surface-sunken`.

**Sengaja TIDAK diubah** (biru di sana membawa arti, bukan hiasan): `--status-*`
(aman/tinjau/bahaya), `--status-live`, `--route-live-soft/strong`, `ROUTE_LIVE_COLORS`
di `lib/supplier-routes.ts`, tint `app/map-console.css`, serta palet kategori grafik
`--cat-*-*`. Kalau pemilik ingin peta dan grafik ikut netral, itu perubahan terpisah
karena menghapus pembeda seri dan rute.
