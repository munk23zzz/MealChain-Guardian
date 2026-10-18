# Seed kasus demo per kota — 18 Oktober 2026

Audit 18 Okt mayor **M4** (seed selalu Jakarta) dan **M12** (`source_location_id = target_location_id` pada riwayat demo).

## Masalah

`POST /demo/seed` dan `/demo/refresh` memakai parameter `_user` yang tidak pernah dibaca, lalu menanam empat kasus dengan target **Jakarta** hardcoded. Kepala Bandung yang menekan "Muat kasus demo" menerima empat kartu yang tidak bisa ia sentuh: `approve`/`execute` mengunci lokasi target (Ruling 2026-10-14 §3), jadi setiap aksi berakhir 403. Idempotensinya juga global — `force=true` dari Bandung akan menghapus kasus Jakarta.

## Perubahan

1. **Target = kota pemanggil** (`_target_lokasi`, `app/api/demo.py`): `POST /demo/seed` dan `/demo/refresh` memakai `user.location_id`. Akun tanpa lokasi (mis. BGN Monitor — memang tidak diizinkan endpoint ini) mendapat 422 yang jelas.
2. **Idempotensi per kota**: pencarian "sudah ada" dan `force`-delete difilter `target_location_id`; kasus kota lain tidak tersentuh.
3. **Sumber ≠ target** (`_nama_sumber`): kandidat sumber dicek berurutan dan lokasi yang sama dengan target dilewati — memindahkan barang ke kota yang sama bukan keputusan rantai pasok.
4. **Teks ikut kota**: rejection reason ("Kuota SPPG <kota> penuh…"), route trace (`<sumber>→<kota>`), dan `location` di trace DETECT memakai nama kota target; respons seed menyebut `target`.
5. **UI**: panel Demo Control menjelaskan bahwa kasus dimuat untuk kota SPPG pemanggil dan kota lain punya set sendiri.

## Bukti hidup

```
-- sebelum (per kota) --            Bandung 7 · Jakarta 7 · Surabaya 7
POST /demo/seed {force:true} as Kepala Bandung
  {"seeded": true, "cases": 4, "decisions": 7, "target": "Bandung",
   "message": "4 kasus demo Bandung siap — v3 kuota & v2 logistik siap approve."}
-- sesudah --                        Bandung 7 · Jakarta 7 · Surabaya 7
isi Bandung: kuota v1 rejected(Cianjur) · v2 rejected(Cianjur) · v3 pending_approval(Cianjur)
             shortage pending_approval(Bogor) · supplier-janggal verifier_flagged(Cianjur)
             logistik v1 rejected(Bogor) · v2 pending_approval(Cianjur)   → semua target Bandung
```

DOM: panel Demo Control menampilkan "…untuk **kota SPPG Anda**… Kepala kota lain memuat kasusnya sendiri — tidak saling menghapus." Setelah klik pada akun Kepala Bandung, tab Recommendations menampilkan 4 kasus actionable milik Bandung.

## Gerbang

- Backend: `test_demo_seed_per_kota` (4 tes baru: target per kota, idempotensi per kota, force tidak menghapus kota lain, Ahli Gizi boleh menyemai) + `test_demo_seed` (query lama discope ke Jakarta) + demo/event/actions/akun-multi-kota hijau; ruff bersih.
- Frontend: gate penuh dijalankan (vitest + tsc + lint).

## Catatan

- Kasus Jakarta lama tetap ada sampai pemiliknya menekan `force` — tidak ada migrasi data demo.
- `refresh` memakai helper yang sama, jadi perilakunya identik; panel "Segarkan ke hari ini" kini juga menyegarkan kasus kota pemanggil saja.
