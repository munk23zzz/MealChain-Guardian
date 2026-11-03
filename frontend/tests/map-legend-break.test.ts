import { describe, expect, it } from "vitest";

import { compactLegendItems, legendBreakIndexes } from "../lib/map-legend-compact";

/**
 * Pemenggalan baris legenda ringkas (permintaan pemilik 2026-10-19).
 *
 * Kenapa aturan ini hidup di lib murni: legenda memakai satu baris `flex-wrap`,
 * jadi di mana ia patah ditentukan lebar layar — bukan makna. Akibatnya kelompok
 * pemasok (5 butir) bisa terbelah: "Pemasok · Keandalan rendah · Dikecualikan"
 * menempel di ujung baris 1, sementara "Di luar jangkauan · Stok layak"
 * menggantung sendirian di baris 2. Pemilik meminta kelompok pemasok UTUH di
 * baris 2, sebaris dengan tiga butir pemasok lainnya.
 *
 * Aturan: pemenggalan HANYA di depan butir pertama kelompok pemasok. Baris 1
 * tetap milik status lokasi + jalur kiriman (keduanya berbicara tentang peta,
 * bukan tentang pemasok).
 */
const JALUR = [
  { tone: "done", label: "Sudah ditempuh" },
  { tone: "todo", label: "Sisa perjalanan (perkiraan)" },
];
const PEMASOK = [
  { tone: "ok", label: "Pemasok" },
  { tone: "low", label: "Keandalan rendah" },
  { tone: "excluded", label: "Dikecualikan" },
  { tone: "far", label: "Di luar jangkauan" },
  { tone: "shipping", label: "Stok layak" },
];

describe("legendBreakIndexes — di mana baris legenda dipenggal", () => {
  it("memenggal tepat sebelum butir pemasok pertama", () => {
    const butir = compactLegendItems({ jalur: JALUR, pemasok: PEMASOK });
    const pemasokPertama = butir.findIndex((item) => item.id.startsWith("pemasok:"));
    expect(pemasokPertama).toBeGreaterThan(0);
    expect(legendBreakIndexes(butir)).toEqual([pemasokPertama]);
    expect(butir[pemasokPertama].label).toBe("Pemasok");
  });

  it("tanpa lapisan pemasok tidak ada pemenggalan (satu baris seperti sebelumnya)", () => {
    for (const mati of [null, []] as const) {
      const butir = compactLegendItems({ jalur: JALUR, pemasok: mati });
      expect(butir.every((item) => !item.id.startsWith("pemasok:"))).toBe(true);
      expect(legendBreakIndexes(butir)).toEqual([]);
    }
  });

  it("status lokasi + jalur tetap berbagi baris 1", () => {
    const butir = compactLegendItems({ jalur: JALUR, pemasok: PEMASOK });
    const [penggal] = legendBreakIndexes(butir);
    const barisSatu = butir.slice(0, penggal).map((item) => item.id);
    expect(barisSatu).toEqual([
      "status:surplus",
      "status:balanced",
      "status:shortage",
      "jalur:done",
      "jalur:todo",
    ]);
  });

  it("kelompok pemasok utuh: kelima butir berada sesudah pemenggalan", () => {
    const butir = compactLegendItems({ jalur: JALUR, pemasok: PEMASOK });
    const [penggal] = legendBreakIndexes(butir);
    const barisDua = butir.slice(penggal).map((item) => item.label);
    expect(barisDua).toEqual([
      "Pemasok",
      "Keandalan rendah",
      "Dikecualikan",
      "Di luar jangkauan",
      "Stok layak",
    ]);
  });

  it("tidak memenggal daftar kosong atau satu kelompok saja", () => {
    expect(legendBreakIndexes([])).toEqual([]);
    expect(legendBreakIndexes(compactLegendItems({ jalur: null, pemasok: null }))).toEqual([]);
  });
});
