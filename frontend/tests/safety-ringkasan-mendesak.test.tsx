// Upgrade "Ringkasan pengawasan" (29 Okt 2026, lanjutan).
//
// Dua tambahan yang diuji di sini, keduanya memakai data yang SUDAH dikirim
// server — tidak ada angka baru yang dikarang komponen:
//
//   1. Baris "Paling mendesak": satu-satunya hal yang tidak bisa dibaca dari
//      lima angka — kapan batch paling cepat kedaluwarsa. Ambil dari
//      `usable_until` baris yang benar-benar tampil (cakupan yang sama dengan
//      angka di atasnya), bukan dari ringkasan baru.
//   2. Berat di bawah "Gagal uji": `failedKg` sudah dihitung server; sebelumnya
//      hanya "Ditahan" yang memperlihatkan berat, sehingga angka gagal terbaca
//      tanpa akibatnya.
//
// Yang TIDAK diuji ulang: lima angka eksklusif, putusan satu kalimat, dan
// larangan bar komposisi — semuanya keputusan 29 Okt yang masih berlaku
// (lima angka yang menjumlah ke total tidak perlu dikodekan ulang sebagai bar).
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import FoodSafetyBoard from "../components/FoodSafetyBoard";

const NOW = new Date("2026-10-29T06:00:00Z");

const BATCHES = [
  {
    id: "b1",
    location: "Jakarta",
    commodity: "ayam",
    quantity_kg: 120,
    safety_status: "fail",
    freshness_score: 0.3,
    usable_until: "2026-10-29T12:00:00Z", // 6 jam lagi — tetapi gagal, jadi bukan kandidat
  },
  {
    id: "b2",
    location: "Jakarta",
    commodity: "telur",
    quantity_kg: 300,
    safety_status: "pass",
    freshness_score: 0.8,
    usable_until: "2026-11-03T06:00:00Z",
  },
  {
    id: "b3",
    location: "Jakarta",
    commodity: "beras",
    quantity_kg: 500,
    safety_status: "pass",
    freshness_score: 0.9,
    usable_until: null,
  },
  {
    id: "b4",
    location: "Jakarta",
    commodity: "wortel",
    quantity_kg: 40,
    safety_status: "pass",
    freshness_score: 0.7,
    usable_until: "2026-10-29T12:00:00Z", // 6 jam lagi — batch gagal di atas tidak dihitung
  },
];

function render(props: Partial<Parameters<typeof FoodSafetyBoard>[0]> = {}) {
  return renderToStaticMarkup(<FoodSafetyBoard batches={BATCHES} now={NOW} {...props} />);
}

function kartu(html: string, id: string): string {
  const mulai = html.indexOf(`id="${id}"`);
  expect(mulai, `kartu #${id} tidak dirender`).toBeGreaterThan(-1);
  return html.slice(mulai, html.indexOf("</article>", mulai));
}

describe("ringkasan — tenggat terdekat", () => {
  it("menyebut batch yang paling cepat kedaluwarsa, dengan jamnya", () => {
    const html = kartu(render(), "safety-ringkasan");
    expect(html).toContain("Paling mendesak");
    // ayam juga kedaluwarsa 6 jam lagi, tetapi gagal uji → bukan kandidat;
    // yang disebut harus batch yang masih boleh dipakai.
    expect(html).toContain("wortel");
    expect(html).toContain("Jakarta");
    expect(html).toContain("6 jam lagi");
  });

  it("tidak mengarang tenggat saat tidak ada tanggal layak", () => {
    const tanpaTanggal = BATCHES.map((batch) => ({ ...batch, usable_until: null }));
    const html = renderToStaticMarkup(
      <FoodSafetyBoard batches={tanpaTanggal} now={NOW} />
    );
    expect(kartu(html, "safety-ringkasan")).not.toContain("Paling mendesak");
  });

  it("tidak menautkan tenggat ke batch gagal — yang gagal sudah diblokir", () => {
    // Batch gagal tetap punya tanggal layak, tetapi tindakan yang benar untuknya
    // adalah "tinjau gagal", bukan "segera pakai"; baris tenggat harus bercerita
    // tentang batch yang masih BISA dipakai.
    const hanyaGagal = BATCHES.map((batch) => ({ ...batch, safety_status: "fail" }));
    const html = renderToStaticMarkup(<FoodSafetyBoard batches={hanyaGagal} now={NOW} />);
    expect(kartu(html, "safety-ringkasan")).not.toContain("Paling mendesak");
  });
});

describe("ringkasan — berat pada angka gagal", () => {
  it("menulis berat batch gagal di bawah angkanya", () => {
    const html = kartu(render(), "safety-ringkasan");
    // 120 kg dari satu batch gagal; angka ini sudah dipakai tooltip "Ditahan"
    // tetapi dulu tidak pernah muncul untuk "Gagal uji".
    expect(html).toContain("120 kg");
    expect(html).toContain("tidak boleh dialokasikan");
  });
});

describe("ringkasan — label tombol tinjau", () => {
  it("menyebut jumlah batch yang perlu tindakan saat tidak ada yang gagal", () => {
    const perluVerifikasi = [
      { ...BATCHES[1], safety_status: "needs_verification" },
      { ...BATCHES[2], safety_status: "needs_verification" },
    ];
    const html = renderToStaticMarkup(<FoodSafetyBoard batches={perluVerifikasi} now={NOW} />);
    const ringkasan = kartu(html, "safety-ringkasan");
    expect(ringkasan).toContain("Tinjau 2 batch perlu tindakan");
  });
});

describe("ringkasan — batch yang sudah lewat masa layak", () => {
  it("menyebut keadaannya apa adanya, bukan 'paling mendesak'", () => {
    // Data demo memuat batch yang tanggalnya sudah lewat sementara statusnya
    // masih lolos uji. Baris itu tetap yang paling perlu perhatian, tetapi
    // kalimat "paling mendesak" untuk barang yang sudah kedaluwarsa terbaca
    // seperti saran memakainya.
    const lewat = [
      { ...BATCHES[1], usable_until: "2026-10-20T06:00:00Z" }, // 9 hari lewat
      { ...BATCHES[2], usable_until: null },
    ];
    const html = renderToStaticMarkup(<FoodSafetyBoard batches={lewat} now={NOW} />);
    const ringkasan = kartu(html, "safety-ringkasan");
    expect(ringkasan).toContain("Sudah lewat");
    expect(ringkasan).not.toContain("Paling mendesak");
    expect(ringkasan).toContain("lewat 9 hari");
  });
});
