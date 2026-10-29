# Ruling — Angkut per trip, laju susut per komoditas, penalti kesegaran linear

**Tanggal:** 29 Oktober 2026 (revisi `sdc-2026.10.29b`)
**Pemilik keputusan:** Roy — permintaan langsung di sesi Hermes 29 Okt 2026:
*"sesuaikan saja dengan dua hitungan tersebut"* (tabel 6 komponen SDC + catatan
operasional: angkut per trip, laju susut tidak seragam, penalti kesegaran tidak
cliff) dan *"pakai saja, di rentang dari itu"* untuk laju per komoditas
(beras < 1%, telur 2–5%, sayur 10–20%).
**Menggantikan sebagian:** `docs/ruling-2026-10-15-jarak-pemasok-biaya.md`
(rute dua kaki tetap ada; **tarifnya** berubah dari per ton-km menjadi per trip).

## 1. Keputusan

| Komponen | Rumus lama | Rumus sekarang | Alasan |
|---|---|---|---|
| transport | `300 × km × kg/1000` per kaki | `jumlah_trip × (250.000 + 4.000 × jarak_total)`, `jumlah_trip = ceil(kg ÷ 1.000)` | Biaya truk adalah per trip: 150 kg dan 1 ton ke tujuan yang sama menanggung ongkos berangkat yang sama |
| expected_loss (susut gudang) | `purchase × 0,2 × (1 − freshness)` | `purchase × laju_komoditas × (hari simpan ÷ umur simpan)` | 20% seragam menghukum beras (umur 180 hari) seberat ayam (5 hari); `(1 − freshness)` mengukur mutu kiriman, bukan lama simpan |
| freshness_risk | `purchase × 0,50` bila freshness < 0,60 | `purchase × 0,50 × (0,60 − f) ÷ 0,60` bila f < 0,60 | Cliff: 0,599 → +50% sedangkan 0,601 → 0; kurva linear mempertahankan puncak 50% tanpa lompatan |
| safety_penalty | `purchase × 0,10` bila needs_verification | **tidak diubah** | Ini harga ketidakpastian, bukan uang keluar — sudah dipisah ke blok "SDC analitis", tidak masuk PO |
| handling | flat 150.000 | **tidak diubah** | — |
| pembulatan | HALF_UP 2dp per komponen | **tidak diubah** | breakdown selalu menjumlah persis ke total |

Laju susut per umur simpan (`backend/app/core/shrinkage.py`):

| komoditas | laju | rentang pemilik |
|---|---|---|
| beras | 0,8% | < 1% |
| telur | 4% | 2–5% |
| wortel (sayur) | 15% | 10–20% |
| ayam | 12% | tidak disebut; diasumsikan "protein segar" — di bawah sayur, di atas telur |
| komoditas tak terdaftar | 20% | cadangan kontrak lama, **selalu** dilabeli `laju_default_0.2` |

Tarif angkut adalah **asumsi** dan dilabeli `tarif_per_trip_asumsi` di
`cost_breakdown` sampai ada angka resmi perusahaan logistik. Ia tidak boleh
disajikan sebagai tarif nyata (`Rules.md` §1.4).

## 2. Rute berbilang kaki: tarif berangkat dibayar sekali

`transport = jumlah_trip × (250.000 + 4.000 × (km_pemasok + km_linehaul))`.
Menghitung dua kaki secara terpisah akan menagih biaya berangkat dua kali untuk
satu pengiriman. Rupiah per kaki tetap dilaporkan
(`transport_supplier_leg`, `transport_linehaul`) sebagai **alokasi proporsional
km** dengan label `transport_allocation: proporsional_km`; jumlah keduanya sama
persis dengan `transport`.

Jalur pengadaan (pemasok → SPPG langsung) hanya punya satu kaki. Bila jarak
tidak diketahui, biaya angkut 0 + label `jarak_tidak_diketahui` — tidak ada tarif
berangkat yang dikarang.

## 3. Dampak angka (data demo, dihitung ulang 29 Okt 2026)

41 dari 45 keputusan dihitung ulang (`backend/scripts/hitung_ulang_biaya.py`);
4 dilewati karena administratif tanpa rincian biaya transfer.

| kasus | SDC sebelum | SDC sesudah | Δ |
|---|---|---|---|
| supplier_procurement (b54d0f11) | 25.299.695,70 | 27.263.042,09 | +1.963.346,39 |
| wortel-coldchain-hold (c0b5a496) | 7.899.883,54 | 9.521.102,09 | +1.621.218,55 |
| wortel-coldchain-sah (21ff762b) | 8.715.660,76 | 10.330.674,94 | +1.615.014,18 |
| rejection-loop-kuota (70d3c0d0) | 18.987.283,20 | 20.525.775,74 | +1.538.492,54 |
| shortage-darurat (20ff3510) | 24.638.468,16 | 26.128.310,46 | +1.489.842,30 |
| beras-ambient (a37e7441) | 8.092.112,89 | 9.600.093,94 | +1.507.981,05 |

Arah perubahan: angkut naik tajam (tarif berangkat), susut turun (laju per
komoditas jauh di bawah 20%), penalti kesegaran turun untuk nilai di dekat
ambang. Efek bersih pada SDC hampir selalu **naik** karena kenaikan angkut
lebih besar daripada penurunan susut.

Konsekuensi ranking: SDC adalah tie-breaker resmi (skor DESC, SDC ASC). Kandidat
dengan skor identik dapat bertukar urutan setelah perubahan ini. Jarak dan
kelayakan delivery window (yang menentukan skor) **tidak** berubah.

## 4. Batas keras yang tidak berubah

- Safety FAIL tetap `ValueError` sebelum satu angka pun dihitung; tidak ada
  jalur yang memberi SDC pada batch FAIL.
- Penalti risiko tidak pernah masuk PO/invoice (`commercial_cost.py`): invoice =
  purchase + transport + handling.
- Semua angka tetap deterministik, 2dp HALF_UP per komponen, jumlah komponen =
  total.
- LLM tidak menghitung angka ini; semuanya kode bertes di `backend/app/core/*`.

## 5. Data lama

Rumus berubah → angka tersimpan harus dihitung ulang, bukan dibiarkan. Skrip
`backend/scripts/hitung_ulang_biaya.py` memakai mesin yang sama dengan tombol
"Hitung ulang biaya" dan, sesuai temuan audit 26 Okt 2026, menyinkronkan
`agent_traces.output_summary["sdc"]` sekaligus. Tanpa langkah kedua, tab Agent
Log menampilkan angka lama yang bertentangan dengan kartu rekomendasi.
