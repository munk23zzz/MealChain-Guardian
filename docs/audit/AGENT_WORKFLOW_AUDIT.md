# AGENT_WORKFLOW_AUDIT — MealChain Guardian

Status: **audit selesai (bukti terkumpul)** — 26 Oktober 2026.
Objek: pipeline `DETECT → PREDICT → OPTIMIZE → DECIDE → VERIFY → ACT → LEARN`,
sifat deterministik vs template tiap tahap, kecocokan angka `agent_traces`
dengan `decisions`, dan perlakuan verdict verifier `UNAVAILABLE`.
Lingkungan: stack berjalan + DB klon sekali pakai `audit_logic` (aturan dan
perintah di `BUSINESS_LOGIC_AUDIT.md` §0 — DB demo hanya SELECT, klon dihapus
sesudah audit).

## 1. Peta pipeline: siapa menghitung apa

| Tahap | Penulis | Sifat | Bukti |
|---|---|---|---|
| `DETECT` | `recommendation_service.build_recommendations` (Event 1), `core.price.price_deviation` (Event 2), `evaluate_safety` (Event 3) | **Deterministik** (tanpa LLM) | `services/event1_orchestrator.py:126-136`, `event2_service.py:277-296`, `event3_service.py:286-303` |
| `VERIFY` | `run_verifier` → rantai provider (Bedrock / SAP AI Core) | **LLM**, fail-closed ke `UNAVAILABLE` | `ai_providers/verifier_client.py:105-199` |
| `TRACE` | orchestrator (penanda langkah) | Metadata, bukan hitungan | `event1_orchestrator.py:240-248` (`{"steps_recorded": 6}`) |
| `PREDICT` | `run_forecast` (SAP-RPT-1.6) atau fallback statistik | Provider/LLM; fallback **deterministik** | `event1_orchestrator.py:250-298` |
| `OPTIMIZE` | `core.scoring` (ranking kandidat) | **Deterministik** | `event1_orchestrator.py:300-313`, `core/scoring.py:66-90` |
| `DECIDE` | persist `Decision` (status `proposed`) | **Deterministik** | `event1_orchestrator.py:315-327` |
| `SUPERVISE` | `run_supervisor` (narasi LLM) | **Template/LLM naratif — tidak dipakai untuk angka** | `services/supervisor_client.py`, `event1_orchestrator.py:329-358` |
| `ACT` | `POST /actions/execute` → mock SAP PO | **Deterministik**, hanya setelah approval manusia | `api/actions.py:851-868` |
| `LEARN` | `POST /actions/repropose` | **Template kode** (bukan model): `learning_note` = teks + `rejection_reason` | `api/actions.py:972-990` |

Konsekuensi penting: **tidak ada satu keputusan pun yang melewati ketujuh
tahap itu dalam satu alur.** `ACT` hanya lahir dari `execute`, `LEARN` hanya
dari `repropose`, dan Event 1 berhenti di `DECIDE`/`SUPERVISE`. Klaim "pipeline
tujuh tahap" benar sebagai **kumpulan jalur**, tidak sebagai urutan yang
dialami satu keputusan. Bukti kelengkapan tahap pada dataset demo:

```sql
-- DB demo, read-only
select step_name, count(*) from agent_traces group by 1 order by 2 desc;
```

```
DECIDE 23 | DETECT 23 | LEARN 9 | PREDICT 6 | VERIFY 4 | OPTIMIZE 3 | ACT 1
(TRACE 0, SUPERVISE 0 — total 69 baris jejak untuk 32 keputusan)
```

## 2. Bukti jalur NYATA berjalan (Event 1 penuh)

Perintah (pada klon, `DEMO_SESSION_ENFORCE=false`):

```bash
docker exec -e DATABASE_URL='…/audit_logic' -e DEMO_MODE=true \
  -e DEMO_SESSION_ENFORCE=false -e MULTI_AGENT_REVIEW=false \
  mealchain-backend python _audit_tmp/probe_s3_lanjut.py
# di dalam probe: POST /demo/event1 {"commodity":"telur","target_location":"Jakarta"}
```

Hasil nyata (`201`):

| Butir | Nilai |
|---|---|
| Keputusan | `5ae2b9c1-3e20-47e4-a36c-7a5cc64c50d1` |
| Status lahir | `proposed` (`approved=false`) |
| `quantity_kg` | **685,00** |
| `safe_delivered_cost` | **18.432.925,78** |
| Tahap yang ditulis | `DETECT, VERIFY, TRACE, PREDICT, OPTIMIZE, DECIDE, SUPERVISE` |
| Kandidat terpilih | `Cianjur→Jakarta:telur`, rank 1, score 0,785083, batch `7ed8ff62…` |
| Verifier | `FLAGGED`, provider `primary:agentcore`, alasan menyebut freshness Bogor `needs_verification` (0,7774) |
| Forecast | `7.333,956` method `sap_rpt_1_6`, provider `SAP-RPT-1.6` |
| Supervisor | `narrated`, provider `primary:agentcore` |

Angka jejak yang tersimpan untuk keputusan itu **konsisten** dengan
keputusannya: `DETECT` menyimpan `surplus/shortage.quantity_kg = 685.00`
(= `decisions.quantity_kg`), `OPTIMIZE` menyimpan
`safe_delivered_cost = 18432925.78` (= `decisions.safe_delivered_cost`), dan
`DECIDE` menyimpan `decision_id` + `expires_at`. Jadi **pada jalur kode nyata**
angka jejak memang berasal dari perhitungan, bukan disalin.

## 3. Dataset demo: jejak angka sebagian besar template

| Ukuran (DB demo, 32 keputusan / 69 jejak) | Hasil |
|---|---|
| Jejak berlabel `output_summary->>'sumber' = 'template demo'` | **8** baris (4 `DETECT`, 4 `DECIDE`) |
| Keputusan yang punya jejak | 32/32 |
| Keputusan dengan jejak **hanya naratif** (tanpa angka) | **10** dari 29 yang berjejak |
| Jejak `DECIDE` dengan kunci `sdc` | 18 |
| `sdc` jejak **identik** dengan `decisions.safe_delivered_cost` (2 dp) | **14 dari 19** jejak numerik; 3 selisih hanya pembulatan 3 dp (`11.024.322,666` vs `11.024.322,67`) |

Dua mekanisme penyemai menjelaskan hampir semua kecocokan itu:

1. `seed/demo_template.py:1070-1104` (`_ringkas_jejak`) menulis ringkasan
   `"sumber": "template demo"` dan menyalin `sdc` **dari keputusan**.
2. `seed/demo_template.py:1517-1546` (`_selaraskan_sdc_jejak`) menulis ulang
   `agent_traces.output_summary.sdc` agar sama dengan
   `decisions.safe_delivered_cost` (toleransi ≤ Rp1). Komentar fungsinya
   menyebut audit 26 Okt 2026: jejak dulu memuat angka tulisan tangan
   (16.206.000 / 14.787.096,28) yang berbeda dari SDC keputusan.

Artinya: **kecocokan `trace.sdc` ↔ `decisions.safe_delivered_cost` di dataset
demo bukan bukti bahwa agen menghitung angka itu** — kecocokan dipaksakan
sesudahnya (AG-01). Pada jalur kode nyata (§2) kecocokan itu punya makna.

## 4. Perbandingan angka jejak vs keputusan (6 contoh)

Sumber: kueri DB demo (read-only)

```sql
select d.demo_case, d.quantity_kg, d.safe_delivered_cost,
       (select t.output_summary->>'sdc' from agent_traces t
          where t.decision_id=d.id and t.step_name='DECIDE' limit 1) sdc_jejak,
       (select t.output_summary->>'shortage_kg' from agent_traces t
          where t.decision_id=d.id and t.step_name='DETECT' limit 1) shortage_jejak
from decisions d where exists (select 1 from agent_traces t where t.decision_id=d.id);
```

| Keputusan | Tipe | qty (kg) | SDC (Rp) | `sdc` jejak | `shortage_kg` jejak | Cocok? |
|---|---|---|---|---|---|---|
| `a1002661…` | safety_disruption | 780 | 22.080.862,39 | 22.080.862,39 | — | **ya** |
| `336ad2d0…` | safety_disruption | 780 | 26.408.213,64 | 26.408.213,64 | — | **ya** |
| `20dd1607…` | safety_disruption | 600 | 15.739.132,38 | 15.739.132,38 | — | **ya** |
| `30bce401…` | price_anomaly | 420 | 11.024.322,67 | 11.024.322,666 | 420.0 | **tidak** (pembulatan 3 dp) |
| `3e2e3cc7…` | regional_balance | 300 | 9.750.000,00 | — (jejak `DECIDE` = `alokasi_kg: 300`) | — | **ya** untuk kuantitas, `sdc` tidak ada di jejak |
| `0157b81c…` | price_anomaly | 600 | 15.739.132,38 | — | — | **tidak ada angka di jejak** (hanya `DETECT` naratif) |
| `ae472e84…` | supplier_exclusion | — | — | — | — | **tidak ada angka** (jejak `DETECT`/`DECIDE` = "dibuat oleh template demo") |

Catatan pembulatan: `safe_delivered_cost` adalah `numeric(12,2)` sedangkan
jejak menyimpan float 3 desimal untuk keputusan salinan 0,7. Selisihnya
Rp0,003 — tidak mengubah angka tampilan, tetapi pencocokan programatik
(`==`) gagal dan itulah yang dipakai uji invarian.

## 5. Verifier `UNAVAILABLE` tidak dianggap lulus

| Uji | Hasil |
|---|---|
| `run_verifier(ctx, default_chain=[])` | `verdict=UNAVAILABLE`, `provider=null`, `recorded=false` |
| `POST /actions/verify` tanpa provider | verdict `UNAVAILABLE` ditulis ke `verifier_note`, **`verified_by` tidak ditulis**; `recorded=false`; tidak ada blok ledger (`api/actions.py:501-541`) |
| `POST /actions/approve` saat `verifier_note='unavailable'` | **409** `keputusan belum diverifikasi — catat hasil verifier dulu sebelum meminta persetujuan` |
| `POST /actions/execute` saat `verifier_note='unavailable'` | **409** `decision belum terverifikasi` |
| Verdict yang sudah tercatat tidak bisa ditimpa | **409** `verdict sudah tercatat — hasil audit tidak bisa ditimpa…` |
| Retry hanya boleh bila percobaan sebelumnya tanpa verdict | dibuktikan oleh kode `_verifier_unverified` (`api/actions.py:115-125`) + tes `test_verifier_tidak_bisa_diulang.py` (lulus di klon) |

Kesimpulan: `UNAVAILABLE` **fail-closed** dan tidak pernah membuka pagar
approve/execute. Yang perlu dibaca hati-hati: pada jalur Event 1,
`verified_by` ditulis **tanpa syarat** (`event1_orchestrator.py:213-214`),
jadi kolom itu tidak boleh dipakai sendiri sebagai bukti "sudah dinilai" —
yang menentukan tetap `verifier_note ∈ {consistent, flagged}`.

## 6. PREDICT tidak mempengaruhi keputusan

Pada uji Event 1, `PREDICT` menghasilkan `forecast_qty_kg = 7.333,956`
(7 hari) sementara `DECIDE` menetapkan alokasi **685 kg** dari kandidat
ranking. Tidak ada kolom `decisions.forecast_*`, dan `ctx` verifier maupun
`cost_breakdown` tidak memuat angka forecast. Forecast hanya muncul di
narasi `SUPERVISE` ("Forecast SAP-RPT-1.6: 7.334 kg"). Jadi PREDICT adalah
**tahap dokumentasi/narasi**, bukan masukan keputusan (AG-02). Tidak salah
secara keamanan, tetapi klaim "prediksi demand memandu alokasi" tidak
didukung kode.

## 7. Temuan

| ID | Severity | Temuan | Status |
|---|---|---|---|
| AG-01 | **P2** | Kecocokan `sdc` jejak ↔ keputusan di dataset demo dipaksakan oleh `_selaraskan_sdc_jejak`; 8/69 jejak berlabel "template demo" dan 10 keputusan hanya punya jejak naratif. Jejak tidak boleh dipakai sebagai bukti komputasi independen | Terbuka |
| AG-02 | **P2** | `PREDICT` tidak dipakai `DECIDE` (7.333,96 kg vs 685 kg); hanya muncul di narasi | Terbuka (dokumentasi) |
| AG-03 | P3 | Jalur Event 1 mencatat verdict `flagged` tanpa menaikkan status ke `verifier_flagged` (beda dari `/actions/verify`) — silang dengan BL-06 | Terbuka |
| AG-04 | P3 | Narasi `SUPERVISE` (LLM) dapat bertentangan dengan verdict verifier: contoh nyata menulis "Semua batch (840+560=1.400 kg) di Cianjur aman" sementara verifier `FLAGGED` menyorot `freshness needs_verification`; juga "rincian alasan tidak tersedia (API 404)" | Terbuka (narasi tidak safety-critical, tetapi dibaca juri) |
| AG-05 | P3 | 10 keputusan berjejak tanpa angka sama sekali (seluruh `price_anomaly` 600 kg dan `supplier_exclusion`/`restoration`) | Terbuka (data demo) |
| AG-06 | P3 | `agent_traces` bukan append-only: penyemai menulis ulang `output_summary` (AG-01). Integritas tindakan hanya dijamin `ledger_blocks` | Terbuka |
| AG-07 | P3 | `LEARN` bukan pembelajaran model: `repropose` menyalin substansi induk (`quantity_kg`, `safe_delivered_cost`, `cost_breakdown`) dan menambah `iteration+1` + teks `learning_note` berisi `rejection_reason`. Terukur: anak `2c9c6914…` iterasi 2, `supersedes ca405786…` | Sesuai desain (klaim "learning" harus hati-hati) |
| AG-08 | P3 | Tidak ada satu keputusan pun yang mengalami ketujuh tahap; `ACT`/`LEARN` lahir dari endpoint manusia, bukan dari orchestrator | Terbuka (dokumentasi) |

Rincian bukti tambahan:

- **AG-04** — keluaran `supervisor.summary` pada uji Event 1 (kutipan apa
  adanya): "Verifikasi backend menandai FLAGGED—rincian alasan tidak tersedia
  (API 404). Semua batch (840+560=1.400 kg) di Cianjur aman, tidak ada yang
  kedaluwarsa 48 jam." Verifier justru menyorot kandidat Bogor
  (`needs_verification`, freshness 0,7774). Kalimat "API 404" itu juga
  **karangan narasi**: konteks supervisor hanya menerima `verifier_verdict`
  (`event1_orchestrator.py:332-342`), tidak menerima `reason`, dan tidak ada
  panggilan API 404 pada jalur itu. Narasi tidak boleh dipakai sebagai
  ringkasan hasil audit.
- **AG-07** — `POST /actions/repropose` pada `ca405786…` (rejected) → `201`,
  anak `2c9c6914…` `status=proposed`, `iteration=2`,
  `parent_rejection_reason="Kuota SPPG Bandung penuh minggu ini — coba skema
  bertahap."`, jejak `LEARN` `tool_called=rejection_loop.repropose`. Tidak ada
  perubahan angka; yang berubah hanya iterasi dan catatan.
- **AG-08** — jejak Event 1 (`5ae2b9c1…`) berisi 7 baris: DETECT, VERIFY,
  TRACE, PREDICT, OPTIMIZE, DECIDE, SUPERVISE. `ACT` baru muncul pada uji
  eksekusi (`agent_traces.step_name='ACT'`, total 1 baris di DB demo).

## 8. Artefak lingkungan (bukan temuan)

Saat `MULTI_AGENT_REVIEW=true` (nilai kontainer), review 7-worker menulis jejak
`SUPERVISE` berisi
`AgentApiError: HTTP 404 pada /decisions/<id>/approval-summary: {"detail":"decision tidak ditemukan"}`.
Penyebabnya bukan produk: worker review memanggil API HTTP (`agent/tools.py:222`)
yang pada audit ini menunjuk DB demo, sedangkan keputusan uji lahir di DB klon.
Pada stack normal keduanya menunjuk DB yang sama. Jalur review 7-worker
karena itu **tidak dinilai** di audit ini (**NOT TESTED**), dan angka apa pun
dari jalur itu tidak dipakai sebagai bukti.

## 9. Yang TIDAK diuji

| Butir | Alasan |
|---|---|
| Jalur `MULTI_AGENT_REVIEW` 7 worker + verifier + SUPERVISE (kontrak 9 baris jejak) | Terhalang artefak lingkungan §8 — **NOT TESTED** |
| Kualitas/kebenaran isi verdict LLM (apakah FLAGGED tepat) | Audit ini menilai *perlakuan* verdict, bukan mutu penalaran model — **NOT TESTED** |
| Determinisme provider (`SAP-RPT-1.6`, `agentcore`) pada panggilan berulang | Butuh panggilan berbayar berulang — **NOT TESTED** |
| `PREDICT` fallback statistik vs provider (perbandingan angka) | Tidak dijalankan pada audit ini — **NOT TESTED** |
| Idempotensi replay Event 2/3 (`operation_key`) dengan payload berbeda | Di luar lingkup (lihat AUDIT_04) — **NOT TESTED** |
| Kinerja penulisan jejak pada volume besar | Di luar lingkup |

## 10. Kesimpulan

Pipeline punya **pemisahan yang benar antara hitungan dan narasi**: DETECT,
OPTIMIZE, DECIDE, ACT dihitung kode deterministik; VERIFY adalah penilaian
model yang dicatat server dan fail-closed; SUPERVISE hanya narasi. Angka jejak
pada jalur nyata cocok dengan keputusan karena diturunkan dari objek yang sama.

Yang harus dijaga saat presentasi: (1) kecocokan angka jejak di **dataset
demo** adalah hasil penyelarasan penyemai, bukan bukti agen menghitung (AG-01);
(2) `PREDICT` tidak memandu alokasi (AG-02); (3) narasi supervisor bisa
bertentangan dengan verdict (AG-04) sehingga verdict yang harus dikutip, bukan
ringkasan naratif; (4) "tujuh tahap" adalah gabungan beberapa jalur, bukan satu
alur per keputusan (AG-08).
