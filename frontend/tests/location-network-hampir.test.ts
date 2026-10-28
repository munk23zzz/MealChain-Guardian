// Kontrak dua kolom tambahan di tabel Location Network:
//   * "Batch ≤7h"  — batch yang layak dipakai ≤ 7 hari lagi dan TIDAK ditahan;
//   * "Rekomendasi" — keputusan terbuka untuk lokasi itu.
//
// Yang dijaga di sini (modul murni, tanpa DOM):
//   * batch ditahan / gagal uji TIDAK dihitung sebagai stok yang akan kedaluwarsa;
//   * tanggal yang tidak terbaca tidak dihitung (bukan dianggap 0 hari);
//   * status keputusan yang sudah selesai/ditolak tidak dihitung terbuka;
//   * nama lokasi dinormalisasi (spasi berlebih) supaya tidak muncul dua kunci.

import { describe, expect, it } from "vitest";

import { hampirKedaluwarsa, rekomendasiTerbuka } from "../lib/location-network";

const NOW = new Date("2026-10-29T03:00:00Z");

function batch(over: Record<string, unknown> = {}) {
  return {
    id: "b1",
    location: "Jakarta",
    quantity_kg: 100,
    safety_status: "pass",
    quarantine_status: "none",
    usable_until: "2026-11-02T03:00:00Z", // 4 hari lagi
    ...over,
  };
}

describe("hampirKedaluwarsa", () => {
  it("menghitung batch ≤7 hari per lokasi, mengabaikan yang masih lama", () => {
    const hasil = hampirKedaluwarsa(
      [
        batch({ id: "a" }),
        batch({ id: "b", usable_until: "2026-10-30T03:00:00Z" }),
        batch({ id: "c", usable_until: "2026-12-01T03:00:00Z" }),
      ],
      NOW
    );
    expect(hasil).toEqual({ Jakarta: 2 });
  });

  it("batch ditahan tidak dihitung: bukan stok yang boleh dipakai", () => {
    const hasil = hampirKedaluwarsa(
      [batch({ id: "a" }), batch({ id: "b", quarantine_status: "quarantined" })],
      NOW
    );
    expect(hasil).toEqual({ Jakarta: 1 });
  });

  it("batch gagal uji tidak dihitung", () => {
    const hasil = hampirKedaluwarsa(
      [batch({ id: "a", safety_status: "fail" }), batch({ id: "b" })],
      NOW
    );
    expect(hasil).toEqual({ Jakarta: 1 });
  });

  it("tanggal tidak terbaca tidak dihitung dan tidak menghasilkan 0 hari", () => {
    const hasil = hampirKedaluwarsa(
      [batch({ id: "a", usable_until: null }), batch({ id: "b", usable_until: "bukan tanggal" })],
      NOW
    );
    expect(hasil).toEqual({});
  });

  it("yang sudah lewat tetap dihitung (sudah kedaluwarsa = paling mendesak)", () => {
    const hasil = hampirKedaluwarsa([batch({ usable_until: "2026-10-28T03:00:00Z" })], NOW);
    expect(hasil).toEqual({ Jakarta: 1 });
  });

  it("lokasi kosong dilewati, spasi dinormalisasi", () => {
    const hasil = hampirKedaluwarsa(
      [
        batch({ id: "a", location: "  Bandung " }),
        batch({ id: "b", location: "" }),
        batch({ id: "c", location: null }),
      ],
      NOW
    );
    expect(hasil).toEqual({ Bandung: 1 });
  });
});

describe("rekomendasiTerbuka", () => {
  it("menghitung status yang masih menunggu tindakan per lokasi tujuan", () => {
    const hasil = rekomendasiTerbuka([
      { status: "proposed", target_location_name: "Jakarta" },
      { status: "pending_approval", target_location_name: "Jakarta" },
      { status: "executed", target_location_name: "Jakarta" },
      { status: "rejected", target_location_name: "Bogor" },
      { status: "verifier_flagged", target_location_name: "Bogor" },
    ]);
    expect(hasil).toEqual({ Jakarta: 2, Bogor: 1 });
  });

  it("lokasi tanpa nama dilewati (tidak ada 'undefined' sebagai kunci)", () => {
    const hasil = rekomendasiTerbuka([
      { status: "proposed", target_location_name: null },
      { status: "proposed" },
    ]);
    expect(hasil).toEqual({});
  });

  it("kosong/null aman", () => {
    expect(rekomendasiTerbuka(null)).toEqual({});
    expect(rekomendasiTerbuka([])).toEqual({});
  });
});
