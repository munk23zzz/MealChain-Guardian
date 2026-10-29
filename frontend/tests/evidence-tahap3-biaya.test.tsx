// TAHAP 3 redesign Decision & Evidence (29 Okt 2026): blok BUKTI BIAYA sebagai
// dua tabel — yang ditagihkan (PO) dan yang analitis (SDC).
//
// Kontrak lama (PO vs SDC terpisah, referensi pasar = pembanding bahan,
// `null` ≠ Rp 0) tetap dijaga oleh `decision-evidence-cost-block.test.tsx` yang
// dihidupkan kembali di tahap ini. Berkas ini memaku BENTUK tabelnya.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import DecisionCostEvidence from "../components/DecisionCostEvidence";

const css = readFileSync(join(__dirname, "../app/evidence-dossier.css"), "utf8");

const COST = {
  purchase_total: "5700000.00",
  transport_total: "34200.00",
  handling_total: "150000.00",
  invoice_total: "5884200.00",
  invoice_unit_price: "29421.00",
  expected_loss: "900000.00",
  freshness_risk: "250000.00",
  safety_penalty: "400000.00",
  sdc_total: "7434200.00",
  sdc_unit_price: "37171.00",
  risk_method: { kind: "simulated_policy" as const, source: "s", version: "v1", period: null, baseline: null },
};

const PASAR = { source: "pihps_reference", price_per_kg: 31000, recorded_at: "2026-10-10T00:00:00+00:00" };

// `over` sengaja longgar: tes juga menyuntik nilai `null` untuk memastikan
// komponen menulis "tidak tercatat", bukan Rp 0.
function html(over: Record<string, unknown> | null = {}, market: typeof PASAR | null = PASAR) {
  return renderToStaticMarkup(
    <DecisionCostEvidence
      cost={(over === null ? null : { ...COST, ...over }) as never}
      market={market as never}
    />
  );
}

function blok(out: string, kunci: "po" | "sdc"): string {
  const i = out.indexOf(`data-block="${kunci}"`);
  if (i < 0) return "";
  const j = kunci === "po" ? out.indexOf('data-block="sdc"', i) : out.length;
  return out.slice(i, j < 0 ? out.length : j);
}

describe("bentuk tabel", () => {
  it("dua tabel terpisah, satu per arti biaya", () => {
    const out = html();
    expect(out.match(/<table/g)?.length).toBe(2);
    expect(blok(out, "po")).toContain("Biaya PO");
    expect(blok(out, "sdc")).toContain("SDC analitis");
  });

  it("tiap baris punya label (th scope=row) dan nilai di kolom kanan", () => {
    const po = blok(html(), "po");
    expect(po).toContain('scope="row">Bahan');
    expect(po).toContain("Rp 5.700.000");
  });

  it("baris Total ditandai dan duduk paling bawah", () => {
    const po = blok(html(), "po");
    const totalIdx = po.indexOf("cost-row-total");
    expect(totalIdx).toBeGreaterThan(-1);
    expect(po.indexOf("Total PO")).toBeGreaterThan(po.indexOf("Harga satuan PO"));
    expect(po.slice(totalIdx)).toContain("Total PO");
  });

  it("caption tabel memuat nama blok untuk pembaca layar", () => {
    const out = html();
    expect(out).toContain('<caption class="cost-caption">Biaya PO</caption>');
    expect(out).toContain('<caption class="cost-caption">SDC analitis</caption>');
  });

  it("satuan per kg menempel pada barisnya, bukan catatan kaki", () => {
    const sdc = blok(html(), "sdc");
    expect(sdc).toContain("Rp 37.171 per kg");
  });

  it("catatan pendek sebaris dengan label; catatan penjelas tetap di bawahnya", () => {
    const out = html();
    // "per kg" (6 huruf) tidak boleh jadi baris sendiri.
    expect(out).toContain('class="cost-note cost-note-inline">per kg');
    // "bukan risiko — biaya karena lama disimpan" tetap blok di bawah label.
    expect(blok(out, "sdc")).toMatch(/class="cost-note">bukan risiko/);
  });
});

describe("kejujuran angka", () => {
  it("komponen risiko kosong → barisnya 'tidak tercatat', totalnya tetap sah", () => {
    // `expected_loss` null TIDAK menurunkan status: total SDC masih dihitung
    // server. Yang tidak boleh terjadi hanya satu — angka nol sebagai pengganti.
    const out = html({ expected_loss: null });
    const sdc = blok(out, "sdc");
    expect(sdc).toContain("Susut gudang");
    expect(sdc).toContain("tidak tercatat");
    expect(sdc).toContain("Total SDC");
    expect(out).not.toContain("Rp 0<");
  });

  it("total SDC kosong → status 'tidak tercatat' + alasannya", () => {
    const out = html({ sdc_total: null });
    expect(out).toContain('data-status="tidak_tercatat"');
    expect(out).toContain("Komponen penalti risiko tidak tercatat untuk keputusan ini");
    expect(out).not.toContain("Rp 0<");
  });

  it("tanpa acuan pasar: 'tidak tercatat', bukan angka karangan", () => {
    const po = blok(html(undefined, null), "po");
    expect(po).toContain("Referensi pasar");
    expect(po).toContain("tidak tercatat");
    expect(po).toContain("tidak ada acuan PIHPS");
  });

  it("tanpa biaya transfer: satu kalimat, tanpa tabel kosong", () => {
    const out = html(null);
    expect(out).toContain('data-status="tidak_berlaku"');
    expect(out).toContain("Biaya tidak berlaku untuk keputusan ini");
    expect(out).not.toContain("<table");
  });

  it("tidak ada istilah internal di layar", () => {
    const out = html().toLowerCase();
    for (const kata of ["backend", "endpoint", "null", "commercial_cost", "sdc_total"]) {
      expect(out).not.toContain(kata);
    }
  });
});

describe("CSS tabel clean dashboard", () => {
  it("nilai rata kanan dan angka tabular", () => {
    // `.cost-row th, .cost-row td` adalah blok bersama; yang memuat perataan
    // adalah blok `.cost-row td` yang berdiri sendiri — ambil yang terakhir.
    const blokCss = css.slice(css.lastIndexOf(".cost-row td {"));
    const isi = blokCss.slice(0, blokCss.indexOf("}"));
    expect(isi).toContain("text-align: right");
    expect(isi).toContain("font-variant-numeric: tabular-nums");
    expect(isi).not.toMatch(/#[0-9a-fA-F]{3,6}/);
  });

  it("di bawah 640 px tabel ditumpuk satu kolom", () => {
    const media = css.slice(css.indexOf("@media (max-width: 640px)", css.indexOf(".cost-grid {")));
    expect(media.slice(0, 200)).toContain("grid-template-columns: 1fr");
  });
});
