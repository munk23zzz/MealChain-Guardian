# Seleksi ketat PLAN.md → apa yang akan diterapkan ke MealChain Guardian

**Tanggal:** 2026-10-17 (pengukuran 00:52–02:10 WIB)
**Sumber yang diteliti:** `D:\Downloads\PLAN.md` (757 baris, audit 11 Okt 2026) — dibaca utuh, seluruh 23 item (`PLAN-001`…`PLAN-023`) + addendum §13.1–§13.10
**Objek verifikasi:** repo aktif `E:\hackathon\HackathonAWS\mealchain-guardian` (branch `feature/sprint2-decision-intelligence`, komit `af2cf6f`)
**Metode:** setiap klaim PLAN.md diuji ke artefak repo — berkas, `git`, baris kode (`file:line`), probe API read-only, `psql`, dan suite frontend lewat kontainer. Bukan dari ringkasan sesi.

Metode seleksi: satu item hanya masuk daftar terapan bila (a) menutup risiko nyata pada area yang dinilai/safety, (b) **belum** terwujud di kode dengan cara apa pun, dan (c) biayanya kecil dibanding risikonya. Item yang sudah terwujud dengan bentuk berbeda **ditolak** — bukan dikerjakan ulang agar cocok dengan dokumen.

---

## 1. Ringkasan keputusan

| Keputusan | Jumlah | Item |
|---|---|---|
| **DITERAPKAN** | **4** | `PLAN-022` (jalur tulis transfer), `PLAN-023` + §13.4/§13.9 (semantik nol vs data hilang), `PLAN-012` + §13.3 (papan status per komponen), `PLAN-014` (determinisme gerbang + bukti) |
| **KEPUTUSAN PEMILIK dulu** | 1 | `PLAN-021` (Head-only propose/execute) — bertentangan dengan ruling repo yang berlaku |
| **DITOLAK: sudah terwujud** | 12 | `PLAN-001`, `003`, `004`, `005`, `006`, `007`, `008`, `009`, `010`, `011`, `015`, `020` |
| **DITOLAK: usang / merusak** | 4 | `PLAN-016`, `017`, `018`, `019` (redesign 8 modul) |
| **DITOLAK: blocker eksternal** | 1 | `PLAN-013` (AWS for SAP MCP) |
| `PLAN-002` | — | terwujud sebagian; sisanya berpindah ke `PLAN-022` (terapan) dan `PLAN-021` (keputusan) |
| **Total** | **23** | |

---

## 2. Verifikasi item per item (bukti, bukan kesan)

| PLAN.md | Klaim / tuntutan | Verdict | Bukti terukur di repo |
|---|---|---|---|
| PLAN-001 | Kunci freshness ke satu sumber, `0.85/0.60` | **SUDAH** | `core/freshness.py:7-8` (`PASS_THRESHOLD`, `VERIFY_THRESHOLD`); hanya ada satu pemakai klasifikasi (`api/freshness.py:66`, `services/recommendation_service.py:176`); `0.60` di `core/safe_delivered_cost.py:35` = ambang biaya, kontrak berbeda (persis seperti yang PLAN.md sendiri catat); tidak ada hardcode `0.85` di frontend |
| PLAN-002 | Rekonsiliasi RBAC + approval dua user | **SEBAGIAN** | Guard "satu user hanya sekali approve" ada → 409 `"approval sudah tercatat"` (`api/actions.py:284`); `can_approve`/`can_execute`/`blocking_reasons` datang dari server dan dipakai UI (`ApprovalModal.tsx:52-57`, `ApprovalMenu.tsx:87-98`). Sisa: `PLAN-022` → §4, dan `PLAN-021` → §5 |
| PLAN-003 | Empat status trace dipisah, tidak ada klaim sukses palsu | **SUDAH (bentuk lain)** | `lib/agent-trace.ts:5-20` memaku "tidak ada inferensi" untuk status yang absen; `ProviderPanel.tsx:2` menyatakan "tidak ada klaim sukses tanpa evidence" dan `:48` memetakan `unavailable` → kata "tidak tersedia"; label `Selesai tanpa anomali` yang dikeluhkan PLAN.md **tidak ada** di kode (`grep` = kosong) |
| PLAN-004 | Perbaiki gate `happy-dom` container | **TIDAK BERLAKU** | `frontend/vitest.config.ts:11` memakai `environment: "node"`; `happy-dom` tidak ada di `package.json` maupun `node_modules` kontainer. Semangatnya (jangan bocorkan galat parser ke user) sudah terpasang: `lib/api.ts:23-30` mengembalikan `Respons bukan JSON dari <path> (HTTP n)` |
| PLAN-005 | Shell bersama + navigasi role-aware | **SUDAH** | `SideNav.tsx` + `page.tsx:632-668` (`roles` per tab; `demo-control` hanya approver, `pengaturan` hanya monitor); probe live: monitor `/admin/users` 200, head 403 |
| PLAN-006 | Overview map + breakdown seimbang | **SUDAH (bentuk lain)** | Overview bento + strip KPI dari data peta + tabel breakdown; `/balance/map` terverifikasi live (head 1 lokasi, monitor 10 lokasi) |
| PLAN-007 | Feed rekomendasi + detail | **SUDAH** | `RecommendationCard.tsx`, `Decision & Evidence` sebagai tab tersendiri; status enum backend apa adanya; tenggat dari server |
| PLAN-008 | UX approval/eksekusi + label mock | **SUDAH** | `ApprovalModal`/`ApprovalMenu` fail-closed dari server; label `MOCK`/`Simulasi` ada di `RecommendationCard.tsx`, `ApprovalModal.tsx`, `AgentQualityBoard.tsx`; PO mock `MC-*` |
| PLAN-009 | Demo Control + empat state per skenario | **SUDAH** | `OpsConsole.tsx`, `Event2Panel.tsx`, `ChaosPanel.tsx`, `DemoDataPanel.tsx`; Event 1/2/3 punya jalur sendiri (`api/events.py:34,94`, `api/demo.py:477`) |
| PLAN-010 | KPI & provenance, tanpa UUID mentah | **SUDAH** | `lib/kpi.ts:56-58` mengunci "null ditulis `—`, bukan diganti angka"; penulis metrik kini ada: langkah `ACT` ditulis (`api/actions.py:493`) dan `is_consistent` ditulis 4 layanan (`supplier_eligibility.py:56`, `supplier_exclusion_service.py:156`, `event2_service.py:265`, `event3_service.py:279`) |
| PLAN-011 | SAP AI Core live | **SUDAH** | `ai_providers/sap_ai_core_caller.py` (invoke + predict); `grep "belum terimplementasi"` = kosong; TODO `S4-10` `Done` dengan bukti 11 Okt |
| PLAN-012 | Status per komponen AgentCore | **BELUM** | Tidak ada satu berkas frontend pun yang menyebut AgentCore (`grep -rl agentcore frontend/` = kosong). Bukti per komponen tersebar di dokumen, bukan permukaan produk → §4 W-3 |
| PLAN-013 | AWS for SAP MCP nyata | **TUNDA** | `Roadmap.md` §Sprint 5: "ON-DEMAND, bukan blocker untuk demo utama"; tidak ada konfigurasi S/4HANA di repo; S5-01 `Blocked`, S5-02…S5-06 `Not Started` |
| PLAN-014 | Regresi penuh + rehearsal + bukti tersimpan | **SEBAGIAN** | Dokumen verifikasi `fase-6`…`fase-12` ada; **tetapi** satu gerbang terbukti flaky (§3 W-4) |
| PLAN-015 | Settings/Admin | **SUDAH** | Tab `Pengaturan` (khusus `bgn_monitor`), `api/admin.py`; S4-11 `Done` 11 Okt. Bertentangan dengan PLAN.md yang menyebutnya "out of scope" |
| PLAN-016–019 | Bangun ulang 8 modul + rekonstruksi seluruh UI | **TOLAK — USANG** | PLAN.md merujuk `components/AgentRunSummary.tsx`, `OverviewLocationBreakdown.tsx`, `KpiTargets.tsx`, `lib/trace-normalizer.ts`; keempatnya **tidak ada** di repo ini maupun di klon demo. UI sekarang 11 tab, 887 tes frontend lulus. Menerapkannya = membongkar UI hidup untuk memenuhi dokumen mati |
| PLAN-020 | Audit 10 lokasi | **SUDAH** | 10 lokasi × 3 komoditas di DB; scope per peran terverifikasi live |
| PLAN-021 | Head-only propose/purpose/execute | **KONFLIK KEBIJAKAN** | `VERIFIER_ROLES` masih dipakai (`api/actions.py:30`, baris 111/185/264/352/545). Sementara `docs/ruling-2026-10-14-scope-lokasi.md` §3 (ruling pemilik yang berlaku) hanya mengunci matriks AND **di dalam satu SPPG** — tidak mensyaratkan Head-only, dan justru membahas kelayakan demonya. Dua dokumen kebijakan bertabrakan → §5 |
| PLAN-022 | Scope single-SPPG di SETIAP boundary | **BELUM pada jalur tulis** | `require_scope(user, target_location_id)` hanya dipanggil di cabang `exclusions.ADMIN_TYPES` (`api/actions.py:203, 273, 358, 397`). Untuk keputusan **transfer**, `approve`/`execute` tidak memeriksa lokasi approver dan matriksnya tidak difilter lokasi → §4 W-1 |
| PLAN-023 | Semantik Location Network + penyajian nol | **BELUM (data), SUDAH (peta)** | Peta/lokasi sudah benar; yang belum: pemisahan makna data → §4 W-2 |
| §13.4 | "Record bernilai nol tetap `0`; data hilang/gagal tidak boleh diam-diam jadi nol" | **BELUM** | `api/balance.py:92-101` dan `:216-225` masih mengisi baris supply/demand yang **tidak ada** dengan `Decimal("0")`, dan payload tidak membawa penanda apa pun (`grep data_state/partial/source` = kosong) |
| §13.5 | Jangan rendahkan supplier = SPPG; jangan karang koordinat/rute | **SUDAH** | Rute nyata dari OSRM (`road_routes`) + migrasi `015_batch_dispatch`; 35 supplier terpisah dari lokasi; pin pemasok punya layer sendiri |
| §13.6 | 10 lokasi dengan ID stabil + diskrepansi Malang vs Makassar diakui | **SUDAH** | 10 lokasi di DB; audit sudah tercatat di `TODO.md` F0/F1 |
| §13.9 | Nol tampil `0 kg`, tidak ada teks galat sebagai nilai utama | **SEBAGIAN** | Prinsip null → `—` berlaku di KPI; penyajian stok belum dibuktikan per komponen → masuk W-2 |

---

## 3. Catatan penting: PLAN.md sebagian sudah tidak sinkron

Empat rujukan artefaknya hilang (AgentRunSummary, OverviewLocationBreakdown, KpiTargets, trace-normalizer), head migrasinya tertinggal (`011_supplier_exclusions` vs `016_batch_receipts`), SAP AI Core sudah selesai meski ditandai `Blocked`, dan Settings/Admin sudah selesai meski ditandai di luar scope. Karena itu seleksi ini memakai **kode sebagai kebenaran**, dan PLAN.md hanya diambil bagian yang masih menunjuk masalah nyata.

---

## 4. YANG AKAN DITERAPKAN (4 item)

### W-1 · Tegakkan scope lokasi pada jalur tulis transfer (dari PLAN-022)

**Masalah.** Ruling 2026-10-14 menyatakan approver kedua "tidak lagi boleh berasal dari SPPG lain". Untuk keputusan **transfer**, aturan itu belum ditegakkan: `approve` dan `execute` tidak memanggil `require_scope`, dan matriks approval dihitung dari role saja tanpa filter lokasi.

**Kenapa penting.** Ini area pemisahan tugas (separation of duties) — tepat yang diuji juri pada sistem pangan. Reviewer yang membaca `api/actions.py` akan menemukan jalur tulis yang bisa dilewati walau jalur bacanya sudah terkunci.

**Perubahan.** Tambahkan pemeriksaan scope untuk **semua** tipe keputusan (bukan hanya `ADMIN_TYPES`) di `approve`/`execute`, dan saring matriks dengan `u.location_id == decision.target_location_id` seperti yang sudah dilakukan di cabang exclusion. Satu sumber aturan: helper bersama, bukan salinan ketiga.

**Kriteria penerimaan.** TDD: tes negatif (approver/eksekutor dari SPPG lain → **403** "cakupan lokasi") GAGAL lebih dulu; setelah perbaikan hijau bersama tes scope yang sudah ada (`test_scope_matrix.py`, `test_approval_summary.py`, `test_s4_sec_guards.py`). Tidak ada perubahan perilaku untuk keputusan yang menyasar lokasi approver sendiri.

**Biaya:** S. **Risiko:** rendah — menambah pemeriksaan, bukan mengubah alur.

---

### W-2 · Pisahkan "nol terukur" dari "tidak ada baris / permintaan gagal" (dari PLAN-023 + §13.4 + §13.9)

**Masalah.** `/balance/map` dan `/balance/{lokasi}/{komoditas}` mengisi supply/demand yang **tidak ada** dengan `0` (`api/balance.py:92-101, 216-225`). Di layar, "tidak ada catatan" dan "stok benar-benar nol" tampil identik. Kebijakan pemilik justru menuntut dua hal sekaligus: nol valid **tetap tampil `0 kg`**, tetapi data hilang/gagal **tidak boleh** diam-diam menjadi nol.

**Perubahan.** Tambahkan penanda per titik di payload (mis. `data_state`: `terukur` / `tidak_ada_baris`, plus asal nilai), **tanpa** mengubah aturan tampilan: angka `0` tetap tampil sebagai `0 kg`; penanda hanya muncul di rincian/tooltip internal dan dipakai untuk tidak menghitung "nol" sebagai fakta. Tambahkan validasi seed/kontrak: kombinasi lokasi × komoditas demo yang wajib ada **harus** membuat gate gagal bila hilang, bukan diisi positif atau nol tanpa jejak.

**Kenapa penting.** Ini kekuatan yang sudah jadi identitas repo ("null ditulis `—`, bukan diganti angka" — `lib/kpi.ts:58`). Menutup satu-satunya tempat yang masih melanggarnya membuat klaim kejujuran data berlaku menyeluruh, dan itu bisa ditunjukkan ke juri dalam satu kalimat: "sistem membedakan angka nol dari data yang tidak ada".

**Kriteria penerimaan.** Tes backend memaku tiga kasus terpisah: baris ada dengan nilai 0 → `0` + `terukur`; baris tidak ada → tetap `0` di tampilan tetapi `tidak_ada_baris`; permintaan gagal → bukan `0` faktual. Tes frontend memaku bahwa angka nol tetap dirender sebagai `0 kg` dan tidak pernah diganti pesan galat.

**Biaya:** M. **Risiko:** sedang — menyentuh kontrak API + UI; wajib dijaga agar tidak ada nilai yang berubah tampilannya.

---

### W-3 · Papan status integrasi per komponen (dari PLAN-012 + keputusan owner §13.3)

**Masalah.** Bukti status integrasi sudah ada dan jujur, tetapi **tersebar di dokumen** — tidak ada satu permukaan yang bisa ditunjukkan. Tidak ada satu berkas frontend pun yang menyebut AgentCore. Akibatnya pertanyaan juri "ini jalan di AWS?" hanya bisa dijawab dengan menceritakan dokumen.

**Perubahan.** Satu endpoint read-only + satu panel kontekstual (di dalam tab yang sudah ada, **bukan** modul/tab baru) yang menampilkan per komponen: nama, kategori bukti (`configured` / `provisioned` / `probe-passed` / `contract-tested` / `unavailable`), sumber artefak, waktu pemeriksaan. Isi awalnya: SAP AI Core (`live`, kontrak lulus), mock SAP (`default`), AgentCore Runtime (artefak siap + kontrak lokal lulus, **deploy tertahan izin IAM**), AgentCore Gateway (`tidak ada`), AgentCore Memory (`provisioned`, adapter aplikasi `unavailable`), Observability (`fail-closed`), AWS for SAP MCP (`not started`).

**Kenapa penting.** Ini satu-satunya item yang menambah nilai penjurian langsung: ia mengubah kejujuran yang tersembunyi menjadi bukti yang terlihat, dan mencegah satu-satunya kesalahan fatal — menyebut sesuatu `OPERATIONAL` dari konfigurasi saja.

**Kriteria penerimaan.** Setiap komponen punya kategori + sumber + waktu; tidak ada label `OPERATIONAL` tanpa bukti probe; komponen tanpa bukti berbunyi `unavailable`/`not started`. Tes: bentuk payload + rendering kategori, termasuk kasus "tanpa bukti" tidak pernah hijau.

**Biaya:** M. **Risiko:** rendah untuk data (read-only), sedang untuk tata letak (harus tidak menambah tab).

---

### W-4 · Determinisme gerbang verifikasi (dari PLAN-014)

**Masalah.** Dua kali menjalankan suite frontend dalam 3 menit memberi hasil berbeda: run-1 `2 failed / 885 passed` (`tests/shipment-timeline.test.ts`, menuntut "3 kejadian tercatat" dan mendapat "2"), run-2 `887 passed / 75 berkas` penuh. Gerbang yang bisa berubah karena perbedaan menit tidak bisa jadi dasar klaim "semua lulus".

**Perubahan.** Buat tes itu deterministik terhadap waktu (suntik `now` sebagai parameter, seperti pola `lib/today.ts`/`lib/datetime.ts` di repo), lalu jalankan gerbang lengkap satu kali dalam keadaan bersih (setelah residu tes disapu) dan simpan keluarannya sebagai bukti ber-tanggal — setara `docs/verification/sprint-5-*.md` yang dituntut PLAN.md, memakai konvensi repo.

**Kenapa penting.** Semua klaim lain bergantung pada gerbang ini. Sekali gerbang flaky terbaca reviewer, seluruh laporan verifikasi kehilangan bobot.

**Biaya:** S. **Risiko:** rendah.

---

## 5. SATU keputusan pemilik (bukan pekerjaan teknis)

**`PLAN-021`: Head-only propose/purpose/execute vs ruling repo.**

- PLAN.md §13.1/§13.3 menuntut: hanya Kepala SPPG yang propose, menentukan purpose, dan execute; Ahli Gizi hanya memberi approval kedua.
- `docs/ruling-2026-10-14-scope-lokasi.md` (ruling yang berlaku di repo) mengunci matriks AND **di dalam satu SPPG** dan tidak menyebut Head-only; kode memakai `VERIFIER_ROLES` untuk propose/verify/approve/execute.

**Rekomendasi saya: pertahankan kebijakan repo.** Alasannya: (1) sudah diimplementasikan dan diuji; (2) ruling itu disusun dengan mempertimbangkan kelayakan demo; (3) menerapkan Head-only = perubahan hak akses tiga peran sekaligus, yang justru menaikkan risiko menjelang penjurian. Konsekuensinya: **jangan** mengklaim "hanya Kepala SPPG yang mengeksekusi" di materi presentasi. Bila pemilik tetap ingin Head-only, kerjakan sebagai fase tersendiri dengan TDD dan matriks izin yang diperbarui — bukan disisipkan.

---

## 6. YANG DITOLAK (dan alasannya, supaya tidak diusulkan lagi)

| Yang ditolak | Alasan tunggal yang menentukan |
|---|---|
| Redesign 8 modul (`PLAN-016`…`019`) | Rujukan komponennya sudah tidak ada; UI hidup (11 tab, 887 tes) akan dibongkar untuk memenuhi dokumen usang |
| Gate `happy-dom` (`PLAN-004`) | Tidak berlaku: env `node`, paketnya tidak dipakai |
| Bangun ulang feed/detail/approval/KPI/demo-control (`PLAN-005`…`010`) | Semuanya sudah terwujud; yang tersisa hanya pemolesan yang tidak menutup risiko |
| SAP AI Core (`PLAN-011`) | Sudah selesai dan terbukti live 11 Okt |
| AWS for SAP MCP (`PLAN-013`) | Blocker eksternal (tenant/S/4HANA) + Roadmap menyebutnya on-demand; mock adalah default MVP |
| Settings/Admin (`PLAN-015`) | Sudah selesai sebagai S4-11 |
| Audit 10 lokasi (`PLAN-020`) | Sudah selesai |
| Deploy AgentCore Runtime (bagian `PLAN-012`) | Tertahan izin IAM milik pemilik akun — bukan pekerjaan kode; `agent/README-deploy.md` sudah memuat langkah manualnya |
| Menyeragamkan angka freshness addendum (0.60/0.40) | Berbeda dari kontrak kanonik `docs/Skill.md`; `0.60` hanya ambang biaya |

---

## 7. Urutan eksekusi yang diusulkan

1. **W-4** dulu (gerbang bersih + determinisme) — murah, dan semua bukti berikutnya berdiri di atasnya.
2. **W-1** (scope jalur tulis) — TDD, risiko rendah, menutup lubang pemisahan tugas.
3. **W-2** (semantik nol vs data hilang) — setelah W-4/W-1 hijau, karena menyentuh kontrak API + UI.
4. **W-3** (papan status integrasi) — paling akhir, karena sifatnya permukaan informasi.
5. **Keputusan §5** diparalel: cukup satu jawaban; tanpa itu, `W-1`/`W-2` tetap bisa jalan tapi klaim izin di materi harus ditahan.

Prasyarat sebelum mulai: bersihkan residu 16 user `%@test.local` di DB demo, dan konfirmasi bahwa tidak ada sesi lain yang sedang menyunting repo (mtime menunjukkan aktivitas < 20 menit sebelum pemeriksaan).

---

## 8. Yang TIDAK diverifikasi di dokumen ini

- Suite backend penuh, `tsc`, lint, `next build` — tidak dijalankan pada sesi ini; angka yang dikutip selalu bertanggal.
- Probe endpoint mutasi — sengaja dihindari agar DB demo tidak berubah, sehingga `W-1` masih temuan dari pembacaan kode (belum probe 403/200).
- Inferensi SAP AI Core live dan konektivitas AWS — dikutip dari artefak tim (11–16 Okt), tidak diprobe ulang.
- Apakah klon demo `HackathonBil\MealChainGuardian` memerlukan perlakuan sama — tidak diperiksa.

---

## 9. Status pelaksanaan (bertahap)

### W-1 · SELESAI — 2026-10-17 (TDD; RED dibuktikan lebih dulu)

**Berkas yang diubah**

| Berkas | Perubahan |
|---|---|
| `backend/app/api/actions.py` | Helper `_require_decision_scope()` — memakai helper kanonik `app/core/scope.assert_in_scope` (satu sumber aturan **dan** pesan dengan endpoint baca, bukan salinan baru) — dipanggil di **empat** endpoint jalur tulis: `propose`, `verify`, `approve`, `execute`. Penjaga "approval sudah tercatat" (409) dinaikkan dari cabang `ADMIN_TYPES` ke jalur umum. Matriks approval di `execute` kini **selalu** disaring `u.location_id == decision.target_location_id` (dulu hanya untuk tipe administratif). |
| `backend/tests/test_actions_scope_operasional.py` | **BARU** — 8 tes: 4 tes negatif lintas-SPPG (propose/verify/approve/execute → 403), 1 tes matriks hanya menghitung approval dari lokasi target (409), 1 tes duplikat approval (409), 1 kontrol positif (200), 1 tes yang memaku batas kebijakan kedaluwarsa. |
| `backend/tests/test_actions.py`, `test_action_boundary_e2e.py`, `test_s4_verifier_independence.py` | Fixture approver kedua dipindah `Bogor` → `Jakarta` (3 tempat) + komentar merujuk Ruling §3. Tes-tes itu menguji *dua peran* dan *integritas jejak audit*, bukan cakupan; sebelum perubahan ini lokasi approver memang tidak berpengaruh, sehingga fixture lama lolos apa adanya. |

**Bukti RED (sebelum perbaikan).** Penjaga dimatikan sementara, lalu `tests/test_actions_scope_operasional.py` dijalankan: **4 gagal** — dan yang paling telak, kepala SPPG **Medan** menerima **200** saat **mengeksekusi** keputusan milik **Jakarta** (PO mock ikut tercipta). Penjaga dinyalakan kembali → hijau.

**Bukti GREEN.**

- `pytest tests/test_actions_scope_operasional.py test_actions.py test_action_boundary_e2e.py test_s4_verifier_independence.py test_scope_matrix.py test_scope_core.py test_s4_sec_guards.py test_approval_summary.py test_compliance.py test_s4_rulings_tdd.py -q` → **113 passed** (115 s).
- Suite backend penuh, dijalankan saat repo sepi (tidak ada pytest lain) → **930 passed, 3 skipped, 0 failed** (256 s).
- `ruff check app` bersih.
- Aplikasi yang sedang hidup: `/health` 200, `/decisions` 200, `/balance/map` 200, `/admin/users` sebagai kepala SPPG → 403 (RBAC utuh).

**Tidak merusak alur demo (diperiksa langsung di DB demo).**

- Kedua user demo (kepala + ahli gizi) ber-lokasi **Jakarta**, dan **seluruh** keputusan yang masih berjalan menargetkan **Jakarta**.
- **0 baris** approval lama yang approvernya berbeda lokasi dengan target → matriks ber-scope tidak memblokir apa pun yang sudah ada.

**Batas yang sengaja TIDAK diubah (Keputusan owner 1b).** Menyetujui keputusan **kedaluwarsa jenis biasa** tetap **diterima** (200); hanya `execute` yang menolak (409 `expired`). Penjaga kedaluwarsa karena itu tetap berada di cabang administratif seperti semula, dan dipaku oleh tes `test_approve_setelah_kedaluwarsa_tetap_diterima_keputusan_owner_1b` supaya perubahan cakupan tidak diam-diam mengubah kebijakan itu. (Temuan awal saya — menaikkan cek kedaluwarsa ke jalur umum — bertentangan dengan keputusan owner tersebut dan sudah dibatalkan; tes lama `test_approve_expired_ordinary_decision_accepted` gagal dan itulah yang mengoreksi saya.)

**Koreksi catatan lama di dokumen ini.**

- §8 "Probe endpoint mutasi sengaja dihindari" → **tidak berlaku lagi**: jalur tulis sekarang diprobe lewat tes (403 / 409 / 200) di DB demo.
- **W-4**: penyebab run-1 `2 failed / 885 passed` **bukan** flake waktu, melainkan berkas `frontend/tests/shipment-timeline.test.ts` disunting pukul 00:49:50 saat run dimulai 00:49:35 — artefak suntingan bersamaan. Determinisme suite frontend tetap perlu dibuktikan dengan satu run bersih, bukan dengan mengubah tes (kecuali setelah dibuktikan bergantung waktu).
- Catatan lingkungan: `ruff check app tests` masih menyisakan 1 `E501` di `tests/test_supplier_routes_api.py` — berkas itu sedang disunting sesi lain, jadi **tidak** disentuh dari sesi ini.

**Sisa urutan:** W-2 (nol terukur vs data hilang) → W-3 (papan status integrasi), dengan W-4 (bukti gerbang bersih) dijalankan bersama langkah berikutnya.

---

### W-2 · SELESAI — 2026-10-17 (TDD; RED dibuktikan lebih dulu)

**Masalah nyata yang terukur (bukan dugaan).** `/balance/map?commodity=telur` melaporkan **Bandung `surplus` 386,43 kg** dan **Cianjur `surplus` 1.457,37 kg**, padahal keduanya **tidak punya baris permintaan sama sekali** — permintaan diisi `0` oleh engine, lalu gap dihitung dari angka itu. Turunannya ikut salah: ringkasan "lokasi surplus", rencana alokasi (Bandung/Cianjur jadi pemasok), agregat kebutuhan-vs-kiriman pengawas, dan chip jaringan di top bar.

**Perubahan.**

| Lapisan | Berkas | Isi |
|---|---|---|
| Backend | `app/api/balance.py` | Helper `_asal_nilai()` / `_data_state()` / `_waktu()`; `/balance/map` **dan** `/balance/{lokasi}/{komoditas}` kini membawa `supply_state`, `demand_state`, `data_state` (`terukur` / `sebagian` / `tidak_ada_baris`) + `supply_recorded_at`/`demand_recorded_at` (asal nilai). **Angka tetap dikirim apa adanya** — aturan tampilan tidak berubah; `/balance/{}/{}` tetap 404 bila KEDUA baris tidak ada. |
| Frontend | `lib/overview-format.ts` | Tipe `DataState`, kolom baru pada `BalanceMapLocation`, helper `tanpaCatatan()` + `dataSourceNote()` (catatan asal nilai untuk rincian/tooltip). |
| Frontend | `lib/surplus.ts` | `surplusSummary()` hanya menghitung surplus bila **permintaannya terukur** (cermin: kekurangan bila pasokannya terukur), `balancedCount` tidak lagi menghitung lokasi tanpa data, dan tambah `unmeasuredCount`. `allocationPlan()` tidak memakai pemasok/tujuan yang sisinya tidak tercatat. Tanpa penanda (respons lama) → diperlakukan seperti sebelumnya, jadi perilaku lama tidak berubah. |
| Frontend | `components/SupplyMap.tsx` | Popup, daftar baris peta, dan label aksesibilitas menampilkan "… tanpa catatan" hanya untuk lokasi yang datanya tidak lengkap. |
| Frontend | `components/SurplusBoard.tsx` | Pil header "{n} lokasi tanpa catatan lengkap" supaya lokasi yang keluar dari hitungan tetap **dikatakan**, bukan hilang diam-diam. |
| Frontend | `lib/food-safety.ts` | Agregat pengawas hanya menjumlah lokasi yang kedua sisinya tercatat; lokasi sendiri yang tidak lengkap → nilainya `null` (aturan repo "null → —"), bukan angka karangan. |
| Frontend | `lib/topbar.ts` | Chip jaringan tidak mengklaim "shortage" dari pasokan yang tak tercatat. |
| Frontend | `app/globals.css` | Gaya `.map-row-note` dan `.map-popup-note` (hanya muncul di keadaan yang tidak lengkap). |
| Tes baru | `tests/test_balance_data_state.py` (5), `tests/balance-data-state.test.ts` (12), `tests/balance-data-state-render.test.tsx` (3) | Memaku tiga kasus yang diminta: baris ada bernilai 0 → tetap `0 kg` **dan** `terukur`; tidak ada baris → tetap `0 kg` di tampilan tetapi `tidak_ada_baris`; serta kontrak deret demo (cakupan `terukur` per komoditas tidak boleh menyusut → gate MERAH bila data hilang). |

**Bukti RED.** Backend: 5 gagal (`KeyError` penanda baru) sebelum implementasi. Frontend: 6 gagal dari 8 sebelum implementasi, lalu 12 hijau.

**Bukti GREEN (gerbang).** Backend penuh: **935 passed, 3 skipped, 0 failed** (473 s; 930 + 5 tes baru). Frontend penuh: **90 berkas / 1080 tes passed, 0 gagal**. `npx tsc --noEmit` bersih, `next lint` bersih, `ruff check app` bersih.

**Bukti UI hidup** (dev server :3010, login BGN Monitor):
- Daftar peta menampilkan "permintaan tanpa catatan" **tepat** pada Bandung & Cianjur; kesepuluh lokasi tetap tampil dengan angka seperti semula ("Kebutuhan: 0 kg" tetap `0 kg`).
- Halaman Keamanan Pangan: "Kebutuhan 3.438 kg · tersedia 3.176 kg → kurang 801 kg" — ketiganya persis jumlah dari **8 lokasi yang kedua sisinya tercatat**; sebelum perbaikan, "tersedia" ikut memuat 1.843,8 kg pasokan Bandung+Cianjur yang tidak berdasar.

**Catatan lingkungan (bukan pekerjaan ini).** Selama gerbang berjalan, satu tes frontend (`tests/sidebar-wiring.test.tsx`, asersi atas `components/DecisionEvidence.tsx`) gagal karena sesi lain sedang meredesain berkas itu (mtime 06:58). Setelah suntingan mereka selesai, suite penuh hijau 1080/1080 — jadi kegagalan itu artefak suntingan bersamaan, bukan regresi.

**Sisa urutan:** W-3 (papan status integrasi) — satu-satunya item yang menambah nilai penjurian langsung.

---

### W-3 · SELESAI — 2026-10-17 (TDD; RED lewat tes kontrak)

**Masalah.** Bukti status integrasi tersebar di dokumen (fase-12, agentcore-deploy, README-deploy) dan **tidak satu pun berkas frontend menyebut AgentCore**. Pertanyaan juri "ini jalan di AWS?" hanya bisa dijawab dengan menceritakan dokumen.

**Perubahan.**

| Lapisan | Berkas | Isi |
|---|---|---|
| Backend | `app/api/integrations.py` (baru) + `app/main.py` | `GET /integrations/status` read-only (JWT). Tujuh komponen, tiap komponen membawa `category` + `category_label` + `evidence` (apa yang diperiksa) + `artifact` (sumber) + `note` + `checked_at`. Kategori dari daftar tertutup: `configured`, `provisioned`, `contract_tested`, `artifacts_ready`, `fail_closed`, `unavailable`, `not_started`. **Endpoint tidak menjalankan probe jaringan** → `probes_run` selalu 0 dan tidak ada komponen berlabel `operational`/`probe_passed`. |
| Frontend | `lib/api.ts`, `lib/query.ts`, `lib/hooks/useIntegrationStatus.ts`, `components/IntegrationStatusPanel.tsx` | Klien + hook React Query (tanpa polling, tanpa retry: gagal = dikatakan) + panel kartu. Hijau **hanya** untuk `probe_passed`; `unavailable`/`not_started` merah; `fail_closed` kuning. Teks kategori selalu ada, jadi warna bukan satu-satunya pembeda. |
| Frontend | `app/page.tsx` | Panel dipasang di tab **Agent Log** (tab yang sudah ada, bukan modul baru) dan terlihat semua peran demo. |
| Frontend | `next.config.js` | Akar `integrations` ditambahkan ke `API_ROOTS` (tanpa ini panel menerima 404 HTML dari router Next). Kontainer frontend **di-restart** karena rewrites dibaca saat start. |
| Frontend | `app/globals.css` | Gaya `.integration-*` memakai token yang ada. |
| Tes baru | `backend/tests/test_integrations_status.py` (7), `frontend/tests/integration-status.test.tsx` (7) | 401 tanpa token; kelengkapan kolom; kategori ⊆ daftar; **tidak ada label hijau tanpa probe**; kategori mengikuti env (ARN kosong → `artifacts_ready`, ARN terisi → `configured`; Memory id kosong → `unavailable`); panel tidak menampilkan baris hijau saat `probes_run = 0`. |

**Bukti RED.** Tes backend dijalankan sebelum endpoint ada → gagal (404); tes panel dijalankan sebelum komponen ada → 6 dari 7 gagal.

**Bukti payload hidup** (`GET /integrations/status`, token BGN Monitor) — `probes_run = 0`, 7 komponen:

| Komponen | Kategori | Bukti |
|---|---|---|
| SAP AI Core (SAP-RPT-1.6) | `contract_tested` | env `SAP_AI_CORE_CLIENT_ID` terisi |
| Mock SAP | `contract_tested` | layanan mock-sap + tes kontrak PO |
| AgentCore Runtime (Strands) | `artifacts_ready` | env `AGENTCORE_RUNTIME_ARN` **kosong**; artefak `agent/` siap |
| AgentCore Gateway | `not_started` | env `AGENTCORE_GATEWAY_URL` kosong |
| AgentCore Memory | `provisioned` | env `AGENTCORE_MEMORY_ID` terisi (adapter aplikasi belum memakainya) |
| Observability | `fail_closed` | galat eksplisit, bukan laporan palsu |
| AWS for SAP MCP | `not_started` | tertahan akses tenant S/4HANA |

`GET /openapi.json` → **55 path** (sebelumnya 54); proxy frontend `/integrations/status` tanpa token → **401** (bukan 404), artinya rewrite + auth benar.

**Bukti UI hidup** (:3010, BGN Monitor → tab Agent Log): panel "Bukti integrasi per komponen" menampilkan 7 baris dengan badge kategori ("kontrak diuji", "artefak siap", "tersedia (provisioned)", "gagal-tertutup", "belum dimulai"), **nol badge hijau**, dan kalimat "Tidak ada probe jaringan dijalankan: status di bawah menyebut jenis bukti (env/artefak/kontrak), bukan klaim operasional."

**Yang sengaja TIDAK diklaim.** Panel tidak menyebut AgentCore Runtime "jalan": ARN masih kosong, dan deploy tertahan izin IAM milik pemilik akun. Memory disebut `provisioned`, bukan "dipakai". SAP AI Core disebut "kontrak diuji", bukan "live" — label `live`/`operational` hanya boleh muncul kalau ada probe nyata, dan itu tidak dilakukan endpoint ini.

---

### W-4 · SELESAI — 2026-10-17 (kesimpulan berbeda dari dugaan awal)

**Hasil investigasi determinisme.** Dugaan di §4 ("tes tidak deterministik karena waktu") **tidak terbukti**:

- `tests/shipment-timeline.test.ts` memakai stempel waktu ISO **tetap**; `grep -c "Date.now\|new Date("` → **0**.
- `lib/shipment-timeline.ts` murni — hanya mengurutkan `Date.parse()` data server, tidak membaca jam sistem.
- Run-1 yang merah terjadi karena berkas tesnya **disunting 00:49:50 saat run dimulai 00:49:35**.

Karena itu **tidak ada kode tes yang diubah** untuk "menstabilkan" sesuatu yang tidak rapuh — mengubah tes yang benar hanya menyembunyikan penyebabnya.

**Yang dikerjakan sebagai gantinya.** Bukti gerbang bersih disimpan bertanggal di **`docs/verification/gerbang-2026-10-17.md`**, lengkap dengan: angka tiap gerbang (backend, frontend, tsc, lint, ruff, openapi), log run yang **tercemar** (19/144/96 gagal) beserta bukti bahwa semuanya polusi run-ganda (berkas yang sama lolos saat berdiri sendiri), aritmetika silang `923+19 = 942 = 935+7`, dan daftar hal yang **tidak** diverifikasi (`next build`, deploy AgentCore, probe SAP AI Core).

**Batas yang harus disebut saat memakai dokumen itu:** gerbang backend untuk keadaan setelah W-3 belum terekam sebagai satu run penuh 0-gagal, karena sesi lain menjalankan pytest berulang kali di DB demo yang sama. Jangan mengutip "semua lulus" untuk backend tanpa menyebut kondisi itu; yang sah dikutip adalah angka run bersih 935/0 (W-1+W-2) dan 12/12 tes W-2+W-3 saat berdiri sendiri.

---

### Ringkasan seluruh rencana

| Item | Status | Bukti utama |
|---|---|---|
| W-1 · Scope lokasi di jalur tulis | **selesai** | 8 tes baru; RED: Medan→Jakarta 200 → GREEN: 403; suite 930/0 |
| W-2 · Nol terukur vs data hilang | **selesai** | penanda asal nilai; Bandung/Cianjur tak lagi "surplus"; 935/0 + 1127/0 |
| W-3 · Papan status integrasi | **selesai** | `GET /integrations/status` (7 komponen, `probes_run=0`) + panel Agent Log; 1127/0 |
| W-4 · Determinisme + bukti gerbang | **selesai** | `gerbang-2026-10-17.md`; klaim flaky dibatalkan lewat bukti |
| §5 · Head-only vs kebijakan repo | **menunggu keputusan pemilik** | rekomendasi: pertahankan kebijakan repo (jangan klaim "hanya Kepala SPPG") |
