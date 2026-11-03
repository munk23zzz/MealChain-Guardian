// Bullet bar KPI (Fase 4 redesign, 2026-10-16).
//
// Kontrak yang dijaga: bar skala HANYA digambar kalau metriknya memang punya
// skala sendiri (persen → 0–100). Angka TARGET tidak ada di data: kpi_service
// tidak pernah mengirim target/threshold, jadi UI TIDAK mengarang ambang
// "baik/buruk". Yang ditampilkan hanya (a) skala nyata metrik itu dan (b) arah
// perbaikan yang sudah tertulis di definisi metrik ("makin tinggi/rendah makin
// baik"). Nilai yang tidak berupa angka tidak digambar sebagai 0 — tidak ada
// bar sama sekali, karena 0% adalah klaim yang berbeda dari "tidak ada data".
import { describe, expect, it } from "vitest";

import { KPI_DIRECTION, bulletOf, directionLabel } from "../lib/kpi";

const m = (over: Record<string, unknown> = {}) => ({
  name: "Evidence Completeness",
  unit: "percent",
  state: "available",
  value: "84.20",
  ...over,
});

describe("bulletOf — bar skala sendiri", () => {
  it("persen sah → lebar bar = nilainya, skala 0–100", () => {
    const b = bulletOf(m());
    expect(b).not.toBeNull();
    expect(b!.hasScale).toBe(true);
    expect(b!.pct).toBeCloseTo(84.2, 1);
    expect(b!.max).toBe(100);
    expect(b!.overMax).toBe(false);
    expect(b!.value).toBeCloseTo(84.2, 1);
  });

  it("nilai di atas skala → bar penuh + penanda lewat skala, angka asli tetap utuh", () => {
    const b = bulletOf(m({ value: "162.00" }));
    expect(b!.pct).toBe(100);
    expect(b!.overMax).toBe(true);
    expect(b!.value).toBe(162);
  });

  it("tanpa skala (IDR / menit) → tidak ada bar, bukan bar 0", () => {
    expect(
      bulletOf(m({ name: "Safe Delivered Cost", unit: "IDR", value: "15496548.14" }))!.hasScale
    ).toBe(false);
    expect(bulletOf(m({ name: "Decision Time", unit: "minutes", value: "120.00" }))!.pct).toBeNull();
  });

  it("state no_data/unavailable → tidak ada bar walau unitnya persen", () => {
    expect(bulletOf(m({ state: "no_data", value: null }))!.pct).toBeNull();
    expect(bulletOf(m({ state: "unavailable", value: null }))!.pct).toBeNull();
  });

  it("nilai kosong/teks/negatif tidak digambar sebagai 0", () => {
    for (const value of [null, undefined, "", "bukan-angka", "-5"]) {
      expect(bulletOf(m({ value }))!.pct, String(value)).toBeNull();
    }
  });

  it("metrik tak dikenal tetap tidak meledak (arah 'none', bar tetap benar)", () => {
    const b = bulletOf(m({ name: "KPI Baru", unit: "percent", value: "10" }));
    expect(b!.direction).toBe("none");
    expect(directionLabel(b!.direction)).toBeNull();
    expect(b!.pct).toBeCloseTo(10, 1);
  });
});

describe("KPI_DIRECTION — arah perbaikan tujuh metrik", () => {
  it("tujuh metrik punya arah; tidak ada metrik karangan", () => {
    const expected = [
      "Avoidable Food Loss",
      "Decision Time",
      "Evidence Completeness",
      "Meal Continuity Rate",
      "Procurement Price Deviation",
      "Regional Imbalance Resolution Rate",
      "Safe Delivered Cost",
    ];
    expect(Object.keys(KPI_DIRECTION).sort()).toEqual(expected);
  });

  it("label arah berbahasa Indonesia (tanpa kata target/ambang)", () => {
    expect(directionLabel("higher")).toBe("makin tinggi makin baik");
    expect(directionLabel("lower")).toBe("makin rendah makin baik");
    expect(directionLabel("none")).toBeNull();
  });
});
