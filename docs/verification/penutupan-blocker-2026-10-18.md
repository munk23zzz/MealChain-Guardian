# Penutupan blocker audit 18 Oktober 2026

Laporan audit lengkap: `docs/verification/audit-menyeluruh-2026-10-18.md`. Dokumen ini mencatat status tiap blocker setelah perbaikan malam 18 Okt, dengan bukti yang bisa dijalankan ulang.

| # | Blocker | Status | Bukti |
|---|---------|--------|-------|
| A1 | Event 1/2/3 berhenti di `proposed`, tanpa tombol Ajukan | **Tutup** (`d0e476d`) | Popup `proposed` → aksi `["verify","propose"]`; klik Ajukan → DB `pending_approval`; `test_propose_dari_feed.py` 4/4 |
| A2 | Approve sebelum verify = jalan buntu permanen | **Tutup** (`81e5909`) | Approve tanpa `verified_by` → 409; `can_approve=false`; setelah verify → Setuju muncul; `test_approve_wajib_verifikasi.py` 4/4 |
| A3 | Status `approved` tak pernah ditulis | **Tutup** (`07a0418`) | Kuorum penuh → `approved` + ledger `status:"approved"`; `test_status_approved.py` 6/6 |
| A4 | Ledger 100% yatim tetapi `/ledger/verify` `valid:true` | **Tutup** (`3934074`) | Respons memuat `orphan_blocks`/`linked_ratio`/`coverage_warning`: 8.732 blok, 11 tertaut, 8.721 yatim; UI menampilkan peringatan |
| A5 | Approval lintas lokasi + hanya 1 Head/1 Gizi (Jakarta) | **Tutup** (`788506e`) | Akun Kepala+Gizi di Jakarta/Bandung/Surabaya; 12 approval di DB, **0** lintas lokasi; approval riwayat demo direparasi saat seed |

## Bukti A5 (diperiksa ulang 18 Okt)

```
SELECT u.role, l.name, count(*) FROM users u LEFT JOIN locations l ...
sppg_head        | Bandung  | 1
sppg_nutritionist| Bandung  | 1
sppg_head        | Jakarta  | 1
sppg_nutritionist| Jakarta  | 1
sppg_head        | Surabaya | 1
sppg_nutritionist| Surabaya | 1

SELECT count(*), count(*) FILTER (WHERE u.location_id IS DISTINCT FROM d.target_location_id)
FROM approvals a JOIN users u ON u.id=a.approved_by JOIN decisions d ON d.id=a.decision_id;
12 | 0
```

Penjaga regresi: `backend/tests/test_akun_multi_kota.py` — 6 tes, termasuk `test_semua_approval_sesuai_lokasi_target` (memeriksa SELURUH approval, bukan hanya riwayat demo) dan `test_kepala_bandung_hanya_melihat_keputusan_bandung`.

## Masih terbuka (bukan blocker demo)

- **Mayor**: `/demo/seed` selalu menanam kasus Jakarta walau dipanggil dari kota lain; `source_location_id = target_location_id` pada riwayat demo; `verified_by` ditulis walau verdict `unavailable` (pagar verifikasi = ada/tidaknya verdict, bukan mutunya).
- **Minor**: `ApiError.detail` belum menyampaikan pesan 409 apa adanya di semua layar; penomoran PO tidak seragam (`MC-*`, `DEMO-PO-*`, `4500000001`).
- **Alur belum ada**: withdraw/cancel keputusan, sweeper kedaluwarsa, eskalasi approver, halaman PO penuh.
