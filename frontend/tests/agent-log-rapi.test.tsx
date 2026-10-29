// Kontrak kerapian halaman Agent Activity Log (29 Okt 2026).
//
// Permintaan pemilik: "design lagi halaman Agent Activity Log" dengan konsep
// dari `06-agent-log.md`. Dokumen itu sudah dipasang (tabel keputusan di atas,
// strip sembilan tahap, banner kejujuran, penanda waktu) — yang tersisa adalah
// sisa ketidakseragaman yang membuat halaman terasa belum didesain:
//
//   1. Dua judul besar bersaing: h1 20 px "Agent Activity Log", lalu h2 18 px
//      "Agent Activity" tepat di bawahnya.
//   2. Dua sub-judul 16 px ("Status Model Agent", "Integritas Bukti") di antara
//      lima sub-judul 14 px — satu halaman, dua bahasa label.
//   3. Filter terpecah: kartu pencarian 158 px + baris periode 28 px terpisah,
//      padahal keduanya satu pekerjaan (menyaring daftar keputusan).
//   4. Panel status model memakai margin 16 px + padding 12 px + judul sendiri
//      (92 px) untuk tiga chip 32 px.
//
// Angka sebelum–sesudah: `_qa/agent-log-rapi/`. Tes ini menjaga BENTUKNYA.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import DecisionAuditTable from "../components/DecisionAuditTable";
import ModuleSearch from "../components/ModuleSearch";
import PeriodPicker from "../components/PeriodPicker";

const css = readFileSync(join(__dirname, "..", "app", "agent-activity.css"), "utf8");
const page = readFileSync(join(__dirname, "..", "app", "page.tsx"), "utf8");
const panel = readFileSync(
  join(__dirname, "..", "components", "AgentActivityPanel.tsx"),
  "utf8",
);
const periodSrc = readFileSync(
  join(__dirname, "..", "components", "PeriodPicker.tsx"),
  "utf8",
);

/** Blok deklarasi yang dimulai dari kemunculan PERTAMA `selector`. */
function blok(selector: string): string {
  const i = css.indexOf(selector);
  if (i < 0) throw new Error(`selektor tidak ditemukan di agent-activity.css: ${selector}`);
  const buka = css.indexOf("{", i);
  const tutup = css.indexOf("}", buka);
  if (buka < 0 || tutup < 0) throw new Error(`blok tidak lengkap: ${selector}`);
  return css.slice(buka + 1, tutup);
}

const CARI = {
  query: "",
  onQuery: () => {},
  commodity: null,
  onCommodity: () => {},
  verification: "all" as const,
  onVerification: () => {},
  commodities: [{ value: "telur", label: "telur", count: 8 }],
  counts: { all: 14, terverifikasi: 2, menunggu: 6, ditolak: 3 },
  total: 14,
};

describe("kedudukan judul — satu judul besar per layar", () => {
  it("label modul memakai skala sub-judul seksi (14 px/600), bukan 18 px", () => {
    const b = blok(".aa-kicker");
    expect(b).toContain("font-size: var(--fs-3)");
    expect(b).toContain("font-weight: 600");
    expect(b).not.toContain("var(--fs-5)");
  });

  it("status model & integritas turun ke bahasa label yang sama", () => {
    const b = blok(".agent-log-section .integrity-panel h3");
    expect(b).toContain("font-size: var(--fs-3)");
    expect(b).toContain("font-weight: 600");
  });

  it("aturan itu DIBATASI ke halaman Agent Log (komponennya dipakai halaman lain)", () => {
    // Decision & Evidence juga merender IntegrityPanel; gaya dasarnya tidak boleh
    // ikut berubah hanya karena halaman ini dirapikan.
    expect(css).toMatch(/\.agent-log-section \.integrity-panel h3/);
    expect(css).not.toMatch(/(?:^|\n)\.integrity-panel h3\s*\{[^}]*var\(--fs-3\)/);
  });

  it("markup: h2 modul membawa kelas label", () => {
    expect(panel).toContain('<h2 className="aa-kicker">Agent Activity</h2>');
    expect(panel).not.toMatch(/<h2>Agent Activity<\/h2>/);
  });
});

describe("satu bilah filter — periode sebaris dengan field", () => {
  it("pemilih periode masuk ke baris field, sebelum chip status", () => {
    const html = renderToStaticMarkup(
      <ModuleSearch
        {...CARI}
        period={<PeriodPicker value="24h" onChange={() => undefined} />}
      />,
    );
    const baris = html.indexOf("aa-search-row");
    const periode = html.indexOf("aa-search-field-periode");
    const chips = html.indexOf("aa-search-filters");
    expect(baris).toBeGreaterThan(-1);
    expect(periode).toBeGreaterThan(baris);
    expect(periode).toBeLessThan(chips);
    // Isi periodenya benar-benar di dalam field, bukan sekadar kelas kosong.
    expect(html.slice(periode, chips)).toContain("kpi-period-pill");
  });

  it("tanpa prop `period`, kartu pencarian tetap sah untuk pemakai lain", () => {
    const html = renderToStaticMarkup(<ModuleSearch {...CARI} />);
    expect(html).not.toContain("aa-search-field-periode");
    expect(html).toContain("aa-search-filters");
  });

  it("halaman hanya merender SATU pemilih periode, di dalam pencarian", () => {
    expect(page.match(/<PeriodPicker/g) ?? []).toHaveLength(1);
    expect(page).toMatch(/<ModuleSearch[\s\S]{0,1400}period=\{/);
  });

  it("margin bawaan `.kpi-period` dinolkan supaya barisnya setinggi input", () => {
    expect(blok(".aa-search-field-periode .kpi-period")).toContain("margin: 0");
  });

  it("petunjuk periode kosong tidak memakan satu baris flex", () => {
    expect(blok(".aa-search-field-periode .feed-period-hint:empty")).toContain("display: none");
  });

  it("petunjuk periode hanya dicetak bila menambah arti", () => {
    expect(periodSrc).toContain("feedWindowHintBilaBerbeda");
    expect(periodSrc).not.toMatch(/feedWindowHint\(value\)/);
  });
});

describe("status model — tinggi dari isinya, bukan dari kotaknya", () => {
  it("judul & chip duduk sebaris dan panelnya kehilangan margin bawaan", () => {
    const pola = /\.agent-log-section \.provider-panel\s*\{([^}]*)\}/g;
    const semua: string[] = [];
    let m: RegExpExecArray | null;
    while ((m = pola.exec(css)) !== null) semua.push(m[1]);
    expect(semua.length).toBeGreaterThan(0);
    const gabung = semua.join("\n");
    expect(gabung).toContain("display: flex");
    expect(gabung).toContain("margin: 0");
    expect(gabung).toContain("align-items: center");
  });
});

describe("tabel keputusan memakai bahasa tabel halaman lain", () => {
  const baris = (i: number) => ({
    decision_id: `d${String(i).padStart(7, "0")}-aaaa`,
    decision_type: "supplier_procurement",
    status: i % 2 === 0 ? "pending_approval" : "rejected",
    quantity_kg: 600,
    safe_delivered_cost: 16519940,
    expires_at: "2026-10-29T05:36:00Z",
    commodity_name: "telur",
    target_location_name: "Bandung",
  });

  it("13 baris → 10 baris tampil + pager '1–10 dari 13'", () => {
    const rows = Array.from({ length: 13 }, (_, i) => baris(i));
    const html = renderToStaticMarkup(
      <DecisionAuditTable
        rows={rows}
        total={rows.length}
        page={1}
        onPage={() => undefined}
        selectedId={null}
        onSelect={() => undefined}
        summary="13 dari 13 keputusan"
      />,
    );
    expect(html.match(/<tr[ >]/g) ?? []).toHaveLength(11); // 1 header + 10 baris
    expect(html).toContain("1–10 dari 13");
    expect(html).toContain('aria-label="Halaman daftar keputusan"');
  });

  it("memakai table.location-table di dalam .board-table-wrap", () => {
    const html = renderToStaticMarkup(
      <DecisionAuditTable
        rows={[baris(0)]}
        total={1}
        page={1}
        onPage={() => undefined}
        selectedId={null}
        onSelect={() => undefined}
        summary="1 dari 1 keputusan"
      />,
    );
    expect(html).toContain('class="location-table aa-table"');
    expect(html).toContain("board-table-wrap aa-table-scroll");
    // Kolom angka memakai konvensi `.num` (rata kanan + huruf data), bukan kelas sendiri.
    expect(html).toContain('class="num"');
    expect(html).not.toContain("aa-col-num");
  });

  it("status tidak pernah tercetak sebagai enum Inggris di kolom Status", () => {
    const html = renderToStaticMarkup(
      <DecisionAuditTable
        rows={[
          { ...baris(0), status: "verifier_flagged" },
          { ...baris(1), status: "proposed" },
          { ...baris(2), status: "review_only" },
        ]}
        total={3}
        page={1}
        onPage={() => undefined}
        selectedId={null}
        onSelect={() => undefined}
        summary="3 dari 3 keputusan"
      />,
    );
    expect(html).toContain("Ditandai verifikator");
    expect(html).toContain("Diusulkan");
    expect(html).toContain("Temuan tinjauan");
    // Kelas CSS memang memuat kode statusnya; yang diuji adalah TEKS yang
    // tercetak ke pengguna.
    expect(html).not.toContain(">verifier_flagged<");
    expect(html).not.toContain(">review_only<");
    expect(html).not.toContain(">proposed<");
  });

  it("baris terpilih bertanda aria-current + tombol 'Dipilih'", () => {
    const rows = [baris(0), baris(1)];
    const html = renderToStaticMarkup(
      <DecisionAuditTable
        rows={rows}
        total={2}
        page={1}
        onPage={() => undefined}
        selectedId={rows[1].decision_id}
        onSelect={() => undefined}
        summary="2 dari 2 keputusan"
      />,
    );
    expect(html).toContain('aria-current="true"');
    expect(html).toContain(">Dipilih<");
  });

  it("berkas CSS tidak lagi menimpa th/td milik .location-table", () => {
    expect(css).not.toMatch(/\.aa-table (?:th|td)[,\s{]/);
    expect(css).not.toContain(".aa-pager");
    expect(css).not.toContain(".aa-row-btn");
  });
});

describe("pemilih keputusan di kepala halaman dihapus", () => {
  it("halaman tidak lagi merender DecisionPicker", () => {
    expect(page).not.toContain("DecisionPicker");
    expect(page).not.toContain("pilih-keputusan-log");
  });

  it("halaman digeser ke halaman tabel yang memuat keputusan terpilih", () => {
    expect(page).toMatch(/findIndex\([\s\S]{0,80}decision_id === selectedId/);
    expect(page).toContain("DECISION_PAGE_SIZE");
  });
});
