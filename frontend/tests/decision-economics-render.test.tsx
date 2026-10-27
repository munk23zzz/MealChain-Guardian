// Fase 9 butir 1 (tampilan): invoice dan SDC punya arti berbeda di layar.
// Dirender statis (tanpa jaringan), sama seperti tes papan lain di repo ini.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import DecisionEconomics from "../components/DecisionEconomics";
import type { CommercialCostPayload } from "../lib/decision-economics";

const PAYLOAD: CommercialCostPayload = {
  purchase_total: "5700000.00",
  transport_total: "34200.00",
  handling_total: "150000.00",
  invoice_total: "5884200.00",
  invoice_unit_price: "29421.00",
  expected_loss: "100000.00",
  freshness_risk: "0.00",
  safety_penalty: "0.00",
  sdc_total: "5984200.00",
  sdc_unit_price: "29921.00",
  risk_method: {
    kind: "simulated_policy",
    source: "app/core/safe_delivered_cost.py:bobot_demo",
    version: "sdc-policy-1",
    period: null,
    baseline: null,
  },
};

function render(cost: CommercialCostPayload | null): string {
  return renderToStaticMarkup(<DecisionEconomics cost={cost} />);
}

/** Potong satu blok dari markup (tanpa regex: batasnya penanda data-block). */
function potong(html: string, key: "po" | "sdc"): string {
  const mulai = html.indexOf(`data-block="${key}"`);
  if (mulai < 0) return "";
  const selesai = html.indexOf("</article>", mulai);
  return selesai < 0 ? html.slice(mulai) : html.slice(mulai, selesai);
}

describe("DecisionEconomics — biaya PO vs SDC", () => {
  it("blok PO memuat bahan, transportasi, handling, dan total PO", () => {
    const po = potong(render(PAYLOAD), "po");
    expect(po).toContain("Bahan");
    expect(po).toContain("Transportasi");
    expect(po).toContain("Handling");
    expect(po).toContain("Total PO");
    expect(po).toContain("Rp 5.884.200");
    expect(po).toContain("Rp 29.421");
  });

  it("penalti risiko tidak muncul di blok PO", () => {
    const po = potong(render(PAYLOAD), "po");
    expect(po).not.toContain("Expected loss");
    expect(po).not.toContain("Risiko kesegaran");
    expect(po).not.toContain("Penalti keamanan");
  });

  it("blok SDC memuat penalti dan total SDC", () => {
    const sdc = potong(render(PAYLOAD), "sdc");
    expect(sdc).toContain("Expected loss");
    expect(sdc).toContain("Risiko kesegaran");
    expect(sdc).toContain("Penalti keamanan");
    expect(sdc).toContain("Total SDC");
    expect(sdc).toContain("Rp 5.984.200");
  });

  it("tidak ada label harga beli untuk SDC", () => {
    const html = render(PAYLOAD);
    expect(html.toLowerCase()).not.toContain("harga beli");
    const sdc = potong(html, "sdc");
    expect(sdc.toLowerCase()).not.toContain("harga beli");
  });

  it("menampilkan sumber dan versi metode risiko", () => {
    const html = render(PAYLOAD);
    expect(html).toContain("Kebijakan simulasi");
    expect(html).toContain("sdc-policy-1");
    expect(html).toContain("safe_delivered_cost");
  });
});

describe("DecisionEconomics — nilai yang tidak ada", () => {
  it("tanpa payload menulis 'tidak berlaku', bukan Rp 0", () => {
    const html = render(null);
    expect(html).toContain("Biaya tidak berlaku untuk keputusan ini");
    expect(html).not.toContain("Rp 0");
    expect(potong(html, "po")).toBe("");
  });

  it("sdc kosong menulis 'tidak tercatat' tanpa total palsu", () => {
    const html = render({ ...PAYLOAD, sdc_total: null, sdc_unit_price: null });
    const sdc = potong(html, "sdc");
    expect(sdc).toContain("tidak tercatat");
    // Penalti bernilai nol yang TERCATAT boleh tampil "Rp 0"; yang dilarang
    // adalah total SDC karangan. Jadi asersinya khusus baris Total SDC.
    const barisTotal = sdc.slice(sdc.indexOf("Total SDC"));
    expect(barisTotal).toContain("tidak tercatat");
    expect(barisTotal).not.toContain("Rp 0");
    // Invoice tetap terbaca walau SDC tidak tercatat.
    expect(potong(html, "po")).toContain("Rp 5.884.200");
  });
});
