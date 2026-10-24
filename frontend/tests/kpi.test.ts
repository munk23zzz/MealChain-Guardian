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
  kpiQueryPolicy,
  kpiWindowRange,
  metricLabel,
  periodeBulan,
  shouldLoadKpi,
} from "../lib/kpi";
import { KPI_POLL_MS, QUERY_POLL_MS } from "../lib/query";

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
describe("kebijakan muat KPI (polling demo)", () => {
  // Permintaan pemilik 23 Okt 2026: panel KPI harus terasa realtime — angka
  // berubah beberapa detik setelah operator menjalankan aksi, tanpa berpindah
  // tab atau memuat ulang halaman. Sebelum ini hook memasang
  // `refetchInterval: false` sehingga angka baru hanya terlihat setelah tab
  // ditinggalkan/dibuka ulang.
  it("tab yang menampilkan KPI dipoll dengan jeda demo", () => {
    for (const tab of ["today", "kpi-kualitas"]) {
      const policy = kpiQueryPolicy(tab);
      expect(policy.enabled, tab).toBe(true);
      expect(policy.staleTime, tab).toBe(0);
      expect(policy.refetchInterval, tab).toBe(KPI_POLL_MS);
      expect(KPI_POLL_MS).toBe(20_000);
      expect(KPI_POLL_MS).toBeLessThan(QUERY_POLL_MS);
    }
  });

  it("tab lain tidak memuat dan tidak dipoll (tanpa permintaan sia-sia)", () => {
    for (const tab of ["overview", "suppliers", "settings", "", null, undefined]) {
      const policy = kpiQueryPolicy(tab);
      expect(policy.enabled, String(tab)).toBe(false);
      expect(policy.refetchInterval, String(tab)).toBe(false);
    }
  });
});

describe("jendela KPI (pemilih periode)", () => {
  it("tiga jendela dengan label Indonesia yang cocok dengan jamnya", () => {
    expect(KPI_WINDOWS.map((w) => w.key)).toEqual(["24h", "7d", "30d"]);
    expect(KPI_WINDOWS.map((w) => w.label)).toEqual(["24 jam", "7 hari", "1 bulan"]);
    expect(KPI_WINDOWS.map((w) => w.hours)).toEqual([24, 168, 720]);
  });

  it("rentang dihitung dari jam jendela; ujungnya waktu sekarang", () => {
    const now = new Date("2026-10-16T16:00:00.000Z");
    // "1 bulan" = bulan berjalan WIB: 16 Okt 16.00 UTC = 17 Okt 00.00 WIB,
    // jadi awalnya 1 Okt 00.00 WIB = 30 Sep 17.00 UTC.
    expect(kpiWindowRange("30d", now)).toEqual({
      start: "2026-09-30T17:00:00.000Z",
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

describe("periodeBulan — label periode sebagai bulan", () => {
  it("satu bulan ditulis sekali", () => {
    expect(periodeBulan("2026-10-19T10:22:41Z", "2026-10-20T10:22:41Z")).toBe(
      "Oktober 2026"
    );
  });

  it("lintas bulan menyebut kedua bulan", () => {
    expect(periodeBulan("2026-09-20T10:22:41Z", "2026-10-20T10:22:41Z")).toBe(
      "September – Oktober 2026"
    );
  });

  it("lintas tahun menyebut kedua tahun", () => {
    expect(periodeBulan("2026-12-15T00:00:00Z", "2027-01-14T00:00:00Z")).toBe(
      "Desember 2026 – Januari 2027"
    );
  });

  it("batas bulan memakai WIB, bukan UTC", () => {
    // 31 Okt 20.00 UTC = 1 Nov 03.00 WIB: kartu harus menulis November.
    expect(periodeBulan("2026-10-01T00:00:00Z", "2026-10-31T20:00:00Z")).toBe(
      "Oktober – November 2026"
    );
  });

  it("nilai kosong tidak dikarang", () => {
    expect(periodeBulan(null, null)).toBe("—");
    expect(periodeBulan("bukan-tanggal", null)).toBe("—");
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
