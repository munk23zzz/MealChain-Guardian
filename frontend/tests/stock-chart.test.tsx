// S4-06 polish — StockChart: grafik surplus/shortage per lokasi (recharts,
// SSR-safe tanpa ResponsiveContainer; data REAL dari /balance/map).
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import StockChart from "../components/StockChart";

const LOCATIONS = [
  {
    location: "Jakarta",
    region: "DKI Jakarta",
    latitude: -6.2088,
    longitude: 106.8456,
    supply_kg: 300,
    demand_kg: 1080,
    surplus_kg: 0,
    shortage_kg: 780,
    status: "shortage",
  },
  {
    location: "Cianjur",
    region: "Jawa Barat",
    latitude: -6.842,
    longitude: 107.1426,
    supply_kg: 1400,
    demand_kg: 300,
    surplus_kg: 1100,
    shortage_kg: 0,
    status: "surplus",
  },
];

describe("StockChart", () => {
  it("SSR: placeholder stabil + judul; angka hanya setelah mount (CLS aman)", () => {
    const html = renderToStaticMarkup(<StockChart locations={LOCATIONS} />);
    expect(html).toContain("stock-chart");
    expect(html).toContain("Surplus");
    expect(html).toContain("Shortage");
    expect(html).toContain("stock-chart-placeholder");
    // recharts butuh ukuran browser — SSR tidak merender SVG (tanpa CLS):
    expect(html).not.toContain("recharts");
  });

  it("tanpa data → null (bukan grafik kosong karangan)", () => {
    expect(renderToStaticMarkup(<StockChart locations={[]} />)).toBe("");
  });
});
