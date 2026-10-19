// Kontrak desain ulang "Decision & Evidence" — 20 Okt 2026.
//
// Permintaan pemilik: "redesign halaman ini, buat sebagus dan semaksimal
// mungkin". Bentuk barunya ada di `app/evidence-dossier.css` (lapisan yang
// diimpor TERAKHIR), jadi yang dijaga di sini dua hal:
//
//   1. CSS-nya sendiri: hierarki (label bagian kapital, judul keputusan dan
//      angka kunci satu tingkat di atas teks), stepper bersambung, fakta
//      governance rata kanan, nav menempel, dan daftar PO yang jadi tabel.
//      Kerusakan tata letak tidak pernah terlihat di tes render (jsdom tidak
//      punya layout), jadi aturannya dikunci di sini.
//   2. Strukturnya: empat panel berjudul (persetujuan, bukti, jejak) dengan
//      id yang dipakai navigasi, tanpa id ganda.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import DecisionEvidence from "../components/DecisionEvidence";

const css = readFileSync(join(__dirname, "..", "app", "evidence-dossier.css"), "utf8");
const layout = readFileSync(join(__dirname, "..", "app", "layout.tsx"), "utf8");

function blok(selector: string): string {
  // Escape metakarakter regex: selektor CSS memuat [ ] " + > yang bukan pola.
  const aman = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const cocok = new RegExp(`^${aman}\\s*\\{([^}]*)\\}`, "ms").exec(css);
  if (!cocok) throw new Error(`blok CSS tidak ditemukan: ${selector}`);
  return cocok[1];
}

describe("dossier keputusan — berkas lapisan", () => {
  it("diimpor sesudah globals, theme-ext, dan map-console", () => {
    const dossier = layout.indexOf("evidence-dossier.css");
    expect(dossier).toBeGreaterThan(layout.indexOf("./globals.css"));
    expect(dossier).toBeGreaterThan(layout.indexOf("./theme-ext.css"));
    expect(dossier).toBeGreaterThan(layout.indexOf("./map-console.css"));
  });

  it("tidak memakai !important (menang karena urutan, bukan paksaan)", () => {
    // Komentar boleh MENYEBUT !important (alasannya), jadi deklarasinya yang
    // diuji: buang komentar dulu, baru cari "!important".
    const tanpaKomentar = css.replace(/\/\*[\s\S]*?\*\//g, "");
    expect(tanpaKomentar).not.toContain("!important");
  });
});

describe("dossier keputusan — satu panel per bagian", () => {
  it("panel bagian punya satu bingkai; kartu di dalamnya kehilangan bingkainya", () => {
    const panel = blok(".evidence-block");
    expect(panel).toContain("border: 1px solid var(--line)");
    expect(panel).toContain("border-radius: var(--radius)");
    const kartu = blok(".evidence-block > .card");
    expect(kartu).toContain("border: 0");
    expect(kartu).toContain("padding: 0");
    expect(kartu).toContain("background: transparent");
  });

  it("kartu kedua dalam satu panel dipisah garis rambut, bukan bingkai baru", () => {
    const pisah = blok(".evidence-block > .card + .card");
    expect(pisah).toContain("border-top: 1px solid var(--line)");
  });

  it("judul bagian = label kapital + garis rambut, judul keputusan dikecualikan", () => {
    expect(css).toMatch(/\.card > h2:not\(\.evidence-hero-title\)/);
    expect(css).toMatch(/\.evidence-block-title::after[\s\S]{0,160}height: 1px/);
    // Kepala governance memakai selector sendiri karena h2-nya bukan anak
    // langsung kartu (ada pembungkus .evidence-decide-head).
    expect(css).toMatch(/\.evidence-page \.evidence-decide-head > h2,/);
  });
});

describe("dossier keputusan — hierarki teks", () => {
  it("judul keputusan satu tingkat di atas judul kartu (--fs-7)", () => {
    const judul = blok(".evidence-page .card > h2.evidence-hero-title");
    expect(judul).toContain("font-size: var(--fs-7)");
    expect(judul).toContain("line-height: 1.2");
  });

  it("angka kunci memakai tangga metrik + angka tabular", () => {
    const angka = blok(".evidence-metric dd");
    expect(angka).toContain("font-size: var(--fs-7)");
    expect(angka).toContain("font-variant-numeric: tabular-nums");
    expect(angka).toContain("font-weight: 600");
    expect(blok(".evidence-metric dt")).toContain("text-transform: uppercase");
  });
});

describe("dossier keputusan — jalur persetujuan sebagai stepper", () => {
  it("empat langkah sejajar dengan garis sambung di belakang penanda", () => {
    expect(blok(".evidence-route-steps")).toContain("repeat(4, minmax(0, 1fr))");
    const garis = blok(".evidence-route-step::before");
    expect(garis).toContain("position: absolute");
    expect(garis).toContain("background: var(--line)");
    // Penanda = bulatan; langkah selesai memakai tinta aman.
    const tanda = blok(".evidence-route-mark");
    expect(tanda).toContain("border-radius: 50%");
    expect(tanda).toContain("width: 24px");
    expect(blok(".evidence-route-done .evidence-route-mark")).toContain("var(--ok-ink)");
    expect(blok(".evidence-route-current .evidence-route-mark")).toContain("var(--accent-strong)");
  });

  it("di layar sempit stepper jadi dua kolom tanpa garis sambung", () => {
    const media = css.slice(css.indexOf("@media (max-width: 680px)"));
    expect(media.slice(0, 400)).toMatch(/\.evidence-route-steps \{ grid-template-columns: repeat\(2/);
    expect(media.slice(0, 400)).toContain(".evidence-route-step::before { content: none; }");
  });
});

describe("dossier keputusan — fakta & navigasi", () => {
  it("fakta governance sejajar dengan kartu bukti: label kiri, nilai rata kanan", () => {
    const baris = blok(".evidence-decide .fact-row");
    expect(baris).toContain("minmax(0, 34%)");
    expect(blok(".evidence-decide .fact-row dd")).toContain("text-align: right");
  });

  it("navigasi bagian menempel dan menandai bagian aktif", () => {
    const nav = blok(".evidence-jump");
    expect(nav).toContain("position: sticky");
    expect(nav).toContain("top: 72px");
    expect(blok('.evidence-jump-link[aria-current="true"]')).toContain("var(--accent-soft)");
    // Jangkar tidak mendarat di balik top bar + nav menempel.
    expect(css).toMatch(/#ringkasan,[\s\S]{0,120}scroll-margin-top: 132px/);
  });
});

describe("dossier keputusan — daftar purchase order jadi tabel", () => {
  it("satu bingkai untuk daftar, garis rambut antar-baris", () => {
    expect(blok(".po-list")).toContain("gap: 0");
    expect(blok(".po-list")).toContain("border: 1px solid var(--line)");
    const baris = blok(".po-row");
    expect(baris).toContain("grid-template-areas");
    expect(baris).toContain("padding: 9px 14px");
    expect(blok(".po-row + .po-row")).toContain("border-top: 1px solid var(--line)");
  });

  it("kembali menumpuk di layar sempit", () => {
    const media = css.slice(css.indexOf("@media (max-width: 899px)"));
    expect(media.slice(0, 500)).toMatch(/\.po-row \{[\s\S]{0,200}grid-template-columns: minmax\(0, 1fr\)/);
  });
});

describe("dossier keputusan — supplier governance tidak bocor ke tab lain", () => {
  it("aturan panel pemasok dibatasi pada halaman Decision & Evidence", () => {
    const aturan = Array.from(
      css.matchAll(/^([^\n{]*aria-label="Supplier exclusion"[^\n{]*)\{/gm),
      (m) => m[1].trim(),
    );
    expect(aturan.length).toBeGreaterThan(0);
    aturan.forEach((selector) => expect(selector.startsWith(".evidence-page ")).toBe(true));
  });
});

// ── Struktur DOM ────────────────────────────────────────────────────────────
const NOW = new Date("2026-10-11T02:30:00Z");
const SUMMARY = {
  decision_id: "d1",
  status: "pending_approval",
  iteration: 1,
  commodity: "telur",
  quantity_kg: 600,
  safe_delivered_cost: 16206000,
  cost_breakdown: { purchase: "15720000", logistics: "486000" },
  safety: { worst_status: "pass", blocked: false, batches_checked: 1 },
  supplier: { id: "s1", name: "Supplier A Cianjur", reliability_score: 0.8 },
  execution_target: "MOCK",
  approval_requirement: { min_approvals: 2, requirement: "2 dari 2" },
  approvals: [{ approver: "a1", role: "sppg_head" }],
};
const SELECTED = {
  decision_id: "d1",
  decision_type: "regional_balance",
  status: "pending_approval",
  quantity_kg: 600,
  safe_delivered_cost: 16206000,
  created_at: "2026-10-07T02:16:47Z",
  expires_at: "2026-10-11T02:16:47.973521+00:00",
};

function render() {
  return renderToStaticMarkup(
    <DecisionEvidence
      decisions={[{ decision_id: "d1", decision_type: "regional_balance", status: "pending_approval" }] as any}
      selected={SELECTED}
      selectedId="d1"
      onSelect={() => {}}
      chain={[]}
      summary={SUMMARY}
      supplierContext={null}
      role="sppg_head"
      token="t"
      now={NOW}
    />
  );
}

describe("dossier keputusan — struktur", () => {
  it("keputusan, persetujuan, bukti, dan jejak jadi panel ber-id", () => {
    const html = render();
    expect(html).toContain('class="card evidence-hero" id="ringkasan"');
    expect(html).toMatch(/<section class="evidence-block" id="rute">/);
    expect(html).toMatch(/<section class="evidence-block" id="bukti">/);
    expect(html).toContain('class="evidence-block-title">Bukti</h2>');
    expect(html).toMatch(/<section class="evidence-block evidence-bottom" id="jejak">/);
  });

  it("tidak ada id ganda (navigasi menunjuk satu sasaran)", () => {
    const html = render();
    for (const id of ["ringkasan", "rute", "zona-keputusan", "bukti", "jejak"]) {
      expect((html.match(new RegExp(`id="${id}"`, "g")) ?? []).length).toBe(1);
    }
  });

  it("kartu kepala membawa statusnya sendiri untuk nada garis atas", () => {
    expect(render()).toContain('data-status="pending_approval"');
  });

  it("navigasi menandai bagian awal sebagai posisi sekarang", () => {
    const html = render();
    expect(html).toMatch(/aria-current="true"[^>]*>Ringkasan</);
    expect((html.match(/aria-current="true"/g) ?? []).length).toBe(1);
  });
});
