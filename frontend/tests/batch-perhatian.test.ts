// Kontrak "Batch perlu perhatian" (29 Okt 2026).
//
// Modul ini menggantikan tiga kartu (bukti suhu, segera dipakai, kesegaran
// terendah) dengan satu daftar baris bertiga-putusan. Yang dikunci:
//   1. durasi menit → satuan manusia ("29685 menit" → "20 hari");
//   2. alasan server diringkas tanpa pengulangan dan tanpa indeks internal;
//   3. baris masuk daftar hanya bila salah satu dari tiga sinyal menyala;
//   4. urutan: bukti bermasalah dulu, lalu yang paling dekat kedaluwarsa;
//   5. skor kosong tidak pernah dibaca sebagai 0.

import { describe, expect, it } from "vitest";

import { alasanSingkat, batchPerhatian, durasiManusia } from "../lib/batch-perhatian";
import type { EvidenceRow, SafetyRow } from "../lib/food-safety";

function safety(over: Partial<SafetyRow> & { id: string }): SafetyRow {
  return {
    id: over.id,
    location: over.location ?? "JKT",
    commodity: over.commodity ?? "telur",
    kg: over.kg ?? 100,
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
    observation: over.observation ?? "observed",
    observationLabel: over.observationLabel ?? "Teramati",
    state: over.state ?? "sufficient",
    stateLabel: over.stateLabel ?? "Bukti cukup",
    tone: over.tone ?? "ok",
    sufficient: over.sufficient ?? true,
    sampleCount: over.sampleCount ?? 4,
    observedAt: over.observedAt ?? null,
    source: "demo",
    sourceLabel: "log simulasi",
    profileVersion: "coldchain-v3",
    policyKind: "simulated_policy",
    coldChainRequired: true,
    reasons: over.reasons ?? [],
  };
}

describe("durasi manusia", () => {
  it("hari, jam, menit", () => {
    expect(durasiManusia(29685)).toBe("20 hari");
    expect(durasiManusia(1484)).toBe("1 hari");
    expect(durasiManusia(200)).toBe("3 jam 20 menit");
    expect(durasiManusia(120)).toBe("2 jam");
    expect(durasiManusia(45)).toBe("45 menit");
  });

  it("nilai tidak masuk akal tidak menjadi angka palsu", () => {
    expect(durasiManusia(null)).toBe("—");
    expect(durasiManusia(Number.NaN)).toBe("—");
    expect(durasiManusia(-5)).toBe("—");
  });
});

describe("alasan singkat", () => {
  it("kedaluwarsa: menit → hari, batas tetap disebut", () => {
    expect(alasanSingkat(["sampel terakhir 29685 menit lalu, lewat batas 360 menit"])).toBe(
      "log kedaluwarsa: sampel terakhir 20 hari lalu (batas 6 jam)"
    );
  });

  it("empat klausa yang mengulang menjadi dua klausa pendek", () => {
    const alasan = [
      "entri log rusak pada indeks 1",
      "entri log rusak pada indeks 2",
      "sampel sah kurang dari 2 (ada 1)",
      "2 entri log tidak terbaca",
    ];
    const hasil = alasanSingkat(alasan);
    expect(hasil).toBe("1 sampel sah dari minimum 2 · 2 entri log rusak");
    expect(hasil).not.toContain("indeks");
  });

  it("tidak mengulang entri yang sama", () => {
    const hasil = alasanSingkat(["entri log rusak pada indeks 1", "entri log rusak pada indeks 3"]);
    expect(hasil).toBe("2 entri log rusak");
  });

  it("tanpa alasan → null (bukan teks karangan)", () => {
    expect(alasanSingkat([])).toBeNull();
    expect(alasanSingkat(null)).toBeNull();
  });

  it("alasan yang tidak dikenal tetap ditulis, terpotong", () => {
    const panjang = "x".repeat(120);
    const hasil = alasanSingkat([panjang]);
    expect(hasil).not.toBeNull();
    expect((hasil as string).length).toBeLessThanOrEqual(65);
    expect(hasil).toContain("…");
  });
});

describe("pemilihan baris", () => {
  const safetyRows = [
    safety({ id: "a" }), // aman di tiga sinyal
    safety({ id: "b", hoursLeft: 20, hoursLabel: "20 jam" }), // mendesak
    safety({ id: "c", freshnessScore: 0.32, freshness: "32%" }), // segar rendah
    safety({ id: "d", freshnessScore: null, freshness: "—" }), // skor kosong
  ];
  const evidenceRows = [
    bukti({ id: "a" }),
    bukti({ id: "b" }),
    bukti({ id: "c" }),
    bukti({ id: "d" }),
    bukti({
      id: "e",
      commodity: "ayam",
      state: "insufficient",
      stateLabel: "Bukti kurang",
      tone: "warn",
      sufficient: false,
      reasons: ["sampel terakhir 100 menit lalu, lewat batas 360 menit"],
    }),
  ];

  it("hanya baris yang punya sinyal masalah", () => {
    const hasil = batchPerhatian([...safetyRows, safety({ id: "e", commodity: "ayam" })], evidenceRows);
    expect(hasil.map((r) => r.id).sort()).toEqual(["b", "c", "e"]);
  });

  it("skor kesegaran kosong tidak dianggap 0", () => {
    const hasil = batchPerhatian([safety({ id: "d", freshnessScore: null })], [bukti({ id: "d" })]);
    expect(hasil).toEqual([]);
  });

  it("bukti kurang diurutkan lebih dulu daripada sekadar mendesak", () => {
    const hasil = batchPerhatian([...safetyRows, safety({ id: "e", commodity: "ayam" })], evidenceRows);
    expect(hasil[0].id).toBe("e");
    expect(hasil[0].buktiLabel).toBe("Bukti kurang");
  });

  it("baris tanpa bukti server tetap muncul bila mendesak, dengan label jujur", () => {
    const hasil = batchPerhatian([safety({ id: "x", hoursLeft: 10, hoursLabel: "10 jam" })], []);
    expect(hasil).toHaveLength(1);
    expect(hasil[0].buktiLabel).toBe("Tidak dinilai");
    expect(hasil[0].buktiTone).toBe("muted");
    expect(hasil[0].kenapa).toBeNull();
  });

  it("maks membatasi baris tanpa mengubah urutan", () => {
    const hasil = batchPerhatian([...safetyRows, safety({ id: "e", commodity: "ayam" })], evidenceRows, {
      maks: 2,
    });
    expect(hasil).toHaveLength(2);
    expect(hasil[0].id).toBe("e");
  });

  it("alasan utuh disimpan untuk tooltip", () => {
    const hasil = batchPerhatian([safety({ id: "e", commodity: "ayam" })], evidenceRows);
    expect(hasil[0].penuh).toEqual(["sampel terakhir 100 menit lalu, lewat batas 360 menit"]);
    expect(hasil[0].kenapa).toBe("log kedaluwarsa: sampel terakhir 1 jam 40 menit lalu (batas 6 jam)");
  });
});
