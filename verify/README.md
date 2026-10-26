# verify/ — gate verifikasi full-stack

Kumpulan spec + skrip untuk membuktikan aplikasi benar-benar berjalan dari proses → backend → DB →
frontend → lintas lapis, dengan exit code (0 lulus, 1 gagal). Dijalankan dengan skill
`fullstack-verification` (`scripts/verify_stack.py`), bukan alat terpisah.

## Spec

| berkas | yang diperiksa | cara jalan |
|---|---|---|
| `stack.coldstart.spec.json` | cold start: `compose down` + `up -d --wait`, lalu 4 service, health, log bersih, RBAC, FE login | stack mati dulu |
| `stack.spec.json` | gate utama: 4 container (awal+akhir), health, login/RBAC, 10 endpoint, alembic + hitungan DB, FE login, `compare` API vs DB | stack hidup (`external`) |
| `roles.spec.json` | matriks 3 peran: cakupan lokasi, 403 di luar cakupan, tab khusus peran | stack hidup |
| `tabs.spec.json` | 29 tab sidebar untuk 3 peran: `aria-current`, isi halaman, teks khas, tanpa console/4xx baru | stack hidup |
| `decisions.spec.json` | alur tulis `propose → verify → approve ×2 → execute` di stack terisolasi + bukti tulisan di DB | `docker-compose.mutations.yml` (project `mcg-mut`) |
| `stack.forensics.spec.json` | forensik container: state awal/akhir, `docker events`, exit code != 0, `health=unhealthy` | butuh kontainer bernama |

`docker-compose.mutations.yml` = stack teruji terisolasi (project `mcg-mut`, volume sendiri, API
`127.0.0.1:18000`, FE `127.0.0.1:13010`, CORS-nya sendiri) supaya uji tulis tidak menyentuh DB demo.
Setelah selesai: `docker compose -p mcg-mut -f verify/docker-compose.mutations.yml down -v`.

## Menjalankan

```bash
PY="C:/Users/User/AppData/Local/hermes/venvs/webapp-testing/Scripts/python.exe"
SS="C:/Users/User/AppData/Local/hermes/skills/software-development/fullstack-verification/scripts"

# gate utama + matriks tab pada stack yang sedang hidup
python "$SS/verify_stack.py" verify/stack.spec.json verify/tabs.spec.json --ui-python "$PY"

# cold start (matikan stack dulu), lalu role matrix
python "$SS/verify_stack.py" verify/stack.coldstart.spec.json --ui-python "$PY"

# alur tulis pada stack terisolasi
docker compose -p mcg-mut -f verify/docker-compose.mutations.yml up -d --wait
python "$SS/verify_stack.py" verify/decisions.spec.json --ui-python "$PY"
docker compose -p mcg-mut -f verify/docker-compose.mutations.yml down -v
```

`--ui-url http://127.0.0.1:13010/` mengarahkan satu spec ke stack uji (bawaan: FE demo `3010`).
Artefak (laporan `.md/.json`, screenshot, log) mendarat di `verify-out*/` dan **tidak di-commit**
(lihat `verify/.gitignore`).

## Skrip investigasi (sekali pakai, disimpan sebagai bukti)

- `frontend-exit0-experiments.sh` — mengukur arti exit code: SIGTERM → 0, SIGKILL → 137,
  `docker stop` tidak di-restart, `kill -TERM 1` di-restart.
- `frontend-exit0-stress.sh` — 30× (GET + touch berkas) dan `npm run build` di dalam kontainer:
  membuktikan `next dev` tidak keluar sendiri.
- `frontend-exit0-repro.sh` — urutan `compose up --force-recreate`: `kill → stop → die exit=0 →
  destroy → start`.
- `fe-healthcheck-detail.sh` — healthcheck: `unhealthy` saat `next-server` di-SIGSTOP, pulih
  setelah SIGCONT, `docker stop` → `exit=0 health=unhealthy`.
- `fe-healthcheck-red-test.sh` — gate menangkap `status=running health=unhealthy` di stack uji.

## Angka terakhir (19 Okt 2026)

- `stack.spec.json`: 41/41 PASS (termasuk 8 cek kontainer + events).
- `tabs.spec.json`: 3 flow PASS (29 tab, 3 peran), sama di stack demo dan stack uji.
- `decisions.spec.json`: 32 PASS / 1 SKIP (skip = spec ini tidak punya bagian `fe`/`db` terpisah; alur tulis diperiksa lewat HTTP + SQL langkah), exit 0.
- `roles.spec.json`: 28/28 PASS. `stack.coldstart.spec.json`: 25/25 PASS.
- Suite cold start + gate + roles: 3 spec, 3 pass, 0 fail.

Catatan: angka ini bisa berubah bila data demo berubah (ledger bertambah, user dari pytest).
Gunakan `compare`/predikat, bukan total mentah.

## Artefak laporan `verify-out*/` — dibuat ulang, tidak disimpan

Folder `verify-out`, `verify-out-coldstart`, `verify-out-decisions`, `verify-out-forensics`,
`verify-out-invariants`, `verify-out-roles`, dan `verify-out-tabs` adalah **keluaran** gate (report,
log, dump JSON), bukan sumber. Semuanya di-ignore git (`verify/.gitignore: verify-out*/`) dan sudah
dihapus dari working tree pada 26 Okt 2026 supaya repo tidak menumpuk 96 berkas (±15 MB) laporan lama.

Membuatnya lagi: jalankan spec yang bersangkutan dengan
`scripts/verify_stack.py` (skill `fullstack-verification`), mis.
`python …/verify_stack.py verify/invariants.spec.json`. Path `artifact_dir` tiap spec menentukan
folder keluarannya, jadi laporan baru akan muncul dengan nama yang sama seperti yang dikutip di
`docs/audit/AUDIT_10_E2E_TEST_RESULTS.md`.

Arsip satu kali dari kondisi sebelum penghapusan (bila perlu membandingkan angka lama):
`C:\Users\User\AppData\Local\hermes\cache\scratch\verify-out-backup-20261026.tar.gz`.
