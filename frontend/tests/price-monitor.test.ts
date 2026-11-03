// Monitor harga pasar — logika murni (lib/price-monitor.ts).
//
// Yang dipaku: jendela mengikuti tanggal publikasi, sel kosong tetap null
// (bukan 0), pemetaan lokasi peta → wilayah PIHPS + cadangan provinsi apa
// adanya, dan ringkasan delta dihitung dari publikasi sebelumnya.
import * as sumber from "../lib/price-monitor";
import { describe, expect, it } from "vitest";

import {
  KOMODITAS_PANEL,
  PETA_WILAYAH,
  formatPersen,
  formatRp,
  kodeTersedia,
  labelTanggalPanjang,
  labelTanggalPendek,
  labelJamTarik,
  labelWaktuTarik,
  persenPerubahan,
  ringkasKomoditas,
  ringkasanTeks,
  susunSeri,
  wilayahUntuk,
  type MonitorBaris,
  type MonitorPayload,
} from "../lib/price-monitor";

function baris(
  tanggal: string,
  kode: string,
  harga: number,
  wilayah = "Kota Jakarta Pusat"
): MonitorBaris {
  return {
    commodity_code: kode,
    commodity_label: kode === "com_10" ? "Telur Ayam Ras Segar" : "Beras Kualitas Medium I",
    region_name: wilayah,
    region_level: wilayah.startsWith("Kota") ? "kota" : "provinsi",
    observed_on: tanggal,
    price_per_kg: harga,
  };
}

const TANGGAL = ["2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23"];

function payload(rows: MonitorBaris[]): MonitorPayload {
  return {
    status: rows.length ? "ok" : "kosong",
    alasan: null,
    source: "PIHPS Bank Indonesia",
    source_url: "https://www.bi.go.id/hargapangan",
    market: "Pasar Tradisional",
    unit: "Rp/kg",
    fetched_at: "2026-10-26T09:54:44+00:00",
    window: { start: "2026-09-28", end: "2026-10-26" },
    days: 30,
    commodities: [
      { code: "com_3", label: "Beras Kualitas Medium I", project_key: "beras" },
      { code: "com_10", label: "Telur Ayam Ras Segar", project_key: "telur" },
    ],
    regions: [
      { level: "kota", name: "Kota Jakarta Pusat" },
      { level: "provinsi", name: "Jawa Barat" },
      { level: "nasional", name: "Semua Provinsi" },
    ],
    coverage: {
      tanggal_terisi: 5,
      tanggal_pertama: TANGGAL[0],
      tanggal_terakhir: TANGGAL[4],
    },
    movers: [
      { region_name: "Kota Medan", awal: 30000, akhir: 27900, delta_pct: -7 },
    ],
    rows,
  };
}

describe("susunSeri", () => {
  it("satu baris per tanggal publikasi, kolom per komoditas", () => {
    const rows = TANGGAL.flatMap((t, i) => [
      baris(t, "com_10", 25000 + i * 100),
      baris(t, "com_3", 17050),
    ]);
    const { data, tanggal } = susunSeri(rows, ["com_10", "com_3"]);
    expect(tanggal).toEqual(TANGGAL);
    expect(data).toHaveLength(5);
    expect(data[0].com_10).toBe(25000);
    expect(data[4].com_3).toBe(17050);
    expect(data[0].label).toBe("19 Okt");
  });

  it("hari tanpa baris tidak muncul dan tidak menjadi 0", () => {
    const rows = [baris("2026-10-19", "com_10", 25000), baris("2026-10-21", "com_10", 25200)];
    const { data } = susunSeri(rows, ["com_10"]);
    expect(data.map((d) => d.tanggal)).toEqual(["2026-10-19", "2026-10-21"]);
    expect(data.some((d) => d.com_10 === 0)).toBe(false);
  });

  it("komoditas terpilih tanpa baris diisi null (garis putus, bukan nol)", () => {
    const rows = [baris("2026-10-19", "com_10", 25000)];
    const { data } = susunSeri(rows, ["com_10", "com_7"]);
    expect(data[0].com_7).toBeNull();
  });

  it("harga 0 / negatif diabaikan (bukan angka sah)", () => {
    const rows = [baris("2026-10-19", "com_10", 0), baris("2026-10-20", "com_10", -5)];
    const { data } = susunSeri(rows, ["com_10"]);
    expect(data).toHaveLength(0);
  });

  it("menambahkan kolom indeks basis 100 untuk tiap komoditas", () => {
    const rows = TANGGAL.flatMap((t, i) => [
      baris(t, "com_10", 25000 + i * 100),
      baris(t, "com_3", 17050),
    ]);
    const { data, basis } = susunSeri(rows, ["com_10", "com_3"]);
    expect(basis.com_10).toBe(25000);
    // Titik pertama = 100, titik terakhir = +1,6%
    expect(data[0].idx_com_10).toBe(100);
    expect(data[4].idx_com_10).toBeCloseTo(101.6, 1);
    // Komoditas yang harganya tidak bergerak tetap 100 (bukan null).
    expect(data[4].idx_com_3).toBeCloseTo(100, 5);
  });

  it("tanggal diurutkan naik walau masukan acak", () => {
    const rows = [baris("2026-10-21", "com_10", 3), baris("2026-10-19", "com_10", 1)];
    const { tanggal } = susunSeri(rows, ["com_10"]);
    expect(tanggal).toEqual(["2026-10-19", "2026-10-21"]);
  });
});

describe("ringkasKomoditas", () => {
  const rows = TANGGAL.map((t, i) => baris(t, "com_10", 25000 + i * 100));

  it("memakai titik terakhir + delta terhadap publikasi sebelumnya", () => {
    const hasil = ringkasKomoditas(rows, "com_10");
    expect(hasil.terakhir).toBe(25400);
    expect(hasil.tanggalTerakhir).toBe("2026-10-23");
    expect(hasil.deltaHarian).toBeCloseTo(0.398, 2);
    expect(hasil.jumlahTitik).toBe(5);
  });

  it("delta tujuh publikasi butuh minimal 8 titik — kurang dari itu memakai titik pertama", () => {
    const hasil = ringkasKomoditas(rows, "com_10");
    // 5 titik < 8 → pembanding = titik pertama (25000)
    expect(hasil.deltaTujuh).toBeCloseTo(1.6, 2);
  });

  it("tertinggi & terendah membawa tanggalnya", () => {
    const hasil = ringkasKomoditas(rows, "com_10");
    expect(hasil.tertinggi).toEqual({ nilai: 25400, tanggal: "2026-10-23" });
    expect(hasil.terendah).toEqual({ nilai: 25000, tanggal: "2026-10-19" });
  });

  it("tanpa baris: semua null, bukan 0", () => {
    const hasil = ringkasKomoditas([], "com_10");
    expect(hasil.terakhir).toBeNull();
    expect(hasil.deltaHarian).toBeNull();
    expect(hasil.tertinggi).toBeNull();
    expect(hasil.jumlahTitik).toBe(0);
  });
});

describe("wilayahUntuk", () => {
  const tersedia = payload([]).regions;

  it("lokasi peta dipetakan ke nama kota PIHPS", () => {
    expect(wilayahUntuk("Jakarta", tersedia)).toEqual({
      nama: "Kota Jakarta Pusat",
      cadangan: false,
      catatan: null,
    });
  });

  it("Cianjur tidak punya baris kota → cadangan provinsi disebut apa adanya", () => {
    const hasil = wilayahUntuk("Cianjur", tersedia);
    expect(hasil.nama).toBe("Jawa Barat");
    expect(hasil.cadangan).toBe(true);
    expect(hasil.catatan).toContain("Cianjur");
    expect(hasil.catatan).toContain("Jawa Barat");
  });

  it("tanpa lokasi aktif memakai baris nasional", () => {
    const hasil = wilayahUntuk(null, tersedia);
    expect(hasil.nama).toBe("Semua Provinsi");
    expect(hasil.cadangan).toBe(true);
  });

  it("lokasi di luar peta diakui, bukan ditebak", () => {
    const hasil = wilayahUntuk("Atlantis", tersedia);
    expect(hasil.nama).toBeNull();
    expect(hasil.catatan).toContain("Atlantis");
  });

  it("peta wilayah memuat semua lokasi demo dan hanya Cianjur tanpa baris kota", () => {
    const tanpaKota = Object.entries(PETA_WILAYAH)
      .filter(([, v]) => v.pihps === null)
      .map(([k]) => k);
    expect(tanpaKota).toEqual(["Cianjur"]);
    expect(Object.keys(PETA_WILAYAH)).toHaveLength(10);
  });
});

describe("format", () => {
  it("rupiah tanpa desimal", () => {
    expect(formatRp(25700)).toBe("Rp25.700");
    expect(formatRp(17050.4)).toBe("Rp17.050");
    expect(formatRp(null)).toBe("—");
  });

  it("persen selalu bertanda", () => {
    expect(formatPersen(2.44)).toBe("+2,4%");
    expect(formatPersen(-3.1)).toBe("−3,1%");
    expect(formatPersen(0)).toBe("0,0%");
    expect(formatPersen(null)).toBe("—");
  });

  it("tanggal Indonesia", () => {
    expect(labelTanggalPendek("2026-10-28")).toBe("28 Okt");
    expect(labelTanggalPanjang("2026-10-28")).toBe("28 Okt 2026");
    expect(labelTanggalPendek("")).toBe("—");
    expect(labelTanggalPendek("2026-13-01")).toBe("—");
  });

  it("waktu tarik dalam WIB", () => {
    // 09:54 UTC = 16:54 WIB
    expect(labelWaktuTarik("2026-10-28T09:54:44+00:00")).toContain("16.54 WIB");
    expect(labelWaktuTarik(null)).toBe("—");
  });

  it("persenPerubahan menolak pembagi nol", () => {
    expect(persenPerubahan(0, 10)).toBeNull();
    expect(persenPerubahan(100, 110)).toBeCloseTo(10, 5);
  });
});

describe("kontrak kamus", () => {
  it("chip panel hanya memuat komoditas yang punya seri PIHPS", () => {
    expect(KOMODITAS_PANEL.map((k) => k.nama)).toEqual(["Beras", "Telur", "Ayam"]);
    expect(KOMODITAS_PANEL.map((k) => k.kode)).not.toContain("wortel");
  });

  it("catatan 'wortel tanpa acuan PIHPS' sudah tidak ada (permintaan pemilik)", () => {
    // 29 Okt 2026: kalimat "Wortel tidak termasuk 21 komoditas PIHPS…" dihapus
    // dari panel. Konstanta & teksnya ikut dicabut supaya tidak ada sisa yang
    // bisa dipasang kembali tanpa sengaja — bukan sekadar disembunyikan di UI.
    expect(Object.keys(sumber)).not.toContain("TANPA_SUMBER_PIHP");
  });

  it("labelJamTarik hanya menulis jam, tanpa mengulang tanggal", () => {
    // Baris sumber sudah menyebut tanggal data terakhir di sebelahnya.
    expect(labelJamTarik("2026-10-28T09:54:00Z")).toBe("16.54 WIB");
    expect(labelJamTarik(null)).toBe("—");
    expect(labelJamTarik("bukan-tanggal")).toBe("—");
  });

  it("kodeTersedia membaca kode dari baris", () => {
    const set = kodeTersedia(payload([baris("2026-10-19", "com_10", 25000)]));
    expect(set.has("com_10")).toBe(true);
    expect(set.has("com_7")).toBe(false);
    expect(kodeTersedia(null).size).toBe(0);
  });
});

describe("ringkasanTeks", () => {
  it("mengucapkan arah naik/turun, bukan hanya angka", () => {
    const rows = TANGGAL.map((t, i) => baris(t, "com_10", 25000 + i * 100));
    const teks = ringkasanTeks([ringkasKomoditas(rows, "com_10")], () => "Telur");
    expect(teks).toContain("Telur");
    expect(teks).toContain("naik");
    expect(teks).toContain("Rp25.400");
  });

  it("tanpa angka: kalimat jujur, bukan grafik kosong tanpa penjelasan", () => {
    expect(ringkasanTeks([ringkasKomoditas([], "com_10")], () => "Telur")).toMatch(
      /Belum ada angka/i
    );
  });
});
