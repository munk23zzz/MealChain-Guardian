import { describe, expect, it } from "vitest";
import { posisiDanArah, siapkanJalur, titikMengalir, titikPada, wakeLine } from "../lib/route-flow";

/**
 * Titik-titik yang bergerak di sepanjang jalur (permintaan pemilik 20 Okt 2026:
 * jalur pemasok yang sedang mengirim "menyala"). MapLibre tidak punya animasi
 * dash-offset, jadi gerak dibuat dari titik yang benar-benar berjalan di
 * geometri jalan.
 *
 * Angka panjang memakai bidang datar (equirectangular) dengan koreksi cos(lat):
 * untuk jarak 100–700 km di Jawa galatnya < 0,3% — cukup untuk menempatkan titik
 * hias, dan jauh lebih murah daripada haversine per frame.
 */

const garis: [number, number][] = [
  [107.6, -6.9],
  [107.6, -6.8],
  [107.7, -6.8],
];

describe("siapkanJalur", () => {
  it("menolak jalur yang tidak bisa ditempuh", () => {
    expect(siapkanJalur([])).toBeNull();
    expect(siapkanJalur([[107.6, -6.9]])).toBeNull();
    // Dua titik identik = panjang nol; titik mana pun akan menempel di ujung.
    expect(siapkanJalur([[107.6, -6.9], [107.6, -6.9]])).toBeNull();
  });

  it("menghitung panjang kumulatif per titik", () => {
    const jalur = siapkanJalur(garis);
    expect(jalur).not.toBeNull();
    const j = jalur!;
    expect(j.kumulatif).toHaveLength(3);
    expect(j.kumulatif[0]).toBe(0);
    expect(j.kumulatif[1]).toBeGreaterThan(0);
    expect(j.total).toBeCloseTo(j.kumulatif[2], 6);
  });

  it("memberi bobot lebih besar pada segmen bujur pada lintang tinggi (cos lat)", () => {
    // Pada lintang 60°, 0,1° bujur hanya separuh panjang 0,1° bujur di ekuator.
    const ekuator = siapkanJalur([[0, 0], [0.1, 0]])!;
    const tinggi = siapkanJalur([[0, 60], [0.1, 60]])!;
    expect(tinggi.total).toBeCloseTo(ekuator.total * Math.cos((60 * Math.PI) / 180), 3);
  });
});

describe("titikPada", () => {
  it("mengembalikan ujung jalur pada frac 0 dan 1", () => {
    const jalur = siapkanJalur(garis)!;
    expect(titikPada(jalur, 0)).toEqual([107.6, -6.9]);
    expect(titikPada(jalur, 1)).toEqual([107.7, -6.8]);
  });

  it("berada di segmen yang benar pada frac tengah", () => {
    const jalur = siapkanJalur(garis)!;
    const tengah = titikPada(jalur, 0.5);
    // Setengah panjang: separuh segmen pertama (bujur tetap) atau awal segmen
    // kedua — yang penting bukan ujung, dan masih di dalam kotak garis.
    expect(tengah[0]).toBeGreaterThanOrEqual(107.6);
    expect(tengah[0]).toBeLessThanOrEqual(107.7);
    expect(tengah[1]).toBeGreaterThanOrEqual(-6.9);
    expect(tengah[1]).toBeLessThanOrEqual(-6.8);
  });

  it("menjepit frac di luar 0..1", () => {
    const jalur = siapkanJalur(garis)!;
    expect(titikPada(jalur, -2)).toEqual([107.6, -6.9]);
    expect(titikPada(jalur, 5)).toEqual([107.7, -6.8]);
  });
});

describe("titikMengalir", () => {
  it("menyebar titik merata dan setiap titik bergerak maju", () => {
    const jalur = siapkanJalur(garis)!;
    const awal = titikMengalir(jalur, 0, { durasiMs: 6000, jumlah: 3 });
    expect(awal).toHaveLength(3);
    // Sebaran merata: titik ke-i ada di frac i/3 (titik pertama di pangkal).
    expect(awal[0]).toEqual(titikPada(jalur, 0));
    expect(awal[1]).toEqual(titikPada(jalur, 1 / 3));
    expect(awal[2]).toEqual(titikPada(jalur, 2 / 3));
    // Satu titik, tanpa membungkus: posisinya maju seiring waktu.
    const satu = [0, 800, 1600].map(
      (t) => titikMengalir(jalur, t, { durasiMs: 6000, jumlah: 1 })[0]
    );
    const jarakKePangkal = satu.map(([lng, lat]) => Math.hypot(lng - 107.6, lat + 6.9));
    expect(jarakKePangkal[1]).toBeGreaterThan(jarakKePangkal[0]);
    expect(jarakKePangkal[2]).toBeGreaterThan(jarakKePangkal[1]);
  });

  it("mengulang siklus: satu durasi penuh kembali ke posisi awal", () => {
    const jalur = siapkanJalur(garis)!;
    const awal = titikMengalir(jalur, 0, { durasiMs: 6000, jumlah: 3 });
    const siklus = titikMengalir(jalur, 6000, { durasiMs: 6000, jumlah: 3 });
    awal.forEach((titik, i) => {
      expect(siklus[i][0]).toBeCloseTo(titik[0], 6);
      expect(siklus[i][1]).toBeCloseTo(titik[1], 6);
    });
  });
});

describe("posisiDanArah (ikon mobil kiriman)", () => {
  // Ikon mobil harus menghadap arah perjalanan, bukan selalu ke atas.
  const utara: [number, number][] = [[107.6, -6.9], [107.6, -6.8]];
  const timur: [number, number][] = [[107.6, -6.9], [107.7, -6.9]];
  const selatan: [number, number][] = [[107.6, -6.8], [107.6, -6.9]];
  const barat: [number, number][] = [[107.7, -6.9], [107.6, -6.9]];

  it("menghitung arah 0/90/180/270 derajat (0 = utara, searah jarum jam)", () => {
    const kasus: Array<[[number, number][], number]> = [
      [utara, 0],
      [timur, 90],
      [selatan, 180],
      [barat, 270],
    ];
    for (const [garis, harapan] of kasus) {
      const jalur = siapkanJalur(garis)!;
      const { arah } = posisiDanArah(jalur, 0.5);
      // Selisih melingkar: 270 dan -90 harus dianggap sama.
      const selisih = Math.abs(((arah - harapan + 540) % 360) - 180);
      expect(selisih).toBeLessThan(0.5);
    }
  });

  it("mengembalikan posisi di sepanjang jalur bersama arahnya", () => {
    const jalur = siapkanJalur(timur)!;
    const { posisi, arah } = posisiDanArah(jalur, 0.5);
    expect(posisi[1]).toBeCloseTo(-6.9, 6);
    expect(posisi[0]).toBeGreaterThan(107.6);
    expect(posisi[0]).toBeLessThan(107.7);
    expect(Math.round(arah)).toBe(90);
  });
});

describe("wakeLine — ekor di belakang kendaraan", () => {
  const jalur = siapkanJalur([
    [107.0, -6.9],
    [107.2, -6.9],
  ])!;

  it("mengembalikan potongan yang berakhir tepat di posisi kendaraan", () => {
    const titik = wakeLine(jalur, 0.5, 0.1);
    expect(titik).toHaveLength(7);
    // Jalur lurus 107,0 → 107,2: frac 0,5 = 107,10; ekor 0,1 mulai di 107,08.
    expect(titik[0][0]).toBeCloseTo(107.08, 3);
    expect(titik[titik.length - 1][0]).toBeCloseTo(107.1, 3);
  });

  it("tidak menembus garis start walau kendaraan masih dekat awal", () => {
    const titik = wakeLine(jalur, 0.02, 0.1);
    expect(titik[0][0]).toBeCloseTo(107.0, 3);
    expect(titik[titik.length - 1][0]).toBeCloseTo(107.004, 3);
  });

  it("kosong saat kendaraan belum bergerak — bukan garis nol panjang", () => {
    expect(wakeLine(jalur, 0)).toEqual([]);
  });
});
