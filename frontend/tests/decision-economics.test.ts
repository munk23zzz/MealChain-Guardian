// Kontrak helper biaya Fase 9 butir 1 & 3 — logika murni, tanpa DOM.
//
// Dua arti biaya yang tidak boleh tercampur:
//   PO/invoice  = bahan + transportasi + handling  (yang ditagih)
//   SDC         = invoice + expected loss + freshness risk + safety penalty
// `null` berarti "tidak berlaku" (keputusan administratif tanpa transfer),
// bukan Rp 0. Field yang kosong di dalam payload berarti "tidak tercatat".
import { describe, expect, it } from "vitest";

import {
  buildCostView,
  formatRupiah,
  labelRiskMethod,
  type CommercialCostPayload,
} from "../lib/decision-economics";

const PAYLOAD: CommercialCostPayload = {
  purchase_total: "5700000.00",
  transport_total: "34200.00",
  handling_total: "150000.00",
  invoice_total: "5884200.00",
  invoice_unit_price: "29421.00",
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

describe("buildCostView — invoice vs SDC", () => {
  it("baris PO hanya bahan, transportasi, handling (+ pembanding pasar)", () => {
    // Fase 5 butir 5: referensi pasar masuk blok PO sebagai PEMBANDING harga
    // bahan. Tanpa acuan ia tetap tampil dengan "tidak tercatat" — menghapus
    // barisnya membuat pembaca mengira tidak ada acuan sama sekali.
    const view = buildCostView(PAYLOAD);
    const po = view.blocks.find((b) => b.key === "po");
    expect(po).toBeDefined();
    expect(po!.rows.map((r) => r.label)).toEqual([
      "Bahan",
      "Transportasi",
      "Handling",
      "Referensi pasar",
      "Harga satuan PO",
      "Total PO",
    ]);
    expect(po!.rows.map((r) => r.value)).toEqual([
      "Rp 5.700.000",
      "Rp 34.200",
      "Rp 150.000",
      "tidak tercatat",
      "Rp 29.421",
      "Rp 5.884.200",
    ]);
  });

  it("referensi pasar terisi bila backend mengirim acuan PIHPS", () => {
    const view = buildCostView(PAYLOAD, {
      source: "pihps_reference",
      price_per_kg: 31000,
      recorded_at: "2026-10-10T00:00:00+00:00",
    });
    const po = view.blocks.find((b) => b.key === "po")!;
    const baris = po.rows.find((r) => r.label === "Referensi pasar")!;
    expect(baris.value).toBe("Rp 31.000 per kg");
    expect((baris.note ?? "").toLowerCase()).toContain("bukan biaya po");
  });

  it("penalti risiko hanya ada di blok SDC", () => {
    const view = buildCostView(PAYLOAD);
    const po = view.blocks.find((b) => b.key === "po")!;
    const sdc = view.blocks.find((b) => b.key === "sdc")!;

    const labelPo = po.rows.map((r) => r.label.toLowerCase()).join(" | ");
    expect(labelPo).not.toContain("expected loss");
    expect(labelPo).not.toContain("freshness");
    expect(labelPo).not.toContain("penalty");
    expect(labelPo).not.toContain("penalti");

    const labelSdc = sdc.rows.map((r) => r.label.toLowerCase()).join(" | ");
    expect(labelSdc).toContain("expected loss");
    expect(labelSdc).toContain("risiko kesegaran");
    expect(labelSdc).toContain("penalti keamanan");
  });

  it("total SDC tidak dilabeli harga beli", () => {
    const view = buildCostView(PAYLOAD);
    const sdc = view.blocks.find((b) => b.key === "sdc")!;
    const total = sdc.rows[sdc.rows.length - 1];
    expect(total.label).toBe("Total SDC");
    expect(total.label.toLowerCase()).not.toContain("harga beli");
  });

  it("sumber dan versi metode risiko ikut ditampilkan", () => {
    const view = buildCostView(PAYLOAD);
    expect(view.riskMethod.kind).toBe("simulated_policy");
    expect(view.riskMethod.label).toBe("Kebijakan simulasi");
    expect(view.riskMethod.source).toContain("safe_delivered_cost");
    expect(view.riskMethod.version).toBe("sdc-policy-1");
  });
});

describe("buildCostView — nilai yang tidak ada", () => {
  it("payload null berarti tidak berlaku, bukan Rp 0", () => {
    const view = buildCostView(null);
    expect(view.status).toBe("tidak_berlaku");
    expect(view.blocks).toEqual([]);
    expect(view.message).toBe("Biaya tidak berlaku untuk keputusan ini");
  });

  it("sdc null berarti tidak tercatat, invoice tetap tampil", () => {
    const view = buildCostView({ ...PAYLOAD, sdc_total: null, sdc_unit_price: null });
    const sdc = view.blocks.find((b) => b.key === "sdc")!;
    expect(sdc.rows.some((r) => r.value === "tidak tercatat")).toBe(true);
    const po = view.blocks.find((b) => b.key === "po")!;
    expect(po.rows.some((r) => r.value === "Rp 5.884.200")).toBe(true);
    expect(view.status).toBe("tidak_tercatat");
  });

  it("metode risiko tak dikenal tidak diklaim terkalibrasi", () => {
    const view = buildCostView({
      ...PAYLOAD,
      risk_method: {
        kind: "unavailable",
        source: "cost_breakdown.risk_method",
        version: "n/a",
        period: null,
        baseline: null,
      },
    });
    expect(view.riskMethod.kind).toBe("unavailable");
    expect(view.riskMethod.label).toBe("Tidak tersedia");
  });
});

describe("formatRupiah", () => {
  it("memformat string desimal tanpa menghitung ulang", () => {
    expect(formatRupiah("5884200.00")).toBe("Rp 5.884.200");
    expect(formatRupiah("29421.50")).toBe("Rp 29.421,50");
  });

  it("null bukan nol", () => {
    expect(formatRupiah(null)).toBe("tidak tercatat");
    expect(formatRupiah(undefined)).toBe("tidak tercatat");
  });
});

describe("labelRiskMethod", () => {
  it("memetakan tiga kind ke bahasa manusia", () => {
    expect(labelRiskMethod("simulated_policy")).toBe("Kebijakan simulasi");
    expect(labelRiskMethod("calibrated_model")).toBe("Model terkalibrasi");
    expect(labelRiskMethod("unavailable")).toBe("Tidak tersedia");
  });
});
