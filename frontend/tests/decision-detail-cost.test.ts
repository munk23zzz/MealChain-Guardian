// Fase 9 butir 3 — blok biaya harus benar-benar sampai ke layar.
//
// Cacat yang dikunci di sini: `GET /decisions` (daftar) TIDAK memuat
// `commercial_cost`, sedangkan halaman Decision & Evidence dulu memberi
// `DecisionEconomics` baris daftar itu. Akibatnya, di browser blok biaya selalu
// menulis "Biaya tidak berlaku untuk keputusan ini" walaupun
// `GET /decisions/{id}` mengirim payload lengkap — unit test komponen tetap
// hijau karena komponennya diuji dengan payload, bukan dengan kabel halamannya.
//
// Perbaikan: satu fungsi murni yang menggabungkan baris daftar dengan detail
// server. Aturannya:
//   - detail berhasil  -> `commercial_cost`/`market_reference` MILIK DETAIL;
//   - detail gagal     -> baris tidak diubah (jangan mengarang "tidak berlaku");
//   - detail tanpa kunci -> nilai baris dipertahankan (backend lama);
//   - `commercial_cost: null` dari server -> tetap null (memang tidak berlaku).
import { describe, expect, it } from "vitest";

import { withDetailCost } from "../lib/decision-economics";

const BARIS = {
  decision_id: "d1",
  status: "executed",
  safe_delivered_cost: "100",
};

const DETAIL = {
  decision_id: "d1",
  commercial_cost: {
    purchase_total: "8220000.00",
    transport_total: "2050.74",
    handling_total: "150000.00",
    invoice_total: "8372050.74",
    invoice_unit_price: "13953.42",
    expected_loss: "295920.00",
    freshness_risk: "0.00",
    safety_penalty: "0.00",
    sdc_total: "8667970.74",
    sdc_unit_price: "14446.62",
    risk_method: { kind: "simulated_policy", source: "s", version: "v1" },
  },
  market_reference: { source: "pihps_reference", price_per_kg: 13315.71 },
};

describe("Fase 9 butir 3 — biaya detail menempel pada baris daftar", () => {
  it("detail berhasil: payload biaya + referensi pasar ikut", () => {
    const gabung = withDetailCost(BARIS, DETAIL);
    expect(gabung?.commercial_cost).toEqual(DETAIL.commercial_cost);
    expect(gabung?.market_reference).toEqual(DETAIL.market_reference);
    // Identitas baris daftar tidak hilang.
    expect(gabung?.decision_id).toBe("d1");
    expect(gabung?.status).toBe("executed");
  });

  it("detail gagal (null): baris tidak diubah, bukan diklaim 'tidak berlaku'", () => {
    const gabung = withDetailCost(BARIS, null);
    expect(gabung).toBe(BARIS);
    expect(gabung?.commercial_cost).toBeUndefined();
  });

  it("server menyatakan commercial_cost null: tetap null", () => {
    const gabung = withDetailCost(BARIS, { ...DETAIL, commercial_cost: null, market_reference: null });
    expect(gabung?.commercial_cost).toBeNull();
    expect(gabung?.market_reference).toBeNull();
  });

  it("detail tanpa kunci commercial_cost: nilai baris dipertahankan", () => {
    const barisBerbiaya = { ...BARIS, commercial_cost: DETAIL.commercial_cost };
    const gabung = withDetailCost(barisBerbiaya, { decision_id: "d1" });
    expect(gabung?.commercial_cost).toEqual(DETAIL.commercial_cost);
  });

  it("baris kosong: tetap kosong (tidak ada keputusan dipilih)", () => {
    expect(withDetailCost(null, DETAIL)).toBeNull();
  });
});
