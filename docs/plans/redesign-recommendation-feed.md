# Rencana redesign — halaman "Recommendation Feed"

Status: **tahap 1–4 selesai (30 Okt 2026)**; tahap 5–7 belum. Dibuat 30 Okt 2026, melanjutkan pola
`redesign-food-safety.md` (tahap 1–7 yang sudah selesai).

Acuan gaya: `docs/design.md` (token warna, radius, gerak) + skill `ui-ux-pro-max`
(aturan UX yang lolos verifikasi; hasil katalog yang tidak cocok ditolak dan
dicatat di §3).

---

## 1. Keadaan sekarang (terukur, bukan kesan)

| Hal | Angka | Sumber |
|---|---|---|
| Baris kendali sebelum kartu pertama | **4** berlapis: `.feed-toolbar` (cari+urut) · `.kpi-period.feed-period` (periode) · `.feed-filters` (chip status) · `.feed-status-row` (hitungan+reset) | `app/page.tsx:1981-2122` |
| Tempat angka yang sama dicetak | **3**: pill di kepala halaman ("N rekomendasi · 7 hari", "N lewat tenggat"), chip status (angka per status), baris "Menampilkan X dari Y" | `page.tsx:1933-1945`, `2062-2121` |
| Tepi kiri berwarna pada kartu | `4px` × **5 nada** (`--accent-strong`, `--status-warning`, `--status-danger`, `--ink-muted`, `--line-strong`) | `.rec-edge::before` |
| Tombol biru penuh di daftar | **1 per kartu** → 10 tombol primer bersaing per halaman | `.rec-act-btn--utama` |
| Judul kartu | `<p class="rec-title">`, bukan heading | `RecommendationCard.tsx:160` |
| Kelas CSS mati (tak dipakai kode) | **6**: `feed-row`, `feed-row-meta`, `rec-meta`, `rec-value`, `rec-expired`, `rec-route` | grep 0 kemunculan di `app/` + `components/` |
| Selektor yang ditulis berulang | `.recommendation-card dl` **3×**, `.feed` **2×**, `.rec-badges` **2×**, `.feed-toolbar` **2×**, `.feed-period-hint` **2×**, `.rec-act-btn` **2×**, `.recommendation-card` **2×** | hitung di `app/globals.css` |
| Kontrol & fokus | input/select/anchor `:focus-visible` sudah ada; chip & pill ber-`aria-pressed`; chip `flex-wrap` | `.feed-field …:focus-visible`, `.filter-chip` |
| Gerak | animasi `feed-row-in` per baris + `prefers-reduced-motion` **sudah** memagari `.feed > div` | `globals.css` |

**Kesimpulan diagnosis.** Masalah halaman ini bukan kekurangan fitur — pencarian,
urutan, periode, saringan status, paginasi, popup rincian, dan keadaan kosong
semuanya sudah ada. Masalahnya **kepadatan kendali dan bobot visual**: empat
baris kontrol mendorong sepuluh kartu ke bawah lipatan, status ditulis di tiga
tempat, setiap kartu menawarkan tombol biru penuh, dan tingkat urgensi
diulang sebagai garis tepi berwarna padahal sudah tertulis di lencana.

Prinsip yang dipakai: **satu fakta, satu tempat**; **aksen biru hanya untuk satu
hal yang memblokir**; **bukan warna saja** untuk menyatakan keadaan.

---

## 2. Yang TIDAK akan diubah

- `lib/decision-feed.ts` (267 baris) — logika saringan/urutan/jendela/paginasi
  sudah diuji (`decision-feed.test.ts` 282 baris, `feed-pagination.test.ts`,
  `feed-window-wiring.test.ts`). Redesign ini tampilan, bukan logika.
- Nama kelas yang dipin tes: `rec-act-btn rec-act-btn--utama`, `rec-komoditas`,
  `rec-qty`, `rec-narrative`, `rec-act`, `rec-hint`, `feed-period`.
  (`tests/recommendation-card.test.tsx`, `tests/feed-window-wiring.test.ts`.)
  Bobot tombol diubah lewat CSS, **bukan** dengan mengganti nama kelas.
- `Popup`/`DecisionDrawer` sebagai tujuan tombol "Tinjau" — alur baca → tinjau →
  setujui tetap satu pintu.
- Atribut `data-*`, `aria-*`, dan teks yang diuji tidak berubah kecuali
  dinyatakan eksplisit di tahap yang bersangkutan.

---

## 3. Bukti katalog skill (dan yang ditolak)

Kueri yang dijalankan (skill `ui-ux-pro-max`, `--domain ux`):

| Kueri | Hasil | Dipakai? |
|---|---|---|
| `status conveyed by color only badge` | **Color Only** (Accessibility, High) + **Contextual Live Badge Updates** | **Ya** (tahap 2 & 4) |
| `empty state next action` | **Empty States** (Feedback, Medium) | **Ya** (tahap 5) |
| `filter chips with counts clickable` | **Chip Collection Reflow** (Layout, High) — bungkus, jangan klip | **Ya** (tahap 2 & 6) |
| `list toolbar too many rows density` | *Excessive Motion*, *Container Width* | **Tidak** — tidak menjawab kepadatan kendali |
| `card list scan hierarchy primary button every row` | *Back Button*, *Input Labels* | **Tidak** — tidak relevan |
| `--stack nextjs` "list pagination search filter" | **0 hasil** ("No matches") | Tidak ada padanan basis data |

Karena kueri kepadatan dan hierarki tidak punya padanan, urutan tahap mengikuti
**tabel prioritas bawaan skill** (Aksesibilitas → Sentuh → Gaya → Layout →
Tipografi → Gerak → Formulir) dan bukan selera. Ini disebut apa adanya: bukan
hasil pencarian katalog.

---

## 4. Tahapan

### Tahap 1 — Empat baris kendali menjadi satu — **selesai 30 Okt 2026**

**Hasil:** keempat blok kendali kini anak dari satu `.feed-kendali`
(`display:flex; flex-wrap:wrap; align-items:flex-end`). Margin bawaan tiap blok
dinolkan lewat `.feed-kendali > …`; baris hitungan menempel ke ujung kanan
(`margin-inline-start:auto`) dan tidak menyisakan slot kosong saat tak ada
saringan. Di ≤720 px pita menumpuk (`flex-direction:column`), bukan menggulir.

**Koreksi terhadap rencana ini sendiri:** butir "pill *N lewat tenggat* dilepas
karena chip status sudah memuatnya" **tidak dijalankan** — setelah diperiksa,
klaim itu keliru. Chip status adalah kategori status (`pending_action`,
`menunggu persetujuan`, …), sedangkan "lewat tenggat" adalah keadaan waktu yang
dihitung `countExpiredActionable`. Keduanya tidak saling menggantikan, jadi pill
itu tetap ada. Yang benar-benar ganda hanyalah angka "N rekomendasi · periode"
versus baris "Menampilkan X dari Y" — dan itu sudah diselesaikan di tahap 1 dengan
menjadikan baris hitungan `sr-only` saat tidak menyaring (perilaku lama,
dipertahankan).

**Uji:** `tests/feed-kendali-pita.test.tsx` (5 uji) mengunci: hanya satu pita,
keempat blok ada di dalamnya, urutan DOM (jadi urutan Tab) tidak berubah,
tidak ada blok kendali tertinggal di luar pita, dan CSS menolkan margin anak
serta menumpuk di layar sempit.

#### Rencana awal tahap ini (dipertahankan sebagai catatan)

**Ubah:** `page.tsx` 1981–2122 + CSS `.feed-toolbar`, `.feed-period`,
`.feed-filters`, `.feed-status-row`.

- Satu wadah `.feed-kendali`: baris pertama = input cari (melebar) + `Urutkan`
  (selebar isinya) + pemilih periode (chip kecil) + chip status; baris kedua
  (hanya bila ada saringan) = hitungan + "Kosongkan filter".
- Label `Cari rekomendasi`/`Urutkan` tetap ada sebagai `<label>` terlihat
  (bukan placeholder-only) tetapi dipadatkan sebaris dengan bidangnya.
- Angka di kepala halaman: sisakan **satu** pill (`N rekomendasi · periode`);
  pill "N lewat tenggat" dilepas karena chip status sudah memuatnya dan tenggat
  terbaca di setiap kartu.
- Baris "Menampilkan X dari Y" tetap `role="status"`; saat tanpa saringan ia
  tetap `sr-only` seperti sekarang (jangan dihapus — pembaca layar butuh rentang).

**Selesai bila:** tes `feed-window-wiring` + `feed-pagination` lulus tanpa
perubahan; markup hanya punya **satu** wadah kendali; `grep` membuktikan pill
"lewat tenggat" tidak lagi dirender ganda.

### Tahap 2 — Chip status menjadi ringkasan yang bisa dibaca sekali lihat — **selesai 30 Okt 2026**

**Hasil:** urutan chip ternyata **sudah** benar (`feedChips` menaruh "Perlu
tindakan" di depan, sisanya mengikuti `STATUS_ORDER`) — jadi yang dikerjakan
adalah tiga hal lain:

- chip berangka **0** dinonaktifkan (`disabled={habis && !aktif}`), tetapi chip
  yang sedang aktif **tidak** ikut terkunci supaya pengguna masih bisa
  melepasnya; angkanya tetap terlihat;
- `aria-label` per chip menyebut cakupan + jumlah ("Saring daftar ke Menunggu
  persetujuan: 7 rekomendasi"), `aria-pressed` tetap;
- angka chip "Perlu tindakan" ditebalkan lewat `data-utama` + tipografi — bukan
  warna baru (aksen biru tetap milik chip aktif dan tombol Tinjau).

**Tidak menambah live region kedua.** `feed-status` (`role="status"`
`aria-atomic`) sudah mengabarkan "Menampilkan X dari Y · filter: …" saat chip
ditekan. Aturan *Contextual Live Badge Updates* menolak beberapa pengumuman
bersaing; tes menegaskan hanya ada **satu** `role="status"` di tab ini.

**Warna chip kosong:** `--ink-subtle` di atas `--surface-sunken` = **4,95:1**,
bukan `opacity` (opacity 0,5 menjatuhkan teks itu ke ± 2,6:1 dan gagal AA).

**Uji:** `tests/feed-chips-ringkasan.test.tsx` (7 uji). Dua di antaranya
mengoreksi ekspektasi saya sendiri: urutan status sebenarnya `proposed →
approved → executed` (bukan tebakan saya), dan `approved` **termasuk**
`ACTIONABLE_STATUSES` sehingga chip "Perlu tindakan" bernilai 0 harus diuji
dengan status `executed`/`rejected`.
Satu tes lama (`feed-pagination`) menulis bentuk `setFeedScope(...)` yang persis;
diperbarui ke bentuk `aktif ? …` dengan perilaku yang tetap diuji.

#### Rencana awal tahap ini (dipertahankan sebagai catatan)

**Ubah:** `.feed-filters` + `filter-chip` + `lib/decision-feed.ts` (hanya urutan
daftar chip bila perlu).

- Urutan: **Perlu tindakan** lebih dulu, lalu sisanya; angka pada chip tebal,
  label biasa.
- Chip dengan hitungan **0** → `disabled` + `aria-disabled`, bukan tombol yang
  tidak mengubah apa pun.
- `aria-label` eksplisit per chip ("Saring daftar ke Menunggu persetujuan: 7"),
  `aria-pressed` tetap; satu `role="status" aria-atomic="true"` mengumumkan
  perubahan ("Saring: menunggu persetujuan — 7 dari 17").
- Chip tetap `flex-wrap` (aturan *Chip Collection Reflow*: jangan memotong baris).

**Selesai bila:** tes baru `feed-chips-summary.test.tsx` (klik chip → daftar
tersaring + pengumuman terbaca + chip 0 tidak bisa ditekan) lulus.

### Tahap 3 — Satu bobot aksi, bukan sepuluh tombol biru — **selesai 30 Okt 2026**

**Hasil:**

- `.rec-act-btn--utama` (bawaan) kini `background: var(--surface)` +
  `color: var(--accent-strong)`; biru penuh hanya pada `:hover`/`:focus-visible`.
  Nama kelasnya tidak disentuh (`rec-act-btn rec-act-btn--utama` dipin tes).
- Judul kartu `<h3>` + daerah daftar `<section className="feed"
  aria-labelledby="feed-judul">` dengan `<h2 className="sr-only">Daftar
  rekomendasi</h2>`, jadi tingkatannya h1 → h2 → h3.
- Baris meta **sudah** sesuai rencana sejak sebelum tahap ini (`.rec-qty` dan
  `.rec-komoditas` = `--ink`, `.rec-meta-line` = `--ink-muted`); tidak ada yang
  diubah, hanya dikunci tes supaya tidak mundur.

**Kesalahan yang saya buat dan perbaiki di tahap ini:** komentar `{/* … */}`
pertama kali saya sisipkan tepat setelah `(` cabang ternary — di posisi itu ia
bukan JSX dan membuat `app/page.tsx` gagal di-parse (15 error `tsc`, dev server
500). Dipindah ke dalam `<section>`. **Dan**: `FEED_SCOPE_ACTION` dipakai di
`data-utama` (tahap 2) tetapi belum diimpor — lolos `vitest` dan `eslint` karena
keduanya tidak memeriksa tipe, baru tertangkap `tsc`. Impor ditambahkan.

**Uji:** `tests/feed-satu-bobot-aksi.test.tsx` (6 uji): `<h3>` menggantikan
`<p>`, `h2` sr-only ada dan benar-benar `position:absolute`, aturan dasar tombol
tidak lagi berisi biru penuh, `:hover`/`:focus-visible` berisi biru penuh,
kontras teks 5,17:1 dan tepi ≥3:1, `.rec-title` tetap `margin:0`.

#### Rencana awal tahap ini (dipertahankan sebagai catatan)

**Ubah:** CSS `.rec-act-btn--utama` + `RecommendationCard.tsx` (hanya struktur
judul).

- `Tinjau` dari biru penuh → **garis biru, isi putih**; saat hover/fokus baru
  menjadi biru penuh. Alasan: tidak ada satu kartu pun yang "utama"; sepuluh
  tombol biru penuh membuat tidak ada yang menonjol dan menambah berat visual
  daftar. Kelas tetap `rec-act-btn rec-act-btn--utama` (dipin tes).
- Judul kartu jadi `<h3>` di dalam `<article>`, dengan **satu `<h2>` untuk
  daerah daftar** ("Daftar rekomendasi", boleh `sr-only` bila tidak ingin
  menambah teks). Halaman punya `h1` dari `PageHeader`; tanpa `h2` di antaranya,
  `h1 → h3` melompati tingkat heading dan itu kegagalan urutan heading —
  karena itu `h2` ikut ditambahkan, bukan hanya mengganti satu tag. Bila tes
  memaku `<p class="rec-title">`, tes diperbarui **dan** alasan perubahan
  dicatat di tesnya.
- Baris meta: komoditas + kg tetap `--ink` 600; "biaya aman …" dan waktu jadi
  `--ink-muted` (dua fakta sekunder yang tidak perlu bersaing dengan kg).

**Selesai bila:** `recommendation-card.test.tsx` lulus (dengan penyesuaian
heading bila ada), kontras teks ≥ 4,5:1 terukur, dan tidak ada tombol biru penuh
di daftar saat tidak di-hover.

### Tahap 4 — Tepi berwarna dilepas, status dibawa kata — **selesai 30 Okt 2026**

**Hasil:** pseudo-elemen `.rec-edge::before` (pita 4 px) beserta **lima** aturan
nadanya (`edge-primary` aksen, `edge-warning` amber, `edge-danger` merah,
`edge-expired` abu tua, `edge-neutral` abu) dihapus seluruhnya. Rencana menulis
"→ 1 px `--line`"; ternyata itu sudah diberikan `.card` (tepi 1 px `--line` di
keempat sisi), jadi menambah pseudo-elemen 1 px hanya menumpuk garis. Yang
tersisa: permukaan `--surface-sunken` untuk kartu lewat tenggat — permukaan,
bukan garis berwarna.

Kelas nada **tetap** ada di DOM dari `cardEdge()` (lima nada, seluruhnya masih
diputuskan) supaya tingkat urgensi terbaca mesin dan bisa dipakai lagi tanpa
menggali logika — hanya tampilannya yang berhenti berwarna.

**Uji:** `tests/feed-tepi-netral.test.tsx` (5 uji): tidak ada `.rec-edge::before`
sama sekali, tidak ada `background: var(--status-…/accent-…/warn/danger)` di
aturan `.rec-edge`, kartu lewat tenggat tetap lewat permukaan, kontrak
`cardEdge()` lima nada utuh, dan lencana status + masa berlaku tetap dicetak
(satu-satunya pembawa keadaan sekarang).

#### Rencana awal tahap ini (dipertahankan sebagai catatan)

**Ubah:** CSS `.rec-edge::before` dan lima nada `.edge-*`.

- Tepi 4 px berwarna → **1 px `--line`** untuk semua nada. Status sudah tertulis
  di `StatusBadge` ("Diusulkan", "Ditolak", …) dan di lencana masa berlaku
  ("lewat tenggat"), jadi warna tepi mengulang informasi yang sama
  (*Color Only*: jangan jadikan warna satu-satunya pembawa makna — di sini malah
  pengulangan yang tidak perlu).
- Kartu lewat tenggat **tetap** berlatar `--surface-sunken` (itu permukaan, bukan
  garis berwarna) karena kekontrasan teks sekunder di atasnya masih lolos AA.
- Nada tetap dipertahankan di markup (`edge-danger` dkk.) — hanya tampilannya
  dinetralkan, supaya data tingkat urgensi tidak hilang dari DOM dan bisa dipakai
  lagi tanpa menggali logika.

**Selesai bila:** `grep` pada CSS yang dilayani menunjukkan hanya satu warna tepi
(`--line`), dan `food-safety`/`recommendation` tes tetap hijau.

### Tahap 5 — Keadaan kosong & galat: jalan keluar, bukan kotak kuning

**Ubah:** `.feed-empty` + blok empty/error di `page.tsx`.

- Kotak putus-putus `--status-warning` → panel netral (`--surface-sunken`,
  garis `--line`) dengan **tiga** hal: satu kalimat sebab, satu aksi utama,
  satu aksi sekunder (mis. "Kosongkan filter" + "Lihat 1 bulan terakhir").
- Galat muat: kalimat + tombol "Coba lagi" (sudah ada) diberi `role="alert"`
  supaya diumumkan, bukan hanya terlihat.
- Aturan *Empty States*: pesan + aksi, bukan layar kosong.

**Selesai bila:** tes baru memeriksa tiga bagian itu ada saat filter kosong dan
saat galat, dan warna kotak tidak lagi `--status-warning`.

### Tahap 6 — Kepadatan, responsif, dan gerak

**Ubah:** `.feed`, `.recommendation-card`, media query ≤720 px.

- Jarak antar kartu 8 → **10 px**; padding kartu tetap 14/16 px (sudah disetel
  pemilik). Target: 10 kartu terasa satu daftar, bukan sepuluh kotak terpisah.
- ≤720 px: kendali menumpuk (cari selebar penuh, chip menggulir-bungkus),
  lencana kembali bertumpuk (sudah), tombol Tinjau selebar kartu dengan tinggi
  ≥ 44 px.
- Gerak: animasi masuk `feed-row-in` dipertahankan **hanya** untuk 6 baris
  pertama (sudah) dan dipastikan tetap dipagari `prefers-reduced-motion`
  (sudah ada — diverifikasi, bukan ditambah).
- `scroll-margin-top` pada kartu pertama agar lompat dari chip tidak menutupi
  judul di bawah `SectionJump`/top bar (pola `.jump-target` yang sudah dipakai
  Food Safety).

**Selesai bila:** tes baru `feed-density.test.tsx` mengunci: jumlah baris
kendali, tinggi target sentuh tombol, dan tidak adanya `transition` baru tanpa
pagar reduced-motion.

### Tahap 7 — Konsolidasi gaya + gerbang mutu

**Ubah:** `app/globals.css`.

- Hapus **6 kelas mati**: `feed-row`, `feed-row-meta`, `rec-meta`, `rec-value`,
  `rec-expired`, `rec-route`.
- Satukan selektor ganda: `.recommendation-card dl` (3×), `.feed` (2×),
  `.rec-badges` (2×), `.feed-toolbar` (2×), `.feed-period-hint` (2×),
  `.rec-act-btn` (2×), `.recommendation-card` (2×) — sisakan satu aturan
  efektif per selektor, dengan komentar tanggal+alasan bila maknanya berubah.
- Gerbang `tests/feed-css-gate.test.ts` (pola `safety-css-gate.test.ts`):
  kelas `feed-*`/`rec-*` yatim · kelas JSX tanpa definisi · kontrol tanpa
  `:focus-visible` · `transition`/`animation` tanpa pagar reduced-motion ·
  kontras baris meta ≥ 4,5:1 · tidak ada `font-size` < 12 px.

**Selesai bila:** gerbang 6–8 uji hijau, suite penuh tetap 0 gagal, `t