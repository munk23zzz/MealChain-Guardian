// @vitest-environment jsdom
// Ringkasan pengawasan dipadatkan (30 Okt 2026).
//
// Sebelumnya tenggat terdekat, bukti suhu, dan "dari N batch + Rincian angka"
// berdiri sebagai TIGA blok bertumpuk, masing-masing dengan garis dan jaraknya
// sendiri. Kartu yang tugasnya menjawab "ada yang perlu saya tindak?" jadi lebih
// tinggi daripada tabel yang dirujuknya. Sekarang ketiganya satu baris ringkas.
//
// Yang dikunci di sini adalah SUSUNANNYA, bukan warna atau kelas CSS: kalau
// seseorang mengembalikan tiga blok terpisah, tes ini merah sebelum halamannya
// terlihat berantakan lagi.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import FoodSafetyBoard from "../components/FoodSafetyBoard";

const NOW = new Date("2026-10-29T01:00:00Z");

const bukti = {
  temperature_observation: "observed",
  evidence_state: "sufficient",
  source: "seed",
  source_label: "log simulasi",
  observed_at: "2026-10-29T00:30:00Z",
  sample_count: 6,
  evidence_sufficient: true,
};

const BATCHES = [
  {
    id: "b1",
    location: "Jakarta",
    commodity: "telur",
    quantity_kg: 100,
    safety_status: "pass",
    freshness_score: 0.9,
    // Sengaja dekat: memicu baris "Paling mendesak".
    usable_until: "2026-10-29T05:00:00Z",
    evidence: bukti,
  },
  {
    id: "b2",
    location: "Jakarta",
    commodity: "beras",
    quantity_kg: 300,
    safety_status: "pass",
    freshness_score: 0.8,
    usable_until: "2026-11-20T05:00:00Z",
    evidence: bukti,
  },
];

function render() {
  return renderToStaticMarkup(
    <FoodSafetyBoard batches={BATCHES} now={NOW} ownLocation="Jakarta" />
  );
}

function kartuRingkasan(html: string): string {
  const mulai = html.indexOf('id="safety-ringkasan"');
  expect(mulai, "kartu Ringkasan pengawasan tidak ditemukan").toBeGreaterThan(-1);
  return html.slice(mulai, html.indexOf('id="safety-perhatian"', mulai) > 0
    ? html.indexOf('id="safety-perhatian"', mulai)
    : undefined);
}

describe("Ringkasan pengawasan — dipadatkan", () => {
  it("tenggat, bukti suhu, dan jumlah batch berada dalam SATU wadah baris", () => {
    const doc = new DOMParser().parseFromString(render(), "text/html");
    const wadah = doc.querySelector('[class*="glance"]');
    expect(wadah, "wadah baris ringkas (.glance) tidak ada").toBeTruthy();
    // Ketiganya harus ANAK dari wadah itu — bukan tetangga di luar wadah.
    for (const kelas of [".safety-deadline", ".safety-temp", ".safety-counts-foot"]) {
      expect(wadah!.querySelector(kelas), `${kelas} tidak ada di dalam wadah`).toBeTruthy();
    }
    // Dan tidak ada salinan di luar wadah (blok lama tidak boleh hidup lagi).
    expect(doc.querySelectorAll(".safety-deadline")).toHaveLength(1);
    expect(doc.querySelectorAll(".safety-temp")).toHaveLength(1);
    expect(doc.querySelectorAll(".safety-counts-foot")).toHaveLength(1);
  });

  it("urutan baca: putusan → angka → fakta sekunder", () => {
    const html = kartuRingkasan(render());
    const putusan = html.indexOf("safety-verdict");
    const angka = html.indexOf('class="safety-counts"');
    const fakta = html.indexOf("glance");
    expect(putusan).toBeGreaterThan(-1);
    expect(putusan).toBeLessThan(angka);
    expect(angka).toBeLessThan(fakta);
  });

  it("tidak kehilangan isi: tenggat dan rincian angka tetap terbaca", () => {
    const html = kartuRingkasan(render());
    expect(html).toContain("Paling mendesak");
    expect(html).toContain("Bukti suhu");
    expect(html).toContain("Rincian angka");
  });
});
