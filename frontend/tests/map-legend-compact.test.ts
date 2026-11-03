import { describe, expect, it } from "vitest";

import {
  STATUS_LEGEND,
  compactLegendItems,
  legendMarkClass,
} from "../lib/map-legend-compact";

/**
 * Baris legenda ringkas di bawah kanvas (celah C2, riset §5;
 * `docs/research/peta-ui-industri.md`).
 *
 * Kenapa fungsi murni: isi baris ini adalah ATURAN, bukan tata letak —
 * "keterangan warna untuk lapisan yang sedang mati adalah informasi palsu"
 * (aturan lama kotak Info map, tetap berlaku). Aturan itu harus bisa diuji
 * tanpa merender peta.
 */
const JALUR = [
  { tone: "done", label: "Sudah tiba" },
  { tone: "todo", label: "Sisa perjalanan" },
];
const PEMASOK = [
  { tone: "ok", label: "Pemasok" },
  { tone: "low", label: "Keandalan rendah" },
];

describe("compactLegendItems — isi baris legenda ringkas", () => {
  it("status lokasi selalu ada: pin SPPG tidak pernah bisa dimatikan", () => {
    const hasil = compactLegendItems({ jalur: null, pemasok: null });
    expect(hasil.map((butir) => butir.label)).toEqual(
      STATUS_LEGEND.map((butir) => butir.label)
    );
    expect(hasil.every((butir) => butir.jenis === "titik")).toBe(true);
  });

  it("butir jalur hanya ikut saat lapisannya hidup — nada & label dari masukan", () => {
    const hidup = compactLegendItems({ jalur: JALUR, pemasok: null });
    expect(
      hidup.filter((butir) => butir.jenis === "garis").map((butir) => butir.label)
    ).toEqual(["Sudah tiba", "Sisa perjalanan"]);

    // `null` = lapisan tidak ada, `[]` = tidak ada nada yang dipakai.
    for (const mati of [null, []]) {
      expect(
        compactLegendItems({ jalur: mati, pemasok: null }).filter(
          (butir) => butir.jenis === "garis"
        )
      ).toHaveLength(0);
    }
  });

  it("butir pemasok hanya ikut saat lapisannya hidup", () => {
    expect(
      compactLegendItems({ jalur: null, pemasok: PEMASOK }).map((butir) => butir.jenis)
    ).toEqual(["titik", "titik", "titik", "bentuk", "bentuk"]);
    expect(compactLegendItems({ jalur: null, pemasok: [] })).toHaveLength(
      STATUS_LEGEND.length
    );
  });

  it("urutan tetap: status lokasi → jalur kiriman → pemasok", () => {
    const jenis = compactLegendItems({ jalur: JALUR, pemasok: PEMASOK }).map(
      (butir) => butir.jenis
    );
    expect(jenis).toEqual([
      "titik",
      "titik",
      "titik",
      "garis",
      "garis",
      "bentuk",
      "bentuk",
    ]);
  });

  it("id unik, stabil, dan menyebut asalnya", () => {
    const hasil = compactLegendItems({ jalur: JALUR, pemasok: PEMASOK });
    const id = hasil.map((butir) => butir.id);
    expect(new Set(id).size).toBe(id.length);
    expect(id).toContain("status:surplus");
    expect(id).toContain("jalur:done");
    expect(id).toContain("pemasok:low");
  });

  it("butir tanpa label dibuang — tidak ada pil kosong di baris legenda", () => {
    const hasil = compactLegendItems({
      jalur: [{ tone: "done", label: "   " }],
      pemasok: [{ tone: "ok", label: "" }],
    });
    expect(hasil).toHaveLength(STATUS_LEGEND.length);
  });
});

describe("legendMarkClass — kelas tanda legenda", () => {
  it("memakai kelas kotak Info map yang sama (satu bahasa visual, tidak ada gaya ganda)", () => {
    const titik = compactLegendItems({ jalur: null, pemasok: null })[0];
    expect(legendMarkClass(titik)).toEqual([
      "map-legend-box-dot",
      "map-legend-box-dot-surplus",
    ]);
  });

  it("jalur menyebut ARTINYA, bukan cuma warnanya — padat vs putus-putus (K1)", () => {
    const jalur = compactLegendItems({
      jalur: [
        { tone: "ok", label: "Sudah ditempuh", gaya: "padat" as const },
        { tone: "ok", label: "Sisa perjalanan (perkiraan)", gaya: "putus" as const },
      ],
      pemasok: null,
    }).filter((butir) => butir.jenis === "garis");

    expect(jalur.map((butir) => butir.gaya)).toEqual(["padat", "putus"]);
    expect(legendMarkClass(jalur[0])).toEqual([
      "map-legend-line",
      "map-legend-line-ok",
      "map-legend-line-padat",
    ]);
    expect(legendMarkClass(jalur[1])).toContain("map-legend-line-putus");
    // Id stabil ikut menyebut gaya supaya dua butir bernada sama tidak bertabrakan.
    expect(jalur[0].id).not.toBe(jalur[1].id);
  });

  it("garis & bentuk memakai kelas yang sudah ada untuk nada masing-masing", () => {
    expect(legendMarkClass({ id: "jalur:todo", jenis: "garis", nada: "todo", label: "x" })).toEqual([
      "map-legend-line",
      "map-legend-line-todo",
    ]);
    expect(legendMarkClass({ id: "pemasok:far", jenis: "bentuk", nada: "far", label: "x" })).toEqual([
      "map-legend-box-shape",
      "map-legend-box-shape-far",
    ]);
  });
});
