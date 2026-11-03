---
name: demo-data-builder
description: Use when building, refreshing, or extending the MealChain Guardian DEMO dataset — deterministic, relative to today, relational-safe, and covering every row of docs/db-coverage-matrix.md.
---

# demo-data-builder — membangun dataset demo yang menutup seluruh matriks UI

Sumber kebutuhan: `docs/db-coverage-matrix.md` (layar → endpoint → tabel.kolom →
bukti). Builder **tidak** mengarang struktur baru: ia memakai jalur seed resmi
repo supaya angka, id, dan invarian sama dengan yang dipakai tes.

## Cara menjalankan

```bash
# bangun/segarkan dataset DEMO di database demo
DB_MODE=demo bash scripts/db-mode.sh init-demo

# bangun ulang deret relatif HARI INI (tanggal bergeser, jumlah baris tetap)
DB_MODE=demo bash scripts/db-mode.sh init-demo --refresh

# periksa cakupan: jumlah baris + penanda demo per tabel
bash scripts/db-mode.sh status
```

Urutan yang dijalankan `init-demo` (modul `backend/app/seed/db_mode.py`):

| # | Langkah | Modul | Yang dijamin |
|---|---|---|---|
| 1 | Referensi | `app.seed.reference` | komoditas, 10 lokasi/SPPG, 3 peran akun — id deterministik |
| 2 | Kanonik | `app.seed.seed_data.load_seed` | 12 pemasok, batch, PO impor SAP, fakta P6 (reference time 8 Okt 2026) |
| 3 | Deret waktu | `app.seed.timeseries.generate_timeseries` | 1 Sep–5 Nov: supply, demand, harga acuan + kutipan, menu, delivery, limbah, `origin='demo'` |
| 4 | Aktivitas | `app.seed.demo_activity` | kiriman hari ini, keputusan selesai (KPI "hari ini"), harga harian |
| 5 | Pelengkap cakupan | `app.seed.demo_extra.build_demo_extra` | semua `decision_type` × `status`, approval, bukti konsisten/tidak, jejak pipeline, PO dari keputusan, penerimaan `menunggu/disetujui/ditolak`, batch karantina, eksklusi 4 status, limbah dengan/tanpa mitra, menu besok, harga anomali, sesi `ended/expired`, pemasok Unicode |
| 6 | Penanda | `db_mode._tandai_demo` | `origin='seed'` → `'demo'` untuk tabel bisnis, sehingga `reset-demo` tepat sasaran |

## Aturan yang WAJIB dipegang saat menambah data

1. **Deterministik.** Id = `stable_uuid("<domain>", "<kunci stabil>")`; jangan
   `uuid4()`. RNG (bila ada) di-seed tetap. Menjalankan dua kali harus
   menghasilkan jumlah baris yang sama (`init-demo` idempoten).
2. **Tanggal relatif.** Waktu lahir dari `datetime.now(timezone.utc)` dan
   `timedelta`, bukan tanggal mati — kecuali dataset kanonik yang memang
   dipatok 8 Okt 2026 agar angka tes stabil.
3. **Integritas relasional.** Insert mengikuti urutan: referensi → pemasok →
   batch → keputusan → approval/bukti/jejak → PO → penerimaan → limbah/menu.
   Ambil id nyata dari database (`select`), jangan mengarang FK.
4. **Bertanda demo.** Setiap baris bisnis `origin='demo'` (atau
   `demo_session_id` untuk tabel tanpa kolom `origin`). Tanpa ini,
   `reset-demo` tidak bisa membedakan data demo dari data kerja.
5. **Idempoten.** Pakai `session.merge`/`_ambil_atau_buat` (get by id → insert
   bila belum ada, segarkan kolom bila sudah).
6. **Jangan menyentuh tabel referensi** (`commodities`, `locations`, `users`)
   dari builder demo — itu wilayah mode DEFAULT.

## Cakupan yang harus selalu ada (checklist)

- [ ] 6 `decision_type`: regional_balance, price_anomaly, safety_disruption,
      supplier_exclusion, supplier_exclusion_restoration, supplier_procurement.
- [ ] 7 `decision.status`: proposed, verifier_flagged, pending_approval,
      approved, rejected, executed, review_only.
- [ ] 4 `batches.safety_status` (pending/pass/fail/needs_verification) dan
      4 `quarantine_status` (none/quarantined/released/failed).
- [ ] 3 `certification_status` (none/hygiene/haccp).
- [ ] 3 `batch_receipts.status` (menunggu/disetujui/ditolak) + minimal 3 antrean.
- [ ] 4 `supplier_exclusions.status` (proposed/active/rejected/revoked).
- [ ] 3 `sap_mock_purchase_orders.status` (draft/submitted/confirmed) **dan**
      minimal 1 PO dengan `decision_id` tidak null (bukti "approval → PO").
- [ ] Limbah dengan `partner_name` dan tanpa mitra.
- [ ] Jejak pipeline lengkap (DETECT + DECIDE + salah satu
      PREDICT/OPTIMIZE/SUPERVISE, `agent_name IS NULL`) minimal 1 keputusan.
- [ ] Angka ekstrem: kuantitas puluhan ribu kg, harga jutaan rupiah, `0`,
      `freshness_score` 0.10 dan 0.98.
- [ ] Teks panjang (>200 karakter) dan Unicode ("—", "“”, °C") minimal 1 baris.
- [ ] Tanggal lampau, hari ini, dan masa depan (`needed_by`/`plan_date` besok).
- [ ] Volume > 1 halaman untuk tabel yang punya pagination.

Bila salah satu hilang, tambahkan di `demo_extra.py` dengan pola
`_ambil_atau_buat(session, Model, "<kunci stabil>", dict(...))`, bukan dengan
menambal database manual.

## Laporan cakupan otomatis

- `bash scripts/db-mode.sh status` → jumlah baris + `bertanda_demo` per tabel.
- `python scripts/audit/db_coverage.py` (di kontainer backend) → menulis ulang
  `docs/db-coverage-matrix.md` dari data live, termasuk daftar baris **GAP**.
- Setelah `init-demo`, jalankan keduanya; matriks harus menunjukkan 0 GAP pada
  baris yang datanya disediakan builder.
