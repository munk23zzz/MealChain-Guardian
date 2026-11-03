// Dashboard Decision & Evidence: kalimat teknis yang diminta DIHAPUS
// (permintaan pemilik 29 Okt 2026).
//
// Yang dibuang dari layar:
//   1. "Dasar risiko: Kebijakan simulasi · app/core/safe_delivered_cost.py:bobot_demo
//      · versi sdc-policy-1" — kartu biaya tidak lagi mencetak jalur berkas.
//   2. Blok "Catatan teknis · 3 cara membaca bukti" beserta tiga barisnya
//      (pemulihan administratif, usulan exclusion, review bukti batch).
//   3. Catatan "harga acuan PIHPS — pembanding bahan, bukan biaya PO" pada baris
//      Referensi pasar.
//   4. Baris pecahan angkut "Angkut pemasok → SPPG" / "Angkut antar SPPG".
//
// Alasan satu file tes: keempat hal itu muncul di satu halaman yang sama, jadi
// kalau salah satunya kembali (mis. saat orang menambah baris ke tabel biaya),
// halaman itu kembali berisik tanpa ada yang sadar.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import DecisionEconomics from "../components/DecisionEconomics";
import { buildCostView, type CommercialCostPayload } from "../lib/decision-economics";
import { costFacts } from "../lib/evidence";

const PAYLOAD: CommercialCostPayload = {
  purchase_total: "5700000.00",
  transport_total: "34200.00",
  handling_total: "150000.00",
  invoice_total: "5884200.00",
  invoice_unit_price: "29421.00",
  expected_loss: "100000.00",
  freshness_risk: "0.00",
  safety_penalty: "0.00",
  sdc_total: "6104200.00",
  sdc_unit_price: "30521.00",
  risk_method: {
    kind: "simulated_policy",
    source: "app/core/safe_delivered_cost.py:bobot_demo",
    version: "sdc-policy-1",
    period: null,
    baseline: null,
  },
};

const sumberDetail = readFileSync(
  join(__dirname, "..", "components", "DecisionDetail.tsx"),
  "utf8",
);

describe("Decision & Evidence tanpa kalimat teknis", () => {
  it("kartu biaya tidak mencetak Dasar risiko / jalur berkas / versi kebijakan", () => {
    const html = renderToStaticMarkup(<DecisionEconomics cost={PAYLOAD} />);
    expect(html).not.toContain("Dasar risiko");
    expect(html).not.toContain("sdc-policy-1");
    expect(html).not.toContain("bobot_demo");
    expect(html).not.toContain("Kebijakan simulasi");
    // Angka tetap ada: yang dibuang kalimatnya, bukan isinya.
    expect(html).toContain("Rp 5.884.200");
  });

  it("rincian logistik tidak dipecah menjadi baris angkut", () => {
    const rows = costFacts({
      cost_breakdown: {
        purchase: "13772500",
        logistics: "18471.85",
        transport_supplier_leg: "6653.07",
        transport_linehaul: "11818.78",
        supplier_leg_km: "45.075",
        supplier_leg_reference: "supplier_coordinates",
      },
      safe_delivered_cost: "14980976.71",
    });
    const labels = rows.map((r) => r.label);
    expect(labels).not.toContain("Angkut pemasok → SPPG");
    expect(labels).not.toContain("Angkut antar SPPG");
    expect(labels).toContain("Logistik");
  });

  it("referensi pasar tidak lagi mencetak catatan pembanding PIHPS", () => {
    const view = buildCostView(PAYLOAD, {
      source: "pihps_reference",
      price_per_kg: 32000,
      recorded_at: null,
    });
    const semua = JSON.stringify(view);
    expect(semua).not.toContain("pembanding bahan");
    expect(semua).not.toContain("bukan biaya PO");
    const baris = view.blocks.flatMap((b) => b.rows).find((r) => r.label === "Referensi pasar");
    expect(baris?.value).toContain("32.000");
    expect(baris?.note ?? null).toBeNull();
  });

  it("halaman detail tidak merender blok Catatan teknis", () => {
    expect(sumberDetail).not.toMatch(/CatatanTeknis/);
    expect(sumberDetail).not.toContain("cara membaca bukti");
  });
});
