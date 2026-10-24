// Tes kalimat cakupan ledger (audit A4). Server tetap sumber angka; helper ini
// hanya memastikan UI tidak menyembunyikan blok yatim di balik "rantai valid".

import { describe, expect, it } from "vitest";

import { coverageNote } from "../lib/ledger";

describe("coverageNote (keterkaitan blok ledger)", () => {
  it("menyebut jumlah blok tertaut saat ada blok yatim", () => {
    const note = coverageNote({
      valid: true,
      blocks: 8732,
      entity_blocks: 8732,
      linked_blocks: 11,
      orphan_blocks: 8721,
      coverage_warning: "rantai utuh, tetapi 8721 blok menunjuk entitas yang sudah tidak ada",
    });
    expect(note).toContain("8721 blok");
    expect(note).toContain("(11 dari 8732 blok masih tertaut)");
  });

  it("null saat tidak ada blok yatim — jangan mengarang peringatan", () => {
    expect(
      coverageNote({ valid: true, entity_blocks: 5, linked_blocks: 5, orphan_blocks: 0 })
    ).toBeNull();
    expect(coverageNote(null)).toBeNull();
  });

  it("menyebut blok arsip generasi lama tanpa menuduhnya sebagai kerusakan", () => {
    const note = coverageNote({
      valid: true,
      blocks: 1541,
      generation: 2,
      entity_blocks: 40,
      linked_blocks: 40,
      orphan_blocks: 0,
      archived_blocks: 1501,
      coverage_warning: null,
    });
    expect(note).toBe(
      "1501 blok generasi lama diarsipkan (rantai tetap terverifikasi)"
    );
  });

  it("tetap menampilkan peringatan walau angka tidak lengkap", () => {
    expect(coverageNote({ coverage_warning: "rantai utuh, tetapi 2 blok yatim" })).toBe(
      "rantai utuh, tetapi 2 blok yatim"
    );
  });
});
