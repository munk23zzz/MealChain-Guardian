# Tombol "Ajukan untuk persetujuan" — 18 Oktober 2026

Fase 0 butir 1 dari audit 18 Okt (BLOCKER A1): keputusan yang lahir `proposed` tidak punya jalan ke `pending_approval`.

## Masalah

Event 1/2/3 (`event1_orchestrator.py:208`, `event2_service.py:221`, `event3_service.py:231`) dan `POST /decisions` menulis status `proposed`. Satu-satunya jalur ke `pending_approval` adalah `POST /actions/propose`, tetapi:

- `DecisionActions.visibleActions()` tidak punya cabang `proposed` sama sekali, sehingga popup governance kosong;
- `nextStep()` jatuh ke kalimat "Tidak ada tindakan mendesak";
- endpoint mewajibkan `material_number`, nilai yang tidak diketahui UI.

Akibatnya keputusan berhenti permanen, dan `proposed` menumpuk (8 baris di DB saat audit).

## Perubahan

1. **Backend** (`app/api/actions.py`): `ProposeRequest.material_number` opsional. Bila kosong, server menurunkannya dari komoditas lewat `_material_number_for()` → `MAT-<KOMODITAS>`. Nilai eksplisit (Demo Control) tetap dihormati, jadi perilaku pemanggil lama tidak berubah.
2. **API klien** (`lib/api.ts`): `proposeAction(decisionId, materialNumber | null, token)` — field `material_number` hanya dikirim bila ada.
3. **`visibleActions`**: field baru `propose` = status `proposed` **dan** role `sppg_head`. Ahli Gizi tetap tidak boleh mengajukan (403 dari server).
4. **`ApprovalMenu`**: blok "Ajukan untuk persetujuan" (`data-action="propose"`) saat `actions.propose` dan keputusan belum lewat tenggat; versi catatan saat kedaluwarsa. Keputusan administratif (`supplier_exclusion*`) **tidak** ditawari karena `/actions/propose` menolaknya (409) — jalurnya panel supplier.
5. **`DecisionActions`**: handler `ajukan()` memanggil `proposeAction(id, null, token)`; pesan sukses "Keputusan diajukan — menunggu persetujuan Ahli Gizi dan Kepala SPPG."
6. **`nextStep`**: status `proposed` menyebut "belum diajukan — ajukan untuk persetujuan…" (tone `warn`), bukan lagi "tidak ada tindakan mendesak".

## Bukti hidup

DB sebelum: `989e6bda…` (regional_balance, Jakarta) `status=proposed`.

DOM popup `Kelola persetujuan` sebelum: aksi `["verify","propose"]`, ringkasan "status proposed". Klik **Ajukan** → pesan "Keputusan diajukan — menunggu persetujuan Ahli Gizi dan Kepala SPPG.", popup tertutup.

DB sesudah: `pending_approval`. Popup dibuka lagi: aksi `["reject","verify"]` + Setuju di ringkasan, baris "status pending_approval".

Probe backend (`tests/test_propose_dari_feed.py`, 4 tes): ajukan tanpa `material_number` → 201 + `MAT-TELUR`; nilai eksplisit dihormati; Ahli Gizi 403; ajukan dua kali 409.

## Gerbang

- Backend: group 7 berkas (`propose_dari_feed`, `actions`, `status_approved`, `approval_summary`, `peran_lanjutan_head_only`, `scope_matrix`, `decision_schema`) **91 passed**; ruff `All checks passed!`.
- Frontend: vitest **1281 tes / 108 berkas**, tsc 0, next lint 0.

## Catatan terbuka

- BLOCKER A2 belum: approve sebelum `verified_by` terisi masih menutup jalan (approve 200, execute 409 "belum diverifikasi" permanen). Ini langkah berikutnya yang disarankan.
- `material_number` turunan hanya dipakai untuk jejak; PO tetap memakai `safe_delivered_cost / quantity` saat eksekusi.
