# W-5 — Purchase order mock SAP terbaca (17 Okt 2026)

> **Snapshot 17 Oktober 2026** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

Status: **selesai, terverifikasi**. Rute: `GET /sap/purchase-orders` dan
`GET /sap/purchase-orders/summary`; UI: panel "Purchase order (mock SAP)" di tab
**Decision & Evidence**, nomor PO di drawer tidak berubah dan di jejak agent (ACT).

## 1. Masalah yang ditutup

`sap_mock_purchase_orders` sudah lama **ditulis** `api/actions.py` setiap kali
keputusan dieksekusi, dan seed menambahkan tiga PO `DEMO-PO-*`. Tetapi:

| Fakta | Bukti (sebelum perbaikan) |
|---|---|
| Baris PO di DB demo | `SELECT count(*)` → 11 |
| Rute yang membacanya | **0** (`grep '@router' purchase` → kosong) |
| Jejak di layar | toast sesaat `DecisionActions.tsx:127` |
| `SAPDataProvider.get_purchase_orders()` | dipanggil **hanya** oleh tes kontrak |
| Dossier keputusan | tidak menyebut PO |

Artinya klaim "dua approval → PO terbit di SAP" tidak punya permukaan yang bisa
ditunjukkan. W-5 menambahkan sisi baca tanpa mengubah satu baris pun jalur tulis.

## 2. Aturan implementasi (yang membuat ini bukan pembaca palsu)

1. **Sumber = tabel `sap_mock_purchase_orders`**, BUKAN
   `MockSAPProvider.get_purchase_orders()` — provider itu mengembalikan dict
   `_POS` hardcoded di modulnya, sehingga daftarnya tidak akan sama dengan PO
   yang benar-benar diterbitkan. Adapter tetap jalur yang benar untuk
   `SAP_MODE=aws_mcp` nanti (di mode itu sumbernya memang SAP).
2. **Read-only**: tanpa POST/PUT/PATCH/DELETE. Terukur 405 untuk keempatnya.
3. **Cakupan** mengikuti `core/scope.py` (Ruling 2026-10-14): SPPG hanya PO
   bertarget lokasinya; `bgn_monitor` lintas lokasi; PO tanpa keputusan
   (tanpa lokasi) **tidak pernah** terlihat SPPG.
4. **Tanpa hitung ulang**: `ordered_quantity` & `price` dibaca apa adanya;
   `total_value = price × qty` hanya untuk tampilan.
5. **Label sumber di layar**: "Dibaca dari tabel transaksi mock di DB demo —
   bukan SAP S/4HANA nyata."

## 3. Hasil verifikasi

### 3.1 Tes
- `backend/tests/test_sap_orders_api.py` — 10 tes (kontrak kolom, label sumber,
  cakupan kepala vs monitor vs ahli gizi lokasi lain, filter status/decision_id,
  jepitan limit, summary mengikuti cakupan, 401 tanpa token, 405 untuk rute tulis).
  RED sebelum implementasi: **10 failed** (rute 404). GREEN sesudah: **10 passed**.
- `frontend/tests/purchase-orders.test.tsx` — 9 tes (label & format rupiah/kg,
  kalimat sumber, deep link `?keputusan=`, baris tanpa keputusan tidak menaut,
  daftar kosong ≠ Rp 0, galat ≠ daftar kosong, trace ACT menyebut nomor PO).
  RED sebelum komponen ada; GREEN sesudah.
- **Gerbang penuh** (HEAD `1447e9b` + W-5): backend **992 passed / 3 skipped /
  0 failed** (522 s, 20:50). Sebelum W-5 angka yang sama adalah 982 passed —
  selisih 10 = tes W-5, tidak ada tes lama yang hilang atau dilonggarkan.
  Frontend: `vitest run` **100 berkas / 1195 tes passed**, `tsc --noEmit` bersih,
  `next lint` bersih, `ruff check` (berkas W-5) bersih.

### 3.2 API hidup (token demo, nilai rahasia tidak dicetak)
| Peran | `scope` | jumlah | lokasi terlihat | by_status |
|---|---|---|---|---|
| `sppg_head` (Jakarta) | lokasi | 3 | Jakarta | submitted 2 · confirmed 1 |
| `sppg_nutritionist` (Jakarta) | lokasi | 3 | Jakarta | submitted 2 · confirmed 1 |
| `bgn_monitor` | nasional | 11 | Bandung, Jakarta, Surabaya | submitted 7 · confirmed 4 |

`openapi.json`: 55 → **57 path**. Proxy Next: `/sap/purchase-orders` → 401 tanpa
token (bukan 404 HTML ⇒ rewrite `sap` di `next.config.js` benar).

### 3.3 Layar (browser, login tombol demo)
- **SPPG Head** → Decision & Evidence: chip `draf 0 · terkirim 2 · terkonfirmasi 1`,
  total **Rp 45.238.305,84**, 3 baris (`DEMO-PO-JAKA-AYAM`, `MC-2C6EBEF348D2`,
  `MC-4AA0C3655C73`), semuanya Jakarta, kalimat sumber versi lokasi.
- **BGN Monitor** → 11 baris, `terkirim 7 · terkonfirmasi 4`, total
  **Rp 150.488.373,04**, tiga lokasi, kalimat sumber versi nasional.
- Tautan `?keputusan=<uuid>` bekerja; baris tanpa keputusan menulis "tanpa keputusan".
- `AgentTraceViewer` menampilkan "PO MC-… diterbitkan (mock SAP)" pada langkah ACT.

## 4. Temuan sampingan saat gerbang penuh

1. **Cacat data, bukan cacat kode:** pemasok demo `Wortel Malino` tersimpan dengan
   id acak (`e94cdca6…`), padahal kontrak seed menuntut UUID5
   `demo_supplier::<nama>`. `seed_demo_suppliers()` mencocokkan **nama** dan tidak
   pernah memperbaiki id, jadi baris itu bertahan dan membuat
   `test_suppliers_data.py::test_demo_rows_use_their_natural_key_ids` gagal.
   Perbaikan: baris tanpa referensi dihapus, seeder dijalankan ulang (created 1) →
   **18 passed**. Ini **bukan** akibat W-5 (W-5 tidak menulis apa pun).
2. **5 baris PO tanpa keputusan** (`4500000001`, `MC-8DDD…`, `MC-DFEB…`,
   `MC-54ED…`, `MC-F8CD…`, `MC-44A9…`) adalah residu run/seed lama: tidak punya
   `decision_id`, jadi hanya terlihat monitor dan ditandai "tanpa keputusan".
   Tidak dibersihkan di W-5 karena bukan bagian dari lingkup, tetapi layak
   dirapikan sebelum demo (bersama 29 keputusan lewat tenggat).

## 5. Batas yang dinyatakan, bukan disembunyikan
- Data PO adalah **mock**: tabel di DB demo. Tidak ada SAP S/4HANA, tidak ada
  panggilan jaringan ke SAP. Panel menuliskannya di setiap render.
- Tidak ada probe operasional; ini endpoint baca DB, bukan pemeriksaan integrasi.
- Status PO hanya `draft | submitted | confirmed` (sesuai CHECK constraint);
  W-5 tidak menambah transisi status apa pun.
