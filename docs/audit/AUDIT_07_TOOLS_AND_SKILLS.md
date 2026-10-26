# AUDIT_07 — Tools, Skills, dan Keterbatasannya

Aturan yang dipegang: hanya tool yang benar-benar dipakai dicatat sebagai bukti; tool yang tidak tersedia dicatat sebagai keterbatasan, bukan dikarang hasilnya. Tidak ada instalasi massal — hanya yang relevan dan sudah tersedia.

## 7.1 Skill (Hermes) yang digunakan

| Skill | Fungsi dalam audit | Dipakai untuk |
|---|---|---|
| `project-audit` | Kerangka audit pra-deploy: dokumen temuan, evidence level, aturan "jangan memperbaiki di tengah audit" | Struktur 11 laporan, pemisahan temuan vs perbaikan, aturan kejujuran |
| `fullstack-verification` | Gate empat lapis (process → be → db → fe → compare) + skrip `verify_stack.py` | Menjalankan `verify/*.spec.json`, membaca kegagalan per lapis |
| `fullstack-verification` (referensi) | `references/mealchain-guardian-suite.md`, `mealchain-guardian-tabs.md` | Mengetahui spec mana yang harus dijalankan dan invarian yang sudah dikodekan |
| `mealchain-guardian-dev-loop` (referensi baru) | `references/kpi-filters-map-journey-bell.md` | Menghindari salah baca `/balance/map` vs `/supplier-routes`, filter `demo_case` KPI |

## 7.2 Tool yang benar-benar dijalankan

| Tool | Versi | Perintah | Hasil |
|---|---|---|---|
| ruff | 0.6.9 | `ruff check .` (container backend) | Awal: 1 pelanggaran `I001` di `tests/test_gate_anchor_canonical.py` → diperbaiki (`--fix`), sesudahnya **All checks passed** |
| pytest | 8.3.3 | `pytest tests/ -q` via `docker run` + bind mount | lihat AUDIT_10 |
| alembic | 1.13.2 | `alembic current`, `alembic check`, `alembic upgrade head` di DB kosong | Drift 22 indeks (BUG-001) → diperbaiki → bersih; migrasi dari nol 24 tabel |
| vitest | 2.1.9 | `npx vitest run` (frontend) | 166 berkas / 1793 tes PASS |
| TypeScript (`tsc`) | 5.6.2 | `npx tsc --noEmit` | exit 0 |
| ESLint (`next lint`) | bawaan Next 14.2.14 | `npm run lint` | "No ESLint warnings or errors" |
| npm audit | npm bawaan Node 25.9.0 | `npm audit --omit=dev [--json]` | 3 kerentanan: `next` critical, `maplibre-gl` critical, `postcss` high |
| psql | 16.15 | query invarian & lineage | semua invarian 0 pelanggaran |
| Playwright (venv Hermes) | terpasang | via `verify_stack.py` (`ui_tabs.py`) | matriks tab per peran |
| verify_stack.py | skrip skill | 4 spec (stack, roles, invariants, tabs) | 76 pemeriksaan be/db PASS; detail AUDIT_10 |
| git | sistem | `git log/status/ls-files` | HEAD & 104 entri kotor dicatat |

## 7.3 Tool yang TIDAK tersedia (keterbatasan, bukan hasil)

| Kebutuhan | Tool | Status | Dampak pada audit |
|---|---|---|---|
| SAST Python | `bandit` | tidak terpasang | Analisis keamanan statis hanya lewat ruff (rules `E,F,I,N,W` — **tidak** ada `S`/bandit) |
| SAST multi-bahasa | `semgrep` | tidak terpasang | Tidak ada pemindaian pola injeksi/XSS otomatis |
| Vulnerability Python | `pip-audit` | tidak terpasang | Kerentanan dependensi backend **tidak** dipindai |
| Container scan | `trivy` | tidak terpasang | Image tidak dipindai CVE |
| Performance/load | `k6`, `locust` | tidak terpasang | Hanya latency per request dari gate (ms), tanpa uji beban |
| SQL lint | `sqlfluff` | tidak terpasang | Query hanya diperiksa secara manual + invarian |
| Markdown lint | `markdownlint-cli2` | tidak terpasang | Format laporan tidak divalidasi tool |
| Accessibility | `axe-core` | tidak terpasang | Pemeriksaan a11y terbatas pada inspeksi DOM manual |

Keputusan: tool di atas **tidak dipasang** karena (a) tidak ada di environment, (b) instalasi menambah permukaan perubahan di luar cakupan audit demo, dan (c) beberapa memerlukan kredensial/izin (image registry, layanan jaringan). Semua area itu diberi status `BLOCKED` di AUDIT_08/AUDIT_10, bukan `PASS`.

## 7.4 Tool yang sengaja tidak dipakai

| Tool | Alasan |
|---|---|
| `decisions.spec.json` (write-flow gate) | Membutuhkan stack terisolasi (`verify/docker-compose.mutations.yml`) dengan volume terpisah; audit ini memilih tidak menyalakan stack kedua. Jalur tulis tetap diuji lewat probe API + DB pada DB demo dengan akun sementara yang dihapus (lihat AUDIT_06 §6.5) |
| `stack.coldstart.spec.json` | Melakukan `docker compose down` pada stack demo; berisiko menghentikan lingkungan yang sedang dipakai. Cold start sudah tercatat dari riwayat `verify/verify-out-coldstart/` dan tidak diulang |
| Uji beban / fuzzing | Tidak ada izin eksplisit dan tidak ada target SLA |

## 7.5 Catatan metode

- Setiap angka yang dikutip di laporan ini berasal dari keluaran sesi ini; tidak ada yang disalin dari laporan lama tanpa pengukuran ulang.
- Kegagalan gate pertama (2 spec merah) ditelusuri ke **ekspektasi spec yang basi** (`030_approval_four_eyes_unique` vs head `033_indeks_fk_hilang`), bukan ke produk; spec diperbarui lalu dijalankan ulang → PASS. Perubahan spec dicatat sebagai bagian perbaikan (AUDIT_09).
