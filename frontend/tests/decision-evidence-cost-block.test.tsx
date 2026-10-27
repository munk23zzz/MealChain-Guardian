// Kontrak markup blok biaya di halaman "Decision & Evidence" (Fase 5 butir 5).
//
// Yang dipin:
// - PO (bahan + transportasi + handling) dan SDC (penalti risiko internal)
//   tampil sebagai DUA blok terpisah — penalti tidak boleh muncul di blok PO;
// - referensi pasar adalah pembanding harga BAHAN, bukan komponen biaya PO;
// - `commercial_cost: null` berarti "tidak berlaku" (keputusan administratif
//   tanpa transfer), bukan Rp 0 dan bukan blok kosong.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import DecisionEvidence from "../components/DecisionEvidence";

const NOW = new Date("2026-10-11T02:30:00Z");

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
  risk_method: {
    kind: "simulated_policy",
    source: "app/core/safe_delivered_cost.py:bobot_demo",
    version: "sdc-policy-1",
    period: null,
    baseline: null,
  },
};

const PASAR = {
  source: "pihps_reference",
  price_per_kg: 31000,
  recorded_at: "2026-10-10T00:00:00+00:00",
};

const SELECTED = {
  decision_id: "d1",
  decision_type: "regional_balance",
  status: "pending_approval",
  quantity_kg: 200,
  safe_delivered_cost: 7434200,
  created_at: "2026-10-07T02:16:47Z",
  expires_at: "2026-10-11T02:16:47.973521+00:00",
  commercial_cost: COST,
  market_reference: PASAR,
};

function render(over: Record<string, unknown> = {}) {
  return renderToStaticMarkup(
    <DecisionEvidence
      decisions={[] as any}
      selected={SELECTED}
      selectedId="d1"
      onSelect={() => {}}
      chain={[]}
      summary={null}
      supplierContext={null}
      role="sppg_head"
      token="t"
      now={NOW}
      {...over}
    />
  );
}

/** Potongan markup satu blok biaya (`data-block="po"` / `"sdc"`). */
function blok(html: string, kunci: "po" | "sdc"): string {
  const mulai = html.indexOf(`data-block="${kunci}"`);
  if (mulai < 0) return "";
  const lain = kunci === "po" ? html.indexOf('data-block="sdc"', mulai) : html.length;
  return html.slice(mulai, lain < 0 ? html.length : lain);
}

describe("Decision & Evidence — blok biaya Fase 5", () => {
  it("memisahkan PO (ditagihkan) dari SDC (analitis)", () => {
    const html = render();
    expect(html).toContain('data-testid="decision-economics"');

    const po = blok(html, "po");
    const sdc = blok(html, "sdc");
    expect(po).toContain("Total PO");
    expect(po).toContain("Rp 5.884.200");
    expect(po).toContain("Bahan");
    expect(sdc).toContain("Total SDC");
    expect(sdc).toContain("Rp 7.434.200");
  });

  it("tidak menaruh penalti risiko di blok PO", () => {
    const html = render();
    const po = blok(html, "po");
    const sdc = blok(html, "sdc");
    expect(po).not.toContain("Expected loss");
    expect(po).not.toContain("Penalti keamanan");
    expect(po).not.toContain("Rp 7.434.200");
    expect(sdc).not.toContain("Bahan");
  });

  it("menampilkan referensi pasar sebagai pembanding harga bahan", () => {
    const html = render();
    const po = blok(html, "po");
    expect(po).toContain("Referensi pasar");
    expect(po).toContain("Rp 31.000");
    expect(po.toLowerCase()).toContain("pembanding");
  });

  it("menulis tidak tercatat bila tidak ada acuan pasar — bukan Rp 0", () => {
    const html = render({
      selected: { ...SELECTED, market_reference: null },
    });
    const po = blok(html, "po");
    expect(po).toContain("Referensi pasar");
    expect(po).toContain("tidak tercatat");
    expect(po).not.toContain("Rp 0");
  });

  it("keputusan administratif tanpa biaya transfer: tidak berlaku, bukan Rp 0", () => {
    const html = render({
      selected: { ...SELECTED, commercial_cost: null, market_reference: null },
    });
    expect(html).toContain('data-status="tidak_berlaku"');
    expect(html).toContain("Biaya tidak berlaku untuk keputusan ini");
    expect(html).not.toContain("Rp 0<");
  });
});
