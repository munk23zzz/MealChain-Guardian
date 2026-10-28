// Kontrak blok "Limbah" versi ringkas untuk halaman Location Network.
//
// Bedanya dengan `wasteFacts` (dipakai kartu Surplus & Limbah lama):
//   * tiga baris saja — tercatat, dialihkan, tanpa mitra; daftar nama mitra
//     berhenti ditampilkan di sini karena bukan angka yang diputuskan;
//   * label pendek (≤ 12 karakter) supaya satu baris dengan nilai;
//   * bila server belum punya angka, hasilnya array KOSONG — pemanggil menulis
//     satu kalimat "Belum dicatat.", bukan tiga baris "—" berhint panjang.

import { describe, expect, it } from "vitest";

import { wasteRingkas } from "../lib/surplus";

const ADA = {
  window_days: 30,
  recorded: { available: true, kg: 469.7, events: 64 },
  diverted: { available: true, kg: 12.5, events: 1 },
  unassigned: { available: true, kg: 457.2, events: 63 },
  partners: [{ name: "Bank Sampah Melati", kg: 12.5, events: 1 }],
};

describe("wasteRingkas", () => {
  it("menghasilkan tepat tiga baris: tercatat, dialihkan, tanpa mitra", () => {
    const rows = wasteRingkas(ADA);
    expect(rows.map((r) => r.label)).toEqual(["Tercatat", "Dialihkan", "Tanpa mitra"]);
    expect(rows.map((r) => r.value)).toEqual(["469,7 kg", "12,5 kg", "457,2 kg"]);
  });

  it("hint hanya menyebut jumlah peristiwa, bukan kalimat", () => {
    const rows = wasteRingkas(ADA);
    expect(rows[0].hint).toBe("64 peristiwa");
    expect(rows[1].hint).toBe("1 peristiwa");
  });

  it("tanpa angka dari server: array kosong, bukan tiga baris '—'", () => {
    expect(wasteRingkas(null)).toEqual([]);
    expect(wasteRingkas({})).toEqual([]);
    expect(wasteRingkas({ recorded: { available: false } })).toEqual([]);
  });

  it("sebagian tersedia: baris yang tidak ada menulis '—' tanpa hint karangan", () => {
    const rows = wasteRingkas({
      recorded: { available: true, kg: 10, events: 2 },
      diverted: { available: false },
      unassigned: { available: false },
    });
    expect(rows.map((r) => r.value)).toEqual(["10 kg", "—", "—"]);
    expect(rows[1].hint).toBeNull();
  });
});
