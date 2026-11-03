// Agenda harian tanpa grid bulan (desain ulang "Hari Ini", 2026-10-17) — fungsi MURNI.
//
// Keputusan pemilik: grid bulan besar DIHAPUS dari kartu, tapi informasinya tetap
// dipakai. Jadi kepala kartu hanya menyisakan: ikon kecil pemilih tanggal (popup),
// tombol ‹ › untuk memindahkan HARI, dan "Hari ini". Berpindah hari harus tetap
// menghasilkan rentang yang diminta ke `GET /agenda` yang memuat hari itu —
// karena itu langkah hari dibatasi ke rentang data yang didukung (`RANGE_MIN`/
// `RANGE_MAX`), bukan dibiarkan melangkah ke luar data lalu menampilkan halaman
// kosong tanpa penjelasan.
import { describe, expect, it } from "vitest";

import { agendaGroups, agendaRows, clampDayStep, shiftDay } from "../lib/agenda";

describe("langkah hari pada agenda harian", () => {
  it("menggeser satu hari, menyeberang bulan dan tahun", () => {
    expect(shiftDay("2026-10-17", 1)).toBe("2026-10-18");
    expect(shiftDay("2026-10-31", 1)).toBe("2026-11-01");
    expect(shiftDay("2026-11-01", -1)).toBe("2026-10-31");
    expect(shiftDay("2026-12-31", 1)).toBe("2027-01-01");
    expect(shiftDay("2027-01-01", -1)).toBe("2026-12-31");
  });

  it("benar pada tahun kabisat dan pada langkah besar", () => {
    // 2028 kabisat: 28 Feb + 1 hari = 29 Feb.
    expect(shiftDay("2028-02-28", 1)).toBe("2028-02-29");
    expect(shiftDay("2028-03-01", -1)).toBe("2028-02-29");
    // 2026 bukan kabisat: 28 Feb + 1 hari = 1 Mar.
    expect(shiftDay("2026-02-28", 1)).toBe("2026-03-01");
    expect(shiftDay("2026-10-17", 7)).toBe("2026-10-24");
    expect(shiftDay("2026-10-17", -30)).toBe("2026-09-17");
  });

  it("menolak melangkah ke luar rentang data yang didukung", () => {
    // Batas: pemilik melihat tanggal awal rentang → tombol ‹ harus mati, bukan
    // menampilkan hari kosong yang tampak seperti "tidak ada operasi".
    expect(clampDayStep("2026-04-01", -1, "2026-04-01", "2027-09-30")).toBeNull();
    expect(clampDayStep("2026-04-01", 1, "2026-04-01", "2027-09-30")).toBe("2026-04-02");
    expect(clampDayStep("2027-09-30", 1, "2026-04-01", "2027-09-30")).toBeNull();
    expect(clampDayStep("2027-09-30", -1, "2026-04-01", "2027-09-30")).toBe("2027-09-29");
  });
});

const HARI = {
  date: "2026-10-20",
  menu: { rows: 1, planned_portions: 1200, available: true },
  delivery: { rows: 0, delivered_portions: 0, available: false },
  disposal: { rows: 0, quantity_kg: 0, available: false },
  supply: { rows: 3, available: true },
  price: { rows: 2, available: true },
  batches_expiring: { rows: 0, available: false },
  decisions: { rows: 0, by_status: {}, available: false },
  activity: 3,
};

describe("pengelompokan info harian", () => {
  it("membagi baris hari menjadi tiga kelompok bertema, tanpa menghilangkan baris", () => {
    const groups = agendaGroups(HARI as never);
    expect(groups.map((g) => g.title)).toEqual([
      "Rencana & pasokan",
      "Limbah & kedaluwarsa",
      "Keputusan agen",
    ]);
    // Semua baris `agendaRows` tetap ada — kelompok hanya menyusun ULANG, tidak
    // menghilangkan. Urutannya memang berubah (itu gunanya kelompok), jadi yang
    // dibandingkan adalah himpunannya.
    const jumlahBaris = groups.reduce((total, g) => total + g.rows.length, 0);
    expect(jumlahBaris).toBe(agendaRows(HARI as never).length);
    const semuaLabel = groups.flatMap((g) => g.rows.map((r) => r.label)).sort();
    const labelAsli = agendaRows(HARI as never)
      .map((r) => r.label)
      .sort();
    expect(semuaLabel).toEqual(labelAsli);
  });

  it("tetap jujur: kelompok tanpa catatan tidak diisi angka nol", () => {
    const groups = agendaGroups(HARI as never);
    const limbah = groups[1].rows.map((r) => r.available);
    expect(limbah).toEqual([false, false]);
    const nilai = groups[1].rows.map((r) => r.value);
    expect(nilai).toEqual([null, null]);
  });
});
