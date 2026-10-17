# Merapikan data demo (17 Okt 2026, 21:0x WIB)

Tujuan: layar demo bersih dari residu run tes — tanpa menyentuh kode, tanpa
merusak rantai bukti, dan tanpa memalsukan apa pun. Semua angka di bawah diukur
sebelum/sesudah di DB yang sama (`mealchain`).

## 1. Temuan: apa yang sebenarnya mengotori layar

| Gejala di layar | Isi DB sebelum dirapikan |
|---|---|
| Lonceng: "4 menunggu tindakan · **29 lewat tenggat**" | 318 keputusan: 283 `proposed` (279 lewat tenggat) + 32 `pending_approval` (29 lewat) + 5 executed + 5 rejected + 1 flagged |
| Panel PO (monitor): 11 baris | 7 PO `MC-*` tanpa keputusan (yatim) + 3 `DEMO-PO-*` + 1 `4500000001` |
| Picklist keputusan penuh baris mati | keputusan `origin='seed'` bertanggal 7–17 Okt, sebagian besar buatan run tes |

Bukti bahwa itu residu, bukan konten: `load_seed()` **tidak membuat keputusan sama
sekali** (tidak ada INSERT ke `decisions` di `app/seed/seed_data.py`), sedangkan
`/demo/data-status` melaporkan `decisions {seed: 316, demo: 10}`. Jadi 316 baris
`seed` itu seluruhnya hasil tes/alur lama, dan 10 baris `demo` adalah kasus skrip.

## 2. Tindakan (satu transaksi, dengan dry-run lebih dulu)

Dry-run `BEGIN … ROLLBACK` lebih dulu: 316 keputusan → 535 trace, 23 approval,
265 evidence (semua **CASCADE**), 2 PO jadi yatim (**SET NULL**), dan **1
`supplier_exclusions` menahan** (FK `NO ACTION`).

```sql
BEGIN;
DELETE FROM supplier_exclusions              -- penahan NO ACTION, status 'proposed',
 WHERE source_decision_id IN (SELECT id FROM decisions      -- buatan tes 16 Okt 19:10
        WHERE demo_case IS NULL AND origin='seed')
    OR restoration_decision_id IN (SELECT id FROM decisions
        WHERE demo_case IS NULL AND origin='seed');
DELETE FROM decisions WHERE demo_case IS NULL AND origin='seed';   -- 316 baris
DELETE FROM sap_mock_purchase_orders
 WHERE decision_id IS NULL AND po_number LIKE 'MC-%';               -- 7 baris yatim
COMMIT;
```
Hasil: `DELETE 1` · `DELETE 316` · `DELETE 7`.

**Yang sengaja dipertahankan:** 10 keputusan demo (3 pending, 3 rejected,
3 executed, 1 flagged), 3 `DEMO-PO-*`, baris adapter `4500000001`, 27 trace kasus
demo, seluruh `ledger_blocks`.

## 3. Hasil terukur sesudahnya

| Pemeriksaan | Sebelum | Sesudah |
|---|---|---|
| Keputusan | 318 | **10** (semua `origin='demo'`) |
| `/demo/data-status` → decisions | seed 316 · demo 10 | **seed 0 · demo 10** |
| Lonceng notifikasi | "4 menunggu · 29 lewat tenggat" | **"4 keputusan menunggu tindakan"** (tanpa angka lewat) |
| Panel PO (monitor / head) | 11 / 3 | **4 / 1** (`DEMO-PO-JAKA-AYAM` untuk Jakarta) |
| `GET /ledger/verify` | valid, 6369 blok | **valid, 6369 blok** (tidak berubah) |
| Pengguna / lokasi / pemasok | 3 / 10 / 35 | **3 / 10 / 35** (0 residu `@test.local`) |
| `supplier_exclusions` | 1 (menunjuk keputusan tes) | **0** |

Verifikasi pendukung: `pytest tests/test_sap_orders_api.py tests/test_suppliers_data.py
tests/test_ledger.py tests/test_decision_read_endpoints.py tests/test_kpi_api.py`
→ **45 passed** (30 s). Layar diperiksa ulang di browser (login tombol demo):
tidak ada galat JS, hanya peringatan `defaultProps` bawaan recharts.

## 4. Batas & catatan pemulihan

1. **Rantai bukti aman**: `ledger_blocks` punya rantai hash sendiri
   (`prev_hash` + `sha256`), tidak membaca `decisions`. Karena itu penghapusan
   keputusan tidak mengubah `valid` maupun `blocks`.
2. **KPI tidak kehilangan produsen**: kasus demo membawa trace sintetis
   (DETECT/DECIDE/ACT/LEARN) dan keputusan `executed` yang menaut ke PO, jadi
   metrik yang butuh ACT/PO tetap punya sampel.
3. **`pytest` akan menambah keputusan lagi** (tes menulis ke DB yang sama). Itu
   normal; kalau DB ingin kembali serapi sekarang, jalankan blok SQL §2 sekali lagi.
4. **Sebelum presentasi**, klik "Segarkan ke hari ini" (`POST /demo/refresh`) agar
   TTL kasus demo baru — kasus yang sekarang dibuat 19:27 WIB akan lewat tenggat
   beberapa jam kemudian, dan itu akan tampak seperti "data hilang" padahal hanya waktu.
5. Kalau butuh keadaan **siap-tes** (tanggal kanonik 8 Okt), jalankan
   `load_seed(datetime(2026,10,8,12,0,tzinfo=timezone.utc))`; jangan menjalankannya
   untuk keadaan siap-demo karena itu memundurkan tanggal dataset.
