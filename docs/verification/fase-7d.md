# Verifikasi Fase 7d — jarak pemasok masuk biaya SDC

**Tanggal:** 15 Oktober 2026 · **Pelaksana:** Hermes · **Ruling:** `docs/ruling-2026-10-15-jarak-pemasok-biaya.md`
**Repo:** `E:\hackathon\HackathonAWS\mealchain-guardian` (backend :8000, frontend :3010, postgres :15432)

Fase ini menutup §7.4b plan `2026-10-14_scope-pemasok-peta-rentang.md`: kaki angkut
**pemasok → SPPG sumber** ikut dihitung dalam Safe Delivered Cost, bukan hanya matriks
SPPG↔SPPG.

---

## 1. Yang dibuat / diubah

| Berkas | Perubahan |
|---|---|
| `backend/app/core/supplier_leg.py` | **BARU.** Murni: `supplier_leg_km` (haversine bersama `app/core/geo.py`, 3 desimal, `None` bila koordinat tidak lengkap) + `supplier_leg_map` (peta `(supplier_id, nama lokasi) → km`, hanya pasangan lengkap) + 3 konstanta label kejujuran |
| `backend/app/services/recommendation_service.py` | `fetch_operational_facts` mengembalikan elemen ke-7 (peta jarak pemasok); `build_recommendations` menerima 6-tuple **atau** 7-tuple (`facts[:6]`); biaya angkut = kaki pertama + linehaul; `cost_breakdown` bertambah 4 kunci + alias `logistics`; payload kandidat bertambah blok `supplier_leg`; helper murni `_resolve_supplier_leg` |
| `backend/tests/test_supplier_leg_cost.py` | **BARU.** 15 tes (murni + kontrak payload) |
| `backend/scripts/verifikasi_fase7d.py` | **BARU.** Tabel dampak angka sebelum/sesudah dari DB |
| `backend/scripts/verifikasi_fase7d_api.py` | **BARU.** Bukti jalur API nyata + persistensi DB |
| `frontend/lib/evidence.ts` | `costFacts` memecah baris angkut bila pecahannya ada; helper murni `supplierLegHint` |
| `frontend/tests/evidence-summary.test.ts` | +3 tes (pecahan tampil, label jujur saat koordinat kosong, payload lama tanpa baris tambahan) |
| `docs/Schema.md`, `docs/design.md`, `TODO.md`, plan §7.4b/7.5, `memory/global/*` | Sinkronisasi dokumen |

Tidak disentuh: `app/core/safe_delivered_cost.py` (komponen tetap 6), `app/core/logistics.py`
(linehaul), `app/core/scoring.py` (kontrak skor terkunci Task 5), data seed & 14 pemasok kanonik.

## 2. TDD (RED → GREEN)

```
RED   : docker compose exec -T backend python -m pytest tests/test_supplier_leg_cost.py -q
        → ModuleNotFoundError: No module named 'app.core.supplier_leg'  (collection error)
GREEN : docker compose exec -T backend python -m pytest tests/test_supplier_leg_cost.py -q
        → 15 passed
```

Tes yang menjaga batas keras: kontrak 6-tuple Task 9 tetap hijau, `logistics_distance_km` tetap
linehaul (120 km) + `feasible` tidak berubah, breakdown tetap menjumlah persis ke
`safe_delivered_cost`, determinisme output.

## 3. Gerbang

| Gerbang | Hasil |
|---|---|
| `pytest` penuh (kontainer backend) | **782 passed, 3 skipped, exit 0** (sebelum fase ini 767; +15 tes baru) |
| `ruff check .` | **All checks passed** |
| `vitest run` (frontend) | **545 passed / 60 berkas** (sebelumnya 542; +3) |
| `tsc --noEmit` | **0 error** |
| `npm run lint` | **0 error** |
| `next build` | **TIDAK dijalankan** — aturan repo: `next build` di kontainer frontend saat `next dev` hidup membuat chunk 404 (catatan F6 (d)). Build perlu menghentikan dev dulu |
| Jangkar kanonik | `tests/test_demo_timeseries_api.py` (telur **4.900 kg**, 3 surplus : 7 shortage, Cianjur 1.400 kg) **lulus** |

## 4. Dampak angka (syarat plan §7.4b (a)) — skrip `scripts/verifikasi_fase7d.py`

Pipeline dijalankan DUA KALI pada facts yang sama dari DB; bedanya hanya elemen ke-7
(ada = sesudah, kosong = sebelum/6-tuple).

| kasus skrip | kandidat | SDC sebelum | SDC sesudah | delta | kaki | label |
|---|---|---|---|---|---|---|
| rejection-loop-kuota | Cianjur→Jakarta telur | 14.169.953,40 | **14.170.235,40** | **+282,00** | 1,880 km | `supplier_coordinates` |
| shortage-darurat | Bogor→Jakarta telur | 14.975.145,33 | **14.981.798,40** | **+6.653,07** | 45,075 km | `supplier_coordinates` |
| supplier-janggal | Cianjur→Jakarta telur | 14.169.953,40 | **14.170.235,40** | **+282,00** | 1,880 km | `supplier_coordinates` |
| gangguan-logistik v1 | Bogor→Jakarta telur | 14.975.145,33 | **14.981.798,40** | **+6.653,07** | 45,075 km | `supplier_coordinates` |
| gangguan-logistik v2 | Cianjur→Jakarta telur | 14.169.953,40 | **14.170.235,40** | **+282,00** | 1,880 km | `supplier_coordinates` |

- **Peringkat: 0 kandidat berpindah** (14 kandidat, rank identik sebelum/sesudah).
- Kaki pertama terpanjang yang muncul: **Bogor → Jakarta 45,075 km** (batch Bogor dipanen dari
  pemasok Supplier A Cianjur). Lima teratas sesudah fase ini semuanya bersumber Bogor.
- **14 dari 14 kandidat punya kaki pertama terhitung** — 0 label "tidak diketahui", karena seluruh
  35 pemasok dan 10 lokasi punya koordinat. Jalur label jujur diuji terpisah dengan fixture.
- Catatan kejujuran: **angka absolut bergeser** beberapa ratus rupiah antar run (14.169.126,60 →
  14.169.953,40 dalam satu sesi) karena data supply/demand/harga DB demo ikut berubah — residu uji
  yang sudah tercatat di `docs/verification/fase-6.md`. **Delta invarian** (300 × km × ton).

## 5. Bukti jalur nyata (skrip `scripts/verifikasi_fase7d_api.py`)

Urutan yang dipakai UI, dijalankan terhadap backend hidup (kata sandi diambil dari
`app.seed.seed_data.DEMO_USERS`, tidak pernah dicetak):

```
akun demo          : sppg_head (login 200)
kandidat teratas   : Bogor→Jakarta 492.00 kg (rank 1)
supplier_leg       : km=45.075 cost=6653.07 reference=supplier_coordinates
pecahan angkut     : kaki=6653.07 linehaul=7380.00 total(transport)=14033.07 alias(logistics)=14033.07
jumlah komponen    : 14981582.46 vs safe_delivered_cost 14981582.46 → SAMA
POST /decisions    : 201
GET /decisions/{id}: 200 — cost_breakdown tersimpan: kaki=6653.07 linehaul=7380.00 km=45.075
                     ref=supplier_coordinates
KESIMPULAN         : jalur API & DB menyimpan jarak pemasok
decision_id        : 7da222a6-8b9e-47e1-b82a-9111741a4fd5
```

Artinya: pecahan biaya angkut tidak hilang setelah keputusan dibuat — ia ikut tersimpan di
`decisions.cost_breakdown` (JSONB) dan akan tetap terlihat di halaman Decision & Evidence,
dossier, dan approval-summary.

## 6. Batas & catatan jujur (tidak ditutup-tutupi)

1. **Bukti layar panel biaya belum diambil.** Konsol hanya bisa dibuka lewat login, dan kata sandi
   akun demo tidak diketik agent (aturan `ONBOARDING.md`: jangan menuliskan kata sandi).
   Penggantinya bersifat kode+API: `costFacts` diuji DOM-level (3 tes) dan pecahan terbukti
   tersimpan di DB. Bila diinginkan, bukti layar bisa diambil pemilik setelah login (buka
   Decision & Evidence untuk keputusan `7da222a6-…`).
2. **Fixture 4 kasus skrip (`POST /demo/seed`) sudah tidak sama dengan mesin** — dan ini
   **bukan akibat 7d**: DB menyimpan 16.206.000 (Cianjur, 600 kg, quote 26.200) sedangkan mesin
   menghitung ±14.169.953 bahkan **sebelum** 7d, karena data & kapasitas batch sekarang berbeda
   (492–500 kg, harga terbaru). Tidak diperbaiki di sini: mengubah angka itu menyentuh narasi juri
   (angka "Rp16,2 jt" juga dipakai di panel login & beberapa dokumen), jadi menunggu keputusan
   pemilik. Opsi: (a) perbarui fixture ke angka mesin, atau (b) berhenti memaku SDC di fixture dan
   biarkan narasi memakai angka mesin.
3. **pytest menulis ke DB demo** (residu lama, F6 (b)) — skrip bukti fase ini menambah 1 keputusan
   (`7da222a6-…`); tetap disarankan `TEST_DATABASE_URL` terpisah.
4. **`next build` tidak dijalankan** karena dev server hidup (aturan repo). Jalankan setelah
   kontainer frontend di-restart bila perlu bukti build.
