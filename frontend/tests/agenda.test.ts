// Kalender agenda harian (permintaan pemilik 2026-10-16) — fungsi MURNI.
//
// Semua aritmetika kalender diuji di sini supaya komponen tinggal merender:
// grid bulan selalu 42 sel mulai SENIN (pola kalender Indonesia), rentangnya
// tak pernah melewati batas 62 hari kontrak `GET /agenda`, dan "hari ini"
// dihitung menurut WIB (UTC+7) — bukan UTC, karena layar konsol memakai WIB.

import { describe, expect, it } from "vitest";

import {
  AGENDA_MONTH_LABELS,
  agendaRows,
  gridRange,
  monthChoices,
  monthGrid,
  pickerYears,
  shiftMonth,
  wibToday,
} from "../lib/agenda";

describe("kalender agenda — grid bulan", () => {
  it("selalu 42 sel mulai Senin", () => {
    const cells = monthGrid(2026, 10);
    expect(cells).toHaveLength(42);
    expect(cells[0].date).toBe("2026-09-28"); // Senin sebelum 1 Okt
    expect(cells[41].date).toBe("2026-11-08");
    expect(new Date(`${cells[0].date}T00:00:00Z`).getUTCDay()).toBe(1); // Senin
    for (const sel of cells) {
      expect(new Date(`${sel.date}T00:00:00Z`).getUTCDay()).toBeGreaterThanOrEqual(0);
      expect(new Date(`${sel.date}T00:00:00Z`).getUTCDay()).toBeLessThanOrEqual(6);
    }
  });

  it("menandai sel di dalam bulan vs sel pipi bulan", () => {
    const cells = monthGrid(2026, 10);
    const sel1Okt = cells.find((c) => c.date === "2026-10-01");
    expect(sel1Okt?.inMonth).toBe(true);
    expect(sel1Okt?.day).toBe(1);
    expect(cells.find((c) => c.date === "2026-09-28")?.inMonth).toBe(false);
    expect(cells.filter((c) => c.inMonth)).toHaveLength(31); // Oktober 31 hari
  });

  it("rentang grid = sel pertama s/d sel terakhir (42 hari, di bawah batas 62)", () => {
    const range = gridRange(monthGrid(2026, 10));
    expect(range).toEqual({ start: "2026-09-28", end: "2026-11-08" });
    const hari =
      (Date.parse(`${range.end}T00:00:00Z`) - Date.parse(`${range.start}T00:00:00Z`)) / 86400000 + 1;
    expect(hari).toBe(42);
    expect(hari).toBeLessThanOrEqual(62);
  });

  it("Februari tahun kabisat tetap 42 sel", () => {
    expect(monthGrid(2028, 2).filter((c) => c.inMonth)).toHaveLength(29);
  });
});

describe("kalender agenda — bulan & hari", () => {
  it("label bulan bahasa Indonesia", () => {
    expect(AGENDA_MONTH_LABELS[1]).toBe("Januari");
    expect(AGENDA_MONTH_LABELS[10]).toBe("Oktober");
    expect(AGENDA_MONTH_LABELS[12]).toBe("Desember");
  });

  it("pindah bulan menyeberang tahun", () => {
    expect(shiftMonth(2026, 12, 1)).toEqual({ year: 2027, month: 1 });
    expect(shiftMonth(2026, 1, -1)).toEqual({ year: 2025, month: 12 });
  });

  it("hari ini menurut WIB, bukan UTC", () => {
    expect(wibToday(new Date("2026-10-16T17:30:00Z"))).toBe("2026-10-17");
    expect(wibToday(new Date("2026-10-16T10:00:00Z"))).toBe("2026-10-16");
  });
});

describe("kalender agenda — baris ringkasan hari", () => {
  const hari = {
    date: "2026-10-20",
    menu: { rows: 1, planned_portions: 1200, available: true },
    delivery: { rows: 0, delivered_portions: 0, available: false },
    disposal: { rows: 0, quantity_kg: 0, available: false },
    supply: { rows: 0, available: false },
    price: { rows: 0, available: false },
    batches_expiring: { rows: 0, available: false },
    decisions: { rows: 0, by_status: {}, available: false },
    activity: 1,
  };

  it("bagian tanpa catatan bernilai null — BUKAN angka nol yang berpura-pura", () => {
    const byLabel = Object.fromEntries(agendaRows(hari).map((r) => [r.label, r.value]));
    expect(byLabel["Rencana menu"]).toBe("1.200 porsi");
    // Label sengaja disebut "Pengiriman makan" (audit data 26 Okt 2026): di
    // Overview istilah "kiriman tiba" dipakai untuk kiriman BAHAN pemasok.
    expect(byLabel["Pengiriman makan tiba"]).toBeNull();
    expect(byLabel["Limbah dibuang"]).toBeNull();
    expect(byLabel["Pasokan tercatat"]).toBeNull();
    expect(byLabel["Harga tercatat"]).toBeNull();
    expect(byLabel["Batch kedaluwarsa"]).toBeNull();
    expect(byLabel["Keputusan agen"]).toBeNull();
  });

  it("available=true selalu punya nilai, available=false selalu null", () => {
    for (const row of agendaRows(hari)) {
      expect(row.available).toBe(row.value !== null);
    }
  });

  it("hari berdata penuh menulis angka yang bisa dibaca", () => {
    const penuh = {
      ...hari,
      delivery: { rows: 1, delivered_portions: 1200, available: true },
      disposal: { rows: 1, quantity_kg: 4, available: true },
      supply: { rows: 6, available: true },
      price: { rows: 6, available: true },
      batches_expiring: { rows: 15, available: true },
      decisions: { rows: 12, by_status: { pending_approval: 12 }, available: true },
      activity: 7,
    };
    const byLabel = Object.fromEntries(agendaRows(penuh).map((r) => [r.label, r.value]));
    expect(byLabel["Pengiriman makan tiba"]).toBe("1.200 porsi");
    expect(byLabel["Limbah dibuang"]).toBe("4 kg");
    expect(byLabel["Keputusan agen"]).toBe("12 (12 menunggu persetujuan)");
  });
});

describe("kalender agenda — daftar pilihan bulan & tahun (popup pemilih tanggal)", () => {
  it("menawarkan 12 bulan bahasa Indonesia, urut Januari→Desember", () => {
    const bulan = monthChoices();
    expect(bulan).toHaveLength(12);
    expect(bulan[0]).toEqual({ value: 1, label: "Januari" });
    expect(bulan[9]).toEqual({ value: 10, label: "Oktober" });
    expect(bulan[11]).toEqual({ value: 12, label: "Desember" });
  });

  it("daftar tahun = tahun yang dicakup rentang data, urut menaik", () => {
    expect(pickerYears("2026-01-01", "2027-01-01")).toEqual([2026, 2027]);
    expect(pickerYears("2026-01-01", "2026-12-31")).toEqual([2026]);
  });

  it("tahun yang sedang tampil selalu ikut ke daftar", () => {
    // Kalau tidak, `<select>` bisa menampilkan nilai yang tidak ada di daftarnya
    // sendiri — kontrol yang tampak kosong padahal bulan itu sedang dibuka.
    expect(pickerYears("2026-01-01", "2027-01-01", 2025)).toEqual([2025, 2026, 2027]);
    expect(pickerYears("2026-01-01", "2026-12-31", 2027)).toEqual([2026, 2027]);
  });
});
