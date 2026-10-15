// Gerbang muat KPI (Fase "KPI & Kualitas Agen", 2026-10-15).
//
// Sebelum penggabungan, `useKpi` dijalankan di SEMUA tab; sekarang hanya di tab
// yang benar-benar menampilkan angka KPI. Daftarnya sengaja ditulis eksplisit dan
// diuji: kalau tab "Hari Ini" (yang memakai KPI 24 jam) lupa dicantumkan, kartu
// KPI-nya kosong TANPA error — jadi kegagalannya harus tertangkap tes, bukan
// ketahuan saat demo.
import { describe, expect, it } from "vitest";

import { KPI_TABS, shouldLoadKpi } from "../lib/kpi";

describe("shouldLoadKpi", () => {
  it("memuat di tab yang benar-benar menampilkan KPI", () => {
    expect(shouldLoadKpi("today")).toBe(true);
    expect(shouldLoadKpi("kpi-kualitas")).toBe(true);
  });

  it("tidak memuat di tab lain (termasuk tab lama yang sudah digabung)", () => {
    for (const tab of [
      "overview",
      "recommendations",
      "evidence",
      "safety",
      "surplus",
      "suppliers",
      "agent-log",
      "settings",
      "demo-control",
      "kpi",
      "quality",
      "",
      null,
      undefined,
    ]) {
      expect(shouldLoadKpi(tab), String(tab)).toBe(false);
    }
  });

  it("daftar tab KPI = Hari Ini + tab gabungan (dua pemakai nyata)", () => {
    expect(KPI_TABS).toEqual(["today", "kpi-kualitas"]);
  });
});
