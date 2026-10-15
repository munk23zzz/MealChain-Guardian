// Kontrak halaman "Keamanan Pangan" (halaman sidebar acuan /compliance).
import { describe, expect, it } from "vitest";

import {
  hoursLabel,
  hoursLeft,
  safetyLabel,
  safetyRows,
  safetySummary,
  safetyTone,
} from "../lib/food-safety";

const NOW = new Date("2026-10-11T06:00:00Z");

const BATCHES = [
  {
    id: "b1",
    location: "Cianjur",
    commodity: "telur",
    quantity_kg: 400,
    safety_status: "pass",
    freshness_score: 0.69,
    usable_until: "2026-10-11T18:00:00Z",
  },
  {
    id: "b2",
    location: "Surabaya",
    commodity: "ayam",
    quantity_kg: 120,
    safety_status: "fail",
    freshness_score: null,
    usable_until: null,
  },
  { id: "b3", location: "Bogor", commodity: "telur", quantity_kg: 50, safety_status: "needs_verification" },
];

describe("safetyLabel / safetyTone", () => {
  it("kosakata backend dibaca manusia", () => {
    expect(safetyLabel("pass")).toBe("Aman");
    expect(safetyLabel("fail")).toBe("Gagal uji");
    expect(safetyLabel("needs_verification")).toBe("Perlu verifikasi");
    expect(safetyLabel("pending")).toBe("Belum diuji");
  });

  it("status asing tetap ditulis apa adanya, kosong jadi '—'", () => {
    expect(safetyLabel("quarantine")).toBe("quarantine");
    expect(safetyLabel(null)).toBe("—");
  });

  it("warna mengikuti makna: fail merah, needs_verification kuning, pass hijau", () => {
    expect(safetyTone("fail")).toBe("danger");
    expect(safetyTone("needs_verification")).toBe("warn");
    expect(safetyTone("pass")).toBe("ok");
    expect(safetyTone("")).toBe("muted");
  });
});

describe("hoursLeft / hoursLabel", () => {
  it("12 jam ke depan ditulis 'lagi', yang sudah lewat 'lewat'", () => {
    expect(hoursLeft("2026-10-11T18:00:00Z", NOW)).toBe(12);
    expect(hoursLabel(12)).toBe("12 jam lagi");
    expect(hoursLabel(-3)).toBe("lewat 3 jam");
    expect(hoursLabel(null)).toBe("—");
  });

  it("tanggal tak terbaca → null (bukan 0)", () => {
    expect(hoursLeft(null, NOW)).toBe(null);
    expect(hoursLeft("bukan tanggal", NOW)).toBe(null);
  });

  it("lebih dari sehari ditulis hari + jam", () => {
    expect(hoursLabel(30)).toBe("1 hari 6 jam lagi");
  });
});

describe("safetyRows", () => {
  it("kolom terisi dari data, yang kosong '—' (tanpa angka karangan)", () => {
    const rows = safetyRows(BATCHES, NOW);
    expect(rows).toHaveLength(3);
    expect(rows[0]).toMatchObject({
      location: "Cianjur",
      commodity: "telur",
      kg: 400,
      statusLabel: "Aman",
      freshness: "69%",
      hoursLabel: "12 jam lagi",
    });
    expect(rows[1].kg).toBe(120);
    expect(rows[1].statusLabel).toBe("Gagal uji");
    expect(rows[1].freshness).toBe("—");
    expect(rows[1].usableUntil).toBe("—");
    expect(rows[2].statusLabel).toBe("Perlu verifikasi");
  });

  it("daftar bukan array → halaman kosong, bukan error", () => {
    expect(safetyRows(null, NOW)).toEqual([]);
    expect(safetyRows({ batches: [] }, NOW)).toEqual([]);
  });
});

describe("safetySummary", () => {
  it("menghitung aman/gagal/perlu verifikasi + kilogram batch gagal", () => {
    const summary = safetySummary(BATCHES);
    expect(summary).toMatchObject({
      total: 3,
      safe: 1,
      failed: 1,
      needsVerification: 1,
      unchecked: 0,
      failedKg: 120,
      failedLocations: ["Surabaya"],
      hasFail: true,
    });
  });

  it("tanpa batch gagal: failedKg null (bukan 0 kg palsu)", () => {
    const summary = safetySummary([{ safety_status: "pass", quantity_kg: 10 }]);
    expect(summary.failed).toBe(0);
    expect(summary.failedKg).toBe(null);
    expect(summary.hasFail).toBe(false);
  });

});
