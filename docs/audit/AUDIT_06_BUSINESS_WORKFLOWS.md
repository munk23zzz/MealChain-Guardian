# AUDIT_06 — Business Workflows (Demo Control, Rekomendasi & KPI, Approval, Delivery, Notifikasi)

Semua angka di bagian ini diukur pada stack berjalan (`mealchain-backend` :8000, `mealchain-frontend` :3010, `mealchain-postgres` :15432) pada 26 Oktober 2026, 07:00–08:40 WIB.

## 6.1 Demo Control — sesi dua jam

| Kriteria | Hasil | Bukti |
|---|---|---|
| Identitas sesi unik | `demo_sessions.id` UUID + `started_at`, `expires_at`, `created_by` | skema + `GET /demo/session` |
| Waktu mulai & kedaluwarsa benar | `expires_at = started_at + 120 menit` | `POST /demo/session/start` → `remaining_seconds=7199`, panjang 120,0 menit |
| Waktu dihitung server | perhitungan di `app/services/demo_session.py` (`_batas_akhir`, `sekarang()`), frontend hanya menampilkan | tidak ada perhitungan kedaluwarsa di klien |
| Plafon absolut 2 jam | `extend {menit:240}` → 200 tetapi `expires_at` **tidak berubah** | probe |
| Satu sesi aktif | partial unique index `uq_demo_sessions_satu_aktif`; DB `sesi_aktif_ganda = 0`; tes atomik 14/14 | migrasi 032 + tes |
| Enforcement mutasi | tanpa sesi: `POST /actions/approve` → 409, `POST /demo/refresh` → 409, `POST /demo/session/extend` → 409; `GET` tetap 200 | probe |
| Kedaluwarsa tidak bisa "dipalsukan" refresh halaman | status dibaca dari tabel, bukan timer | probe + kode |
| Reset idempoten | `POST /demo/refresh` → `{"rows":{"dilewati":"snapshot kanonik sudah ada"}}`; 3× rebuild nyata tidak menambah baris | tes + rebuild |
| Reset tidak menghapus non-demo | sweep `origin='demo'`; invarian "baris kanonik berstempel sesi = 0" | gate invariants |
| Reset saat proses berjalan | tidak ada worker terpisah; satu transaksi per request. Reset bersamaan tidak diuji | **NOT TESTED** |
| Audit pelaku reset | `demo_sessions.created_by` + `ledger_blocks` | skema |
| Kegagalan DB saat reset | tidak disimulasikan | **NOT TESTED** |

## 6.2 Rekomendasi Jakarta hari ini

| Kriteria | Hasil |
|---|---|
| Sumber dari DB/pipeline | `decisions` (bukan data statis); 5 `demo_case` unik |
| Tidak membuat 5 baru tiap refresh | `STATUS_KARTU_HARI_INI` + `build_into` idempoten; rebuild 3× tetap 36 keputusan |
| Tidak duplikat akibat retry/restart | tidak ada duplikat `decision_id`; 11 kartu terbuka (9 `pending_approval` + 2 `verifier_flagged`) |
| Tanggal/status/referensi valid | `created_at` hari ini untuk kartu terbuka, `expires_at > now()` |
| Target 5 rekomendasi PRD | **PARTIAL**: 11 kartu bisa ditindak berasal dari 5 skenario; PRD menyebut "5 rekomendasi", implementasi menyajikan semua keputusan terbuka (9 pending + 2 flagged) |

## 6.3 KPI — periode & pergerakan angka

| Uji | Hasil |
|---|---|
| `periode=today` = hari kalender Asia/Jakarta | start `2026-10-25T17:00Z` = 26 Okt 00:00 WIB |
| `periode=7d` | 7 hari kalender, 7 sampel Meal Continuity |
| `periode=1bulan` | bulan berjalan (bukan 30 hari bergulir), 26 sampel |
| `periode=24h` (tidak sah) | 422 |
| `periode` + `start`/`end` | 422 |
| Tanpa argumen | 422 |
| KPI bergerak karena aksi | approve×2 → execute satu kartu: Safe Delivered Cost 15.749.032,38 (n=1) → 18.914.947,39 (n=2); Price Deviation 3,28% (18) → 3,49% (19); Decision Time `—` (7 eligible) → 20,98 menit (1); Evidence Completeness `—` → 0,00% (1) |
| KPI tidak berubah karena refresh | `GET /kpi` idempoten (tes `test_kpi_read_idempotent`) |
| KPI tidak menghitung ganda | tes dedup + invarian "0 PO ganda per keputusan" |
| Kembali ke baseline saat reset | rebuild mengembalikan 36 keputusan / 660 menu; angka KPI aksi kembali `no_data` |
| Zona waktu | seluruh label memakai WIB; tidak ada pencampuran UTC/lokal pada rentang (tes batas tanggal) |

Rumus per KPI, tabel sumber, filter, dan alasan `no_data` didokumentasikan di `docs/kamus-kpi-dan-state-machine.md` §2 (termasuk tiga selisih dengan `docs/Skill.md`).

## 6.4 Approval dua pihak

| Kriteria | Hasil | Bukti |
|---|---|---|
| Identitas kedua pihak tercatat | `approvals.decision_id`, `approved_by`, `approved_at` | DB: 12 approval, 0 duplikat akun |
| Pihak berwenang | hanya `sppg_head` / `sppg_nutritionist` (matrix per tipe keputusan) | 409 untuk peran lain |
| Satu akun tidak boleh dua approval | 409 "approval sudah tercatat untuk akun ini" | probe |
| Duplikat tidak dihitung dua kali | unique constraint per (decision, approver) | skema |
| Status menunggu ≠ approved | `pending_approval` ≠ `approved`; transisi hanya setelah 2 approval | probe: setelah 1 approval status tetap `pending_approval` |
| Satu approval tidak memicu final | `execute` sebelum 2 approval → 409 | tes `test_can_execute*` |
| Approval kedua memicu transisi | status → `approved`; `execute` → `executed` + PO | probe (PO `MC-215FFA979FCB`) |
| Race dua approval bersamaan | dijaga unique constraint; tidak diuji dengan thread paralel | **NOT TESTED** (konkurensi nyata) |
| Transisi tidak bisa dilewati via API | endpoint `execute` memeriksa status + jumlah approval + verifikasi | tes + probe 409 |
| Audit trail | `approvals`, `agent_traces`, `decision_evidence`, `ledger_blocks` | DB |
| Notifikasi | tidak ada notifikasi push; daftar turunan `/decisions` | §6.6 |
| Retry tidak menciptakan approval ganda | 409 pada percobaan kedua akun sama | probe |

## 6.5 Pengiriman & animasi Overview

| Kriteria | Hasil |
|---|---|
| Animasi tidak muncul setelah approval pertama | `execute` adalah satu-satunya penulis `batches.dispatched_at`; approval tidak menyentuh batch |
| Event pemicu punya bukti backend | `dispatched_at` terisi untuk 5 batch dalam 30 menit setelah eksekusi |
| Animasi mengikuti status benar | `GET /supplier-routes`: 12 rute — `di_jalan` 6, `sudah_tiba` 5, `tidak_diketahui` 1, `belum_berangkat` 0 |
| Gerak nyata (bukan statis) | `journey.progress` naik di **6/6** rute dalam 8 detik (0,521→0,527; 0,682→0,694; 0,532→0,539; 0,277→0,279; 0,410→0,413; 0,393→0,395) |
| `approved` tidak ditampilkan sebagai delivered | label journey dari server, bukan asumsi UI |
| Refresh tidak memicu pengiriman ulang | `dispatched_at` hanya ditulis sekali per batch (tidak ada penulisan ulang pada GET) |
| Event duplikat tidak membuat kiriman ganda | 120 batch, 0 batch ganda per (pemasok, lokasi, komoditas, panen) — invarian tes |
| Animasi gagal → data tetap konsisten | animasi murni visual dari `progress`; kegagalan render tidak mengubah DB (statis: tidak ada penulisan dari peta) |
| Reduced motion | tidak diverifikasi (**NOT TESTED**) |
| Klaim real-time | UI mem-poll; bukan WebSocket/SSE. Tidak ada klaim real-time di laporan ini |

## 6.6 Notifikasi

| Kriteria | Hasil |
|---|---|
| Event sumber | keputusan yang butuh tindakan (`pending_approval`, `approved`, `verifier_flagged`) dan belum kedaluwarsa |
| Penerima | daftar difilter per peran + scope lokasi di `/decisions` |
| Tidak ada tabel notifikasi | **desain saat ini**: turunan, tanpa read-state |
| Badge menghitung dengan benar | 12 → 9 setelah tiga kartu dieksekusi (kartu hilang dari daftar) |
| Notifikasi ganda akibat retry | tidak mungkin: tidak ada penulisan, hanya query |
| Menandai dibaca | **tidak ada fitur** (bukan bug; tercatat sebagai keputusan produk di kamus §7.3) |
| Notifikasi sukses menyesatkan | tidak ada; isi = daftar tugas, bukan klaim sukses |
| Reset demo membersihkan notifikasi demo | otomatis, karena sumbernya keputusan demo yang di-reset |

## 6.7 Temuan alur bisnis

| ID | Temuan | P | Status |
|---|---|---|---|
| WF-01 | Tab **Pemasok** memanggil `/decisions/{id}/approval-summary` untuk id yang tidak ada → 404 berulang (terlihat pada 2 dari 3 peran saat gate dijalankan bersamaan dengan pytest) | P2 | Sedang ditelusuri; lihat AUDIT_09 & AUDIT_10 (uji ulang tanpa beban paralel) |
| WF-02 | "5 rekomendasi" vs 11 kartu siap tindak | P3 | Terdokumentasi (definisi produk) |
| WF-03 | Notifikasi tanpa read-state | P3 | Keputusan produk |
| WF-04 | Regional Imbalance tidak bisa bergerak oleh kartu demo (`demo_case` dikecualikan) | P2 | Terbuka (keputusan owner) |
