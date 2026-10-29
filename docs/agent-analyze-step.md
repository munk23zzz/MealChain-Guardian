# Langkah ANALYZE — hipotesis sebab dari LLM, angka tetap dari kode

Status: **aktif di jalur demo pengadaan** (`/demo/agent/run`, mode `supplier_procurement`).
Diperkenalkan 29 Okt 2026 (TODO S4-83, migration `045_analyze_step`).

## 1. Mengapa langkah ini ada

Sebelum ANALYZE, satu putaran agent hanya memakai model di dua tempat: VERIFY
(menilai konsistensi) dan SUPERVISE (narasi akhir). Semua angka — stok, kebutuhan,
gap, peringkat pemasok, SDC — keluar dari kode. Itu disengaja: angka yang lahir dari
LLM adalah karangan.

Akibatnya pertanyaan "mengapa" tidak terjawab. Trace menampilkan
`supply_kg=900, demand_kg=3010, gap=2110` tanpa satu kalimat pun yang menjelaskan apa
artinya bagi pengambil keputusan. ANALYZE mengisi celah itu **tanpa memindahkan
kewenangan angka ke model**.

## 2. Posisi di pipeline

```
DETECT → VERIFY → TRACE → PREDICT → OPTIMIZE → ANALYZE → DECIDE → SUPERVISE → …
```

ANALYZE berjalan **sesudah** seluruh fakta deterministik selesai (stok, kebutuhan,
pemasok terpilih, prakiraan) dan **sebelum** keputusan ditulis. Sifatnya *advisory*:
tidak mengubah verdict verifier, tidak mengubah status keputusan, tidak mengubah angka.

## 3. Pembagian kerja yang dipaku

| Pihak | Menyediakan |
|---|---|
| Kode | commodity, supply_kg, demand_kg, gap_kg, pemasok terpilih (+skor, jarak, harga acuan, deviasi), ringkasan prakiraan, verdict verifier |
| Model | `penyebab` (sebab paling mungkin), `rekomendasi` (satu tindakan), `keyakinan` (tinggi/sedang/rendah) |

Prompt melarang model menghitung atau menyebut angka yang tidak ada di fakta, dan
melarang menyebut ID batch/keputusan, nomor dokumen, atau nama pemasok di luar fakta.

## 4. Dua penjaga keluaran

1. **Pemeriksa angka tak berdasar.** Setiap angka di jawaban model dibandingkan
   dengan angka di fakta (setelah normalisasi format Indonesia: `2.110` = `2110`,
   `1.500,5` = `1500.5`). Angka yang tidak punya padanan dicatat di
   `ungrounded_numbers` dan status menjadi `ungrounded`.
2. **Pembersih ID karangan.** Pola UUID di jawaban diganti `(id tidak ada di fakta)`.
   Fakta memang tidak pernah membawa ID, jadi UUID di jawaban pasti karangan — dan
   ID palsu di layar lebih berbahaya daripada kalimat yang tidak lengkap.

Status yang mungkin: `analyzed` (bersih), `ungrounded` (ada angka/ID tak berdasar),
`unavailable` (seluruh rantai model mati), `error` (jawaban tak bisa diurai).
Pada semua status selain `analyzed`, teks tetap disimpan apa adanya **beserta
peringatannya** — bukan dibuang, bukan diperbaiki diam-diam.

## 5. Bukti dua putaran nyata (29 Okt 2026)

| Putaran | Keputusan | Durasi ANALYZE | Provider | Status | Angka ditandai |
|---|---|---|---|---|---|
| 1 | `9e0cb1fb-4e59-409e-8d30-0c85add1ead0` | 8.337 ms | `primary:agentcore` | `ungrounded` | 14 token |
| 2 | `86cad754-e175-49da-96ca-a0250ad81cb7` | 7.074 ms | `primary:agentcore` | `ungrounded` | `1220`, `1440`, `1750.00`, `3`, `48`, `800` |

Bacaan jujur: model **cenderung mengarang angka tambahan** (mis. "800 kg", "48 jam",
kuantitas pemasok yang tidak ada di fakta). Penjaga menangkapnya, dan angka yang
berasal dari fakta (`900,00`, `3010,00`, `2110,00`) tidak ikut ditandai — jadi
peringatan yang muncul memang peringatan, bukan derau. Karena itu ANALYZE tidak
boleh dipakai sebagai sumber angka, dan VERIFY tetap pemegang keputusan konsistensi.

## 6. Biaya dan kegagalan

- Latensi nyata 7–8 detik per putaran (AgentCore). Rantai fallback tetap dipakai:
  bila slot primer mati, label provider menunjukkan pemenangnya (`slot:kind`).
- Bila seluruh rantai mati, langkah ditulis dengan status `unavailable` + alasan, dan
  putaran tetap lanjut ke DECIDE. Analisis yang tidak ada tidak boleh menghentikan
  pengadaan.
- `duration_ms` kini terisi untuk langkah ini, sehingga timeline Agent Log
  menampilkan waktu nyata, bukan waktu penulisan baris.

## 7. Cara memverifikasi ulang

```bash
# tes kontrak langkah
docker exec mealchain-backend python -m pytest /app/tests/test_hypothesis_client.py -q

# putaran nyata (menulis satu keputusan demo), lalu periksa trace-nya
docker exec mealchain-postgres psql -U mealchain -d mealchain -c \
  "SELECT step_name, duration_ms, output_summary->>'status', output_summary->>'provider',
          output_summary->>'ungrounded_numbers'
     FROM agent_traces WHERE decision_id='<id>' ORDER BY step_at;"
```
