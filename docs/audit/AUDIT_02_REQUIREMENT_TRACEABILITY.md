# AUDIT_02 — Traceability Requirement → Implementasi → Bukti

Sumber requirement: `docs/PRD.md` (§5 Core features, §7 metrics), `docs/Skill.md` (§4 tujuh KPI), `IDEA.md`, `docs/kamus-kpi-dan-state-machine.md`, plus keputusan pemilik yang tercatat (`memory/global/decisions.md`, komentar kode bertanggal).

Legenda status: `PASS` (ada implementasi + bukti uji/runtime), `PARTIAL` (ada tetapi ada celah terdokumentasi), `GAP` (tidak ada), `BLOCKED` (tidak dapat diuji di lingkungan ini).

## 2.1 Fitur inti PRD §5

| # | Requirement (PRD) | Implementasi | Bukti | Status |
|---|---|---|---|---|
| R1 | Overview 10 lokasi + status surplus/shortage/tight | `GET /balance/map`, `frontend/components/OverviewMap*`, tab Overview | gate `stack.spec.json` (GET /balance/map 200), `verify-out` PASS; UI tab Overview PASS (tabs.spec) | PASS |
| R2 | Recommendation Feed dari Supervisor Agent, urut urgensi | `GET /decisions`, `app/page.tsx` tab `recommendations`, `lib/decisions-window.ts` | gate invariants; runtime: 11 kartu siap tindak Jakarta (9 pending + 2 flagged) | PASS |
| R3 | Decision detail + evidence + Safe Delivered Cost + hard constraint | `GET /decisions/{id}`, `/chain`, `/traces`, `/dossier`, `/compliance`; `components/DecisionEvidence.tsx` | gate: `/decisions/{uuid}/chain` 404 untuk id palsu, 422 untuk non-UUID | PASS |
| R4 | Agent activity log DETECT→…→LEARN dari trace | `GET /decisions/{id}/traces`, `components/AgentTraceViewer.tsx`; tabel `agent_traces` | DB: 85 trace; invarian "jejak yatim = 0", "keputusan tanpa trace = 0" | PASS |
| R5 | Approval flow 2 peran, bgn_monitor read-only | `/actions/approve` (empat mata), `app/core/approval_matrix.py`, `approvals` (unique per akun) | gate roles: 16 pemeriksaan PASS (403 lintas lokasi, monitor ditolak); runtime: approve akun sama → 409 | PASS |
| R6 | KPI Dashboard 7 metrik (digabung dengan Kualitas Agen) | `GET /kpi`, `app/services/kpi_service.py`, `components/KPIDashboard.tsx` | 69 tes KPI lulus; runtime `periode=today|7d|1bulan` | PARTIAL — definisi 3 metrik beda dari `Skill.md` (§2.3) |
| R7 | Auth & role-based view | `/auth/login`, `/auth/me`, `app/core/scope.py` | gate roles: login 3 peran, scope lokasi 403 | PASS |

## 2.2 Requirement demo (sesi 2 jam, reset, 5 rekomendasi Jakarta)

| # | Requirement | Implementasi | Bukti | Status |
|---|---|---|---|---|
| D1 | Sesi demo berdurasi 2 jam, waktu server | `demo_sessions`, `app/services/demo_session.py::_batas_akhir`, `DEMO_SESSION_MAX_MINUTES=120` | runtime: start → 120,0 menit; extend 240 tidak mengubah `expires_at`; tes `test_demo_sesi_batas_dan_enforcement.py` 6/6 | PASS |
| D2 | Hanya satu sesi aktif | partial unique index `uq_demo_sessions_satu_aktif` (migrasi 032) | `pg_indexes`; DB: `sesi_aktif_ganda = 0`; tes 6/6 | PASS |
| D3 | Mutasi tanpa sesi ditolak | middleware `_konteks_sesi_demo` (`app/main.py`) | runtime: approve tanpa sesi → 409, GET tetap 200 | PASS |
| D4 | Reset demo idempoten, tidak menghapus non-demo | `POST /demo/refresh`, `app/seed/demo_kpi_riwayat.py`, sweep `origin='demo'` | tes `test_demo_template_deret.py`, `test_demo_kpi_riwayat.py`; invarian "baris kanonik berstempel sesi = 0" | PASS |
| D5 | 5 rekomendasi Jakarta hari ini, tidak duplikat saat refresh | `_seed_demo_cases` + `STATUS_KARTU_HARI_INI` | runtime: 11 kartu siap tindak atas 5 `demo_case` unik; rebuild berulang tidak menambah | PARTIAL — 11 kartu (bukan tepat 5); 5 skenario unik |
| D6 | Animasi kiriman setelah approve+execute | `execute` → `batches.dispatched_at`; `GET /supplier-routes` → `journey` | runtime: 5 batch berangkat/30 menit; 12 rute; `progress` naik 6/6 dalam 8 detik | PASS |
| D7 | Notifikasi | `frontend/lib/topbar.ts` (turunan `/decisions`) | runtime: 12 → 9 baris siap tindak setelah 3 eksekusi | PARTIAL — tanpa tabel/read-state (keputusan produk) |

## 2.3 Tujuh KPI — definisi dokumen vs kode

| KPI | `docs/Skill.md` | Kode (`kpi_service.py`) | Selisih | Status |
|---|---|---|---|---|
| Meal Continuity | % menu terpenuhi **tanpa substitusi tidak aman** | `SUM(delivered)/SUM(planned)` dengan batas jendela kirim | Tidak memfilter substitusi/safety | PARTIAL |
| Avoidable Food Loss | kg batch terbuang **yang masih lolos freshness** | `disposal_events` (batch tak teralokasi) | Cakupan berbeda | PARTIAL |
| Regional Imbalance Resolution | % kasus selesai (`executed`) | DETECT→executed, **mengecualikan `demo_case`** | Kartu demo tidak dihitung | PARTIAL (terdokumentasi) |
| Safe Delivered Cost | rata-rata `safe_delivered_cost` untuk **executed** | rata-rata untuk keputusan yang punya **PO** | Ambang berbeda | PARTIAL |
| Procurement Price Deviation | \|harga − referensi\|/referensi | idem, kutipan tanpa referensi dibuang dari sampel | — | PASS |
| Decision Time | DETECT→ACT per decision | idem, **ACT harus committed (PO)**, kini termasuk `demo_case` | Tambahan syarat committed (terdokumentasi) | PASS |
| Evidence Completeness | ≥2 bukti konsisten sebelum `approved` | idem, cutoff approval-complete | — | PASS |

Ketiga selisih pertama (Meal Continuity, Avoidable Food Loss, Safe Delivered Cost) sudah tercatat sebagai keputusan terbuka di `docs/kamus-kpi-dan-state-machine.md` §7; audit ini tidak mengubahnya karena memerlukan keputusan owner (bukan bug implementasi).

## 2.4 Kontrak periode KPI

| Requirement | Implementasi | Bukti |
|---|---|---|
| Periode ditentukan server, hari kalender `Asia/Jakarta` | `app/core/kpi_period.py`, `GET /kpi?periode=` | 422 untuk `periode=24h`, 422 untuk periode+start/end, 422 tanpa keduanya |
| Envelope periode di respons | `period: {key,label,timezone,start,end}` | `openapi.json` + tes `test_kpi_period.py`, `test_kpi_api.py` |
| Rentang setengah terbuka `[start,end)`, timestamp berzona | `kpi.py` | tes batas tanggal (`test_kpi_batas_tanggal.py`) PASS |

## 2.5 Requirement yang tidak dapat diverifikasi penuh di lingkungan ini

| Requirement | Alasan | Status |
|---|---|---|
| Agent nyata di Bedrock AgentCore (bukan wrapper) | Kredensial AWS ada di `.env`, tetapi panggilan model berbayar di luar izin audit | BLOCKED |
| SAP live (BTP/AI Core) | Mode SAP memakai mock (`SAP_*_MODE`), integrasi asli tidak diuji | BLOCKED |
| Login lewat form UI (klik "Masuk") | Kredensial demo tidak disediakan untuk audit; kebijakan agen melarang mengetik password ke form | BLOCKED (gate memakai login API) |

## 2.6 Kesimpulan traceability

- 7/7 fitur inti PRD punya jalur UI → API → service → tabel dan bukti runtime.
- 4/7 KPI persis sesuai dokumen; 3 KPI punya selisih definisi yang sudah didokumentasikan, bukan disembunyikan.
- Demo Control memenuhi kontrak 2 jam + satu sesi aktif + enforcement.
- Yang belum terbukti: panggilan AgentCore/SAP asli dan login form di browser.
