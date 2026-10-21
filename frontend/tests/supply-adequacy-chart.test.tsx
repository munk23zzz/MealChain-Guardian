import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import SupplyAdequacyChart from "../components/SupplyAdequacyChart";
import { buildAdequacyRows } from "../lib/supply-adequacy";

const NOW = new Date("2026-10-20T12:00:00Z");

function batchesFor(commodity: string, kg: number, hari: number) {
  return {
    location: "Jakarta",
    commodity,
    quantity_kg: kg,
    safety_status: "pass",
    quarantine_status: "none",
    usable_until: new Date(NOW.getTime() + hari * 86_400_000).toISOString(),
  };
}

const MAP = {
  telur: [
    {
      location: "Jakarta",
      demand_kg: 1080,
      supply_kg: 300,
      shortage_kg: 780,
      surplus_kg: 0,
      status: "shortage",
      demand_state: "terukur",
    },
  ],
  beras: [
    {
      location: "Jakarta",
      demand_kg: 3010,
      supply_kg: 1179,
      shortage_kg: 1831,
      surplus_kg: 0,
      status: "shortage",
      demand_state: "terukur",
    },
  ],
  ayam: [
    {
      location: "Jakarta",
      demand_kg: 308,
      supply_kg: 250,
      shortage_kg: 58,
      surplus_kg: 0,
      status: "shortage",
      demand_state: "terukur",
    },
  ],
  wortel: [
    {
      location: "Jakarta",
      demand_kg: 392,
      supply_kg: 500,
      shortage_kg: 0,
      surplus_kg: 108,
      status: "surplus",
      demand_state: "terukur",
    },
  ],
};

const BATCHES = [
  batchesFor("telur", 200, 5),
  batchesFor("telur", 100, 1), // ≤48 jam
  batchesFor("beras", 0, 5),
  batchesFor("ayam", 250, 4),
  batchesFor("wortel", 500, 6),
];

const ROWS = buildAdequacyRows({
  commodities: ["telur", "ayam", "beras", "wortel"],
  byCommodity: MAP,
  batches: BATCHES,
  location: "Jakarta",
  now: NOW,
});

function render(role: string, rows = ROWS) {
  return renderToStaticMarkup(
    <SupplyAdequacyChart
      rows={rows}
      role={role}
      locationName="Jakarta"
      updatedAt={NOW.getTime()}
      now={NOW}
    />
  );
}

describe("SupplyAdequacyChart", () => {
  it("kepala SPPG: cakupan total, urut dari yang paling kurang", () => {
    const html = render("sppg_head");
    expect(html).toContain("Kecukupan pasokan");
    expect(html).toContain("Kuantitas");
    expect(html).toContain("komoditas di bawah kebutuhan");
    // beras 0% mendahului telur 27,8%
    expect(html.indexOf("beras")).toBeLessThan(html.indexOf("telur"));
    expect(html.indexOf("telur")).toBeLessThan(html.indexOf("wortel"));
    expect(html).toContain("128%"); // wortel 500/392
    expect(html).toContain("−780 kg");
    expect(html).toContain("stok layak 300 kg");
    expect(html).toContain("Kebutuhan");
  });

  it("ahli gizi: default Kesegaran dan urut menurut stok segar", () => {
    const html = render("sppg_nutritionist");
    expect(html).toContain("Kesegaran");
    expect(html).toContain("stok segar di bawah kebutuhan");
    // telur hanya 200/1080 segar = 19%; beras 0%
    expect(html.indexOf("beras")).toBeLessThan(html.indexOf("telur"));
    expect(html).toContain("1 batch ≤48 jam");
  });

  it("sumber data ditulis apa adanya, bukan jam sinkron sebagai tanggal data", () => {
    const html = renderToStaticMarkup(
      <SupplyAdequacyChart
        rows={ROWS}
        role="sppg_head"
        locationName="Jakarta"
        updatedAt={NOW.getTime()}
        now={NOW}
        sourceNote="Data per 8 Okt 2026"
      />
    );
    expect(html).toContain("Data per 8 Okt 2026");
    expect(html).toContain("dihitung");
  });

  it("tidak mengarang angka saat kebutuhan belum tercatat", () => {
    const rows = buildAdequacyRows({
      commodities: ["telur"],
      byCommodity: { telur: [] },
      batches: BATCHES,
      location: "Jakarta",
      now: NOW,
    });
    const html = render("sppg_head", rows);
    expect(html).toContain("kebutuhan belum tercatat");
    expect(html).not.toContain("NaN");
    expect(html).not.toContain("0%");
  });

  it("menandai pasokan tercatat yang tidak punya baris batch", () => {
    const rows = buildAdequacyRows({
      commodities: ["telur"],
      byCommodity: MAP,
      batches: [],
      location: "Jakarta",
      now: NOW,
    });
    const html = render("sppg_head", rows);
    expect(html).toContain("tanpa batch");
    expect(html).toContain("0 kg layak");
  });

  it("Kesegaran hanya menghitung stok yang masih >48 jam", () => {
    const rows = buildAdequacyRows({
      commodities: ["ayam"],
      byCommodity: MAP,
      batches: [
        batchesFor("ayam", 80, 1), // ≤48 jam: layak, tetapi bukan segar
        {
          ...batchesFor("ayam", 120, 4),
          safety_status: "fail", // tidak layak
        },
      ],
      location: "Jakarta",
      now: NOW,
    });
    const html = render("sppg_nutritionist", rows);
    expect(html).toContain("0 kg segar · 80 kg layak");
    expect(html).toContain("−308 kg");
    expect(html).toContain("0 kg / 308 kg");
  });

  it("tanpa baris sama sekali → tidak merender kartu kosong", () => {
    expect(render("sppg_head", [])).toBe("");
  });
});
