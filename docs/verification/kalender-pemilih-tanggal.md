# Kalender agenda — langkah 3: popup pemilih tanggal (2026-10-17)

> **Snapshot 17 Oktober 2026 (dari waktu berkas)** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

Permintaan pemilik: *"perbaiki fitur kalender… saya mau kalender yang mana sebuah icon
kecil yang bisa di klik dan menampilkan pop up untuk memilih tanggal bulan tahun"*
(didahului riset karena diminta: "sebelum membuatnya di frontend anda research dulu").

## Masalah yang diperbaiki

Kepala kalender tab "Hari Ini" hanya punya tombol ‹ › dan judul bulan sebagai **teks
mati**: tidak ada cara melompat bulan/tahun, sehingga Oktober 2026 → Oktober 2025
butuh 12 klik. Ini keluhan yang paling sering dicatat di literatur date picker
("make the month and year directly clickable; forcing twelve clicks of a chevron to
move one year is the single most common date picker sin"). Verifikasi awal di browser
hidup mengonfirmasi: `Oktober 2026` adalah `<span>`, bukan kontrol.

## Keputusan yang dipegang

1. **Tanpa dependensi baru.** Dibandingkan tiga jalur: (a) hand-rolled di atas
   `Popup.tsx` + fungsi murni, (b) `react-day-picker` v9/v10, (c) `<input type="date">`
   + `showPicker()` native. Yang dipilih (a) — repo ini memegang pola "logika murni di
   `lib/` yang diuji, cangkang UI memakai `Popup` yang sudah ada, ikon inline SVG".
   Native ditolak karena isi popup dikendalikan peramban dan **tidak bisa menampilkan
   titik "hari punya catatan"**; `showPicker()` juga tidak ada di Safari iOS.
2. **Grid dipakai bersama.** `components/AgendaMonthGrid.tsx` melayani kartu DAN popup,
   jadi bentuk sel (42 sel mulai Senin, `data-date`/`data-activity`, aria-label
   bertanggal lengkap, tepat satu `aria-current`) tidak bisa berbeda antara keduanya.
3. **Bulan DRAFT dimiliki halaman.** Popup boleh menelusuri bulan lain tanpa
   mengubah kartu: `agendaPickerMonth` (draft) vs `agendaMonth` (kartu). Rentang draft
   diminta ke `GET /agenda` lewat hook yang sama, dan **hanya saat popup terbuka**
   (saklar `enabled` baru di `useAgenda`) — membuka tab "Hari Ini" tidak memuat dua
   bulan sekaligus.
4. **Daftar tahun bukan angka karangan.** `pickerYears(RANGE_MIN, RANGE_MAX, tahunAktif)`
   memakai rentang data yang didukung backend (`lib/demo-data.ts` → 2026–2027) dan
   selalu menyertakan tahun yang sedang tampil, supaya `<select>` tidak pernah
   menampilkan nilai di luar daftarnya sendiri.
5. **Bulan yang belum termuat menulis status MEMUAT**, bukan grid kosong: grid kosong
   akan terbaca sebagai "bulan ini tidak punya catatan" — klaim yang belum bisa
   dibuktikan. Aturan anti-angka-palsu repo juga berlaku di titik ini.
6. **Fokus kembali ke pemicu.** `Popup` menerima `returnFocusRef` ke tombol pemicu,
   jadi pengguna keyboard tidak dilempar ke awal dokumen saat popup ditutup.
7. **Kolom tanggal di tab Demo Control TIDAK diubah** (keputusan pemilik): `input
   type=date` di sana sudah punya ikon + popup bawaan peramban.

## Bukti tes (RED lebih dulu)

25 uji baru: `tests/agenda-date-picker.test.tsx` **15** (jsdom, interaksi sungguhan:
klik sel, ganti dropdown, Escape, fokus kembali), `tests/today-agenda-calendar.test.tsx`
**+3** (header jadi pemicu `aria-haspopup="dialog"`/`aria-expanded`, ‹ › & "Hari ini"
tetap ada, draft tidak mengubah header kartu), `tests/agenda.test.ts` **+3**
(`monthChoices`, `pickerYears` termasuk tahun di luar rentang), `tests/agenda-wiring.test.ts`
**+4** (bulan draft milik halaman, `useAgenda(..., agendaPickerRange, agendaPickerOpen)`,
satu prop `agendaPicker`, komponen tidak memanggil API).

Gerbang frontend setelah perubahan: **80 berkas / 945 uji hijau**, `tsc --noEmit`
0 error, `next lint` bersih. Putaran gerbang terakhir di sesi ini menunjukkan
**82 berkas / 955 uji hijau** (angka naik karena sesi Hermes LAIN menambah berkas uji `??`
di repo yang sama) dan `next lint` tetap bersih, sedangkan `tsc` saat itu merah **hanya di
berkas milik sesi lain yang sedang disunting** (`components/SupplyMap.tsx` 01:17:24, lalu
`components/ShipmentBoard.tsx`) — bukan berkas pekerjaan ini, dan putaran tsc sebelumnya 0
error. Satu tes sesi lain (`tests/route-line-split.test.ts`) pernah merah di suite penuh
tetapi lulus 10/10 saat dijalankan sendiri: isolasi, bukan regresi. Tidak ada commit
menyeluruh yang dibuat karena repo sedang dikerjakan dua sesi.

## Bukti di browser hidup

`localhost:3010`, SPPG Head, tab "Hari Ini":

- header kartu sekarang berbunyi `‹ [ikon kalender] Oktober 2026 › Hari ini`; pemicunya
  punya nama aksesibel "Pilih bulan dan tahun — sekarang Oktober 2026";
- klik pemicu → dialog "Pilih tanggal" (`aria-modal=true`), deskripsi "…Tahun yang
  tersedia 2026–2027.", `select[aria-label="Bulan"]` 12 bulan Indonesia (nilai 10),
  `select[aria-label="Tahun"]` = 2026 (opsi 2026 & 2027), 42 sel, tombol "Hari ini" +
  "Tutup";
- ganti draft Bulan → **September**: grid popup menjadi 31 Agu–11 Okt dengan titik
  catatan September (1–6 Sep masing-masing 3 bagian berisi) **sementara kartu di
  belakang tetap Oktober 2026** (draft tidak bocor);
- klik sel **1 Sep** → popup tertutup (`aria-expanded=false`), kartu pindah ke
  "September 2026", sel aktif 2026-09-01, panel "Selasa, 1 September 2026": rencana menu
  **1.217 porsi** · pasokan **6 baris** · harga 7 baris — **cocok dengan catatan
  verifikasi langkah 2** (`docs/verification/kalender-agenda-harian.md`);
- ganti Tahun → **2027**: grid 30 Agu–10 Okt 2027, **0 hari bercatatan** dan tidak ada
  status memuat yang tersisa (jujur, bukan nol karangan);
- tekan **Escape** → popup tertutup dan `document.activeElement` kembali ke tombol
  pemicu (dikonfirmasi via DOM);
- konsol: 0 galat JS baru (peringatan `defaultProps` recharts sudah ada sebelumnya,
  dari `StockChart`).

## Residual

- Navigasi keyboard antar sel grid (arrow/PageUp-PageDown) belum ada — sama seperti grid
  besar yang sudah ada; semua sel tetap bisa dicapai dengan Tab dan dipilih dengan Enter.
- Bulan di luar rentang data (mis. 2027) menampilkan grid tanpa titik; itu memang
  perilaku yang diinginkan (jujur), bukan bug.
