// Logika murni panel "Data & rentang waktu" (Fase 5, 2026-10-15).
//
// Diuji di sini tanpa React/DOM karena semua kalimat yang dilihat operator
// lahir di sini: kalau salah, layar berbohong tanpa ada tes yang menangkapnya.
// Contoh payload diambil dari respons NYATA backend (probe 2026-10-15), bukan
// karangan — bentuk kunci yang salah akan terlihat sebagai tes gagal.
import { describe, expect, it } from "vitest";

import {
  DEFAULT_RANGE,
  INTERVAL_HOURS,
  RANGE_MAX,
  RANGE_MIN,
  buildLine,
  canSubmit,
  formatCount,
  formatShortDate,
  honestNote,
  previewLine,
  purgeLine,
  purgeWarning,
  rangeError,
  refreshLine,
  refreshWarning,
  spanDays,
  statusLine,
  toIsoDateTime,
} from "../lib/demo-data";

// GET /demo/preview?start=2026-09-01&end=2026-11-05 (respons nyata).
const PREVIEW = {
  range: {
    start: "2026-09-01T00:00:00+00:00",
    end: "2026-11-05T00:00:00+00:00",
    actual_start: "2026-09-01T00:00:00+00:00",
    actual_end: "2026-10-07T12:00:00+00:00",
    plan_end: "2026-11-05",
  },
  counts: {
    supply: { planned: 2190 },
    prices: { planned: 2274 },
    menu_plans: { planned: 660, existing_rows: 660 },
  },
  actual_timestamps: 73,
  interval_hours: 12,
  writes: false,
};

// POST /demo/timeseries (respons nyata).
const GENERATED = {
  range: PREVIEW.range,
  counts: {
    supply: { planned: 2190, added: 0, in_db: 2190 },
    prices: { planned: 2274, added: 0, in_db: 2274 },
    menu_plans: { planned: 660, added: 0, in_db: 590 },
  },
  actual_timestamps: 73,
  interval_hours: 12,
  skipped: { menu_plans_kept: 660 },
  purged: null,
};

// GET /demo/data-status (respons nyata).
const STATUS = {
  as_of: "2026-10-15T05:31:05.485869+00:00",
  canonical_ref: "2026-10-08T12:00:00+00:00",
  actual_cutoff: "2026-10-07T12:00:00+00:00",
  tables: {
    supply_records: {
      seed: 30,
      demo: 2190,
      demo_from: "2026-09-01T00:00:00+00:00",
      demo_to: "2026-10-07T00:00:00+00:00",
      generated_at: "2026-10-15T01:55:25.114198+00:00",
    },
    price_signals: { seed: 44, demo: 2274, demo_from: "2026-09-01T00:00:00+00:00" },
    menu_plans: { seed: 70, demo: 590, demo_to: "2026-11-05" },
  },
  totals: { seed: 144, demo: 5054 },
};

describe("format & rentang", () => {
  it("formatShortDate menulis bulan Indonesia tanpa Intl", () => {
    expect(formatShortDate("2026-09-01")).toBe("1 Sep 2026");
    expect(formatShortDate("2026-11-05T00:00:00+00:00")).toBe("5 Nov 2026");
    expect(formatShortDate(null)).toBe("—");
    expect(formatShortDate("bukan-tanggal")).toBe("bukan-tanggal");
  });

  it("formatCount memakai pemisah ribuan id-ID dan tidak melempar pada null", () => {
    expect(formatCount(2190)).toBe("2.190");
    expect(formatCount(0)).toBe("0");
    expect(formatCount(null)).toBe("0");
    expect(formatCount(undefined)).toBe("0");
  });

  it("toIsoDateTime menambahkan offset eksplisit (kontrak backend)", () => {
    expect(toIsoDateTime("2026-09-01")).toBe("2026-09-01T00:00:00+00:00");
  });

  it("spanDays inklusif kedua ujung; rentang terbalik = null", () => {
    expect(spanDays(DEFAULT_RANGE.start, DEFAULT_RANGE.end)).toBe(66);
    expect(spanDays("2026-09-01", "2026-09-01")).toBe(1);
    expect(spanDays("2026-11-05", "2026-09-01")).toBeNull();
    expect(spanDays("", "")).toBeNull();
  });

  it("rangeError menolak format salah, urutan terbalik, dan di luar batas backend", () => {
    expect(rangeError(DEFAULT_RANGE.start, DEFAULT_RANGE.end)).toBeNull();
    expect(rangeError("01-09-2026", "2026-11-05")).toMatch(/YYYY-MM-DD/);
    expect(rangeError("2026-11-05", "2026-09-01")).toMatch(/setelah tanggal mulai/);
    expect(rangeError("2025-12-31", "2026-11-05")).toMatch(/didukung/);
    expect(rangeError("2026-09-01", "2027-06-01")).toMatch(/didukung/);
    expect(rangeError(RANGE_MIN, RANGE_MAX)).toBeNull();
  });

  it("INTERVAL_HOURS = 12 (dua baris per hari) dan rentang default = rencana", () => {
    expect(INTERVAL_HOURS).toBe(12);
    expect(DEFAULT_RANGE).toEqual({ start: "2026-09-01", end: "2026-11-05" });
  });
});

describe("pratinjau", () => {
  it("previewLine memakai angka payload dan menyebut batas baris aktual", () => {
    const baris = previewLine(PREVIEW);
    expect(baris).toContain("2.190 baris pasokan");
    expect(baris).toContain("2.274 harga");
    expect(baris).toContain("660 rencana menu");
    expect(baris).toContain("untuk 66 hari");
    expect(baris).toContain("Baris aktual berhenti 7 Okt 2026 12.00 UTC");
  });

  it("previewLine tidak mengarang saat payload tidak dikenali", () => {
    expect(previewLine(null)).toBe("Pratinjau tidak tersedia.");
    expect(previewLine({})).toBe("Pratinjau tidak tersedia.");
  });
});

describe("hasil aksi", () => {
  it("buildLine melaporkan added + isi tabel + rencana menu yang tidak ditimpa", () => {
    const baris = buildLine(GENERATED);
    expect(baris).toContain("Ditambahkan 0 pasokan");
    expect(baris).toContain("2.190");
    expect(baris).toContain("660 rencana menu yang sudah ada (baris kanonik) tidak ditimpa");
    expect(baris).not.toContain("Dihapus dulu");
  });

  it("buildLine menyebut penghapusan lebih dulu saat force=true", () => {
    const baris = buildLine({ ...GENERATED, purged: { total: 5054 } });
    expect(baris.startsWith("Dihapus dulu 5.054 baris demo.")).toBe(true);
  });

  it("buildLine jujur saat ringkasan tidak dikenali", () => {
    expect(buildLine(null)).toBe("Selesai, tetapi ringkasan tidak dikenali.");
  });

  it("purgeLine merinci yang dihapus per tabel", () => {
    const baris = purgeLine({
      deleted: { supply_records: 2190, price_signals: 2274, menu_plans: 590 },
      total: 5054,
    });
    expect(baris).toContain("Dihapus 5.054 baris demo");
    expect(baris).toContain("2.190 pasokan");
    expect(baris).toContain("2.274 harga");
    expect(baris).toContain("590 rencana menu");
    expect(baris).toContain("Snapshot kanonik tidak tersentuh");
  });

  it("purgeLine tidak mengklaim menghapus saat memang tidak ada baris demo", () => {
    expect(purgeLine({ deleted: {}, total: 0 })).toMatch(/Tidak ada baris deret waktu demo/);
  });

  it("refreshLine memakai reference_time + jumlah kasus dari backend", () => {
    const baris = refreshLine({
      reference_time: "2026-10-15T05:40:00+00:00",
      cases: { seeded: true, cases: 4, decisions: 4 },
      rows: {},
    });
    expect(baris).toContain("15 Okt 2026 05.40 UTC");
    expect(baris).toContain("4 kasus skrip dimuat ulang (4 keputusan siap)");
  });

  it("refreshLine tetap jujur saat payload tanpa cases", () => {
    expect(
      refreshLine({ reference_time: "2026-10-15T05:40:00+00:00" })
    ).toBe("Snapshot kanonik disegarkan ke 15 Okt 2026 05.40 UTC.");
    expect(refreshLine(null)).toBe("Penyegaran belum dijalankan.");
  });
});

describe("status data", () => {
  it("statusLine melaporkan deret waktu demo + kanonik + waktu pembuatan", () => {
    const baris = statusLine(STATUS);
    expect(baris).toContain("5.054 baris");
    expect(baris).toContain("2.190 pasokan");
    expect(baris).toContain("2.274 harga");
    expect(baris).toContain("590 rencana menu");
    expect(baris).toContain("(1 Sep 2026 – 5 Nov 2026)");
    expect(baris).toContain("Snapshot kanonik: 144 baris (per 8 Okt 2026 12.00 UTC)");
    expect(baris).toContain("Terakhir dibuat 15 Okt 2026 01.55 UTC");
  });

  it("statusLine menyebut keadaan kosong tanpa menyamarkannya sebagai nol", () => {
    const kosong = statusLine({
      canonical_ref: "2026-10-08T12:00:00+00:00",
      tables: { supply_records: { seed: 30, demo: 0 }, price_signals: { seed: 44, demo: 0 }, menu_plans: { seed: 70, demo: 0 } },
    });
    expect(kosong).toMatch(/Belum ada deret waktu demo/);
  });

  it("statusLine tidak menebak saat bentuk payload tidak dikenali", () => {
    expect(statusLine(null)).toBe("Status data belum bisa dibaca.");
  });
});

describe("peringatan jujur & gerbang tombol", () => {
  it("purgeWarning menyebut apa yang hilang dan apa yang tidak", () => {
    const teks = purgeWarning();
    expect(teks).toContain("SEMUA baris deret waktu demo");
    expect(teks).toContain("Snapshot kanonik tidak tersentuh");
    expect(teks).toContain("4.900 kg");
  });

  it("refreshWarning menyebut tanggal yang bergeser, bukan angkanya", () => {
    const teks = refreshWarning();
    expect(teks).toContain("TANGGALNYA");
    expect(teks).toContain("4.900 kg");
    expect(teks).toContain("8 Okt 12.00");
    expect(teks).toContain("Akun demo tidak direset");
  });

  it("honestNote menegaskan aktual tidak dikarang di masa depan", () => {
    expect(honestNote()).toContain("Aktual tidak pernah dikarang di masa depan");
    expect(honestNote()).toContain("rencana menu sampai 5 Nov");
  });

  it("canSubmit hanya saat rentang sah dan tidak sedang sibuk", () => {
    expect(canSubmit(DEFAULT_RANGE.start, DEFAULT_RANGE.end, false)).toBe(true);
    expect(canSubmit(DEFAULT_RANGE.start, DEFAULT_RANGE.end, true)).toBe(false);
    expect(canSubmit("2026-11-05", "2026-09-01", false)).toBe(false);
  });
});
