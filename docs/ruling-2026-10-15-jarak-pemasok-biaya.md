# Ruling — Jarak pemasok masuk biaya SDC (Fase 7d)

**Tanggal:** 15 Oktober 2026
**Pemilik keputusan:** Roy (plan `2026-10-14_scope-pemasok-peta-rentang.md` §7.4 keputusan #4:
*"YA — pemilik ingin jarak pemasok ikut dihitung dalam biaya SDC"*, dinaikkan menjadi fase
tersendiri **7d** di §7.4b)
**Pelaksana:** Hermes
**Bukti angka & tes:** `docs/verification/fase-7d.md`

## 1. Keputusan

Biaya angkut satu kandidat balancing sekarang **DUA KAKI**, bukan satu:

```
angkut = kaki pertama (pemasok → SPPG sumber) + linehaul (SPPG sumber → SPPG tujuan)
tarif  = 300 Rp/km/ton untuk KEDUA kaki (konstanta tidak berubah)
```

- **Kaki pertama** dihitung dari koordinat nyata: `suppliers.latitude/longitude` →
  `locations.latitude/longitude` SPPG tempat batch berada. Rumusnya haversine
  `app/core/geo.py` (satu implementasi, dibagi dengan halaman Pemasok & validasi seed 7a).
- **Linehaul** tetap dari matriks SPPG↔SPPG `app/core/logistics.py` (Cianjur–Jakarta 120 km dll).
- Komponen SDC **tetap enam** (`purchase, transport, handling, expected_loss, freshness_risk,
  safety_penalty`) — `app/core/safe_delivered_cost.py` **tidak disentuh**; yang berubah hanya nilai
  `transport` yang disuapkan ke sana.

## 2. Alasan

1. Data koordinat pemasok sudah ada dan sudah dipakai untuk fitur "terjangkau" (7a–7c), tetapi
   angka itu **tidak pernah masuk keputusan**: engine hanya memakai `reliability_score` dan
   komoditas. Artinya peta pemasok dan biaya keputusan bercerita dua hal berbeda.
2. Skenario yang mau ditunjukkan ke juri: sumber yang **murah tapi jauh** memiliki biaya angkut
   tersembunyi. Tanpa kaki pertama, sistem bisa merekomendasikan pemasok 45 km dari gudang
   seolah angkutnya nol dari titik pemasok.
3. Memasukkan jarak ke **skor** (bukan biaya) akan bertabrakan dengan kontrak terkunci Task 5
   (`score = DemandFit × SupplyAvail × Freshness × Safety × Reliability × LogisticsFeasible`).
   Karena itu jarak masuk sebagai **biaya**, dan biaya sudah menjadi tie-breaker resmi ranking
   (Task 7: skor DESC, SDC ASC).

## 3. Yang TIDAK berubah (batas keras)

- **Skor & eligibilitas tidak bergeser.** `logistics_distance_km`, `logistics_time_min`, dan
  `logistics_feasible` tetap nilai linehaul → delivery window, hard constraint, dan peringkat
  faktor tetap sama. Biaya hanya memutus seri skor yang identik.
- **Safety/kesegaran tidak disesuaikan** oleh biaya: PASS/FAIL/NEEDS_VERIFICATION tetap dari
  evaluator, tidak pernah dikompensasi angka rupiah (Rules.md).
- **Tarif 300 Rp/km/ton** tidak diubah, tidak ada tarif kedua per kaki.
- **14 pemasok kanonik & 14 kutipan harga** tidak disentuh.

## 4. Fallback: koordinat tidak lengkap TIDAK ditebak

Modul `app/core/supplier_leg.py` mengembalikan `None` bila salah satu koordinat kosong/separuh.
Pemanggil menuliskannya sebagai **biaya 0 + label alasan**, bukan 0 km yang menyamar sebagai data
(0 km berarti "pemasok menempel di dinding SPPG" — klaim yang tidak punya dasar).

| label `supplier_leg_reference` | arti | biaya kaki |
|---|---|---|
| `supplier_coordinates` | jarak terhitung dari koordinat nyata | `300 × km × ton` |
| `supplier_coordinates_missing` | identitas pemasok ada, koordinat kosong | 0,00 + label |
| `no_supplier` | batch/quote tanpa identitas pemasok | 0,00 + label |

Payload kandidat membawa `supplier_leg = {source_location, supplier_id, km, cost, reference}`;
`cost_breakdown` membawa `transport_linehaul`, `transport_supplier_leg`, `supplier_leg_km`,
`supplier_leg_reference`, plus alias `logistics` = total `transport` (pembaca lama/UI).
`transport` tetap = `linehaul + kaki` sehingga enam komponen tetap menjumlah persis ke
`safe_delivered_cost` (audit-proof, diuji).

## 5. Kompatibilitas kontrak

- `fetch_facts` kontrak Task 9 **tetap sah sebagai 6-tuple**; elemen ke-**7** (peta
  `(supplier_id, nama lokasi) → km`) opsional. Tanpa elemen itu, perilaku = sebelum 7d dan kaki
  pertama ditandai `supplier_coordinates_missing`/`no_supplier`. Test Task 9 lama hijau tanpa diubah.
- Keputusan lama (mis. 4 kasus skrip hasil `POST /demo/seed`) **tidak ditulis ulang**; UI hanya
  menampilkan baris pecahan angkut untuk keputusan yang memang membawa pecahannya.

## 6. Dampak angka (syarat §7.4b)

| kasus skrip | kandidat | SDC sebelum | SDC sesudah | delta | kaki |
|---|---|---|---|---|---|
| rejection-loop-kuota (v1–v3) | Cianjur→Jakarta telur | ±14.169.953 | ±14.170.235 | **+282,00** | 1,880 km |
| shortage-darurat | Bogor→Jakarta telur | ±14.975.145 | ±14.981.798 | **+6.653,07** | 45,075 km |
| supplier-janggal | Cianjur→Jakarta telur | ±14.169.953 | ±14.170.235 | **+282,00** | 1,880 km |
| gangguan-logistik v1 / v2 | Bogor / Cianjur→Jakarta telur | ±14.975.145 / ±14.169.953 | ±14.981.798 / ±14.170.235 | **+6.653,07 / +282,00** | 45,075 / 1,880 km |

- **Delta adalah invarian** (300 × km × ton dengan km terpaku koordinat). Angka absolut bergerak
  beberapa ratus rupiah antar run karena data supply/demand/harga di DB demo ikut berubah —
  residu yang sudah tercatat di `docs/verification/fase-6.md` (pytest menulis ke DB demo).
- **Tidak ada kandidat yang berpindah peringkat** (rank identik sebelum/sesudah, 14 kandidat).
- **Jangkar kanonik utuh**: total telur 4.900 kg, 3 surplus : 7 shortage, Cianjur 1.400 kg —
  tes jangkar `tests/test_demo_timeseries_api.py` lulus.
- 14 dari 14 kandidat punya kaki pertama **terhitung** (0 label "tidak diketahui") karena seluruh
  35 pemasok & 10 lokasi punya koordinat; jalur label jujur diuji terpisah dengan fixture.

## 7. Catatan jujur

- Angka **kasus skrip di DB sudah berbeda dari mesin SEBELUM 7d** (mis. DB 16.206.000 vs mesin
  14.169.953 untuk Cianjur→Jakarta). Penyebabnya fixture rilis lama (600 kg, quote 26.200) versus
  data & kapasitas batch sekarang (492–500 kg dari harga terbaru). Ini **bukan akibat 7d** dan
  tidak diperbaiki di sini — keputusan mengubah fixture demo menyentuh narasi juri (angka 16,2 jt
  juga dipakai di panel login & dokumen), jadi menunggu keputusan pemilik.
- Bukti layar panel biaya belum diambil di sesi ini: konsol hanya bisa dibuka dengan login, dan
  kata sandi akun demo tidak diketik oleh agent (aturan repo `ONBOARDING.md`). Bukti yang ada:
  API nyata + DB (keputusan `7da222a6-…` menyimpan `transport_supplier_leg=6653.07`,
  `supplier_leg_km=45.075`, `reference=supplier_coordinates`), plus tes DOM `costFacts` yang lulus.
