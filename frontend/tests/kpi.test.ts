// Gerbang muat KPI (Fase "KPI & Kualitas Agen", 2026-10-15).
//
// Sebelum penggabungan, `useKpi` dijalankan di SEMUA tab; sekarang hanya di tab
// yang benar-benar menampilkan angka KPI. Daftarnya sengaja ditulis eksplisit dan
// diuji: kalau tab "Hari Ini" (yang memakai KPI 24 jam) lupa dicantumkan, kartu
// KPI-nya kosong TANPA error — jadi kegagalannya harus tertangkap tes, bukan
// ketahuan saat demo.
import { describe, expect, it } from "vitest";

import {
  KPI_TABS,
  KPI_WINDOWS,
  kpiWindowRange,
  metricLabel,
  shouldLoadKpi,
} from "../lib/kpi";

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

// Pemilih periode (permintaan pemilik 2026-10-16). Sebelum ini jendela KPI
// DIPAKU 24 jam di dalam hook (`KPI_WINDOW_MS`), sementara dataset demo berhenti
// di sekitar 8 Okt — akibatnya tiga kartu menjawab "belum ada data" walau
// datanya ADA di database, cuma di luar 24 jam. Daftar jendela ditulis
// eksplisit (bukan angka ajaib di dalam hook) supaya label di layar, jamnya,
// dan rentang yang dikirim ke API tidak bisa saling menyimpang.
describe("jendela KPI (pemilih periode)", () => {
  it("tiga jendela dengan label Indonesia yang cocok dengan jamnya", () => {
    expect(KPI_WINDOWS.map((w) => w.key)).toEqual(["24h", "7d", "30d"]);
    expect(KPI_WINDOWS.map((w) => w.label)).toEqual(["24 jam", "7 hari", "30 hari"]);
    expect(KPI_WINDOWS.map((w) => w.hours)).toEqual([24, 168, 720]);
  });

  it("rentang dihitung dari jam jendela; ujungnya waktu sekarang", () => {
    const now = new Date("2026-10-16T16:00:00.000Z");
    expect(kpiWindowRange("30d", now)).toEqual({
      start: "2026-09-16T16:00:00.000Z",
      end: "2026-10-16T16:00:00.000Z",
    });
    expect(kpiWindowRange("24h", now).start).toBe("2026-10-15T16:00:00.000Z");
  });

  it("kunci tak dikenal jatuh ke 24 jam, bukan rentang kosong", () => {
    const now = new Date("2026-10-16T16:00:00.000Z");
    expect(kpiWindowRange("ngawur", now).start).toBe("2026-10-15T16:00:00.000Z");
    expect(kpiWindowRange(undefined, now).start).toBe("2026-10-15T16:00:00.000Z");
  });
});

describe("metricLabel — nama metrik untuk layar", () => {
  it("menerjemahkan nama kanonik yang dipakai halaman", () => {
    expect(metricLabel("Meal Continuity Rate")).toBe("Keberlanjutan menu");
    expect(metricLabel("Avoidable Food Loss")).toBe("Susut pangan");
    expect(metricLabel("Evidence Completeness")).toBe("Kelengkapan bukti");
  });

  it("nama yang belum dikenal dikembalikan apa adanya, bukan dikarang", () => {
    expect(metricLabel("New Metric From Server")).toBe("New Metric From Server");
    expect(metricLabel(null)).toBe("—");
  });
});
