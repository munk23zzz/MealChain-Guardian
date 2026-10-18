import { describe, expect, it } from "vitest";
import {
  KLASTER_JARAK_PIKSEL,
  KLASTER_ZOOM_MAKS,
  kelompokkanBertumpuk,
  gabungKlasterBerdekatan,
  klasterPerluGelembung,
  labelKlaster,
  offsetSpider,
  pusatKlaster,
} from "../lib/map-cluster";

describe("kelompokkanBertumpuk", () => {
  it("menggabungkan penanda yang berjarak kurang dari radius", () => {
    // Jarak nyata dari audit 375 px: pusat (158,1223), (153,1223), (149,1220).
    const hasil = kelompokkanBertumpuk([
      { id: "jakarta", x: 158, y: 1223 },
      { id: "bandung", x: 153, y: 1223 },
      { id: "bogor", x: 149, y: 1220 },
    ]);
    expect(hasil).toHaveLength(1);
    expect(hasil[0].map((t) => t.id)).toEqual(["jakarta", "bandung", "bogor"]);
  });

  it("memisahkan penanda yang jauh (Jakarta vs Surabaya)", () => {
    const hasil = kelompokkanBertumpuk([
      { id: "jakarta", x: 100, y: 100 },
      { id: "surabaya", x: 400, y: 320 },
    ]);
    expect(hasil).toHaveLength(2);
    expect(hasil.every((g) => g.length === 1)).toBe(true);
  });

  it("memakai pusat massa, bukan titik pertama, saat menilai kedekatan", () => {
    // c(0,0), (20,0) -> pusat 10; titik (28,0) berjarak 18 dari pusat (masuk),
    // meski 28 dari titik pertama (di luar radius).
    const hasil = kelompokkanBertumpuk(
      [
        { id: "a", x: 0, y: 0 },
        { id: "b", x: 20, y: 0 },
        { id: "c", x: 28, y: 0 },
      ],
      24
    );
    expect(hasil).toHaveLength(1);
    expect(hasil[0]).toHaveLength(3);
  });

  it("deterministik: urutan input yang sama memberi kelompok yang sama", () => {
    const titik = [
      { id: "a", x: 10, y: 10 },
      { id: "b", x: 20, y: 12 },
      { id: "c", x: 300, y: 300 },
      { id: "d", x: 305, y: 302 },
    ];
    const sekali = kelompokkanBertumpuk(titik).map((g) => g.map((t) => t.id));
    const dua = kelompokkanBertumpuk(titik).map((g) => g.map((t) => t.id));
    expect(sekali).toEqual(dua);
    expect(sekali).toEqual([
      ["a", "b"],
      ["c", "d"],
    ]);
  });

  it("radius bisa diatur dan radius kecil memisahkan yang tadinya satu kelompok", () => {
    const titik = [
      { id: "a", x: 0, y: 0 },
      { id: "b", x: 30, y: 0 },
    ];
    expect(kelompokkanBertumpuk(titik, 40)).toHaveLength(1);
    expect(kelompokkanBertumpuk(titik, 10)).toHaveLength(2);
  });

  it("daftar kosong menghasilkan tanpa kelompok", () => {
    expect(kelompokkanBertumpuk([])).toEqual([]);
  });
});

describe("pusatKlaster & klasterPerluGelembung", () => {
  it("pusat kelompok adalah rata-rata koordinat", () => {
    expect(pusatKlaster([{ id: "a", x: 0, y: 0 }, { id: "b", x: 10, y: 20 }])).toEqual({ x: 5, y: 10 });
  });

  it("pusat kelompok kosong tidak melempar", () => {
    expect(pusatKlaster([])).toEqual({ x: 0, y: 0 });
  });

  it("hanya kelompok 2+ yang butuh gelembung", () => {
    const grup = kelompokkanBertumpuk([
      { id: "a", x: 0, y: 0 },
      { id: "b", x: 5, y: 0 },
      { id: "c", x: 500, y: 500 },
    ]);
    const perlu = klasterPerluGelembung(grup);
    expect(perlu).toHaveLength(1);
    expect(perlu[0].map((t) => t.id)).toEqual(["a", "b"]);
  });
});

describe("gabungKlasterBerdekatan", () => {
  it("menggabungkan dua kelompok yang pusatnya berdekatan", () => {
    const a = [{ id: "a1", x: 100, y: 100 }, { id: "a2", x: 104, y: 100 }];
    const b = [{ id: "b1", x: 110, y: 118 }, { id: "b2", x: 114, y: 118 }];
    const hasil = gabungKlasterBerdekatan([a, b], 24);
    expect(hasil).toHaveLength(1);
    expect(hasil[0].map((t) => t.id)).toEqual(["a1", "a2", "b1", "b2"]);
  });

  it("tidak menggabungkan kelompok yang berjauhan", () => {
    const a = [{ id: "a1", x: 0, y: 0 }, { id: "a2", x: 4, y: 0 }];
    const b = [{ id: "b1", x: 300, y: 300 }, { id: "b2", x: 304, y: 300 }];
    expect(gabungKlasterBerdekatan([a, b], 24)).toHaveLength(2);
  });

  it("menggabung berantai: kelompok C baru ikut setelah pusat A+B bergeser", () => {
    // A(0,0), B(20,0) -> pusat (10,0); C(10,24) berjarak 24 dari pusat itu,
    // tetapi 26 px dari A maupun B — jadi ia hanya bergabung pada putaran kedua.
    const a = [{ id: "a", x: 0, y: 0 }];
    const b = [{ id: "b", x: 20, y: 0 }];
    const c = [{ id: "c", x: 10, y: 24 }];
    const hasil = gabungKlasterBerdekatan([a, b, c], 24);
    expect(hasil).toHaveLength(1);
    expect(hasil[0].map((t) => t.id).sort()).toEqual(["a", "b", "c"]);
  });

  it("tidak mengubah input asal", () => {
    const a = [{ id: "a1", x: 0, y: 0 }, { id: "a2", x: 2, y: 0 }];
    const b = [{ id: "b1", x: 6, y: 0 }];
    gabungKlasterBerdekatan([a, b], 24);
    expect(a).toHaveLength(2);
    expect(b).toHaveLength(1);
  });

  it("daftar kosong aman", () => {
    expect(gabungKlasterBerdekatan([], 24)).toEqual([]);
  });
});

describe("offsetSpider", () => {
  it("satu penanda tidak digeser", () => {
    expect(offsetSpider(1)).toEqual([{ dx: 0, dy: 0 }]);
  });

  it("menyebar n penanda pada radius tetap dan tidak ada yang berimpit", () => {
    const n = 5;
    const hasil = offsetSpider(n, 30);
    expect(hasil).toHaveLength(n);
    const kunci = new Set(hasil.map((o) => `${o.dx},${o.dy}`));
    expect(kunci.size).toBe(n);
    for (const o of hasil) {
      const r = Math.hypot(o.dx, o.dy);
      expect(r).toBeGreaterThanOrEqual(29);
      expect(r).toBeLessThanOrEqual(31);
    }
  });

  it("hasil deterministik untuk jumlah yang sama", () => {
    expect(offsetSpider(4)).toEqual(offsetSpider(4));
  });
});

describe("labelKlaster", () => {
  it("menyebut jumlah dan nama lokasi", () => {
    expect(labelKlaster(["Bandung", "Bogor"])).toBe(
      "2 lokasi berdekatan: Bandung, Bogor. Tekan untuk memperbesar peta."
    );
  });

  it("membuang nama kosong dan tidak menyisakan koma menggantung", () => {
    expect(labelKlaster(["Bandung", "  ", ""])).toBe(
      "1 lokasi berdekatan: Bandung. Tekan untuk memperbesar peta."
    );
  });

  it("tetap memberi kalimat bermakna saat nama kosong semua", () => {
    expect(labelKlaster([])).toContain("Tekan untuk memperbesar peta");
  });
});

describe("konstanta", () => {
  it("radius klaster minimal sebesar target WCAG 2.5.8", () => {
    expect(KLASTER_JARAK_PIKSEL).toBeGreaterThanOrEqual(24);
  });

  it("klaster berhenti sebelum zoom jalan (agar pin kota terpisah)", () => {
    expect(KLASTER_ZOOM_MAKS).toBeLessThan(22);
  });
});
