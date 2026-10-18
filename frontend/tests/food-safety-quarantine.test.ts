// Karantina di layar "Keamanan Pangan": label, nada, dan ringkasan.
import { describe, expect, it } from "vitest";

import {
  quarantineLabel,
  quarantineStatus,
  quarantineTone,
  safetyRows,
  safetySummary,
} from "../lib/food-safety";

const BATCH_TAHAN = {
  id: "b-1",
  location: "Jakarta",
  commodity: "telur",
  quantity_kg: 120,
  safety_status: "needs_verification",
  freshness_score: 0.9,
  usable_until: null,
  quarantine_status: "quarantined",
};

const BATCH_BEBAS = { ...BATCH_TAHAN, id: "b-2", quarantine_status: "none" };

describe("quarantineStatus", () => {
  it("membaca empat status sah", () => {
    expect(quarantineStatus("none")).toBe("none");
    expect(quarantineStatus("quarantined")).toBe("quarantined");
    expect(quarantineStatus("released")).toBe("released");
    expect(quarantineStatus("failed")).toBe("failed");
  });

  it("data lama tanpa kolom karantina dianggap bebas", () => {
    expect(quarantineStatus(undefined)).toBe("none");
    expect(quarantineStatus(null)).toBe("none");
    expect(quarantineStatus("")).toBe("none");
  });

  it("nilai tak dikenal tidak diteruskan mentah ke layar", () => {
    expect(quarantineStatus("entah")).toBe("none");
  });
});

describe("quarantineLabel / tone", () => {
  it("hanya status yang perlu perhatian diberi label", () => {
    expect(quarantineLabel("none")).toBe("");
    expect(quarantineLabel("quarantined")).toBe("Ditahan");
    expect(quarantineLabel("released")).toBe("Dilepas");
    expect(quarantineLabel("failed")).toBe("Gagal");
  });

  it("batch ditahan diberi nada bahaya, bukan aman", () => {
    expect(quarantineTone("quarantined")).toBe("danger");
    expect(quarantineTone("failed")).toBe("danger");
    expect(quarantineTone("released")).toBe("muted");
    expect(quarantineTone("none")).toBe("muted");
  });
});

describe("safetyRows", () => {
  it("membawa status karantina per baris", () => {
    const rows = safetyRows([BATCH_TAHAN, BATCH_BEBAS], new Date("2026-10-18T00:00:00Z"));
    expect(rows[0].quarantine).toBe("quarantined");
    expect(rows[0].quarantineLabel).toBe("Ditahan");
    expect(rows[1].quarantine).toBe("none");
    expect(rows[1].quarantineLabel).toBe("");
  });
});

describe("safetySummary", () => {
  it("batch yang ditahan tidak dihitung sebagai aman", () => {
    const s = safetySummary([BATCH_TAHAN, BATCH_BEBAS]);
    // BATCH_BEBAS: needs_verification → belum "aman" juga, tapi bukan karantina.
    expect(s.quarantined).toBe(1);
    expect(s.quarantinedKg).toBe(120);
    expect(s.safe).toBe(0);
  });

  it("menghitung kilogram yang ditahan terpisah dari kilogram gagal", () => {
    const gagal = { ...BATCH_BEBAS, id: "b-3", safety_status: "fail", quantity_kg: 40 };
    const s = safetySummary([BATCH_TAHAN, gagal]);
    expect(s.failed).toBe(1);
    expect(s.failedKg).toBe(40);
    expect(s.quarantinedKg).toBe(120);
  });
});
