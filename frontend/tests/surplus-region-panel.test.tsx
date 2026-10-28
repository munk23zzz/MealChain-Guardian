// Panel "Surplus wilayah lain" — kontrak tampilan (28 Okt 2026).
//
// Yang dipaku di sini (bukan selera visual):
// 1. Angka yang dibaca pengguna adalah angka SERVER, ditulis apa adanya.
// 2. Panel kosong TIDAK menulis "0 kg" — ia menulis sebabnya.
// 3. Tidak ada "NaN"/"undefined" yang lolos ke layar, termasuk saat payload
//    separuh jadi.
// 4. Setengah halaman: panel wajib memakai kartu grafik yang sama
//    (`supply-adequacy`), bukan chrome grafik kedua.
import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import SurplusRegionPanel from "../components/SurplusRegionPanel";

const PAYLOAD = {
  as_of: "2026-10-28T03:00:00+00:00",
  commodities: ["ayam", "beras", "telur", "wortel"],
  excluded_location: "Bandung",
  min_surplus_kg: 150,
  available: true,
  reason: null,
  totals: {
    surplus_kg: 3782.74,
    layak_kg: 3547.89,
    source_locations: 3,
    regions: 2,
    excluded_surplus_kg: 184.81,
    surplus_unmeasured_locations: 0,
  },
  regions: [
    {
      region: "Jawa Barat",
      surplus_kg: 3547.89,
      layak_kg: 3547.89,
      locations: 2,
      by_commodity: [
        { commodity: "beras", surplus_kg: 1572.41 },
        { commodity: "telur", surplus_kg: 1261.09 },
      ],
      sources: [
        { location: "Cianjur", surplus_kg: 2689.16, by_commodity: [] },
        { location: "Bogor", surplus_kg: 858.73, by_commodity: [] },
      ],
    },
    {
      region: "DKI Jakarta",
      surplus_kg: 215.4,
      layak_kg: 215.4,
      locations: 1,
      by_commodity: [{ commodity: "wortel", surplus_kg: 215.4 }],
      sources: [{ location: "Jakarta", surplus_kg: 215.4, by_commodity: [] }],
    },
  ],
};

function render(props: Partial<React.ComponentProps<typeof SurplusRegionPanel>>) {
  return renderToStaticMarkup(
    <SurplusRegionPanel
      payload={PAYLOAD}
      commodities={["ayam", "beras", "telur", "wortel"]}
      locationName="Bandung"
      sourceNote="Data per 8 Okt 2026"
      updatedAt={Date.parse("2026-10-28T03:00:00Z")}
      {...props}
    />
  );
}

describe("panel surplus wilayah lain", () => {
  it("memakai kartu grafik yang sama, bukan chrome kedua", () => {
    const html = render({});
    expect(html).toContain("supply-adequacy");
    expect(html).toContain("sa-rows");
    expect(html).toContain("sa-track-fill");
    expect(html).toContain("Surplus wilayah lain");
  });

  it("menulis total, wilayah, dan kg tiap wilayah apa adanya", () => {
    const html = render({});
    expect(html).toContain("3.782,74 kg"); // id-ID, dua desimal dari server
    expect(html).toContain("Jawa Barat");
    expect(html).toContain("DKI Jakarta");
    expect(html).toContain("3.547,89");
    expect(html).toContain("215,4 kg");
    expect(html).toContain("2 wilayah");
    expect(html).toContain("terbesar");
    expect(html).toContain("Cianjur, Bogor");
    expect(html).not.toMatch(/NaN|undefined|Infinity/);
  });

  it("menyebut lokasi sendiri yang dilewati server", () => {
    const html = render({});
    expect(html).toContain("di luar Bandung");
    expect(html).toContain("Surplus Bandung sendiri");
    expect(html).toContain("184,81 kg");
  });

  it("kosong = sebab, bukan 0 kg", () => {
    const html = render({
      payload: {
        available: false,
        reason: "surplus_hanya_di_lokasi_ini",
        commodities: ["telur"],
        regions: [],
        totals: { surplus_kg: 0, layak_kg: 0, source_locations: 0 },
      },
    });
    expect(html).toContain("Seluruh surplus komoditas ini ada di lokasi Anda sendiri");
    expect(html).not.toContain("0 kg");
    expect(html).toContain("—");
  });

  it("payload belum tiba / rusak tidak merender angka palsu", () => {
    const html = render({ payload: null });
    expect(html).not.toMatch(/NaN|undefined/);
    expect(html).toContain("—");
    expect(html).toContain("Belum ada surplus terukur di daerah lain");
  });

  it("memuat: aria-busy dan tanpa angka setengah jadi", () => {
    const html = render({ loading: true, payload: null });
    expect(html).toContain('aria-busy="true"');
    expect(html).toContain("memuat wilayah");
    expect(html).not.toContain("sa-rows");
  });

  it("galat: pesan server + tombol coba lagi", () => {
    const html = render({ error: "Surplus wilayah tidak tersedia.", onRetry: () => {} });
    expect(html).toContain("Surplus wilayah tidak tersedia.");
    expect(html).toContain("Coba lagi");
    expect(html).toContain('role="alert"');
  });

  it("komoditas hanya disebut lewat chip 'Asal', tanpa baris legenda terpisah", () => {
    const html = render({ commodities: ["beras", "telur"] });
    // 28 Okt 2026 (permintaan: "tampilan surplus lebih simple lagi"):
    // baris legenda komoditas dihapus — chip "Asal" sudah menyebut nama +
    // titik warnanya, jadi legenda hanya mengulang.
    expect(html).not.toContain("sr-legend");
    const chip = html.slice(html.indexOf("sr-mix"));
    expect(chip).toContain("beras");
    expect(chip).toContain("telur");
    expect(chip).not.toContain("wortel");
  });

  it("teks panel: satu baris sub, tanpa catatan kaki", () => {
    const html = render({});
    const tercetak = html.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ");
    // 29 Okt 2026: "dihitung server" adalah penjelasan mekanisme; kalimatnya
    // diganti bahasa pengguna yang tetap menyebut asal angkanya.
    expect(tercetak).toContain("dari data tercatat");
    expect(tercetak).not.toContain("dihitung server");
    // Jam tidak lagi dicetak di sub panel (28 Okt 2026).
    expect(tercetak).not.toMatch(/\d\d\.\d\d/);
    // Catatan kaki dihapus; kalimat panjangnya hidup di `title` kartu (hover).
    expect(html).not.toContain("sa-foot");
    expect(tercetak).not.toContain("peta akun SPPG hanya memuat lokasi sendiri");
    expect(html).toMatch(/title="Angka = pasokan tercatat[^"]*peta akun SPPG hanya memuat lokasi sendiri/);
  });

  it("BGN nasional (tanpa exclude): judul & keterangan ikut cakupan", () => {
    const html = render({
      payload: { ...PAYLOAD, excluded_location: null },
      locationName: "seluruh jaringan",
    });
    expect(html).toContain("Surplus per wilayah");
    expect(html).toContain("surplus seluruh jaringan");
    expect(html).not.toContain("Surplus wilayah lain");
    expect(html).toContain("seluruh jaringan · 4 komoditas");
  });

  it("surplus kecil tetap disebut, tetapi satu baris — bukan baris grafik", () => {
    const html = render({
      payload: {
        ...PAYLOAD,
        regions: [
          ...PAYLOAD.regions,
          {
            region: "Jawa Tengah",
            surplus_kg: 10.06,
            layak_kg: 0,
            locations: 1,
            by_commodity: [{ commodity: "telur", surplus_kg: 10.06 }],
            sources: [{ location: "Semarang", surplus_kg: 10.06, by_commodity: [] }],
          },
        ],
        totals: { ...PAYLOAD.totals, surplus_kg: 3792.8 },
      },
    });
    expect(html).toContain("Surplus kecil");
    expect(html).toContain("Jawa Tengah 10,06 kg");
    // Wilayah kecil TIDAK punya baris grafik sendiri (hanya 2 baris wilayah).
    expect(html.match(/sr-row-btn/g)?.length).toBe(2);
  });

  it("semua wilayah di bawah ambang: sebab ditulis, bukan daftar kosong", () => {
    const html = render({
      payload: {
        available: true,
        min_surplus_kg: 150,
        commodities: ["telur"],
        regions: [
          {
            region: "Bali",
            surplus_kg: 90,
            layak_kg: 0,
            locations: 1,
            by_commodity: [{ commodity: "telur", surplus_kg: 90 }],
            sources: [{ location: "Denpasar", surplus_kg: 90, by_commodity: [] }],
          },
        ],
        totals: { surplus_kg: 90, layak_kg: 0, source_locations: 1, regions: 1 },
      },
    });
    expect(html).toContain("di bawah ambang 150 kg");
    expect(html).toContain("Surplus kecil");
    expect(html).toContain("Bali 90 kg");
    expect(html).not.toContain("sr-row-btn");
  });
});

describe("tata letak setengah halaman", () => {
  const css = readFileSync(
    path.resolve(__dirname, "../app/surplus-regions.css"),
    "utf8"
  );

  it("dua kolom sama lebar, dengan lantai minmax(0, 1fr)", () => {
    const blok = css.match(/\.ov-pasokan-grid\s*\{([^}]*)\}/);
    expect(blok, "blok .ov-pasokan-grid hilang").not.toBeNull();
    expect(blok![1]).toMatch(
      /grid-template-columns:\s*minmax\(0,\s*1fr\)\s+minmax\(0,\s*1fr\)/
    );
    expect(blok![1]).toContain("align-items: start");
  });

  it("menumpuk satu kolom di layar sempit", () => {
    expect(css).toMatch(
      /@media \(max-width: 1180px\)[\s\S]*?\.ov-pasokan-grid\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)/
    );
  });

  it("kartu sempit memakai query kontainer: batang penuh di baris sendiri", () => {
    expect(css).toContain("container-type: inline-size");
    expect(css).toMatch(/@container \(max-width: 680px\)/);
    // Batang memakai SELURUH lebar baris kedua; kolomnya dilepas dari baris atas.
    expect(css).toContain('"track track track"');
    expect(css).toMatch(/"name nilai1 nilai2"/);
  });

  it("warna komoditas tidak memakai token status", () => {
    // Hijau/merah/kuning tetap berarti aman/bahaya di seluruh aplikasi.
    const segmen = css.slice(css.indexOf(".sr-komod-0"));
    expect(segmen).not.toContain("--status-safe");
    expect(segmen).not.toContain("--status-danger");
    expect(segmen).not.toContain("--status-warning");
  });
});
