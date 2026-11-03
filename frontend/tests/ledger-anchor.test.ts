// Fase 11 MG, butir 2: kalimat status anchor eksternal untuk panel Integritas.
//
// Kontrak: "belum ada checkpoint" tidak boleh tampil sebagai aman, dan
// kecocokan yang dilaporkan harus membawa tinggi blok yang benar-benar
// dibandingkan (bukan angka karangan).

import { describe, expect, it } from "vitest";

import { anchorNote } from "../lib/ledger";

describe("anchorNote", () => {
  it("menyebut blok yang cocok dengan checkpoint", () => {
    const note = anchorNote({
      valid: true,
      anchor: { configured: true, match: true, height: 42, reason: null },
    });
    expect(note).toBe("Cocok dengan checkpoint eksternal pada blok 42.");
  });

  it("menyatakan ketidakcocokan sebagai peringatan, bukan aman", () => {
    const note = anchorNote({
      valid: true,
      anchor: {
        configured: true,
        match: false,
        height: 10,
        reason: "hash blok 10 di database berbeda dari anchor",
      },
    });
    expect(note).toContain("TIDAK cocok");
    expect(note).toContain("ditulis ulang");
    expect(note).toContain("hash blok 10");
  });

  it("checkpoint yang belum dibuat dilaporkan jujur, bukan cocok", () => {
    const note = anchorNote({
      valid: true,
      anchor: { configured: true, match: null, reason: null },
    });
    expect(note).toContain("belum dibuat");
    expect(note).not.toContain("Cocok");
  });

  it("anchor yang dimatikan disebut sebagai dimatikan", () => {
    const note = anchorNote({
      valid: true,
      anchor: { configured: false, match: null, reason: null },
    });
    expect(note).toContain("Anchor eksternal belum dipasang");
  });

  it("tanpa field anchor tidak mengarang kalimat", () => {
    expect(anchorNote({ valid: true })).toBeNull();
    expect(anchorNote(null)).toBeNull();
  });
});
