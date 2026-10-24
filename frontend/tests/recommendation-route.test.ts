/**
 * Baris "siapa yang mengirim" pada kartu rekomendasi (24 Okt 2026).
 *
 * Masalah yang dilaporkan pemilik: kartu hanya menyebut WILAYAH, jadi tidak
 * jelas apakah barang datang dari pemasok atau dari SPPG lain. Kontraknya:
 * kalimat hanya muncul bila backend mengirim fakta yang cukup — tidak ada
 * kalimat karangan saat `supplier_name`/`pengirim` kosong.
 */
import { describe, expect, it } from "vitest";

import { routeLineOf } from "../components/RecommendationCard";

describe("routeLineOf", () => {
  it("menyebut nama pemasok dan tujuannya", () => {
    expect(
      routeLineOf({
        supplier_name: "CV Ambarawa Telur Utama",
        pengirim: "pemasok",
        status: "executed",
        target_location_name: "Bandung",
      })
    ).toBe("Dikirim pemasok CV Ambarawa Telur Utama ke Bandung");
  });

  it("menegaskan bila stok dipindahkan antar-SPPG, bukan dari pemasok", () => {
    expect(
      routeLineOf({ pengirim: "antar_sppg", target_location_name: "Jakarta" })
    ).toBe("Bukan dari pemasok — stok dipindahkan antar-SPPG ke Jakarta");
  });

  it("tanpa tujuan tetap terbaca", () => {
    expect(routeLineOf({ supplier_name: "UD Blitar Telur Makmur", status: "executed" })).toBe(
      "Dikirim pemasok UD Blitar Telur Makmur"
    );
  });

  it("sebelum disetujui menulis RENCANA, bukan Dikirim", () => {
    expect(
      routeLineOf({
        supplier_name: "CV Cengkareng Protein Mandiri",
        status: "pending_approval",
        target_location_name: "Jakarta",
      })
    ).toBe("Rencana kirim dari pemasok CV Cengkareng Protein Mandiri ke Jakarta");
  });

  it("tanpa fakta yang cukup: tidak ada baris (bukan karangan)", () => {
    expect(routeLineOf({})).toBeNull();
    expect(routeLineOf(null)).toBeNull();
    expect(routeLineOf({ pengirim: null })).toBeNull();
  });
});
