# Akun approver per kota — 18 Oktober 2026

> **Snapshot 18 Oktober 2026** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

Keputusan produk 3A (pilihan user): demo tetap multi-kota, dengan approver sendiri di setiap kota.

## Masalah yang ditutup

Hanya ada **satu** Kepala SPPG dan **satu** Ahli Gizi, keduanya Jakarta. Karena `/actions/approve` dan `/actions/execute` mengunci lokasi target (Ruling 2026-10-14 §3), setiap keputusan yang menyasar Bandung/Surabaya **mustahil** di-approve siapa pun. Riwayat demo `executed` untuk dua kota itu pun disemai dengan approval akun Jakarta — sah sebagai baris, tidak sah sebagai alur. Audit 18 Okt mencatatnya sebagai BLOCKER A5 (4 dari 6 approval lintas lokasi).

## Perubahan

1. **Seed akun** (`backend/app/seed/seed_data.py`): `DEMO_USERS` bertambah empat akun — Kepala & Ahli Gizi Bandung, Kepala & Ahli Gizi Surabaya. Password mengikuti pasangan Jakarta (lihat `DEMO_PASSWORD_<ROLE>`; nilai bawaan ada di `backend/app/seed/demo_credentials.py` dan hanya aktif saat `DEMO_MODE=true`). `ensure_demo_users()` tetap idempoten (UUID stabil dari email).
2. **Seed riwayat** (`backend/app/seed/demo_activity.py`): approver dipilih per `(location_id, role)` dari kota target, bukan lagi `order_by(email).first()`. Kota tanpa pasangan approver **dilewati** (tidak menyemai riwayat yang mustahil) dan namanya dilaporkan di `dilewati_kota`. Baris approval lama **direparasi** saat seed dijalankan ulang (`approved_by` ditimpa ke approver kota yang benar).
3. **Login** (`frontend/app/page.tsx`): tambah baris "Kota lain:" dengan empat tombol isi-cepat (Kepala/Gizi Bandung & Surabaya). Email tetap tidak dipajang; `demo.local` tidak muncul di HTML.
4. **Tes**: `backend/tests/test_akun_multi_kota.py` (5 tes baru) memaku akun per kota, kecocokan password↔hash, approval riwayat sesuai target, dan feed Kepala Bandung hanya berisi keputusan Bandung. `test_demo_users.py` disesuaikan dari "tepat tiga akun" menjadi "tiga role × tiga kota + monitor".

## Bukti hidup (probe di dalam kontainer)

```
1. feed Kepala Bandung    : 200 jumlah 1 status ['executed']
2. buat keputusan Bandung : 201 proposed
3. ajukan                 : 201 pending_approval
4. verifikasi             : 200 UNAVAILABLE
5. approve Kepala Jakarta : 403 keputusan di cakupan lokasi di luar SPPG Anda
6. approve Gizi Bandung   : 200 pending_approval satisfied=False
7. approve Kepala Bandung : 200 approved        satisfied=True
8. eksekusi Bandung       : 200 executed MC-51092B0C2B26
```

Bukti DB setelah reparasi: `SELECT ... FROM approvals JOIN decisions ... WHERE status='executed' AND origin='demo'` → tidak ada satu pun approval yang lokasinya berbeda dari target.

DOM: halaman login menampilkan tujuh tombol demo (3 utama + "Kota lain:" 4). Setelah login sebagai Kepala Bandung, tab Recommendations berisi **2 kartu** (riwayat demo Bandung + keputusan probe), tanpa kartu Jakarta.

## Gerbang

- Backend: `test_akun_multi_kota` **5/5**, `test_demo_users` **2/2**, `test_demo_seed`, `test_admin_api`, `test_scope_matrix`, `test_peran_*`, `test_supplier_exclusion_api` — hijau (lihat lampiran run).
- Frontend: vitest **1277 tes / 108 berkas**, `tsc` 0, `next lint` 0.
- `test_demo_event1_api` sempat gagal sekali (24 != 25 keputusan) karena sesi lain mem-purge data demo di tengah run; hijau saat dijalankan sendiri.

## Catatan terbuka

- Keputusan probe `51092b0c` (executed, PO `MC-51092B0C2B26`) sengaja dibiarkan agar ledger tidak makin yatim.
- Masih di luar lingkup: `/demo/seed` menanam kasus baru yang menyasar **Jakarta** walau pemanggilnya di Bandung (audit M4), dan `source_location_id = target_location_id` pada riwayat demo (audit M12).
- `/actions/verify` tetap menulis `verified_by` meski verdict `UNAVAILABLE` (audit M1).
