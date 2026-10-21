import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import SupplyBalanceChart from "../components/SupplyBalanceChart";

const NOW = new Date("2026-10-20T12:00:00Z");

const LOKASI = [
  {
    location: "Surabaya",
    status: "shortage",
    demand_kg: 1000,
    supply_kg: 988,
    shortage_kg: 12,
    surplus_kg: 0,
    demand_state: "terukur",
    supply_state: "terukur",
  },
  {
    location: "Jakarta",
    status: "shortage",
    demand_kg: 1000,
    supply_kg: 220,
    shortage_kg: 780,
    surplus_kg: 0,
    demand_state: "terukur",
    supply_state: "terukur",
  },
  {
    location: "Cianjur",
    status: "surplus",
    demand_kg: 400,
    supply_kg: 1085,
    shortage_kg: 0,
    surplus_kg: 685,
    demand_state: "terukur",
    supply_state: "terukur",
  },
  {
    location: "Bandung",
    status: "balanced",
    demand_kg: 500,
    supply_kg: 500,
    shortage_kg: 0,
    surplus_kg: 0,
    demand_state: "terukur",
    supply_state: "terukur",
  },
  {
    location: "Semarang",
    status: "balanced",
    demand_kg: "",
    supply_kg: 200,
    demand_state: "tidak_ada_baris",
    supply_state: "terukur",
  },
  {
    location: "Bogor",
    status: "balanced",
    demand_kg: 0,
    supply_kg: 300,
    demand_state: "terukur",
    supply_state: "terukur",
  },
  {
    location: "Medan",
    status: "balanced",
    demand_kg: 100,
    supply_kg: null,
    demand_state: "terukur",
    supply_state: "tidak_ada_baris",
  },
];

function render(locations = LOKASI) {
  return renderToStaticMarkup(
    <SupplyBalanceChart
      locations={locations}
      commodity="telur"
      updatedAt={NOW.getTime()}
      now={NOW}
    />
  );
}

describe("SupplyBalanceChart (BGN)", () => {
  it("memakai bahasa visual yang sama: kartu, ringkasan, baris, bar, garis kebutuhan", () => {
    const html = render();
    expect(html).toContain("supply-adequacy");
    expect(html).toContain("Pasokan per Lokasi");
    expect(html).toContain("telur · 7 lokasi");
    expect(html).toContain("2<em>/4</em>");
    expect(html).toContain("lokasi di bawah kebutuhan");
    expect(html).toContain("Jakarta −780 kg");
    expect(html).toContain("sa-track");
    expect(html).toContain("sa-seg-pasokan");
    expect(html).toContain("sa-demand");
    expect(html).toContain("tidak pernah digambar");
  });

  it("mengurutkan kekurangan terbesar lebih dulu", () => {
    const html = render();
    expect(html.indexOf("Jakarta")).toBeLessThan(html.indexOf("Surabaya"));
    expect(html.indexOf("Surabaya")).toBeLessThan(html.indexOf("Cianjur"));
    expect(html).toContain("−780 kg");
    expect(html).toContain("+685 kg");
  });

  it("menyatakan data yang belum tercatat, bukan 0%", () => {
    const html = render();
    expect(html).toContain("kebutuhan belum tercatat");
    expect(html).toContain("pasokan belum tercatat");
    expect(html).not.toContain("NaN");
  });

  it("tanpa lokasi: kartu tetap tampil dengan penjelasan", () => {
    const html = render([]);
    expect(html).toContain("Pasokan per Lokasi");
    expect(html).toContain("Belum ada lokasi");
    expect(html).not.toContain("NaN");
  });
});
