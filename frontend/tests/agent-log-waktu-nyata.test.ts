// Waktu jejak Agent Log harus jujur (audit 29 Okt 2026).
//
// Dua cacat yang ditutup di sini:
//  1. `formatClockUtc` memotong ISO jadi jam saja, sehingga langkah yang terjadi
//     KEMARIN tampil seolah hari ini. 81 dari 109 baris trace di DB punya
//     `step_at` sebelum `created_at` keputusannya — kalau tanggalnya tidak
//     dicetak, pembaca tidak punya cara melihatnya.
//  2. Label kolom "Verifikasi" mencetak kunci mentah huruf kecil ("menunggu")
//     di sebelah label kalimat ("Menunggu persetujuan").

import { describe, expect, it } from "vitest";

import { catatanAwalJejak, jejakSebelumKeputusan } from "../lib/agent-trace";
import { formatTraceWib } from "../lib/datetime";
import {
  TANPA_KOMODITAS,
  commodityOptions,
  filterDecisions,
  labelVerifikasi,
} from "../lib/decision-table";

const SEKARANG = new Date("2026-10-29T03:10:00Z");

describe("formatTraceWib", () => {
  it("mencetak tanggal, jam, dan zona — bukan jam saja", () => {
    expect(formatTraceWib("2026-10-28T01:41:21Z", SEKARANG)).toBe("28 Okt 08.41 WIB");
  });

  it("mencetak tahun bila berbeda dari tahun berjalan", () => {
    expect(formatTraceWib("2024-05-04T01:00:00Z", SEKARANG)).toBe("4 Mei 2024 08.00 WIB");
  });

  it("pergantian tahun dihitung dalam WIB, bukan zona mesin", () => {
    // 31 Des 2025 17.05 UTC = 1 Jan 2026 00.05 WIB — tahunnya SAMA dengan
    // `sekarang`, jadi tahun tidak dicetak.
    expect(formatTraceWib("2025-12-31T17:05:00Z", SEKARANG)).toBe("1 Jan 00.05 WIB");
  });

  it("nilai kosong atau tidak sah tetap '—', bukan RangeError", () => {
    expect(formatTraceWib(null, SEKARANG)).toBe("—");
    expect(formatTraceWib("bukan-tanggal", SEKARANG)).toBe("—");
  });
});

describe("jejakSebelumKeputusan", () => {
  const LANGKAH = [
    { step_name: "DETECT", step_at: "2026-10-28T01:41:21Z" },
    { step_name: "DECIDE", step_at: "2026-10-28T01:43:21Z" },
  ];

  it("menghitung langkah yang tercatat sebelum keputusan dibuat", () => {
    const hasil = jejakSebelumKeputusan("2026-10-29T02:42:11Z", LANGKAH);
    expect(hasil.jumlah).toBe(2);
    expect(hasil.pertama).toBe("2026-10-28T01:41:21Z");
  });

  it("nol bila semua langkah terjadi setelah keputusan dibuat", () => {
    const hasil = jejakSebelumKeputusan("2026-10-28T01:00:00Z", LANGKAH);
    expect(hasil.jumlah).toBe(0);
    expect(hasil.pertama).toBeNull();
  });

  it("tanpa created_at, tidak mengklaim apa pun", () => {
    expect(jejakSebelumKeputusan(null, LANGKAH).jumlah).toBe(0);
  });
});

describe("labelVerifikasi", () => {
  it("memakai kalimat, bukan kunci mentah", () => {
    expect(labelVerifikasi("menunggu")).toBe("Menunggu verifikasi");
    expect(labelVerifikasi("terverifikasi")).toBe("Terverifikasi");
    expect(labelVerifikasi("ditolak")).toBe("Ditolak");
  });

  it("keadaan lain ditulis '—'", () => {
    expect(labelVerifikasi("lainnya")).toBe("—");
  });
});

describe("baris tanpa komoditas tetap terjangkau", () => {
  const BARIS = [
    { decision_id: "a", decision_type: "t", status: "pending_approval", commodity_name: "beras" },
    { decision_id: "b", decision_type: "t", status: "pending_approval", commodity_name: "telur" },
    { decision_id: "c", decision_type: "t", status: "pending_approval", commodity_name: null },
  ] as never;

  it("opsi komoditas menyebut jumlah baris tanpa komoditas", () => {
    const opsi = commodityOptions(BARIS as never);
    const tanpa = opsi.find((o) => o.value === TANPA_KOMODITAS);
    expect(tanpa?.count).toBe(1);
  });

  it("menyaring 'tanpa komoditas' mengembalikan baris yang tepat", () => {
    const hasil = filterDecisions(BARIS as never, { commodity: TANPA_KOMODITAS });
    expect(hasil.map((r) => r.decision_id)).toEqual(["c"]);
  });
});

describe("catatanAwalJejak", () => {
  it("menyebut tahap awal yang hilang, bukan diam", () => {
    expect(catatanAwalJejak([{ step_name: "LEARN" }])).toBe(
      "Jejak ini dimulai dari LEARN, bukan DETECT — tahap awal tidak tercatat pada data demo.",
    );
  });

  it("jejak yang dimulai DETECT tidak diberi catatan", () => {
    expect(catatanAwalJejak([{ step_name: "DETECT" }, { step_name: "DECIDE" }])).toBeNull();
  });

  it("jejak kosong tidak mengklaim apa pun", () => {
    expect(catatanAwalJejak([])).toBeNull();
  });
});
