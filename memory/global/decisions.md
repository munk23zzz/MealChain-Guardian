# Decisions — MealChain Guardian (log ADR ringkas)

> Format: `[YYYY-MM-DD] Keputusan — alasan — dampak`. Append ke bawah, jangan edit baris lama.
> Keputusan permanen; kondisi kerja harian ada di [[active-context]].

---

- [2026-10-05] Sprint 2 dieksekusi via plan terkunci `.hermes/plans/2026-10-05-sprint2-decision-intelligence.md` — item Roadmap di luar plan = carry-over eksplisit, bukan kegagalan. — diperjaskan ruang lingkup sprint.
- [2026-10-06] Opsi A SDC dikunci — endpoint `/cost/safe-delivered` standalone jadi carry-over plan-binding. — mengunci desain balancing engine.
- [2026-10-06] Kode agent ditaruh di `app/services/` & `app/ai_providers/`, BUKAN `agent/` root — `agent/` di luar bind-mount container. — lokasi file agent layer.
- [2026-10-06] Chain model frontier-first: Bedrock Claude → Astra → Claude-5.5 → Claude-5 → kimi-k3 → qwen TERAKHIR; AgentCore Runtime (ARN terisi) jadi primary, chain total 7. — Revisi 2 arah Roy.
- [2026-10-07] Verifier REST client (bukan agent Strands kedua); UNAVAILABLE → syarat dual approval (fail-closed). — desain verifier.
- [2026-10-07] Rejection WAJIB alasan (422 bila kosong) → re-propose via `supersedes_id` + trace LEARN; chain v1→v2→v3 via `GET /decisions/{id}/chain`. — Revisi 8.
- [2026-10-07] CORS allow-list eksplisit localhost:3000/127.0.0.1:3000 — fix "Failed to fetch". — Revisi 7.
- [2026-10-07] AgentCore Gateway LIVE (gateway READY; verifikasi via get_gateway by ID — quirk `list_gateways` count=0). — Revisi 6.
- [2026-10-08] RBAC guard di SEMUA endpoint incl. 13 endpoint legacy Sprint 1/2 (Revisi 10, TDD); final gate Sprint 3 PASS → Sprint 3 DONE. — penutupan Sprint 3.
- [2026-10-09] Overhaul visual: latar abu + kartu depth + filter chip status; MapLibre GL (tile OSM raster, tanpa API key) menggantikan peta SVG skematik. — keputusan Roy.
- [2026-10-09] Navigasi direstrukturisasi ke 5 tab PRD 2.4 (Overview/KPI/Recommendations/Agent Log/Demo Control approver-only); persona label = judul resmi PRD §2. — keputusan Roy.
- [2026-10-09] Komponen kripto PRD (Polygon/IPFS/Merkle/FIDO2 versi PRD) & chaos sliders backend TIDAK dibuat — arsitektur & backend tetap keputusan terakhir. — boundary PRD vs implementasi.
- [2026-10-09] Paket integrity & KPI disetujui Roy: P1 Merkle ledger append-only + `GET /ledger/verify`; P2 dossier SHA-256 `mc1-`; P3 ECDSA secp256k1 per approval (`SIGNING_KEY_HEX`, tanpa kunci = `unsigned` jujur); P4 chaos sliders via API resmi; P5 telemetry banner jujur; P6 tabel facts KPI (Meal Continuity & Avoidable Food Loss LIVE). — Sprint 4.
- [2026-10-09] REF seed canonical = 2026-10-08 12:00 UTC (ruling Roy) — dataset demo ter-anchor di situ; REF lain menduplikasi baris. — penting untuk seed/test.
- [2026-10-09] Video fallback DIBATALKAN (waived Owner) — evidence dokumen saja. — S4-06 tanpa video.
- [2026-10-10] Desain Stitch (7 layar) diadaptasi VISUAL-ONLY via token CSS `globals.css` (palet teal #005c55/#0f766e/#0F172A/#2DD4BF) — struktur komponen & kontrak API TIDAK diubah. — S4-09.
- [2026-10-10] Paket akses SAP diterima (RPT-1.6, general 40+, Joule, AI Launchpad) → S4-10 dibuat. SAP AI Core = jalur "real SAP" yang murah & independen; S/4HANA cloud (mahal) dikeluarkan dari rencana. "Real SAP" = model AI nyata (RPT-1.6 forecast + LLM AI Core verifier primary), data tetap mock. Joule = talking point saja. — arah Roy via diskusi sesi ini.
- [2026-10-10] BL-01 (Settings/Admin screen) naik ke Sprint 4 sebagai S4-11. — arah Roy.
- [2026-10-10] Vault Obsidian MealChain dibuat di `memory/` (pola sama dgn AI-TIOS) sebagai memory build lintas sesi; TODO.md tetap primary untuk status task. — keputusan sesi ini.
- [2026-10-10] Supplier exclusion lokal per SPPG, aktif sampai dicabut melalui keputusan pemulihan berbukti dan approval baru; batch safety `FAIL` tetap tidak eligible. — scope administratif tidak melemahkan safety.
- [2026-10-10] Adopsi selektif Nabil selesai untuk A/B/C/D1/D2 tanpa transplant frontend: Overview mempertahankan desain MealChain/Stitch, SAP mock tetap default dan mode real unsupported fail-closed, evidence/export memakai dossier tersimpan dan authorization. — S4-09d.
- [2026-10-14] **Ruling cakupan lokasi per peran**: peran SPPG (`sppg_head`, `sppg_nutritionist`) hanya membaca lokasi sendiri di `/decisions`, `/balance/*`, `/supply`, `/demand`, `/kpi` (permintaan ke lokasi lain = `403`, bukan daftar kosong); `bgn_monitor` membaca semua lokasi dan read-only (dilarang menyentuh `/demo/*`, `/admin/*` boleh dibaca). Pengecualian disengaja: data sumber pemasok (`GET /suppliers`, register eksklusi) boleh dibaca lintas daerah. — ruling Roy, dokumen `docs/ruling-2026-10-14-scope-lokasi.md`.
- [2026-10-15] `GET /suppliers` + migrasi `012_supplier_profile` (koordinat berpasangan, kapasitas mingguan, sertifikasi, kontak). Tab **Pemasok** dan **pin pemasok di peta** memakai daftar nyata, menggantikan sampel 8 keputusan dari `approval-summary` untuk keperluan daftar. — Fase 2–3.
- [2026-10-15] Migrasi `013_origin_generated_at`: `origin` (`'seed'`/`'demo'`) + `generated_at` (NULL = kanonik) di 6 tabel + kunci upsert deret waktu; `downgrade()` menghapus baris demo lebih dulu supaya baris turunan tidak terbaca sebagai kanonik. Baris demo = 5.054, kanonik = 144. — Fase 4.
- [2026-10-15] Panel "Data & rentang waktu" di tab Demo Control dipasang **sebelum** konsol pemicu skenario (urutan: siapkan data → picu skenario → analisis); pratinjau dipicu tombol, hapus data demo 2 langkah, dan "Segarkan ke hari ini" diberi peringatan karena memindahkan jangkar snapshot kanonik 8 Okt 12.00 UTC. — Fase 5.
- [2026-10-15] **Fase 7 dikunci**: pemasok demo dipindahkan ke klaster Jabodetabek + penyangga Jawa Barat ≤ ~150 km (10–12 pemasok, jarak berjenjang 0–25/25–60/60–150 km); 14 pemasok kanonik (kunci 14 kutipan harga) tidak diganggu; `max_distance_km` + cakupan jarak di UI jadi fase tersendiri. — jawaban Roy atas 4 pertanyaan plan §7.
- [2026-10-15] Temuan verifikasi Fase 6 yang mengikat cara kerja: (a) suite pytest menulis ke **DB demo yang sama** → residu uji (156 keputusan vs 4 kasus skrip + 11 seed; tabel `users` 1.073 baris untuk 3 akun demo) — perlu DB tes terpisah atau langkah bersih-bersih; (b) `next build` di kontainer frontend saat `next dev` hidup membuat chunk 404 → halaman kehilangan hidrasi sampai kontainer di-restart; (c) filter komoditas peta memuat `beras` yang tidak ada di DB → `404` + galat jujur di UI; (d) `beras`/`wortel` pada filter peta adalah 2 dari 4 pilihan yang tidak semuanya ada di DB.
- [2026-10-15] **Fase 7b — "terjangkau" sebagai RELEVANSI, bukan scope**: `GET /suppliers` menerima `max_distance_km` (+ `commodity`) dan mengembalikan `distance_km`, `distance_reference`, dan blok `reach` (`excluded_out_of_reach`, `excluded_unknown_distance`). Titik rujukan = lokasi user (peran SPPG) → hub pada filter `location=` → tidak ada; **tanpa rujukan, penyaring dijawab 422** (fail-closed, bukan seluruh tabel seolah tersaring). Jarak dihitung SERVER di satu implementasi (`app/core/geo.py`), UI hanya membandingkan dengan ambang 150 km (`SUPPLIER_REACH_KM`); baris tanpa jarak tidak pernah dianggap dekat. Peta Overview = penyaring server (peran SPPG) dengan kalimat berapa yang tidak dipasang; halaman Pemasok = daftar penuh + kolom Jarak + penyaring pilihan pengguna. — Fase 7b/7c, bukti `docs/verification/fase-7.md`.
- [2026-10-15] **Strip "Target KPI — Demo Day" dihapus dari halaman KPI** (arahan pemilik): `components/KpiTargets.tsx` dibuang, pemakaian + CSS `.kpi-target*` (~1,8 kB) ikut dibuang, dan `tests/prd-nav.test.tsx` sekarang memaku KETIADAANNYA (dulu memaku keberadaannya). Alasan: panel itu memuat angka PRD yang bukan angka live (`TARGETS` hardcoded) sehingga bertabrakan dengan prinsip "tidak ada angka karangan" — halaman KPI kini hanya memuat nilai dari backend.
- [2026-10-15] **Tab gabungan "KPI & Kualitas Agen"** (keputusan pemilik): dua tab lama "KPI" + "Kualitas Agen" disatukan — id tab `"kpi-kualitas"`, urutan **KPI dulu** lalu mutu agen, "Rincian per run" tetap tampil penuh. Nama dipilih pemilik dari 4 usulan ("Kinerja & Mutu", "Kinerja & Mutu Agen", "Hasil & Mutu", "KPI & Kualitas Agen"). Komposisi di `components/KpiQualityBoard.tsx` yang sengaja TIPIS: isi `KPIDashboard` dan `AgentQualityBoard` tidak diubah, jadi angka di layar tidak bisa berbeda dari sebelum penggabungan; yang diatur hanya urutan + satu pembatas. Strip "Target KPI Demo Day" dihapus di hari yang sama atas arahan pemilik → tab ini hanya memuat angka backend.
- [2026-10-15] **Gerbang muat KPI** (`lib/kpi.ts::shouldLoadKpi` = `today || kpi-kualitas`): sebelumnya `/kpi` diambil di SEMUA tab. Daftarnya konstanta eksplisit + diuji karena angka yang hilang TIDAK memunculkan error — kalau tab pemakai baru ditambah dan daftar ini lupa diperbarui, kegagalannya senyap.
- [2026-10-15] **Fase 7d — jarak pemasok masuk biaya SDC** (jawaban Roy plan §7.4 #4: "pemilik ingin jarak pemasok ikut dihitung dalam biaya SDC"). Biaya angkut satu kandidat = **kaki pertama (pemasok → SPPG sumber)** + **linehaul (SPPG → SPPG tujuan)**, keduanya tarif 300 Rp/km/ton; kaki pertama dari koordinat nyata (`suppliers` → `locations`) via haversine `app/core/geo.py`. Jarak masuk **biaya**, BUKAN skor (kontrak Task 5 terkunci); biaya sudah jadi tie-breaker resmi ranking (Task 7). Yang TIDAK berubah: komponen SDC tetap 6 (`safe_delivered_cost.py` tidak disentuh), `logistics_distance_km`/kelayakan delivery window tetap linehaul → skor & eligibilitas tidak bergeser. Koordinat tidak lengkap TIDAK ditebak: biaya 0 + label `supplier_coordinates_missing` / `no_supplier`; 0 km tidak pernah diklaim sebagai jarak. Kontrak `fetch_facts` 6-tuple Task 9 tetap sah — peta jarak adalah elemen ke-7 opsional. Dampak: Cianjur→Jakarta +282,00 (kaki 1,880 km), Bogor→Jakarta +6.653,07 (kaki 45,075 km), 0 kandidat berpindah peringkat, jangkar 4.900 kg telur utuh. — bukti `docs/verification/fase-7d.md`.
- [2026-10-16] **Profil pemasok kanonik diisi DARI DATA NYATA, bukan dikarang** (permintaan pemilik: "untuk db suplier anda cek laagi apakah sudah benar, jika belum perbaiki"). Audit menemukan 14/14 pemasok kanonik tanpa `commodity_id`/`certification_status`/`capacity_kg_per_week`; hanya 3 di antaranya dipakai batch. Aturan turunan dikunci di modul murni `app/seed/supplier_profile.py`: komoditas = total `quantity_kg` terbesar (seri → batch terbaru; masih seri → `None`), sertifikasi = nilai terbanyak (seri → `None`), **kapasitas TIDAK diturunkan** karena tidak ada sumbernya. Seeder mengisi **hanya celah kosong** (tidak menimpa nilai yang sudah ada) → 3 pemasok terisi (A/B/C Cianjur = telur + HACCP), 11 tanpa batch tetap kosong. Dua jalan yang ditolak: mengarang angka, dan menyalin profil dari pemasok demo. — bukti `docs/verification/fase-9.md` §2-§4.
- [2026-10-16] **Definisi "sedang mengirim" dikunci pemilik**: pemasok yang punya batch kiriman dengan **`usable_until >= sekarang`** (masih layak hari ini). Kiriman kedaluwarsa bukan kiriman aktif. Dihitung backend (`app/core/supplier_shipping.py`, satu suara) dan dikirim sebagai kunci `shipping` per baris `GET /suppliers` (`count`, `total_kg`, `until`, `commodities`, `safety_fail_count`); frontend hanya menampilkan. Di peta ini **cincin tambahan** pada pin (`map-pin-supplier-shipping`, token `--status-safe`), BUKAN nada kelima — warna tetap berarti keandalan/jangkauan, jadi dua fakta berbeda tidak saling menutup. Kiriman berstatus `safety_status=fail` tetap dihitung dan **dilaporkan terpisah**, tidak disembunyikan di balik kata "sedang mengirim". Saat ini 2 pemasok (A: 3 kiriman 1.400 kg telur s/d 2 Nov; B: 1 kiriman 600 kg s/d 26 Okt, 1 gagal uji). — bukti `docs/verification/fase-9.md` §5.
- [2026-10-16] **Garis peta mengikuti JALAN (OSRM), dan rutenya di-cache di DB** (jawaban pemilik atas "dimap ada seperti garis mengikuti jalur dari suplier ke tujuan"). Dua alternatif ditolak: garis lurus antar dua pin (tidak menggambarkan jalur), dan pemanggilan OSRM dari peramban saat peta dibuka (demo bergantung internet, hasil bisa berbeda tiap buka, dan server OSRM demo dibanjiri tiap pengunjung). Geometri diambil **saat seeding/sync** (`app/seed/road_routes.py`, CLI `scripts/sync_road_routes.py`) dan disimpan di tabel baru `road_routes` (migrasi `014_road_routes`, kunci = koordinat 4 desimal → dua batch dari pasangan sama cukup satu rute, sinkronisasi idempoten). Hanya kiriman yang masih layak (`usable_until >= now`) yang dipanggil rutenya. Angka OSRM adalah **data pihak ketiga** dan disebut begitu di UI ("jalur jalan dari OSRM"); kalau rute belum ada, peta menulis alasannya (`belum_disinkron` dll), bukan menggambar garis lurus yang menyamar sebagai rute jalan. Jarak lurus (haversine server) dan jarak jalan dilaporkan berdampingan supaya bedanya terlihat: Cianjur→Jakarta **78,35 km lurus vs 110,4 km jalan (1,41×)**. — bukti `docs/verification/fase-10.md`.
- [2026-10-16] **Kiriman demo baru ke SPPG Jakarta + kelas CSS `ship-route`** (lanjutan keputusan di atas). Tidak ada kiriman yang menuju Jakarta, jadi akun SPPG Jakarta tidak akan pernah melihat jalur; pemilik memilih kiriman yang ditambahkan: **Supplier A Cianjur → SPPG Jakarta, telur, 800 kg, layak s/d 7 Nov 2026, `pass`** — angka dari pemilik, tanggal dihitung mesin seed yang ada (harvest −36 jam + shelf 35 hari × 0,90), bukan angka baru yang dikarang. Kelas DOM memakai prefiks **`ship-route`**, BUKAN `route-line`, karena `route-line` sudah milik signature halaman login (dikunci `tests/login.test.tsx`) — pelajaran dari tabrakan nama yang sama di masa lalu. Karena data berubah, tiga ekspektasi tes lama ikut diselaraskan secara sadar (A Cianjur 3→4 kiriman; keputusan telur Jakarta kini punya pemasok sehingga skenario "pemasok tak diketahui" dipindah ke komoditas ayam) — aturan produksi tidak dilonggarkan untuk meluluskan tes. — bukti `docs/verification/fase-10.md` §6.
- [2026-10-16] **Kolom "Jalur kirim" di tabel Pemasok** (lanjutan permintaan yang sama). Sumbernya `GET /supplier-routes` dengan query **penuh tanpa saringan komoditas** — tabel menampilkan semua pemasok, jadi menyaring jalur akan membuat baris pemasok lain terbaca "tidak punya jalur" padahal jalurnya cuma tidak diminta. Tiga aturan tampilan dikunci tes: (1) baris utama = jalur **terpendek yang geometrinya sudah ada** (jalur tanpa geometri TIDAK dianggap 0 km); (2) **tanpa lencana warna** — lencana sudah milik kolom Status, dan dua makna berbeda tidak boleh memakai bahasa visual yang sama; (3) **jarak lurus tidak diulang** di kolom ini karena kolom Jarak sudah memuatnya (kalau diulang, angkanya terbaca seperti hitungan ganda). Empat keadaan dibedakan tegas: `—` (tidak punya kiriman aktif), `…` (data jalur belum dimuat), `belum disinkronkan` (hanya untuk alasan itu), `jalur tidak tersedia` (alasan lain, tidak disamarkan). Bukti layar akun BGN Monitor: A Cianjur `→ Cianjur · 3,2 km jalan · +3 tujuan`, B Cianjur `→ Surabaya · 730,8 km jalan`, 33 baris `—`, ringkasan `5 dari 5`. — bukti `docs/verification/fase-10.md` §8.
- [2026-10-16] **Fase 9 — rail diperkecil, panah lipat dibalik, ujung atas skala font diturunkan** (permintaan pemilik: "menu sidebar diperkecil, ikon `<` saat sidebar ditutup pakai `>`"). **Panah:** arahnya SUDAH benar di komponen (`ChevronIcon`: buka `<`, tutup `>`) tetapi CSS lama memutar `rotate(180deg)` saat rail tertutup sehingga yang tampil justru `<` — putaran itu dibuang; terukur terbuka `m15 18-6-6 6-6` (`<`), tertutup `m9 18 6-6-6-6` (`>`), `transform: none`. **Rail (desktop saja):** item 44→**38px**, pitch 48→41, gap 4→3, padding 12→10, radius 10→9, ikon 18→**16px**, label `--fs-3`→**`--fs-2`** (14→13px), tombol demo min-height 40→36; batas sentuh 44px TETAP lewat `@media (pointer: coarse)` + baris mobile ≤720px; label tetap satu kolom (x=46) dan rail terlipat tetap terpusat (pusat ikon 34 = pusat rail 34). **Skala:** ujung atas diturunkan — `--fs-6` page 22→**20**, `--fs-7` metric 28→**24**, `--fs-8` hero 44→**36** (contoh skala hero skill: 36–42); skala tetap 8 langkah (12/13/14/16/18/20/24/36) dan karena semua `font-size` bertoken, perubahan merambat ke seluruh app tanpa menyentuh selector (hero terukur 36, metrik 24, judul halaman 20). **Koreksi penting:** entri Fase 8 mengklaim `.overview-header-title h1` & `.settings-title` diseragamkan ke `--fs-6`, padahal pemetaan otomatis menaruhnya di `--fs-5` (18px) — ketemu saat mengukur judul per tab, dan baru dikerjakan sekarang (ketiganya kini `--fs-6`). Aturan baru: **klaim "diseragamkan" wajib dibuktikan dengan pengukuran per halaman**, bukan disimpulkan dari tabel pemetaan. **Survey ikon:** hanya 2 SVG ≥22px di seluruh app (logo rail 26px di kotak 32px + kanvas stock-chart) — tidak ada ikon lain kebesaran. Gerbang: tsc=0 + 667 tes + lint=0; harness responsif 0 luapan; belum ada commit/push. — bukti: `…\scratch\fase7\verif-fase9.py`, `cek-font-tab.py`, `cari-ikon-besar.py`, `fase9-*.png`, dokumen `_qa/rencana-redesign-ui.md` (Fase 9) + `docs/design.md`.
- [2026-10-16] **Fase 8 — skala tipografi 8 langkah + perapian rail (permintaan pemilik: "atur ukuran fontnya supaya UI lebih bagus dan rapikan sidebar")**. Dipandu skill `ui-ux-pro-max`: pencarian `--domain typography` mengembalikan pasangan "Dashboard Data (Fira Code/Fira Sans)" = persis yang sudah dipakai, `--design-system --density 8` memberi pola "Real-Time/Operations" (aturannya "label telemetri sebagai live hanya bila sumbernya nyata + waktu pembaruan" sudah dipatuhi), sedangkan rekomendasi **Dark Mode (OLED) DITOLAK** karena bertentangan dengan Arah 4 terang. **Diagnosis:** `globals.css` punya **24 ukuran font** (11px & 11,5px di bawah lantai 12px, pecahan 12,5/13,5/14,5/15,5, satuan `0.8rem`/`0.82rem`, dan dua sistem kembar: angka mentah vs token `--text-micro`/`--text-meta`). **Perbaikan:** token `--fs-1..--fs-8` = 12/13/14/16/18/22/28/44 + `--lh-num/--lh-head/--lh-body` (1.15/1.3/1.5) + `--track-tight/--track-caps`; token lama DIHAPUS setelah semua pemakaian dialihkan; **243 deklarasi `font-size` → 0 angka mentah**; ukuran berbeda 24 → 8. Judul halaman diseragamkan ke `--fs-6` (22px: `.page-header h1` 24→22, `.overview-header-title h1` 18→22, `.settings-title` 18→22, `.overview-header-main h1` 20→22); angka metrik ke `--fs-7` (28px: kpi-value 30/32→28, quality-stat-value 30/26→28, stat-tile-value 30→28, balance-value 26→28, kpi-value-none 24→28). **Dua cacat bawaan yang hanya ketemu dengan mengukur:** (1) `.provider-panel h2` dan `.header h3` panel governance TIDAK punya aturan font-size → jatuh ke bawaan peramban (terukur 21px & 16,38px) → diberi aturan; (2) sisa perubahan level judul Fase 7 membuat 4 selector kehilangan sasaran (`.page-header h1`→+`h2` 18px untuk level 2, `.quality-section-head h2`/`.quality-error h2`→+`h3`, `.chaos-panel/.event2-panel h4`→`h3`, `.decision-chain h4`→`h3`). Sesudahnya sapuan 2 peran × 11 tab: **semua simpul teks "✓ dalam skala"**. **Rail:** baris brand 64px (= top bar, dulu ~70px sehingga tidak segaris), item nav 44px (dulu 40, pitch 48px), padding rail 12px seragam, kotak ikon tetap 18×18 (9 label kini mulai di x=53 yang sama), ikon pakai token `--ink-subtle` (bukan `opacity:.75`), bar aktif 3×20px dipusatkan, semua tombol ikon 32×32, aturan mati `.side-brand-sub` dihapus. **Rail terlipat 68px — dua bug yang hanya ketemu dengan mengukur:** label berlebar 0 tetap menyumbang satu `gap` (ikon duduk di 29, bukan 34 → `gap:0` di rail terlipat), dan tombol ber-`width:0` tetap menyisakan padding+border 14px (avatar 27 → padding & border-width dinolkan). Verifikasi akhir: pusat ikon = avatar = tombol lipat = pusat rail = **34**. Gerbang: tsc bersih + **667 tes** + lint bersih + harness responsif 0 luapan. **Belum ada commit/push.** — dokumen: `_qa/rencana-redesign-ui.md` (Fase 8), `docs/design.md` (tabel skala + kontrak rail). Diukur **29 kombinasi peran×tab** (BGN Monitor 9, SPPG Head 10, Nutritionist 10) di 375/768/1024/1440 px + reflow 320 px; harness + bukti JSON/PNG di `…\hermes\cache\scratch\fase7\` (di luar repo). Hasil: **0 luapan halaman** (sebelumnya Pengaturan@375 10 px & @320 65 px), **0 fokus tanpa cincin** (Tab 14×, `outline 2px rgb(37,99,235)`), temuan **● 123 → 0** di axe-core 4.10.2. **Kontras:** akar masalah terukur — hijau `#2E7D32` di atas tint-nya `rgba(46,125,50,.1)` = **4,49:1** (gagal AA beda 0,01) di 9 aturan; `opacity: .75` di `.legend-count` = 4,00:1; `--ink-subtle` di atas permukaan ber-tint = 4,34:1. Perbaikan: token baru **`--safe-ink-tint: #2A722E`** khusus teks di atas tint hijau (dot/garis rute/teks di atas putih tetap `--status-safe` — keputusan Fase 0 "jangan mencerahkan warna status" TIDAK dilanggar), `.legend-count` pakai token warna (bukan opacity), label ber-tint pakai `--ink-muted`. **Judul:** satu h1 per halaman + tanpa lompatan tingkat (KPI 2→1 h1; Pengaturan 0→1) lewat prop baru `level` di `PageHeader`; `DecisionChain` h4→h3, panel Demo Control h4→h3, `ProviderPanel` h3→h2, `SettingsPanel` judul h1 + kartu h2. **Reflow:** `.settings-table-wrap` dapat `contain: paint` (penyebab diverifikasi dengan menyembunyikan elemen satu per satu: Chrome memperhitungkan isi kontainer scroll pada `scrollWidth` dokumen) + `.board-scroll-hint` di kedua tabel; `.top-bar-clock` ganti `aria-label` (tak sah pada `<span>` tanpa role) menjadi teks `.sr-only` + teks terlihat `aria-hidden` (terbaca sekali; `lib/jam.ts` tak diubah → tesnya tetap hijau). **Pelajaran penting yang mahal:** `max-width: min(320px, 100%)` pada select di dalam flex **MEMPERBURUK** halaman (Agent Log & Decision & Evidence @375 meluap 236 px) karena persentase di `min()` membuat elemen melaporkan kontribusi intrinsik 589 px ke induk; yang benar = batasi induknya (`max-width: 100%` + `min-width: 0`) lalu `width: 100%` + batas px pada elemennya (diuji 320/375/768/1440: 276/320/320 px). Kotak centang Demo Control: target label 295×19 → **295×44 px** (`min-height`), klik pada teksnya terbukti men-toggle. Pengecualian target sentuh yang disengaja: kontrol bawaan MapLibre 29×29 (di atas batas WCAG 2.2 = 24 px) & `.map-layer-toggle` 34 px (keputusan pemilik). **◐ yang diverifikasi bukan kegagalan:** lonceng `aria-controls="top-bar-notif-panel"` — ID-nya ADA saat panel dibuka; `.map-pin-label` 17,85:1 & inisial avatar 5,17/6,7:1 (dua-duanya LULUS — pengukuran mencegah "perbaikan" palsu). **Terbuka (keputusan pemilik):** `aria-prohibited-attr` pada 3 pin peta (`div.map-pin[tabindex="0"][aria-label]` tanpa role) — opsi `role="img"` atau `keyboard: false` pada `maplibregl.Marker`; popup pin memang belum bisa dibuka keyboard (dampak rendah: daftar lokasi di samping peta memuat data yang sama). **Favicon masih belum ada** (F5/WS-E diputuskan dilewati; 7 jalur kandidat 404) — satu `app/icon.svg` bisa menutupnya kapan pun. Gerbang: tsc bersih + 667 tes + lint bersih. **Belum ada commit/push.** — dokumen: `_qa/rencana-redesign-ui.md` (di luar repo), `docs/design.md`.
- [2026-10-16] **Arah visual dikunci ke "Bento Modern" (Arah 4); eksekusi bertahap dimulai** (arahan pemilik: "sebenarnya saya kurang suka dengan ui ux yang sekarang" → 5 mockup dibangun → pemilik memilih **Arah 4** dan menerima 3 default: rail + top bar **TERANG fros**, aksen biru `#2563EB`, font **Fira Sans + Fira Code**). Ini **membalik keputusan "rail biru" 2026-10-09**, bukan menambah di atasnya — alasan: biru pekat adalah penyebab utama kesan "admin CRUD lama", dan yang diperbaiki adalah **hierarki** (grid bento asimetris), bukan sekadar warna. Rencana 7 fase ditulis **di luar repo** (`_qa/rencana-redesign-ui.md`) supaya tidak mengotori git. Kontrak yang TIDAK boleh berubah: kelas tes-sensitif (`.map-*`, `.side-tab*`, `.board-table-wrap`), `lib/supplier-pins.ts`, kontras WCAG AA, polling peta 5 detik, zoom pengguna. **Fase 0 (lapisan token) selesai**: `:root` → ink `#0F172A`, brand `#2563EB`, kanvas `#F8FAFC`, garis `#E2E8F0`, radius 16px, bayangan ultra-halus, `--font-data` → Fira Code. **Warna status (hijau `#2E7D32` / merah `#C62828` / amber `#F9A825`) sengaja TIDAK dicerahkan**: green-600/red-600 sebagai teks lencana jatuh di ~3,3:1–4,5:1, di bawah AA — akibat keputusan ini `ROUTE_LINE_COLORS` tidak perlu disinkronkan (rencana awal keliru di titik ini dan sudah dikoreksi). **Fase 1 (kerangka) selesai**: rail & top bar jadi permukaan kaca putih + garis rambut, item rail aktif = tint `--accent-soft` `#EFF6FF` + bar biru, chip peran jadi pill bertint biru, jam top bar pindah ke Fira Code, tombol keluar rail memakai nada merah-terang, dan bug lama `var(--canvas)` (token tak pernah terdefinisi, hover tombol tutup notifikasi jadi tanpa latar) diperbaiki. Gerbang tiap fase: `tsc` bersih + 620 tes frontend lulus + `next lint` bersih + tangkapan layar browser.   **Fase 2 (Overview) selesai**: strip KPI jadi bento 12 kolom berbobot 5/3/4 — tile hero = selisih pasokan (lokasi aktif bila dipilih, kalau tidak Σsurplus−Σshortage jaringan) berangka 44px Fira Code bernada, kartu pasokan + bar kemajuan, kartu rekomendasi; kartu "Perlu keputusan" di samping peta memakai `notifList` yang SAMA dengan lonceng top bar; basemap peta diredupkan lewat filter pada kanvas (`.map-gl canvas`) sehingga pin DOM tetap menyala penuh — nol tile/gaya baru, nol dependensi; logika murni `lib/overview-bento.ts` (TDD, 21 tes baru). **Grafik "Pasokan per Lokasi" DIPINDAH dari kolom samping peta ke baris selebar halaman**: kolom itu cuma ~310px, dan setelah kartu antrean masuk grafiknya tersisa 68px sehingga label 10 lokasi mustahil terbaca; konsekuensinya mode `stretch` StockChart kehilangan satu-satunya pemakainya dan dihapus. **Dua pelajaran teknis yang terukur** (jangan diulang): (1) `ResponsiveContainer` bisa setinggi 0 — di rantai flex yang tingginya dari `min-height`/`auto`, Chrome menghitung `height: 100%` sebagai 0 sehingga SVG tidak dirender sama sekali (terukur: kartu 320, holder 258, RC 0, `svg:false`) → pakai tinggi tetap; (2) urutan media query menentukan — aturan dasar yang ditulis SESUDAH media query akan menang, jadi override layar sempit harus diletakkan setelah aturan dasarnya. Gerbang: `tsc` bersih + **641** tes frontend lulus + `next lint` bersih + verifikasi DOM dua tata letak. **Fase 3 (Recommendations + Decision & Evidence) SELESAI 16 Okt**: kartu lewat tenggat diredam lewat permukaan `--surface-sunken` (BUKAN `opacity` — 0,7 menjatuhkan teks sekunder ke ~3:1, gagal AA) + lencana "Lewat tenggat"; feed masuk bertingkat 6 kartu pertama (`feed-row-in`, mati pada reduced-motion); chip filter hover tint (batas kontrol tetap `--line-input`); Decision & Evidence jadi bento (ringkasan hero 2 kolom, tiga kartu fakta span 4 grid-12, baris bawah 5fr/7fr = Riwayat iterasi | Bukti & integritas, form supplier-exclusion naik jadi baris penuh setelah Governance); **kartu kepercayaan GELAP** `.integrity-trust` (token `--trust-*`, #0F172A) khusus bukti kriptografis — daftar pengukuran + tombol ekspor tetap terang; modal approval radius 16 + garis aksen kiri 4px, gating 1b/2b/3b tidak disentuh. Cacat yang ketemu saat verifikasi: di kartu span-4 (~305px) `.fact-row` dua kolom menyisakan ~105px sehingga "Rp14.022.000" terpecah di tengah angka → label di atas nilai khusus `.evidence-grid`. **Fase 4 (KPI & Kualitas Agen + Agent Log) SELESAI 16 Okt**: kartu KPI jadi angka besar mono 32px + bullet bar dari `bulletOf()` (lib/kpi.ts, TDD 8 tes) — **target/ambang TIDAK dikarang** karena envelope /kpi tidak mengirim target/threshold, jadi bar hanya untuk metrik berskala sendiri (persen 0–100) + catatan arah perbaikan; nilai null/teks/negatif → TANPA bar (bukan 0%); metrik tanpa skala (IDR/menit) juga tanpa bar. Agent Log: chip umur langkah terakhir dari `step_at` (lib/agent-trace.ts, TDD 11 tes), titik berdenyut untuk langkah baru, **shimmer hanya bila data menyatakan berjalan** (`output_summary.status` ∈ running/in_progress/started/pending — tabel agent_traces TIDAK punya kolom status, jadi tidak ada klaim "sedang bekerja" yang dikira-kira), durasi `duration_ms` kini dirender, panel provider jadi chip dengan kata status (warna bukan satu-satunya pembawa makna). Konsol Agent Log tetap TERANG: permukaan gelap hanya sekali di app (kartu kepercayaan Fase 3) — dipakai dua kali efeknya hilang. Gerbang: tsc bersih + 660 tes + lint bersih. **Fase 5 (Keamanan Pangan, Surplus & Limbah, Pemasok) SELESAI 16 Okt**: tiles angka besar ber-tint status di Keamanan Pangan (tint hanya bila keadaannya ada), pagar bahaya 4px untuk blokir batch gagal, titik amber di daftar mendesak; neraca surplus jadi aliran 2 angka + panah SVG (`data-kosong` → panah netral bila salah satu sisi kosong); kolom Keandalan Pemasok jadi bar mini 0–100 dari `reliabilityMeter()` (TDD, ambang `LOW_RELIABILITY`, skor kosong = tanpa bar); panel governance pindah ke token tema. Gerbang: tsc + 663 tes + lint. Temuan data: `/balance/map` peran SPPG hanya mengembalikan lokasi sendiri (Jakarta, surplus 0) sehingga rencana alokasi surplus kosong pada seed ini — surplus nyata ada di Cianjur/Bogor (hanya peran global), sementara peran global tidak punya tab Surplus. **Fase 6 (Hari Ini, Demo Control, Pengaturan) SELESAI 16 Okt**: Hari Ini jadi bento 12 kolom (Menunggu tindakan span 7 × 2 baris 546×617 px; batch & shortage span 5; KPI + rantai audit baris penuh 947 px; daftar KPI 2 kolom ≥900px), chip sisa waktu jadi pil + dot (lewat merah, ≤48 jam amber dari `DUE_SOON_HOURS` — bukan ambang baru; jam klien belum siap → tidak ada klaim), sapaan lewat slot `eyebrow` baru di `PageHeader` (server tidak menyapa), baris "kurang N kg" dipindah ke kelas sendiri (`today-due-short`) supaya merah berarti "kekurangan" bukan "lewat tenggat". **Cacat yang ketemu:** media query lama `@media (min-width:1080px){.today-pending{grid-column:span 2}}` menimpa penempatan bento (kartu terukur 145 px) → aturan dihapus; pelajaran Fase 2 (urutan aturan vs media query) berlaku dua arah. Demo Control: empat blok jadi kartu dengan chip urutan (Langkah 1 siapkan → 2 bangun data → 3 picu agen → 4 skenario), `OpsConsole` naik jadi kartu putih radius 16, pratinjau `writes:false` diberi lencana "pratinjau — tidak menulis apa pun" (amber), baris hasil/pratinjau backend jadi mono sementara prosa tetap font badan; logika `lib/demo-data.ts` + peringatan dua langkah tidak diubah. Pengaturan: kontrol radius 10px (tinggi 44 px tetap) + chip "belum disimpan" hanya pada baris yang draft-nya berbeda (terukur 1 chip, hilang setelah muat ulang tanpa menyimpan). Gerbang: tsc + 667 tes + lint. Fase 7 (responsive 375/768/1024/1440 + audit a11y) BELUM dikerjakan. `docs/design.md` sudah disinkronkan. — belum ada commit/push (aturan pemilik).
- [2026-10-16] **Tab Keamanan Pangan: picker komoditas + pill "Komoditas <x>" DIHAPUS** (permintaan pemilik: "menu memilih komoditas dan komoditas di samping batch di keamanan pangan dihapus"). Dua hal yang dibuang dari `FoodSafetyBoard`: (1) baris chip `.commodity-filters` ("Komoditas: telur | ayam | beras | wortel", aria-label "Komoditas peta") yang menulis ke `mapCommodity` GLOBAL, dan (2) pill `Komoditas {x}` di kepala halaman yang duduk persis di samping pill jumlah batch. **Alasan kenapa aman:** `todayQuery = useToday(token, identityScope)` TIDAK memakai komoditas sebagai kunci, jadi tabel batch tidak pernah tersaring oleh pilihan itu — pill tersebut menampilkan pilihan global yang tidak berpengaruh ke halaman ini (menyesatkan), dan pickernya duplikat dari kontrol komoditas di Overview/`page.tsx`. Props `commodity`/`commodities`/`onChangeCommodity` ikut dihapus dari komponen + pemanggilnya (`page.tsx`) dan dari tes yang masih mengoper `commodity="telur"` (perubahan tes yang disengaja, bukan pelonggaran aturan). Yang TIDAK diubah: kolom `KOMODITAS` di tabel "Status keamanan per batch" dan label `lokasi · komoditas` di daftar "Batch perlu segera dipakai" (keduanya informasi data per batch, bukan kontrol). Bukti layar: pills kepala halaman kini hanya `7 batch` (dulu `7 batch` + `Komoditas telur`), `.commodity-filters` = 0 elemen, teks "Komoditas:"/"Komoditas telur" = 0 kemunculan, tabel tetap 7 baris, luapan 0 px @1440 dan @375. Gerbang: tsc=0 + 667 tes + lint=0. Belum ada commit/push.
- [2026-10-16] **Peta Overview: 2 sakelar lapisan diperkecil + rincian informasi jadi panel yang bisa dibuka/ditutup + gerak UI** (permintaan pemilik: *"untuk maps di overview tolong penjelasan infomasi di rapihin dibuat kecil saja dan bisa di tampilkan dan di tutup dan untuk 2 tombol di atas di buat kecil saja dan animasi ui dan ux di perbaiki"*). **Bilah rincian**: strip `.map-layer-controls` (dua kalimat penuh selalu memakan dua baris di bawah kanvas) diganti `.map-layer-info` = tombol kecil "Rincian lapisan peta" (`aria-expanded`/`aria-controls`, chevron CSS diputar 90°) + **tag angka yang selalu terlihat** (`supplierReachTag` "7/9 pemasok dalam 150 km", `routeLayerTag` "1 jalur kiriman · jalur jalan OSRM") + panel lipat berisi kalimat jujurnya (`supplierReachNote`, ringkasan asal OSRM). Isi panel **tidak dihapus dari DOM, hanya dilipat** (tinggi `grid-template-rows: 0fr` + `visibility: hidden` → hilang dari pohon aksesibilitas, tetap bisa diperiksa) sehingga angka "N di luar jangkauan tidak dipasang di peta" tetap tersedia: penyaringan jangkauan tidak pernah menjadi penyembunyian. Peringatan zoom (`.map-layer-hint`) sengaja **di luar** panel supaya muncul seketika saat lapisan dinyalakan pada zoom jauh. **2 tombol**: 34 → **26 px**, padding 4×9 → 2×8, pil terukur 350×42 → **203×32 px** di :3010 (−42 % lebar, −24 % tinggi); teks yang terlihat menjadi "Pemasok (7)"/"Jalur kiriman (1)" — keadaan hidup/mati dibawa `aria-pressed` + warna (pola pil komoditas yang sudah dipakai app) dan kalimat "Tampilkan/Sembunyikan …" pindah ke `title` (tooltip), jadi nama tombol tetap memuat teks yang terlihat (WCAG 2.5.3 aman). Ukuran huruf **tidak** turun (12 px = lantai teks data) dan target sentuh 44 px tetap di `(pointer: coarse)`/≤720 px. **Gerak**: transisi token (`--dur-1/2/3`, `--ease-standard`) pada sakelar/chevron/tinggi panel, legenda masuk (`map-legend-in`), isi popup masuk (`map-popup-in` dipasang di `.map-popup` — BUKAN `.maplibregl-popup`, yang `transform`-nya milik MapLibre untuk posisi), pin titik bertransisi + hover 1,28× (rotasi 45° pin pemasok dipertahankan); semua dimatikan di `prefers-reduced-motion: reduce`. **TDD**: 5 tes murni baru + 4 tes kontrak komponen (tertutup bawaan, klik buka–tutup, isi panel, tanpa lapisan → bilah tidak dirender); ekspektasi teks sakelar di 3 berkas tes diperbarui **sadar** (kalimat penuhnya tetap ada di `title`, bukan dihapus). Gerbang: vitest **699 lulus/67 berkas**, `tsc --noEmit` 0, `next lint` 0 (`next build` tidak dijalankan — `next dev` hidup). Bukti: pengukuran CDP :3010 akun SPPG Head + `docs/design.md` §3.1/§4. **Belum ada commit/push.**
- [2026-10-16] **Agent Supervisor Strands benar-benar dibuat + dibuktikan live ke Bedrock** (jawaban atas pertanyaan pemilik "apakah supervisor agent sudah terimplementasi??"). Klaim repo selama ini adalah "BLOCKED live", padahal berkasnya **tidak pernah ada**: `git log --all -- agent/supervisor_agent.py` kosong, `agent/` hanya dua `__init__.py`, dan `backend/tests/conftest.py` menaruh tes kontraknya di daftar HOST_ONLY sehingga suite kontainer tetap hijau tanpa membuktikan apa pun — kegagalan senyap yang sama polanya dengan pelajaran "klaim wajib diukur". Tiga berkas baru: `agent/supervisor_agent.py`, `agent/prompts/supervisor_system_prompt.md`, `agent/requirements.txt`. **Keputusan teknis:** atribut Strands diakses lewat modul (`strands.Agent`, `strands.models.BedrockModel`) — bukan `from strands import Agent` — supaya kontrak mock tes S0-07 (`patch("strands.Agent")`) benar-benar berpengaruh; kalau tidak, impor mengikat nama saat impor dan mock jadi hiasan. Aturan prompt yang dikunci: angka safety-critical hanya dari tool deterministik, safety status tidak pernah di-override, tidak ada auto-execute aksi berisiko tinggi. **Bukti:** `pytest tests/test_supervisor_agent.py` 4 passed (host, strands-agents 1.61.1, Python 3.12.3) + hello-world **LIVE** `us.anthropic.claude-haiku-4-5-20251001-v1:0` **3,4 dtk** akun 624606539664 + `ruff check`/`format` bersih. Batas jujur yang harus ikut dikutip: **belum di-deploy ke AgentCore Runtime** (`AGENTCORE_RUNTIME_ARN`/`AGENTCORE_GATEWAY_URL` masih 0 char) dan orkestrator Event 1 masih **tidak** memanggil agent ini. — bukti `docs/verification/fase-11.md` §2-§3.
- [2026-10-16] **Event 1 penuh punya pemicu di aplikasi, bukan cuma di tes** (lanjutan "tetap di cek bahwa semua berjalan di frontend maupun backend"). `run_event1` sebelumnya hanya dipanggil berkas tes → langkah SUPERVISE tidak pernah muncul di aplikasi yang dilihat juri (`agent_traces`: SUPERVISE 1 baris vs DETECT 83). Yang ditambah: `POST /demo/event1` (`backend/app/api/demo.py`, guard `require_roles("sppg_head","sppg_nutritionist")` + `assert_in_scope` atas **lokasi tujuan**, lokasi tak dikenal → 404, tak ada kandidat → **409** keadaan domain, dijalankan lewat `run_in_threadpool` karena `run_event1` sinkron dan membuka loop sendiri) + `runEvent1()` di `frontend/lib/api.ts` + tombol **"Jalankan Event 1 penuh"** di `OpsConsole` dengan blok hasil (decision id, verdict verifier, forecast, status+provider supervisor, rantai langkah, **narasi supervisor**). Endpoint **tidak** meng-approve/mengeksekusi apa pun. **Jebakan yang benar-benar terjadi saat uji:** handler mula-mula memanggil `onSubmitted` (perilaku lama tombol "Ajukan") sehingga halaman **langsung lompat tab ke Recommendations** dan blok hasil + narasinya hilang sebelum terbaca — diperbaiki dengan prop baru `onDecisionCreated` yang hanya menyegarkan feed, TANPA memindah tab; dijaga tes wiring karena jebakan ini tidak terlihat di tes SSR mana pun. Bukti jalur nyata: lewat rewrite Next `POST :3010/demo/event1` → **201 dalam 26,2 dtk**, keputusan `proposed`, supervisor `narrated` `primary:sap_ai_core`, 7 langkah DETECT→…→SUPERVISE; di layar (:3010 akun SPPG Head) halaman tetap di Demo Control + pesan sukses tampil. Gerbang: backend 863 passed/3 skipped + ruff; frontend 710 passed (1 gagal = `proxy-roots`, bukan dari perubahan ini — lihat entri berikutnya) + tsc 0 + lint 0. — bukti `docs/verification/fase-11.md`.
- [2026-10-16] **Proxy dev Next memutus koneksi di 30 detik — pipeline Event 1 butuh ~28 detik, jadi klien melihat kegagalan padahal keputusan SUDAH tersimpan.** Akar masalah terukur, bukan dugaan: `node_modules/next/dist/server/lib/router-utils/proxy-request.js:31` memakai `proxyTimeout || 30000` dan Next 14.2.14 menerima `experimental.proxyTimeout` (tervalidasi di `config-schema.js`). Gejalanya menipu: lewat `:3010` klien dapat `socket hang up`/500 "Internal Server Error", sementara di DB keputusan lahir lengkap 7 langkah termasuk SUPERVISE (pernah terjadi pada keputusan `5ea17278`) — **jangan menyimpulkan "orkestrator gagal" dari kegagalan HTTP di origin aplikasi tanpa memeriksa DB lebih dulu.** Perbaikan: `experimental.proxyTimeout: 180000` di `frontend/next.config.js` + restart kontainer frontend (perubahan config dibaca saat proses mulai, bukan saat request). Terukur sesudahnya: 26,2 dtk → 201. — bukti `docs/verification/fase-11.md` §4.3.
- [2026-10-16] **Revisi UI lanjutan — TAHAP 1 (Overview): ukuran BENTUK, bukan teks** (permintaan pemilik: "banyak bagian shape yang berisi teks yang ukurannya terlalu besar atau UI-nya terlihat sangat jelek… sapu menyeluruh 3 peran + rapikan kartu yang kebesaran/kosong"). **Diagnosis dengan mengukur, bukan menebak:** skala tipografi sudah bersih dari Fase 8–9 (sapuan 3 peran × 11 tab: teks terbesar 36 px = angka hero, sisanya ≤24 px), jadi tersangka utamanya adalah PEMBUNGKUSNYA. Terukur sebelum: lencana "PENDING APPROVAL" **120×42 px** & "VERIFIER FLAGGED" **136×42 px** untuk teks 12 px (membungkus dua baris di kolom sempit), kotak legenda peta **300×137 px** menutupi kanvas 752×460, kartu grafik **448 px** berisi SATU batang, Telemetri Node 237 px + Status Lokasi 203 px berdiri sendiri-sendiri. **Perbaikan (5 berkas):** (1) `.badge` dapat `white-space: nowrap` + `flex: none` + `line-height: 1.35` → **142×22 px** — `flex: none` WAJIB, tanpa itu badge menyusut di baris flex dan labelnya membungkus lagi; `.node-badge` ikut 12 px (dulu 13) supaya satu bahasa; (2) legenda peta jadi **chip lipat "Legenda peta" 103×24 px** (`map-legend-toggle`, `aria-expanded` + `aria-controls="map-legend-panel"`), isi TIDAK dihapus dari DOM — hanya `display:none` saat tertutup sehingga keluar dari pohon aksesibilitas sekaligus tetap satu klik lagi (terverifikasi: dibuka → `display:flex`, tinggi stack 154 px; ditutup → `none`); (3) grafik batang tingginya **mengikuti jumlah lokasi** (`--chart-h` = 96 + 34×n, dijepit 180–380, `maxBarSize` 26) → kartu 448 → **248 px**; **jebakan yang ketemu saat verifikasi: `.stock-chart-holder { height: 380px }` di CSS memaku tinggi holder sehingga `height` child tidak berpengaruh — tinggi harus lewat CSS var yang dipasang komponen**; (4) Telemetri Node + Status Lokasi jadi sepasang `.overview-pair` (grid 2 kolom ≥1100 px) → 440 → **223 px**; (5) jarak di dalam kartu ringkas dirapatkan (padding 14, gauge gap 8). **Hasil terukur (1440 px, SPPG Head/Overview): tinggi dokumen 2256 → 1826 px (−19%); 0 luapan di 375/768/1280/1440 px;** tsc=0, tes 710 lulus (1 gagal = `proxy-roots`, pekerjaan sesi lain yang masih berjalan), harness `…\scratch\verif-tahap1.py` + `ukur-overview.py`. **Belum ada commit/push.** Sisa Tahap 2 (belum dikerjakan): lencana/pil di halaman lain (`.today-badge`, `.board-badge`, pil header), kartu besar-kosong di Hari Ini/Keamanan Pangan/KPI, dan duplikasi Status Lokasi vs tabel Rincian Pasokan per Lokasi di Overview. — dokumen: `docs/design.md` §3.1 & atrium Overview, `_qa/rencana-redesign-ui.md`.

- [2026-10-16] **Keamanan Pangan jadi halaman BER-CAKUPAN untuk kepala SPPG (Fase 11)** — permintaan pemilik: "coba anda terapkan semua saya mau lihat tapi tolong fitur tetap harus berjalan dengan backend dan database yaa supaya data akurat". Terukur SEBELUM di akun SPPG Jakarta: daftar LINTAS LOKASI (tile 6 aman/1 gagal; tabel 7 baris dari 7 kota; "perlu segera dipakai" = Palembang & Semarang) padahal perannya terkunci satu SPPG, sementara `/batches` memang lintas lokasi (sengaja, dipakai panel chaos — catatan audit 2026-10-11). SESUDAH: (1) cakupan "Lokasi saya — Jakarta" jadi default peran SPPG + chip "Semua lokasi (pengawasan)" DI KEPALA KARTU TABEL (bukan baris filter selebar halaman — picker komoditas sudah dihapus atas permintaan sebelumnya); (2) kartu "Pasokan masuk menuju Jakarta" dari `GET /supplier-routes` (Supplier A Cianjur → Jakarta · telur 800 kg · 110,4 km jalan · ±84 menit · 1,41× jarak lurus · mutu Aman) + satu kalimat cakupan dari `GET /balance/map`: "Kebutuhan 1.080 kg · tersedia 300 kg → kurang 780 kg; kiriman 800 kg menutup kekurangan (+20 kg)"; (3) kolom LOKASI → ASAL (nama pemasok dari rute) saat ber-scope sendiri; (4) masa layak diterjemahkan jadi chip keadaan (Kedaluwarsa / ≤48 jam / ≤7 hari) — bukan cuma "kesegaran 0%" — chip hanya muncul untuk keadaan yang perlu ditindak; (5) kartu "Keputusan keamanan lokasi ini" dari feed `/decisions` ber-scope (terukur: 83 keputusan · 4 masih berlaku · 1 ditolak · 79 lewat jendela · 2 menunggu persetujuan · total 41.730,45 kg) + "Buka Decision & Evidence"; (6) peringatan gagal-uji kini tahu dampaknya: "Batch gagal uji di jaringan: Surabaya — bukan stok lokasi ini, jadi tidak memengaruhi alokasi Anda". **DUA JEBAKAN TERUKUR:** (a) `/actions/repropose` (`backend/app/api/actions.py:541`) menolak **409** kecuali `status == "rejected"` DAN ada `rejection_reason` — tombol "Ajukan ulang" semula dipasang untuk keputusan kedaluwarsa sehingga UI menampilkan "Tidak bisa mengajukan ulang: HTTP 409"; sekarang `canRepropose = status === "rejected"` dan kalimat kartunya menyatakan aturan itu apa adanya; (b) "Periksa kiriman"/"Uji ulang" membalas **404 HTML dari Next sendiri** ("Tidak bisa memeriksa: HTTP 404: /freshness/evaluate") karena root `/freshness` & `/safety` belum ada di `API_ROOTS` (`frontend/next.config.js`) — pelajaran: setiap path API baru wajib didaftarkan di DUA tempat (`lib/api.ts` + `API_ROOTS`), dijaga tes kontrak `tests/proxy-roots.test.ts`. **Bukti MENULIS ke DB (bukan pratinjau):** klik "Periksa kiriman" → `POST /freshness/evaluate` + `POST /safety/evaluate` → `freshness_score 0,90 → 0,66`, `usable_until 2026-11-07 → 2026-10-25` (dibaca ulang dari `/batches` sesudahnya), pesan layar "Hasil periksa dari server: keamanan PASS · kesegaran 66% · layak s/d 25 Okt"; klik "Ajukan ulang" pada satu-satunya keputusan ditolak → 201 → "Keputusan baru dibuat dari ac5e9710: 3c2331c7 (status: diusulkan)", jumlah keputusan 183 → 184 (iterasi 2, `supersedes_id` terisi). Fungsi murni baru di `frontend/lib/food-safety.ts` (`coverageSentence`, `expiryState`, `incomingBatchId`, `incomingShipments`, `ownLocationRows`, `safetyDecisions`, `sortByDeadline`, `balanceForLocation`) diuji di `tests/food-safety.test.ts`; markup dikunci di `tests/food-safety-board.test.tsx`. Hook `useSupplierRoutes` dapat parameter `forceEnabled` — tab Keamanan Pangan memuat rute kiriman TANPA menambah tab ke `shouldLoadSuppliers` (daftar itu mengatur pin peta di `lib/supplier-pins.ts`). Gerbang: `tsc --noEmit` 0 · `vitest` 711/711 (67 berkas) · `next lint` 0 — belum ada commit/push.
- [2026-10-16] **Peta: kotak "Info map" + estimasi tiba perjalanan kiriman dari DB (Fase 12)** — permintaan pemilik: "untuk teks legenda map ganti menjadi info map … lalu ketika mengaktifkan jalur kiriman tampilkan juga waktu estimasi sampai … pastikan sinkron dengan database"; setelah ditanya pemilik memilih **membuat jam berangkatnya nyata di DB** ("pakai perhitungan waktu yang sesuai dengan realnya"), bukan ETA bersyarat. Temuan sebelum perubahan: `GET /supplier-routes` mengirim `batch_id: "None"` untuk SEMUA rute (endpoint tidak memilih `Batch.id`; `str(None)`) sehingga identitas kiriman hilang, `harvested_at` tidak pernah dikirim, dan **DB tidak punya jam keberangkatan sama sekali**. Perubahan: migrasi `015_batch_dispatch` (`batches.dispatched_at` NULL = belum berangkat + CHECK `dispatched_at >= harvested_at`, estimasi tiba TIDAK disimpan), seed kanonik dapat `dispatch_offset_hours` (Jakarta −1 jam dari REF → tiba +24,3 menit dari REF = "di jalan"; Surabaya −5 jam → tiba +4 jam; Cianjur/Bogor sudah tiba; **Bandung NULL = belum berangkat**), `journey` + `summary.journey_states` di `/supplier-routes`, modul murni `app/core/journey.py` dengan aturan "tanpa jam berangkat → TIDAK ada estimasi" dan "sudah berangkat tapi jalur jalan belum tersinkron → `tidak_diketahui`, bukan diklaim tiba". UI: chip + `aria-label` jadi **"Info map"**, isi mengikuti lapisan yang hidup, entri "gagal uji" hanya bila ada kiriman bergaris gagal, blok "Perjalanan kiriman" (maks 3 + "+N kiriman lain"), tag bilah rincian `2 jalur kiriman · 1 di jalan · tiba terdekat ± 22.54`, popup garis menambah jam berangkat/ETA/sisa menit/batas layak — nol aritmetika waktu di peramban. Gerbang: backend 900 passed/3 skipped (2 merah `test_kpi_*` = **residu demo**: 1 keputusan `executed` 15:42 UTC dari sesi sebelumnya), frontend **736 passed / 67 berkas**, `tsc` 0, `next lint` 0. Bukti: `docs/verification/fase-12.md`. **Untuk demo**: dengan REF kanonik 8 Okt semua terbaca "sudah tiba" (jujur) → tekan "Segarkan ke hari ini" agar ETA hidup.
- [2026-10-16] **Popup jalur kiriman dipangkas (Fase 12b)** — permintaan pemilik: *"Jarak lurus: 78,4 km, Tiba sebelum batas layak (25 Okt 2026) dan ini Jalur jalan 1,41× jarak lurus (jalan berkelok, bukan garis lurus) hapus saja."* Dihapus dari `routePopupLines`/`routeEtaLines`: baris `Jarak lurus: …`, baris rasio `1,41×`, kalimat `Tiba sebelum batas layak (…)`. Fakta tidak hilang: tanggal layak pakai tetap tertulis sekali di `Layak dipakai s/d 7 Nov 2026`, dan `straightKm`/`ratioVsStraight` tetap dikirim server (halaman Keamanan Pangan & kartu Kiriman memakainya). **Peringatan `Estimasi tiba melewati batas layak pakai` SENGAJA dipertahankan** — menandai masalah nyata, sedangkan yang dibuang adalah kalimat menenangkan; tawarkan lagi kalau pemilik ingin itu juga hilang. Alasannya konsisten dengan aturan lama: yang dihapus adalah derajat presisi yang tidak mengubah keputusan pembaca peta. Diuji di dua tingkat: murni (2 tes menuntut ketiadaan) + DOM popup yang dirender (klik garis palsu di `tests/supply-map-layer.test.tsx`, tiruan `FakePopup` kini `setLngLat`/`addTo` + `popupLog`). Gerbang: frontend 773 lulus / 69 berkas, `tsc` 0, `next lint` 0.
- [2026-10-16] **Lanjutan Fase 11 — dua butir sisa dipasang ("sekarang lanjutkan")**: (6) kartu **"Penerimaan barang"** (`ownLocation && batchOpsi.length > 0`): lima titik periksa petugas via `RECEIVING_CHECKS`, pemilih batch default = kiriman yang sedang datang bila bisa dipasangkan ke batch nyata (`incomingBatchId`; rute sering tanpa `batch_id`), tombol "Catat hasil terima & hitung ulang" → `onRecheck` (dua endpoint evaluate). **Keputusan sadar: daftar periksa TIDAK dipersistensikan** — backend tidak punya kolomnya; mengarang penyimpanan = berbohong, yang tersimpan ke DB adalah hasil hitung ulang. Terukur: menandai 2 → "2 dari 5 titik periksa sudah ditandai — tandai sisanya sebelum barang dipakai."; klik → DB `freshness_score 0,90 → 0,65`, `usable_until 2026-11-07 → 2026-10-25`, pesan "Hasil dari server: keamanan PASS · kesegaran 65% · layak s/d 25 Okt, 14.56". (7) tombol **"Ajukan keputusan"** per baris tabel — HANYA untuk baris gagal uji (`row.tone === "danger"`) → `POST /events/safety-disruption` (Event 3, akar `/events` sudah ada di `API_ROOTS`): batch gagal → 201 keputusan `safety_disruption` + bukti suhu + jejak; batch aman → 200 `no_disruption` dan layar bilang "tidak ada keputusan baru" (tidak mengarang keputusan). Terukur di Jakarta: klik pada baris gagal Surabaya → "Keputusan penanganan dibuat: 0f230339 (status: diusulkan) — menyasar Jakarta", keputusan 188 → 189, kartu keputusan 85 → 86. **DUA ATURAN EVENT 3 YANG DIPEGANG:** (a) `operation_key` = kunci idempotensi per batch — dibuat sekali per batch di komponen (`useRef`), dikirim ULANG saat mengulang supaya server melayani dari catatan (`_find_replay`) dan bukan membuat keputusan kembar; kunci beda untuk batch sama = keputusan baru, kunci sama untuk batch beda = 409; (b) `target_location_id` diambil dari `/auth/me` (`me.location_id`) — WAJIB lokasi pemakai sendiri (ruling 2026-10-14); batch pemicu boleh milik lokasi lain (sisi sumber), jadi tombolnya tetap boleh muncul di cakupan jaringan. Tes: `food-safety.test.ts` 39 (fungsi murni `RECEIVING_CHECKS`/`receivingState`/`receivingSentence`) + `food-safety-board.test.tsx` 16 (kartu penerimaan menyatakan batas peran, tombol hanya baris gagal). Kelas CSS baru: `.safety-pick`, `.safety-checks` (matikan `::before` titik amber `.board-list` — titik itu berarti "mendesak", bukan "sudah diperiksa"), `.safety-row-actions`. Gerbang: `tsc --noEmit` 0 · `vitest` 736/736 (67 berkas) · `next lint` 0 — belum ada commit/push.
- [2026-10-16] **Informasi pengiriman: riset pembanding industri + Arah A "Kartu Kiriman" dibangun** — permintaan pemilik: "untuk informasi pengirimannya anda harus research cari referensi yang bagus dari web atau apps yang sudah ada, apa aja info yang diberikan dan tampilan UI-nya gimana supaya enak dibaca". Riset 11 sumber BERSITASI (`docs/research/informasi-pengiriman-industri.md`): Oracle OTM Shipment Visibility (daftar field + bagan Route and Status: simpul hijau ≤30 mnt / kuning 30–60 / merah >60 / ABU = belum ada kejadian, garis antar-simpul memuat jarak + waktu tempuh, putus-putus = belum ditempuh), Baymard (6 detail wajib halaman pelacakan; pakai "tanggal tiba", bukan "kecepatan kirim"), NN/g (16 panduan: info terbaru paling menonjol, bahasa manusia tanpa jargon backend, pembaruan lama tetap bertanggal, progres vertikal untuk riwayat panjang), Gojek Engineering ("Why We Killed the Live Map": stepper menggantikan peta live, lima realitas, warna = makna), FourKites/project44/Shippeo (ETA per-perhentian, klasifikasi akar penyebab, ambang suhu per kiriman, dan yang paling berguna: **bedakan "feed pengangkut hilang" dari "kiriman memang terlambat"**), SAP Fiori (Track Freight Orders, Monitor Shipment Milestones, POD). Temuan inti: **datanya sudah ada, penyajiannya yang terpecah** — 7 dari 9 angka perjalanan (`progress`, `elapsed_min`, `remaining_min`, `arrives_before_usable_until`, …) sudah dikirim server tetapi belum pernah dipakai UI; informasi kiriman hidup di tiga tempat yang saling tidak menyapa (popup peta, satu kolom teks tabel Pemasok, satu tag kecil). Pemilik memilih **Arah A (Kartu Kiriman)** dari tiga arah yang diajukan. Yang dibangun: `frontend/lib/shipment-card.ts` (murni, 32 tes) + `frontend/components/ShipmentCard.tsx` (5 tes kontrak SSR) + blok CSS `.shipment-*`, dipasang di tab Overview dan halaman Pemasok. Empat lapis: pil status (`Di jalan · 20 menit lagi`) → stepper `Dipanen/Berangkat/Di jalan/Tiba` → satu baris angka kunci (`110,4 km jalan · ± 1 jam 24 menit · 800 kg telur`) → kalimat keputusan + rincian di balik `<details>` (bekerja tanpa JavaScript, isinya tetap di DOM saat tertutup). **DUA KEJAHATAN DATA YANG DITOLAK:** (a) jalur belum tersinkron → yang ditulis jarak LURUS berlabel "lurus (jarak udara)" + sebab dari `road_missing_reason`, bukan "0 km", dan waktu tempuh tidak diklaim; (b) simpangan "terlambat N menit" TIDAK ditampilkan karena model kita belum punya waktu tiba yang dijanjikan — angka simpangan apa pun akan karangan (pelajaran Shippeo: "belum ada data" ≠ "terlambat", keduanya butuh tindakan berbeda). Terukur sesudah (1440 px, data seed 1 kiriman): kartu **1140×223 px** tertutup → **401 px** saat rincian dibuka; satu blok kiriman **128 px**; pil `Sudah tiba 19.24` **111×22 px satu baris** (mengikuti aturan `.badge`); luapan horizontal **0 px** di 375/768/1280/1440 px. Gerbang: `tsc` 0, suite frontend **773 passed / 69 berkas**. Sisa yang disengaja: tab Keamanan Pangan belum memakai kartu ini (kartu "Pasokan masuk" di sana punya aksi "Periksa kiriman" dan berkasnya sedang disunting sesi lain) dan Arah B (papan kiriman) belum dikerjakan. — bukti `docs/design.md` bagian "Kontrak kartu Informasi pengiriman"; angka ukur di `C:\Users\User\AppData\Local\hermes\cache\scratch\ui-audit\kiriman-hasil.json`.
- [2026-10-16] **Revisi UI lanjutan TAHAP 2 — pil, lencana, dan kartu yang direntangkan** (lanjutan Tahap 1, permintaan pemilik "banyak shape berisi teks yang ukurannya terlalu besar"; pemilik memilih "lanjut ke tahap 2"). Ukur SEBELUM dulu (bukan menebak) di 4 tab peran SPPG Head: pil kepala 32 px untuk teks 12–13 px di Hari Ini ("Jumat, 16 Oktober 2026" 173×32), KPI ("Periode 15 Okt…" 240×32), Keamanan Pangan ("1 batch" 74×32), Pemasok; lencana `.today-badge` 26 px/13 px (satu-satunya lencana 13 px di app); dan yang paling parah: kartu "Batch perlu segera dipakai" **562×423 px dengan isi hanya 72 px (17% berisi)** karena `.board-grid` merentangkan kartu setinggi tetangganya. Tiga perbaikan: (1) `.commodity-pill` → `padding: 2px 10px; font-size: --fs-1` = **22 px** (pil penyaring komoditas 13 px = 24 px), dengan **pengecualian penting**: pil kepala halaman adalah TEKS STATIS (span) sehingga `.page-header-pills > .commodity-pill` diberi `min-height: 0` + `cursor: default` — kalau tidak, aturan target sentuh `@media (pointer: coarse)/≤720px` menaikkannya ke 44 px dan pil teks mati itu terlihat seperti tombol raksasa; kontrol yang benar-benar ditekan TETAP 44 px di 375 px (terverifikasi). **Jebakan yang ketemu saat verifikasi:** menambah `line-height: 1.35` di aturan dasar membuat pil penyaring komoditas Overview naik 30 → 33 px (karena `.filter-card .commodity-pill` mendeklarasikan 14 px + 6px 14px sendiri dan sebelumnya mewarisi line-height kecil) — diperbaiki dengan memberi aturan itu geometri eksplisit (13 px + 2px 10px → 24 px). (2) `.today-badge` disamakan dengan `.badge` (12 px, satu baris, `flex: none`) → 26 → **22 px**. (3) `.board-grid { align-items: start }` → kartu kosong kembali setinggi isinya: "Batch perlu segera dipakai" 423 → **117 px** (17% → 61% berisi); efek samping bagus: tabel "Rincian per run" KPI 532 → 401 px. **Gerbang:** tsc 0 · suite frontend **774 lulus / 69 berkas** · luapan horizontal **0 px** di 375/768/1440 px untuk 9 tab. **Yang diperiksa lalu sengaja TIDAK diubah:** duplikasi kartu "Status Lokasi" vs tabel "Rincian Pasokan per Lokasi" di Overview — terukur keduanya **89% berisi** (223 px, isi 199 px), jadi bukan kartu kosong; menghapusnya keputusan produk, bukan perbaikan kepadatan (menunggu keputusan pemilik). — angka ukur: `C:\Users\User\AppData\Local\hermes\cache\scratch\ui-audit\t2-sebelum.json` vs `t2-sesudah2.json` + `t2-lebar.json`; aturan tercatat di `docs/design.md` §"Tahap 2".
- [2026-10-16] **Halaman Pemasok dirapikan (Fase 12c)** — permintaan pemilik: *"pada halaman pemasok anda gunakan skill ui ux dan anda susun supaya tampilan nya rapih dan enak di lihat user dan pastikan shape teks harus enak di lihat juga tidak kebesaran maupun ke kecilan"*. **Ukur dulu (bukan tebak), akun SPPG Head, viewport 1262 px** (`(max-width: 1280px)` aktif saat pengukuran; aturan CSS yang ditambah top-level → berlaku di semua lebar) **— keadaan SEBELUM:** tabel 9 kolom **1025 px di dalam wadah 913 px** (wajib geser ke samping), kolom "Hub"+"Koordinat" sendiri-sendiri = 178 px dari 913 px, `.shipping-tag` memuat KALIMAT PENUH ("Sedang mengirim · 1 kiriman · 600 kg · s/d 1 Nov 2026 · 1 gagal uji") sehingga membungkus **3 baris, 186×63 px** — jadi bentuk terbesar di barisnya — sementara `.reach-tag` 13 px/24 px (dua bentuk label, dua ukuran, tidak ada standar); tinggi baris **74 / 79 px tak rata**; kartu "Ringkasan" duduk di grid 2 kolom tanpa tetangga → **466 px dari 947 px**, 7 baris fakta memanjang. **SESUDAH — tiga perubahan:** (1) **kolom dilebur**: "Hub" + "Koordinat" pindah jadi baris kedua sel "Pemasok" (`supplierMetaLine`, murni: "Surabaya · -7,2395 / 112,7731") → tabel **7 kolom**, **913 px = 913 px, 0 geser**; (2) **satu standar bentuk label** untuk `.reach-tag`/`.shipping-tag`/`.shipping-tag-fail` (12 px, `padding: 2px 8px`, `inline-flex`, `white-space: nowrap`, `text-overflow: ellipsis`) → semua pil **22 px** (sama dengan pil kepala halaman), tidak pernah membungkus; kalimat penuh pindah ke `title`; pil jangkauan cukup menulis keadaannya ("di luar jangkauan") karena km-nya sudah ada di kolom **Jarak** persis di sebelahnya (`directoryReachTagLabel` — supaya angka yang sama tidak ditulis dua kali); (3) **Ringkasan selebar halaman** (`.board-grid` + `.supplier-summary`), 7 fakta jadi kotak **296×38 px** dalam grid `auto-fit minmax(240px, 1fr)`. **Hasil ukur:** tinggi baris **54 px untuk 34 dari 35 baris** (1 baris 65 px — memang punya dua pil: "Mengirim 1 kiriman" + "1 gagal uji"), tabel **2386 → 1925 px**, halaman **3669 → 3046 px**, kartu Ringkasan **466×392 → 947×226 px**, pil kiriman **63 → 22 px**. **Skala tipografi halaman diaudit ulang:** hanya 12 / 13 / 14 / 20 px yang terpakai (sel tabel 13, meta & pil 12, judul kartu 14, h1 20) dan **tidak ada satu pun teks di bawah 12 px** — ini yang dibuktikan untuk permintaan "tidak kebesaran maupun kekecilan", bukan kesan mata. **Dua cacat kecil yang ikut ditutup:** `text-wrap: pretty` pada kalimat penjelas halaman (dulu menyisakan satu kata menggantung: "…usul eksklusi / baru") dan `routeCellLabel` melepas kata " jalan" (nama kolomnya sudah "Jalur kirim", asal-usul OSRM tetap di `title`) — pelepasan itu memberi kolom Status **35 px** tambahan sehingga pil status berhenti turun ke baris kedua. **TDD:** `shippingTagLabel` (pil ringkas + `title` kalimat penuh), `supplierMetaLine` (hub · koordinat, "—" tidak menggantung), `directoryReachTagLabel` (keadaan, bukan angka) ditulis sebagai tes gagal lebih dulu, baru implementasi; markup dikunci di `tests/supplier-board.test.tsx` (kolom Hub/Koordinat tidak ada lagi, pil kiriman satu baris, pil gagal uji berkelas sendiri, Ringkasan berkelas `.supplier-summary`). **Gerbang:** frontend **792 lulus / 69 berkas** (naik dari 774), `tsc --noEmit` 0, `next lint` 0; live :3010 **0 error baru selama 9 detik** setelah HMR (40 entri lama = `AbortError` permintaan ubin peta saat peta Overview dilepas, bukan cacat halaman ini) — belum ada commit/push.
- [2026-10-16] **Keputusan pemilik: tabel "Rincian Pasokan per Lokasi" DIHAPUS dari Overview** (pemilik: "no 3 hapus Rincian Pasokan per Lokasi", setelah saya laporkan bahwa kartu "Status Lokasi" dan tabel itu menyajikan angka yang sama — keduanya 89% berisi, jadi pilihan yang benar memang menyisakan SATU penyaji). Yang dihapus: blok `<section aria-label="Rincian pasokan per lokasi">` di `app/page.tsx` + importnya, dan berkas `components/OverviewLocationBreakdown.tsx`, `components/OverviewLocationBreakdown.module.css`, `tests/overview-location-breakdown.test.tsx` (ketiganya masih terlacak di git → bisa dikembalikan). Kartu "Status Lokasi" (daftar ringkas + legenda warna) DIPERTAHANKAN. **Ikutan yang wajib:** teks aksesibilitas `StockChart` dulu berbunyi "Angka rinci per lokasi ada di tabel Rincian Pasokan per Lokasi" — diubah menjadi "…di kartu Status Lokasi"; teks bantuan yang menunjuk elemen yang sudah tidak ada itu lebih buruk daripada tidak ada teks. — tsc 0; suite frontend ikut turun sebesar tes milik komponen yang dihapus (bukan regresi).
- [2026-10-16] **Tahap 2 (lanjutan) — orphan kata di daftar "Hari Ini" diperbaiki.** Terukur sebelum: `.today-row-meta` "250 kg · kesegaran 0% · lolos uji" membungkus dengan baris terakhir hanya **18 px** (kata "uji" sendirian) karena pil "Lewat N hari" di kolom kanan (grid `1fr auto`) menyempitkan kolom teks; sesudah `.today-row-meta`/`.today-row-title` diberi `text-wrap: pretty`: baris terakhir **58 px** ("lolos uji" utuh). Sengaja CSS-only (tanpa menyentuh fungsi penyusun teks) supaya tidak ada tes yang rusak dan teks tetap utuh di peramban lama. — ukur: `scratch/ui-audit/t2-wrap-*.json` (3 lebar), tangkapan `t2-wrap-sesudah.png`.
- [2026-10-16] **Cara kerja yang diminta pemilik untuk lanjutan: BERTAHAP** ("no 4 kerjakan bertahap") — sisa daftar: (b) selesai, (c) kartu kiriman Arah A di tab Keamanan Pangan (tunggu sesi Hermes lain yang menyentuh `FoodSafetyBoard.tsx`), (d) Arah B papan kiriman.
- [2026-10-16] **Kartu kiriman (Arah A) masuk ke tab Keamanan Pangan — MENGGANTIKAN daftar ringkas "Pasokan masuk".** Alasannya sama dengan keputusan Overview di atas: daftar lama menyajikan angka jalur yang SAMA dengan kartu (jarak jalan, waktu tempuh, rasio, mutu, masa layak) dan halaman ini belum punya TAHAP perjalanan. Jadi bukan ditambahkan (jadi dua penyaji angka), melainkan menggantikan. Tombol "Periksa kiriman" tidak hilang — dipindah menempel pada kirimannya lewat prop baru `action`; penyaring cakupan juga tetap SATU aturan dengan hitungan `masukKg` (predikat `hanyaKeLokasi` dipakai dua tempat). Kontrak `ShipmentCard` bertambah: `hanya` (saring sebelum pilih; baris di luar cakupan TIDAK dihitung `hidden`), `empty` (pesan pengganti; tanpa itu kartu tetap tidak dirender), `action` (tindakan per kiriman). Logika penyaring ditaruh di `pickShipments(rows, maks, hanya)` yang murni + diuji, BUKAN di JSX, supaya angka "+N lain" ikut tersaring. Tes: 7 tes baru (5 murni + 3 kontrak; 1 di antaranya memperbarui tes lama). Satu ekspektasi tes lama diubah dengan sadar: `"84 menit"` → `"1 jam 24 menit"` — angka server 84,3 menit yang sama, kini lewat `durationLabel` (jam+menit) seperti kartu lain; bukan regresi. **Gerbang:** tsc 0 · suite frontend **801 lulus / 68 berkas** · terukur di app hidup: kartu 1140×264 px, 1 kiriman, 4 tahap stepper, tombol + panel rincian ada, teks lama "… jalan · … mutu …" 0 kemunculan, hanya SATU judul "Pasokan masuk…", luapan 0 px di 1440 & 375.
- [2026-10-16] **Catatan kerja: tabrakan dengan sesi Hermes lain saat menyentuh `FoodSafetyBoard.tsx`.** Sesi lain menulis berkas itu tepat sebelum saya mulai (mtime 23:54:46 → 23:55:18, ukuran 33.648 → 34.353 B); saya menunggu sampai tenang (mtime tetap 23:55:54 selama 2,5 menit), lalu tetap berjaga: (a) snapshot berkas ke `scratch/fsb-snapshot-2359.tsx`, (b) hanya memakai patch berbasis pencocokan teks (tidak pernah menimpa seluruh berkas), (c) membandingkan snapshot vs hasil akhir — selisihnya HANYA perubahan saya (2 import + 1 predikat + 1 blok kartu), jadi tidak ada pekerjaan mereka yang hilang. Pelajaran: saat repo dikerjakan dua sesi, urutannya = cek mtime → tunggu tenang → snapshot → patch (jangan write_file) → diff.
- [2026-10-16] **Opsi "Lainnya" di kartu "Penerimaan barang" (permintaan pemilik) — migrasi `016_batch_receipts`.** Permintaan aslinya: petugas harus bisa mengisi keadaan yang tidak ada di daftar periksa. Sebelum menulis kode, skema diperiksa dulu: `batches` tidak punya kolom catatan (hanya `temperature_log` JSONB), jadi menyimpan tanpa tabel = mengarang. Keputusan: (1) tabel sendiri `batch_receipts` (id, batch_id FK cascade, `checked` JSONB = snapshot titik periksa, `other_note` TEXT NULL, `recorded_by` FK NOT NULL, `recorded_at` server) — satu batch boleh punya banyak catatan (kiriman ulang/koreksi), kolom di `batches` akan menghapus riwayat; (2) `POST /receipts` (201) + `GET /receipts?batch_id=&limit=` baru di `backend/app/api/receipts.py`; mencatat butuh `MUTATING_ROLES` **dan** `assert_in_scope` (barang diterima di dapur sendiri — batch lokasi lain → 403), membaca bebas untuk semua peran terautentikasi (pengawas nasional); (3) catatan berisi spasi saja disimpan `NULL` supaya layar bisa membedakan "tidak ada catatan" dari "ada"; (4) opsi "Lainnya" SENGAJA bukan titik periksa ke-6 (`RECEIVING_OTHER` di luar `RECEIVING_CHECKS`) supaya kalimat "N dari 5 titik periksa" tidak berubah arti; (5) `checked` dikirim sebagai snapshot LENGKAP 5 titik (bukan hanya yang dicentang) lewat `checkedForReceipt()`. Akar proxy `receipts` ditambahkan ke `API_ROOTS`. **Gerbang:** backend 7 tes baru hijau · frontend 800 lulus / 68 berkas · tsc 0 · lint 0. **Terukur di app hidup (SPPG Head, Jakarta):** catatan 102 karakter "Karung lapis kedua basah kena hujan…" tersimpan → riwayat kartu membaca ulang dari DB → setelah halaman DIMUAT ULANG catatan tetap ada (2 baris riwayat, "2 titik" dan "0 titik"); DB diperiksa langsung: `kemasan=true, suhu=true, warna=false`.
- [2026-10-16] **Arah B "Papan Kiriman" dibangun di halaman Pemasok** (riset §6; pemilik: "lanjutkan"). Sepuluh kolom: Pemasok · Tujuan · Muatan · Jalur · Berangkat · Estimasi tiba · Sisa · Masa layak · Mutu · Keadaan + kontrol urutan "Paling mendesak" (bawaan, memakai `shipmentUrgency` yang sudah teruji) / "Estimasi tiba" / "Batas layak", memakai bentuk pil `.kpi-period` + `aria-pressed` (44 px di perangkat sentuh). **Keputusan produk — papan MENGGANTIKAN kartu ringkas Arah A di halaman ini**, bukan menemaninya (kartu tetap di Overview & Keamanan Pangan). Alasan: kalau keduanya tampil di satu halaman, itu persis pola "dua penyaji angka yang sama" yang sudah dibuang pemilik di Overview. Kolom teks "Jalur kirim" di tabel pemasok TETAP (grain berbeda: per pemasok, bukan per kiriman). Satu baris revert kalau pemilik menghendaki keduanya. **Aturan jujur baru yang diuji:** (a) `Sisa` hanya ditampilkan untuk keadaan `di_jalan` — kiriman "sudah tiba" yang masih membawa `remaining_min` besar (data seed sempat 197 jam!) akan menyesatkan, jadi selnya "—"; (b) sel waktu ringkas "8 Okt 18.00" TANPA tahun + tooltip waktu lengkap `8 Okt 2026 18.00 WIB` — ini yang membuat 10 kolom muat di 1440 px tanpa kolom terpotong; (c) urutan selalu menaruh baris tanpa data di belakang dan memakai nama pemasok sebagai pemutus terakhir (banding eksplisit, bukan `a-b`, karena `Infinity - Infinity = NaN` membuat hasil `sort` bergantung mesin); (d) tanpa geometri & tanpa jarak lurus, sel "—" + sebab dalam tanda kurung kalau server memberikannya. **Terukur:** 1440 px — lebar isi tabel = lebar pembungkus = 1106 px, **tidak ada gulir mendatar**, 10 kolom terlihat penuh (sebelum penyesuaian: 1244 px → kolom Mutu/Keadaan terpotong); 375 px — isi 1065 px digulir di dalam `.board-table-wrap`, luapan halaman 0 px. Ukuran huruf tabel 12 px (lantai tipografi), hanya untuk `.shipment-table`. **Gerbang:** tsc 0 · 27 tes baru (19 murni + 6 kontrak + 2) lulus · suite penuh 848 lulus; 4 merah yang tersisa BUKAN dari perubahan ini: 2 `agenda-wiring` + 1 `today-agenda-calendar` (kerja sesi Hermes lain yang sedang berjalan di `app/page.tsx`) dan 1 `proxy-roots` (sudah merah sebelum perubahan ini).
- [2026-10-16] **Catatan tabrakan (lanjutan): sesi lain memegang `app/page.tsx`.** Saat memverifikasi langkah 4, `tsc --noEmit` sempat melaporkan `agendaErrorText` tidak ditemukan di `page.tsx:406` — ternyata sesi lain sedang menyunting berkas itu pada detik yang sama (import-nya menyusul); menjalankan ulang tsc 15 detik kemudian memberi 0 error. Pelajaran: bila `tsc` gagal pada berkas yang bukan milik pekerjaan kita, JANGAN buru-buru "memperbaiki" — jalankan ulang dulu, dan cek mtime berkasnya.
- [2026-10-16] **Riwayat kejadian per kiriman dibangun (kesenjangan #12 riset)** — di DALAM panel `Rincian kiriman` yang sudah ada, bukan bentuk baru di halaman. Berkas: `frontend/lib/shipment-timeline.ts` (murni) + `frontend/components/ShipmentCard.tsx` + `frontend/tests/shipment-timeline.test.ts` (14 tes murni) + 1 tes kontrak. **Keputusan yang dipegang:** (1) hanya kejadian yang PUNYA WAKTU di server yang masuk daftar — model menyimpan `safety_status` tanpa waktu pemeriksaan, jadi baris "uji mutu" TIDAK dibuat (jangan karang tanggal); (2) estimasi tiba ditandai `kind: "rencana"` → tag "perkiraan" + judul redup, dan kiriman yang sudah tiba menampilkan "Tiba di tujuan" sebagai gantinya; (3) **waktu hitung jalur dipindahkan jadi catatan kaki audit** (`shipmentRouteAudit()`), setelah melihat dampaknya: karena geometri dihitung "hari ini", entri itu duduk di ATAS kejadian "Tiba" (8 Okt) dan garis waktunya terbaca rusak — pelajaran: log sistem jangan dicampur ke garis waktu kejadian fisik; (4) waktu yang tidak terbaca tidak masuk daftar, dan tanpa kejadian bloknya TIDAK dirender (tidak ada blok kosong). **Bug nyata yang ditemukan lewat tangkapan layar (bukan oleh tes):** kolom waktu lebar tetap `16ch` lebih sempit daripada teks "16 Okt 2026 07.00 WIB" → tanggal MENABRAK judul. Perbaikan: satu baris flex (judul kiri, waktu kanan), tanpa kolom lebar tetap. Ini contoh konkret mengapa verifikasi visual tetap wajib walau suite hijau. **Terukur:** 3 baris, tiap baris 46–47 px; kartu terbuka 1140×608 px; luapan halaman 0 px di 1440 & 375; celah judul→waktu 784–845 px (tidak tumpang tindih). **Gerbang:** tsc 0 (kecuali 1 error di `tests/board-scroll-hint.test.ts` milik sesi lain) · ESLint bersih · suite penuh 886 lulus / 888; 2 merah = fitur "petunjuk geser tabel" sesi lain yang belum selesai (`board-scroll-hint`, `scroll-hint`, `scroll-hint-component`), bukan dari perubahan ini.
- [2026-10-16] **Catatan batas data (jangan dipalsukan):** pada data seed saat ini, SATU-SATUNYA kiriman yang tampil di Overview/Pemasok berkeadaan "sudah tiba", jadi tag "perkiraan" di riwayat tidak terlihat di aplikasi hidup walau jalan kodenya terbukti lewat tes kontrak + tes murni. Untuk melihatnya, seed perlu memuat kiriman `di_jalan`/`belum_berangkat`. Dua hal yang masih menunggu karena butuh field backend: riwayat uji mutu berwaktu (butuh `safety_checked_at`) dan riwayat peristiwa suhu/keamanan per kiriman (butuh relasi kejadian→kiriman).

- [2026-10-16] **Petunjuk geser tabel jadi TERUKUR, bukan ditebak (lanjutan F12c).** `.board-scroll-hint` semula hanya `display: block` di `max-width: 640px`, padahal tabel "Daftar pemasok" butuh wadah >= 879 px → tabel bisa digeser tanpa petunjuk. Menaikkan ambang ke 900 px (percobaan pertama) belum menutup semuanya: pada 901–1150 px tabel masih meluap tanpa petunjuk, karena ambang lebar hanyalah PROKSI dari "tabel benar-benar meluap". Sekarang `components/ScrollHint.tsx` mencari `.board-table-wrap` di kartunya dan mengukur `scrollWidth` vs `clientWidth` (toleransi 1 px, `lib/scroll-hint.ts`), lalu menulis `data-tampil="true|false"`; diukur ulang lewat ResizeObserver (wadah + isinya) dan `resize`, jadi tabel yang berubah lebar setelah data dimuat tetap benar. CSS: `.board-scroll-hint { display: none }` + `.board-scroll-hint[data-tampil="true"] { display: block }` — TANPA ambang lebar layar. Dipasang di 7 tempat (Pemasok ×2, Surplus, Mutu Agen, Keamanan Pangan). **Bukti:** 8 lebar viewport (375/640/768/900/901/1100/1262/1440) → 0 pasangan "petunjuk tampil" vs "tabel meluap" yang tidak cocok, luapan halaman 0 px; 901 & 1100 px yang dulu senyap kini disertai petunjuk. **Gerbang:** tsc 0 · ESLint 0 · suite frontend 897 lulus / 0 gagal (tes baru: 4 murni + 4 perilaku komponen + 3 kontrak CSS). **Dikecualikan sengaja dari commit:** `SettingsPanel.tsx` (dua petunjuk di sana tidak ada di HEAD — milik pekerjaan lain yang belum di-commit, jadi meng-commit-nya akan menyapu kerja mereka) dan migrasi token tipografi di `globals.css` (hanya 2 hunk milik pekerjaan ini yang distaging).

- [2026-10-16] **Berat + batas layak kiriman kembali TERLIHAT (lanjutan F12c, langkah 6).** Fase 12c memindahkan seluruh kalimat kiriman ke `title`; yang ikut hilang dari layar adalah dua fakta keputusan (berat kiriman + batas layak pakai) — dan fakta yang hanya terbaca saat hover praktis tidak terbaca di tablet/telepon. Sekarang `shippingMetaLine()` (`lib/supplier-pins.ts`, murni) menulis HANYA dua fakta itu (`1.400 kg · s/d 2 Nov 2026`) sebagai baris kedua sel "Kiriman" (`.shipping-meta` + `flex-basis: 100%` di `.status-cell`, jadi pil 22 px tidak terdorong turun); kalimat penuhnya tetap di `title`. Aturan jujur: berat 0 tidak ditulis "0 kg", tanpa kiriman "—", batas layak yang belum dilaporkan server cukup tidak muncul. Tes markup membuang SELURUH atribut `title` dulu sebelum mencari teksnya — supaya "terlihat" benar-benar berarti terlihat. **Bukti:** 375/768/1262/1440 px → luapan halaman 0 px, teks <12 px nol, pil tetap 112×22 px; 33 dari 35 baris TETAP 54 px di 1262/1440 px (fakta baru tidak menambah tinggi baris); tabel tetap tanpa geser di 1262/1440 px. **Gerbang:** tsc 0 · ESLint 0 · suite 902 lulus / 0 gagal. **Catatan proses penting:** saat commit langkah ini sesi lain menjalankan `git add -A` (140 berkas ter-stage) sampai kunci index bentrok — commit saya dibuat memakai index SEMENTARA (`GIT_INDEX_FILE`), jadi index sesi lain tidak disentuh sama sekali dan hanya berkas pekerjaan ini yang masuk. Pola ini aman dipakai lagi saat dua sesi menyentuh repo yang sama.

- [2026-10-16] **Dua info yang tidak mengubah keputusan dibuang dari papan kiriman.** Permintaan pemilik (menanggapi laporan saya): *"terdapat info yang tidak penting, anda hapus saja, karena user tidak memerlukan info tersebut"*. Yang dibuang: `boardRasio()` + tampilannya (`1,41× jarak lurus`) dan catatan kabar baik `tiba sebelum batas` (kolom "Masa layak" kini hanya tanggalnya) — plus kelas CSS `.cell-tone-ok` yang jadi mati. Yang SENGAJA tetap: peringatan `tiba MELEWATI batas` (itulah yang mengubah keputusan — pola sama dengan F12b), jarak + waktu jalur (`110,4 km jalan · ± 1 jam 24 menit`), dan jejak sumber `OSRM` sebagai label kecil bertooltip ("dihitung OSRM saat sinkronisasi rute, bukan saat papan dibuka"). **Bukti:** penjaga markup `not.toContain` untuk keempat frasa + `toContain("OSRM")`; live 1440/768/375 px → 10 kolom tetap, tabel 1106 = 1106 px tanpa geser di 1440 px, luapan halaman 0 px; tsc 0 · ESLint 0 · suite 955 lulus / 0 gagal.
- [2026-10-17] **Kalender agenda — langkah 3: judul bulan jadi TOMBOL + popup pemilih tanggal (permintaan pemilik).** Keluhan: *"perbaiki fitur kalender yang sekarang karena tidak sesuai ekspetasi saya, saya mau kalender yang mana sebuah icon kecil yang bisa di klik dan menampilkan pop up untuk memilih tanggal bulan tahun"* — dan pemilik meminta RISET dulu ("sebelum membuatnya di frontend anda research dulu"). Temuan awal (browser hidup): `Oktober 2026` adalah `<span>` mati + hanya ‹ ›, jadi melompat setahun = 12 klik; literatur date picker menyebut ini "the single most common date picker sin". Tiga jalur dibandingkan sebelum menulis kode: hand-rolled di atas `Popup.tsx`, `react-day-picker` v9/v10 (`captionLayout="dropdown"`), dan `<input type="date">` + `showPicker()` native (dukungan 97%, tapi isi popup milik peramban dan **tidak bisa menampilkan titik "hari punya catatan"**, `showPicker()` juga absen di Safari iOS). Pemilik memilih **hand-rolled tanpa dependensi baru**, grid besar TETAP, kolom tanggal Demo Control dibiarkan native. Yang dibangun: `components/AgendaDatePicker.tsx` (popup: dropdown Bulan 12 nama Indonesia + Tahun + grid + "Hari ini"/"Tutup") dan `components/AgendaMonthGrid.tsx` (grid dipakai BERSAMA kartu & popup supaya bentuk sel/aria tidak bisa berbeda); `lib/agenda.ts` dapat `monthChoices()` + `pickerYears(fromIso, toIso, keep)`; `useAgenda` dapat saklar `enabled` (kelima) supaya rentang bulan DRAFT hanya diminta saat popup terbuka; `TodayDashboard` menerima SATU prop `agendaPicker` (bukan belasan); `NavIcon` dapat `CalendarIcon` inline SVG. **Aturan yang dipegang:** (1) bulan DRAFT (`agendaPickerMonth`) tidak pernah menimpa bulan kartu (`agendaMonth`) — dibuktikan live: draft ke September 2026 mengisi titik catatan September di popup sementara kartu tetap Oktober; (2) daftar TAHUN berasal dari rentang data backend (`RANGE_MIN/RANGE_MAX` di `lib/demo-data.ts`, 2026–2027) + tahun yang sedang tampil, supaya `<select>` tak pernah menampilkan nilai di luar daftarnya sendiri — bukan angka karangan; (3) bulan yang belum termuat menulis status MEMUAT, bukan grid kosong yang akan terbaca "tidak ada catatan"; (4) fokus kembali ke tombol pemicu saat popup ditutup; (5) memilih tanggal hanya MEMBERI TAHU halaman (`onSelect`) — yang menutup popup adalah halaman, supaya hari & bulan terpilih tetap satu sumber. **Gerbang:** 25 uji baru RED→GREEN (15 di antaranya jsdom dengan klik/dispatch/DOM sungguhan) → frontend **80 berkas / 945 uji hijau**, `tsc` 0, `next lint` 0. **Bukti hidup:** klik 1 Sep dari popup → kartu pindah September 2026, panel "Selasa, 1 September 2026" rencana 1.217 porsi + pasokan 6 baris (cocok dengan catatan langkah 2); Tahun 2027 → grid 30 Agu–10 Okt 2027, 0 hari bercatatan (jujur); Escape → fokus kembali ke pemicu; 0 galat JS baru. Detail: `docs/verification/kalender-pemilih-tanggal.md`. **Catatan sesi:** sesi Hermes lain sedang bekerja di repo yang sama (berkas `??` `lib/route-line-split.ts` berubah saat saya bekerja; satu putaran suite menandai tesnya merah lalu hijau saat dijalankan sendiri) → jangan commit menyeluruh; pakai index sementara bila commit diperlukan.
- [2026-10-16] **Arah C "sorotan kiriman di peta" dibangun** (riset §6; pemilik: "lanjut ke arah C"). Berkas: `frontend/lib/route-focus.ts` + `frontend/lib/route-line-split.ts` (dua-duanya murni) + `frontend/components/RouteFocusPicker.tsx` + `SupplyMap.tsx` (props `focusedRouteId`/`onFocusRoute` + source/layer sorotan) + `app/page.tsx` (satu state `focusedRoute` dikirim ke PETA dan KARTU sekaligus, jadi garis yang menyala dan angka kartu tidak bisa beda cerita). **Keputusan penting:** (1) **tombol pemilih WAJIB ada**, bukan hanya klik peta — garis di kanvas MapLibre tidak bisa difokus keyboard dan tidak ada di pohon aksesibilitas; (2) **popup jalur TIDAK dihapus** walau isinya bersinggungan dengan kartu, karena pemilik sendiri pernah memangkas popup itu di Fase 12b (menghapusnya tanpa izin lebih buruk daripada menanggung tumpang tindih); (3) **gagal-tertutup**: id tak dikenal/kosong = tampilan SEMUA, bukan menyorot kiriman pertama; (4) **sudah tiba → seluruh garis padat** walau `progress` tidak dikirim (keadaan dari server tidak ambigu; menebak 0% akan menggambar perjalanan selesai sebagai "belum ditempuh"); (5) tanpa `progress` & belum tiba → garis utuh putus-putus, dan tanpa geometri jalan tidak ada yang digambar (bukan garis lurus palsu). **Pelajaran teknis yang mahal:** `ROUTE_LINE_WIDTH` di `SupplyMap.tsx` adalah `ExpressionSpecification` (interpolasi zoom), sehingga `ROUTE_LINE_WIDTH + 2` **gagal tipe** (dan kalau dipaksa jalan, peta diam saja) → dibuat ekspresi terpisah `ROUTE_FOCUS_WIDTH`. Juga: `event.features[0].properties.id` bertipe `string | undefined` → pakai `row.id` (hasil pencarian baris) untuk callback fokus, bukan `id` mentah. **Cara verifikasi sorotan (baru, dan layak dipakai lagi):** line layer tidak ada di DOM, jadi dibuktikan dengan **beda piksel** peta, bukan mata: baseline stabil (dua tangkapan tanpa aksi berbeda 45 px), saat disorot muncul **28.584 px** berbeda dan citra bedanya persis mengikuti jalur Cianjur → Jakarta, setelah dilepas beda di area jalur hilang (sisa 27.797 px ada di bilah tombol lapisan = teks angka yang berdenyut tiap polling 5 detik). Alat: `cek-pixel-arah-c2.py` (+pillow), bukti `ui-audit/c3-beda-*.png`. **Penting:** md5 tangkapan mentah TIDAK cukup (anti-aliasing/raster ulang membuat md5 selalu beda) — yang dihitung harus jumlah piksel yang benar-benar berubah, plus citra beda untuk memeriksa LOKASI perbedaannya. **Terukur:** pemilih 22 px satu baris @1440, 94 px terbungkus @375 (target sentuh 44 px terjaga), luapan halaman 0 px di kedua lebar; `Semua (N)` memuat jumlah sebenarnya. **Gerbang:** tsc 0 (kecuali berkas sesi lain) · ESLint bersih · 5 berkas tes baru (28 tes) + 6 tes peta baru. **Belum diubah, minta keputusan pemilik:** garis dasar peta digambar putus-putus untuk SEMUA kiriman (`line-dasharray: [2,1.2]`) padahal riset menetapkan putus-putus = "belum ditempuh" — sesudah Arah C kontrasnya mulai terlihat (tersorot padat, sisanya putus-putus). Satu baris CSS bisa mengubahnya, tapi garis dasar muncul di setiap tangkapan demo, jadi tidak saya ubah sendiri.
- [2026-10-17] **Riset UI peta selesai (langkah 7a) — arah desain peta ditetapkan dari referensi industri, implementasi BELUM dikerjakan.** Permintaan pemilik: *"sepertinya anda harus research fitur yang ada di maps ini dengan melihat referensi yang sudah ada baik web atau aplikasi, selanjutnya anda gunakan skill ui ui untuk membuat hasil yang sempurna dari referensi yang anda pilih"*. Hasil: `docs/research/peta-ui-industri.md` (22 sumber di ledger sitasi `grounded-citations`, 14 kutipan verbatim dengan pemeriksaan teks halaman; `sources.py verify` → "citations OK"). **Temuan pembatas yang jujur:** katalog skill `ui-ux-pro-max` TIDAK punya baris panduan bertema peta (3 kueri peta → 0/2 hasil tidak relevan), jadi panduan peta diambil dari sumber peta itu sendiri (dokumen platform, pola map UI, panduan kartografi), sementara skill dipakai untuk aturan yang memang ada (44 px, kontras 4.5:1, fokus keyboard, jangan andalkan warna saja, CLS). **Tiga referensi primer yang dipilih:** Axis Maps Cartography Guide (hierarki visual + interaksi peta), ArcGIS *application layouts* + Map UI Patterns *partial map* (tata letak peta+panel), Admiralty *Find a location* (pola peta+panel dua arah + aksesibilitas peta). Pendukung: Bathyl (kelola lapisan), Google Maps (taksonomi kontrol & kontrol harus elemen HTML asli), NN/g + liputan redesign Google Maps (panel tanpa menutup peta), ISOM/USGS (konvensi garis), W3C/NSGIC (keyboard & padanan teks). **Celah terukur yang ditemukan** (dari `ui-audit/p0-inventaris.json`): kartu peta 752×528 px dari 1440; kontrol bawaan MapLibre 29×29 px, toggle lapisan 26 px, legenda & "Rincian lapisan peta" 24 px — SEMUA di bawah 44 px; tidak ada kontrol skala, tidak ada tombol kembali ke tampilan awal, dan angka operasional "−780 kg" menempel di baris attribution peta. **Keputusan yang saya ambil di riset ini:** popup jalur sebaiknya DIPANGKAS jadi ringkas, bukan dihapus (literatur: tooltip = info singkat, panel tetap = cerita panjang), dan konvensi kartografi mendukung aturan Arah C bahwa putus-putus = belum ditempuh — artinya garis dasar kiriman yang sudah tiba semestinya SOLID; ini masuk daftar keputusan pemilik, bukan saya ubah sendiri. Rencana 3 tahap (7b-1 aman/CSS-terukur → 7b-2 konsolidasi zona kontrol → 7b-3 butuh keputusan pemilik) ada di §6 dokumen riset.
- [2026-10-17] **7b-1 dikerjakan (kontrol peta) — pemilik memilih "kerjakan 7b-1 dulu" lewat pertanyaan pilihan.** Berkas: `frontend/lib/map-view.ts` (BARU, murni: `MAP_RESET_LABEL`, `MAP_RESET_ICON`, `mapResetTitle`), `frontend/components/SupplyMap.tsx` (kontrol `ScaleControl` metrik kanan-bawah + tombol `<button>` "Tampilkan semua" kelas `.map-reset-view` di grup kontrol kanan-atas lewat `map.addControl({onAdd,onRemove}, "top-right")`, dengan `fitAllRef` supaya kontrol yang dibuat SEKALI selalu memanggil fungsi terbaru), `frontend/app/globals.css` (gaya `.map-reset-view`, `.maplibregl-ctrl-scale`, dan blok kontrol peta di `@media (pointer: coarse), (max-width: 720px)`). **Temuan yang mengubah kode lama:** aturan `.map-layer-toggle` MENGAKU "target sentuh 44px tetap berlaku lewat aturan global", padahal `min-height` kelas MENANG atas `button { min-height: 44px }` — chip itu benar-benar 26 px di 375 px (dibuktikan dengan mengukur, bukan membaca CSS). Klaim komentar itu diganti. Juga: kontrol MapLibre sengaja ditahan 29 px dengan alasan "supaya tidak menabrak atribusi" — alasan itu belum pernah diukur; sesudah diukur (kanvas 375 px = 329×318, grup 3×44 px) tidak ada tabrakan, jadi dinaikkan ke 44 px. **Koreksi temuan riset:** dugaan "angka −780 kg menempel di baris attribution" BATAL — attribution memang hanya `© OpenStreetMap contributors`; angka itu label pin yang ikut terbaca karena skrip inventaris pertama membaca `innerText` kontainer peta. **Keputusan turun-temurun yang dipertahankan:** skala ditaruh KANAN-BAWAH (bukan kiri-bawah bawaan MapLibre) karena panggung legenda memakai sudut kiri-bawah; tombol reset memakai `fitBoundsFor()` yang sama dengan tampilan awal (bukan rumus kedua) dan hanya menyertakan jalur kalau lapisannya hidup; `aria-label` = NAMA tombol (tetap) sedangkan `title` = keterangan yang ikut berubah saat data/lapisan berubah (dijaga tes). **Terukur (sesudah):** skala 62×21 px "30 km"; reset 29×29 @1440 → 44×44 @375; zoom/kompas 29→44 px @375; chip toggle 26→44 px; luapan 0 px; tumpang tindih antar kontrol TIDAK ADA (diperiksa berpasangan); kontras terendah tag bilah 4,55:1 (semua ≥4,5:1). **Gerbang:** 11 tes baru hijau (6 murni + 5 kontrak; tiruan MapLibre diperluas dengan `ScaleControl` + pencatatan `onAdd`/`fitBounds`) · ESLint bersih · `tsc` 0 error pada berkas pekerjaan ini (19 error sisa milik pekerjaan sesi lain: `agenda-day-step`, `today-summary*`). Bukti: `ui-audit/p1-ukur.json`, `p1-peta-1440.png`, `p1-kanvas-1440.png`, `p1-kanvas-375.png`.
- [2026-10-17] **Pelajaran mahal dari 7b-1: "terlihat benar" ≠ "bisa diklik".** Tombol "Tampilkan semua" tampil rapi di tangkapan layar, terukur 29 px, dan semua tes unit hijau — tetapi TIDAK BISA DIKLIK. Sebabnya: sudut kontrol MapLibre (`.maplibregl-ctrl-top-right`) memakai `pointer-events: none` dan mewariskannya ke anak; kontrol bawaan MapLibre diselamatkan kelas `.maplibregl-ctrl { pointer-events: auto }` yang DITAMBAHKAN MapLibre, tetapi versi yang terpasang TIDAK memberi kelas itu ke kontrol buatan sendiri. Ketahuan hanya karena Playwright menolak mengklik ("subtree intercepts pointer events") dan `getComputedStyle(...).pointerEvents === "none"`. Perbaikan: satu baris `pointer-events: auto` + tes kontrak CSS `tests/map-controls-css.test.ts` (5 tes) supaya tidak hilang lagi. **Aturan baru yang dipegang: kontrol peta/kontrol baru WAJIB diuji dengan KLIK di aplikasi hidup — mengukur kotak dan memotret tidak cukup.** Cara buktinya juga baru dan layak dipakai lagi: posisi layar pin direkam tiga kali (awal → sesudah digeser+zoom → sesudah tombol diklik) lewat `cek-reset-peta.py`; hasilnya awal `[614,741]` → geser `[201,485]` → reset `[633,731]` (selisih 29 px wajar: peta membingkai ulang saat geometri jalur tiba dengan margin 0,5°, sedangkan tombol reset memakai rumus tampilan awal bermargin 1,6°).
- [2026-10-17] **Desain ulang halaman "Hari Ini": grid bulan besar DIHAPUS dari kartu, status naik ke atas (permintaan pemilik: "hapus untuk kelender agenda yang yang bukan pop up namun untuk informasi nya tetap di pakai … 1 page hari ini harus di desain ulang ui ux nya … fitur tetap … supaya lebih mudah di gunakan oleh user").** Empat keputusan bentuk (dipilih pemilik lewat pertanyaan beropsi, semuanya opsi rekomendasi): (1) `‹`/`›` di kepala kartu bergeser **SATU HARI** + pil "Hari ini" (bukan satu bulan lagi), grid bulan hidup hanya di popup pemilih tanggal; (2) **strip ringkasan 5 tile tombol** di bawah kepala halaman (Menunggu tindakan / Batch <48 jam / Lokasi shortage / KPI terisi / Rantai audit) yang mengklik-nya menggulir + memfokuskan kartu tujuan (`jumpToSection`, id `#today-action`…`#today-ledger`); (3) urutan baru **status → pengecualian → agenda → rincian**; (4) empat kartu rincian pindah ke bento **dua kolom** (`.today-detail-grid`, 1 kolom ≤1180 px) — bobot 7/5 yang merentangkan satu kartu setinggi tetangganya dibuang. Info hari terpilih TIDAK hilang: dikelompokkan tiga tema (`agendaGroups`: Rencana & pasokan / Limbah & kedaluwarsa / Keputusan agen) dan tetap menulis "tidak ada catatan" per baris. Riset yang dipakai: uxpatterns.dev (agenda hybrid), Apple HIG (compact date picker), NN/g + ixDF (progressive disclosure), studi kasus redesain dashboard operasional (buang grafik pasif, sisakan 4–5 indikator + daftar pengecualian); **`ui-ux-pro-max --design-system` DITOLAK** (pola LANDING + palet oranye + Fira, bentrok token repo) — palet/skala tipe tetap milik repo. `updatedLabel`/`kpiPeriodLabel` menulis waktu & periode dari data nyata, bukan tebakan. Bukti: docs/verification/hari-ini-desain-ulang.md.
- [2026-10-17] **Strip ringkasan "Hari Ini" dirapatkan (keluhan pemilik: "ukuran font bagian 5 informasi singkat ... ukuran shape nya kurang pas dan ukuran shape text terlalu besar").** Dipandu skill `ui-ux-pro-max` (`--domain ux` "compact stat tile label value density" → *Compact Label Overflow*: label pendek tidak boleh membungkus; `--domain typography` → "Dashboard Data" Fira Code/Sans = sudah dipakai repo). Terukur: strip **89 → 70 px** (−21%), bentuk **181×89 → 183×70 px**, padding 10/12 → **8/10**, radius 12 → **10**, gap 10 → **8**, angka `--fs-5` 18px → **`--fs-4` 16px bobot 600** (18px terbaca seperti judul di bentuk 181 px), keterangan yang dulu membungkus 2 baris kini **1 baris**, dan kolom jadi **eksplisit 5/3/2** (≥1181 / 768-1180 / ≤767 px) supaya kelima bentuk identik. Luapan 0 px, tidak ada teks terpotong. Bukti: docs/verification/hari-ini-desain-ulang.md §8.
- [2026-10-17] **Nilai 5 tile "Hari Ini" & lencana "Lewat …" dirapikan (keluhan pemilik: "bagian 15, 2, 1, 5/7, dan rantai utuh ... masih kurang pass dilihat tampilannya dan bagian informasi \"lewat jam/hari\" itu masih terlalu kebesaran").** Diperiksa dengan strip dizoom 3x, temuan: nilai "Rantai utuh" memakai font DATA (frasa dalam Fira Code = seperti potongan kode), warna nilai campur (2 merah + 2 kuning + 1 hitam) padahal nada sudah dibawa garis kiri, dan lencana `.today-due` terukur **176x26 px** (mono, padding 3px 10px). Perbaikan: angka tetap Fira Code + `tabular-nums`, frasa pindah ke font UI lewat kelas `.today-tile-value--teks` (dipilih fungsi murni `nilaiAngka()` di lib/today.ts, TDD: 3 uji RED dulu), **warna nilai diseragamkan ke `--ink`** (nada hanya garis kiri), dan lencana jadi **131-138x24 px** (Fira Sans + tabular-nums, padding 2px 8px — mengikuti standar label docs/design.md §3.8). Tinggi strip tetap 70 px, luapan 0. Bukti: docs/verification/hari-ini-desain-ulang.md §9.
- [2026-10-17] **Nilai 5 tile "Hari Ini" dipindah ke KANAN (permintaan pemilik: "taruh di kanan saja 15, 2, 1, 5/7, dan rantai utuh — ini −765,8 kg pada halaman overview").** Acuan = baris `.node-gauge` di Overview (label 12px kiri, nilai Fira Code 13px di kolom kanan, gap 2px 10px). Percobaan pertama DITOLAK: label+nilai sebaris (kolom label menyusut ke 126 px sedangkan "MENUNGGU TINDAKAN" butuh 143 px → dua label membungkus dua baris, baseline nilai tidak sebaris). Yang dipakai: label `grid-column: 1 / -1`, **nilai barisnya sendiri rata kanan** (`text-align: right`, `grid-column: 2`), keterangan `1 / -1` di bawah. Terukur: kelima label satu baris (159 px), nilai rata kanan 11 px dari tepi (= padding 10 + garis 1) dan sebaris sempurna di kelima bentuk, bentuk tetap 183x70 px, tinggi strip 70 px, luapan 0. Bukti: docs/verification/hari-ini-desain-ulang.md §10.
- [2026-10-17] **Nilai tile "Hari Ini" digeser 8 px ke kiri (permintaan pemilik "sedikit ke kiri").** Nilai menempel tepi (11 px = padding 10 + garis 1) → `margin-right: 8px` pada `.today-tile-value` (bukan padding bentuk, agar label/keterangan tak ikut bergeser) → jarak tepi 19 px di kelima tile, tetap sebaris & rata kanan. Label tetap satu baris, bentuk tetap 183x70 px, strip 70 px, luapan 0. Bukti: docs/verification/hari-ini-desain-ulang.md §10.1.
- [2026-10-17] **Nilai kartu KPI Overview ("-765,8 kg", kartu "Selisih pasokan Jakarta") dipindah ke kanan (permintaan pemilik: "bagian ini -765,8 kg di halaman overview tolong di buat di sebelah kanan juga").** Aturan `.overview-kpis .kpi-card`: grid `minmax(0,1fr) auto`, label kolom 1, nilai `grid-column: 2; text-align: right`, foot/mini selebar kartu. DIBATASI ke `.overview-kpis` karena `.kpi-card` dipakai juga oleh halaman KPI (KPIDashboard: `.kpi-card-top`/`.kpi-card-name`/`.kpi-card-flags`) - aturan global akan merusaknya. Terukur: nilai rata kanan 19 px dari tepi kartu (= padding kartu) di KETIGA kartu Overview - sama dengan strip "Hari Ini" (§10.1); tinggi kartu tetap 121 px, luapan 0. Baris "kurang 765,8 kg" di kartu Telemetri Node/Status Lokasi sengaja belum disentuh (teks pemilik berbunyi "-765,8 kg" = bentuk angka bertanda). Bukti: docs/verification/hari-ini-desain-ulang.md §11.
- [2026-10-17] **Riset 7b-3 (lima keputusan peta) SELESAI — RISET SAJA, tidak ada kode yang diubah (permintaan pemilik: "gunakan skills untuk ini, anda lakukan research saja deh dan anda lihat mana yang terbaik di terapan pada mealchain guardian").** Keluaran: `docs/research/7b3-keputusan-peta.md` (6 sumber bercatatan, ledger sitasi diverifikasi). Rekomendasi: **K1** garis padat = sudah ditempuh, putus-putus = sisa/perkiraan (satu arti dengan legenda; sekaligus memperbaiki klik popup — terukur 8 klik tepat di piksel garis, hanya 1 membuka popup); **K2** JANGAN melebarkan peta — terukur `.overview-split` 1140 px dengan `grid-template-columns: 752px 376px`, peta sudah 2,0× kolom keputusan (66,7%); **K3** daftar penanda ringkas (nama·status·selisih, BUKAN tabel pasokan/kebutuhan) + padanan sr-only, karena `showStatusList={false}` mematikan daftar teks di Overview dan penanda peta tidak masuk urutan Tab; **K4** JANGAN memangkas popup lagi (terukur 240×176 px, 165 huruf, 5 baris — sudah semua fakta yang dipakai memutuskan; cukup gabung 2 baris jam jadi 1); **K5** tambah 2 kiriman seed backend (satu "di jalan" progres ~40%, satu terlambat/batal) — tanpa itu garis "sisa perjalanan", tag "perkiraan", dan alur keputusan dari peta tidak bisa diperagakan (pemilih sekarang hanya 1 kiriman "Sudah tiba 19.24"). Tidak diambil dari aplikasi peta lain: geocoder, ganti basemap, alat ukur manual, clustering, peta layar penuh (alasan per butir ada di §7 memo). Urutan usul: K5 → K1 → K3 → K4; K2 tidak dikerjakan. Catatan keadaan: Overview kini ditulis ulang sesi lain menjadi `.overview-split` (peta + "Perlu keputusan" 4 butir), lapisan pemasok MATI secara bawaan (`useState(false)`, ambang zoom 6/8) — angka diukur 11.05-11.15 WIB, ukur ulang bila halaman berubah lagi. Bukti angka: `ui-audit/p5-bahan-7b3.json`, `p5-popup.json`, `p5-kanvas-garis.png`, `p5-popup.png`, `p5-overview.png`; skrip `ukur-7b3-bahan.py`, `ukur-7b3-popup.py`, `ukur-7b3-garis.py`, `ukur-7b3-kolom.py`.
- [2026-10-17] **Batas pengukuran responsif DITUTUP dan satu cacat ditemukan+diperbaiki.** Cara yang berhasil: iframe same-origin selebar X px di dalam halaman konsol (viewport iframe = lebar, jadi media query benar-benar dievaluasi; sesi login ikut karena origin sama) - bukan `window.resizeTo` (ditolak jendela otomasi) dan bukan iframe yang dibuat sebelum hidrasi. Terukur: strip "Hari Ini" 2-2-1 tile di 369/762 px dan 5 sebaris di 1434 px, luapan 0, tidak ada teks terpotong. CACAT yang ditemukan: di 375 px nilai hero "-765,8 kg" (44 px) memakan hampir seluruh lebar kartu KPI Overview sehingga label pecah TIGA baris -> `@media (max-width: 560px)` menurunkan nilai ke barisnya sendiri (tetap rata kanan) -> label 1 baris, tinggi 135 px, luapan 0 di 369/474/554 px, sedangkan 762/1434 px tetap sebaris. Pelajaran: klaim "rapi di layar sempit" wajib diukur, bukan disimpulkan dari `minmax(0,1fr) auto`. Bukti: docs/verification/hari-ini-desain-ulang.md §12.
- [2026-10-17] **K5 dikerjakan: seed Jakarta kini memperagakan TIGA keadaan perjalanan — dan dua bug yang memblokir tombol demo ditemukan+diperbaiki.** Pemilik: "saa setuju" atas subset rekomendasi 7b-3; mulai dari K5 karena paling berdampak dan tidak menyentuh tata letak. `data/seed/sprint1_seed.json`: tiga kiriman Jakarta — `BATCH-JAKARTA-TELUR-CIANJUR` berangkat −21 menit pada rute 84 menit (di jalan, 27%), `BATCH-JAKARTA-TELUR-BOGOR-1` −2,5 jam (sudah tiba), `BATCH-JAKARTA-TELUR-D` `dispatch=null` (belum berangkat). **Keputusan penting: ketiganya SATU komoditas (telur) dari tiga pemasok** — pemilih kiriman disaring komoditas, jadi percobaan pertama dengan ayam/wortel hanya menampilkan satu pil. **Bug 1 (bukan bug K5, dan sudah lama):** `POST /demo/refresh` 500 — upsert `menu_plans` mengganti PK baris `origin='demo'` di tanggal kanonik sementara `delivery_events` masih merujuk id lama → `ForeignKeyViolationError`, satu tanggal bentrok menggagalkan SELURUH refresh. Perbaikan di `app/seed/seed_data.py`: baris demo **diadopsi** (isi + origin jadi `seed`, **id dipertahankan**) dan anak-anaknya diarahkan lewat `peta_plan` (id aktual per (lokasi,tanggal)) — tidak ada PK yang diganti. Dijaga `backend/tests/test_seed_menu_plan_anak.py` (merah dulu: reproduksi 500, hijau sesudah). **Bug 2:** `onDataChanged` hanya me-refetch keputusan, peta & pemilih kiriman tetap cache → tombol terasa mati sampai halaman dimuat ulang. Perbaikan `app/page.tsx`: ikut `mapQuery.refetch()` + `mapSupplierRoutesQuery.refetch()`. **Terukur hidup (localhost:3010, 17 Okt 12.15 WIB):** refresh **200**; pil `Semua (3)` + `Di jalan · 1 jam 2 menit lagi` + `Belum berangkat` + `Sudah tiba 10.32`; kartu fokus `27% jalur`, `Tiba ± 13.18 WIB`, `110,4 km jalan`, `± 1 jam 24 menit`, `800 kg telur`. **Gerbang:** frontend `tsc` 0 · ESLint 0 · **1131 tes / 93 berkas hijau**; backend subset seed+journey+kpi+refresh **52 lulus**. **Catatan jujur:** suite backend PENUH sudah rusak sebelum pekerjaan ini (baseline tanpa perubahan saya: 118 gagal / 841 lulus / 20 deadlock; kegagalan didominasi FK `menu_plans` yang kini diperbaiki), dan suite itu flaky karena sesi lain menyunting berkas backend (uvicorn reload) sementara DB dipakai bersama. **Pelajaran: dua dari tiga masalah di sini hanya muncul saat tombolnya benar-benar diklik** — membaca komponen memberi keyakinan yang salah. Bukti: `ui-audit/p6-k5-tiga-keadaan.png`, `p6-k5-fokus-di-jalan.png`; skrip `cek-k5-alur.py`, `ukur-k5-tiga-keadaan.py`; dokumen `docs/design.md` §7b-3 + `docs/research/7b3-keputusan-peta.md` §9.
- [2026-10-17] **Kebijakan peran PLAN.md §13 DITEGAKKAN di kode (bukan lagi hanya dokumen): Head-only usul/eksekusi, dua approval untuk transfer, pagar tata kelola Monitor.** Keputusan owner: butir 1 dan 2 disetujui, butir 3 dipilih **(a) diresmikan + pagar**. Yang berubah: `api/actions.py` punya `PROPOSER_ROLES = ("sppg_head",)` untuk `propose`/`repropose`/`execute` (`verify`/`approve` tetap dua role); `core/approval_matrix.py::approval_requirement(..., dua_role_wajib=True)` membuat transfer SELALU butuh 2 approval dari Head + Nutritionist (dua user persisten berbeda) apa pun verdict verifier, sementara tipe administrasi (`supplier_exclusion*`) tetap ikut verdict; `services/approval_summary.py` memakai aturan yang sama supaya `can_execute` parity dengan execute (dua salinan `_requirement_for` — pernah hanya satu yang diubah sehingga ringkasan bilang bisa eksekusi padahal 403/409); `api/supplier_exclusions.py` proposal jadi Head-only; `api/admin.py` menolak `bgn_monitor` mengubah peran akunnya sendiri (422 "tidak boleh mengubah peran sendiri"); `frontend/components/DecisionActions.tsx` menyembunyikan Eksekusi/Ajukan ulang dari Ahli Gizi (`approve` tetap). Bukti hidup (body salah tipe; 403 = diblokir, 422 = lolos gerbang): propose/execute/repropose Ahli Gizi `422 → 403`, verify/approve tetap `422`, usul supplier exclusion `422 → 403`, admin Monitor tetap `422`. Tes: `backend/tests/test_peran_final_head_only.py` (10 tes, 3× stabil); berkas tes lama yang mengunci kebijakan "1 approval cukup"/"Nutritionist mengeksekusi" diselaraskan (`test_actions`, `test_action_boundary_e2e`, `test_approval_summary`, `test_supplier_exclusion_api`, `decision-loop.test.tsx`). Gerbang: frontend 1130 tes/93 berkas, tsc 0, lint 0, ruff bersih di berkas yang disentuh; suite backend penuh TIDAK bisa jadi verdikt saat itu karena dua proses pytest sesi lain hidup di kontainer yang sama (fixture akun ber-email tetap saling menghapus → `401 "email atau password salah"`; tes baru memakai domain `@uji-peran.local` agar kebal). Batas yang SENGAJA belum dikerjakan: `POST /decisions` (draf) masih terbuka dua role, mutasi demo belum dibedakan Head vs Nutritionist, `restore` supplier exclusion masih dua role. Bukti: `docs/verification/peran-final-head-only-2026-10-17.md`; ceklis diperbarui di `docs/verification/ceklis-role-vs-plan-2026-10-17.md`. Catatan git: perubahan ini masuk HEAD lewat commit broad sesi lain `8291713` (`git add -A`), jadi catatan ini dibuat supaya kebijakan punya jejak commit sendiri.
- [2026-10-17] **K1 dikerjakan: bentuk garis peta kini punya SATU arti — padat = sudah ditempuh, putus-putus = sisa/perkiraan.** Kontradiksi yang diperbaiki: legenda menulis "Sisa perjalanan" putus-putus sementara layer menggambar SEMUA kiriman putus-putus, termasuk yang sudah tiba. Berkas: `frontend/lib/route-line-split.ts` (`journeyLineParts`: sudah_tiba → padat penuh walau `progress` null; di_jalan+progress → potong; belum_berangkat/journey null → putus-putus), `frontend/lib/supplier-routes.ts` (`routeGeoJson` mengirim dua fitur per kiriman dengan `kind`, `routeLegendEntries` membawa `gaya`, `RouteLineKind`), `frontend/components/SupplyMap.tsx` (satu source + dua layer `supplier-route-line-done`/`-todo`, popup dipasang di KEDUA layer), `frontend/lib/map-legend-compact.ts` (gaya jadi kelas ketiga tanda), `frontend/app/globals.css` (`.map-legend-line-padat/-putus`). **Batasan teknis yang menentukan desain:** `line-dasharray` MapLibre tidak bisa data-driven → harus dua fitur + dua layer dengan filter `kind`. **Jebakan yang tertangkap:** sesudah gaya dibuat, legenda tetap tampil putus-putus karena `legendMarkClass` dipakai dengan destructuring `[kelasDasar, kelasNada]` sehingga kelas KETIGA terbuang — diperbaiki jadi `.join(" ")`. **Gerbang:** 13 tes RED dulu → hijau; 5 berkas peta 138 lulus; `tsc` 0; ESLint 0. **Bukti hidup:** legenda "Sudah ditempuh" (`border-top-style: solid`) + "Sisa perjalanan (perkiraan)" (`dashed`); analisis komponen piksel kanvas → komponen hijau menyambung **780 px** + **40 komponen <20 px** (dua gaya tergambar bersamaan), garis Bogor-1 (sudah tiba) menyambung penuh Jakarta→Bogor sedangkan Cianjur putus-putus. Bukti: `ui-audit/p7-k1-*.png`, `p7-dbg-*.png`; skrip `ukur-k1-garis2.py`, `k1-debug.py`, `k1-komponen.py`; dokumen `docs/design.md` §7b-3 K1 + `docs/research/7b3-keputusan-peta.md` §10.
- [2026-10-17] **Perbaikan ronde 1 laporan QA: enum teknis & kebocoran detail internal dibersihkan dari layar.** StatusBadge memakai `statusLabel()` baru di `lib/bahasa.ts` (PENDING_APPROVAL -> "Menunggu persetujuan", PROPOSED -> "Diusulkan", VERIFIER_FLAGGED -> "Ditandai verifikator"; nilai tak dikenal tidak dikarang, hanya garis bawahnya dibuang). `toolLabel()` menerjemahkan nama alat agen (supply_balance.propose, demand.snapshot, POST /decisions, fallback -> "langkah cadangan"); aslinya tetap di `title`. KPI: pill "scope <uuid> (sppg_head)" -> "Cakupan: Kepala SPPG" (UUID ke title). Agent Log: path berkas internal hilang dari layar, tetap di `title` "Bukti: ..." - tes integration-status dibalik menjadi not.toContain(path) + toContain(title=path). SupplierBoard/Event2Panel: kata "backend"/"purchase order" diganti bahasa pengguna. executionTargetLabel: "Simulasi (mock)" -> "Simulasi". batchLabel memakai safetyLabel ("· fail" -> "· Gagal"). Deskripsi Demo Control & judul ChaosPanel ditulis ulang. Verifikasi peramban 3 peran: 0 token enum Inggris. TDD: statusLabel/toolLabel + tests/status-badge.test.tsx merah dulu. Sisa: kalimat teknis Demo Control datang dari server (backend). Bukti: docs/qa/laporan-qa-3-peran-2026-10-17.md §8.
- [2026-10-17] **Panel kini realtime dengan DB + data demo dibuat ramai (permintaan pemilik: "semua bagian yang menampilkan informasi harus realtime dengan DB ... buat data mock yang lumayan banyak supaya terlihat aktiv").** **Akar masalah:** repo tidak punya SATU pun `useMutation`/`invalidateQueries`; setiap aksi hanya me-refresh query yang diingat komponennya, dan tiga hook tanpa polling (`useSuppliers`, `useSupplierRoutes`, `useExclusions`) ber-`staleTime` 5–10 menit — kelas bug yang sama dengan peta basi pasca-"Segarkan". **Perbaikan terpusat:** `frontend/lib/refresh.ts` (`metodeMenulis`/`segarkanSetelahTulis`) dipanggil `lib/api.ts` dan `lib/supplier-exclusions.ts` (pembungkus fetch sendiri, sengaja demi pesan `detail`), didaftarkan `app/providers.tsx` → setiap POST/PUT/PATCH/DELETE sukses memanggil `queryClient.invalidateQueries()` untuk SELURUH cache; panel yang belum terbuka ditandai basi dan mengambil ulang saat dibuka walau `staleTime` 5 menit. **Bukti hidup:** satu `POST /demo/refresh` → 8 endpoint diambil ulang (26 permintaan GET, semua 200); `/suppliers` + `/kpi` terpanggil saat tab Pemasok & KPI dibuka sesudahnya. **Data demo:** `backend/app/seed/demo_activity.py` — 40 kiriman `origin='demo'` di 10 lokasi (4 komoditas, tiga keadaan, UUID5 deterministik, idempoten) + rute OSRM 37/47 diambil 0 gagal; lalu `seed_demo_completed_decisions` — 3 keputusan selesai (jejak DETECT..ACT, 2 bukti konsisten SEBELUM approval, approval manusia, `safe_delivered_cost`, PO mock hari ini) + 2 limbah hari ini. `PURGE_MODELS` ditambah `Batch` agar "Bersihkan data demo" tidak meninggalkan peta ramai. **Hasil terukur (SPPG Head, periode 24 jam):** `6/7 · 1 metrik belum ada data` → **`7/7 · semua metrik ada`**; KPI: Continuity 100,00% · Food Loss 0,53% (2) · Imbalance 4,41% (68) · SDC Rp15.079.436 (3) · Price Deviation 0,98% (4) · Decision Time 6,74 mnt (3) · Evidence Completeness 75,00% (4); Hari Ini: 33 menunggu tindakan, 2 batch <48 jam (450 kg), 1 shortage 765,8 kg, rantai audit 5.649 blok, agenda 1.115 porsi. **Tidak diisi dengan karangan:** Agent Log tetap "belum ada langkah agent" (AGENTCORE_RUNTIME_ARN kosong) dan Surplus "belum ada data mitra pengolahan" (kolom tidak ada) — sengaja dibiarkan jujur. **Gerbang:** frontend `tsc` 0 · ESLint 0 · **1159 tes / 96 berkas**; backend `test_demo_activity` 2 lulus (idempoten + 4 syarat metrik) + `test_demo_refresh_routes` + `test_seed_jakarta_journey_states` 7 lulus. **Pelajaran:** pemantauan "semua panel realtime" tidak bisa disimpulkan dari membaca komponen — harus dari lalu lintas jaringan sesudah aksi nyata (Playwright `page.on("response")`), karena kegagalan jenis ini tidak menghasilkan galat apa pun. Dokumen: `docs/design.md` §8–§9.
- [2026-10-17] **K3 + K4 selesai (sisa urutan 7b-3 yang disetujui pemilik).** **K3 — padanan teks peta:** `frontend/lib/map-a11y.ts` (`penandaPeta` mengurutkan shortage terbesar dulu lalu surplus lalu seimbang; `ringkasPenanda` memotong di 3 + "+N lokasi lain") + `SupplyMap.tsx` merender baris `Penanda: …` SELALU (juga saat `showStatusList={false}`, keadaan Overview) dan `<ul class="sr-only" aria-label="Daftar penanda peta">` satu butir per lokasi dengan status disebut kata (bukan warna). Batas yang dijaga: SATU BARIS, bukan tabel — tes menolak `<table>`/kata "Kebutuhan" di blok itu supaya "Rincian Pasokan per Lokasi" yang sudah dihapus tidak hidup lagi. **Terukur hidup:** Jakarta `Penanda: Jakarta kurang 765,8 kg`, tinggi 18 px, 1 butir sr-only; BGN Monitor (10 lokasi) `Jakarta kurang 765,8 kg · Surabaya kurang 11,48 kg · Semarang kurang 10,68 kg · +7 lokasi lain`, 10 butir sr-only, tetap 18 px, dipotong elipsis tanpa luapan. **K4 — popup jalur:** dua baris jam digabung jadi satu di `routeEtaLines` — `Berangkat 17 Okt 2026 17.33 WIB → tiba ± 18.21 WIB · 30 menit lagi` dan `Belum berangkat (barang masih di pemasok) → tiba belum ada — barang belum berangkat`; semua fakta lain tetap (jalur jalan, masa layak, peringatan batas layak, waktu tempuh saat ETA belum ada). **Gerbang:** 13 tes ditulis RED dulu (7 murni `map-a11y`, 3 render SSR, 3 asersi popup lama diubah) → hijau; frontend **tsc 0 · ESLint 0 · 1176 tes / 99 berkas**; satu error tsc tertangkap (`readonly BalanceMapLocation[]` vs `BalanceMapLocation[]`) dan diperbaiki dengan parameter `readonly`. **Bukti:** `ui-audit/p10-k3-k4.png`, `p10-k3-nasional.png`, `p10-k4-popup.png`; skrip `ukur-k3-k4.py`, `ukur-k3-bgn-k4.py`; dokumen `docs/design.md` §10–§11.
- [2026-10-18] **Beras jadi komoditas PENUH (permintaan pemilik "buat data beras").** Chip beras sudah ada di UI sejak awal tetapi DB hanya telur/ayam/wortel, sehingga memilihnya memberi layar kosong. Ditambahkan lewat jalur seed: komoditas 180 hari; 3 pemasok beras (Beras Makmur Jakarta, Beras Sari Bogor, Beras Pandan Wangi Cianjur) lengkap dengan koordinat/kapasitas/sertifikasi di data/seed/suppliers_demo.json; pasokan 10 lokasi; permintaan 8 lokasi SPPG (7 observasi); 4 kiriman (2 tiba, 1 di jalan, 1 belum berangkat); harga 10 kota + 3 quote; stok SAP 1003. **Dua aturan yang jangan disederhanakan:** (1) `_SAFE_TEMP_BY_COMMODITY` memberi beras 15-30 C — memakai rentang dingin 0-8 C akan menuduh penyimpanan kering sebagai excursion; (2) komoditas tanpa masa layak kini 422, bukan KeyError. Terukur: peta nasional 10 lokasi (Jakarta kurang 2.110 kg, Cianjur surplus 2.400 kg), pemasok beras 0,6/44,8/77,1 km, 4 rute OSRM baru 0 gagal, chip beras menampilkan 2 kartu kiriman, 0 respons >=400. Batas jujur: belum ada keputusan demo beras dan deret waktu beras belum dibuat. **Bug ikutan diperbaiki:** kunci daftar kiriman memakai id pasangan pemasok-tujuan sehingga dua batch ke tujuan sama memicu "same key"; kini shipmentKey = id#batchId (id pemilihan tetap per pasangan). Tes: backend/tests/test_seed_beras.py (7) + penyesuaian sadar 3 tes yang memaku 3 komoditas; frontend tests/supplier-routes.test.ts (+2).
## 19 Okt 2026 — sisa pekerjaan dituntaskan (rollover harian, beras, limbah bermitra)

- **Keputusan: menyegarkan tanggal baris demo yang SUDAH ADA, bukan membuat baris baru
  tiap hari.** Seeder idempoten membuat KPI "hari ini" kosong setiap hari baru
  (terukur 6/7 pada 18 Okt). Sekarang anak-anak keputusan demo (bukti, persetujuan,
  jejak, PO, limbah) ikut dipindah ke `now` pada setiap penyemaian; id deterministik
  tetap, jadi tidak ada duplikat.
- **Keputusan: harga harian disemai berpasangan (acuan lebih dulu, kutipan sesudahnya).**
  Metrik deviasi harga memasangkan kutipan dengan acuan terakhir SEBELUM kutipan;
  urutan timestamp adalah bagian dari kebenaran data, bukan detail teknis.
- **Keputusan: keputusan BERAS disemai eksplisit** (Jakarta), karena rotasi 3 kota
  tidak pernah memilihnya dan panel Decision & Evidence jadi kosong untuk beras.
  Harga PO per komoditas (`HARGA_PO`) menggantikan satu harga telur untuk semua.
- **Keputusan: mitra pengolahan menjadi kolom, bukan tebakan.** Migrasi
  `022_disposal_partner` menambah `disposal_events.partner_name`; `NULL` = dibuang
  tanpa mitra dan itu dipisahkan dari 0 kg di `GET /waste/summary`
  (`recorded = diverted + unassigned`). UI tidak lagi menulis "—" saat datanya ada.
- **Pelajaran operasional:** DB demo dipakai bersama sesi lain; baris demo bisa hilang
  di antara dua pemeriksaan karena pembersihan tes. Selalu tekan "Segarkan ke hari ini"
  sebelum menilai UI, dan verifikasi lewat DB/tes, bukan dari tangkapan layar tunggal.

## 19 Okt 2026 — pil peta jadi ikon, "Info map" dilebur

- **Keputusan: sakelar lapisan peta jadi tombol IKON (32 px desktop / 44 px sentuh).** Teks
  "Pemasok (7)"/"Jalur kiriman (3)" memakan ~120 px tepat di atas Jawa Barat, sementara jumlah dan
  maknanya sudah ada di baris legenda (tanpa klik) dan tag "Rincian lapisan peta". Nama aksesibel
  membawa jumlah, `title` membawa aksi, `aria-pressed` membawa keadaan.
- **Keputusan: keadaan MATI ditandai garis miring, bukan hanya warna** — pengguna buta warna tetap
  melihat bedanya; ini syarat dari skill ui-ux-pro-max prioritas 1, bukan hiasan.
- **Keputusan: kotak "Info map" dihapus, bukan dirapikan.** Isinya duplikat butir legenda
  (sumber data yang sama); satu-satunya isi unik, daftar Perjalanan kiriman, dipindah ke panel
  "Rincian lapisan peta". Satu fakta, satu tempat: legenda (tanpa klik) → tag jumlah → panel rincian.
- **Pelajaran:** klaim dokumen "kontrol skala & tombol reset belum ada" ternyata BASI — keduanya
  sudah ditambahkan di 7b-1. Periksa kode sebelum mengutip daftar celah dari dokumen desain.

## 19 Okt 2026 — skala peta dihapus, pil sakelar turun & transparan

- **Keputusan pemilik: bilah skala ("50 km") dihapus.** Kiri-bawah dipakai pil sakelar lapisan.
  Konsekuensi diterima: jarak tidak bisa diukur langsung dari peta; km tetap ada di popup jalur,
  kartu kiriman, dan panel rincian (sumber sama: OSRM).
- **Keputusan pemilik: pil di kiri-bawah, tanpa piring putih.** Tombol transparan di atas peta;
  plat putih hanya muncul saat hover/fokus supaya area klik tetap terlihat.
- **Konsekuensi desain: keadaan nyala tidak lagi berupa kotak aksen terisi.** Nyala = ikon hijau tua
  + garis miring hilang; mati = ikon tinta + garis miring. Dua penanda (bentuk + warna) supaya
  tidak bergantung warna saja, dan ikon 16 px tanpa latar butuh ≥4,5:1 — karena itu `#15803d`,
  bukan `--map-accent` #22c55e.
- **Catatan teknis:** tema konsol peta (`app/map-console.css`, sesi paralel) mengecat tombol dengan
  kaca gelap; aturan transparan di `globals.css` dinaikkan spesifisitasnya
  (`.map-card .map-overlay-toggles .map-layer-toggle`) alih-alih memakai `!important`.

## 19 Okt 2026 — audit UI/UX ketat: cincin fokus, target 24 px, warna nyala

- **Cincin fokus tidak boleh memakai satu warna.** Pil transparan duduk di peta
  TERANG, tetapi saat fokus ia mendapat piringan GELAP dari tema. `--map-focus`
  #7dd3fc hanya 1,43:1 di peta terang; tinta gelap hilang di piringan gelap.
  Dipakai dua lapis: cincin putih 2 px + halo tinta gelap 5 px.
- **WCAG 2.5.8 (24 px) berlaku untuk penunjuk apa pun, bukan hanya sentuh.**
  Pil "Pilih kiriman" 22 px karena padding kecil; dinaikkan ke 28 px (44 px di
  perangkat sentuh lewat aturan `button`).
- **Warna keadaan harus diukur terhadap basemap, bukan terhadap aksen merek.**
  Hijau #15803D gagal 3:1 di ubin hijau (2,84:1); `--map-accent-ink` #1E40AF
  lolos 4,94–8,72:1 di empat ekstrem (putih/jalan/hijau/air).
- **Jangan menulis dua aturan dengan spesifisitas sama dan nilai berbeda** (putih
  vs kaca gelap untuk hover pil): hasilnya bergantung urutan berkas. Samakan
  nilainya, atau naikkan spesifisitas secara sadar dan catat alasannya.

## 19 Okt 2026 — bingkai pil: buang abu setengah transparan, cincin fokus dari luar

- **Bingkai abu `rgba(203,213,225,.5)` di atas piringan gelap terbaca kotor** (tiga lapis
  bingkai: abu → putih → gelap). Piringan hover/fokus kini tanpa border; penanda fokus
  sepenuhnya tugas cincin.
- **Cincin fokus disusun dari LUAR ke dalam**: celah putih 2 px (pemisah dari piringan gelap)
  lalu cincin tinta 2 px (13:1 di atas peta terang). Urutan ini dipilih karena latar pil
  adalah peta terang — cincin putih murni hanya ~1:1 di sana.
- **Jangan pakai `!important` untuk menang atas tema.** Naikkan spesifisitas secara sadar
  (`button` di selektor) dan tulis alasannya di komentar, supaya tema tetap bisa mengubah.

## 19 Okt 2026 — chrome peta kembali ke tema TERANG

- **Arah berbalik dari 18 Okt.** Chrome gelap (kaca navy) di dalam kartu peta diganti tema terang;
  nama token `--map-*` dipertahankan supaya globals.css + tes lama tetap berlaku.
- **Batas kontrol ≠ rambut dekoratif.** Di tema terang, pemisah cukup `rgba(15,23,42,.12)` (dekoratif),
  tetapi batas tombol/kontrol wajib `rgba(15,23,42,.45)` (3,2:1) — WCAG 1.4.11.
- **Filter `invert` pada ikon MapLibre harus dihapus saat tema jadi terang**; kalau tidak, ikon
  zoom/kompas menjadi putih di piringan putih.
- **Warna aksen vs ikon mengapung diukur terhadap basemap, bukan terhadap piringan.** `#2563EB`
  (aksen brand) 5,17:1 di putih tetapi 2,93:1 di ubin taman → ikon pil & cincin fokus memakai
  `#1E40AF` (4,94:1 di taman).
- **Jangan pasang `min-height` kelas lebih kecil dari 44 px tanpa blok sentuh**: kelas 0,3,0 menang
  atas `button` (0,0,1), jadi pil pemilih turun ke 28 px di ponsel. Selalu tambahkan
  `@media (pointer: coarse), (max-width: 720px)` yang menaikkannya lagi.


## 19 Okt 2026 — bukti binding ditulis penyemai kasus demo, bukan `resolve_binding`

- **Gejala:** setelah dataset diperluas, 21/21 `demo_case` tanpa `allocation_binding` → kartu unggulan
  menulis "pemasok tidak dikenal" dan `can_execute=false`. Aturan "jangan menebak pemasok" tetap
  dipertahankan; yang berubah adalah penyemainya kini MENULIS bukti sendiri
  (`_ikat_sumber` di `app/api/demo.py`, `human_inspection` + payload `allocation_binding`).
- **Aturan pemilihan batch:** batch di lokasi asal + komoditas, `usable_until >= now`, kuantitas terbesar,
  seri → id terkecil; tidak ada batch layak → tidak ada binding (alasan tetap jujur).
- **Kasus `verifier_flagged` sengaja TIDAK diikat:** tuduhannya soal HARGA sebuah kutipan, dan pemasok
  itu bukan selalu pemilik batch terbesar — mengikat batch terbesar = menampilkan pemasok yang bukan
  subjek tuduhan. Alasan "pemasok tidak dikenal" di kartu itu diterima apa adanya.

## 19 Okt 2026 — batch demo adalah prasyarat gerbang, dan dijaga fixture `conftest`

- **Batch kanonik seed dijangkar `CANONICAL_REF` 8 Okt**; dengan `PASS_THRESHOLD` 0,85 dan shelf telur
  28 hari, batch seed gugur sebagai kandidat sekitar 4 hari setelah REF. Satu-satunya sumber kandidat
  segar adalah batch `origin='demo'` (harvest relatif `now`).
- **Karena itu jangan menyemai manual sekali di awal gerbang.** `purge_demo_rows()` dan tes yang
  menghapus batch demo membuang 40 baris itu di tengah suite → 37 lalu 28 lalu 9 kegagalan beruntun
  dengan satu kalimat "tidak ada kandidat eligible untuk Event 1 (telur -> Jakarta)".
- **Perbaikan permanen:** fixture autouse `jaga_kiriman_demo` di `tests/conftest.py`, menyemai ulang
  hanya bila `count(origin='demo') = 0` dan hanya untuk 13 modul yang menuntut kandidat; ditambah
  teardown modul di `tests/test_deret_demo_aman.py`. Verifikasi: hapus 40 batch demo → satu modul
  dijalankan → hijau dan hitungan kembali 40 dengan `max(harvested_at)` hari ini.

## 19 Okt 2026 — tes pemasok: jumlah lot dipaku dari DB, bukan dari ingatan penulis tes

- `test_shipping_reports_batch_that_failed_testing` (`count == 1`) dan `test_expired_batch_is_not_counted`
  (`count == 0`) merah begitu penyemai demo membuat lot baru untuk pemasok yang sama — bukan regresi,
  melainkan asersi yang memaku keadaan dataset sehari.
- Diganti uji sifat dengan ground truth dihitung saat tes berjalan: lot gagal uji tetap DILAPORKAN
  (`safety_fail_count == sql["fails"]`), lot lewat tenggat tetap DIKECUALIKAN
  (`total > layak`, `(shipping is None) == (sql["count"] == 0)`).

## 19 Okt 2026 — "Integritas Bukti": permukaan gelap terakhir menjadi terang

- Arah pemilik: panel bukti di halaman Decision & Evidence kurang disukai, minta palet yang cocok
  dengan tema terang. Setelah §15 (`map-console.css`), `.integrity-trust` adalah **satu-satunya
  permukaan gelap** yang tersisa — jadi ini penutup konversi gelap→terang, bukan tema kedua.
- **Pola yang dipakai ulang (dan harus dipakai lagi):** pertahankan NAMA token (`--trust-*`), ganti
  nilainya. Aturan lama + tes lama + `docs/design.md` §4 tetap sah; tidak ada penulisan ulang selektor.
- **Warna = keadaan, bukan suasana.** `data-tone` (ok/warn/danger/plain) memetakan ke token
  `--ok/--warn/--danger/--neutral-*` yang sudah ada; tidak ada hex baru. Lencana wajib titik + kata,
  supaya keadaan tidak bergantung pada warna saja; emoji ✅/❌/⚠️ dihapus dari panel ini.
- **Angka jangan dicampur kalimat:** "Blok 3301 · head 9f2c…" satu paragraf itu susah dibaca —
  dipisah jadi baris label→nilai, angka mono `tabular-nums`, hash/alamat sebagai chip mono.
- Gerbang sesi: vitest 1359 lulus / 119 berkas, `tsc --noEmit` 0, `npm run build` 0.
  Rujukan lengkap: `docs/design.md` §16.

## 19 Okt 2026 — popup "Governance & persetujuan": latar blur 20% + kartu fakta

- Arah pemilik (verbatim): "pada halaman pop up 'Governance & persetujuan' ubah tampilan ui dan
  bacgraud di buat blur 20% saja", lalu "untuk blur nya mungkin bisa 15% saja", lalu "blur nya itu
  masih samar samar untuk tampilan di belakangnya, berarti di turunin lagi". Membalik keputusan latar
  pagi hari yang sama: kabut putih 66% + `saturate(140%)` dibuang, tinggal `rgba(248,250,252,.2)` +
  `backdrop-filter: blur(8px)`. Lantainya 6 px: di bawah itu huruf di belakang mulai terbaca.
  Konsekuensi yang diuji: tes CSS lama memaku 0,66 dan saturasi → tes diubah, bukan kode yang
  dipaksa cocok.
- **Satu dialog, bukan semua.** `Popup` dapat prop `className`; tata letak baru hidup di
  `popup-governance` supaya pemilih tanggal & dialog karantina tidak ikut berubah (hanya latarnya,
  karena `.popup-backdrop` milik cangkang bersama).
- Ringkasan bukti jadi `<dl>` label→nilai: bullet padat dengan id panjang membuat mata harus membaca
  prosa; sekarang satu fakta satu baris. Teks tidak diubah karena tes mem-pin sebagian kalimatnya.
- Pelajaran yang bisa dipakai lagi: (a) `--danger-border` (#FECACA) tidak layak jadi stripe 3 px di
  atas putih — pakai `--status-danger`; (b) track progres ber-`--surface-sunken` hilang di atas strip
  sunken; (c) bar progres selebar panel terbaca seperti garis pemisah, batasi ~240 px.
- Gerbang: vitest 1359 lulus / 119 berkas, `tsc --noEmit` 0, `npm run build` 0. Rujukan lengkap:
  `docs/design.md` §17.

## 19 Okt 2026 — dock "Ke zona keputusan": bentuk pil diganti dock ber-hierarki

- Arah pemilik: "popup ke zona keputusan rada kurang, redesign pakai ui ux pro max". Bar melayang itu
  dulu pil 720 px radius 999 dengan satu baris abu-abu "status · hitungan" — terbaca seperti toast dan
  menyamakan bobot dua informasi.
- Sekarang: dock 560 px radius 14, titik nada keadaan (`data-tone` dari `STATUS_TONES`, bukan palet
  baru), keadaan 13 px/600 di atas hitungan 12 px muted, CTA "↓" sepadan dengan tautan di kepala
  keputusan, safe-area iOS, animasi 240 ms yang dimatikan `prefers-reduced-motion`, disembunyikan saat
  cetak, dan ≤560 px memadatkan (bukan menghapus) informasi.
- Jebakan kecil yang terulang di repo ini: `<a class="button">` tetap menampilkan garis bawah bawaan —
  label putih di atas biru jadi terbaca seperti tautan teks. Selalu set `text-decoration: none` pada
  tautan bergaya tombol.
- Gerbang: vitest 120/1368, tsc 0, build 0. Rujukan: `docs/design.md` §18.
- Jebakan build di mesin ini (exFAT): `next build` sesekali gagal
  `ENOENT ... .next/server/pages-manifest.json` walau build sebelumnya lulus. Obatnya `rm -rf .next`
  lalu build ulang — bukan bug kode, melainkan sisa `.next` yang tidak lengkap. Jangan langsung
  menyimpulkan regresi dari error ini.
- Posisi dock "Ke zona keputusan" DIPUTUSKAN TETAP DI TENGAH. Sempat diminta "rata kanan kiri
  mengikuti sidebar buka/tutup" dan sudah dipasang (`left: rail + 22px; right: 22px`, terukur 947 px
  di layar 1262), lalu dikoreksi pemilik: "eh salah tetap kaya di buat rata tengah maksudnya".
  Jangan ulangi full-width; lebar 560 px + `left: 50%` + `translateX(-50%)` adalah kontraknya
  (delta pusat 0 px terhadap layout viewport).

- [2026-10-20] Dokumen PO = PDF dari BACKEND, bukan rakit di browser — angka & jejak persetujuan harus dibaca dari DB pada detik unduh, dan hanya backend yang bisa memagari "sudah disetujui". — rute `GET /sap/purchase-orders/{po_number}/pdf`, pembangun `app/services/po_document.py`.
- [2026-10-20] PDF PO hanya untuk PO dari keputusan `approved`/`executed`; PO impor tanpa keputusan & keputusan yang belum disetujui ditolak 409 dengan alasan, PO lokasi lain 404 (cakupan daftar). — dokumen yang dibawa keluar aplikasi tidak boleh ada untuk pembelian yang approval-nya belum tercatat.
- [2026-10-20] `reportlab` (runtime) + `pypdf` (khusus tes) masuk `backend/requirements.txt`; image WAJIB di-build ulang, karena `pip install` di kontainer hilang saat kontainer dibuat ulang. — sebelumnya PDF hanya hidup sampai `docker compose up` berikutnya.
- [2026-10-20] Tombol "Unduh PDF" hanya muncul di baris yang berhak, baris lain mendapat kalimat sebabnya — tombol yang hilang tanpa penjelasan terbaca sebagai fitur rusak, tombol yang selalu ada padahal 409 terbaca sebagai janji palsu. — pola yang dipakai juga untuk aksi ber-pagar lain.
- [2026-10-20] Komponen yang memegang hook TIDAK boleh dipanggil sebagai fungsi di tes (`renderToStaticMarkup(Komponen({...}))`, `root.render(Komponen({...}))`); render sebagai elemen. — dua berkas tes lama pecah `Cannot read properties of null (reading 'useState')` saat `PurchaseOrderList` mulai memegang state unduhan.
- [2026-10-20] Joule membaca PO lewat skill keempat di jembatan A2A (`purchase_order`), bukan lewat model: rute deterministik mendahulukan nomor `MC-…` dan kata `po`/`purchase order` SEBELUM kata kunci antrean, karena "PO mana yang sudah disetujui?" memuat `setuju` milik skill antrean. Angka PO (harga, total) dibaca apa adanya dari `/sap/purchase-orders`; jembatan tidak mengalikan. PDF PO tetap hanya di UI MealChain — artefak Joule berupa teks, tidak bisa melampirkan berkas.
- [2026-10-20] Data pemasok dirapikan menyeluruh: 60 nama usaha unik bergaya Indonesia nyata (CV/UD/Koperasi/PT) menggantikan nama lama yang berulang; setiap pemasok WAJIB ≤150 km dari SPPG tujuannya (validator `backend/app/seed/validate_supplier_data.py`, 8 tes); `role_hint` 10 lokasi diseragamkan `sppg`; batch demo WAJIB dipasok pemasok di hub yang SAMA + komoditas yang SAMA (`jakarta_lengkap.seed_batches`). Volume Postgres di-reset lalu di-seed ulang karena DB lama menyisakan 119 baris (60 lama + 59 baru). — pemasok yang tidak terjangkau/aneh membuat klaim peta dan keputusan pengadaan tidak bisa dipertahankan di depan juri.
- [2026-10-20] Joule mendapat skill kelima `supplier_directory` (baca `GET /suppliers`): direktori pemasok per SPPG + kiriman aktif; rute deterministik `pemasok`/`supplier`/`direktori` diperiksa SETELAH antrean agar "usulan eksklusi pemasok" tetap masuk antrean. — klaim "Joule bisa memanggil data pemasok" harus terbukti lewat skill, bukan hanya lewat batch/PO.
- [2026-10-20] `jakarta_lengkap` menulis `verifier_note="consistent"` (bukan "konsisten") karena `approval_summary` memetakan teks lain ke verdict `unavailable`; tes keputusan KPI dibatasi ke ID `demo_decision_id` agar tidak mencampur 30 baris riwayat `jakarta_lengkap`. — verdict layar dan gate harus membaca kontrak yang sama.
- [2026-10-20] `seed_demo_activity` hanya menghapus batch milik namespace `demo_batch_id`-nya sendiri (bukan semua `origin='demo'`), supaya 40 batch kaya `jakarta_lengkap` tidak ikut terhapus saat suite menjalankan penyemai ini; `test_demo_activity._bersihkan` memakai himpunan ID yang sama. — seeder demo harus komposabel; filter `origin` terlalu luas dan merusak data seeder lain.
- [2026-10-20] Kartu "Penerimaan barang" (Keamanan Pangan) diaudit: daftar batch penerimaan kini SELALU dapur sendiri (`receivingBatchOptions`, bukan baris yang sudah disaring cakupan tabel) karena batch kota lain dijawab 403 `assert_in_scope` — opsi yang dijamin gagal bukan opsi; batch yang masih layak didahulukan supaya default tidak jatuh ke batch kedaluwarsa; kalimat "tandai sisanya sebelum barang dipakai" dihapus karena gerbangnya tidak pernah ditegakkan (tombol aktif di 0/5) dan diganti "Boleh disimpan sebagian"; pesan sesudah simpan memakai bentuk lampau (`receiptSavedSentence`); kendaraan berpendingin TIDAK jadi titik periksa ke-6 (rantai dingin dihitung deterministik oleh `/safety/evaluate`, dan batas 15–30 °C beras membuat titik periksa generik salah). — bukti 403, daftar 50+ opsi, dan simpan nyata 201 (`checked` berisi `bau_warna`) ada di `_qa/penerimaan-barang/`.

[2026-10-20] **Sesi demo (langkah 1).** Pemilik meminta default kosong + tombol "Siapkan data demo" yang
mengaktifkan data selama satu jendela waktu (bawaan 2 jam, maksimum 4 jam), hitungan mundur, perpanjangan tanpa
mengubah data berjalan, dan data kembali kosong saat sesi habis. Implementasi: migrasi `024_demo_sessions`,
`app/services/demo_session.py` (kedaluwarsa malas, pembersihan HANYA baris ber-stempel, penjaga ORM
`before_flush` + `do_orm_execute` yang mati bila `DEMO_SESSION_ENFORCE=false`), router `/demo/session`, dan 7 tes.
Keputusan penting: jam tidak dibekukan (`anchor_now` hanya dicatat); pembersihan tidak menghapus data tanpa
stempel; flag belum dinyalakan karena UI belum ada. Sisa pekerjaan: stempel tabel lain + UI Demo Control.

[2026-10-20] **Sesi demo (lanjutan) — filter ORM dibuang.** `with_loader_criteria` tidak bisa diandalkan: banyak endpoint memilih kolom (`select(Batch.id, ...)`) atau memakai Core/bulk sehingga penyaringan hanya sebagian (`/batches` 0 padahal 118 baris; `count` 118). Penggantinya: kosong-secara-default dijaga SIKLUS DATA — mulai sesi mengosongkan semua baris operasional lalu menyemai + stempel massal (`tandai_sesi`) untuk menutup celah bulk insert; sesi berakhir mengosongkan; boot tanpa sesi mengosongkan. Mutasi dijaga dependency `butuh_sesi_aktif` (409). Konsekuensi diterima pemilik: bukti sesi lama tidak diarsipkan di DB. Temuan lain: cache `model_bersesi()` yang dihitung saat impor melewatkan tabel yang diimpor belakangan → ForeignKeyViolationError; sekarang cache dihitung ulang bila jumlah mapper berubah.


## 2026-10-20 — Sesi demo: kosong-secara-default lewat siklus data, bukan filter kueri

**Keputusan.** `with_loader_criteria` dibuang. Kosong-secara-default dijamin siklus:
`start` mengosongkan seluruh baris operasional lalu menyemai + menstempel; `end`/kedaluwarsa
mengosongkan; boot tanpa sesi mengosongkan (restart saat sesi aktif tidak menyentuh data).
`kosongkan_kecuali(db, None)` = purge semua baris bertanda sesi ditambah baris tanpa stempel;
`kosongkan_kecuali(db, sid)` = sisakan milik sesi itu.

**Alasan.** Banyak endpoint memilih kolom (`select(Batch.id, …)`) atau memakai Core/bulk yang
tidak tersaring `with_loader_criteria`, sehingga `/batches` menjawab 0 padahal 118 baris ada —
filter itu tampak benar di tes unit dan salah di aplikasi.

**Konsekuensi.** Riwayat sesi lama tidak diarsipkan di DB (audit trail tetap ada di
`agent_traces`/`decision_evidence` selama sesi berjalan). `asyncio.Lock` menyerialkan
`start`/`end` supaya penyemaian yang masih berjalan tidak menyisakan baris tanpa stempel
setelah "Akhiri sesi".

**Prasyarat gerbang lokal.** Suite backend memakai DB demo bersama; jalankan dengan
`-e DEMO_SESSION_ENFORCE=false` dan data kanonik dari `seed_data --reference-time
2026-10-08T12:00:00+00:00` + `generate_timeseries()`. Seed dengan referensi "hari ini"
menggeser jangkar dan membuat `test_agenda_api` merah.

## 2026-10-20 — Nav "lompat ke bagian" jadi komponen bersama, dipasang hanya di halaman yang butuh

**Keputusan.** Nav menempel "Bagian" yang dulu hidup di dalam `components/DecisionEvidence.tsx`
dipindah ke tiga berkas bersama: `components/SectionJump.tsx` (markup + `aria-current`),
`lib/hooks/useActiveSection.ts` (pengukur posisi), `lib/section-jump.ts` (daftar tujuan per
halaman). Gayanya pindah dari `evidence-dossier.css` ke `globals.css` (`.section-jump`,
`.jump-target`). Dipasang di **dua** halaman baru — Keamanan Pangan dan Overview — dan **tidak**
di halaman lain.

**Alasan.** (1) Menyalin pola ini ke halaman kedua berarti menyalin pengukur gulir + aturan
aksesibilitas, dan dua salinan pasti menyimpang. (2) Tidak semua halaman berhak mendapatkannya:
hari Ini sudah punya lima tile tombol yang menggulir **dan** memindahkan fokus (lebih baik
daripada anchor), Recommendations sudah dipendekkan pencarian/filter/urut/paginasi, dan Pemasok,
KPI & Kualitas, Agent Log, Demo Control punya ≤ tiga bagian. Aturan pemakaian + tabel alasan
tertulis di `docs/design.md` §24 supaya keputusan ini tidak dibuka ulang tanpa argumen baru.
(3) Daftar tujuan dibangun dari **kondisi render yang sama** dengan bagiannya — "Penerimaan
barang" hanya untuk peran ber-SPPG, "Keputusan keamanan lokasi ini" hanya bila daftar keputusan
ada, "Kiriman" hanya bila kartu kiriman benar-benar dirender (kartu itu `return null` saat daftar
kosong). Tautan mati lebih buruk daripada tidak ada nav.

**Konsekuensi.** (a) Ambang posisi = 140 px dari atas viewport, diukur dengan listener gulir
rAF-throttled, bukan `IntersectionObserver` (bagian lebih tinggi dari viewport tidak pernah
"menang" pada rasio irisan). (b) Di **dasar halaman** bagian terakhir dipaksa aktif: cacat ini
hanya terlihat saat verifikasi di aplikasi hidup (Overview, bagian Telemetri selalu kalah dari
Kecukupan), sudah diperbaiki + dites. (c) `scroll-margin-top` kini satu kelas `.jump-target`
(132 px), bukan daftar lima id — halaman baru tidak perlu menambah selektor. (d) Nav hanya
muncul setelah datanya ada; di Overview, tujuan "Kiriman" bisa menyusul beberapa ratus milidetik
setelah muat pertama.

## 2026-10-22 — Audit peta: legenda = kanvas, klaim kiriman per batch, klik garis tiba

Temuan dan perbaikan (diverifikasi di aplikasi hidup, gate frontend hijau):

(a) LEGENDA bercerita beda dengan kanvas: contoh garis "sisa" memakai biru aksi
    (--accent-strong) sementara layer `todo` menggambar violet terang; entri
    "Sudah tiba (redup)" memakai nada `ok` (violet) sementara garisnya SLATE #475569.
    Kini ada nada baru `tiba` (--route-arrived); `.map-legend-line-ok/-sisa/-tiba`
    memakai token yang SAMA dengan ROUTE_DONE_COLORS / ROUTE_TODO_COLORS, dijaga
    tes drift (nilai token + kelas CSS).

(b) Pin "sedang mengirim" tidak pernah berwarna: DUA blok CSS dengan selektor
    identik (pin pengirim), yang pertama cincin hijau --status-safe menang cascade
    sehingga aturan violet di bawahnya mati. Dua tes lama justru mengunci cincin itu.
    Blok mati dihapus; tes diganti ke kontrak isian violet + halo (dengan cabang
    prefers-reduced-motion). Catatan: label "sedang mengirim N kiriman" tetap dihitung
    dari blok `shipping` (keputusan pemilik 16 Okt), jadi pin bisa menyebut mengirim
    walau tidak ada perjalanan aktif — itu teks, bukan warna.

(c) Id fitur GeoJSON dulu id LAJUR: dua batch di lajur sama berbagi id, dan dua fitur
    satu kiriman (ditempuh + sisa) juga berbagi id. Kini `properties.id` = shipmentKey
    (lajur#batch) dan id tingkat-fitur = lajur#batch#kind; lookup klik ikut shipmentKey.

(d) Garis kiriman yang SUDAH TIBA (layer supplier-route-line-tiba) tidak pernah
    didaftarkan ke handler klik — satu-satunya garis yang terlihat sore hari justru
    mati saat diklik. Didaftarkan; popup + sorotan hidup lagi (diuji lewat handler
    per layer di tiruan peta).

(e) Ekor kendaraan dinaikkan eksplisit (moveLayer) setelah layer jalur dipasang,
    supaya urutan pasang layer yang mengikuti urutan data tidak menenggelamkannya.

(f) Popup mencetak "Sisa ± -200 menit" untuk kiriman yang sudah tiba (remaining_min
    negatif dari server). Kini sisa hanya ditulis bila > 0; selain itu
    "100% perjalanan ditempuh".

## 2026-10-22 — Audit UI/UX + animasi seluruh halaman (12 layar)

Metode: pemindaian token statis + sweep computed style per tab di DOM hidup, satu turn.
Artefak: `_qa/design-consistency/00-ringkasan-2026-10-22.md` + 11 laporan per halaman.

Tiga cacat "diam" yang ditutup (tanpa error, hanya tampil beda):

(a) KONTROL FORM tidak mewarisi tipografi proyek: `button`/`input`/`select` tampil Arial
    13,3333 px bawaan peramban di SEMUA halaman (terukur 70–146 elemen per halaman), dan
    `select.dc-select` berteks hitam murni. Kini `button,input,select,textarea{font:inherit;
    color:inherit}` di `theme-ext.css` (dimuat terakhir, tanpa !important). Terukur sesudah:
    satu keluarga huruf per halaman, 0 elemen Arial.

(b) 7 TOKEN HANTU dipakai sebagai `var(--x, #hex)` tanpa deklarasi, jadi fallback yang menang:
    `--warning-ink/-bg/-line`, `--status-warn`, `--safe`, `--warn`, `--surface-2`. Kini alias
    di `:root` theme-ext → `--warn-ink`, `--warn-bg`, `--warn-border`, `--status-warning`,
    `--status-safe`, `--surface-sunken`; 11 cadangan hex di globals.css dihapus. Bukti:
    `.integrity-warning` berubah dari #92400e/#fcd34d ke --warn-ink/--warn-border.

(c) BAHASA GERAK tidak merata: 4 dari 11 tab beranimasi masuk, 7 tidak. Ditambah SATU reveal
    panel (`page-reveal`, opacity + 6 px, `--dur-3` 240 ms, `--ease-standard`) untuk
    `.app-content > *`, hanya pada `prefers-reduced-motion: no-preference`. Keyframe berakhir
    `transform: none` supaya tidak meninggalkan containing block untuk elemen fixed.

Ikutan yang ikut ditutup: lantai tipografi 12 px ditegakkan (11 px di Overview & Keamanan
Pangan; 8,5–10,5 px di popup peta → `--fs-1`); popup peta dibatasi `max-height: 340px` +
`overflow-y:auto` karena pada 12 px tingginya 402 px > kanvas 400 px sehingga `jagaPopup`
menyerah; dua hex di luar palet (`#FAFBFC`, `#fbfcfe`) → token; `font-family` literal di
`.today-tile-value--teks` → `var(--font-ui)`; bayangan logo rail → token `--shadow-brand`.

TIDAK diubah (keputusan, bukan cacat): angka tile "Hari Ini" 16 px (pemilik 17 Okt: 18 px
terbaca seperti judul); warna pil komoditas aktif = warna kategori (`--cat-amber-solid`).
Bersih tanpa perubahan: radius 100% token, keluarga lencana seragam 22/12 px tanpa label
terpotong, 28 blok reduced-motion menutup semua keyframe.

Kontrak baru: `frontend/tests/design-tokens-kontrak.test.ts` (8 tes). Gerbang: tsc 0,
161 berkas / 1760 tes, lint 0.

## 2026-10-22 — Audit 375 px + peran BGN Monitor & Nutritionist

BGN Monitor (9 tab, ada Pengaturan, tanpa Surplus/Demo Control) dan Nutritionist (10 tab,
ada Surplus + Demo Control, tanpa Pengaturan) konsisten di 1262 px: 2 keluarga huruf per tab
(Overview 3 = kanvas MapLibre), skala 12-32 px, 0 teks < 12 px, tanpa luapan.

Satu cacat nyata di 375 px, hanya di Pemasok: pager meluap 9 px. Sebab: nomor halaman satu
baris flex yang tidak boleh menyusut, sementara pada `(pointer: coarse), (max-width: 720px)`
tombolnya naik ke 44 px -> 6 nomor + rentang + 2 tombol langkah = 301 px di ruang 286 px.
Membiarkan nomor membungkus DITOLAK (pager jadi 214 px / 6 baris). Perbaikan: nomor halaman
disembunyikan di <=720 px (posisi tetap terbaca dari "1-10 dari 105" + Sebelumnya/Berikutnya)
plus `min-width: 0` pada `.pager-controls`. Terukur sesudah: luapan 0 px di 9 tab, pager
44 px satu baris (sw=cw=286), 0 target sentuh < 44 px, desktop tidak berubah (pager 32 px,
nomor 1-5-11 tetap tampil).

Elemen yang melewati tepi kanan di mobile tapi bukan cacat: `.section-jump-list`
(rail chip, induk `overflow-x: auto`), `.board-table-wrap` (tabel lebar), `.side-nav`
(drawer off-canvas) — luapan halaman tetap 0.

Metode 375 px: iframe same-origin 375x812 di halaman hidup (media query ikut lebar iframe),
reload di antara kelompok tab karena hot-reload dev mengganti pohon React dan membuat
pengukuran kosong. Artefak: `_qa/design-consistency/00b-mobile-dan-peran-2026-10-22.md`.

Kontrak: tes `pager menyempit di <=720 px` di design-tokens-kontrak.test.ts (9 tes).
Gerbang: tsc 0, 161 berkas / 1761 tes, lint 0.

- [2026-10-23] **KPI 24 jam mulai dari "belum ada aksi hari ini", lalu menyala saat aksi dijalankan (permintaan pemilik: "ketika demo nanti baru mencoba atau memproses hari itu kpi baru akan berjalan ... jadi seperti real time").** Keputusan pemilik: hanya **Jakarta** (akun demo), bukan semua lokasi; pandangan global BGN dan kota lain tetap seperti disemai. Implementasi: `app/seed/demo_kpi_riwayat.py` menggeser baris AKSI Jakarta (keputusan, trace, bukti, approval, PO) yang lahir di jendela 24 jam ke ~25 jam lalu dengan SATU delta seragam (urutan rantai tetap, `expires_at` tidak ikut bergeser), dipanggil dari `demo_template.build_into` dan `POST /demo/refresh`; baris FAKTA hari ini (menu plan, kiriman, limbah, kutipan harga, supply) tidak disentuh karena hanya penyemai yang bisa menulisnya, sedangkan empat metrik lain bisa lahir dari Event 1/approve/execute. Panel juga berhenti jadi potret: `kpiQueryPolicy` + `KPI_POLL_MS` 20 dtk (hanya tab Hari Ini & KPI, `refetchIntervalInBackground: false`). Terukur 23 Okt: Jakarta 24 jam 3/7 (Meal 100,00% · Susut 1,15% · Simpangan 2,66%), 0 baris aksi Jakarta dalam 24 jam, 7 hari/1 bulan tetap 7/7, BGN global 7/7; UI Hari Ini "KPI tersedia 3/7"; `/kpi` dipanggil tepat tiap 20 dtk dan berhenti saat pindah tab. Dua jebakan yang ditemukan saat verifikasi live: (a) baris ORM yang belum di-flush tidak terlihat UPDATE raw SQL → 7 keputusan lolos, (b) `now` di awal build (build ±50 dtk) membuat baris yang lahir belakangan lolos dari saringan `<= now` → batas atas memakai jam nyata. Tes: backend 5 uji baru (`tests/test_demo_kpi_riwayat.py`), frontend kpi 21 uji, suite frontend 161 berkas / 1764 uji, tsc 0, lint 0.

- [2026-10-23] **Rehearsal penuh mengungkap Kelengkapan Bukti 0,00%, ditutup dengan satu kasus data demo di jendela 24 jam.** Rehearsal nyata lewat API (Event 1 telur → propose → approve kepala+gizi → execute; Event 3 beras FAIL) menaikkan Jakarta 3/7 → 7/7, tetapi Kelengkapan Bukti tampil 0,00%: keputusan pengadaan hanya punya SATU jenis bukti konsisten sebelum approval (human_inspection), sedangkan Event 3 memang punya dua (human_inspection + temperature) namun verifier menandainya FLAGGED karena batch safety FAIL adalah blocker absolut — jalur itu tertutup oleh aturan, bukan bug. Pilihan yang diambil pemilik: **data demo saja**, bukan mengubah alur produk. Implementasi: `app/seed/demo_kasus_bukti.py` menyemai satu keputusan `demo_case` "bukti-hari-ini" (Bandung → Jakarta, 300 kg, status pending_approval, verifier konsisten) DI DALAM jendela 24 jam dengan DUA jenis bukti konsisten yang direkam sebelum approval, tanpa approval dan tanpa PO; dipanggil setelah penggeser di `demo_template.build_into` dan `POST /demo/refresh`, dan kedua jalur menghapus approval/PO lama milik kasus itu supaya cerita demo bisa diulang. Alasan ini aman: Imbalance & Decision Time mengabaikan baris `demo_case`, Safe Delivered Cost menuntut PO (tidak ada), Kelengkapan Bukti hanya menghitung keputusan yang SUDAH disetujui, jadi keadaan awal tetap 3/7. Terukur 23 Okt: 3/7 → approve kasus (2 approval) → 4/7 dengan Kelengkapan Bukti 100,00% → Event 1 → 7/7 dengan Kelengkapan Bukti 50,00% (1 dari 2 keputusan yang disetujui hari itu berbukti lengkap). Label kartu: `CASE_LABELS["bukti-hari-ini"]` = "Kasus: Alokasi Bandung–Jakarta" (`frontend/components/RecommendationCard.tsx`). Tes: `tests/test_demo_kasus_bukti.py` 3 uji (idempoten + reset approval/PO), subset demo 24 uji lulus, tsc 0, lint 0. Batas jujur: 100,00% hanya bertahan kalau keputusan Event 1 juga membawa ≥2 jenis bukti — itu perubahan produk dan belum dikerjakan.

- [2026-10-24] **Meal Continuity 24 jam: 0,00% → 100,00% (audit KPI-01).** Keputusan: perbaiki rumus, bukan menambal data. Penyebab ganda — `plan_date < CAST(:end AS date)` membuang rencana hari ini (`end` = sekarang), dan pembilang difilter `delivered_at` sementara penyebut `plan_date` sehingga jendela 24 jam bergulir mentok ~50%. Perbaikan di `app/services/kpi_service.py`: `_plan_date_range()` (inklusif dua ujung, konversi `Asia/Jakarta` eksplisit) dipakai untuk pembilang & penyebut; `delivered_at` berhenti jadi filter. Tes kontrak `tests/test_kpi_batas_tanggal.py` (5) RED→GREEN; regresi 46 tes KPI/demo + 30 tes demo/event1 lulus; live Jakarta 24 jam 0,00% → 100,00%, 7 hari 85,42% → 100,00%. Alasan "hari kalender/plan-day" menang atas "jendela bergulir murni": metrik kontinuitas makanan dihitung per tanggal rencana, bukan per jam kirim.

- [2026-10-24] **DB-01 ditutup: model = sumber kebenaran skema, `alembic check` bersih.** Keputusan: daftarkan seluruh objek DB di ORM (bukan allowlist `include_object` di `env.py`), karena allowlist menyembunyikan drift berikutnya. `LedgerBlock` baru menyalin DDL `ledger_blocks`; 22 index migrasi dideklarasikan ulang (termasuk `text("recorded_at DESC")` dan index parsial `WHERE source_ref IS NOT NULL`); 5 tipe kolom dan FK `ondelete=RESTRICT` disamakan. Bukti: `alembic check` → "No new upgrade operations detected.", ORM 22 tabel, 6 tes ledger lulus, ruff bersih. Konsekuensi yang disengaja: autogenerate kini tidak akan pernah mengusulkan DROP `ledger_blocks`; kalau migrasi berikutnya menambah index parsial, deklarasikan juga di model atau `alembic check` akan merah.

- [2026-10-24] **DEP-01: image frontend produksi, bukan dev server.** Dipilih target-stage dalam satu Dockerfile (bukan Dockerfile terpisah) supaya dev dan prod berbagi layer dependensi yang sama dan tidak bisa menyimpang. `runner` memakai `npm ci --omit=dev` + `next start` + user non-root; `docker-compose.prod.yml` berdiri sendiri (nama kontainer/volume/jaringan `-prod`) agar stack dev tetap jalan apa adanya. Healthcheck backend ditambahkan di kedua stack (GET `/health` lewat python, bukan cek port) dan frontend menunggu `service_healthy`, sehingga urutan siap benar. Jebakan yang tercatat: (a) tanpa `.dockerignore` build mengirim `node_modules`/`.next`; (b) dua target dengan nama image sama akan saling menimpa; (c) dua stack penuh di mesin ini memacetkan Docker Desktop — verifikasi image prod cukup satu kontainer frontend; (d) build bisa gagal karena snapshot berkas setengah jadi saat sesi lain menyunting `app/page.tsx` — jalankan `tsc` dulu sebelum menyimpulkan build rusak.



- [2026-10-25] **Lensa Kesegaran di grafik "Kecukupan pasokan" ternyata identik dengan lensa Kuantitas — diperbaiki di dua lapis (data + tampilan).** Temuan: Kesegaran hanya menghitung batch dengan sisa masa layak > 48 jam (`frontend/lib/supply-adequacy.ts`), sedangkan Kuantitas menghitung layak (fresh + ≤48 jam). Template demo hanya menyemai batch `pass` yang masih >48 jam (ayam 49–76 jam, telur ~400 jam, beras berbulan-bulan), sehingga terukur di DB 25 Okt: **39 dari 40 kombinasi lokasi×komoditas** menghasilkan angka yang persis sama di kedua lensa; satu-satunya yang beda adalah Yogyakarta/ayam (97% vs 79%). Selain itu batang grafik tidak bergantung lensa — segmen fresh/near/unsafe/unverified selalu digambar sama, jadi bahkan baris yang angkanya beda pun tampak identik. Perbaikan data: `app/seed/demo_template.py` mendapat `STOK_MENDEKATI_BATAS` + `rencana_stok_mendekati_batas()` (fungsi murni) dan langkah `_semai_stok_mendekati_batas()` yang memilih batch `pass` TERKECIL per target lalu memundurkan `usable_until` ke 16–36 jam; `harvested_at` ikut dimundurkan supaya `harvested_at + umur simpan = usable_until` tetap sama dengan hitungan `recommendation_service.compute_freshness_score`, dan `freshness_score` diisi porsi sisa umur. Target: Jakarta/wortel 28 jam, Bandung/ayam 20, Bandung/wortel 33, Surabaya/ayam 16, Surabaya/wortel 36 — jadi ketiga kota demo melihat bedanya. Langkah ini WAJIB jalan setelah `_rapikan_kiriman_jakarta` (pemangkasan menghapus batch terkecil Jakarta). Perbaikan tampilan: lensa Kesegaran menambahkan kelas `sa-fill-segar` pada `.sa-track-fill`; segmen ≤48 jam jadi berongga (garis miring, opacity 0,65) dan segmen tidak layak/belum terverifikasi meredup 0,35, ditambah catatan legenda "garis miring = layak, tidak dihitung segar". Dengan begitu panjang batang pekat selalu sama dengan angka "segar", bukan cuma angkanya yang berubah. Hasil: template dibangun ulang 25 Okt (66 dtk, 120 batch), sekarang 6 dari 40 baris berbeda — Jakarta/wortel 228%→183%, Bandung/ayam 81%→72%, Bandung/wortel 89%→75%, Surabaya/ayam 97%→89%, Surabaya/wortel 98%→59%, Semarang/ayam 97%→80%. Verifikasi live (Gizi Bandung): Kesegaran ayam 72/telur 74/wortel 75/beras 124 vs Kuantitas telur 74/ayam 81/wortel 89/beras 124, urutan baris ikut berubah, catatan legenda hanya muncul di lensa Kesegaran. Tes: `backend/tests/test_demo_template_kesegaran.py` 4 uji (jendela ≤48 jam, konsistensi umur simpan, determinisme, urutan pemanggilan di `build_into`), frontend 1 uji baru di `tests/supply-adequacy-chart.test.tsx`. ruff bersih, tsc 0. Catatan: `road_routes` di DB ini kosong karena OSRM tidak hidup saat rebuild — pengaruhnya hanya durasi kiriman, tidak ke angka pasokan.



- [2026-10-27] **Pengadaan (`supplier_procurement`) tidak bisa dieksekusi: 409 `binding batch/supplier berubah` walau approval sah — diperbaiki di guard, bukan di data.** Keputusan: pengadaan TIDAK diberi `source_location_id` palsu (= target) walaupun itu cara tercepat menyembuhkan gejala, karena model data sudah menyatakan pengadaan tidak memindahkan stok SPPG lain (`demo_procurement_orchestrator.py:209`) dan `demo_cost.py:145` bergantung pada fakta itu. Yang diperbaiki: satu definisi lokasi acuan `lokasi_batch_acuan(decision)` di `services/supplier_eligibility.py` (pengadaan → `target_location_id`, jenis lain → `source_location_id`) dipakai oleh `resolve_binding`, `batch_sumber_transfer`, `actions._source_batches_still_safe`, dan `approval_summary._safety_view`, supaya endpoint dan read model tidak bisa menyimpang lagi. Fakta penyebab bug lolos: pengadaan hasil seed selalu punya `source_location_id` terisi, hanya jalur agen (`POST /demo/agent/run`) yang menulis NULL — jadi jalur demo yang dipakai juri justru yang tidak teruji. Jenis non-pengadaan dengan lokasi asal NULL tetap ditolak (fail-closed). Bukti: `backend/tests/test_procurement_execute_guard.py` 6 tes RED→GREEN; rusak → hijau terukur pada keputusan demo `943e662c…` (`still_safe=True`, sisa penghalang hanya `decision expired`).



- [2026-10-27] **Satu definisi "lokasi acuan batch" dipakai di SEMUA penulis dan pembaca binding — bukan hanya guard eksekusi.** Setelah temuan F1 diperbaiki, audit menemukan tiga jalur lain yang masih memakai `source_location_id` untuk keputusan pengadaan: (a) `api/demo.py::_ikat_sumber` (penyemai kasus demo menulis binding transfer untuk pengadaan → PO bisa ke pemasok berbeda dari layar; sesudah guard diperbaiki justru 409), (b) `supplier_eligibility.persist_binding` (`POST /decisions` menolak 422 binding pengadaan yang sah — terukur di gate write-flow), (c) `actions.repropose_action` (iterasi baru pengadaan kehilangan `supplier_id` + binding → `409 supplier_unknown`). Keputusan: `lokasi_batch_acuan(decision)` + aturan "pemasok binding = pemasok keputusan" menjadi kontrak tunggal; binding pengadaan divalidasi terhadap SPPG TUJUAN. Data demo 4 kota disemai ulang lewat jalur resmi `_seed_demo_cases(force=True)` supaya binding lama yang menunjuk stok SPPG asal hilang. Bukti: `test_persist_binding_acuan.py` (2 RED→GREEN, 1 regresi transfer), `test_repropose_pengadaan.py`, `test_demo_cases_procurement_binding.py` (3), guard pengadaan 6; gate read-only `verify/decision-evidence.spec.json` 100/100 PASS.

- [2026-10-27] Geladi Fase 12 dijalankan pada **DB klon** `mealchain_r12` + stack terpisah `mcg-f12` (backend 18100, frontend 13110) supaya DB demo tidak tersentuh; tiga mode diuji lewat skrip `_qa/f12/rehearsal_f12.py` yang menulis JSON bukti. — replay 22/22, realtime, operasional 6/6.
- [2026-10-27] **Jembatan Joule tidak dipush ulang.** `mealchain-joule-bridge-4sehat3trio` hidup tetapi `backend.reachable=false`; uji fungsional lima skill dilakukan pada jembatan lokal yang menunjuk backend sesi. Alasan: aturan fase melarang push tanpa izin pemilik. — status CF dicatat sebagai batas, bukan selesai.
- [2026-10-27] Gate suite penuh pada DB terpisah: **50 gagal / 2077 lulus / 31 skip**. Sebab utama bukan kode demo: batch berjangkar REF 8 Okt menjadi basi pada jam dinding 27 Okt, dan `fuse_evidence` menilai satu lokasi secara konservatif sehingga gabungan batch tua+baru = `on_hold`. — butir 7 tetap `OPEN` sampai jam evaluasi suite dipin atau batch REF dibersihkan.
- [2026-10-28] **Tata letak halaman Keamanan Pangan diubah jadi papan operasi — FRONTEND SAJA (permintaan pemilik: "redesign layout ... hanya ubah design di front end").** Dua perubahan susunan, nol perubahan data/logika: (a) kartu "Ringkasan pengawasan" keluar dari grid 2 kolom dan menjadi BAND selebar halaman — empat tile status + tile penanda kini 4 kolom sejajar (dulu berdesakan 3+1 di kolom kiri), fakta keputusan di kolom kiri dan tombol "Tinjau N batch gagal" + peringatan di kolom kanan (`app/globals.css` `.safety-band`); (b) "Bukti suhu" dan "Batch perlu segera dipakai" berdampingan dengan kolom bukti lebih lebar (`.safety-grid-evidence` 1,4fr/1fr), keduanya jatuh ke satu kolom pada <=1100 px. Kartu "Bukti suhu" dipindah ke komponen presentasional `frontend/components/TemperatureEvidenceCard.tsx` + modul CSS-nya: bar tersegmen + legenda berangka menggantikan satu kalimat berjalan, baris per batch jadi ledger (komoditas + lencana keadaan, meta observasi/sampel/asal log, profil, alasan server), baris yang membelokkan alokasi didahulukan (sort stabil), dan SEMUA kelas yang sudah jadi bahasa halaman dipakai ulang (`.card`, `.board-card-head`, `.board-badge-*`, `.evidence-note`, `.board-link`, geometri `.board-list li`). Batas keselamatan tidak berubah: label tetap dari blok `evidence` server, klien tidak menghitung kelengkapan, "log simulasi" dan "simulasi, bukan standar regulasi" tetap disebut, radius hanya dari skala sah, warna hanya token (`--status-warning` tetap tint; teks peringatan `--warn-ink`). Bukti: suite frontend 186 berkas / 2035 tes lulus (termasuk 8 tes baru `tests/temperature-evidence-card.test.tsx` dan gate `radius-scale-css`), `tsc --noEmit` 0, `next lint` 0; live di stack dev (viewport 1262 px): band 947 px dengan empat tile 222 px sejajar, grid bukti 543/388 px, tanpa overflow horizontal. Batas jujur: pemeriksaan 375 px lewat iframe tidak bisa dijalankan di sesi ini (dokumen menolak framing), jadi responsif diverifikasi dari aturan media query (<=1100 px -> satu kolom), bukan dari tangkapan layar.

- [2026-10-28] **Lapisan visual Keamanan Pangan: band ringkasan jadi "kepala" halaman, tetap token-only.** Lanjutan redesign tata letak hari yang sama (permintaan pemilik: "layout dan design eye catching" + tetap konsisten). Yang ditambahkan hanya tampilan: (a) band ringkasan memakai `data-tone` = keadaan terburuk pada cakupan (gagal/karantina -> danger, perlu verifikasi -> warn, selain itu ok) sehingga PERMUKAAN band ber-tint `--danger-bg`/`--warn-bg`/`--ok-bg` + tepi kiri 4 px warna status — satu-satunya bidang ber-tint besar di halaman; (b) tile di dalam band diputihkan (`--surface`) supaya angka tidak tenggelam, nilai tile berwarna `--danger-ink`/`--warn-ink`/`--ok-ink`, lencana kepala diputihkan agar tidak menyatu dengan tint, kotak `.board-alert` di band danger dibalik jadi putih; (c) judul band naik ke `--fs-5` (18 px) sebagai hierarki "band = kepala, kartu lain = isi"; (d) fakta keputusan disusun 2 kolom (`.safety-band .fact-list`) agar nilai tidak melayang jauh dari label di lebar 900 px; (e) tombol "Tinjau N batch gagal" duduk di kolom kanan sejajar fakta, peringatan selebar band di bawahnya; (f) kepala kartu "Batch perlu segera dipakai" diseragamkan (`board-card-head` + lencana "≤ 48 jam"). Label kepala band sengaja TANPA angka ("Ada batch gagal") karena angkanya sudah ada di tile — halaman ini tidak menyimpan dua penyaji angka yang sama. Tidak ada warna baru, tidak ada radius baru, tidak ada hitungan baru di klien. Gerbang: suite frontend 186 berkas / 2035 tes lulus, `tsc --noEmit` 0, `next lint` 0, `radius-scale-css` + `design-tokens-kontrak` hijau; live di viewport 1262 px: band 947 px tone=danger (rgb(254,242,242), tepi kiri rgb(198,40,40), tile putih), grid bukti 543/388 px, tanpa overflow horizontal.

- [2026-10-28] **Pass kerapian TERUKUR halaman Keamanan Pangan: dua ruang kosong besar dihapus tanpa menambah hiasan baru (frontend saja).** Baseline diukur lebih dulu di aplikasi hidup (viewport 1262 px, kepala SPPG Bandung): band 947x394 px, dan DUA ruang kosong terukur: (1) baris tile penanda `0 DITAHAN` + `0 KEDALUWARSA` memakai grid 4 kolom padahal isinya 2 -> 452 px kosong di kanan, ditambah keterangan `stat-tiles-legend` yang menempati barisnya sendiri selebar band (42 px); (2) baris bukti dua kolom 1,4fr/1fr menaruh kartu `Bukti suhu` 543x904 px di samping `Batch perlu segera dipakai` 388x143 px -> 761 px kosong di kolom kanan. Perbaikan: (a) keterangan dipindah ke kolom 2 band dan tile penanda ke kolom 1 (`grid-column`), jadi satu baris penuh (markers 478 px + keterangan 416 px) dan satu baris band hilang; markers memakai `repeat(auto-fit, minmax(220px, 1fr))` supaya tampilan jaringan yang hanya punya satu penanda tidak separuh kosong; (b) `.safety-grid-evidence` jadi SATU kolom: kartu bukti selebar halaman (baris ledger 117 -> 100 px karena alasan server tidak lagi membungkus) dan kartu `segera` selebar halaman dengan daftarnya disusun 2 kolom (2 item 455x38 px). Kalimat keterangan berubah dari `Penanda di bawah` menjadi `Penanda menandai kondisi tambahan ...` karena posisinya kini di samping (di <=1100 px ia kembali di bawah, jadi kata arah dihapus). Hasil terukur: band 394 -> 328 px (-66), ruang kosong baris penanda 452 -> 0 px, ruang kosong kolom kanan 761 -> 0 px, dokumen 3883 -> 3856 px, luapan horizontal 0 px, teks terpotong 0, tumpang tindih anak kartu 0, font terkecil di band+bukti 12 px. Gerbang: vitest 186 berkas / 2035 tes lulus, `tsc --noEmit` 0, `next lint` 0, gate `radius-scale-css`/`design-tokens-kontrak`/`token-warna-komponen` hijau (dijalankan ulang sesudah suntingan CSS terakhir). Artefak angka sebelum/sesudah: `_qa/keamanan-pangan-28okt-sebelum.json` dan `_qa/keamanan-pangan-28okt-sesudah.json`. Batas jujur: (i) data demo bergeser antar-run (11 -> 15 batch), jadi yang dibandingkan adalah angka struktural dan baris bukti yang sama-sama 6 baris; (ii) uji lebar 375/768 px tetap tidak bisa lewat iframe (dokumen menolak framing) -> responsif diverifikasi dari aturan media query, dan reset `.safety-band > .stat-tiles-markers/.stat-tiles-legend { grid-column: 1/-1 }` ditambahkan di blok <=1100 px karena selektor itu lebih spesifik daripada `.safety-band > *`; (iii) tile `Status lain` (hanya muncul bila ada status uji di luar empat kategori) masih 1 tile di grid 4 kolom - tidak disentuh karena tidak pernah muncul pada data sekarang.

- [2026-10-28] **Overview: "Informasi pengiriman" + "Telemetri Node" + daftar "Status Lokasi" DIGANTI panel "Monitor harga komoditas" (permintaan pemilik: "saya mau hapus dan ganti menjadi monitoring harga komoditas ... gunakan skill ui ux dan terapkan semuanya").** Keputusan yang mengikat: (a) penghapusan tingkat-MOUNT — `ShipmentCard`, `NodeTelemetry`, dan `StatusLocationList` dilepas dari Overview tetapi berkas komponen + tesnya TETAP ada (isi kiriman masih terbaca di tab Pemasok lewat `ShipmentBoard` dan di Decision & Evidence); (b) data panel = SALINAN harian PIHPS Bank Indonesia (Pasar Tradisional, Rp/kg, 21 komoditas, tingkat provinsi/kota) yang ditarik `backend/scripts/tarik_harga_pihps.py` ke `data/harga_pihps/pihps_latest.json` dan dibaca `GET /price/monitor` lewat `app/core/harga_monitor.py` — **tabel `price_signals` tidak disentuh**, supaya metrik deviasi 5%/15% tidak berubah diam-diam; (c) hari tanpa publikasi (Sabtu/Minggu) digambar sebagai JARAK, bukan harga 0; (d) panel memakai mode INDEKS (basis 100) sebagai bawaan karena tiga komoditas punya level harga jauh berbeda (beras ~Rp17rb vs ayam ~Rp39rb) sehingga grafik rupiah terbaca sebagai tiga garis datar; (e) wortel TIDAK diterbitkan PIHPS → disebut sebagai keterbatasan cakupan di layar, bukan digambar seri palsunya; (f) nav "Lompat ke bagian" Overview turun 5 → 4 tujuan (Ringkasan · Peta & antrean · Kecukupan · Harga pasar). Bukti: `pytest tests/test_harga_monitor.py` 17 lulus, `tests/price-monitor*.test.*` 31 lulus, suite frontend penuh 2.088 lulus, `tsc` 0, `next lint` 0, `next build` sukses; verifikasi hidup :3010 (BGN Monitor = cakupan nasional; Kepala Bandung = Kota Bandung).

- [2026-10-28] **Ringkasan pengawasan + Bukti suhu: tiga cacat pemahaman ditutup di tampilan, bukan dengan hiasan baru (frontend saja).** Permintaan pemilik: "upgrade ui ux supaya lebih enak dilihat dan dipahami ... no ai slop dan tidak aneh dengan desain halaman lain". Yang diperbaiki, semuanya terukur di DOM hidup: (a) **bar komposisi tanpa keterangan** — bar 5 px menggelar selebar kartu (913 px) dengan empat warna yang tidak punya padanan label, dan tanpa penyebut (porsi dari berapa batch?). Sekarang tiap sel angka membawa titik 8 px yang warnanya SAMA dengan segmen bar (`--safe-ink-tint`/`--warn-ink`/`--danger-ink`/`--neutral-ink`) dan bar duduk di baris bersama penyebut `dari N batch`; (b) **dua angka berdempet** — penanda "Ditahan (karantina) **1** 540 kg tidak boleh dialokasikan" terbaca sebagai "1540 kg" karena hitungan batch dan berat karantina bersambung tanpa pemisah. Sekarang hint penanda didahului `· ` (`<span aria-hidden>`), jadi "1 · 540 kg"; (c) **kalimat profil diulang enam kali** di kartu Bukti suhu — "Profil sim-2026-10-27.v1 — simulasi, bukan standar regulasi" dicetak di SETIAP baris sehingga menutupi yang memang beda antar-baris (asal log, jumlah sampel, alasan server). Sekarang dicetak SEKALI sebagai catatan kaki kartu bila profilnya seragam; kalau tidak seragam (ada komoditas tanpa profil) tiap baris tetap menyebut miliknya sendiri — jadi tidak ada label yang dikarang saat keadaan berbeda. Tidak ada warna, radius, bayangan, gradien, ikon, atau gerak baru; bentuknya memakai bahasa yang sudah ada di halaman lain (`.kpi-card-label` = titik + label, `.safety-marker` = titik + nilai, `.safety-foot` = lipatan sebaris). Terukur (viewport 1262 px): band 947x227 -> 947x244 px (**+17 px** = harga penyebut: baris bar 5 px jadi 18 px berisi teks 12 px, plus 4 px jarak baris penanda), bar komposisi 913x5 -> bar 831 px + penyebut 82 px dalam baris 913x18, baris Bukti suhu 3 -> 2 paragraf (profil dipindah), enam baris tetap sama tinggi per baris grid (76 px), luapan horizontal 0 px, font terkecil 12 px. Batas jujur: data demo bergerak antar-pengukuran (cakupan lokasi sendiri 12 batch -> cakupan jaringan 118 batch), jadi tinggi dokumen (3488 -> 3032 px) TIDAK boleh dibaca sebagai efek suntingan; artefak angka sebelum/sesudah: `_qa/keamanan-pangan-28okt-ringkasan-suhu.json`. Uji baru yang mengunci janji ini: `tests/food-safety-board.test.tsx` (penyebut + 4 titik kategori, dan teks pengguna tidak lagi memuat "1 540 kg") dan `tests/temperature-evidence-card.test.tsx` (profil seragam dicetak sekali; profil tidak seragam tetap per baris). Gerbang: vitest 189 berkas / 2087 tes lulus, `tsc --noEmit` 0, `next lint` 0. Responsif 375 px tetap tidak bisa dibuktikan lewat iframe (dokumen menolak framing); aturan <=640 px dan <=1100 px tidak diubah dan label memakai elipsis supaya tidak melimpah.

- [2026-10-28] **Kartu feed Recommendations diringkas (frontend saja): pengirim, badge kasus, dan verdict verifier mentah DIHAPUS dari kartu.** Permintaan pemilik: "shape rekomendasi diperkecil dan hapus informasi konsisten, supplier, dan kasus". Tiga elemen yang dilepas dari `components/RecommendationCard.tsx`: (a) baris "Rencana kirim dari pemasok X ke Y" + helper `routeLineOf()` (dihapus seluruhnya beserta `tests/recommendation-route.test.ts` — tidak ada pemakai lain; pengirim tetap terbaca di Decision & Evidence lewat panel konteks pemasok), (b) badge "Kasus: …" (`caseLabelOf()` TETAP diekspor karena kepala Decision & Evidence memakainya, dan `lib/decision-feed.ts` masih mencocokkan `demo_case` saat pencarian, jadi placeholder "…kasus…" tetap benar), (c) narasi `verifier_note` — isinya verdict mentah backend ("consistent"/"flagged") yang tampil sebagai satu kata Inggris tak bertuan di tiap kartu; `rejection_reason` TETAP dicetak (kontrak lama, diuji) tetapi kini satu baris bergaris kiri, bukan kotak. Tata letak: kedua badge status berjejer ke samping (dulu bertumpuk 50 px; di ≤720 px kembali bertumpuk), padding kartu 14 px vertikal / 16 px horizontal, jarak feed 10 → 8 px, jarak baris ajakan 18 px. Terukur di DOM hidup (viewport 1262 px, Kepala Bandung): tinggi kartu **188 → 113-114 px** (−39%), seragam untuk 10 kartu — versi pertama (padding 12 / jarak 8 = 99-100 px) dinaikkan dua kali atas permintaan pemilik: "sedikit dinaikan saja" lalu "kalimat Klik untuk rincian duduk pas di bawah waktu, tidak ada space" (jarak meta→ajakan 12 → 18 px, terukur), luapan horizontal 0 px, `/\bconsistent\b/`, `/\bflagged\b/`, `Kasus:`, `Rencana kirim` = 0 kemunculan di seluruh `.feed`. Uji kontrak diperbarui/ditambah: `tests/recommendation-card.test.tsx` (verdict verifier tidak dicetak, baris pengirim + badge kasus tidak dirender), `tests/ops-console.test.tsx` (badge kasus hilang dari kartu feed, `caseLabelOf` tetap melabeli kepala bukti). Gerbang: vitest 191 berkas / 2.128 tes lulus, `tsc --noEmit` 0, `next lint` 0, gate token (`design-tokens-kontrak`, `radius-scale-css`, `token-warna-komponen`, `token-alias-css`, `token-bayangan`) 27 tes hijau, tanpa warna/radius/bayangan baru. Batas jujur: uji lebar 375 px lewat iframe tetap gagal (dokumen menolak framing); responsif diverifikasi dengan menyempitkan `.feed` ke 358 px di DOM hidup — 0 luapan, badge membungkus 2 baris — ditambah aturan media query ≤720 px yang menumpuk badge kembali.


- [2026-10-28] **Overview: "Perlu keputusan" dipangkas setengah dan di bawahnya ditambah kartu bukti "Jejak kepercayaan" (permintaan pemilik).** Keputusan yang mengikat: (a) antrean menampilkan DUA baris teratas, bukan empat — satu konstanta `QUEUE_SHOWN` di `app/page.tsx` dipakai juga oleh tile "Rekomendasi menunggu" (`pendingKpiCopy`), supaya "+N lain menunggu tindakan" di tile dan di kaki antrean tidak pernah berbeda angka; sisa pekerjaan tetap dinyatakan apa adanya ("+10 keputusan lain menunggu tindakan", "+21 lewat tenggat") dan seluruhnya tetap bisa dibuka lewat tab Recommendations — yang dipangkas ruang yang terlihat, bukan jumlah kerja; (b) kartu baru menjawab pertanyaan dasar "kenapa angka di halaman ini bisa dipercaya" dengan EMPAT bukti: blok ledger (`GET /ledger/verify`), batch lolos uji (`GET /batches`), keputusan tereksekusi (`GET /decisions`), dan node tanpa angka terlapor (`GET /balance/map`, sisi berstatus `tidak_ada_baris`); (c) logika murni di `frontend/lib/trust-trail.ts` (16 uji `tests/trust-trail.test.ts`) memegang aturan "tanpa angka karangan": data tidak terbaca → "—" + alasan (bukan 0), 0 hanya sah bila terukur (mis. 0 dari 10 node tanpa catatan), setiap rasio menuliskan totalnya ("101/118"), dan batch yang ditahan TIDAK dihitung lolos; kepala kartu menulis keadaan terburuk yang jujur (`plain` "sebagian belum terbaca" menang atas "perlu tinjau", karena "terverifikasi" tidak boleh ditulis sementara satu bukti belum termuat). Tampilan (revisi kedua hari yang sama, arah pemilik "dibuat 2 baris, ada teks yang hilang, kurang center atas-bawah", lalu "jejak kepercayaan terlalu banyak space"): `components/TrustTrailCard.tsx` + blok CSS di `app/overview-p0.css` — empat bukti disusun **grid 2 baris × 2 kolom** dengan pemisah garis rambut (bukan empat kotak berbingkai, bukan pula satu daftar memanjang), dan **tiap sel hanya DUA baris**: label di kiri + angka/keadaan di kanan pada baris pertama, alasan selebar sel di baris kedua. Sebelumnya label/angka/alasan bertumpuk tiga baris sehingga sel 77 px dan separuh kanan sel kosong. **Alasan SELALU dicetak penuh** (boleh membungkus) — versi sebelumnya menyembunyikannya saat metrik aman dan memotongnya dengan elipsis, sehingga kalimat bukti ("102 blok tertaut keputusan · checkpoint luar cocok") hilang dari layar. Catatan teknis yang menjebak: `dl > div > dt/dd` tidak boleh dipecah lagi ke dalam div baris (invalid), dan membuat `dd` memuat `foot` selebar 100% membuat lebar intrinsik `dd` = lebar teks alasan sehingga angka selalu terdorong ke baris baru; karena itu sel memakai `div`/`span` dengan `role="list"`/`role="listitem"` dan flex-wrap (label `flex: 0 1 auto`, angka `margin-left: auto`, alasan `flex: 0 0 100%`). Tinggi (arah pemilik "panjangin lagi sampe space kosong rata dengan shape peta"): **antrean memanjang mengisi sisa kolom** (`.overview-side .queue-card { flex: 1 1 auto }`) sehingga tepi bawah KOLOM KANAN rata dengan tepi bawah kartu peta, sementara **kartu bukti tetap setinggi isinya** (`flex: 0 0 auto`) supaya tidak ada rongga di dalam kartu bukti. Ruang sisa antrean dikumpulkan di atas tombol "Lihat semua rekomendasi" (`.queue-foot` `margin-top: auto`), jadi CTA duduk di dasar kartu dan isi (dua baris + catatan "+N lain menunggu tindakan") tetap rapat di atas — bukan lubang di tengah. Terukur di DOM hidup (viewport 1262 px, BGN Monitor): susunan bertumpuk — antrean 947x257 px, kartu bukti 947x**158** px (dari 214 px, −26%) dengan empat sel SAMA tinggi 51 px, luapan 0; susunan 2 kolom (grid `.overview-split` dipaksa di DOM untuk mensimulasikan >=1280 px) — kolom kanan 312 px: antrean **452** px (isi 748-980 px, tombol 1092-1130 px, sisa 100 px di atas tombol) + kartu bukti 258 px, dan tepi bawah kolom **1417 px = tepi bawah kartu peta 1417 px** (selisih 0 px); sel kartu bukti 132x101 px tanpa luapan horizontal. Di <=1280 px susunan menumpuk selebar halaman dan flex-grow tidak berefek — tidak ada yang perlu diratakan. Data nyata saat pengukuran (BGN Monitor): ledger 978 blok (78 tertaut, checkpoint luar cocok), batch 101/118 lolos (2 gagal uji, 1 ditahan, 13 perlu verifikasi), keputusan 5/51 tereksekusi, node 0/10 tanpa catatan. Gerbang: vitest 196 berkas / 2218 tes lulus (termasuk 16 uji `tests/trust-trail.test.ts`), `next lint` 0. Catatan gate: `tsc --noEmit` pada berkas aplikasi 0 galat, tetapi `tests/approval-panel.test.ts` — berkas uji baru milik pekerjaan paralel, bukan perubahan ini — masih menyisakan 3 galat `TS18047` saat entri ini ditulis. Batas jujur: (i) susunan >=1280 px diverifikasi dengan memaksa aturan grid di DOM (viewport sesi 1262 px), bukan dari monitor 1440 px; (ii) `ledger`/`batches` berasal dari `useToday` yang mem-poll 60 detik, jadi angka kartu ini bergerak lebih lambat daripada peta (5 detik) — sengaja: bukti tidak perlu secepat posisi truk.

- [2026-10-28] **Overview: kartu "Kecukupan pasokan" menjadi bar chart SETENGAH halaman dan separuh kanannya panel "Surplus wilayah lain" (permintaan pemilik).** Keputusan yang mengikat: (a) angka surplus wilayah TIDAK dihitung klien dari peta — peta akun SPPG dibatasi cakupan (Ruling 2026-10-14) sehingga hanya berisi satu lokasi, jadi "daerah lain" mustahil ada di data klien; sumbernya endpoint baru `GET /surplus/regions` yang mengagregasi per `Location.region` lintas lokasi (boleh empat komoditas sekali panggil, `exclude` = lokasi pengguna). (b) Kejujuran angka: sumber surplus hanya lokasi yang permintaannya tercatat (PLAN-023), kg lokasi pengguna yang dibuang dilaporkan (`totals.excluded_surplus_kg`), lokasi bersurplus tanpa baris permintaan dihitung terpisah, dan panel kosong menulis SEBAB bukan "0 kg". (c) Wilayah dengan surplus di bawah ambang 150 kg tetap disebut — dikumpulkan satu baris "surplus kecil" — karena baris 0,5 kg di daftar utama hanya menghasilkan batang tak terlihat; yang dipangkas ruang grafiknya, bukan angkanya. (d) Dua kartu memakai satu bahasa visual (`supply-adequacy`/`sa-*`): yang berbeda hanya arti baris (wilayah vs komoditas) dan susunan kolom; warna batang komoditas memakai palet kategorikal, BUKAN token status, supaya hijau/merah tetap berarti aman/bahaya. Terukur di DOM hidup (viewport 1000 px, Kepala Bandung): grid 467,5+467,5 px, batang grafik 406 px selebar kartu, baris grafik 139-162 → 106-129 px, panel 1 wilayah layak (Jawa Barat 3.554,81 kg) + 4 wilayah surplus kecil (16,76 kg), tanpa luapan horizontal dan tanpa galat konsol; BGN nasional berjudul "Surplus per wilayah" dengan sub "seluruh jaringan · 1 komoditas". Gerbang: vitest 2.132 lulus / 191 berkas, `tsc` 0, `next lint` 0, ruff bersih, pytest surplus+drift 22 lulus. Batas: `next build` tidak dijalankan (dev server hidup), responsif 375 px diverifikasi dari media query.

- [2026-10-28] **Kecukupan pasokan jadi bar vertikal ringkas + soft UI (lanjutan permintaan pemilik).** Keputusan yang mengikat: (a) TINGGI BATANG dinormalkan per kolom — stok dibagi kebutuhan KOMODITAS/LOKASI ITU SENDIRI, bukan dibagi kg terbesar di grafik. Percobaan pertama memakai skala kg bersama dan hasilnya menipu: ayam berkebutuhan 400 kg tampil sebagai tonggak 6 px walau cakupannya 65%, sementara beras mendominasi seluruh kotak. Dengan normalisasi per kebutuhan, tinggi batang SELALU sama dengan angka cakupan di atasnya, dan garis putus-putus di puncak kotak berarti "kebutuhan (100%)" untuk semua kolom. (b) Stok yang TIDAK ikut dihitung lensa (tidak layak / tidak segar) tetap digambar sebagai bagian batang, tetapi diberi garis putus-putus putih di dalam batang pada posisi kg yang dihitung — jadi selisih batang ↔ garis adalah kg yang tidak layak, dan angkanya tidak pernah lebih besar dari gambar. (c) Tanpa kebutuhan terukur tidak ada batang (bukan 100% mengarang) dan catatannya berbunyi "belum tercatat", bukan "0 kg layak". (d) Saat kolom lebih dari 6 (BGN nasional 10 lokasi), nama dibaca tegak dan angka mengecil: label horizontal terpotong menjadi "Jak…/Band…" pada kolom 40 px, dan itu terbukti di DOM sebelum diperbaiki. (e) Dua grafik bentuk lama dilepas dari Overview (tetap di repo + tes), pemasangan dijaga tes kontrak. (f) Token bayangan peran baru `--shadow-inset-soft` untuk permukaan terbenam; tanpa itu file kartu memakai literal dan gerbang `tests/token-bayangan.test.ts` merah. Terukur di DOM hidup (viewport 1000 px, kartu 468 px): Kepala Bandung 542 px tinggi dengan batang 65/68/70/100% dan garis dalam 80% pada beras; Gizi Bandung (lensa Kesegaran) 57/59/68/80; BGN 502 px, 10 kolom tanpa tabrakan angka. Gerbang: vitest 2.166 lulus / 193 berkas, `tsc` 0, `next lint` 0. Batas: `next build` tidak dijalankan karena dev server hidup.

- [2026-10-28] **Kartu Overview dibuat "simple, sedikit teks" (permintaan pemilik).** Aturan yang mengikat untuk kartu sejenis: (a) TIDAK ada paragraf penjelasan di dalam kartu. Yang tercetak maksimum judul + satu baris sub + satu angka ringkasan + legenda kata-per-kata + satu baris petunjuk; semua kalimat pindah ke `title` (hover) dan aria-label, sehingga kejujuran angka tetap bisa diperiksa tanpa memenuhi layar. (b) Angka yang mengulang angka lain tidak dicetak — mis. "3.554,81 kg / 3.554,81 kg layak dialihkan" kini satu angka saja, dan "1 wilayah layak dialihkan" jadi "1 wilayah layak". (c) Label satuan yang berulang ("cakupan"/"segar" di bawah tiap angka) dihapus karena pil lensa sudah menyebutnya. (d) Kepala panel dua kartu ditumpuk (judul → angka → chip) supaya judul tidak terlipat dua baris karena angka besar di kanan. (e) Dijaga tes: `tests/adequacy-columns-render.test.tsx` membatasi teks tercetak kartu < 320 karakter dan melarang paragraf lama muncul kembali. Terukur: teks kartu 209 karakter, tinggi 378 px (dari 542 px); panel 460 px dengan teks 324 karakter. Gerbang: vitest 2.194 lulus / 195 berkas, `next lint` 0; `tsc` memerahkan 3 galat lama di tests/approval-panel.test.ts (bukan dari perubahan ini, tersingkap setelah cache incremental invalid).
- [2026-10-28] **"Detail & jejak agen" dibuka sebagai POPUP, bukan pindah tab (permintaan pemilik).** Alasan yang mengikat: pengguna yang mengklik kartu ke-7 dari feed kehilangan posisi gulir + filter, lalu harus kembali sendiri; dokumen acuan `D:\Downloads-detail-keputusan.md` menggambarkan pola drawer/popup untuk alur yang sama. Yang dikerjakan: (a) ISI detail dipindah dari `components/DecisionEvidence.tsx` (721 baris) ke `components/DecisionDetail.tsx` (572 baris) tanpa mengubah markup — halaman tinggal cangkang (PageHeader + DecisionPicker + SectionJump + keadaan kosong), dengan prop baru `dalamPopup` yang mematikan pengukur posisi zona (memakai gulir jendela) dan bilah pintasan bawah; (b) `components/DecisionDetailPopup.tsx` memakai cangkang `Popup` yang sudah ada (portal, role=dialog, aria-modal, Escape, klik latar, focus trap, kunci gulir, fokus balik) + pengalih dua tampilan "Detail & bukti" / "Jejak agen (N)" — tombol `aria-pressed` + `is-active`, BUKAN role=tablist (pola pengalih yang sudah dipakai konsol); "Buka jejak agen" di dalam detail kini berpindah tampilan DI JENDELA YANG SAMA (keputusan pemilik), memakai `AgentTraceViewer` dari endpoint yang sama (GET /decisions/{id}/traces); (c) alur klik yang DIUBAH: kartu feed Recommendations dan antrean "Hari Ini" → `bukaPopupKeputusan()` (set `selectedId` + popup, TIDAK set tab), fokus dikembalikan ke kartu pemicu lewat `popupTriggerRef`; yang TETAP pindah tab: deep link `?keputusan=`, daftar PO (`bukaKeputusanDariPO`), dan sidebar — sebab semuanya berbagi URL/tautan dan popup tidak bisa dibagikan. Terukur di DOM hidup (Kepala Jakarta, viewport sempit 570 px): panel 1000x488 px (batas 86vh milik `.popup`, badan menggulir 2.823 px isi dalam 398 px), `role=dialog` + `aria-modal=true` + `aria-labelledby=popup-detail-keputusan-title`, judul "Detail keputusan #2ae7e0f9", `.evidence-actionbar` 0 di popup, scroll halaman dikunci (`body.style.overflow=hidden`), tab tetap "Recommendations (2)" saat popup terbuka, ESC menutup + fokus kembali ke `link-button` kartu, tautan "Ke zona keputusan" di dalam popup menggulir BADAN POPUP (scrollTop 0 → 543 px) tanpa menggeser halaman di belakang (window.scrollY tetap 0). Bug yang tertangkap saat verifikasi layar dan sudah diperbaiki: menutup lalu membuka kartu yang SAMA masih menampilkan tampilan "Jejak agen" (komponen tidak dilepas saat `open=false`) — efek reset kini bergantung pada `[decisionId, open]`, dikunci uji. Uji: `tests/decision-detail-popup.test.tsx` (11 tes, env jsdom: dialog & label, tanpa bilah pintasan, pindah ke jejak & kembali, ESC, klik latar vs isi, fokus balik, ganti keputusan, buka ulang kartu sama, dan kontrak sumber `app/page.tsx` bahwa kartu feed/antrean memakai `bukaPopupKeputusan` dan tidak lagi `setTab("evidence")`). Gerbang: vitest 195 berkas / 2.195 tes lulus, `tsc --noEmit` 0, `next lint` 0, tanpa warna/radius/bayangan baru (kelas `.popup-decision*` hanya token). Batas jujur: (i) popup memuat 2.823 px isi dalam badan 398 px pada viewport pendek — tanpa navigasi bagian halaman; kalau pemilik ingin lompat antar-bagian, pasang bilah ringkas di dalam popup, jangan hidupkan `SectionJump` (tautannya menunjuk jangkar halaman); (ii) dua cacat LAMA ikut terlihat dan belum disentuh: judul hero mencetak slug mentah "supplier exclusion restoration: …" (tidak ada label untuk `supplier_exclusion_restoration`), dan hero menulis "Rp0" untuk biaya yang di kartu feed ditulis "—"; (iii) ejaan berkas baru tetap ber-CRLF karena tes kontrak membaca sumber mentah.


- [2026-10-28] **Dua kartu Overview: warna SOLID, panel surplus dipangkas lagi (permintaan pemilik).** Aturan: (a) TIDAK ada gradasi di kartu Overview — latar kartu, kotak batang, segmen, titik legenda, skeleton, dan hero panel semuanya satu warna solid dari token; kedalaman hanya dari bayangan token (`--shadow-2`, `--shadow-inset-soft`). Ini dijaga tes yang menolak kata `gradient` di `adequacy-columns.css` dan `surplus-regions.css` — kalau nanti butuh gradasi, ubah tesnya secara sadar, jangan diam-diam. (b) Baris legenda komoditas di panel surplus DIHAPUS: chip "Asal" sudah menyebut nama komoditas + titik warnanya, jadi legenda hanya mengulang. (c) Chip "N wilayah layak" dihapus — baris wilayah sudah menyebut daerahnya. (d) Catatan kaki panel dihapus: "dihitung server" masuk ke baris sub, dan kalimat kejujuran lengkap (peta SPPG hanya memuat lokasi sendiri, hanya lokasi dengan permintaan tercatat yang boleh menyumbang, ambang 150 kg, surplus lokasi sendiri tidak dihitung) menjadi `title` kartu — tetap bisa diaudit lewat hover, tanpa memenuhi layar. Terukur: teks panel 324 → 196 karakter, tinggi 460 → 360 px; kartu kecukupan 378 px, jadi kedua kartu kini hampir setinggi. Gerbang: vitest 2.206 lulus / 196 berkas, `next lint` 0. Sisa: 3 galat tipe lama di tests/approval-panel.test.ts.
- [2026-10-28] **Dua cacat lama di kepala keputusan ditutup: judul slug mentah & "Rp0" untuk biaya tak diketahui.** (a) **Judul**: `decisionHeadline()` di `frontend/lib/evidence.ts` memakai peta `HEADLINE_VERBS` yang menyebut tipe KARANGAN (`supplier_restoration`, dan `supplier_reinstatement` pada penjaga rute) sehingga `supplier_exclusion_restoration` jatuh ke `type.replace(/_/g, " ")` dan tampil sebagai "supplier exclusion restoration: …" di layar. Tipe yang benar-benar bisa tersimpan hanya enam (`CheckConstraint decisions_decision_type_check` di `backend/app/models/decisions.py`). Sekarang labelnya "Pulihkan status pemasok" (mengikuti frasa UI yang sudah ada) dan himpunan `JENIS_ADMINISTRATIF` (price_anomaly, supplier_exclusion, supplier_exclusion_restoration) memakai "di <lokasi>", BUKAN panah — tidak ada barang berpindah. Judul terukur: "Pulihkan status pemasok: CV Ayam Kampung Cugenang di Jakarta". (b) **Biaya**: `Number(s.safe_delivered_cost ?? d.safe_delivered_cost)` mengubah `null` (kolom DB kosong, dipetakan eksplisit oleh `backend/app/api/decisions.py`) menjadi 0, jadi hero mencetak "Rp0" sementara kartu feed (yang memakai `formatIDR`) mencetak "—". Sekarang `angkaAtauNull()` membedakan tak-diketahui dari nol, biaya kosong ditulis "—", selisih dari harga beli tidak dihitung, dan hint rekonsiliasi tidak lagi mencetak Rp0; nol yang BENAR-BENAR tersimpan tetap "Rp0". Terukur di layar: kartu "SDC —" ↔ hero "Biaya aman terkirim —", tidak ada "Rp0" di hero. Uji: `tests/evidence-summary.test.ts` +3 (restorasi tanpa slug/panah; setiap tipe backend punya label; bentuk lama tidak berubah) dan +6 (null→"—" identik dengan kartu, selisih tidak dihitung, medan tak dikirim tidak dikarang, 0 tersimpan tetap Rp0). Gerbang: vitest 196 berkas / 2.218 tes lulus, `tsc --noEmit` 0, `next lint` 0. Efek samping yang DITERIMA sementara (belum diputuskan pemilik): karena satu aturan yang sama, judul `supplier_exclusion` dan `price_anomaly` kini juga menyebut pihak + lokasi ("Keluarkan pemasok: CV Ayam Kampung Cugenang di Jakarta", "Sesuaikan harga 600 kg telur di Jakarta") — sebelumnya diam soal siapa & di mana. Kalau pemilik ingin keduanya persis seperti dulu, persempit `JENIS_ADMINISTRATIF` ke tipe restorasi saja.


- [2026-10-28] **Kepala kartu Overview tanpa lokasi/jam.** Pemilik menunjuk baris "Jakarta · 22.00" di bawah judul "Kecukupan pasokan" dan meminta dihapus. Keputusan: mode komoditas tidak lagi mencetak baris sub sama sekali — kepala kartu hanya judul + satu angka ringkasan ("4/4 kurang"); lokasi, jumlah komoditas, sumber snapshot, dan jam hitung pindah ke `title` judul (hover) dan aria-label. Mode lokasi (monitor nasional) TETAP mencetak "komoditas · N lokasi" karena itu pembeda utamanya. Jam juga dihapus dari sub panel surplus (kini "di luar Bandung · dihitung server"). Dijaga tes: kartu tidak boleh punya `.ac-sub`, dan teks tercetak panel tidak boleh memuat pola jam `HH.MM`. Terukur: kartu 361 px, panel 360 px (praktis setinggi). Gerbang: vitest 2.219 lulus / 196 berkas, `next lint` 0.

- [2026-10-28] **Overview: antrean "Perlu keputusan" kembali menampilkan EMPAT keputusan, dan sisa tinggi kolom kanan diserap KANVAS PETA (bukan rongga).** Koreksi pemilik setelah revisi sebelumnya: "kenapa gak nampil yang lainya?" — pemotongan dua baris membuat antrean hanya menampilkan 2 dari 32 keputusan. Keputusan yang mengikat: (a) `QUEUE_SHOWN` 2 → 4 (app/page.tsx) — yang dipangkas TINGGINYA, bukan jumlah yang bisa dibaca: baris antrean memang sudah padat (56 px, dua baris teks + badge), jadi empat keputusan masuk dalam tinggi yang dulu dipakai dua baris longgar; sisa pekerjaan tetap dinyatakan ("+28 keputusan lain menunggu tindakan") dan konstanta yang sama dipakai tile "Rekomendasi menunggu" sehingga 32 / 4 / +28 tidak pernah berbeda antar-tempat. (b) Kolom kanan kini bisa LEBIH TINGGI daripada kartu peta saat empat baris ditampilkan (terukur 537 px vs 610 px tinggi peta pada 312 px)—karena itu kartu peta dibuat kolom flex dan kanvas yang menyerap kelebihan: `.overview-split .map-card{display:flex;flex-direction:column}`, `.map-body{flex:1 1 auto;min-height:0}`, `.map-shell{flex:1 1 auto;min-height:400px}`, `.map-shell .map-gl{flex:1 1 auto;height:auto;min-height:400px}`. Tanpa aturan ini kartu peta melar dengan ±85 px ruang kosong di bawah "Rincian lapisan peta" (terukur); dengan aturan ini MapLibre ikut membesar (canvas 400 → 483 px) sehingga tidak ada rongga, dan batas bawah kanvas tetap 400 px. Antrean tetap `flex: 1 1 auto` (memanjang mengisi sisa kolom, CTA di dasar kartu) dan kartu bukti `flex: 0 0 auto` (setinggi isinya). Terukur di DOM hidup (viewport 1262 px, BGN Monitor): susunan bertumpuk — antrean 947x368 px (empat baris 56 px), kartu bukti 947x158 px, peta 947x610 px; susunan 2 kolom (grid dipaksa di DOM untuk >=1280 px) — kolom kanan 312 px: antrean 537 px + kartu bukti 258 px, tepi bawah kolom = tepi bawah kartu peta (selisih 0 px), `map-body` mengisi seluruh kartu (selisih 0 px), kanvas peta 485 px. Gerbang: vitest 197 berkas / 2.244 tes lulus, `next lint` 0. Batas jujur: (i) susunan >=1280 px masih disimulasikan di DOM karena viewport sesi 1262 px; (ii) saat verifikasi, dev server sempat mati dan gagal build karena pekerjaan paralel (`components/DecisionDrawer.tsx` mengimpor `../lib/detail-keputusan` yang tidak ada — modulnya bernama `lib/drawer-keputusan.ts`; import diperbaiki satu baris dan container `mealchain-frontend` dijalankan ulang), jadi halaman sempat kosong bukan karena perubahan ini. Catatan: `tsc --noEmit` masih 10 galat di berkas pekerjaan paralel (`components/DecisionDrawer.tsx`, `lib/location-network.ts`), bukan di berkas perubahan ini.


- [2026-10-28] **Halaman "Decision & Evidence": modul persetujuan mengikuti `02-approval-action.md` §7 + review PO dijadikan JALUR SUNGGUHAN (dua gerbang).** Keputusan yang mengikat: (a) dua gerbang: `POST /actions/execute` hanya MENERBITKAN PO `draft` (keputusan tetap `approved`, tidak ada barang berangkat), lalu `POST /actions/purchase-orders/{po_number}/approve` oleh Kepala SPPG mengirim PO ke SAP mock (`submitted`) dan menuntaskan keputusan ke `executed`; matriks approval dipakai bersama lewat `_evaluasi_approval` supaya kedua gerbang tidak menyimpang. Konsekuensi yang diterima: pesan "PO ... dibuat (mock)" DIGANTI, dan tes yang mengharapkan `submitted`/`executed` tepat setelah `execute` harus menambah langkah review (`test_actions`, `test_event1_e2e_acceptance`, `test_procurement_execute_guard`, `test_approval_summary`, `test_kpi_act_trace`, `test_status_approved`). (b) Satu kepala, tiga jawaban: "apa menahan, siapa dibutuhkan, apa setelah ini" naik ke atas, kronologi jalur turun ke bawahnya, lima blok lama dilebur jadi satu modul (`components/ApprovalOverview.tsx`) yang seluruh isinya diturunkan modul murni `frontend/lib/approval-panel.ts` sehingga komponen tidak menghitung keadaan sendiri. (c) Ditolak tidak sama dengan kedaluwarsa: penolakan bernada bahaya dan bisa diusulkan ulang, kedaluwarsa bergaris putus-putus dengan nada sendiri (waktu habis bukan tindakan orang). (d) Keadaan kelima yang tidak ada di dokumen ditambahkan karena nyata di lapangan: semua peran sudah menyetujui tetapi PO belum terbit, sehingga panel menulis "Siap menerbitkan PO draft" (sebelumnya "Belum bisa disetujui" padahal ada pekerjaan). (e) Read model diperbaiki, bukan hanya UI: `can_approve`/`can_reject` kini false untuk pembaca di luar `APPROVER_ROLES`; terukur `bgn_monitor` menerima `can_approve: true` sebelum perbaikan, sehingga panel baru menawarkan "Bisa Anda setujui sekarang" kepada peran pengawas. (f) Label pemicu per-peran: "Menunggu rekan" hanya bagi yang sudah menyetujui; yang belum melihat "Setujui sekarang" (terukur: Ahli Gizi menunggu dirinya sendiri). (g) Status PO adalah fakta SERVER (`approval-summary.purchase_order`), bukan rakitan UI dari daftar PO, supaya satu keadaan punya satu sumber. Bukti: DOM hidup tiga peran (Kepala: "Siap menerbitkan PO draft" lalu eksekusi lalu "Menunggu review PO" + "Review PO..." lalu "Selesai"; Ahli Gizi: "Setujui sekarang..." lalu ledger berisi nama+jam; Monitor: "tampilan read-only (Monitor BGN)" dengan semua langkah tertutup beralasan peran), DB `sap_mock_purchase_orders` draft lalu submitted + `decisions.status` executed, vitest 196 berkas / 2218 tes lulus, `tsc` 0, `next build` EXIT 0 (distDir `.next-verif` terpisah karena `.next` dipakai dev server + pekerjaan paralel), 7 berkas backend yang disentuh 56 lulus / 1 skip. Batas jujur: suite backend PENUH pada `mealchain_po_review` masih 59 gagal / 2126 lulus / 31 skip, semuanya galat lingkungan yang diperiksa satu per satu (jendela keputusan lampau pada `test_dispatch_safety_gate` yang memilih keputusan approved TERBARU dari DB bersama; `token tidak valid`/401 karena sesi demo dibangun ulang proses lain saat suite berjalan; `11 == 10` dan `61 == 60` karena lokasi/batch bertambah; satu teardown `ForeignKeyViolation` di `test_approval_summary`) dan berkas yang sama hijau saat dijalankan terisolasi.

- [2026-10-28] **Overview: pasangan kartu "Kecukupan pasokan" + "Surplus wilayah lain" dibuat SAMA TINGGI (permintaan pemilik: "perbaiki lagi keduanya").** Masalah terukur sebelumnya: `.ov-pasokan-grid` memakai `align-items: start`, sehingga grafik kecukupan 468x372 px berdampingan dengan panel surplus 468x328 px — tepi bawah ragged 44 px dan pasangan yang seharusnya terbaca sebagai SATU grafik terlihat seperti dua kotak lepas. Perbaikan (hanya `app/surplus-regions.css`, tanpa warna/radius/bayangan baru): (a) `align-items: stretch`; (b) panel surplus jadi kolom flex (`.ov-pasokan-grid > .sr-panel`), daftar wilayahnya `flex: 1 1 auto` dan chip "Asal" `margin-top: auto` sehingga kelebihan tinggi TIDAK jadi lubang di tengah; (c) baris wilayah di dalam daftar `justify-content: safe center` — di tengah selama ada sisa ruang (kasus BGN: satu wilayah layak, kelebihan 57 px terbagi 29 px atas / 28 px bawah), tetapi kembali ke atas (`safe`) begitu wilayahnya banyak supaya tidak terpotong dan tidak ada baris yang tak bisa dijangkau. Terukur di DOM hidup: BGN Monitor (viewport 1262 px) — kiri 468x372 px, kanan 468x**372** px, selisih tepi bawah 0 px, baris wilayah 106 px di tengah daftar 163 px, chip "Asal" menempel dasar; Kepala Bandung (SPPG) — kiri 468x348 px, kanan 468x**348** px, selisih 0 px, tanpa luapan. Gerbang: vitest 200 berkas / 2.289 tes lulus, `next lint` 0. Catatan jujur: (i) saat verifikasi, dev server beberapa kali gagal build karena pekerjaan paralel di `components/DecisionDrawer.tsx` (`Module not found: ../lib/detail-keputusan` — modulnya `lib/drawer-keputusan.ts`, import saya perbaiki; lalu `Unexpected token`/`Lipat is defined multiple times` saat berkas sedang ditulis), jadi halaman sempat kosong; angka di atas diambil saat kompilasi sehat. (ii) kepala dua kartu masih beda tinggi (kiri 44 px satu baris; kanan 130 px karena hero angka ditumpuk) sehingga isi panel surplus mulai ~57 px lebih rendah — sengaja dari redesign "judul → angka"; kalau pemilik ingin keduanya rata, itu perubahan terpisah.


## 2026-10-28 — Popup "Detail Keputusan" dirancang ulang (tetap di tengah)

Keputusan pemilik: **popup tetap di tengah**, yang berubah hanya desain, tata letak, dan isinya,
mengikuti dokumen acuan `D:\Downloads\01-detail-keputusan.md`. Panel samping (drawer kanan 520 px)
yang sempat dibuat DITOLAK — jangan dikembalikan.

Bentuk sekarang:
- `components/DecisionDrawer.tsx` (nama berkas dipertahankan agar wiring halaman tidak berubah) memakai
  cangkang `Popup.tsx` dengan modifier `.popup-keputusan`: lebar `min(920px, 100%)`, tinggi maksimum
  `min(90vh, 880px)`, terpusat, sudut membulat, animasi naik 8 px. Backdrop memakai gaya `.popup` biasa.
- Isi = grid dua kolom (`.popup-keputusan .popup-body`); bagian lebar penuh memakai `.detail-sec--full`
  (pengalih tampilan, strip alur, aksi, usulan, lipatan).
- Kepala popup memakai slot baru `Popup` → `eyebrow` ("Detail Keputusan") + `meta` (pil status + id 8 aksara).
  Kasus sengaja TIDAK diulang di kepala: ia sudah jadi baris "Alasan" di Fakta dasar.
- Urutan bagian mengikuti §2 dokumen: alur → fakta dasar → biaya → PO → catatan verifier → kewajiban
  persetujuan → aksi → usulan → jejak iterasi → pemasok → bukti & audit. Tampilan kedua "Jejak agen (N)"
  tetap ada di jendela yang sama.
- Tiga bagian dilipat (`<details>` + komponen lokal `Lipat`): Kewajiban persetujuan ("N dari M disetujui"),
  Jejak iterasi ("N langkah"), Bukti & audit (berkas JSON + halaman lengkap). Panjang gulungan badan
  2.008 → 1.088 px pada keputusan uji.
- Biaya disusun §6.1/§6.2: total terkirim + rumus "RpX ÷ N kg" + chip perbandingan di ATAS, lalu tiga
  lapis (dibayar ke pemasok / tambahan sampai tiba / tambahan karena risiko). Angka hanya dari payload
  (`commercial_cost`, `market_reference`), dihitung di `lib/detail-keputusan.ts`.
- Keputusan administratif tidak menampilkan biaya/PO palsu: bagian biaya menjelaskan "tidak membeli barang"
  dan PO menulis "belum terbit".

Kontrak yang dikunci tes: `tests/decision-drawer.test.tsx` (bentuk terpusat, urutan bagian, tiga lapis + rumus,
perbandingan harga, tiga titik PO, jejak di jendela yang sama, wiring `page.tsx` tidak memindah tab) dan
`tests/detail-keputusan.test.ts` (22 uji acuan hitung). Gerbang: 199 berkas / 2.275 tes lulus, tsc 0, lint 0.

## Ronde 41 — 2026-10-28: dokumen 03 §6 masuk guardian (Location Network + pop-up pasokan/permintaan)

**Keputusan 1 — koridor dari `decisions`, bukan tabel baru.** `GET /balance/flows` mengagregasi baris
`decisions` (sumber→tujuan, kg, status per lane) dan TIDAK punya rumus gap kedua. Alasan: dokumen §6.2
meminta garis "yang sudah punya rekomendasi"; membuat tabel alur sendiri berarti dua sumber kebenaran untuk
pasangan lokasi yang sama.

**Keputusan 2 — cakupan peran disempitkan di klien, bukan di endpoint.** `/balance/flows` hanya mengirim
pasangan hasil olahan (pola sama dengan `/surplus/allocations`); `corridorsFromFlows(flows, {dalamCakupan})`
menyaring lane yang tidak menyentuh lokasi terlihat. Kalau kelak ada konsumen lain, cakupan harus pindah ke server.

**Keputusan 3 — peta dipakai ulang (`SupplyMap`), bukan peta kedua.** Dua prop aditif: `corridors`
(layer garis sendiri: source `network-corridors`, warna status, lebar 1,5–4 px dari kg aktif, kedaluwarsa redup)
dan `showSuppliersPins` (bawaan `true`, dimatikan modul ini supaya legenda tidak menerangkan lapisan pemasok
yang tidak dikirim). Peta kedua akan menggandakan 1.900 baris kode MapLibre untuk nol manfaat.

**Keputusan 4 — pop-up memakai `Popup.tsx` yang sudah ada**, bukan dialog baru. Fokus, Esc, kunci gulir, dan
portal sudah diuji di sana; dialog kedua selalu menyimpang pada satu dari empat hal itu.

**Temuan yang diperbaiki (bukan fitur):** (a) `next.config.js` tidak mem-proxy akar `supply`/`demand`, sehingga
pop-up menulis "catatan tidak tersedia" padahal `curl` ke backend menjawab 200 — terukur pada uji UI pertama;
(b) `hoursLabel` menulis "2 hari 24 jam" karena pembulatan jam tidak dibawa ke satuan hari.

Gerbang: tsc 0, lint 0, vitest **200 berkas / 2.289 tes**, build `B4avyq5nyf_GBIMaRKPut`. 0 commit.

## Ronde 42 — 2026-10-28: dokumen 05 §8 masuk guardian (penerimaan barang)

Permintaan pemilik repo: terapkan `05-penerimaan-barang.md` **di repo ini**, bukan di klon lain; desain
sederhana, konsisten dengan token yang sudah ada, dan diuji dengan data/backend sungguhan.

**Keputusan 1 — model data TIDAK diubah.** Repo ini tidak punya mesin ceklis berbobot dokumen 05 (7 butir,
skor 0–100, ambang 65/85, jumlah diterima sebagian). Yang ada: lima titik periksa boolean (`RECEIVING_CHECKS`)
→ catatan `menunggu` → Kepala SPPG setujui/tolak, plus nilai dari harga invoice PO. Karena itu §8.1 ditampilkan
sebagai **titik yang benar-benar ditandai** ("4 dari 5"), bukan skor yang dikarang; menambah tabel/skor berarti
migrasi baru untuk angka yang belum dipakai keputusan mana pun.

**Keputusan 2 — angka pratinjau dihitung SERVER.** `backend/app/services/receipt_value.py` mendapat
`po_dan_harga()` (nomor PO + harga satuan) dan `nilai_dari()`; `_row()` di `api/receipts.py` kini membawa
`batch_quantity_kg`, `po_number`, `unit_price_idr`, `estimated_value_idr` untuk POST, GET, approve, dan reject.
`accepted_value_idr`/`stock_kg` tetap kosong sampai disetujui — jadi UI bisa menampilkan tiga angka (§8.2) dan
menulis asal harga (§8.3) tanpa pernah mengalikan kg × harga sendiri.

**Keputusan 3 — panel jadi daftar + drawer kanan tiga langkah.** `GoodsReceiptDrawer` dipecah: panel mendaftar
batch (kg + nilai, label "(perkiraan)" bila belum disetujui), tombol "Buka penerimaan" membuka drawer 440 px
berisi langkah 1 titik periksa, 2 tiga angka + asal harga + status, 3 penandaan. Drawer dirender lewat
**portal ke `<body>`** karena popup keputusan ber-`transform` membuat `position: fixed` mengacu ke leluhur itu —
tanpa portal panel melayang di tengah halaman (terukur sebelum perbaikan: tinggi 4.923 px, bukan 568 px).

**Temuan yang diperbaiki (bukan fitur):** `frontend/components/LocationNetworkBoard.module.css` memakai
`border-radius: 4px` mentah sehingga tes `radius-scale-css` gagal → diganti `var(--radius-chip)`.

Gerbang: frontend **200 berkas / 2.289 tes** lulus, tsc 0, `next lint` 0; backend 58 tes penerimaan lulus
(DB klon `mealchain_doc05`), ruff bersih. Verifikasi hidup di `:3010`/`:8000`: batch 800 kg, PO
`MC-B54D0F110D61`, `unit_price_idr` Rp 41.500 → "800 kg × Rp 41.500 per kg dari PO MC-B54D0F110D61",
nilai Rp 33.200.000 berlabel perkiraan, 4 dari 5 titik ditandai, drawer 440 × 568 px, gulir latar terkunci.
Catatan uji (1 penerimaan sementara) dihapus kembali dari DB demo. 0 commit.

## Ronde 43 — 2026-10-28: bentuk modul Location Network dibalik (halaman gabungan, tanpa peta)

Pemilik menilai hasil Ronde 41 aneh: modul berdiri sebagai halaman jaringan sendiri, sementara
isi "pasokan & permintaan" disembunyikan di pop-up. Keputusannya verbatim: *"satu halaman
gabungan berisi kalimat ringkasan + pemilih lokasi + 4 kartu + tabel batch (koridor/peta
dibuang)"*.

1. **Halaman jadi satu kolom.** Urutan: kalimat ringkasan §6.3 → baris angka → pemilih lokasi
   (`button aria-pressed`, urut terparah, otomatis memilih yang paling kekurangan) → rincian
   `SupplyDemandPanel` **inline** → chip kelengkapan §6.5. `Popup` tidak dipakai lagi; state
   `sdTarget` dihapus. Pemilih menggantikan tabel lokasi 6 kolom.
2. **Peta & koridor dibuang seluruhnya**: `SupplyMap` tidak lagi dipakai halaman ini
   (`components/SupplyMap.tsx` dikembalikan ke `HEAD`, jadi 0 sisa kode koridor),
   `useBalanceFlows`, `corridorsFromFlows`/`corridorLegend`, `fetchBalanceFlows`, dan endpoint
   `GET /balance/flows` ikut dihapus karena tidak ada konsumen. Bentuk endpoint tercatat di
   `TODO.md` S4-59 bila nanti dibutuhkan lagi.
3. **Regresi §5 diperbaiki**: `sppg_nutritionist` semula tidak punya jalan masuk ke modul ini.
   Kini ia melihat tab dan judul "Pasokan & Kebutuhan"; peran lain tetap "Location Network".
   Judul halaman ikut peran (`heading`/`description` prop di `LocationNetworkBoard`).
4. **Kartu ke-4 §3 bukan lagi tulisan "belum ada"**: backend ternyata sudah punya
   `GET /demand/forecast` (pekerjaan sesi paralel), jadi kartu menampilkan angka + metode +
   keyakinan (`perkiraan statistik · keyakinan penuh`).

Gerbang: `tsc` 0, `next lint` 0, vitest **201 berkas / 2.300 tes** lulus (tes board ditulis
ulang: 14 tes, termasuk "tidak lagi memasang peta", "pemilih urut terparah", "tidak ada field
mentah"). Browser: SPPG Head 1 lokasi/780 kg/7.420 kg/5 batch; nutritionist judul "Pasokan &
Kebutuhan"; BGN Monitor 10 tombol dua baris, headline 8 lokasi kurang 968 kg sisa 209 kg;
`document.querySelector("canvas") === null`. 0 commit.

## 2026-10-28 — Popup detail: dua tombol tampilan di kepala + persetujuan tanpa jendela kedua

Permintaan pemilik: "buat 2 tombol supaya tidak ada popup dalam popup dan bisa mengganti rincian
dan jejak agen", disesuaikan dengan `01-detail-keputusan.md` dan `02-approval-action.md`.

1. Slot baru `Popup.tsx` → `tabs`: deret tombol dirender di bawah kepala, DI LUAR `.popup-body`
   yang bisa digulir. Popup detail memakai dua tombol pil `.popup-tab`: "Rincian" dan
   "Jejak agen (N)" (aria-pressed). Bar pil lama `.detail-switch` di dalam badan dihapus — inilah
   yang terbaca sebagai "panel di dalam panel". Slot `eyebrow`/`meta` tetap dipakai.
2. `DecisionActions` dapat prop `tampil?: "dialog" | "panel"`. Di popup detail dipakai
   `tampil="panel"`: konfirmasi dirender sebagai `.aksi-panel` di dalam badan popup yang sama,
   bukan `<Popup>` kedua. Isinya tetap `ApprovalMenu` + `GovernanceStatus`, jadi jalur mutasi
   tunggal (dokumen 02 §3) dan isi konfirmasi (requirement, penghalang, label tindakan) tidak
   berubah. Panel digulir ke tampilan (`scrollIntoView`, dijaga bila tidak tersedia) supaya
   pengguna tidak menekan tombol lalu melihat apa-apa.
   Halaman lain TIDAK berubah: tanpa prop, perilakunya tetap dialog.

Bukti DOM (popup "Pengadaan 600 kg telur", Kepala Jakarta): `.popup-tabs` ada dan bukan keturunan
`.popup-body`; tombol `["Rincian", "Jejak agen (2)"]`; `aria-pressed` berpindah; setelah "Kelola
persetujuan": `popup-backdrop`=1, `[role=dialog]`=1, `.aksi-panel` di dalam `.popup-body`,
`.popup-governance`=0. Gerbang: 201 berkas / 2.300 tes, tsc 0, lint 0.

- [2026-10-28] **Overview: penggunaan warna pada pasangan "Kecukupan pasokan" + "Surplus wilayah lain" disamakan (permintaan pemilik: "sesuaikan penggunaan warna").** Masalah: kartu kanan memakai hex kategorikal sendiri (`#2563eb`, `#7c3aed`, `#0891b2`, `#b45309`) dan memetakan warna menurut URUTAN komoditas (`komoditasTone`), jadi (a) telur bisa biru di panel tapi amber di pil peta, (b) satu baris memakai tiga warna sekaligus: rel kiri aksen biru (`--accent-strong`), batang biru pekat, angka kg hijau (`--sa-tone` status). Keputusan: warna DATA mengikuti palet identitas yang sudah didokumentasikan di `docs/design.md` — telur amber, ayam rose, beras biru, wortel violet (token `--cat-*-solid`, sama dengan titik di pil komoditas peta) — dan satu warna membawa satu arti: (1) `lib/surplus-regions.ts` menambah `komoditasKeluarga(nama)` (nama → amber/rose/blue/violet, tanpa peka huruf besar & spasi tepi); `komoditasTone` TETAP ada sebagai cadangan indeks untuk komoditas di luar empat kanonik; (2) `components/SurplusRegionPanel.tsx` memakai kelas `sr-komod-<keluarga>` pada segmen batang, titik legenda, DAN baris wilayah; (3) `app/surplus-regions.css`: kelas `sr-komod-*` hanya menetapkan hue (`--sr-komod`), `.sr-seg`/`.sr-dot`/rel baris memakai variabel itu — batang & titik & rel satu wilayah kini SATU warna; batang memakai warna identitas PENUH sementara batang kartu kiri tetap pucat karena pucat = STATUS, jadi dua bahasa warna tidak tertukar; (4) angka kg baris kembali TINTA NETRAL (aturan `docs/design.md`: "angka hero tetap tinta netral, hanya wash yang berwarna") — sebelumnya hijau warisan `--sa-tone`; (5) `#DBEAFE`/`--accent-soft` untuk kotak hero dan lencana diganti token `--cat-blue-line`/`--cat-blue-bg`/`--cat-blue-ink`; rel aksen biru pada baris teratas DIHAPUS (aturan `.sr-row-teratas` dibuang, bukan CSS mati) karena penanda "terbesar" sudah ada sebagai lencana. Terukur di DOM hidup (BGN Monitor, viewport 1262 px): rel `rgb(146,64,14)` = batang `rgb(146,64,14)` = titik legenda `rgb(146,64,14)`; angka kg `rgb(15,23,42)` (tinta); lencana & hero `#EFF6FF` + `#BFDBFE`; batang kartu kiri tidak berubah (`color-mix(--status-*)`); tinggi dua kartu tetap 372 px = 372 px. Gerbang: vitest 201 berkas / 2.300 tes lulus (termasuk 3 uji baru `komoditasKelas` di `tests/surplus-regions.test.ts` dan gate token `design-tokens-kontrak`, `token-warna-komponen`, `token-alias-css`, `token-bayangan`, `radius-scale-css`), `next lint` 0. Catatan: uji lama `warna komoditas tidak memakai token status` sempat merah karena aturan `.sr-row-teratas` menaruh `--status-safe` setelah blok `.sr-komod-0`; aturan itu dihapus sehingga uji kembali hijau tanpa melonggarkan tes. Batas jujur: bar telur sekarang berwarna amber-tua (identitas komoditas), bukan hijau "surplus" — makna surplus dibawa label/angka/lencana, bukan warna. Kalau pemilik ingin batang memakai warna status hijau, itu perubahan satu baris di `.sr-seg` tetapi akan bertabrakan dengan makna identitas komoditas.


## 2026-10-28 (revisi) — Dua tombol pindah ke KARTU feed, popup tidak lagi punya tab

Pemilik menolak tab di dalam popup: "halaman popup dan rincian dibedakan… 2 tombol berada di sini
`<span class="rec-hint">Klik untuk rincian & jejak agen</span>`". Jadi:

- `RecommendationCard` punya prop `onBuka?: (tampilan, pemicu) => void`. Bila diisi, ajakan teks
  `rec-hint` DIGANTI dua tombol `.rec-act-btn`: "Rincian" dan "Jejak agen" (aria-label menyebut tipe
  keputusan, tidak `aria-hidden`). Tanpa prop, perilaku lama (hint teks) tetap — dipakai kartu
  "Usulan" di dalam popup dan halaman Decision & Evidence.
- Pembungkus kartu di feed berubah dari `<button class="link-button">` menjadi `<div class="rec-baris">`:
  tombol tidak boleh bersarang di dalam tombol. Klik seluruh kartu karena itu tidak lagi membuka popup —
  masukannya hanya lewat dua tombol.
- `bukaPopupKeputusan(decisionId, pemicu, tampilan)` menyimpan pilihan ke `popupTampilan`; `DecisionDrawer`
  menerima `tampilanAwal` dan me-reset tampilan pada `[decisionId, open, tampilanAwal]`. Tab `.popup-tab`
  dan slot `tabs` di `Popup.tsx` DIHAPUS — jangan dihidupkan lagi tanpa alasan.
- `onBuka` meneruskan elemen tombol sebagai `pemicu` supaya fokus balik ke tombol yang ditekan saat
  popup ditutup (diuji di layar: `document.activeElement` = `.rec-act-btn`).

Bukti DOM: 10 kartu, tinggi 76 → 82 px, tiap kartu `["Rincian [Rincian: …]", "Jejak agen [Jejak agen: …]"]`,
teks "Klik untuk rincian" hilang; klik "Jejak agen" → popup langsung `.agent-console` (tanpa `.detail-layer`,
`.popup-tab` = 0); klik "Rincian" → tampilan rincian. Gerbang: 203 berkas / 2.341 tes, tsc 0, lint 0.

### Tambahan Ronde 42 — bentuk dialog: popup tengah, bukan drawer kanan

Pemilik bertanya "bukannya pop up yaa??" setelah drawer kanan 440 px dipasang. Tiga subagent read-only
menilai tiga opsi; hasilnya: popup tengah `Popup.tsx` **direkomendasikan**, drawer kanan "dapat diterima
tapi cacat", satu-tombol-tanpa-daftar **ditolak** (menghapus pembanding kg/nilai antar batch dan memaksa
pemilih batch baru).

Bukti yang menentukan: `decisions.md:520-522` sudah mencatat pemilik **menolak** drawer kanan 520 px untuk
permukaan bersaudara dan meminta popup tetap di tengah; `decisions.md:564-565` mewajibkan `Popup.tsx`
sebagai satu-satunya cangkang dialog. Klausa dok 05 §1 "drawer kanan, sama seperti drawer keputusan" sudah
tidak punya rujukan di repo ini (DecisionDrawer.tsx memakai `Popup` terpusat), jadi paritas yang diminta
dokumen kini berarti popup tengah. Bentuknya menyimpang dari bunyi §1 — dicatat di sini supaya tidak dibaca
sebagai kelalaian; yang mengikat dari §2 (tiga langkah berurutan) tetap utuh di `GoodsReceiptSheet`.

Cacat cangkang buatan sendiri yang TERUKUR hidup lalu hilang setelah pindah ke `Popup`:
(a) Tab keluar ke "Tutup sidebar" di halaman belakang meski `aria-modal="true"`; (b) Escape saat panel
TERTUTUP memindahkan fokus ke tombol "Buka penerimaan" (effect keydown tanpa dependensi + `tutupPanel`
selalu memfokuskan pemicu); (c) tombol Tutup hilang saat isi digulir (seluruh panel yang menggulir, bukan
hanya isi); (d) latar ditutup `onClick` (seleksi teks yang berakhir di latar membuang isian alasan tolak);
(e) `z-index: 60` di bawah `.popup-backdrop` 80.

Sesudah: `role=dialog`, `aria-labelledby="popup-penerimaan-judul"`, fokus awal di dalam popup, Tab berputar
dari "Tolak penerimaan" ke "Tutup jendela", Escape menutup + fokus kembali ke `receipt-open-drawer` +
`body.overflow` dipulihkan, Escape saat tertutup tidak menyentuh fokus. Popup 720 × 500 px (dari 640 px
bawaan lewat modifier `.popup-penerimaan`), tanpa luapan horizontal, tombol 44 px pada pointer kasar, dan
media query 460 px menumpuk strip tiga angka jadi satu kolom.

Gerbang: frontend **203 berkas / 2.341 tes** lulus, tsc 0 error, `next lint` 0. Backend tidak disentuh ronde
ini (58 tes penerimaan lulus sebelumnya). Catatan: saat ronde ini berjalan ada penulis lain di tree yang
sama (`LocationNetworkBoard.tsx` + tes `agent-activity`/`location-network-board`) sehingga tsc sempat merah
di berkas itu; sudah hijau lagi dan bukan bagian pekerjaan ini. 0 commit.

- [2026-10-28] **Location Network = satu halaman gabungan tanpa peta, rincian lokasi lewat pop-up; koridor dan `GET /balance/flows` dibatalkan.** Keputusan pemilik, dan bentuk inilah yang berlaku sekarang. (a) Tab `location-network` (`frontend/app/page.tsx`) satu kolom: kalimat ringkasan jaringan → baris statistik (kekurangan / kelebihan / seimbang / tanpa koordinat) → pemilih lokasi `aria-pressed` urut keparahan → satu pintu masuk rincian → panel Kelengkapan data (`frontend/components/LocationNetworkBoard.tsx`). (b) Rincian satu lokasi dibuka sebagai pop-up `frontend/components/Popup.tsx` (`sdTarget` + `returnFocusRef` di `app/page.tsx`, isi `frontend/components/SupplyDemandPanel.tsx`, empat kartu), BUKAN dirender inline — klaim "pop-up dihapus" di S4-60 dan di halaman verifikasi lama tidak berlaku. (c) Peta `SupplyMap` tidak lagi dirender di modul ini (tetap dipakai Overview); layer koridor `network-corridors` beserta `useBalanceFlows`, `corridorsFromFlows`, `corridorLegend`, `corridorStatusLabel`, dan **endpoint `GET /balance/flows`** dihapus dari `backend/app/api/balance.py` — sekarang 404 dan 0 rujukan tersisa di `backend/` + `frontend/`. Alasan: agregat baris `decisions` tidak bisa menjamin lane surplus→kekurangan dan endpoint itu tidak punya cakupan peran, sehingga garis di peta akan terbaca sebagai bukti aliran barang padahal bukan; halaman jaringan berdiri sendiri juga tidak memberi `sppg_nutritionist` jalan masuk. (d) Kartu keempat "Perkiraan 7 hari" WAJIB memakai `GET /demand/forecast/{lokasi}/{komoditas}?horizon_days=7` (metode `statistical_fallback`, keyakinan `min(1, jumlah catatan / 3)`) dan WAJIB menulis "dasar tipis" bila keyakinan < 1, karena tanpa label itu angka perkiraan terbaca sebagai kepastian. (e) Penyimpangan sadar yang diterima: `GET /balance/map` tetap mengirim `0.0` untuk sisi yang tidak punya catatan, ditambah penanda `supply_state`/`demand_state` = `tidak_ada_baris`, bukan `null`; mengubahnya ke `null` akan menyentuh Overview dan grafik kecukupan, jadi klien wajib membaca penanda itu. Gerbang ronde ini: `tsc --noEmit` 0 galat, vitest 203 berkas / 2.341 tes lulus; tangkapan Jakarta·telur pasokan 299,09 kg, kebutuhan 1.087,22 kg, selisih kurang 780 kg, perkiraan 7 hari 7.550,26 kg.

## Ronde 43 — 2026-10-29: realisasi PO (nilai PO vs nilai barang masuk)

**Keputusan.** Dokumen 05 §9 butir 3 ("belum ada tampilan perbandingan antara
nilai PO dan nilai diterima dalam satu baris") dikerjakan pada daftar Purchase
Order yang sudah ada, **tanpa migrasi dan tanpa endpoint baru**: `GET
/sap/purchase-orders` diperluas dan `PurchaseOrderList` menampilkan dua angka
berlabel plus selisih bertanda.

**Alasan memilih ini, bukan §8.5 atau popup penerimaan.** Diukur dari DB demo:
`batch_receipts` hanya 2 baris dan 0 di antaranya menunjuk batch yang punya
ikatan PO, sehingga kolom nilai di jalur penerimaan akan berbunyi "tidak
tercatat" di semua baris. Sisi realisasi PO punya angka nyata (4 dari 6 PO
berkeputusan) dan tempatnya sudah ada. Dua dari tiga butir §8.5 ternyata SUDAH
selesai di repo ini (urut `recorded_at` di `api/receipts.py`, warna putusan di
`lib/food-safety.ts`), jadi §8.5 bukan celah terbuka — hanya kehilangan kolom
nilai yang, seperti di atas, kosong hari ini.

**Cara menghitung (server, satu kueri).** `services/po_realization.py` membaca
ikatan PO→batch dari jalur yang SAMA dengan nilai penerimaan
(`decision_evidence` bertipe `human_inspection` → `payload->'batch_ids'`),
dengan `SELECT DISTINCT` supaya batch yang muncul di beberapa bukti tidak
dihitung dua kali. `received_value_idr = harga_satuan × kg_terikat`;
`variance_idr = received − total PO`.

**Aturan yang dijaga.** `None` ≠ `0`: PO tanpa ikatan bukti mengirim
`received_kg/received_value_idr/variance_*` = `null` dan panel menulis "belum
ada barang tercatat". `0` hanya sah bila memang ada batch 0 kg. Selisih diberi
tanda arah (`+`/`−`) dan kata, bukan hanya warna.

**Gate.** `backend/tests/test_sap_orders_api.py`: `FIELDS` diperluas (asersi
`set(row) == FIELDS` DIPERTAHANKAN) + 2 tes baru yang membandingkan hasil API
dengan kueri ground truth di DB; 15 lulus. `frontend/tests/purchase-orders.test.tsx`
+3 tes (dua angka berdampingan, selisih bertanda, null ≠ Rp 0): 20 lulus.
`tsc` 0, `next lint` 0.

**Belum dikerjakan.** Dok 05 §8.4 (bukti foto) menuntut kolom baru — migrasi
`044` + kolom `photos` jsonb, base64 di body JSON, 1 foto ≤300 KB terikat
`check_id`, tanpa dependensi/endpoint baru. Bentuk itu sudah dinilai dan
direkomendasikan, tetapi keputusan skema tetap milik pemilik repo.

## 2026-10-28 (final) — Kartu feed: "Rincian" + "Persetujuan"; jejak agen pindah ke kepala popup

Keputusan pemilik: dua tombol di kartu adalah **Rincian** (baca) dan **Persetujuan** (tindakan),
bukan Rincian + Jejak agen.

- `RecommendationCard`: prop `onBuka(tampilan: "rincian" | "persetujuan", pemicu)` dan
  `tampilPersetujuan` (dari `visibleActions(role, status)` di `page.tsx` — `!readOnly && approve`;
  jangan menduplikasi daftar peran). Tombol kedua berkelas `.rec-act-btn--utama`. Untuk peran pengawas
  dan keputusan yang sudah disetujui/ditolak tombolnya ABSEN (dok 02 §7.5), bukan tombol mati.
- `DecisionDrawer`: `tampilanAwal: "rincian" | "persetujuan"`. Pilihan "persetujuan" meneruskan
  `terbukaAwal` ke `DecisionActions` dan menggulir `.detail-aksi` ke tampilan.
- Jejak agen bukan lagi tombol kartu: tautan tenang `.detail-tautan` di kepala popup
  ("Jejak agen (N)" ↔ "Kembali ke rincian"), satu elemen supaya fokus keyboard tidak hilang.
- **Jebakan yang sudah diperbaiki** (temuan audit eksternal): `DecisionActions` dulu hanya memakai
  `useState(terbukaAwal)`, jadi sesudah popup ditutup dan dibuka ulang dengan pilihan lain, panel
  bisa tertutup padahal diminta atau terbuka padahal cuma membaca. Sekarang ada efek sinkron
  `[terbukaAwal, decisionId]`. Tes regresinya memakai root yang SAMA (`renderUlang()`);
  tes "mount segar" tidak bisa menangkap kelas bug ini.
- `ApprovalMenu` dapat prop `dalamPanel`: saat dirender di dalam popup, kalimat
  "Tekan Esc untuk menutup jendela ini" diganti "Tutup panel ini untuk kembali membaca rincian."
  (Escape menutup seluruh popup keputusan, bukan panel).
- Sesuai dok 01 §4, keputusan administratif TIDAK merender bagian biaya maupun PO sama sekali
  (sebelumnya dirender lalu diberi penjelasan). Seksi PO kini juga mencetak "Status PO" dalam
  bahasa Indonesia ("Terkirim ke SAP"), bukan status mentah.

Bukti DOM (keputusan "Ganti pasokan 780 kg telur", Kepala Jakarta): kartu `["Rincian", "Persetujuan"]`;
tombol Persetujuan → `.aksi-panel` terbuka (panelTop 125), 1 `.popup-backdrop`, 1 `[role=dialog]`,
tanpa teks "Tekan Esc"; buka ulang via Rincian → panel 0; buka ulang via Persetujuan → panel 1 lagi.
Kartu "Disetujui" hanya menampilkan Rincian. Gerbang: 203 berkas / 2.363 tes, tsc 0, lint 0,
5 gate token hijau (27 tes).

## Ronde 44 — 2026-10-28: bentuk halaman Location Network diputuskan lewat audit + verifikasi, bukan selera

Dua subagent (read-only) dijalankan: audit UI/UX yang menimbang tiga bentuk, dan verifikasi
fullstack yang menelusuri tiap angka sampai endpoint. Keputusannya: **satu kartu ringkasan →
tabel lokasi → baris terbuka berisi rincian**, tanpa peta, tanpa chip, tanpa popup.

1. Alasan pilihan, terukur: popup 640 px memaksa 4 kartu jadi 3+1 dan menyembunyikan tabel
   batch di bawah tepi panel (y=491 vs y=488); `aria-pressed` pada chip bertahan `true`
   setelah jendela ditutup. Tabel yang membuka rincian di tempat menghapus ketiganya tanpa
   CSS baru, dan memakai bahasa tabel yang sudah ada (`location-table`).
2. `TONE_CLASS` (kelas global pada elemen ber-CSS-module) tidak pernah cocok karena kelas
   di-hash → penekanan bahaya diganti `data-tone` + selektor atribut. Ini cacat yang tidak
   pernah tertangkap tes.
3. Invarian baru di layar: jumlah 0 tidak mencetak kg; data belum masuk tidak dibunyikan
   sebagai "tidak ada kekurangan"; saat galat tidak ada kesimpulan sama sekali.
4. Batch ber-`quarantine_status=quarantined` kini bertanda "Ditahan" dan tidak dihitung
   "lolos uji" — server sudah mengirim field itu, klien dulu membuangnya.
5. Pemilihan otomatis lokasi terparah dibatasi sekali per kunjungan (`autoPilihRef`); tanpa
   itu baris tidak bisa ditutup karena efek langsung memilih ulang.
6. **Bentrok sesi dicatat terbuka**: sesi lain menulis berkas yang sama dengan bentuk "popup"
   (S4-61) sementara kode berjalan memakai tabel + rincian sebaris (S4-62). Pemilik harus
   memilih satu; jangan menambah bentuk ketiga.

Batas yang tetap terbuka: `/supply`, `/demand`, `/demand/forecast` belum menerima `as_of`
sehingga panel bisa menampilkan dua snapshot (300/1.080 vs 299,09/1.087,22; selisih 780 vs
788,13). Gerbang: `tsc` 0, `next lint` 0, vitest 2.362 lulus (1 kegagalan di
`decision-drawer.test.tsx` milik sesi lain), `npm run build` `GP2D05hcnICD2cJ5206ct`. 0 commit.

## 2026-10-29 — Redesign dua popup halaman Recommendations (Rincian & Persetujuan)

Permintaan pemilik: "redesign lagi untuk setiap pop up pada halaman rekomendasi, design
tampilan dan susunan isinya".

Tiga popup, tiga susunan (kepala popup sama supaya tidak terasa pindah aplikasi):

| Popup | Lebar / kolom | Urutan isi |
|---|---|---|
| Rincian (baca) | 920 px, 2 kolom | alur → pita 3 angka → fakta dasar / biaya+PO → verifier → kewajiban (lipat) → aksi → usulan → jejak iterasi → pemasok → bukti |
| Persetujuan (putus) | 760 px, 1 kolom | pita 3 angka → **Putuskan sekarang** (panel terbuka) → kewajiban (terbuka) → verifier → konteks angka (lipat) → bukti |
| Jejak agen | 920 px | kepala berisi jumlah langkah + waktu UTC → konsol jejak |

- Pita angka `.detail-kpi` (3 sel): Jumlah, Harga terkirim/kg, selisih vs harga acuan
  beserta persennya. Semua angka turunan `lib/detail-keputusan.ts`, bukan hitungan baru.
- CTA di popup Persetujuan ditaruh di atas kewajiban: tombol tidak boleh di bawah gulungan.
  Daftar penyetuju tetap terbuka karena justru itu isi "siapa yang dibutuhkan" (dok 02 §7.1).
- Gulir: popup selalu dibuka dari atas. `DecisionActions` hanya menggulir bila KEPALA panel
  di luar layar (`top < 0 || top > viewport - 120`) — patokan dasar panel membuat panel
  setinggi layar selalu "digulir", dan pita angka ikut hilang.
- Tombol pemicu "Kelola persetujuan…" disembunyikan saat panel terbuka (panel sudah punya
  "Tutup panel"); fokus kembali ke pemicu saat panel ditutup.
- `.aksi-panel .approval-menu-foot { position: static }`: kaki sticky dirancang untuk modal
  setinggi layar; di panel inline ia melayang menutupi ringkasan bukti.
- Copy: `ApprovalModal`/`ApprovalMenu` tidak lagi mencetak enum mentah — pakai `statusLabel`,
  `roleList` dari `lib/bahasa.ts`; "unavailable" → "belum tercatat"; slug jenis keputusan
  dibuang dari baris Alokasi; contoh `<code>executed</code>` → `<code>dieksekusi</code>`.

Bukti DOM (Kepala Jakarta, "Ganti pasokan 780 kg telur"):
- Rincian: 920 px, kolom "426.5px 426.5px", urutan 11 blok, KPI `780 kg` / `Rp29.186/kg` / `−Rp1.947/kg · 6,3%`.
- Persetujuan: 760 px, kolom 711 px, urutan `KPI → Putuskan sekarang → Kewajiban → Verifier → Konteks angka → Bukti`,
  `.aksi-panel` terbuka, gulir badan 0, tidak ada "pending_approval/unavailable/expired" di teks popup.
- Gerbang: 203 berkas / 2.364 tes, tsc 0, lint 0, 5 gate token hijau.

## Ronde 45 — 2026-10-28: halaman Location Network dirapikan, satu fakta satu tempat

1. Informasi berulang dihapus: baris angka di bawah kalimat ringkasan, pil "N lokasi",
   pil "Sinkron" (jam pengambilan, bukan tanggal data), kotak kelengkapan yang selalu
   tampil, kolom "Catatan" berisi "lengkap", caption tabel, dan suku rekap batch yang nol.
2. Kelengkapan data kini **hanya muncul bila ada isu**; kolom tanda hanya dipasang bila ada
   baris bertanda. Prinsipnya: elemen yang selalu berbunyi sama sekali tidak memberi informasi.
3. Panel rincian tidak boleh berada di dalam `<td>` — tabel bersarang merusak lebar kolom
   tabel luar (terukur). Daftar disclosure dipakai sebagai gantinya.
4. Komoditas bisa diganti dari halaman ini (chips `aria-pressed`), menutup temuan bahwa pil
   statis menyerupai kontrol.

Gerbang: `tsc` 0, `next lint` 0, vitest 203/2.367, build `cidkYdagb5FLBY_2ljV0n`. 0 commit.

## 2026-10-29 (lanj.) — "Ringkasan bukti" di panel persetujuan dirapikan

Keluhan pemilik: blok Ringkasan bukti / Konfirmasi Approval "kurang rapih".

Penyebab sebenarnya bukan isi, tapi dua hal:
1. `.approval-facts` hanya diberi gaya di dalam `.popup-governance`; begitu dipakai di
   panel inline, daftar 12 baris itu jatuh ke gaya bawaan peramban.
2. Nilai mentah ikut tercetak: uuid panjang, `consistent (server-side)`, kode peran
   `sppg_head + sppg_nutritionist`, `MOCK`, `7071 detik`, "approval belum memenuhi
   requirement (missing/rejected)".

Bentuk baru — empat bagian tetap, dua kolom label-nilai (`.approval-grid`):
  1. Isi keputusan  : Alokasi, Komoditas, Pemasok (+ kode material), Total biaya
  2. Pemeriksaan    : Status, Keamanan batch sumber, Hasil verifier, Masa berlaku
  3. Persetujuan    : Dibutuhkan, Peran, Sudah tercatat
  4. Setelah disetujui : Jalur (simulasi vs administratif)
  + blok "Tertahan" (alasan kalimat) dan tombol aksi.

Aturan copy yang dipakai: id 8 aksara (`#bef077a8 · versi 1`), `consistent` → "Konsisten",
`unavailable` → "Belum tersedia", kode peran → nama manusia (`Kepala SPPG + Ahli Gizi SPPG`),
`MOCK` → "Simulasi - PO simulasi, bukan PO SAP sungguhan", detik → "Masih 1 jam 37 menit lagi",
"approval belum memenuhi requirement (missing/rejected)" → "Persetujuan belum lengkap - masih
ada peran yang belum menyetujui." Peran hanya diulang di baris "Sudah tercatat" bila sebagian
sudah menyetujui (kalau masih nol, baris "Peran" sudah menyebut semuanya).

Chip status di kepala panel dihapus: ringkasan di bawahnya sudah mencetak status, syarat, dan
peran yang kurang — tiga kalimat sama dalam satu layar terbaca sebagai berisik.

Bukti DOM: kartu 655 × 754 px, kolom `307px 307px`, empat bagian, `.aksi-panel` tanpa chip.
Gerbang: tsc 0, lint 0, vitest 205/2419 (1 sisa kegagalan di `prd-nav` milik penulis lain).
Catatan: `next dev` sempat menggantung (port 3010 menerima koneksi tapi tak menjawab); proses
lama dimatikan lalu dijalankan ulang, siap dalam 5,6 dtk.

**Tambahan Ronde 43 (29 Okt, 01:10) — pemasangan UI ditunda karena refactor paralel.**
Saat ronde ini selesai, ada alur kerja LAIN di checkout yang sama yang menulis
ulang halaman Decision & Evidence (`components/DecisionDetail.tsx`,
`components/DecisionPurchaseOrder.tsx`, `lib/decision-dossier.ts` — semuanya
untracked, berubah 00:42–01:00). Refactor itu mencabut `<PurchaseOrderList>` dari
halaman keputusan (diganti satu PO per keputusan), sehingga kolom
"Nilai PO | Diterima | selisih" BELUM tampil di UI walau API dan tesnya benar.
Pemilik repo memilih MENUNGGU refactor itu selesai, lalu memasang angkanya di
komponen baru. Yang harus disambungkan nanti: `received_kg`,
`received_value_idr`, `variance_idr`, `variance_pct`, `received_batch_count`,
`received_basis` (sudah dikirim `GET /sap/purchase-orders`), dengan aturan
`null` != 0 dan bantuan `varianceNada()` / `varianceLabel()` di
`components/PurchaseOrderList.tsx` yang bisa dipindahkan apa adanya.

## Ronde 46 — 2026-10-29: Location Network memakai bahasa desain konsol, bukan CSS sendiri

1. Halaman ini tidak boleh punya sistem visual sendiri. Primitive wajib: `board-page`,
   `PageHeader` (+`page-header-pills`), kartu `card` + `board-card-head`, tabel
   `location-table` di `board-table-wrap`, `commodity-filters`/`commodity-pill`,
   `button`, `evidence-note`. CSS modul hanya untuk hal yang belum ada padanannya.
2. Rincian lokasi tidak boleh berada di dalam `<td>`: panel berisi tabel batch membuat
   tabel bersarang dan merusak lebar kolom tabel luar. Rincian = kartu sendiri di bawah
   tabel, baris memakai `aria-pressed` + penanda ▸/▾.
3. Satu batch satu badge: "Ditahan" mengalahkan "Aman". Satu sel satu keterangan:
   angka masa layak mengalahkan ember "≤ 7 hari". Rekap batch tidak menghitung ulang
   apa yang sudah tampak di badge.
4. Keterangan proses ("dihitung server…"), asal data ("catatan simulasi"), dan ambang
   metode ("≥ 3 catatan permintaan") bukan informasi layar operator — dihapus.

Gerbang: `tsc` 0, `next lint` 0, vitest 205 berkas/2.417 tes (1 gagal `prd-nav.test.tsx`,
milik sesi lain), build `WDpMMCWmdO-Z04vCJsV-2`. 0 commit.


## Ronde 47 — 2026-10-29: Keamanan Pangan — §4.2 `07-safety-evidence.md` dikerjakan di permukaan yang sudah ada

Dokumen acuan ditulis untuk repo lain (modul “Safety & Evidence”). Di repo ini
permukaannya tab “Keamanan Pangan” (`FoodSafetyBoard` + `lib/food-safety.ts`) dan tab
“Decision & Evidence” (`DecisionEvidence`/`DecisionDetail`/`IntegrityPanel`). Yang dipakai
adalah MAKSUD tiap butir, bukan nama berkasnya. Audit enam butir lebih dulu, baru menyunting.

1. Butir 1 (postur ↔ gerbang) dikerjakan sebagai saringan komoditas, bukan tabel baru:
   `safetyDecisions(items, commodity?)` menyaring keputusan `safety_disruption` menurut
   `commodity_name` yang SUDAH dikirim `GET /decisions`. Sel komoditas di tabel status menjadi
   tautan hanya bila komoditas itu benar-benar punya keputusan; komoditas lain tetap teks.
   `allTotal` tetap menyebut seluruh feed, dan kalimat ringkasan dibuka “Disaring ke komoditas X”
   supaya angka kecil tidak terbaca sebagai riwayat yang hilang.
2. Butir 2 (jumlah batch di lencana) tidak boleh mengarang: `_safety_view` di
   `approval_summary.py` mengirim `batches_checked: 0` juga saat status tidak terdefinisi, jadi
   `safetyBadge()` hanya mencetak “N batch diperiksa” bila N > 0. Angka yang sudah naik ke
   lencana TIDAK dicetak lagi sebagai baris fakta (`safetyFacts(summary, { countInBadge: true })`).
3. Butir 3 tidak boleh mengurangi informasi: tabel status sudah menampilkan kesegaran tiap baris
   tanpa lipatan, jadi lipatan baru tidak dipakai untuk menggantikannya. Yang ditambahkan adalah
   kartu “Kesegaran terendah” (tiga skor terendah terbuka, sisanya di satu lipatan) plus dua
   catatan yang memang belum ada: skor kosong bukan 0, dan rekap hanya dari baris yang termuat
   (server mengirim maksimum 500 baris terbaru).
4. Butir 4 (penanda mendekati kedaluwarsa) SUDAH ADA (`expiryState` + `URGENT_HOURS`/`WATCH_HOURS`,
   kolom “Sisa masa”, kartu “Batch perlu segera dipakai”) — tidak dibungkus ulang.
5. Butir 5 dijawab satu baris di bawah bilah saring tabel: saringan itu hanya menyentuh daftar
   batch, sedangkan daftar keputusan punya saringan komoditas sendiri. Di tab Decision & Evidence
   tidak berlaku (pemilih keputusan dan sakelar “lewat tenggat” menyaring kumpulan yang sama).
6. Butir 6 memakai pola ekspor yang sudah ada: `tableToCsv` (diekstrak dari `dossierToCsv`, aturan
   formula-injection ikut) + `downloadText`. Isi berkas = baris yang SEDANG tampil setelah saringan.
   Satu penyimpangan yang disengaja: kolom `lokasi` memakai nama lengkap, bukan kode wilayah tabel,
   karena singkatan justru menghilangkan informasi di berkas audit.

Tidak dikerjakan dan disebut di laporan: ekspor PDF dan persistensi pilihan saringan antar-sesi
(keduanya butuh keputusan produk, bukan kekurangan data). Tidak ada tombol tulis baru, tidak ada
persentase gabungan, tidak ada status PASS/FAIL yang diubah.

Gerbang: `tsc --noEmit` exit 0, `npm run lint` exit 0, vitest **212 berkas / 2.473 tes lulus,
0 gagal**. (Run tengah sempat 1 gagal di `tests/agenda.test.ts` karena `lib/agenda.ts` sedang
disunting sesi lain — berkas itu tidak disentuh di sini; hijau setelah suntingan itu selesai.)
34 tes baru ditulis MERAH lebih dulu lalu hijau. 0 commit.

## Ronde 47 — 2026-10-29: kalimat di "Jejak kepercayaan" harus bisa dicocokkan, bukan hanya pendek

1. Kalimat penjelas satu sel memakai satu bentuk: `N <kategori>` dipisah " · ", tanpa
   kata ganti yang menggantung ("masih", "luar", "…tidak ada yang…").
2. Kategori hitungan WAJIB saling meniadakan. Batch: ditahan > gagal > belum diuji >
   lolos > tanpa status, sehingga jumlahnya selalu sama dengan `/total`. Keputusan:
   dieksekusi + menunggu + ditolak + sudah selesai = total.
3. Status yang tidak masuk kategori mana pun tetap disebut ("N tanpa status"), tidak
   dibiarkan hilang — penjelasan yang tidak bisa dijumlahkan membuat angka tampak salah.
4. Label sel tidak boleh lebih kecil dari kalimat penjelasnya (12 → 13px), dan
   `.trust-foot` 13px/1,5 dengan `text-wrap: pretty`.

Gerbang: `tsc` 0, `next lint` 0, vitest 212 berkas/2.476 tes, build `nAmr-_z0zd1Mzz1CGFOEH`. 0 commit.

## Ronde 48 — 2026-10-29: ukuran huruf penjelas "Jejak kepercayaan" = 12px

Pemilik meminta kalimat penjelas dikecilkan ("bisa diperkecil mungkin fontnya") setelah
sempat dinaikkan ke 13px. Aturan: `.trust-foot` 12px / line-height 1,4 / jarak 3px /
`tabular-nums` / `text-wrap: pretty`, label sel 13px supaya hierarki tetap benar
(label > penjelas bukan sebaliknya). Bukti di browser 947px: kartu 166px, empat sel 55px
sama tinggi, keempat kalimat satu baris (tinggi 17px, tidak membungkus).

Gerbang: `next lint` 0, vitest 25 tes terkait lulus, build `5HQf9LYaawBv5pstd_qPk`. 0 commit.

## Ronde 49 — 2026-10-29: Location Network jadi satu halaman lima blok

1. Satu tab = satu kepala + satu filter komoditas. `SurplusBoard` tidak dirender utuh lagi;
   isinya menjadi blok 4 (Rencana alih, `AllocationTable`) dan 5 (Limbah) di dalam board.
2. Rencana alih wajib dari `GET /surplus/allocations` (server), bukan hitungan klien: peta
   peran SPPG hanya memuat satu lokasi sehingga hitungan klien selalu kosong.
3. Rencana alih & limbah tampil untuk SEMUA peran (keputusan pemilik 29 Okt 2026); gerbang
   `SURPLUS_ROLES` dicabut.
4. Hook `useWasteSummary`/`useSurplusPlan` dulu bergantung pada `tab === "surplus"` yang sudah
   tidak ada → blok selalu kosong. Kini juga hidup untuk `tab === "location-network"`.
5. Panah aliran surplus→kekurangan TIDAK dipakai: mengulang angka kalimat ringkasan.

Gerbang: tsc 0, lint 0, vitest 213/2489, build `ritoIHqRhgMCfG_oksSgY`. 0 commit.

## Ronde 50 — 2026-10-29: dua kolom penting di tabel Location Network

1. "Batch ≤7h" hanya menghitung stok yang BOLEH dipakai: `safety_status=pass` dan tidak
   ditahan; tanggal tak terbaca tidak dihitung; yang sudah lewat masa layak tetap dihitung.
2. "Rekomendasi" = keputusan berstatus terbuka per `target_location_name`; baris tanpa nama
   dilewati supaya tidak muncul kunci "undefined".
3. Kolom dipasang hanya bila ada nilai > 0 di salah satu baris (arahan pemilik); sel kosong
   menulis "—", bukan 0.

Gerbang: tsc 0, lint 0, vitest 214/2502, build `ubpvBA7URr_Dy82BlkAZE`. 0 commit.

## Ronde 51 — 2026-10-29: copy & keadaan halaman Location Network (Langkah 3 rencana)

1. Kalimat kepala halaman punya SATU sumber teks: bawaan `LocationNetworkBoard` ("Siapa
   kekurangan, siapa kelebihan, apa yang dialihkan, dan apa yang terbuang"); `app/page.tsx`
   hanya mengirim kalimat untuk peran nutritionist. Dua salinan sebelumnya sempat berbeda.
2. Istilah di kepala & judul menu disamakan dengan kartu ringkasan ("kelebihan", bukan
   "berlebih"); frasa "isi catatan tiap lokasi"/"dari mana catatannya" dibuang karena isi
   itu tidak lagi ada di halaman.
3. Angka hanya dicetak bila benar-benar terbaca: pil "N lokasi" disembunyikan selama memuat
   dan saat galat ("0 lokasi" terbaca sebagai hasil pengukuran, bukan sebagai "belum tahu").
4. Keadaan kosong diucapkan SEKALI (kartu "Keadaan jaringan"); kartu tabel tidak dirender.
   Memuat memakai tiga baris kerangka `skeleton skeleton-line`, bukan teks "Memuat…".
5. Satu lokasi dalam cakupan diberi baris kaki "Akun ini hanya mencakup satu lokasi." —
   bukan paragraf penjelas di kepala.
6. Penjelasan proses tidak masuk baris baca: rumus biaya rencana alih pindah ke `title`
   judul kolom; kaki tabel tinggal ambang surplus.
7. Layar sempit 390 px DIUKUR dengan CDP (`_qa/ukur-viewport.cjs`), bukan disimpulkan dari CSS.
   Dua cacat ikut diperbaiki: `<th>` "Wilayah" harus hilang bersama selnya (dulu seluruh angka
   bergeser satu kolom), dan setiap tabel yang bergulir sendiri wajib punya `ScrollHint`
   (`kelasWadah` baru supaya panel bisa memakai pengukur yang sama).
8. Sisa yang disengaja: pada 390 px tabel lokasi masih digeser di dalam kartunya (389 vs 316 px)
   — dinyatakan lewat petunjuk, bukan disembunyikan.

Gerbang: tsc 0, lint 0, vitest 217/2528, build `YZRmCQjqXtfsWB-9rnFUA`. 0 commit.

## Ronde 52 — 2026-10-29: Decision & Evidence — bukti pemasok & pesan batch ditahan

Ditemukan saat menelusuri alur nyata (approve → eksekusi → review PO) di :3010,
bukan dari membaca kode.

1. **Modul fetch frontend WAJIB memakai basis relatif.** `lib/supplier-exclusions.ts`
   memakai `NEXT_PUBLIC_API_URL || "http://localhost:8000"`. Variabel itu ada tetapi
   KOSONG di stack lokal, jadi `||` memilih URL absolut; CSP `connect-src 'self'`
   menolaknya dan request tidak pernah sampai ke backend (log bersih, `dikirim`
   tidak ada). `lib/api.ts` memakai `??` sehingga path relatif lewat rewrites Next.
   Fix `?? ""`. Konsekuensi yang dulu tidak terlihat: `supplierContext = null` membuat
   `DecisionDetail` MELEWATI panel Supplier governance sepenuhnya — panelnya tidak
   "kosong", panelnya tidak ada.
2. **Endpoint yang mengembalikan alasan wajib punya pembaca.** `review PO`
   (`POST /actions/purchase-orders/{po}/approve`) mengirim `dikirim` + `ditahan`;
   `DecisionActions.reviewPo` hanya membaca status. Keputusan bisa `executed` dengan
   PO `submitted` sementara batch terikat DITAHAN dan tidak ada truk bergerak
   (terukur: bef077a8, batch b772248c "sudah berangkat", `max(dispatched_at)` tetap).
   Ditambal dengan helper murni `ringkasanBatchPo()` + dipakai di `reviewPo`, supaya
   teks "tidak ada barang berangkat" punya satu sumber yang bisa diuji.
3. **Sesi demo adalah prasyarat tulis, bukan hiasan.** Approval/eksekusi ditolak
   ("aksi tulis ditolak") sampai `POST /demo/session/start` aktif. Membangun template
   menyegarkan timestamp dan me-reset baris approval meski ID deterministik tetap —
   keputusan yang tadi "1 dari 2" bisa berubah jadi "0 dari 2" setelah "Muat Demo".

Gerbang: tsc 0 (seluruh proyek), vitest 4 berkas / 37 tes lulus (termasuk
`tests/po-dispatch-summary.test.ts`, 6 tes baru), bukti live pesan review PO:
"… executed. 1 batch ditahan: sudah berangkat 2026-10-28T05:15:30.119336+00:00."
0 commit.

## Ronde 53 — 2026-10-29: halaman "Pasokan & Kebutuhan" disamakan dengan bahasa konsol

Arahan pemilik: "redesign page supaya hasilnya benar-benar design consistent dengan halaman
lainnya". Halaman = tab `Pasokan & Kebutuhan` (peran Ahli Gizi). Sebelum menyunting, hierarki
judul dan tombol seluruh tab DIUKUR di aplikasi hidup (Hari Ini, Overview, Location Network,
Recommendations, Decision & Evidence) — jadi keputusannya angka, bukan selera.

1. **`button-quiet` adalah kelas HANTU.** Dipakai empat kali (tombol "Tutup" rincian lokasi +
   tiga kontrol Demo Control) tetapi TIDAK PERNAH dideklarasikan, sehingga keempatnya mewarisi
   `.button` dan tampil pil biru penuh. Terukur: `Tutup` 71x39 px, `backgroundColor` rgb(37,99,235)
   — elemen paling berteriak di kartu, mengalahkan judul kartunya sendiri. Dideklarasikan sebagai
   kontrol tenang (putih, garis `--line`, tinta `--ink`, hover `--surface-sunken`); sesudahnya
   terukur putih/rgb(15,23,42), tetap pil 999px (bahasa tombol proyek sejak 27 Okt 2026).
2. **Judul sub-bagian "Batch" keluar dari tangga tipografi.** `.batches h4` memakai `--fs-4` (16 px)
   + bobot bawaan h4 (700) sehingga LEBIH BESAR daripada judul kartu induknya ("Jakarta · telur",
   14 px/600) — hierarki terbalik, dan satu-satunya 16 px di antara sebelas judul 14 px/600.
   Diturunkan ke bahasa label mikro yang sudah dipakai `agenda-group-title` / kepala panel
   Governance: 12 px/700 KAPITAL, letter-spacing `--track-caps`, tinta `--ink-muted`.
3. **Empat ubin angka adalah kartu di dalam kartu.** Permukaan putih + radius 12 + garis sendiri
   di dalam kartu putih radius 12, nilai 18 px/650 (bobot 650 tidak ada di skala 400/500/600/700).
   Disamakan dengan bahasa ubin dalam-kartu `.detail-kpi` (Decision & Evidence): `--surface-sunken`,
   radius kontrol 8 px, label 12 px/600 KAPITAL, nilai `--font-data` 16 px/600 dengan angka tabular.
   Nada danger/safe/unknown DIPERTAHANKAN — di situ warnanya membawa makna, bukan hiasan.

Yang sengaja TIDAK diubah, karena sudah konsisten dan terukur: kolom `.fact-row`
(`minmax(150px,45%) 1fr` — dipakai bersama Decision & Evidence), radius pil 999 px pada semua
tombol (keputusan pemilik 27 Okt 2026), dan judul kartu 14 px/600.

Gerbang: tsc 0, `next lint` 0, vitest **219 berkas / 2.532 tes lulus** (termasuk
`tests/tombol-quiet-dan-label-batch.test.ts`, 4 tes baru, ditulis MERAH dulu: 4 gagal sebelum
implementasi), build `BUILD_ID=5h4_bilKeSy83C_aN2b0W` (via `NEXT_DIST_DIR=.next-build` karena
`next dev` memegang `.next`). Bukti live (peran Ahli Gizi, 1247 px): Tutup putih/tinta biasa,
label BATCH 12 px/700 KAPITAL, ubin `rgb(241,245,249)` radius 8 px, nilai 16 px/600 Fira Code.
0 commit.

### Gugus filter "Komoditas" → bahasa chip filter Recommendations

Pemilik memilih (setelah diukur): gugus filter disamakan ke POLA CHIP FILTER Recommendations,
bukan dibiarkan seperti Overview. Fakta sebelum perubahan: gugus "Komoditas" di Pasokan &
Kebutuhan dan di Overview SUDAH identik piksel satu sama lain (kartu 947x46, padding 10px 16px,
radius 12, label 14 px/500, pil 63x24 13 px/500) — jadi yang benar-benar berbeda adalah blok
filter di Recommendations: chip 132x32, 13 px/600, TANPA kartu putih.

Perubahan: `filter-card` dilepas dari TIGA tempat markup (`components/LocationNetworkBoard.tsx`,
`components/SurplusBoard.tsx`, `app/page.tsx` bagian Overview) sehingga tidak ada lagi kartu
putih untuk gugus filter; CSS baru ditulis SESUDAH aturan `.filter-card .commodity-pill` dan
semua selektornya bersarang di `.commodity-filters` (`.commodity-filters .commodity-pill`,
`…-active`, `…:hover`) supaya pil hitungan statis di halaman lain tidak ikut berubah.

Bukti terukur sesudahnya (1247 px): gugus 947x32, latar transparan, tanpa garis/padding, gap 8,
satu baris; chip 56x32, 13 px/600, padding 5px 13px, radius 999, aktif `rgb(37,99,235)`/putih —
sama keluarga dengan chip Recommendations 132x32 13 px/600. Pil statis di halaman Pemasok TETAP
88x22 / 12 px/500 / padding 2px 10px (scope berhasil). 390 px: `docScrollWidth` 390 =
`docClientWidth`, tanpa gulir mendatar; tinggi halaman 1.856 px.

Tes: `tests/filter-komoditas-chip.test.ts` (6 tes, MERAH dulu — 5 gagal). Satu tes lama yang
memaku kelas persis (`tests/location-network-transfers.test.tsx:119`) sengaja diubah ke
`class="commodity-filters"` — kontraknya memang berubah, bukan dilonggarkan.

Gerbang: tsc 0, `next lint` 0, vitest **220 berkas / 2.538 tes lulus**, build
`BUILD_ID=JTXRrhT23kPfgXu8Cajwd`. 0 commit.

## Ronde 54 — 2026-10-29: Keamanan Pangan — Ringkasan pengawasan & Bukti suhu diupgrade

Arahan pemilik: *"gunakan berbagai skill fullstack, ui ux, testing pada halaman Keamanan Pangan
upgrade design upgrade ringkasan pengawasan, suhu semaksimal mungkin namun tetap sama atau cocok
dengan design lainnya"*.

**Batas yang dipegang.** Keputusan 29 Okt sebelumnya tetap berlaku: lima angka EKSKLUSIF di
Ringkasan, tanpa bar komposisi, tanpa persentase, tanpa legenda — menambah bar berarti
mengembalikan tiga pengkodean untuk satu himpunan data. Karena itu upgrade diisi dengan informasi
yang BELUM ada di kartu, bukan dengan menggambar ulang angka yang sudah ada:

1. **Paling mendesak** (`components/FoodSafetyBoard.tsx`): satu batch dengan `usable_until` terdekat
   di antara baris yang MASIH boleh dipakai. Batch bertone danger dan yang ditahan dikecualikan —
   "segera pakai" untuk keduanya menyesatkan. Bila `hoursLeft < 0`, label berganti **"Sudah lewat"**
   dan waktunya bertinta bahaya; datanya tidak disembunyikan, kalimatnya tidak menyarankan memakai.
2. **Berat di bawah "Gagal uji"**: `summary.failedKg` sudah ada tetapi hanya dicetak untuk "Ditahan".
   Kini `tile.kg` mengisi kedua kelompok; berat yang tidak dikirim server tetap ditulis
   "berat tidak tercatat" (null ≠ 0).
3. **Label tombol** menjadi `Tinjau N batch perlu tindakan` dengan N =
   needsVerification + quarantined + unchecked.
4. **Kebaruan bukti** (`components/TemperatureEvidenceCard.tsx`): `observed_at` dikirim server tetapi
   tidak pernah dicetak; sekarang tiap baris menulis "dibaca 28 Okt 2026 06.20" (via
   `formatMomentWib`). Tanpa `observed_at` → tidak ada kalimat waktu.
5. **Penanda "wajib dingin"** untuk `cold_chain_required = true`: netral (garis + teks redup),
   karena ini SYARAT, bukan keadaan. Geometrinya disamakan dengan `.board-badge` — `line-height: 16px`
   + `display: inline-block`; terukur 87x22 vs 86x22, selisih tinggi 0 px (percobaan pertama
   `line-height: inherit` menghasilkan 24 px, beda 2 px — dicatat supaya tidak diulang).
6. **Ukuran bukti**: kaki kartu menyebut `N sampel tercatat` (jumlah `sample_count` yang dikirim);
   tidak dicetak bila tidak ada satu pun jumlah.
7. **Catatan "menuntut bukti"** berhenti menjadi kotak amber penuh dengan pagar kiri 4 px —
   sekarang pola yang sama dengan putusan Ringkasan: titik 8 px + kalimat, latar transparan.

**Tes.** Dua berkas baru, ditulis MERAH lebih dulu: `tests/safety-ringkasan-mendesak.test.tsx`
(6 tes; 6 gagal sebelum implementasi) dan `tests/temperature-evidence-recency.test.tsx`
(6 tes). Satu tes lama menghitung `safety-count-note` secara global dan jadi 2 setelah berat gagal
ikut dicetak — asersinya DIPERTAJAM per kelompok (blok "Ditahan" berisi 540 kg, blok "Gagal uji"
tidak), bukan dilonggarkan.

**Gerbang.** `tsc` 0, `next lint` 0, vitest **223 berkas / 2.560 tes lulus**, build
`BUILD_ID=xb_mNGteO2N0HbVkfLPZU`. Build pertama sempat gagal dengan "JSX expressions must have one
parent element" pada pohon yang sedang disunting sesi lain; `tsc` bersih dan build berikutnya hijau
— dicatat sebagai kejadian pohon bersama, bukan cacat commit ini.

**Bukti live** (localhost:3010, Kepala SPPG Bandung, 1247 px): Ringkasan 947x233 (baris tenggat
911x20, label 12 px kapital, waktu 13 px/600 `--warn-ink` tabular), Bukti suhu 947x447 dengan enam
baris 454x76, tanpa gulir mendatar, tinggi halaman 3.599 px. 390 px: `docScrollWidth` =
`docClientWidth` = 390, tinggi 8.655 px (tabel menjadi kartu berlabel ≤860 px).

**Catatan alat.** `_qa/ukur-viewport.cjs` kini menerima `UKUR_TAB` (regex judul tab) sehingga
pengukuran 390 px bisa dipakai untuk halaman selain Location Network; sebelumnya tab-nya dipaku.

## Ronde 55 — 2026-10-29: Pemasok dapat riwayat penerimaan (Dok 05 §8.5/§9)

**Keputusan.** Halaman Pemasok mendapat kartu "Riwayat penerimaan" yang disuapi endpoint baru
`GET /receipts/riwayat`, bukan memakai ulang `GET /receipts/menunggu`.

Alasannya: antrean `menunggu` hanya memuat barang yang BELUM diputuskan — ia tidak bisa menjawab
pertanyaan audit "berapa nilai yang sudah diterima dari pemasok ini", karena catatan `disetujui`
dan `ditolak` tidak pernah ada di sana. Menambah parameter status pada endpoint antrean akan
membuat satu endpoint dengan dua arti (antrean kerja vs buku riwayat); dua endpoint dengan dua
kontrak lebih jujur.

**Data honesty, tiga aturan yang tidak boleh dilunakkan.**
1. `received_kg` tetap `null` sampai status `disetujui`; UI mencetak "diterima —", bukan 0.
2. Batch tanpa ikatan PO → nilai `null` → "tidak tercatat", **bukan** "Rp 0". Rp 0 berarti
   "barangnya tidak bernilai"; null berarti "acuannya tidak ada".
3. Baris `ditolak` tidak menampilkan rupiah sama sekali ("—") dan tidak dirender kalimat asal
   harga. Perkiraan rupiah untuk barang yang tidak diterima terbaca sebagai uang yang keluar.

**Ringkasan dihitung server.** `ringkasan` menjumlah seluruh baris cakupan, termasuk yang tidak
dikirim karena `limit`. Penyaring di UI hanya menyaring tampilan; angka kepala tetap angka
cakupan — kalau klien yang menjumlah, angka kepala akan berubah saat orang menekan "Disetujui".

**`nilai_menunggu_idr` hanya baris `menunggu`.** Versi pertama menjumlah setiap baris yang tidak
punya `accepted_value_idr`, sehingga barang yang sudah ditolak ikut terhitung "menunggu"
(Rp 8.100.000 → seharusnya Rp 2.700.000). Ditemukan dari verifikasi live, bukan dari tes; kini
dikunci asersi di `tests/test_receipts_riwayat.py`.

**Seed berbagi batch = data yang saling bertentangan.** Seed penerimaan lama membuat catatan pada
batch yang sama dengan seed baru, sehingga satu batch punya catatan `disetujui` DAN `menunggu`.
`_semai_riwayat_penerimaan` sekarang melewati batch yang sudah punya catatan; tidak ada lagi
batch dengan dua putusan berbeda.

**Tabel harus muat, bukan bergulir di desktop.** Tanpa lebar kolom eksplisit, tabel 1.116 px di
bungkus 917 px dan kolom Nilai — alasan kartu ini ada — terpotong. `table-layout: fixed` + lima
lebar kolom (15/24/13/17/31 %) menguncinya; gulir horizontal hanya diizinkan ≤760 px.

**Catatan alat.** `pytest` backend di kontainer memakai DB dev yang sama dan me-reset data
penerimaan lewat fixture. Setelah suite backend, jalankan
`python -m app.seed.demo_template` sebelum mengukur atau demo — kalau tidak, angka yang dilaporkan
berasal dari data tes, bukan data demo.
## Ronde 59 — 2026-10-29: Demo Control — log "Proses pengambilan data" real time

**Permintaan pemilik.** *"Pada bagian Bukti agent dibuat real time untuk log
Proses Pengambilan Data kayak di terminal."* Sebelumnya blok itu hanya menulis
"tunggu…" lalu semua langkah muncul sekaligus saat putaran selesai.

**Bentuk yang dipilih — pub/sub bertoken, bukan streaming yang menjalankan ulang.**
- `POST /demo/agent/run` menerima `run_token` opsional. Tanpa token, perilakunya
  persis seperti sebelumnya (nol biaya siaran).
- `_run_supplier_procurement` menerima `on_step`; satu helper `_tambah()` yang
  dipakai ketujuh titik `traces.append(...)` menyimpan langkah DAN menyiarkannya.
- `GET /demo/agent/stream?run_token=…` (SSE) hanya mendengar kanal
  (`app/services/agent_progress.py`, `queue.Queue` karena pipeline berjalan di
  threadpool, bukan event loop FastAPI).
- Ditolak: endpoint SSE yang menjalankan pipeline sendiri — satu klik bisa
  melahirkan dua keputusan, dan logika run akan tergandakan.

**Kontrak kecil yang dijaga.**
- `: siap` dikirim pertama; panel menunggu penanda itu (maks 2 dtk) SEBELUM POST.
- Komentar `: tunggu` tiap 15 dtk supaya proxy tidak memutus koneksi diam.
- Kanal ditutup di `finally`; batas umur 300 dtk; antrean penuh = siaran ditelan.
- `ringkas` hanya mencetak skalar (maks 4 kunci, 60 karakter per nilai); struktur
  bersarang dibiarkan ke tab Agent Log, bukan diratakan jadi JSON panjang.

**Klien.**
- `lib/agent-stream.ts` (murni): `bacaSse` + `langkahDari` — potongan jaringan
  sembarang, termasuk `data:` terbelah dua dan CRLF dari proxy.
- `streamDemoAgent` di `lib/api.ts`: `fetch` + `ReadableStream`, bukan
  `EventSource`, karena `EventSource` tidak bisa mengirim header `Authorization`.
- `components/AgentRunTerminal.tsx`: mono, jam WIB, pil live/selesai/siap/galat,
  gulir otomatis yang mati saat operator menggulir ke atas (tombol **Ikuti**).
- `DemoControlPanel`: kanal dibuka sebelum POST, ditutup di `finally`; penjaga
  3 menit supaya tombol tidak tertinggal "berjalan" bila server tidak menjawab;
  badge blok Bukti agent menulis "putaran berjalan" selama siaran (dua angka
  berbeda berdampingan membingungkan).

**Bukti terukur.** Baris datang bertahap: 2 → 4 → 7 → 8 pada 0,4 / 4,4 / 8,9 /
13,4 dtk, lalu SUPERVISE ±45 dtk; akhir "selesai" 7 baris, badge berpindah ke
"16 langkah tercatat". 390 px: terminal 316 px, badan `clientHeight` 260 /
`scrollHeight` 352, kolom baris `52px 232px`, `scrollWidth 390 = clientWidth 390`.
Uji: 19 tes frontend (parser + terminal), 9 tes backend (bus + endpoint SSE).

**Ditolak / belum.** Terminal gelap (acuan menolak chrome jendela; yang diambil
hanya mono + jam + baris mengalir). Warna tetap token terang yang sudah ada.
