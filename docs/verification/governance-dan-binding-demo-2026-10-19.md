# Governance & persetujuan + bukti binding kasus demo — 19 Oktober 2026

> **Snapshot 19 Oktober 2026** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

Dua jalur dikerjakan berurutan atas permintaan pemilik: (A) kasus demo harus
punya bukti `allocation_binding` sendiri supaya alur dua peran tidak tertahan
"pemasok tidak dikenal", lalu gerbang backend penuh; (B) UI "Governance &
persetujuan" Langkah 1–5 diverifikasi terukur di tiga lebar layar.

## A. Kasus demo menulis bukti binding sendiri

### Gejala dan diagnosis

Setelah dataset diperluas (60 pemasok, 78 batch; Cianjur punya 4 pemasok
telur), 21 dari 21 keputusan `demo_case` tidak punya `allocation_binding`.
`resolve_binding` sengaja tidak menebak pemasok, jadi kartu unggulan demo
menampilkan `pemasok tidak dikenal: keputusan lama perlu binding batch
eksplisit` dan `Boleh dieksekusi: Belum`.

Perbaikan ada di penyemai, bukan di `resolve_binding`:
`backend/app/api/demo.py::_ikat_sumber()` menulis
`DecisionEvidence(evidence_type='human_inspection', payload={allocation_binding:
true, supplier_id, batch_ids, demo: true})` untuk setiap kasus yang akan
DIEKSEKUSI (status `pending_approval`), memakai aturan deterministik "batch di
lokasi asal + komoditas, `usable_until >= now`, kuantitas terbesar, seri → id
terkecil". Bila tidak ada batch layak, TIDAK ada binding — alasannya jujur.

Kasus `supplier-janggal` (`verifier_flagged`) SENGAJA tidak diikat: tuduhannya
tentang HARGA sebuah kutipan pemasok, dan pemasok itu bukan selalu pemilik batch
terbesar di lokasi asal. Mengikat batch terbesar berarti menampilkan pemasok
yang bukan subjek tuduhan — tebakan yang menyamar sebagai bukti.

Dikunci `backend/tests/test_demo_seed_binding.py`: tiap keputusan
`pending_approval` punya tepat satu binding yang batch-nya cocok
lokasi/komoditas/pemasok, dan `/decisions/{id}/approval-summary` melaporkan
pemasoknya.

### Akar 37 kegagalan beruntun yang bukan berasal dari perubahan ini

Pytest penuh sempat merah dengan satu kalimat yang sama di 37 tes:

```
ValueError: tidak ada kandidat eligible untuk Event 1 (telur -> Jakarta)
```

Diagnosis tiga langkah:

1. `SELECT origin, count(*) FROM batches GROUP BY 1` → **nol** baris `demo`.
2. `POST /balance/analyze {"commodity":"telur"}` → `candidates_total: 0`
   padahal `facts` menunjukkan surplus (Cianjur 1.472,89 kg vs permintaan 710 kg).
3. Setelah `seed_demo_activity` dijalankan → `candidates_total: 24,
   eligible: 24`, dan 66/66 tes pada 12 berkas terdampak hijau.

Sebabnya umur data, bukan kode: batch kanonik seed dijangkar `CANONICAL_REF`
8 Okt 12:00 UTC, sedangkan `PASS_THRESHOLD` kesegaran 0,85 dengan shelf telur
28 hari — sekitar empat hari setelah REF batch seed tidak lagi lolos, sehingga
hanya batch `origin='demo'` (harvest relatif `now`) yang bisa menjadi kandidat.

Karena itu perbaikannya permanen di `backend/tests/conftest.py`:

- fixture autouse `jaga_kiriman_demo` menyemai ulang kegiatan demo **hanya bila**
  `SELECT count(*) FROM batches WHERE origin='demo'` = 0, dan **hanya** untuk 13
  modul yang menuntut kandidat (`_MODUL_BUTUH_KANDIDAT`); tes lain tidak
  membayar apa pun (early-return).
- `backend/tests/test_deret_demo_aman.py` memulihkan kegiatan demo di akhir
  modul, karena `purge_demo_rows()` menghapus seluruh baris `origin='demo'`
  termasuk 40 batch ber-harvest hari ini.

Verifikasi sengaja dibuat kejam: `DELETE FROM batches WHERE origin='demo'`
(40 baris hilang) lalu satu modul dijalankan → hijau, dan hitungan kembali 40
dengan `max(harvested_at)` = hari ini.

Angka gerbang menyusut bertahap sebagai bukti diagnosis: **28 gagal → 9 gagal →
2 gagal**.

### Dua tes `test_suppliers_api.py` yang memaku jumlah lot

`test_shipping_reports_batch_that_failed_testing` (`count == 1`) dan
`test_expired_batch_is_not_counted` (`count == 0`) memaku keadaan dataset yang
tidak lagi benar begitu penyemai demo membuat lot baru untuk pemasok yang sama
("Telur Berkah Surabaya" → 2 lot, "PT Ayam Potong Cileunyi" → 1 lot hidup
berdampingan dengan 2 lot kedaluwarsa).

Keduanya diubah menjadi uji sifat dengan ground truth DB yang dihitung saat tes
berjalan (`_sql_shipping` + helper baru `_sql_lot_supplier`):

- lot gagal uji **tetap dilaporkan** (`safety_fail_count == sql["fails"]`, dan
  prasyarat `sql["fails"] >= 1`);
- lot lewat tenggat **tetap dikecualikan** (`total > layak`, lalu
  `(shipping is None) == (sql["count"] == 0)` dan `count == sql["count"]`).

Yang diuji tetap intinya; yang dilepas hanya "jumlah lot hari itu".

## B. UI Governance & persetujuan (Langkah 1–5)

Perilaku yang dikunci:

- `frontend/lib/governance.ts` menambah keadaan `lengkap` (semua peran syarat
  setuju tetapi `can_execute = false`). Chip memakai nada biru informasi dan
  penanda bentuk `◉`, bukan hijau — hijau hanya untuk `siap`/`selesai`.
- `frontend/components/DecisionActions.tsx` menurunkan `view` SEKALI dan
  memakainya untuk label pemicu maupun chip, sehingga label dan status tidak
  bisa menyimpang.
- `.approval-menu-foot` sticky: ringkasan persetujuan bisa panjang, tombol
  Tutup harus selalu terjangkau.

### Pengukuran nyata (Playwright, 375 / 768 / 1440 px)

Login memakai resep repo: klik tombol demo "SPPG Head" (mengisi email+sandi),
lalu "Masuk". Klik tombol demo saja menyisakan halaman login (token 0) — sudah
terbukti, bukan asumsi.

| Ukuran | 1440 | 768 | 375 |
| --- | --- | --- | --- |
| Luapan mendatar halaman | 0 px | 0 px | 0 px |
| Lebar kartu | 1.102 px | 686 px | 293 px |
| Chip `○ Menunggu persetujuan` | 161,9 px, kanan 458,9 | 161,9 px, kanan 202,9 | 161,9 px, kanan 202,9 |
| Progres `0 dari 2 peran syarat terpenuhi` | 420 px, fs 14 | 420 px, kanan 461 | 293 px, fs 15 (memenuhi kartu) |
| Tinggi trek progres | 6 px | 6 px | 6 px |
| Tombol pemicu | 34 px | 34 px | **44 px** |
| Panel popup | 640 px, radius 12 | 640 px, radius 12 | 375 px (penuh), radius atas saja |
| Kaki popup | sticky, 63 px | sticky, 63 px | sticky, 73 px |
| Tombol aksi dalam popup | 34 px | 34 px | **44 px** |
| Escape menutup & panel hilang | ya | ya | ya |

Pada 375 px isi popup dapat digulir; setelah digulir ke dasar, kaki menempel
`top 739 / bottom 812` dengan `panel_bottom 812` — jarak 0 px, jadi tidak ada
isi yang tertutup permanen dan tombol Tutup tetap terlihat.

## Gerbang

- Backend pytest penuh, HEAD `7ac4a7f`, 19 Okt 2026 11:32–11:43 WIB:
  **1.167 lulus, 6 skip, 0 gagal (10m54s, `PYTEST_EXIT=0`)** — 1.173 tes
  terkumpul, jadi tidak ada tes yang hilang dari hitungan.
- Run tepat sebelumnya (11:19) menyisakan **2 gagal / 1.165 lulus** di
  `tests/test_agenda_api.py`, dan keduanya hilang saat diuji ulang: berkas itu
  sendiri `9 passed`, dan berurutan dengan pendahulunya (`test_actions.py`,
  `test_actions_scope_operasional.py`, `test_action_boundary_e2e.py`)
  `36 passed`. Run itu bertepatan dengan kontainer aplikasi dihapus lalu dibuat
  ulang sesi lain di tengah run (satu kegagalan berbentuk galat SQLAlchemy =
  koneksi putus); klasifikasinya flake lingkungan, bukan regresi.
- `ruff check` pada berkas yang saya sentuh (`app/api/demo.py`,
  `tests/conftest.py`, `tests/test_deret_demo_aman.py`,
  `tests/test_demo_seed_binding.py`, `tests/test_suppliers_api.py`):
  **All checks passed**.
- `ruff check app tests` (seluruh repo) masih 10 temuan, semuanya di berkas
  pekerjaan perluasan seed yang bukan milik saya (`app/api/waste.py`,
  `app/main.py`, `tests/test_agent_golden_cases.py`, `tests/test_demo_harian.py`,
  `tests/test_review_only.py`, `tests/test_suppliers_data.py`) — dilaporkan,
  tidak dirapikan agar tidak mencampur commit orang lain.
- Frontend, diukur ulang sesudah semua perubahan (HEAD `9f1b50d`):
  `npx vitest run` → **119 berkas / 1.359 tes lulus, `VITEST_EXIT=0`**;
  `npx tsc --noEmit` → `TSC_EXIT=0` (nol baris keluaran);
  `npx next lint` → `LINT_EXIT=0`, "No ESLint warnings or errors".

## Catatan terbuka

1. **Gerbang sempat mati `EXIT=137`** saat dua suite berjalan serentak
   (kontainer `mg-gate*` sesi lain hidup; RAM host tersisa 1,87 GB dari 15,7 GB).
   Itu kehabisan memori, bukan regresi; run diulang setelah deret demo pulih.
2. **Kontainer aplikasi sempat dihapus** (status `created`) di tengah sesi dan
   harus dinyalakan ulang; data selamat karena volume `postgres_data` bernama.
3. Kasus `supplier-janggal` tetap menampilkan alasan "pemasok tidak dikenal".
   Itu keputusan sadar (lihat A), bukan cacat yang tertinggal.
