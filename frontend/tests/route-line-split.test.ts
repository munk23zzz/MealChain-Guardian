// Memotong garis jalur pada posisi yang sudah ditempuh (Arah C) — logika MURNI.
// Aturan yang diuji: tidak ada tebakan (progress null → null), 0/1 dijepit apa
// adanya, titik potong tepat di antara dua titik, dan geometri rusak ditolak.
import { describe, expect, it } from "vitest";

import { lineSplit } from "../lib/route-line-split";

const GARIS: [number, number][] = [
  [0, 0],
  [2, 0],
  [2, 1],
];

describe("potong garis jalur", () => {
  it("tanpa angka progress → null (pemanggil menggambar apa adanya)", () => {
    expect(lineSplit(GARIS, null)).toBeNull();
    expect(lineSplit(GARIS, undefined)).toBeNull();
    expect(lineSplit(GARIS, Number.NaN)).toBeNull();
  });

  it("geometri kurang dari dua titik tidak bisa dipotong", () => {
    expect(lineSplit([], 0.5)).toBeNull();
    expect(lineSplit([[107, -6]], 0.5)).toBeNull();
    expect(lineSplit(null, 0.5)).toBeNull();
  });

  it("titik rusak (NaN) ditolak, bukan digambar setengah", () => {
    expect(lineSplit([[0, 0], [Number.NaN, 0]], 0.5)).toBeNull();
  });

  it("progress 0: seluruh garis belum ditempuh", () => {
    const split = lineSplit(GARIS, 0)!;
    expect(split.done).toEqual([]);
    expect(split.todo).toEqual(GARIS);
    expect(split.progress).toBe(0);
  });

  it("progress 1: seluruh garis sudah ditempuh", () => {
    const split = lineSplit(GARIS, 1)!;
    expect(split.done).toEqual(GARIS);
    expect(split.todo).toEqual([]);
    expect(split.progress).toBe(1);
  });

  it("nilai di luar 0–1 dijepit, tidak mengubah bentuk", () => {
    expect(lineSplit(GARIS, 1.4)!.progress).toBe(1);
    expect(lineSplit(GARIS, -0.3)!.progress).toBe(0);
    expect(lineSplit(GARIS, -0.3)!.todo).toEqual(GARIS);
  });

  it("setengah jalan pada garis lurus: potongan tepat di tengah", () => {
    const split = lineSplit(
      [
        [0, 0],
        [2, 0],
      ],
      0.5
    )!;
    expect(split.done).toHaveLength(2);
    expect(split.todo).toHaveLength(2);
    // Titik potong sama persis di kedua bagian — tidak ada celah di peta.
    expect(split.done[split.done.length - 1]).toEqual(split.todo[0]);
    expect(split.done[1][0]).toBeCloseTo(1, 6);
    expect(split.done[1][1]).toBeCloseTo(0, 6);
  });

  it("potongan mengikuti PANJANG tiap segmen, bukan jumlah titik", () => {
    // Segmen 1 (0,0)→(2,0) ±222 km; segmen 2 (2,0)→(2,1) ±111 km; total ±333 km.
    // 50% = ±167 km → masih di segmen 1, 3/4 jalan.
    const split = lineSplit(GARIS, 0.5)!;
    expect(split.done).toHaveLength(2);
    expect(split.done[1][0]).toBeCloseTo(1.5, 3);
    expect(split.todo).toHaveLength(3);
    expect(split.todo[0]).toEqual(split.done[1]);
  });

  it("75% sudah melewati simpang: titik simpang ikut di bagian selesai", () => {
    const split = lineSplit(GARIS, 0.75)!;
    expect(split.done).toEqual([
      [0, 0],
      [2, 0],
      expect.anything(),
    ]);
    expect(split.done[1]).toEqual([2, 0]);
  });

  it("geometri bertumpuk (panjang nol) tidak mengaku selesai", () => {
    const split = lineSplit(
      [
        [107, -6],
        [107, -6],
      ],
      0.4
    )!;
    expect(split.done).toEqual([
      [107, -6],
      [107, -6],
    ]);
    expect(split.todo).toEqual([]);
    // Angka server dibiarkan apa adanya — jangan dinaikkan jadi 1 (itu klaim).
    expect(split.progress).toBe(0.4);
  });
});
