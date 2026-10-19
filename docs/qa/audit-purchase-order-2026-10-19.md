# Audit Purchase Order (19 Okt 2026)

Permintaan pemilik: *"Purchase order (mock lokal) untuk bagian ini tolong di audit secara
rinci dan ketat dong, bagaimana cara kerja dia dan proses, logika nya bagaimana supaya
jelas dan kata kata di fe tolong di perbaiki supaya seperti aplikasi bukan demo."*

Dokumen ini mencatat **apa yang benar-benar terjadi di kode**, bukan apa yang ingin
diklaim UI, lalu apa yang diubah dan buktinya.

---

## 1. Cara kerja (jalur tulis)

| Langkah | Kode | Fakta |
|---|---|---|
| 1. Keputusan dieksekusi | `backend/app/api/actions.py` (`/actions/execute`) | Hanya `sppg_head`; gerbang: approval matrix terpenuhi, TTL keputusan belum lewat (409), pemasok masih eligible, batch keamanan pangan diverifikasi ulang (409 bila gagal), komoditas/kuantitas/harga valid (422). |
| 2. Nomor PO | `app/core/nomor_po` | `MC-` + 12 heksa pertama UUID keputusan — deterministik, jadi eksekusi ganda tidak melahirkan nomor acak. |
| 3. Baris PO ditulis | `actions.py` → `INSERT INTO sap_mock_purchase_orders … status 'submitted'` | Harga = `safe_delivered_cost / quantity_kg` (2 desimal), bahan = `MAT-<KOMODITAS>`, `decision_id` terisi. |
| 4. Efek samping | `actions.py` | `decision.status = 'executed'`, jejak `ACT` (`sap_mock.create_purchase_order`), blok Merkle. |
| 5. Keputusan ditolak/di-repropose | `actions.py` | **Tidak** menerbitkan PO dan **tidak** menulis `ACT` — "approval belum berarti komitmen ke SAP". |

## 2. Cara kerja (jalur baca)

- `GET /sap/purchase-orders` (`backend/app/api/sap_orders.py`) — read-only, filter
  `status`, `decision_id`, `limit` (dijepit 200).
- `GET /sap/purchase-orders/summary` — jumlah per status + total nilai.
- Cakupan dari peran (`core/scope.py`): `sppg_head`/`sppg_nutritionist` hanya PO yang
  keputusannya bertarget lokasinya; `bgn_monitor` lintas lokasi **termasuk** baris tanpa
  keputusan (`decision_id IS NULL`).
- `origin` = `"execution"` bila `decision_id` terisi, `"demo"` bila tidak.
- `total_value` = `price × ordered_quantity` (dihitung dari kolom, tidak disimpan ganda).

## 3. Temuan audit (dengan bukti)

1. **Status `draft` adalah status hantu.** `CHECK` mengizinkan `draft`, tetapi tidak ada
   satu pun penulis yang menulisnya — jalur eksekusi selalu `submitted`, seeder hanya
   `submitted`/`confirmed`. UI lama tetap menampilkan chip `draf 0`.
2. **`confirmed` bukan hasil proses aplikasi.** `actions.py` menulis `'submitted'` untuk
   PO yang lahir dari eksekusi; `confirmed` hanya muncul dari data seed/impor
   (`app/seed/demo_activity.py`) dan dari `MockSAPProvider` (`Status: "confirmed"`).
   Tidak ada endpoint transisi status. Ground truth DB saat audit: **2 `submitted`,
   14 `confirmed`**; 12 di antaranya baris impor tanpa keputusan.
3. **Label "dari eksekusi" keliru.** `demo_activity.py` menulis PO `MC-*` dengan
   `decision_id` **tanpa** melewati `POST /actions/execute`; karena `origin` hanya
   melihat `decision_id`, empat baris seed tampil sebagai "dari eksekusi". Fakta yang
   bisa dibuktikan hanyalah "tertaut ke keputusan".
4. **Total `Rp 0,00` saat ringkasan gagal.** `summary?.total_value ?? 0` membuat panel
   menulis "Total nilai Rp 0,00" padahal daftar berisi 16 PO — melanggar aturan repo
   "kosong ≠ nol".
5. **`count` = panjang daftar terbatas.** Server menjepit `limit` ke 200 dan mengembalikan
   `count = len(items)`; ringkasan tahu total sebenarnya. Tanpa penanda, daftar 200 baris
   terbaca sebagai seluruh populasi.
6. **Panel terbaca sebagai "PO keputusan ini".** Panel duduk tepat di bawah detail
   keputusan tetapi isinya seluruh PO dalam cakupan; tidak ada penanda baris mana milik
   keputusan yang sedang dibuka.
7. **Bahan mentah internal di layar.** `material_number` ditampilkan apa adanya
   (`MAT-BERA`, `1000`), dan seeder memakai dua konvensi berbeda (`MAT-{nama}` di
   `actions.py`, `MAT-{nama[:4]}` di `demo_activity.py`) sehingga tebakan dari kode
   menghasilkan kata rusak ("Bera").
8. **Bahasa demo, bukan bahasa produk.** Judul "Purchase order (mock lokal)" dan kalimat
   "Dibaca dari tabel transaksi mock di DB demo" membocorkan nama tabel/DB ke pengguna.

## 4. Perbaikan

**Kontrak data**

- `/sap/purchase-orders` kini mengirim `commodity_name` dari relasi
  `decisions.commodity_id → commodities.name` (`LEFT JOIN commodities`). UI memakai nama
  itu; untuk baris impor tanpa keputusan nilainya `null` (tidak dikarang).

**Copy & informasi (frontend `components/PurchaseOrderList.tsx`)**

- Judul: **"Purchase order"** + chip **"SAP simulasi"** (penanda kejujuran tetap,
  `Rules.md §4`).
- Sub per cakupan: "Data dari SAP simulasi di lingkungan ini (bukan SAP S/4HANA
  produksi). Anda melihat PO untuk SPPG Anda." / "… Cakupan nasional: seluruh lokasi,
  termasuk PO tanpa keputusan."
- Chip status hanya dirender untuk status yang benar-benar punya baris (`draf 0` hilang),
  dengan nada token sistem: terkirim = aksen biru, terkonfirmasi = hijau aman.
- Satu kalimat arti status (`lifecycleNote`): *"Terkonfirmasi adalah PO yang sudah ada di
  data SAP dan diimpor ke aplikasi ini; PO yang diterbitkan dari eksekusi keputusan di
  aplikasi ini tercatat Terkirim."*
- Asal baris: "dari keputusan" / "impor SAP" / "asal tidak tercatat".
- Baris milik keputusan yang sedang dibuka: garis kiri aksen + label **"keputusan ini"**
  dan tautan berubah menjadi "Buka keputusan" (`page.tsx` meneruskan `decisionId`).
- Total: `—` bila ringkasan belum/gagal termuat (`formatRupiahOpsional`), bukan `Rp 0,00`.
- Daftar terpotong: "Menampilkan 200 dari 1.234 PO terbaru."
- Bahan: `commodity_name` → fallback nomor bahan (`Bahan 1000`) → "bahan tidak tercatat";
  tidak ada penerjemahan tebakan.

## 5. Verifikasi

| Gerbang | Hasil |
|---|---|
| `pytest tests/test_sap_orders_api.py` | **12 passed** (termasuk tes baru `test_nama_komoditas_dari_keputusan_bukan_tebakan_kode`) |
| `vitest tests/purchase-orders.test.tsx` | **17 passed** |
| `tsc --noEmit` | 0 error |
| Live `:3010` (SPPG Head) | judul "Purchase order", chip "SAP simulasi", sub jujur, chip "terkonfirmasi 2", total Rp 32.880.000,00, baris `MC-661695B2C685 … beras`, penanda "keputusan ini" muncul di baris yang tepat setelah membuka `?keputusan=…` |
| Live `:3010` (BGN Monitor) | 16 baris, chip "terkirim 2" + "terkonfirmasi 14", asal "dari keputusan"/"impor SAP", baris impor `4500000001 … Bahan 1000 … tanpa keputusan`, total Rp 179.749.434,00 |
| Overflow | `.po-panel` 947 px, tidak ada elemen dengan `scrollWidth > clientWidth` |

## 7. Tindak lanjut: tombol "Lihat keputusan" (laporan pemilik, 19 Okt 2026)

Gejala: diklik, terasa "tidak berfungsi".

Sebab: tautan memakai `href="?keputusan=<id>"` **tanpa penangan klik**, jadi klik =
navigasi penuh (reload). Setelah reload halaman mulai dari gulir 0, dan pengguna yang
sedang melihat daftar PO di dasar halaman tidak dibawa ke keputusan yang dituju —
pilihan berubah, tetapi tidak terlihat.

Perbaikan: `PurchaseOrderList` menerima `onOpenDecision`; klik kiri memanggil
`bukaKeputusanDariPO` di `page.tsx` (set `selectedId` + tab `evidence`, lalu
`scrollIntoView` ke `#ringkasan`). `href` tetap ada supaya Ctrl/Cmd-klik membuka tab baru
dan tautan bisa disalin.

Bukti live (SPPG Head, sebelum → sesudah klik baris `MC-661695B2C685`):

| Ukuran | Sebelum | Sesudah |
|---|---|---|
| Reload halaman | ya (navigasi penuh) | **tidak** (penanda `window` bertahan) |
| Keputusan terpilih | `#e7aba250` | `#661695b2` — "Alihkan 600 kg beras: Jakarta → Jakarta" |
| `scrollY` | 2848 (panel PO) | 165, `#ringkasan` 120 px dari atas → kartu keputusan terlihat |
| Penanda baris | tidak ada | "keputusan ini" pada baris yang diklik |
| URL | `?keputusan=e7aba250…` | `?keputusan=661695b2…` (tanpa reload) |

Gerbang uji baru: `frontend/tests/purchase-order-decision-link.test.tsx` (3 tes, jsdom) —
klik kiri memanggil penangan + `defaultPrevented`, Ctrl-klik tidak, `href` tetap ada.

**Kesalahan pengujian saya sebelumnya (dicatat supaya tidak terulang):** verifikasi lama
hanya memeriksa bahwa URL dan penanda "keputusan ini" berubah, lalu saya menyimpulkan
"tautan berfungsi". Yang tidak diperiksa: apakah halaman dimuat ulang, apakah pengguna
dibawa ke keputusan, dan apakah isi keputusan benar-benar berganti. Penanda bisa muncul
tanpa perubahan yang terlihat oleh pengguna — itu bukti yang lemah.

## 8. Yang sengaja TIDAK diubah

- Status `confirmed` tidak "dipalsukan" menjadi transisi aplikasi: tidak ada endpoint
  konfirmasi ke SAP, jadi UI menjelaskan asalnya (impor) daripada mengarang proses.
- Cakupan peran, gerbang approval, dan aturan keamanan pangan tidak disentuh.
- `origin: "execution"` tetap nama field-nya di API (kontrak + tes backend); yang berubah
  hanya kata yang dibaca pengguna.
