// Angka Ringkasan halaman Pemasok — kontrak murni (KPI strip, 29 Okt 2026).
//
// Yang dikunci:
//   1. urutan dan label lima angka tetap (label = kalimat biasa, bukan kode);
//   2. "Tanpa stok layak" = pemasok dikurangi yang sedang kirim, tidak pernah
//      negatif walau data server tidak konsisten;
//   3. angka 0 TETAP ditampilkan (bukan disembunyikan) — pada strip KPI, nol
//      adalah jawaban yang sah;
//   4. baris "Di luar jangkauan" hanya ada bila peran punya ambang jangkauan.

import { describe, expect, it } from "vitest";

import { kpiRingkasan } from "../lib/supplier-summary";
import type { DirectoryMetrics } from "../lib/suppliers-board";

function metrics(over: Partial<DirectoryMetrics> = {}): DirectoryMetrics {
  return {
    suppliers: 60,
    avgReliability: 0.82,
    avgReliabilityLabel: "82%",
    lowReliability: 4,
    excluded: 1,
    withCoordinates: 60,
    outOfReach: 30,
    unknownDistance: 0,
    shipping: 51,
    ...over,
  };
}

describe("strip KPI Ringkasan", () => {
  it("lima angka, urut tetap, label berbahasa manusia", () => {
    const kpi = kpiRingkasan(metrics(), 150);
    expect(kpi.map((k) => k.label)).toEqual([
      "Pemasok",
      "Rata-rata keandalan",
      "Keandalan di bawah 60%",
      "Tanpa stok layak hari ini",
      "Di luar jangkauan 150 km",
    ]);
    expect(kpi.map((k) => k.value)).toEqual(["60", "82%", "4", "9", "30"]);
  });

  it("tanpa ambang jangkauan hanya empat angka", () => {
    const kpi = kpiRingkasan(metrics(), null);
    expect(kpi).toHaveLength(4);
    expect(kpi.some((k) => k.label.startsWith("Di luar jangkauan"))).toBe(false);
  });

  it("nol tetap ditampilkan dan tidak diberi nada peringatan", () => {
    const kpi = kpiRingkasan(metrics({ lowReliability: 0, outOfReach: 0, shipping: 60 }), 150);
    expect(kpi.find((k) => k.label === "Keandalan di bawah 60%")).toEqual({
      label: "Keandalan di bawah 60%",
      value: "0",
      tone: "plain",
    });
    expect(kpi.find((k) => k.label.startsWith("Di luar jangkauan"))?.tone).toBe("plain");
  });

  it("angka yang perlu dilihat diberi nada warn", () => {
    const kpi = kpiRingkasan(metrics(), 150);
    expect(kpi.find((k) => k.label === "Keandalan di bawah 60%")?.tone).toBe("warn");
    expect(kpi.find((k) => k.label === "Tanpa stok layak hari ini")?.tone).toBe("warn");
  });

  it("tanpa stok layak = pemasok dikurangi yang sedang kirim", () => {
    const kpi = kpiRingkasan(metrics({ suppliers: 10, shipping: 3 }), 150);
    expect(kpi.find((k) => k.label === "Tanpa stok layak hari ini")?.value).toBe("7");
  });

  it("tidak pernah negatif walau server melaporkan kirim lebih banyak", () => {
    const kpi = kpiRingkasan(metrics({ suppliers: 3, shipping: 5 }), 150);
    expect(kpi.find((k) => k.label === "Tanpa stok layak hari ini")?.value).toBe("0");
  });

  it("ribuan memakai pemisah titik, bukan koma", () => {
    const kpi = kpiRingkasan(metrics({ suppliers: 1250, shipping: 1250 }), null);
    expect(kpi[0].value).toBe("1.250");
  });

  it("ambang jangkauan muncul di label, bukan angka telanjang", () => {
    expect(kpiRingkasan(metrics(), 75).at(-1)?.label).toBe("Di luar jangkauan 75 km");
  });

  it("bukan kontrol: hasilnya data biasa, tanpa medan aksi", () => {
    const kpi = kpiRingkasan(metrics(), 150);
    expect(kpi.every((k) => Object.keys(k).sort().join(",") === "label,tone,value")).toBe(true);
  });
});
