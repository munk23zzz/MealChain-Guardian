// Kontrak redesign halaman "Agent Activity Log" (Tahap 0 — baseline, 29 Okt 2026).
//
// Berkas ini adalah PAGAR, bukan tes fungsional: ia mengunci hal-hal yang sudah
// benar hari ini (supaya redesign tidak menghapusnya) dan mencatat kontrak yang
// BELUM ada sebagai `it.todo` — satu todo per tahap, dibuka satu per satu saat
// tahapnya dikerjakan. Sengaja tidak ditulis sebagai tes merah: working tree ini
// dipakai bersama, dan suite yang merah terus-menerus menghapus gunanya gate.
//
// Aturan desain yang dijaga di sini berasal dari UI/UX Pro Max:
// - `Color Only` (High): status tidak boleh dibedakan HANYA dari warna.
// - `Table Handling` (Medium): tabel lebar wajib punya jalan gulir horizontal.
// - `No Results` (Medium): keadaan kosong harus memberi saran + aksi.
// - `Number Formatting`, `Line Height 1.5-1.75`: dipegang lewat token, bukan tes.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import AgentActivityPanel from "../components/AgentActivityPanel";
import AgentPipelinePanel from "../components/AgentPipelinePanel";
import AgentTraceViewer from "../components/AgentTraceViewer";
import { ringkasIntegritas } from "../components/IntegrityPanel";
import DecisionAuditTable from "../components/DecisionAuditTable";
import ModuleSearch from "../components/ModuleSearch";
import { agentLogSections } from "../lib/section-jump";
import { PIPELINE_STAGES } from "../lib/pipeline-stages";
import type { AuditDecision } from "../lib/decision-table";

const css = readFileSync(join(__dirname, "..", "app", "agent-activity.css"), "utf8");

function row(over: Partial<AuditDecision>): AuditDecision {
  return {
    decision_id: "aaaaaaaa-1111-2222-3333-444444444444",
    decision_type: "supplier_procurement",
    status: "pending_approval",
    commodity: "beras",
    location: "Jakarta",
    created_at: "2026-10-27T05:00:00.000Z",
    expires_at: "2026-10-30T05:00:00.000Z",
    quantity_kg: 300,
    safe_delivered_cost: 4500000,
    ...over,
  } as AuditDecision;
}

const SEPULUH = Array.from({ length: 10 }, (_, i) =>
  row({
    decision_id: `aaaaaaaa-1111-2222-3333-0000000000${String(i).padStart(2, "0")}`,
    status: i === 2 ? "rejected" : "pending_approval",
  }),
);

function tabel(rows: AuditDecision[]): string {
  return renderToStaticMarkup(
    <DecisionAuditTable
      rows={rows}
      total={rows.length}
      page={1}
      onPage={() => {}}
      selectedId={null}
      onSelect={() => {}}
      summary="tes"
      now={null}
    />,
  );
}

function panel(rows: AuditDecision[]): string {
  return renderToStaticMarkup(
    <AgentActivityPanel
      role="sppg_head"
      decisions={rows}
      total={rows.length}
      page={1}
      onPage={() => {}}
      selectedId={null}
      onSelect={() => {}}
      summary="10 keputusan"
      steps={null}
      ledger={null}
      overview={null}
      periodLabel="7 hari"
      now={null}
      loading={false}
      onOpenEvidence={() => {}}
    />,
  );
}

describe("pagar: yang sudah benar sebelum redesign", () => {
  it("status ditolak dibedakan TEKS + warna, bukan warna saja", () => {
    const html = tabel([row({ status: "rejected" })]);
    // Teks ikut tercetak: pembaca layar dan pembaca buta warna tetap tahu.
    expect(html.toLowerCase()).toContain("ditolak");
    expect(html).toContain("aa-row-rejected");
    expect(html).toContain("aa-status-rejected");
  });

  it("tidak ada status yang hanya bergantung pada kelas warna", () => {
    const semua = ["pending_approval", "approved", "executed", "rejected", "verifier_flagged"];
    for (const status of semua) {
      const html = tabel([row({ status })]);
      const teks = html.replace(/<[^>]+>/g, " ").toLowerCase();
      const kata = {
        pending_approval: "menunggu",
        approved: "disetujui",
        executed: "dieksekusi",
        rejected: "ditolak",
        verifier_flagged: "verifikator",
      }[status]!;
      expect(teks, `status ${status} tanpa kata ${kata}`).toContain(kata);
    }
  });

  it("kepadatan sekarang dicatat sebagai anggaran: 10 baris tidak membengkak", () => {
    // Baseline Tahap 0: panel 10 baris = 7.000 karakter markup. Pagar ini
    // memberi ruang 15% untuk perbaikan visual, bukan untuk menumpuk kartu.
    const ukuran = panel(SEPULUH).length;
    expect(ukuran).toBeLessThan(8050);
  });
});

describe("Tahap 1 — kerangka halaman", () => {
  const sumberHalaman = readFileSync(join(__dirname, "..", "app", "page.tsx"), "utf8");
  // Potong hanya blok tab Agent Activity Log, supaya deskripsi tab lain tidak ikut.
  // Jangkar: judul halamannya sendiri (`PAGE_TITLES.agentLog`), bukan nama tab —
  // nama tab muncul juga di daftar tab di atas berkas.
  const jangkar = sumberHalaman.indexOf("title={PAGE_TITLES.agentLog}");
  const blok = sumberHalaman.slice(jangkar - 400, jangkar + 6000);

  it("deskripsi halaman satu baris dan ≤ 90 karakter", () => {
    const cocok = blok.match(/description="([^"]+)"/);
    expect(cocok, "deskripsi PageShell tidak ditemukan").toBeTruthy();
    const teks = cocok![1];
    expect(teks.length).toBeLessThanOrEqual(90);
  });

  it("navigasi bagian maksimum 3 tujuan", () => {
    const bagian = agentLogSections();
    expect(bagian.length).toBeLessThanOrEqual(3);
    // Tujuannya harus cocok dengan jangkar yang benar-benar dipasang di halaman.
    for (const item of bagian) {
      expect(sumberHalaman).toContain(`id={AGENT_LOG_SECTION_IDS.${item.id === "log-pilih" ? "pilih" : item.id === "log-langkah" ? "langkah" : "integritas"}}`);
    }
  });

  it("tiga kelompok bertajuk, dan paragraf penghubung sudah hilang", () => {
    const judul = blok.match(/className="log-section-title"/g) ?? [];
    expect(judul.length).toBe(3);
    expect(blok).not.toContain("agent-log-connector");
  });
});

describe("Tahap 2 — bilah filter", () => {
  const CARI = {
    query: "",
    onQuery: () => {},
    commodity: null as string | null,
    onCommodity: () => {},
    verification: "all" as const,
    onVerification: () => {},
    commodities: [
      { value: "beras", label: "Beras", count: 4 },
      { value: "telur", label: "Telur", count: 2 },
    ],
    counts: { all: 6, verified: 3, unverified: 3 } as never,
    total: 6,
  };

  function cari(over: Partial<Record<string, unknown>> = {}): string {
    const props = { ...CARI, ...over } as unknown as Parameters<typeof ModuleSearch>[0];
    return renderToStaticMarkup(<ModuleSearch {...props} />);
  }

  it("tetap SATU kartu, dengan kalimat penjelas maksimum satu baris", () => {
    const html = cari({ shown: 6 });
    expect(html.match(/class="aa-search"/g) ?? []).toHaveLength(1);
    const catatan = html.match(/class="aa-search-note"[^>]*>([^<]+)</);
    expect(catatan).toBeTruthy();
    expect(catatan![1].trim().length).toBeLessThanOrEqual(80);
    // Penjelas tetap ada (dokumen 06 §4.2), hanya dipendekkan.
    expect(catatan![1].toLowerCase()).toContain("bukan langkah trace");
  });

  it("mencetak ringkasan hasil 'X dari Y' di baris filter", () => {
    const html = cari({ shown: 2, total: 6 });
    expect(html).toContain("aa-search-count");
    expect(html).toContain("2 dari 6 keputusan");
    expect(html).toContain('role="status"');
  });

  it("tanpa prop `shown`, ringkasannya tidak dicetak (pemakai lain tidak berubah)", () => {
    expect(cari()).not.toContain("aa-search-count");
  });

  it("keadaan tidak-ada-hasil menyebut filter yang aktif dan memberi aksi", () => {
    const html = cari({ commodity: "beras", shown: 0 });
    const blokKosong = html.slice(html.indexOf("aa-search-empty"));
    expect(blokKosong).toContain("Tidak ada keputusan yang cocok");
    expect(blokKosong.toLowerCase()).toContain("komoditas beras");
    expect(blokKosong).toContain("Kosongkan filter");
    // Angka total tetap disebut: "0 hasil" telanjang dilarang aturan No Results.
    expect(blokKosong).toContain("6 keputusan tetap ada");
  });

  it("tidak mencetak blok kosong saat masih ada hasil", () => {
    expect(cari({ shown: 2 })).not.toContain("aa-search-empty");
    // Filter tidak aktif + hasil kosong juga bukan "tidak ada hasil": itu data kosong.
    expect(cari({ shown: 0 })).not.toContain("aa-search-empty");
  });
});

describe("Tahap 3 — tabel dan irama kotak", () => {
  const cssBersih = css.replace(/\/\*[\s\S]*?\*\//g, "");
  function aturan(selektor: string): string {
    const mulai = cssBersih.indexOf(`${selektor} {`);
    expect(mulai, `aturan ${selektor} tidak ditemukan`).toBeGreaterThan(-1);
    const buka = cssBersih.indexOf("{", mulai);
    const tutup = cssBersih.indexOf("}", buka);
    return cssBersih.slice(buka + 1, tutup);
  }

  it("tabel punya wadah bergulir sendiri, bukan menggeser halaman", () => {
    expect(tabel([row({})])).toContain("aa-table-scroll");
    const isi = aturan(".aa-table-scroll");
    expect(isi).toContain("overflow: auto");
    // Tanpa tinggi maksimum, `sticky` tidak punya wadah gulir.
    expect(isi).toContain("max-height");
  });

  it("header lengket berlatar opak dan baris setinggi 44 px", () => {
    const th = aturan(".aa-table thead th");
    expect(th).toContain("position: sticky");
    expect(th).toContain("background: var(--surface)");
    expect(aturan(".aa-table tbody tr")).toContain("height: 44px");
  });

  it("kolom di header berurutan: triage dulu, identitas kemudian", () => {
    const html = tabel([row({})]);
    const thead = html
      .slice(html.indexOf("<thead>"), html.indexOf("</thead>"))
      .replace(/<\/?thead>/g, "")
      .replace(/<tr[^>]*>/g, "");
    const judul = thead
      .split("<th")
      .slice(1)
      .map((sel) => sel.slice(sel.indexOf(">") + 1, sel.indexOf("</th>")).replace(/<[^>]*>/g, "").trim())
      .filter((teks) => teks.length > 0);
    expect(judul).toEqual([
      "Status",
      "Tenggat",
      "Verifikasi",
      "Keputusan",
      "Komoditas",
      "Kuantitas",
      "Biaya aman",
      "Aksi",
    ]);
  });

  it("strip tahap mengikuti JUMLAH tahap, bukan angka 9 yang dikunci", () => {
    const strip = aturan(".aa-strip");
    expect(strip).toContain("auto-fit");
    expect(strip).not.toContain("repeat(9");
    // Label pembaca layar juga tidak boleh menyebut angka lama.
    const panelSumber = readFileSync(
      join(__dirname, "..", "components", "AgentPipelinePanel.tsx"),
      "utf8",
    );
    expect(panelSumber).not.toContain("Sembilan tahap");
    expect(panelSumber).toContain("tahap pipeline`}");
  });

  it("irama jarak kotak ditulis sekali untuk semua kotak, bukan per komponen", () => {
    expect(aturan(".agent-log-section .jump-target > * + *")).toContain(
      "margin-top: var(--space-3)",
    );
    expect(aturan(".agent-log-section .jump-target + .jump-target")).toContain(
      "margin-top: var(--space-5)",
    );
  });
});

describe("Tahap 4 — kepala ringkas + chip menyaring langkah", () => {
  const STEPS = [
    { step_name: "DETECT", step_at: "2026-10-27T05:01:00.000Z", tool_called: "detect_signal" },
    { step_name: "VERIFY", step_at: "2026-10-27T05:02:00.000Z", tool_called: "verify_evidence" },
    { step_name: "DECIDE", step_at: "2026-10-27T05:03:00.000Z", tool_called: "decide" },
  ];

  function panelBerlangkah(over: Record<string, unknown> = {}): string {
    const props = {
      role: "sppg_head",
      decisions: SEPULUH,
      total: SEPULUH.length,
      page: 1,
      onPage: () => {},
      selectedId: SEPULUH[0].decision_id,
      onSelect: () => {},
      summary: "10 keputusan",
      steps: STEPS,
      ledger: [],
      overview: null,
      periodLabel: "7 hari",
      now: null,
      loading: false,
      onOpenEvidence: () => {},
      ...over,
    } as unknown as Parameters<typeof AgentActivityPanel>[0];
    return renderToStaticMarkup(<AgentActivityPanel {...props} />);
  }

  it("ringkasan pindah ke kanan kepala panel, diumumkan lewat role=status", () => {
    const html = panelBerlangkah();
    const kepala = html.slice(html.indexOf("<header"), html.indexOf("</header>"));
    expect(kepala).toContain("aa-head-sum");
    expect(kepala).toContain('role="status"');
    expect(kepala).toContain("3 dari 10 tahap punya jejak tercatat");
    // Muncul SEKALI: duplikat di atas strip sudah dibuang.
    expect(html.match(/tahap punya jejak tercatat/g) ?? []).toHaveLength(1);
  });

  it("kepala ditulis sebagai satu baris: label + kalimat peran sebaris, elipsis", () => {
    const bersih = css.replace(/\/\*[\s\S]*?\*\//g, "");
    const main = bersih.slice(bersih.indexOf(".aa-head-main {"));
    const isi = main.slice(main.indexOf("{") + 1, main.indexOf("}"));
    expect(isi).toContain("display: flex");
    expect(isi).toContain("align-items: baseline");
    const sub = bersih.slice(bersih.indexOf(".aa-head-main p {"));
    expect(sub.slice(0, sub.indexOf("}"))).toContain("white-space: nowrap");
    expect(sub.slice(0, sub.indexOf("}"))).toContain("text-overflow: ellipsis");
  });

  it("chip membawa aria-pressed sesuai saringan yang aktif", () => {
    const tanpa = renderToStaticMarkup(
      <AgentPipelinePanel decisionId="d-1" steps={STEPS} ledger={[]} stageFilter={null} />,
    );
    expect(tanpa).not.toContain('aria-pressed="true"');
    const dengan = renderToStaticMarkup(
      <AgentPipelinePanel decisionId="d-1" steps={STEPS} ledger={[]} stageFilter="VERIFY" />,
    );
    expect(dengan.match(/aria-pressed="true"/g) ?? []).toHaveLength(1);
    expect(dengan).toContain("Hapus saringan tahap VERIFY");
  });

  it("langkah rinci disaring ke satu tahap, dengan jumlah yang menyebut totalnya", () => {
    const semua = renderToStaticMarkup(<AgentTraceViewer steps={STEPS} decisionId="d-1" />);
    expect(semua.match(/class="trace-step /g) ?? []).toHaveLength(3);
    expect(semua).not.toContain("trace-filter");

    const saring = renderToStaticMarkup(
      <AgentTraceViewer
        steps={STEPS}
        decisionId="d-1"
        stageFilter="VERIFY"
        onClearStageFilter={() => {}}
      />,
    );
    expect(saring.match(/class="trace-step /g) ?? []).toHaveLength(1);
    expect(saring).toContain("Saringan tahap VERIFY: 1 dari 3 langkah.");
    expect(saring).toContain('role="status"');
    expect(saring).toContain("Tampilkan semua langkah");
  });

  it("tahap tanpa langkah: menyebut namanya, tidak mencetak daftar kosong", () => {
    const html = renderToStaticMarkup(
      <AgentTraceViewer steps={STEPS} decisionId="d-1" stageFilter="ACT" />,
    );
    expect(html).toContain("Tidak ada langkah tahap ACT di jejak ini (3 langkah tercatat).");
    expect(html).not.toContain("trace-timeline");
  });

  it("halaman menyambungkan satu state saringan ke chip dan ke daftar langkah", () => {
    const halaman = readFileSync(join(__dirname, "..", "app", "page.tsx"), "utf8");
    expect(halaman).toContain("const [logStage, setLogStage]");
    expect(halaman).toContain("stageFilter={logStage}");
    expect(halaman).toContain("onStageFilter={setLogStage}");
    expect(halaman).toContain("onClearStageFilter={() => setLogStage(null)}");
    // Keputusan berganti = saringan lama tidak berlaku.
    expect(halaman).toContain("setLogStage(null);");
  });

  it("jarak antar shape diberi ruang (permintaan pemilik 29 Okt 2026)", () => {
    const bersih = css.replace(/\/\*[\s\S]*?\*\//g, "");
    const ambil = (sel: string) => {
      const i = bersih.indexOf(`${sel} {`);
      expect(i, `${sel} tidak ada`).toBeGreaterThan(-1);
      return bersih.slice(bersih.indexOf("{", i) + 1, bersih.indexOf("}", i));
    };
    // Wadah panel sebelumnya tanpa aturan → kotak saling menempel.
    expect(ambil(".aa-pipeline")).toContain("gap: var(--space-3)");
    expect(ambil(".aa-strip")).toContain("gap: var(--space-3)");
    expect(ambil(".aa-stage")).toContain("padding: 8px 10px");
  });
});

describe("Tahap 5 — langkah rinci jadi baris ringkas", () => {
  const LANGKAH = PIPELINE_STAGES.map((t, i) => ({
    step_name: t.code,
    step_at: `2026-10-27T05:${String(i + 1).padStart(2, "0")}:00.000Z`,
    tool_called: "evaluate_safety",
    output_summary: { summary: `Putusan ${t.code} untuk 780 kg; status menunggu.` },
  }));

  const tampil = (steps: unknown[], over: Record<string, unknown> = {}) => {
    const props = { steps, decisionId: "d-1", ...over } as unknown as Parameters<
      typeof AgentTraceViewer
    >[0];
    return renderToStaticMarkup(<AgentTraceViewer {...props} />);
  };

  it("tiap langkah satu baris yang BELUM terbuka (details tanpa open)", () => {
    const html = tampil(LANGKAH);
    const kepala = html.match(/<details class="trace-step step-[A-Z]+" data-state="[a-z]+">/g) ?? [];
    expect(kepala).toHaveLength(LANGKAH.length);
    expect(html).not.toMatch(/<details[^>]*\sopen/);
    // Isi langkah tetap ADA di markup — hanya tidak tampil sampai dibuka.
    expect(html.match(/class="trace-step-body"/g) ?? []).toHaveLength(LANGKAH.length);
  });

  it("judul baris memuat kode tahap, jam, dan chevron; isi memuat alat + kalimat", () => {
    const html = tampil(LANGKAH);
    expect(html).toContain('<summary class="trace-step-head">');
    expect(html).toContain("trace-chevron");
    expect(html).toContain("DETECT");
    expect(html).toContain("trace-summary");
    expect(html).toContain("Data mentah");
  });

  it("langkah tanpa kalimat ringkas tidak lagi mencetak JSON telanjang", () => {
    const html = tampil([{ step_name: "DETECT", step_at: "2026-10-27T05:01:00.000Z", tool_called: "x" }]);
    // Varian lama: <pre class="trace-output"> langsung di dalam <li>.
    expect(html).not.toMatch(/<\/div>\s*<pre class="trace-output"/);
    expect(html).not.toContain("trace-summary");
    expect(html).toContain('class="trace-raw"');
    expect(html).toContain("<summary>Data mentah</summary>");
  });

  it("CSS: penanda bawaan dibuang, ada chevron berputar + fokus terlihat", () => {
    const bersih = css.replace(/\/\*[\s\S]*?\*\//g, "");
    const ambil = (sel: string) => {
      const i = bersih.indexOf(`${sel} {`);
      expect(i, `${sel} tidak ada`).toBeGreaterThan(-1);
      return bersih.slice(bersih.indexOf("{", i) + 1, bersih.indexOf("}", i));
    };
    expect(ambil(".agent-console .trace-step > summary")).toContain("list-style: none");
    expect(bersih).toContain("summary::-webkit-details-marker");
    expect(bersih).toContain(".trace-step[open] .trace-chevron");
    expect(bersih).toContain("prefers-reduced-motion");
    expect(ambil(".trace-step-body")).toContain("flex-direction: column");
  });

  it("roster berdiri sendiri; supervisor jadi KOTAK abu-abu di kepala kelompok", () => {
    const bersih = css.replace(/\/\*[\s\S]*?\*\//g, "");
    // Kartu besar berjudul sendiri tetap tidak dipakai.
    expect(bersih).not.toContain(".aa-supervisor {");
    const i = bersih.indexOf(".log-section-head {");
    expect(i).toBeGreaterThan(-1);
    const isi = bersih.slice(bersih.indexOf("{", i) + 1, bersih.indexOf("}", i));
    expect(isi).toContain("justify-content: space-between");

    // Bentuk kotak dikembalikan, warnanya netral (abu-abu).
    const j = bersih.indexOf(".aa-supervisor-line {");
    expect(j).toBeGreaterThan(-1);
    const kotak = bersih.slice(bersih.indexOf("{", j) + 1, bersih.indexOf("}", j));
    expect(kotak).toContain("background: var(--neutral-bg)");
    expect(kotak).toContain("border: 1px solid var(--neutral-border)");
    expect(kotak).toContain("border-radius");
    expect(kotak).toContain("padding");
    // Teks di dalam kotak tidak boleh ikut hijau/amber dari `.aa-tone-*`.
    expect(bersih).toContain(".log-section-head .aa-supervisor-line strong,");
    const k = bersih.indexOf(".log-section-head .aa-supervisor-line,");
    expect(k).toBeGreaterThan(-1);
    const override = bersih.slice(bersih.indexOf("{", k) + 1, bersih.indexOf("}", k));
    expect(override).toContain("color: var(--neutral-ink)");

    const halaman = readFileSync(join(__dirname, "..", "app", "page.tsx"), "utf8");
    const kepala = halaman.slice(halaman.indexOf('className="log-section-head"'));
    const potong = kepala.slice(0, kepala.indexOf("</div>"));
    expect(potong).toContain("Langkah &amp; model");
    expect(potong).toContain("<SupervisorStatusLine");

    // Roster tidak lagi dibungkus strip dua kolom.
    expect(halaman).not.toContain("aa-model-strip");
    expect(halaman).toContain("<AgentRoster />");

    // Kotak punya nama terlihat + label pembaca layar, tanpa judul <h3>.
    const komponen = readFileSync(
      join(__dirname, "..", "components", "SupervisorStatusLine.tsx"),
      "utf8",
    );
    expect(komponen).toContain('className="aa-sr"');
    expect(komponen).toContain('className="aa-supervisor-label">Supervisor<');
    expect(komponen).not.toContain("<h3");
    expect(komponen).not.toContain('className="aa-supervisor"');
  });
});

describe("Tahap 6 — integritas satu baris + tanya-jawab paling bawah", () => {
  const SRC = readFileSync(
    join(__dirname, "..", "components", "IntegrityPanel.tsx"),
    "utf8",
  );
  const angka = (n: number) => new Intl.NumberFormat("id-ID").format(n);

  const rantaiValid = { valid: true, blocks: 3128, head: "abc", orphan_blocks: 0 } as never;
  const dossierSah = {
    decision_id: "d-1",
    signature: { state: "signed", algorithm: "ECDSA-secp256k1" },
    verify: true,
  } as never;
  const dossierUnsigned = {
    decision_id: "d-1",
    signature: { state: "unsigned", reason: "kunci tidak diset" },
    verify: null,
  } as never;
  const dossierSegelGagal = {
    decision_id: "d-1",
    signature: { state: "signed", algorithm: "ECDSA-secp256k1" },
    verify: false,
  } as never;

  it("SAH hanya bila rantai valid, tidak ada blok yatim, dan segel cocok", () => {
    const r = ringkasIntegritas(rantaiValid, dossierSah, "d-1");
    expect(r.tone).toBe("ok");
    expect(r.label).toBe("SAH");
    expect(r.detail).toContain(`${angka(3128)} blok`);
    expect(r.detail).toContain(`0 blok yatim`);
    expect(r.detail).toContain("dossier tersegel & terverifikasi");
  });

  it("blok yatim → PERINGATAN, jumlahnya disebut", () => {
    const r = ringkasIntegritas({ ...(rantaiValid as object), orphan_blocks: 3 } as never, dossierSah, "d-1");
    expect(r.tone).toBe("warn");
    expect(r.label).toBe("PERINGATAN");
    expect(r.detail).toContain("3 blok yatim");
  });

  it("rantai putus, checkpoint berbeda, atau segel gagal → GAGAL", () => {
    expect(ringkasIntegritas({ ...(rantaiValid as object), valid: false } as never, dossierSah, "d-1").tone).toBe("danger");
    expect(
      ringkasIntegritas(
        { ...(rantaiValid as object), anchor: { match: false } } as never,
        dossierSah,
        "d-1",
      ).tone,
    ).toBe("danger");
    const segel = ringkasIntegritas(rantaiValid, dossierSegelGagal, "d-1");
    expect(segel.tone).toBe("danger");
    expect(segel.label).toBe("GAGAL");
  });

  it("belum ditandatangani → PERINGATAN; belum dimuat → 'Memeriksa…'", () => {
    const unsigned = ringkasIntegritas(rantaiValid, dossierUnsigned, "d-1");
    expect(unsigned.tone).toBe("warn");
    expect(unsigned.detail).toContain("dossier belum ditandatangani");
    const memuat = ringkasIntegritas(null, null, "d-1");
    expect(memuat.tone).toBe("plain");
    expect(memuat.label).toBe("Memeriksa…");
  });

  it("panel mencetak satu baris status, rincian pindah ke lipatan", () => {
    expect(SRC).toContain('data-testid="integrity-summary"');
    expect(SRC).toContain('role="status"');
    expect(SRC).toContain('className="integrity-fold"');
    expect(SRC).toContain("Buka rincian integritas");
    // Kalimat teknis lama dibuang (bukan disembunyikan di balik lipatan).
    expect(SRC).not.toContain("integrity-sub");
    // Rincian lama tetap ada di dalam lipatan.
    expect(SRC).toContain('data-testid="ledger-status"');
    expect(SRC).toContain('data-testid="dossier-status"');
    expect(SRC).toContain('data-testid="btn-verify-ledger"');
  });

  it("tanya-jawab dipindah ke PALING BAWAH, setelah integritas", () => {
    const halaman = readFileSync(join(__dirname, "..", "app", "page.tsx"), "utf8");
    const posisiIntegritas = halaman.indexOf("<IntegrityPanel");
    const posisiTanya = halaman.indexOf("<SupervisorAskPanel");
    expect(posisiIntegritas).toBeGreaterThan(-1);
    expect(posisiTanya).toBeGreaterThan(posisiIntegritas);
    expect(halaman).toContain('className="agent-log-ask"');
    // Bukan lagi di kelompok pemilih keputusan: blok tanya-jawab kini punya
    // pembungkus sendiri setelah kelompok integritas.
    expect(halaman.indexOf("agent-log-ask")).toBeLessThan(posisiTanya);
  });

  it("CSS lipatan: penanda bawaan dibuang, fokus terlihat, tanya-jawab diberi jarak", () => {
    const bersih = css.replace(/\/\*[\s\S]*?\*\//g, "");
    const i = bersih.indexOf(".integrity-fold > summary {");
    expect(i).toBeGreaterThan(-1);
    const isi = bersih.slice(bersih.indexOf("{", i) + 1, bersih.indexOf("}", i));
    expect(isi).toContain("list-style: none");
    expect(isi).toContain("cursor: pointer");
    expect(bersih).toContain(".integrity-fold > summary::-webkit-details-marker");
    expect(bersih).toContain(".integrity-fold > summary:focus-visible");
    const j = bersih.indexOf(".agent-log-ask {");
    expect(j).toBeGreaterThan(-1);
    expect(bersih.slice(bersih.indexOf("{", j) + 1, bersih.indexOf("}", j))).toContain(
      "margin-top: var(--space-5)",
    );
  });
});

describe("catatan baseline (dokumentasi, bukan asersi)", () => {
  it("selektor CSS halaman ini tercatat 150+ dan akan menyusut", () => {
    const jumlahSelektor = (css.match(/^\.[a-z]/gm) || []).length;
    expect(jumlahSelektor).toBeGreaterThan(100);
  });
});
