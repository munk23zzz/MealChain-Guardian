// Gerbang muat KPI (Fase "KPI & Kualitas Agen", 2026-10-15).
//
// Sebelum penggabungan, `useKpi` dijalankan di SEMUA tab; sekarang hanya di tab
// yang benar-benar menampilkan angka KPI. Daftarnya sengaja ditulis eksplisit dan
// diuji: kalau tab "Hari Ini" (yang memakai KPI hari ini) lupa dicantumkan, kartu
// KPI-nya kosong TANPA error — jadi kegagalannya harus tertangkap tes, bukan
// ketahuan saat demo.
import { describe, expect, it } from "vitest";

import {
  KPI_DEFAULT_WINDOW,
  KPI_TABS,
  KPI_WINDOWS,
  kpiQueryPolicy,
  fmtCoverage,
  metricLabel,
  periodeBulan,
  periodePil,
  shouldLoadKpi,
} from "../lib/kpi";
import * as kpiMod from "../lib/kpi";
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
  it("tiga periode dengan kunci dan label yang cocok dengan namanya", () => {
    expect(KPI_WINDOWS.map((w) => w.key)).toEqual(["today", "7d", "1bulan"]);
    expect(KPI_WINDOWS.map((w) => w.label)).toEqual([
      "Hari ini",
      "7 hari",
      "1 bulan",
    ]);
    expect(KPI_DEFAULT_WINDOW).toBe("today");
  });

  it("klien tidak lagi menghitung rentang tanggal", () => {
    // Batas hari (termasuk pergeseran 7 jam WIB) milik server: GET /kpi?periode=.
    // Kalau `kpiWindowRange` kembali, dua klien bisa mengirim jendela berbeda
    // untuk tombol "Hari ini" yang sama.
    expect(kpiMod).not.toHaveProperty("kpiWindowRange");
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

describe("periodePil — label pil mengikuti jendela, bukan nama bulan", () => {
  // Audit 26 Okt 2026: dengan jendela "Hari ini" pil dulu menulis
  // "Periode Oktober 2026" (dari rentang 26 Okt 00.00 WIB), sehingga angka
  // harian terbaca sebagai angka sebulan.
  const MULAI = "2026-10-25T17:00:00Z"; // 26 Okt 00.00 WIB
  const AKHIR = "2026-10-26T01:10:02Z"; // 26 Okt 08.10 WIB

  it("hari ini menyebut 'Hari ini' + tanggal, bukan nama bulan", () => {
    const teks = periodePil("today", MULAI, AKHIR);
    expect(teks).toBe("Hari ini · 26 Okt 2026");
    expect(teks).not.toContain("Oktober 2026");
  });

  it("tujuh hari menulis rentang tanggal", () => {
    expect(periodePil("7d", "2026-10-19T17:00:00Z", AKHIR)).toBe(
      "7 hari · 20–26 Okt 2026"
    );
  });

  it("satu bulan tetap memakai nama bulan", () => {
    expect(periodePil("1bulan", "2026-09-30T17:00:00Z", AKHIR)).toBe(
      "1 bulan · Oktober 2026"
    );
  });

  it("tanpa tanggal tetap menyebut jendelanya, tidak mengarang", () => {
    expect(periodePil("today", null, null)).toBe("Hari ini");
    expect(periodePil(null, null, null)).toBe("Periode");
  });
});

describe("fmtCoverage — rasio payload ditulis sebagai persen", () => {
  it("1.00 berarti 100%, bukan 1", () => {
    expect(fmtCoverage("1.00")).toBe("100%");
  });
  it("0.50 berarti 50%", () => {
    expect(fmtCoverage("0.50")).toBe("50%");
  });
  it("nilai kosong tetap '—'", () => {
    expect(fmtCoverage(null)).toBe("—");
    expect(fmtCoverage(undefined)).toBe("—");
    expect(fmtCoverage("bukan-angka")).toBe("—");
  });
});
