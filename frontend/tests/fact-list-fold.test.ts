// FactList — dua cara menyingkat kartu fakta:
//   collapseEmpty : baris "—" (tidak ada data) masuk rincian
//   foldAfter     : baris TERISI di atas ambang masuk rincian (isi tetap ada)
//
// Kenapa dipisah labelnya: "belum ada datanya" jujur untuk baris kosong, tetapi
// menyesatkan untuk baris yang datanya ada. `hiddenRowsLabel` menulis
// "rincian lainnya" supaya pembaca tahu yang disembunyikan bukan kekosongan.

import { describe, expect, it } from "vitest";

import { hiddenRowsLabel } from "../lib/evidence";

describe("hiddenRowsLabel", () => {
  it("menyebut jumlah, bukan 'detail'", () => {
    expect(hiddenRowsLabel(1)).toBe("1 rincian lainnya");
    expect(hiddenRowsLabel(3)).toBe("3 rincian lainnya");
  });

  it("nol/negatif/tidak masuk akal → string kosong (jangan bikin tombol kosong)", () => {
    expect(hiddenRowsLabel(0)).toBe("");
    expect(hiddenRowsLabel(-2)).toBe("");
    expect(hiddenRowsLabel(Number.NaN)).toBe("");
  });
});
