// Angka Ringkasan halaman Pemasok — kontrak murni (KPI strip, 29 Okt 2026).
//
// Yang dikunci:
//   1. EMPAT angka, urut tetap, dan HANYA yang pertama dipromosikan (lead);
//   2. "Tanpa stok layak" = pemasok dikurangi yang sedang kirim, tidak pernah
//      negatif walau data server tidak konsisten;
//   3. angka 0 TETAP ditampilkan (bukan disembunyikan) — pada strip KPI, nol
//      adalah jawaban yang sah;
//   4. angka "di luar jangkauan" TIDAK lagi jadi kolom sendiri (S2, 29 Okt
//      2026): jumlah pemasok sudah jadi pil kepala halaman, dan "di luar
//      jangkauan" sudah tertulis di baris penyaring jangkauan.

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
  it("empat angka, urut tetap, label berbahasa manusia", () => {
    const kpi = kpiRingkasan(metrics(), 150);
    expect(kpi.map((k) => k.label)).toEqual([
      "Pemasok dalam jangkauan 150 km",
      "Rata-rata keandalan",
      "Keandalan di bawah 60%",
      "Tanpa stok layak hari ini",
    ]);
    // 60 pemasok, 30 di luar jangkauan → 30 dalam jangkauan (angka yang dipromosikan).
    expect(kpi.map((k) => k.value)).toEqual(["30", "82%", "4", "9"]);
    expect(kpi.every((k) => k.label.startsWith("Di luar jangkauan") === false)).toBe(true);
  });

  it("tepat satu angka dipromosikan, dan itu yang pertama", () => {
    const kpi = kpiRingkasan(metrics(), 150);
    expect(kpi.filter((k) => k.lead)).toHaveLength(1);
    expect(kpi[0].lead).toBe(true);
  });

  it("tanpa ambang jangkauan: yang dipromosikan = pemasok terdaftar", () => {
    const kpi = kpiRingkasan(metrics(), null);
    expect(kpi).toHaveLength(4);
    expect(kpi[0]).toEqual({
      label: "Pemasok terdaftar",
      value: "60",
      tone: "plain",
      lead: true,
    });
  });

  it("nol tetap ditampilkan dan tidak diberi nada peringatan", () => {
    const kpi = kpiRingkasan(metrics({ lowReliability: 0, outOfReach: 0, shipping: 60 }), 150);
    expect(kpi.find((k) => k.label === "Keandalan di bawah 60%")).toEqual({
      label: "Keandalan di bawah 60%",
      value: "0",
      tone: "plain",
    });
    expect(kpi.find((k) => k.label === "Tanpa stok layak hari ini")?.tone).toBe("plain");
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
    expect(kpiRingkasan(metrics(), 75)[0].label).toBe("Pemasok dalam jangkauan 75 km");
  });

  it("bukan kontrol: hasilnya data biasa, tanpa medan aksi", () => {
    const kpi = kpiRingkasan(metrics(), 150);
    const kunciSah = new Set(["label", "tone", "value", "lead"]);
    expect(kpi.every((k) => Object.keys(k).every((nama) => kunciSah.has(nama)))).toBe(true);
    expect(kpi.some((k) => "onClick" in k || "href" in k || "action" in k)).toBe(false);
    // `lead` hanya ada pada angka yang dipromosikan (tidak dipaksakan ke semua).
    expect(kpi.filter((k) => k.lead === true)).toHaveLength(1);
  });
});
