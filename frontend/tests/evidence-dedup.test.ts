// F1 redesign Decision & Evidence — kontrak "satu angka, satu tempat".
//
// Aturan yang dikunci di sini (lihat _qa/rencana-decision-evidence-v3.md §4.2):
// angka yang sudah tampil di strip metrik TIDAK diulang di kartu fakta. Tes ini
// sengaja mengubah kontrak lama (Jumlah/Biaya aman terkirim/Persetujuan pindah
// keluar dari kartu) — perubahan yang disengaja, bukan pelonggaran aturan.

import { describe, expect, it } from "vitest";

import { approvalFacts, costFacts, decisionFacts, decisionMetrics } from "../lib/evidence";

const KEPUTUSAN = {
  decision_id: "d-1",
  quantity_kg: 780,
  target_location: "Jakarta",
  source_location: "Bogor",
  commodity: "telur",
  iteration: 2,
  expires_at: "2026-10-18T12:00:00Z",
  summary: {
    quantity_kg: 780,
    safe_delivered_cost: 14787096,
    target_location: "Jakarta",
    source_location: "Bogor",
    commodity: "telur",
    cost_breakdown: { purchase: 15720000, logistics: 458000, note: "seed demo" },
  },
};

const SEKARANG = new Date("2026-10-18T10:00:00Z");

describe("strip metrik", () => {
  it("memuat tenggat, bukan tujuan (tujuan sudah ada di judul)", () => {
    const label = decisionMetrics(KEPUTUSAN, KEPUTUSAN.summary, SEKARANG).map((m) => m.label);
    expect(label).toContain("Tenggat");
    expect(label).not.toContain("Tujuan");
  });

  it("tanpa jam acuan, tenggat ditulis '—' (baris tetap ada, jam tidak dikarang)", () => {
    const rows = decisionMetrics(KEPUTUSAN, KEPUTUSAN.summary);
    expect(rows.map((m) => m.label)).toEqual([
      "Kuantitas",
      "Biaya aman terkirim",
      "Selisih dari harga beli",
      "Tenggat",
    ]);
    expect(rows.find((m) => m.label === "Tenggat")?.value).toBe("—");
  });

  it("tiga angka inti tetap ada", () => {
    const rows = decisionMetrics(KEPUTUSAN, KEPUTUSAN.summary, SEKARANG);
    expect(rows.find((r) => r.label === "Kuantitas")?.value).toBe("780 kg");
    expect(rows.find((r) => r.label === "Biaya aman terkirim")?.value).toContain("14.787.096");
  });
});

describe("kartu fakta tidak mengulang strip", () => {
  it("Identitas tidak memuat Jumlah maupun Tenggat", () => {
    const label = decisionFacts(KEPUTUSAN, SEKARANG).map((r) => r.label);
    expect(label).not.toContain("Jumlah");
    expect(label).not.toContain("Tenggat");
    expect(label).toContain("Rute");
  });

  it("Biaya memuat rincian, bukan total (total ada di strip)", () => {
    const label = costFacts(KEPUTUSAN).map((r) => r.label);
    expect(label).not.toContain("Biaya aman terkirim");
    expect(label).toEqual(expect.arrayContaining(["Harga beli", "Logistik"]));
  });

  it("Governance tidak mengulang hitungan persetujuan (stepper sudah menyebutnya)", () => {
    const ringkas = {
      approvals: [{ approved: true }],
      approval_requirement: { min_approvals: 2, requirement: "minimal 2 persetujuan" },
    };
    const label = approvalFacts(ringkas).map((r) => r.label);
    expect(label).not.toContain("Persetujuan");
    expect(label).toContain("Syarat persetujuan");
  });
});
