// Kejujuran angka peta (PLAN-023 · 2026-10-17) — sisi FRONTEND.
//
// Aturan yang dipaku di sini:
//   1. Angka `0` yang TERUKUR tetap tampil `0 kg` (tidak diganti "—" maupun
//      pesan galat) — aturan tampilan repo tidak berubah.
//   2. Angka `0` yang berasal dari baris yang TIDAK ADA tidak boleh dihitung
//      sebagai fakta: lokasi tanpa catatan permintaan (nyata: Bandung &
//      Cianjur untuk telur) tidak boleh lagi muncul sebagai penyumbang surplus
//      di ringkasan maupun rencana alokasi.
//   3. Nilai tanpa penanda (data/panggilan lama) diperlakukan seperti sebelumnya
//      (terukur) supaya perubahan ini tidak mengubah perilaku fixture lama.
import { describe, expect, it } from "vitest";

import { balanceForLocation } from "../lib/food-safety";
import { dataSourceNote, formatBalanceGap, formatKg } from "../lib/overview-format";
import { allocationPlan, surplusSummary } from "../lib/surplus";
import { networkState } from "../lib/topbar";

const TELUR = [
  {
    location: "Bandung",
    supply_kg: 386.4,
    demand_kg: 0,
    surplus_kg: 386.4,
    shortage_kg: 0,
    status: "surplus",
    supply_state: "terukur",
    demand_state: "tidak_ada_baris",
  },
  {
    location: "Cianjur",
    supply_kg: 1457.4,
    demand_kg: 0,
    surplus_kg: 1457.4,
    shortage_kg: 0,
    status: "surplus",
    supply_state: "terukur",
    demand_state: "tidak_ada_baris",
  },
  {
    location: "Bogor",
    supply_kg: 843.9,
    demand_kg: 308,
    surplus_kg: 535.9,
    shortage_kg: 0,
    status: "surplus",
    supply_state: "terukur",
    demand_state: "terukur",
  },
  {
    location: "Jakarta",
    supply_kg: 314.2,
    demand_kg: 1080,
    surplus_kg: 0,
    shortage_kg: 765.8,
    status: "shortage",
    supply_state: "terukur",
    demand_state: "terukur",
  },
];

describe("surplusSummary — angka dari baris yang tidak ada bukan fakta", () => {
  it("lokasi tanpa catatan permintaan tidak dihitung sebagai surplus", () => {
    const summary = surplusSummary(TELUR);
    // Hanya Bogor yang surplus-nya berdiri di atas permintaan terukur.
    expect(summary.surplusCount).toBe(1);
    expect(summary.surplusKg).toBe(535.9);
    // Jakarta tetap kekurangan nyata (pasokan & permintaan terukur).
    expect(summary.shortageCount).toBe(1);
    expect(summary.shortageKg).toBe(765.8);
    // Dua lokasi dilaporkan sebagai "tanpa catatan", bukan dibuang diam-diam.
    expect(summary.unmeasuredCount).toBe(2);
  });

  it("sisi cermin: pasokan tanpa catatan tidak dihitung sebagai kekurangan", () => {
    const summary = surplusSummary([
      {
        location: "X",
        supply_kg: 0,
        demand_kg: 500,
        shortage_kg: 500,
        surplus_kg: 0,
        status: "shortage",
        supply_state: "tidak_ada_baris",
        demand_state: "terukur",
      },
    ]);
    expect(summary.shortageCount).toBe(0);
    expect(summary.shortageKg).toBe(null);
    expect(summary.unmeasuredCount).toBe(1);
  });

  it("nol yang TERUKUR tetap dihitung (0 kg bukan 'tidak ada data')", () => {
    const summary = surplusSummary([
      {
        location: "Y",
        supply_kg: 200,
        demand_kg: 0,
        surplus_kg: 200,
        shortage_kg: 0,
        status: "surplus",
        supply_state: "terukur",
        demand_state: "terukur",
      },
      {
        location: "Z",
        supply_kg: 100,
        demand_kg: 100,
        surplus_kg: 0,
        shortage_kg: 0,
        status: "balanced",
        supply_state: "terukur",
        demand_state: "terukur",
      },
    ]);
    expect(summary.surplusCount).toBe(1);
    expect(summary.surplusKg).toBe(200);
    expect(summary.balancedCount).toBe(1);
    expect(summary.unmeasuredCount).toBe(0);
  });

  it("data lama tanpa penanda tetap diperlakukan seperti sebelumnya", () => {
    const summary = surplusSummary([
      { location: "Lama", surplus_kg: 50, shortage_kg: 0, status: "surplus" },
    ]);
    expect(summary.surplusCount).toBe(1);
    expect(summary.surplusKg).toBe(50);
    expect(summary.unmeasuredCount).toBe(0);
  });
});

describe("allocationPlan — tidak mengalirkan surplus yang tidak terukur", () => {
  it("Bandung/Cianjur tidak menjadi pemasok (permintaannya tak tercatat)", () => {
    const plan = allocationPlan(TELUR, 5);
    expect(plan.length).toBeGreaterThan(0);
    expect(plan.map((row) => row.from)).not.toContain("Bandung");
    expect(plan.map((row) => row.from)).not.toContain("Cianjur");
    expect(plan[0]).toMatchObject({ from: "Bogor", to: "Jakarta", kg: 535.9 });
  });
});

describe("tampilan angka nol & asal nilai", () => {
  it("nol tetap dirender `0 kg`, tidak pernah jadi pesan galat", () => {
    expect(formatKg(0)).toBe("0 kg");
    expect(formatKg("0")).toBe("0 kg");
    // Nilai yang memang tidak ada tetap memakai aturan lama: "—".
    expect(formatKg(null)).toBe("—");
  });

  it("status surplus dengan angka nol tetap berbunyi `lebih 0 kg`", () => {
    expect(
      formatBalanceGap({ location: "Z", status: "surplus", surplus_kg: 0 })
    ).toBe("lebih 0 kg");
  });

  it("catatan asal nilai menyebut sisi yang tidak tercatat", () => {
    expect(
      dataSourceNote({ location: "Bandung", demand_state: "tidak_ada_baris" })
    ).toBe("permintaan tanpa catatan");
    expect(
      dataSourceNote({
        location: "X",
        supply_state: "tidak_ada_baris",
        demand_state: "tidak_ada_baris",
      })
    ).toBe("pasokan & permintaan tanpa catatan");
    expect(
      dataSourceNote({
        location: "Bogor",
        supply_state: "terukur",
        demand_state: "terukur",
      })
    ).toBe(null);
    // data lama tanpa penanda → tidak mengklaim apa pun
    expect(dataSourceNote({ location: "Lama" })).toBe(null);
  });
});

describe("turunan lain yang dulu menghitung angka pengisian sebagai fakta", () => {
  it("agregat kebutuhan-vs-kiriman (pengawas) hanya menjumlah baris lengkap", () => {
    const slice = balanceForLocation({ commodity: "telur", locations: TELUR }, null);
    expect(slice).not.toBe(null);
    // Bandung & Cianjur (permintaan tak tercatat) tidak ikut dijumlah.
    expect(slice?.demandKg).toBe(308 + 1080);
    expect(slice?.supplyKg).toBe(843.9 + 314.2);
    expect(slice?.surplusKg).toBe(535.9);
    expect(slice?.shortageKg).toBe(765.8);
    expect(slice?.isAggregate).toBe(true);
  });

  it("lokasi sendiri dengan sisi tak tercatat → nilainya null, bukan 0 karangan", () => {
    const slice = balanceForLocation({ commodity: "telur", locations: TELUR }, "Bandung");
    expect(slice?.locationLabel).toBe("Bandung");
    expect(slice?.demandKg).toBe(null);
    expect(slice?.surplusKg).toBe(null);
    expect(slice?.shortageKg).toBe(null);
  });

  it("lokasi sendiri yang lengkap tetap dibaca apa adanya", () => {
    const slice = balanceForLocation({ commodity: "telur", locations: TELUR }, "Jakarta");
    expect(slice?.demandKg).toBe(1080);
    expect(slice?.shortageKg).toBe(765.8);
  });

  it("chip top bar tidak mengklaim shortage dari pasokan yang tak tercatat", () => {
    const state = networkState([
      { location: "X", status: "shortage", supply_state: "tidak_ada_baris" },
      { location: "Jakarta", status: "shortage", supply_state: "terukur" },
    ]);
    expect(state.label).toBe("1 lokasi shortage (2 terpantau)");
  });
});
