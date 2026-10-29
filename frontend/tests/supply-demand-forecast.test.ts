// Tes murni untuk kartu keempat pop-up "Pasokan & permintaan": perkiraan
// kebutuhan 7 hari (dokumen 03 §3 butir 3 dan §4, 28 Okt 2026).
//
// Aturan yang dikunci:
//   - angka perkiraan datang dari `GET /demand/forecast/{loc}/{com}` — bukan
//     dihitung ulang di halaman;
//   - metode dan keyakinan ditampilkan apa adanya, dan dasar yang tipis
//     (keyakinan < 1, yaitu kurang dari 3 catatan permintaan) DINYATAKAN;
//   - perkiraan yang tidak ada ditulis "—" dengan sebabnya, tidak pernah 0 kg.

import { describe, expect, it } from "vitest";

import { buildForecastView, buildSupplyDemandDetail } from "../lib/supply-demand";

describe("buildForecastView", () => {
  it("membaca forecast_qty_kg, metode, dan keyakinan dari server", () => {
    const view = buildForecastView({ forecast_qty_kg: 7420, method: "statistical_fallback", confidence: 1 });
    expect(view).not.toBeNull();
    expect(view!.quantityKg).toBe(7420);
    expect(view!.horizonDays).toBe(7);
    expect(view!.methodLabel).toBe("perkiraan statistik");
    expect(view!.confidence).toBe(1);
    expect(view!.note).toBeNull();
  });

  it("menyatakan dasar yang tipis bila keyakinan di bawah 1", () => {
    const view = buildForecastView({ forecast_qty_kg: 1200, method: "statistical_fallback", confidence: 0.67 });
    expect(view!.confidence).toBe(0.67);
    expect(view!.confidenceLabel).toMatch(/dasar tipis/);
    expect(view!.note).toMatch(/kurang dari 3 catatan permintaan/);
  });

  it("memakai nama metode apa adanya bila bukan metode yang dikenal", () => {
    const view = buildForecastView({ forecast_qty_kg: 10, method: "provider_forecast", confidence: 1 });
    expect(view!.methodLabel).toBe("perkiraan penyedia");
    const asing = buildForecastView({ forecast_qty_kg: 10, method: "regresi_linear", confidence: 1 });
    expect(asing!.methodLabel).toBe("regresi_linear");
  });

  it("tidak mengarang angka bila kuantitas perkiraan tidak ada", () => {
    const view = buildForecastView({ method: "statistical_fallback", confidence: 1 });
    expect(view!.quantityKg).toBeNull();
    expect(view!.note).toMatch(/tidak ada angka perkiraan/);
  });

  it("mengembalikan null untuk balasan kosong", () => {
    expect(buildForecastView(null)).toBeNull();
    expect(buildForecastView(undefined)).toBeNull();
  });

  it("menampilkan sumber SAP-RPT-1.6 apa adanya", () => {
    const view = buildForecastView({
      forecast_qty_kg: 2166.92,
      method: "sap_rpt_1_6",
      confidence: 0.9956,
      source: "SAP-RPT-1.6",
      fallback_used: false,
    });
    expect(view!.source).toBe("SAP-RPT-1.6");
    expect(view!.sourceLabel).toBe("SAP-RPT-1.6");
    expect(view!.fallbackUsed).toBe(false);
    // Keyakinan model 0,9956 dibaca sebagai probabilitas model, BUKAN "dasar
    // tipis" (aturan itu hanya untuk cadangan statistik).
    expect(view!.confidenceLabel).toBe("keyakinan 99.6%");
    expect(view!.note).toBeNull();
  });

  it("menyebut sumber cadangan dan alasannya bila model gagal", () => {
    const view = buildForecastView({
      forecast_qty_kg: 2100,
      method: "statistical_fallback",
      confidence: 1,
      source: "statistical_fallback",
      fallback_used: true,
      reason: "provider peramalan gagal; pakai cadangan",
    });
    expect(view!.sourceLabel).toBe("cadangan statistik");
    expect(view!.fallbackUsed).toBe(true);
    // Sumbernya memang statistik, jadi tidak ada klaim "cadangan dipakai" —
    // itu hanya relevan bila label sumber masih mengaku model.
    expect(view!.note).toBeNull();
  });

  it("menyatakan sumber yang tidak dilaporkan alih-alih menebak", () => {
    const view = buildForecastView({ forecast_qty_kg: 10, method: "statistical_fallback" });
    expect(view!.source).toBeNull();
    expect(view!.sourceLabel).toBe("sumber tidak dilaporkan");
  });
});

describe("buildSupplyDemandDetail — kartu perkiraan", () => {
  const dasar = {
    location: "Jakarta",
    commodity: "telur",
    balance: { shortage_kg: 780, surplus_kg: 0 },
    supply: { quantity_kg: 300, recorded_at: "2026-10-28T15:00:00Z", source: "mock_sap" },
    demand: { quantity_kg: 1080, needed_by: "2026-10-31T15:00:00Z" },
    batches: [],
  };

  it("meneruskan perkiraan ke detail", () => {
    const detail = buildSupplyDemandDetail({
      ...dasar,
      forecast: { forecast_qty_kg: 7420, method: "statistical_fallback", confidence: 1 },
    });
    expect(detail.forecast?.quantityKg).toBe(7420);
    expect(detail.notes.join(" ")).not.toMatch(/perkiraan/i);
  });

  it("perkiraan yang tidak ada cukup dinyatakan kartunya, tidak diulang di catatan", () => {
    const detail = buildSupplyDemandDetail({
      ...dasar,
      forecast: null,
      failed: { forecast: "404 Not Found" },
    });
    expect(detail.forecast).toBeNull();
    // Kartu perkiraan menulis "—" + "belum ada perkiraan"; catatan tidak mengulanginya.
    expect(detail.notes.join(" ")).not.toMatch(/[Pp]erkiraan/);
    expect(detail.notes.join(" ")).not.toMatch(/0 kg/);
  });
});
