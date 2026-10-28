# Fase 12 MG — dokumentasi & geladi dua jalur demo (bukti)

Tanggal: 2026-10-27 · Repo: `E:\hackathon\HackathonAWS\mealchain-guardian`
Rencana: `MG/prompts-fase.md` Fase 12 · Definisi butir: `MG/phase-12-docs-rehearsal.md`

> Catatan nama: `docs/verification/fase-12.md` yang lama **bukan** fase ini — itu fase peta/ETA
> dari track 2026-10-16. Berkas ini khusus Fase 12 rencana MG.

Ringkasan: **6 dari 8 butir terpenuhi dengan bukti eksekusi; 2 butir `OPEN`** (pytest penuh,
konteks sesi Joule) dan 1 sub-butir persiapan (push jembatan CF) menunggu izin pemilik.

## Lingkungan geladi

| Hal | Nilai |
|---|---|
| DB geladi | `mealchain_r12` (klon terpisah, head `043_least_privilege_app`) |
| Stack | `mcg-f12` — backend `127.0.0.1:18100`, frontend `127.0.0.1:13110`, mock-sap, postgres |
| Backend operasional | `mcg-f12-ops` di `127.0.0.1:18110`, `DEMO_MODE=false`, DB yang sama |
| Jembatan Joule | lokal `127.0.0.1:18091` → backend `18100` (akun baca `bgn.monitor@demo.local`) |
| Driver geladi | `_qa/f12/rehearsal_f12.py` (replay / realtime / operasional / kpi) |
| Driver Joule | `_qa/f12/joule_f12.py` (lima skill + penolakan approval) |

## Hasil per butir

| Butir | Status | Bukti |
|---|---|---|
| 1 Persiapan | sebagian | `_qa/f12/clone-r12.txt`; stack `mcg-f12` sehat; `cf push` **belum** |
| 2 Replay | **22/22 lulus** | `_qa/f12/out/replay.json` |
| 3 Realtime | **22/22 lulus** | `_qa/f12/out/realtime.json` |
| 4 Operasional | **6/6 lulus** | `_qa/f12/out/operasional.json` |
| 5 Joule | **10/10 per mode, konteks sesi ikut dicetak** | `_qa/f12/out/joule-replay.json`, `joule-realtime.json` |
| 6 Gerbang negatif | **N1–N5 lulus** | di kedua JSON rehearsal |
| 7 Gate statis & runtime | statis bersih, **pytest 50 gagal** | `_qa/f12/gate-statis-27okt.txt`, `_qa/gerbang-db-terpisah-2026-10-27.txt` |
| 8 Keputusan akhir | tercatat | `MG/phase-12-docs-rehearsal.md` §Keputusan akhir |

## Angka kunci

- Replay dan realtime menghasilkan PO yang **sama**: `MC-8167887C3B7A`, keputusan
  `8167887c-3b7a-539a-8a4a-4c1e51856f44` — business-logic tidak bergantung mode.
- Operasional: `POST /demo/seed`, `POST /demo/agent/run`, `GET /demo/session`, `GET /demo/data-status`
  semuanya **404**; baris DB identik sebelum/sesudah (60 / 133 / 9 / 20).
- Joule: seluruh nomor PO yang disebut ada di `GET /sap/purchase-orders`; permintaan approval
  ditolak dan status keputusan tidak berubah; jawaban KPI menyebut mode + jangkar + id sesi
  aktif (`Sesi demo aktif: mode replay, jangkar 8 Okt 2026 19:00 WIB, sesi 44088be6`), cocok
  dengan `GET /demo/session` backend.
- Gate statis: ruff `All checks passed`; `alembic check` tanpa operasi baru; drift OpenAPI
  `1 passed`; tes jembatan `192 passed, 14 skipped`; `tsc --noEmit` bersih; `next lint` bersih; vitest `185 berkas / 2027 tes lulus`
  (satu pelanggaran `react/no-unescaped-entities` diperbaiki pada fase ini).

## Kegagalan yang jujur harus disebut

Pytest penuh pada DB gate terpisah: **50 gagal / 2077 lulus / 31 skip**. 40 di antaranya satu
sebab: batch demo berjangkar REF 8 Okt menjadi basi pada jam dinding 27 Okt, dan `fuse_evidence`
menilai satu lokasi sebagai satu grup sehingga satu batch tua menahan seluruh grup
(`temperature_evidence_incomplete`, `freshness_fail`) → `tidak ada kandidat eligible untuk Event 1
(telur -> Jakarta)`. Rincian + dua opsi perbaikan ada di `MG/phase-12-docs-rehearsal.md`
§Analisis kegagalan suite. Butir 7 karena itu tetap `OPEN`.

## Berkas dokumen yang diselaraskan pada fase ini

- `docs/DemoRunbook.md` (baru) — pemilihan replay/realtime, urutan klik, verifikasi `on_hold`,
  peran approval, arti simulasi suhu, cara mengulang tanpa merusak sesi.
- `docs/Architecture.md`, `docs/Schema.md`, `docs/Skill.md`, `docs/PRD.md` — dicek ulang terhadap
  kode (head migrasi, 81 path OpenAPI, mode waktu, batas MVP bahan-sampai-diterima).
- `sap-joule/docs/peta-skill-joule.md` §7 dan `sap-joule/docs/runbook-cf-joule.md` §Status terukur —
  status as-built + batas CF (`backend.reachable=false`).
- `docs/verification/AGENTCORE_STATUS.md`, `TODO.md`, `Roadmap.md`,
  `memory/global/{decisions,active_context,architecture,project_memory}.md`.
