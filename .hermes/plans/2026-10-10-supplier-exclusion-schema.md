# Proposal schema supplier exclusion

## Keputusan yang sudah diberikan Roy

- Exclusion bersifat lokal per SPPG. Scope ditentukan oleh lokasi SPPG penerima dan approval server.
- Exclusion aktif sampai dicabut melalui keputusan pemulihan berbukti dan approval manusia baru.
- Pemulihan supplier tidak pernah mengubah batch safety `FAIL` menjadi eligible.
- Role tetap `sppg_head`, `sppg_nutritionist`, dan `bgn_monitor`.

## Batas domain

Supplier exclusion adalah status administratif terpisah dari evaluasi safety batch. `FAIL`, `PASS`, dan `NEEDS_VERIFICATION` tetap berasal dari evaluator safety existing. Candidate eligibility menggabungkan safety, exclusion scope, freshness, capacity, delivery window, dan constraint lain yang sudah ada.

Usulan exclusion tidak otomatis memblokir supplier. Insiden Event 3 menjadi evidence reference. Exclusion aktif hanya setelah decision administratif memperoleh approval sesuai policy existing.

## Kontrak persistence additive

Tambahkan tabel `supplier_exclusions` setelah perubahan schema disetujui.

- `id` UUID primary key.
- `supplier_id` UUID not null FK `suppliers.id`.
- `scope_location_id` UUID not null FK `locations.id`.
- `status` text not null dengan nilai `proposed`, `active`, `rejected`, `revoked`.
- `reason` text not null.
- `evidence_refs` JSONB not null. Minimal satu referensi persisten ke incident, batch, atau decision.
- `source_decision_id` UUID not null FK `decisions.id`.
- `restoration_decision_id` UUID nullable FK `decisions.id`.
- `proposed_by` UUID not null FK `users.id`.
- `approved_at` timestamptz nullable.
- `activated_at` timestamptz nullable.
- `revoked_at` timestamptz nullable.
- `revocation_reason` text nullable.
- `created_at` timestamptz not null default now.
- `updated_at` timestamptz not null default now.

Tidak menambah kolom `is_excluded` pada `suppliers`. Status dan history perlu dipertahankan per scope serta dapat diaudit.

Constraint yang perlu direview sebelum migration:

- status hanya menerima empat nilai di atas.
- reason tidak kosong setelah trim pada boundary service.
- supplier dan scope location harus ada.
- source decision harus bertipe administratif supplier exclusion dan tidak boleh memakai quantity atau cost palsu.
- hanya satu exclusion `active` untuk pasangan `supplier_id, scope_location_id`.
- restoration hanya boleh menunjuk exclusion aktif dan evidence baru.

Jika decision type existing hanya menerima transfer, price anomaly, dan safety disruption, tambahkan decision type administratif secara additive atau gunakan tabel approval administratif terpisah. Jangan mengubah check constraint tanpa review `docs/Schema.md` dan `docs/Architecture.md`.

## Relasi supplier yang wajib eksplisit

Candidate builder harus memakai `supplier_id` dari batch atau supply fact yang memang menyimpan relasi tersebut. Location tidak boleh dipakai sebagai substitusi ketika beberapa supplier berada pada lokasi yang sama. Jika relasi tidak diketahui, hasil harus `supplier_unknown` dan proposal ditolak dengan penjelasan.

## Transaksi dan race protection

Service exclusion dan jalur execute harus memakai transaction yang sama untuk revalidasi akhir. Sebelum eksekusi PO:

1. lock decision row;
2. lock supplier exclusion rows untuk supplier dan scope;
3. evaluasi safety batch terbaru;
4. tolak jika ada exclusion aktif atau safety `FAIL`;
5. tulis PO dan ledger sekali setelah semua guard lolos.

Proposal, approval, activation, dan revocation harus idempotent terhadap request retry. Unique active constraint dan decision/ledger reference mencegah efek ganda. Revocation tidak menghapus history.

## Approval policy

- `sppg_head` dan `sppg_nutritionist` hanya boleh menyetujui scope SPPG yang berwenang.
- `bgn_monitor` hanya membaca evidence dan history.
- Usulan pending atau rejected tidak mengubah eligibility.
- Revocation membutuhkan evidence pemulihan dan approval baru. Tidak ada auto-unblock dari batch PASS baru.
- Approval summary harus membaca decision administratif tanpa menganggap `status=approved` dari Nabil sebagai otorisasi.

## Migration dan implementasi setelah review

1. Review proposal ini bersama `docs/Schema.md`, `docs/Architecture.md`, model `Decision`, `Approval`, `Batch`, dan candidate builder.
2. Setelah disetujui, buat migration di `backend/alembic/versions/` dengan head tunggal.
3. Tambahkan model, service domain, eligibility guard, API, dan ledger integration secara terpisah.
4. Tambahkan RED/GREEN tests untuk safety matrix, excluded reroute, unknown supplier, rejected proposal, old decision, retry, dan concurrent execute/exclusion.
5. Jalankan full backend regression dan tiga demo scenario.

Belum ada migration atau perubahan aplikasi dari proposal ini.
