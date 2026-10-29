// PAGAR KONTRAK redesign halaman "Performance & Audit" (tab `kpi-kualitas`).
//
// Dibuat di Tahap 0 sebelum satu pun tampilan diubah. Tujuannya sama seperti
// pagar kontrak Agent Activity Log: redesign tidak boleh "membaikkan" tampilan
// dengan merusak sifat yang sudah benar. Karena itu:
//
//   1. SATU tes nyata di bawah mengunci sifat yang harus tetap benar selamanya
//      (urutan isi: KPI → audit perhitungan → mutu agen, dan panel audit TIDAK
//      menghitung angka sendiri).
//   2. `it.todo` adalah janji per tahap; tiap tahap mengubah satu todo
//      menjadi tes sungguhan. Sisa todo saat ini: Tahap 5 dan Tahap 6
//      (Tahap 1–4 sudah jadi tes nyata).
//
// Baseline Tahap 0 (diukur, bukan diperkirakan):
//   markup ter-render 22.373 char — teks terbaca 3.912 char
//   KPI 7.924 · audit 2.851 · mutu 11.520 (mutu 51% halaman)
//   5 komponen 1.525 baris · 89 selektor `.kpi-*` · 15 selektor `.perf-audit*`
//   38 selektor `.quality-*` · 3 <table> · 2 <details> · 5 <h3> · 2 <h2>
//
// Aturan desain yang dipakai (skill ui-ux-pro-max: Minimalism & Swiss, density
// 7/10, "avoid ornate design + no filtering"; palet skill TIDAK dipakai — token
// repo di docs/design.md yang menang):
//   - Number Formatting: angka pakai pemisah ribuan / tabular-nums
//   - Table Handling: tabel lebar dibungkus wadah ber-gulir, bukan merusak layout
//   - Empty States: bagian kosong menyebut sebab + aksi, bukan layar putih
//   - Sticky Navigation: nav lengket tidak boleh menutupi isi bagian pertama
//   - Active State: bagian yang sedang dilihat ditandai
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import KpiQualityBoard from "../components/KpiQualityBoard";
import KPIDashboard, { DESKRIPSI_HALAMAN } from "../components/KPIDashboard";
import { ringkasMetrik } from "../components/KpiMetaLine";
import { runOf } from "../lib/agent-quality";
import { PERF_AUDIT_SECTION_IDS, perfAuditSections } from "../lib/section-jump";

const AKAR = join(__dirname, "..");
const baca = (p: string) => readFileSync(join(AKAR, p), "utf8");

const TRACE = {
  steps: [
    {
      step_name: "PREDICT",
      tool_called: "forecast.daily",
      output_summary: { method: "provider_forecast" },
      step_at: "2026-10-11T05:16:46Z",
    },
  ],
};

const RUNS = [
  runOf(
    {
      decision_id: "e430a0e8-9d9a",
      decision_type: "regional_balance",
      status: "pending_approval",
      iteration: 3,
    },
    TRACE,
    { verifier: { verdict: "consistent" } }
  ),
];

const KPI = {
  period: { start: "2026-10-07T12:00:00+00:00", end: "2026-10-08T12:00:00+00:00" },
  scope: { location_id: "loc-1", role: "sppg_head" },
  data_source: "live_aggregate",
  data_mode: "demo",
  method_version: "kpi-2026.10",
  computed_at: "2026-10-08T12:05:00+00:00",
  metrics: [
    {
      name: "Meal Continuity Rate",
      unit: "percent",
      state: "available",
      value: 96.4,
      reason: null,
      sample_count: 12,
      coverage: 0.92,
      previous_value: 93.5,
      trend: "up",
      facts: {
        formula_version: "sdc-3",
        storage_default_days: 2,
        storage_default_basis: "rencana_menu",
      },
    },
    {
      name: "Delivery On Time",
      unit: "percent",
      state: "no_data",
      value: null,
      reason: "penyebut kosong",
      sample_count: 0,
      coverage: null,
      previous_value: null,
      trend: null,
    },
  ],
};

const render = (kpi: any = KPI) =>
  renderToStaticMarkup(
    <KpiQualityBoard
      kpi={kpi}
      runs={RUNS}
      evaluatedCount={8}
      totalDecisions={95}
      windowKey={"past7d" as never}
      scope={"simulasi" as never}
    />
  );

describe("Performance & Audit — pagar kontrak redesign", () => {
  // SIFAT YANG TIDAK BOLEH BERUBAH SELAMA REDESIGN ------------------------
  it("tetap satu halaman: KPI → audit perhitungan → mutu agen", () => {
    const html = render();
    const kpi = html.indexOf('class="kpi-dashboard"');
    const audit = html.indexOf('data-testid="performance-audit"');
    const mutu = html.indexOf('class="board-page"');
    expect(kpi).toBeGreaterThan(-1);
    expect(audit).toBeGreaterThan(kpi);
    expect(mutu).toBeGreaterThan(audit);
  });

  it("panel audit tidak menghitung angka sendiri (hanya membaca amplop /kpi)", () => {
    // Komentar dibuang dulu: tanggal seperti "29 Okt" bukan kode.
    const panel = baca("components/PerformanceAuditPanel.tsx")
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/^\s*\/\/.*$/gm, "");
    // Boleh memformat (toLocaleString) dan membaca, tidak boleh menurunkan
    // metrik baru dari nilai KPI.
    expect(panel).not.toMatch(/\bMath\./);
    expect(panel).not.toMatch(/\.reduce\(/);
    expect(panel).not.toMatch(/\*\s*100\b|\/\s*100\b/);
  });

  // JANJI PER TAHAP -------------------------------------------------------
  it("Tahap 1 — kerangka: PageShell + tiga bagian bertajuk, tanpa <hr> ornamen", () => {
    const html = render();

    // (1) Satu kepala halaman: judul + deskripsi dari PageShell, bukan dari
    //     KPIDashboard (yang kini dipanggil dengan showHeader={false}).
    expect(html).toContain("Performance &amp; Audit");
    expect(html).toContain(DESKRIPSI_HALAMAN);
    // Tepat satu <h1> di halaman — judul tidak boleh lahir dua kali. (Nama
    // halaman juga muncul di aria-label navigasi lompat, itu bukan judul.)
    expect((html.match(/<h1/g) || []).length).toBe(1);

    // (2) Tiga bagian bertajuk, urut sesuai bacaan, tiap judul punya jangkar
    //     yang benar-benar ada di halaman (bukan tautan mati).
    const judul = [...html.matchAll(/class="pa-section" id="([^"]+)"/g)].map((m) => m[1]);
    expect(judul).toEqual([
      PERF_AUDIT_SECTION_IDS.hasil,
      PERF_AUDIT_SECTION_IDS.audit,
      PERF_AUDIT_SECTION_IDS.mutu,
    ]);
    for (const id of judul) {
      expect(html).toContain(`id="${id}"`);
    }

    // (3) Navigasi lompat memakai daftar yang sama dengan jangkar di atas.
    const target = perfAuditSections();
    expect(target).toHaveLength(3);
    expect(target.map((t) => t.id)).toEqual(judul);
    expect(html).toContain('class="section-jump');

    // (4) Ornamen dibuang; pemisah bagian kini judul h2.
    expect(html).not.toContain("kpi-quality-divider");
    expect(html).not.toContain("<hr");

    // (5) Sumbernya: KPIDashboard dirender tanpa kepala sendiri di dalam board.
    const board = baca("components/KpiQualityBoard.tsx").replace(/\/\*[\s\S]*?\*\//g, "");
    expect(board).toContain("<PageShell");
    expect(board).toContain("showHeader={false}");
    expect(baca("app/globals.css")).toContain(".pa-section-title {");
  });
  it("Tahap 2 — satu bilah kontrol: periode + cakupan + meta sebaris", () => {
    const html = render();

    // (1) Satu bilah, memuat ketiga kelompoknya.
    expect((html.match(/class="kpi-controls"/g) || []).length).toBe(1);
    const mulai = html.indexOf('class="kpi-controls"');
    const bilah = html.slice(mulai, html.indexOf("kpi-group", mulai));
    expect(bilah).toContain('class="kpi-period"');
    expect(bilah).toContain("kpi-scope-toggle");
    expect(bilah).toContain('class="kpi-meta-line"');
    // Periode · cakupan · meta sebaris, bukan tiga blok bertumpuk.
    expect(bilah.indexOf("kpi-period")).toBeLessThan(bilah.indexOf("kpi-scope-toggle"));
    expect(bilah.indexOf("kpi-scope-toggle")).toBeLessThan(bilah.indexOf("kpi-meta-line"));

    // (2) Duplikat dibuang: pemilih periode hanya tombol (tiga jendela), tidak
    //     ada lagi pil teks periode di kepala halaman.
    expect((html.match(/kpi-period-pill/g) || []).length).toBe(3);
    // Kepala halaman tidak boleh MENGULANG kontrol periode/cakupan — itu inti
    // tahap 2. Sejak 30 Okt 2026 kepala memakai baris pil seperti tujuh tab
    // lain, tetapi isinya jumlah (metrik, run), bukan pilihan yang sama.
    const kepala = html.slice(0, html.indexOf('id="pa-hasil"'));
    expect(kepala).not.toMatch(/kpi-period-pill|kpi-scope-toggle/);
    expect(kepala).not.toMatch(/7 hari terakhir|1 bulan terakhir/);

    // (3) Meta yang tidak bisa dipilih tetap ada, satu kali masing-masing.
    for (const testid of ["kpi-scope", "kpi-data-mode", "kpi-computed-at"]) {
      expect((html.match(new RegExp(`data-testid="${testid}"`, "g")) || []).length).toBe(1);
    }

    // (4) Ringkasan keadaan metrik: dihitung dari payload, diumumkan pembaca
    //     layar, dan nol tidak dicetak. Fixture punya 1 tersedia + 1 no_data.
    const ringkas = html.match(/data-testid="kpi-ringkasan"[^>]*>([^<]+)</);
    expect(ringkas?.[1]).toBe("2 metrik · 1 tersedia · 1 belum ada data");
    const blokRingkas = html.slice(html.indexOf('data-testid="kpi-ringkasan"') - 80, html.indexOf('data-testid="kpi-ringkasan"') + 20);
    expect(blokRingkas).toContain('role="status"');
    expect(blokRingkas).toContain('aria-atomic="true"');

    // (5) Fungsi ringkasannya sendiri: nol tidak dicetak, keadaan tak dikenal
    //     tetap dihitung (tidak disembunyikan).
    expect(ringkasMetrik([{ state: "available" }, { state: "available" }])).toBe(
      "2 metrik · 2 tersedia"
    );
    expect(ringkasMetrik([{ state: "aneh" }])).toBe("1 metrik · 1 keadaan lain");
    expect(ringkasMetrik([])).toBeNull();

    // (6) CSS: bilah memakai flex satu baris, meta didorong ke kanan, dan
    //     margin bawaan kedua kelompok dinolkan supaya tidak jadi dua baris.
    const cssBersih = baca("app/globals.css").replace(/\/\*[\s\S]*?\*\//g, "");
    const ambil = (sel: string) => {
      const i = cssBersih.indexOf(sel);
      return i < 0 ? "" : cssBersih.slice(cssBersih.indexOf("{", i) + 1, cssBersih.indexOf("}", i));
    };
    expect(ambil(".kpi-controls {")).toContain("flex-wrap: wrap");
    expect(ambil(".kpi-meta-line {")).toContain("margin: 0 0 0 auto");
    expect(ambil(".kpi-controls .kpi-period,")).toContain("margin: 0");
  });
  it("Tahap 3 — kartu ringkas: rincian di satu panel, kartu seragam, tanpa lipatan teknis", () => {
    const html = render();

    // (1) Mekanisme di rencana tahap ini (`<details>` per kartu) DIBATALKAN
    //     pemilik 29 Okt 2026 ("ketika KPI diklik muncul penjelasan detail di
    //     bawah sub sub KPI, ada 1 shape informasi"). Rincian dibuka sebagai
    //     SATU panel di bawah grid, bukan lipatan per kartu.
    //     Cakupan: bagian "Hasil KPI" saja — bagian Mutu agen punya lipatan
    //     "Cara membaca kartu ini" miliknya sendiri dan tidak diubah di sini.
    const bagianKpi = html.slice(
      html.indexOf('class="kpi-dashboard"'),
      html.indexOf('id="pa-audit"'),
    );
    expect(bagianKpi.length).toBeGreaterThan(0);
    expect(bagianKpi).not.toContain("<details");
    expect(bagianKpi).not.toContain("<summary");

    // (2) Semua kartu satu bentuk: seluruh kartu adalah tombol yang menunjuk
    //     panel yang SAMA — tidak ada kartu yang membuka tempat lain.
    const kartu = html.match(/<article[^>]*class="kpi-card card[^"]*"[^>]*>/g) || [];
    expect(kartu).toHaveLength(2);
    for (const k of kartu) {
      expect(k).toContain('role="button"');
      expect(k).toContain('aria-controls="kpi-detail"');
      expect(k).toContain('aria-expanded="false"');
    }

    // (3) Slot kartu sama dan urutannya sama di setiap kartu: kepala (nama +
    //     ikon) → angka → satu baris keadaan. Keseragaman ini yang membuat
    //     tujuh kartu terbaca sebagai satu tabel, bukan tujuh kotak.
    const potong = html.split('<article class="kpi-card card');
    const isiKartu = potong.slice(1).map((s) => s.slice(0, s.indexOf("</article>")));
    expect(isiKartu).toHaveLength(2);
    for (const isi of isiKartu) {
      const top = isi.indexOf('class="kpi-card-top"');
      const nilai = isi.indexOf('class="kpi-value');
      const flags = isi.indexOf('class="kpi-card-flags"');
      expect(top).toBeGreaterThan(-1);
      expect(nilai).toBeGreaterThan(top);
      expect(flags).toBeGreaterThan(nilai);
    }

    // (4) Kartu tidak memuat rincian teknis — itu tugas panel. Yang diuji
    //     khusus: istilah audit yang dulu bocor dari `facts` metrik.
    for (const isi of isiKartu) {
      for (const teknis of ["sdc-3", "formula_version", "storage_default_basis", "Rumus"]) {
        expect(isi).not.toContain(teknis);
      }
    }

    // (5) Dua fakta berbeda tidak boleh menempel jadi satu kata untuk pembaca
    //     layar ("belum ada dataBukti: …" terbaca sebagai satu istilah asing).
    //     Diuji dari markup: elemen bersaudara di baris keadaan harus dipisah
    //     spasi, bukan berimpit `</span><span`.
    expect(bagianKpi).toMatch(/<\/span> <span class="kpi-trend/);
    expect(bagianKpi).not.toMatch(/<\/span><span class="kpi-trend/);
    expect(bagianKpi).not.toMatch(/<\/span><span class="kpi-prov-evidence/);

    // (6) Panel: satu wilayah bernama, judulnya bisa menerima fokus, dan
    //     pembungkusnya menggulir panel ke layar saat dibuka. Tanpa ini kartu
    //     di baris pertama membuka panel yang berada DI BAWAH lipatan (terukur
    //     873 px dari atas pada viewport 900 px) sehingga klik terasa mati.
    const panelSrc = baca("components/KpiDetailPanel.tsx");
    expect(panelSrc).toContain('role="region"');
    expect(panelSrc).toContain("kpi-detail-judul");
    const dashSrc = baca("components/KPIDashboard.tsx");
    expect(dashSrc).toContain("scrollIntoView");
    expect(dashSrc).toMatch(/prefers-reduced-motion/);

    // (7) CSS: tinggi seragam dipaksa grid (bukan tinggi tetap per kartu) dan
    //     panel punya jarak aman terhadap bar kepala yang lengket.
    const cssExt = baca("app/theme-ext.css");
    const ambilExt = (sel: string) => {
      const i = cssExt.indexOf(sel + " {");
      return i < 0 ? "" : cssExt.slice(cssExt.indexOf("{", i) + 1, cssExt.indexOf("}", i));
    };
    expect(ambilExt(".kpi-grid")).toContain("grid-auto-rows: 1fr");
    expect(ambilExt(".kpi-grid > .kpi-card")).toContain("height: 100%");
    expect(ambilExt(".kpi-card-flags")).toContain("margin-top: auto");
    expect(ambilExt(".kpi-detail")).toContain("scroll-margin-top");

    // (8) Judul panel menerima fokus terprogram → peramban menggambar kotak
    //     fokus persegi di atas judul (terlihat di tangkapan 1360 px). Cincin
    //     dimatikan hanya untuk elemen ini; kontrol lain tidak disentuh.
    const judulCss = cssExt.slice(cssExt.indexOf(".kpi-detail-title:focus"));
    expect(judulCss).toContain(".kpi-detail-title:focus,");
    expect(judulCss).toContain(".kpi-detail-title:focus-visible");
    expect(judulCss.slice(0, judulCss.indexOf("}"))).toContain("outline: none");
  });
  it("Tahap 4 — audit: strip 6 sel + tabel Metrik · Keadaan · Sampel · Sebab", () => {
    const html = render();
    const cssBersih = baca("app/theme-ext.css").replace(/\/\*[\s\S]*?\*\//g, "");
    const aturan = (sel: string) => {
      const i = cssBersih.indexOf(`${sel} {`);
      expect(i, `aturan ${sel} tidak ditemukan`).toBeGreaterThan(-1);
      const buka = cssBersih.indexOf("{", i);
      return cssBersih.slice(buka + 1, cssBersih.indexOf("}", buka));
    };

    // (1) Enam jejak perhitungan jadi SATU strip enam sel, urutannya tetap
    //     seperti sebelumnya — ringkas tanpa kehilangan satu fakta pun.
    expect((html.match(/class="perf-audit-strip"/g) || []).length).toBe(1);
    expect((html.match(/class="perf-audit-cell"/g) || []).length).toBe(6);
    const strip = html.slice(0, html.indexOf('class="perf-audit-h4"'));
    const label = [...strip.matchAll(/<dt>([^<]*)<\/dt>/g)].map((m) => m[1]);
    expect(label).toEqual([
      "Metode agregasi",
      "Versi rumus biaya kirim aman",
      "Jendela simpan gudang",
      "Periode laporan",
      "Cakupan data",
      "Dihitung",
    ]);
    // Tidak ada lagi grid dua-tiga baris: strip = satu baris enam kolom.
    expect(aturan(".perf-audit-strip")).toContain("grid-template-columns: repeat(6");
    expect(html).not.toContain("perf-audit-grid");

    // (2) Kolom tabel persis seperti rencana, dan "sebab" bukan "cakupan/alasan".
    const thead = html.slice(html.indexOf("<thead>"), html.indexOf("</thead>"));
    const kolom = [...thead.matchAll(/<th[^>]*>([^<]*)<\/th>/g)].map((m) => m[1].trim());
    expect(kolom).toEqual(["Metrik", "Keadaan", "Sampel", "Sebab"]);

    // (3) Keadaan dibawa TEKS + nada (aturan Color Only), bukan warna saja.
    expect(html).toContain('class="perf-audit-state is-available"');
    expect(html).toContain('class="perf-audit-state is-no_data"');
    expect(html).toContain("Tersedia");
    expect(html).toContain("Belum ada data");

    // (4) Baris bermasalah disorot (satu baris saja di fixture ini), dan
    //     penandanya bukan warna: teks keadaan + `data-state` untuk pembaca
    //     layar, warna hanya penguat.
    expect((html.match(/is-bermasalah/g) || []).length).toBe(1);
    const barisBermasalah = html.slice(html.indexOf("is-bermasalah") - 60);
    expect(barisBermasalah).toContain('data-state="no_data"');
    expect(aturan(".perf-audit-row.is-bermasalah > th:first-child")).toContain(
      "box-shadow: inset 3px 0 0"
    );
    expect(aturan(".perf-audit-row.is-bermasalah > td")).toContain(
      "background: var(--warn-bg)"
    );

    // (5) Tabel dilipat HANYA bila semua metrik tersedia; kalau ada yang
    //     bermasalah ia terbuka — audit yang menyembunyikan masalah gagal
    //     tujuannya.
    expect(html).not.toContain("perf-audit-fold");
    const semuaTersedia = render(
      {
        ...KPI,
        metrics: [KPI.metrics[0]],
      }
    );
    expect(semuaTersedia).toContain('class="perf-audit-fold"');
    expect(semuaTersedia).toContain("<summary");
    expect(semuaTersedia).not.toMatch(/<details[^>]*\bopen\b/);
    // Isi tabel tetap ada di markup saat terlipat (bukan dimuat ulang).
    expect(semuaTersedia).toContain("Meal Continuity Rate");

    // (6) Tabel tetap punya jalan gulir sendiri, dan di bawah 620 px tiap
    //     metrik jadi DUA BARIS lewat `data-label` — kolom "Sebab" tidak perlu
    //     digeser mendatar dan tidak dipaksa jadi kartu tinggi.
    expect(aturan(".perf-audit-table-wrap")).toContain("overflow-x: auto");
    expect(html).toContain('data-label="Keadaan"');
    expect(html).toContain('data-label="Sampel"');
    expect(html).toContain('data-label="Sebab"');
    const cssSempit = cssBersih.slice(cssBersih.indexOf("@media (max-width: 620px)"));
    const blok620 = cssSempit.slice(0, cssSempit.indexOf("@media", 10));
    expect(blok620).toContain("grid-template-columns: minmax(0, 1fr) auto auto");
    expect(blok620).toContain('td[data-label="Sebab"]');
    expect(blok620).toContain("grid-column: 1 / -1");
    expect(blok620).not.toContain("min-width: 560px");

    // (7) Nav bagian lengket tidak menutupi bagian yang dituju. Terukur 29 Okt
    //     2026: judul bagian mendarat di y=0 dan strip di y=95, sementara nav
    //     berakhir di y=116 (1440) / 156 (390) — judul + label strip tertutup.
    const cssGlobal = baca("app/globals.css").replace(/\/\*[\s\S]*?\*\//g, "");
    const paSection = cssGlobal.slice(
      cssGlobal.indexOf(".pa-section {"),
      cssGlobal.indexOf("}", cssGlobal.indexOf(".pa-section {"))
    );
    expect(paSection).toContain("scroll-margin-top: 128px");
  });
  it("Tahap 5 — mutu agen: dua sub-blok, rincian per run 44 px + header lengket", () => {
    const html = render();

    // (1) Dua sub-blok bernama, urut skor → rincian, masing-masing menunjuk
    //     judulnya sendiri (wilayah yang bisa disebut pembaca layar).
    const sub = [...html.matchAll(/data-sub-block="([^"]+)"/g)].map((m) => m[1]);
    expect(sub).toEqual(["ringkasan", "rincian"]);
    const judulBlok = [...html.matchAll(/class="quality-block-title" id="([^"]+)"/g)].map((m) => m[1]);
    expect(judulBlok).toEqual(["mutu-ringkasan-judul", "mutu-rincian-judul"]);
    expect(html).toMatch(
      /data-sub-block="ringkasan"[^>]*aria-labelledby="mutu-ringkasan-judul"/
    );
    expect(html).toMatch(/data-sub-block="rincian"[^>]*aria-labelledby="mutu-rincian-judul"/);

    // (2) Hierarki judul tidak dilompati: sub-blok h3, kartu di dalamnya h4.
    expect(html).toContain('<h3 class="quality-block-title"');
    expect((html.match(/<h4/g) || []).length).toBeGreaterThanOrEqual(3);
    expect(html).not.toContain('class="quality-section-head"');

    // (3) Pembagian isi: skor + putusan verifikator di ringkasan; per agen +
    //     per run di rincian. Tidak ada isi yang pindah dua kali.
    const ringkas = html.slice(
      html.indexOf('data-sub-block="ringkasan"'),
      html.indexOf('data-sub-block="rincian"')
    );
    expect(ringkas).toContain('class="quality-stats"');
    expect(ringkas).toContain("Putusan verifikator");
    const rincian = html.slice(html.indexOf('data-sub-block="rincian"'));
    expect(rincian).toContain("Kualitas per agen");
    expect(rincian).toContain("Rincian per run");
    expect(rincian).not.toContain('class="quality-stats"');

    // (4) Tabel per run punya penanda sendiri supaya aturan 44 px + kepala
    //     lengket bisa ditulis untuk tabel ITU saja (tabel per agen tidak ikut).
    expect(html).toContain('class="location-table quality-table quality-runs"');
    expect(html).toContain('data-table="per-run"');
    const agenTable = html.slice(html.indexOf("Kualitas per agen"), html.indexOf("Rincian per run"));
    expect(agenTable).toContain('data-table="per-agen"');

    // (5) CSS: baris per run minimal 44 px (target sentuh), dan kepala tabel
    //     menempel di bawah bilah atas + nav bagian saat halaman digulir.
    const css = baca("app/globals.css").replace(/\/\*[\s\S]*?\*\//g, "");
    const aturan = (sel: string, dari = 0) => {
      const i = css.indexOf(`${sel} {`, dari);
      expect(i, `aturan ${sel} tidak ditemukan`).toBeGreaterThan(-1);
      const buka = css.indexOf("{", i);
      return css.slice(buka + 1, css.indexOf("}", buka));
    };
    expect(aturan(".quality-runs tbody tr")).toContain("height: 44px");
    expect(aturan(".quality-block-title")).toContain("font-size");
    const awal1280 = css.indexOf("@media (min-width: 1280px)");
    expect(awal1280).toBeGreaterThan(-1);
    const blok1280 = css.slice(awal1280, css.indexOf("@media", awal1280 + 10));
    expect(blok1280).toContain(".quality-runs-wrap");
    expect(blok1280).toContain("overflow-x: clip");
    expect(blok1280).toContain(".quality-runs thead th");
    expect(blok1280).toContain("position: sticky");
    expect(blok1280).toContain("top: 118px");
    expect(blok1280).toMatch(/prefers-reduced-motion|z-index: 2/);
  });
  it("Tahap 6 — keadaan kosong bersaran + ringkasan metrik bermasalah", () => {
    const html = render();

    // (1) Ringkasan metrik bermasalah: disebut SEBELUM tabel, dengan jumlah,
    //     nama, dan keadaan tiap metrik — pembaca tidak perlu memindai tujuh
    //     baris untuk tahu ada yang tidak beres. Fixture: 1 tersedia + 1 no_data.
    const ringkas = html.match(
      /data-testid="audit-ringkasan-bermasalah"[^>]*>([\s\S]*?)<\/p>/
    );
    expect(ringkas).not.toBeNull();
    const teksRingkas = (ringkas?.[1] ?? "").replace(/<[^>]+>/g, "").trim();
    expect(teksRingkas).toBe(
      "1 dari 2 metrik perlu perhatian — Delivery On Time (belum ada data)"
    );
    expect(html.indexOf('data-testid="audit-ringkasan-bermasalah"')).toBeLessThan(
      html.indexOf("<thead>")
    );
    // Angka di ringkasan adalah HITUNGAN baris payload, bukan metrik baru.
    expect(ringkas?.[0]).toContain('role="status"');

    // Semua metrik tersedia → tidak ada ringkasan yang mengarang masalah.
    const semuaBaik = render({ ...KPI, metrics: [KPI.metrics[0]] });
    expect(semuaBaik).not.toContain('data-testid="audit-ringkasan-bermasalah"');

    // (2) Keadaan kosong KPI: dulu `return null` — bagian berjudul tanpa isi
    //     dan tanpa sebab. Sekarang dijelaskan + diberi jalan keluar.
    const kosong = renderToStaticMarkup(
      <KPIDashboard kpi={null} onRetry={() => {}} showHeader={false} />
    );
    expect(kosong).toContain('data-empty-state="kpi"');
    expect(kosong).toContain("Belum ada angka KPI");
    expect(kosong).toContain("Coba periode lain");
    expect(kosong).toContain('class="button kpi-retry"');

    // (3) Keadaan kosong mutu agen: sebab + saran, bukan kalimat tunggal.
    const tanpaRun = renderToStaticMarkup(
      <KpiQualityBoard
        kpi={KPI}
        runs={[]}
        evaluatedCount={0}
        totalDecisions={0}
        onRetryQuality={() => {}}
      />
    );
    expect(tanpaRun).toContain('data-empty-state="mutu"');
    expect(tanpaRun).toContain("Belum ada run agen yang tercatat");
    expect(tanpaRun).toContain("muat ulang");

    // (4) CSS: kedua bentuk punya gayanya sendiri; keadaan kosong tidak boleh
    //     menumpuk kartu bergaris tebal di tengah halaman.
    const css = baca("app/globals.css").replace(/\/\*[\s\S]*?\*\//g, "");
    const aturan = (sel: string) => {
      const i = css.indexOf(`${sel} {`);
      expect(i, `aturan ${sel} tidak ditemukan`).toBeGreaterThan(-1);
      const buka = css.indexOf("{", i);
      return css.slice(buka + 1, css.indexOf("}", buka));
    };
    expect(aturan(".empty-panel")).toContain("border-style: dashed");
    expect(aturan(".empty-panel-title")).toContain("font-weight: 600");
    const cssPanel = baca("app/theme-ext.css").replace(/\/\*[\s\S]*?\*\//g, "");
    const iPanel = cssPanel.indexOf(".perf-audit-bermasalah {");

    expect(iPanel, "aturan .perf-audit-bermasalah tidak ditemukan").toBeGreaterThan(-1);

    expect(
      cssPanel.slice(cssPanel.indexOf("{", iPanel) + 1, cssPanel.indexOf("}", iPanel))

    ).toContain("border-left");
  });

});
