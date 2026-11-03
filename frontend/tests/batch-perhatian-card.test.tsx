// Kontrak render kartu "Batch perlu perhatian" (29 Okt 2026).
//
// Bentuk yang dijaga: SATU tabel, bukan tiga kartu bertumpuk. Teks sedikit —
// angka + satu alasan pendek per baris; alasan utuh hanya di tooltip.
// Kategori yang jumlahnya nol tidak dicetak.

import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import BatchPerhatianCard from "../components/BatchPerhatianCard";
import type { EvidenceRow, SafetyRow } from "../lib/food-safety";

function safety(over: Partial<SafetyRow> & { id: string }): SafetyRow {
  return {
    id: over.id,
    location: over.location ?? "JKT",
    commodity: over.commodity ?? "telur",
    kg: 100,
    statusLabel: "Lolos uji",
    tone: over.tone ?? "ok",
    freshness: over.freshness ?? "80%",
    freshnessScore: over.freshnessScore ?? 0.8,
    usableUntil: "7 Nov 2026",
    hoursLeft: over.hoursLeft ?? 240,
    hoursLabel: over.hoursLabel ?? "10 hari",
    quarantine: "none",
    quarantineLabel: "—",
    receiptStatus: null,
    safetyStatus: "passed",
  } as SafetyRow;
}

function bukti(over: Partial<EvidenceRow> & { id: string }): EvidenceRow {
  return {
    id: over.id,
    commodity: over.commodity ?? "telur",
    observation: "observed",
    observationLabel: "Teramati",
    state: over.state ?? "sufficient",
    stateLabel: over.stateLabel ?? "Bukti cukup",
    tone: over.tone ?? "ok",
    sufficient: over.sufficient ?? true,
    sampleCount: 4,
    observedAt: null,
    source: "demo",
    sourceLabel: over.sourceLabel ?? "log simulasi",
    profileVersion: "coldchain-v3",
    policyKind: "simulated_policy",
    coldChainRequired: true,
    reasons: over.reasons ?? [],
  };
}

const safetyRows: SafetyRow[] = [
  safety({ id: "a" }),
  safety({ id: "b", commodity: "ayam", hoursLeft: 20, hoursLabel: "20 jam" }),
  safety({ id: "c", commodity: "wortel", freshnessScore: 0.32, freshness: "32%" }),
];

const evidenceRows: EvidenceRow[] = [
  bukti({ id: "a" }),
  bukti({
    id: "b",
    commodity: "ayam",
    state: "insufficient",
    stateLabel: "Bukti kurang",
    tone: "warn",
    sufficient: false,
    reasons: ["sampel terakhir 1484 menit lalu, lewat batas 360 menit"],
  }),
  bukti({ id: "c", commodity: "wortel" }),
];

const summary = {
  total: 3,
  sufficient: 2,
  insufficient: 1,
  ambiguous: 0,
  unknown: 0,
  perluVerifikasi: 1,
};

function render(props: Partial<Parameters<typeof BatchPerhatianCard>[0]> = {}) {
  return renderToStaticMarkup(
    <BatchPerhatianCard safetyRows={safetyRows} evidence={evidenceRows} summary={summary} {...props} />
  );
}

describe("kartu Batch perlu perhatian", () => {
  it("satu tabel dengan lima kolom yang menyebut pertanyaannya", () => {
    const html = render();
    expect(html).toContain("<table");
    for (const kolom of ["Batch", "Bukti suhu", "Sisa layak", "Segar", "Kenapa"]) {
      expect(html).toContain(`>${kolom}<`);
    }
  });

  it("kepala kartu: judul + satu rasio, bukan empat angka", () => {
    const html = render();
    expect(html).toContain("Batch perlu perhatian");
    expect(html).toContain("2 dari 3 cukup bukti");
    expect(html).toContain("2 cukup · 1 kurang");
    // Kategori nol tidak dicetak di baris ringkas. (Ringkasan untuk pembaca
    // layar tetap menyebut semua kategori — itu `aria-label`, bukan teks visual.)
    expect(html).toContain(">2 cukup · 1 kurang</p>");
    expect(html).not.toMatch(/>[^<]*0 bertentangan/);
    expect(html).not.toMatch(/>[^<]*0 tidak tercatat/);
  });

  it("satu baris per batch, bukan satu batch di tiga tempat", () => {
    const html = render();
    expect(html.match(/data-label="Batch"/g)).toHaveLength(2); // ayam + wortel
    expect(html).toContain("Bukti kurang");
    expect(html).not.toContain("Batch perlu segera dipakai");
    expect(html).not.toContain("Kesegaran terendah");
  });

  it("alasan sudah diterjemahkan dan utuh ada di tooltip", () => {
    const html = render();
    expect(html).toContain("log kedaluwarsa: sampel terakhir 1 hari lalu (batas 6 jam)");
    expect(html).toContain('title="sampel terakhir 1484 menit lalu, lewat batas 360 menit"');
    expect(html).not.toContain("indeks");
  });

  it("tidak ada kalimat panjang dari versi lama", () => {
    const html = render();
    expect(html).not.toContain("lengkapi pembacaan suhu lalu verifikasi");
    expect(html).not.toContain("menuntut bukti suhu tetapi belum cukup");
  });

  it("sumber log & profil dicetak sekali, bukan per baris", () => {
    const html = render();
    expect(html.match(/log simulasi/g)).toHaveLength(1);
    expect(html).toContain("profil coldchain-v3");
  });

  it("semua aman: satu kalimat, tanpa tabel", () => {
    const html = render({
      safetyRows: [safety({ id: "z" })],
      evidence: [bukti({ id: "z" })],
      summary: { total: 1, sufficient: 1, insufficient: 0, ambiguous: 0, unknown: 0, perluVerifikasi: 0 },
    });
    expect(html).not.toContain("<table");
    expect(html).toContain("Semua batch cukup bukti, masih layak, dan skor kesegarannya di atas 50%.");
  });

  it("tanpa batch: tidak mengarang angka", () => {
    const html = render({
      safetyRows: [],
      evidence: [],
      summary: { total: 0, sufficient: 0, insufficient: 0, ambiguous: 0, unknown: 0, perluVerifikasi: 0 },
    });
    expect(html).toContain("Belum ada batch pada cakupan ini.");
  });
});
