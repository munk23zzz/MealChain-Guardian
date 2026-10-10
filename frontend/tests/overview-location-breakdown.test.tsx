import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import OverviewLocationBreakdown from "../components/OverviewLocationBreakdown";
import { sumFiniteKg, type BalanceMapLocation } from "../lib/overview-format";

const LOCATIONS: BalanceMapLocation[] = [
  { location: "Jakarta", status: "shortage", supply_kg: 300, demand_kg: 1080, shortage_kg: 780, surplus_kg: 0 },
  { location: "Cianjur", status: "surplus", supply_kg: 1400, demand_kg: 300, shortage_kg: 0, surplus_kg: 1100 },
  { location: "Bogor", status: "balanced", supply_kg: 550, demand_kg: 550, shortage_kg: 0, surplus_kg: 0 },
  ...Array.from({ length: 7 }, (_, index) => ({
    location: `Lokasi ${index + 4}`,
    status: "shortage" as const,
    supply_kg: 100,
    demand_kg: 200,
    shortage_kg: 100,
    surplus_kg: 0,
  })),
];

describe("OverviewLocationBreakdown", () => {
  it("total tidak tersedia bila satu nilai hilang atau tidak valid", () => {
    expect(sumFiniteKg([{ supply_kg: 100 }, { supply_kg: undefined }])).toBeNull();
    expect(sumFiniteKg([{ supply_kg: "bad" }])).toBeNull();
    expect(sumFiniteKg([])).toBeNull();
    expect(sumFiniteKg([{ supply_kg: 0 }])).toBe(0);
    expect(sumFiniteKg([{ supply_kg: 100 }, { supply_kg: "250.5" }])).toBe(350.5);
  });

  it("renders all rows once with real desktop headers and separated values", () => {
    const html = renderToStaticMarkup(<OverviewLocationBreakdown locations={LOCATIONS} />);
    expect((html.match(/data-location-row=/g) ?? []).length).toBe(10);
    for (const heading of ["Lokasi", "Status", "Pasokan", "Kebutuhan", "Selisih"]) expect(html).toContain(`<th>${heading}</th>`);
    expect(html).toContain("Jakarta");
    expect(html).toContain("Shortage");
    expect(html).toContain("Pasokan: 300 kg");
    expect(html).toContain("Kebutuhan: 1.080 kg");
    expect(html).toContain("Selisih: kurang 780 kg");
    expect(html).toContain("1 surplus · 8 shortage · 1 seimbang");
  });

  it("keeps valid zero distinct from missing values", () => {
    const html = renderToStaticMarkup(<OverviewLocationBreakdown locations={[{ ...LOCATIONS[0], shortage_kg: 0, demand_kg: undefined }]} />);
    expect(html).toContain("Kebutuhan: —");
    expect(html).toContain("Selisih: kurang 0 kg");
    expect(html).not.toContain("Kebutuhan: 0 kg");
  });

  it("does not silently classify unknown status as balanced", () => {
    const html = renderToStaticMarkup(<OverviewLocationBreakdown locations={[{ ...LOCATIONS[0], status: "pending" as never }]} />);
    expect(html).toContain("Status belum tersedia");
    expect(html).not.toContain("Seimbang");
  });

  it("uses an honest empty state instead of a busy state", () => {
    const html = renderToStaticMarkup(<OverviewLocationBreakdown locations={[]} />);
    expect(html).toContain("Belum ada data lokasi");
    expect(html).not.toContain("aria-busy=\"true\"");
  });

  it("can represent loading separately", () => {
    const html = renderToStaticMarkup(<OverviewLocationBreakdown locations={[]} loading />);
    expect(html).toContain("Memuat data lokasi");
    expect(html).toContain("aria-busy=\"true\"");
  });
});
