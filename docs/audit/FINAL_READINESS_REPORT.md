# LAPORAN KESIAPAN AKHIR — MealChain Guardian

| Field | Nilai |
|---|---|
| Tanggal | 26 Oktober 2026 (WIB) |
| Repo / HEAD | `mealchain-guardian` @ `5885810` (branch `feature/db-modes-demo-coverage`), + perbaikan belum di-commit hari ini |
| Lingkup | Kesiapan demo (panggung), staging, dan produksi |
| Bukti acuan | `docs/audit/MASTER_AUDIT_SUMMARY.md`, 7 dokumen audit, rebuild + gate 26 Okt 2026 22:1x WIB |
| Sifat | Verdict terpisah per tingkat. Yang belum diperbaiki **ditulis belum**. |

---

## 1. Verdict

| Tingkat | Verdict | Alasan ringkas |
|---|---|---|
| **DEMO_READY** (panggung juri, satu sesi 120 menit, operator terlatih) | **YA — bersyarat** | Gate invarian PASS 59/0/1 (exit 0); 170 tes terkait lulus pada klon DB; 4 defek P2 yang menyangkut angka & jejak audit sudah diperbaiki dan diukur ulang. Syarat operasional ada di §2. |
| **STAGING_READY** (lingkungan uji bersama, data bukan demo) | **BELUM** | 2 advisory dependensi **High** (SEC-01, SEC-02); ledger belum *append-only* di DB (D-03); suite demo belum deterministik (TST-01/TST-03); belum ada `pip-audit` di CI (SEC-07). |
| **PRODUCTION_READY** | **BELUM** | Semua alasan staging + artefak build lama memuat literal sandi demo (SEC-03), rate-limit/DAST belum diuji (SEC-09), aksesibilitas/aksesibilitas-keyboard & uji beban belum pernah masuk gerbang (TST-05, AUD-040), dan rantai keputusan→PO belum lengkap untuk baris impor (D-05 sisa). |

**Satu kalimat.** Sistem ini **layak didemokan** dengan angka yang kini dapat
dipertanggungjawabkan (rincian biaya menjumlah, ledger tanpa blok yatim,
provenance demo utuh, 4 PO tertaut keputusan), tetapi **belum layak** menjadi
staging/produksi karena keamanan dependensi, penegakan *append-only*, dan
determinisme suite belum ditutup.

---

## 2. Syarat pemakaian untuk DEMO_READY

1. **Bangun template sekali sebelum naik panggung** lewat tombol "Siapkan data
   demo" (atau `mulai_dengan_template`). Rebuild 26 Okt 2026 memakan ~40 detik
   dan berakhir dengan sesi `active` 120 menit.
2. **Jangan menjalankan `pytest` penuh pada DB demo** — 13 tes suite menyentuh
   keadaan data demo (TST-01). Untuk verifikasi, pakai klon (`pg_dump` →
   `createdb`) seperti yang dilakukan hari ini.
3. **Segmen KPI harus setelah satu eksekusi nyata.** `Safe Delivered Cost` dan
   `Decision Time` untuk periode **today** memang `no_data` sampai operator
   mengeksekusi satu kartu (by design, NUM-02). Pada 7 hari/1 bulan keduanya
   `available` (SDC Rp 18.965.818,44, n=2; Decision Time 20,00 menit, n=2).
4. **Jangan menampilkan daftar PO ke SPPG sebagai bukti "semua PO tertaut".**
   SPPG Jakarta melihat 2 PO (hasil eksekusi). 12 PO impor SAP sengaja tidak
   punya keputusan dan tidak terlihat oleh peran SPPG (D-05 sisa, DIFF-01).
5. **Jangan mengklaim "pipeline 7 tahap dialami satu keputusan"** (AG-08), dan
   jangan menjadikan jejak `sdc` sebagai bukti komputasi independen (AG-01).
6. **Jangan menekan "Hapus data demo" tanpa backup** dan jangan mengubah `.env`
   saat sesi berjalan.

---

## 3. Apa yang berubah hari ini (bukti, bukan klaim)

| Defek | Sebelum (terukur) | Sesudah (terukur) |
|---|---|---|
| D-01/BL-01/NUM-01 — SDC ≠ Σ komponen | 4 keputusan, selisih Rp 4.724.709,71 & Rp 6.624.258,72 | **0** keputusan; 4 kartu `selisih = 0.00` |
| D-02 — blok ledger yatim | 12 (snapshot audit), 22 (reproduksi `force=True`) | **0**; `/ledger/verify` `linked_ratio 1.0`, `coverage_warning null` |
| D-04 — provenance demo | `origin='demo'` 0 baris; 26 `demo_case` ber-`origin='seed'` | **30** keputusan `origin='demo'`; **0** `demo_case` ber-`origin='seed'`; 12.950 baris demo di 9 tabel |
| D-05 — PO tanpa keputusan | 12/12 PO tanpa `decision_id` (cek gate vakum) | **4** PO tertaut (cek gate tidak vakum), 12 impor NULL **dengan bukti 0 kandidat pemicu** |
| Gate invarian | 52 PASS, buta terhadap 4 cacat di atas | **59 PASS / 0 FAIL / 1 SKIP**, exit **0**, +7 cek baru |

Tes: **170 passed, 15 skipped, 0 failed** (30 berkas pada klon `fix_verif`,
`DEMO_SESSION_ENFORCE=false`); subset fokus **68 passed**. `ruff check` bersih
pada 7 berkas yang disentuh.

---

## 4. Sisa risiko (jujur, dengan tingkat)

### Risiko tinggi bila sistem dipakai di luar panggung

| ID | Risiko | Mengapa belum ditutup |
|---|---|---|
| SEC-01 | `maplibre-gl@4.7.1` XSS sanitizer bypass (CVSS 10) pada dependensi **produksi** | Upgrade mayor + uji regresi peta belum dijadwalkan |
| SEC-02 | `next@14.2.14` DoS Server Actions + jalur `postcss` | Perlu patch/mayor + build ulang |
| D-03 | Ledger "append-only" hanya konvensi aplikasi: 0 trigger, role `mealchain` superuser + pemilik tabel, `docker-compose.prod.yml` memakai role yang sama | Perlu role DB terpisah atau trigger penolak UPDATE/DELETE — pekerjaan skema, bukan seed |
| SEC-03 | Literal sandi demo di 3 direktori build lama (tidak dilayani dev server, bocor bila diterbitkan) | Perlu hapus artefak + bangun ulang + rotasi sandi |

### Risiko menengah yang mempengaruhi kualitas demo/uji

| ID | Risiko |
|---|---|
| D-05 (sisa) | 12 PO impor tanpa keputusan → KPI SDC hanya hidup setelah ada eksekusi; klaim "setiap PO berasal dari keputusan" tidak boleh diucapkan |
| NUM-01 (sisa) | Alasan `no_data` SDC masih menyebut sebab yang salah ("tidak ada batch terkirim yang punya biaya") |
| NUM-02/NUM-03/NUM-04 | Decision Time bergantung eksekusi; jendela `start/end` masa depan belum dijepit; Meal Continuity `today` pecah setelah 21.00 WIB |
| BL-03 | Gerbang "log suhu lengkap = aman" — **laten P1** begitu ada endpoint penambah log suhu |
| BL-02/BL-04 | `executed` bisa berarti "semua batch ditahan"; `quarantine_status='failed'` masih jadi kandidat yang pasti 409 |
| AG-01/AG-02 | Jejak `sdc` diselaraskan penyemai; `PREDICT` tidak mempengaruhi `DECIDE` |
| TST-01/TST-03 | 13 tes suite gagal pada keadaan data tertentu; suite demo tidak deterministik terhadap keadaan DB |
| D-08 (sisa) | Empat mata, koordinat pemasok unik, kosakata `delivery_events` belum masuk gate |

### Risiko rendah / tercatat

D-06 (indeks duplikat), D-07 (1 akun uji), D-09/D-11 (indeks tak terpakai, 10 DB
residu), D-10 (teks CHECK berbeda, UNVERIFIED), NUM-05…NUM-13, BL-05…BL-09,
AG-03…AG-08, DIFF-02…DIFF-05, SEC-04…SEC-09, TST-02/TST-04…TST-06.
Rincian per ID ada di `MASTER_AUDIT_SUMMARY.md` §3.

---

## 5. Langkah berikutnya (urut prioritas)

1. **Keputusan owner atas D-05 sisa** — pilih salah satu: (a) biarkan 12 PO impor
   tanpa keputusan dan cantumkan di narasi demo (keadaan sekarang), (b) hapus
   baris impor (memecah 2 tes seed/SAP), atau (c) buat 12 keputusan rekonstruksi
   (menambah 12 keputusan demo & mengubah angka KPI). Tanpa keputusan ini,
   target "0 PO tanpa keputusan" tidak dapat dicapai secara jujur.
2. **Tutup SEC-01/SEC-02** (upgrade `maplibre-gl` ≥6.16 dan `next` patch/mayor) +
   uji regresi peta & build; lalu **SEC-03** (hapus artefak lama, build ulang,
   rotasi sandi demo).
3. **D-03**: buat role DB aplikasi tanpa hak UPDATE/DELETE pada `ledger_blocks`
   (atau trigger penolak) + uji bahwa UPDATE ditolak. Ini syarat staging.
4. **NUM-03**: jepit `end` ke `now` di `api/kpi.py` (perubahan kecil, menutup
   jalur KPI menghitung masa depan). **NUM-01 sisa**: perbaiki teks alasan
   `no_data` agar menyebut sebab sebenarnya.
5. **BL-03/BL-04**: samakan definisi "log lengkap" dengan gerbang keselamatan;
   kecualikan `quarantine_status='failed'` dari kandidat.
6. **TST-01/TST-03**: jadikan suite demo deterministik (fixture yang memulihkan
   deret + kasus) supaya gerbang merah/hijau berarti.
7. **D-08 sisa**: tambahkan cek empat mata, koordinat pemasok unik, dan kosakata
   `delivery_events` ke `verify/invariants.spec.json`; jalankan spec browser
   (`ui`) supaya lapisan FE tidak lagi SKIP.
8. **Sebelum produksi**: `pip-audit` + `bandit` di CI (SEC-07), rate-limit login &
   DAST pada stack terisolasi (SEC-09), aksesibilitas (AUD-040), uji beban, dan
   pembersihan 10 database residu (D-11).

---

## 6. Yang TIDAK diklaim dokumen ini

- Tidak ada klaim bahwa seluruh 60+ temuan audit sudah selesai. Yang selesai
  hari ini **4 defek** (D-01/BL-01/NUM-01, D-02, D-04, D-05 sebagian) + 1
  perluasan gate (D-08 sebagian).
- Tidak ada klaim kesiapan produksi, kesiapan staging, atau kelulusan audit
  keamanan.
- Tidak ada klaim bahwa angka KPI "hidup" tanpa aksi operator: `today` memang
  kosong sampai ada eksekusi (by design).
- Tidak ada klaim bahwa lapisan browser diuji oleh gate ini (SKIP: spec tanpa
  bagian `ui`).
