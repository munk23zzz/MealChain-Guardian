// Panel "Surplus wilayah lain" — kontrak tampilan (28 Okt 2026; kolom 29 Okt 2026).
//
// Yang dipaku di sini (bukan selera visual):
// 1. Angka yang dibaca pengguna adalah angka SERVER, ditulis apa adanya.
// 2. Panel kosong TIDAK menulis "0 kg" — ia menulis sebabnya.
// 3. Tidak ada "NaN"/"undefined" yang lolos ke layar, termasuk saat payload
//    separuh jadi.
// 4. Setengah halaman: panel memakai KARTU & PLOT YANG SAMA dengan grafik
//    kecukupan (`adequacy-columns` / `ac-*`), bukan chrome grafik kedua.
// 5. Kolom = wilayah. Wilayah di bawah ambang tetap punya kolom (pucat), bukan
//    dibuang ke satu kalimat yang menyembunyikan namanya.
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

function teksTercetak(html: string): string {
  return html.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
}

describe("panel surplus wilayah lain", () => {
  it("memakai kartu & donat yang sama dengan grafik kecukupan, bukan chrome kedua", () => {
    const html = render({});
    expect(html).toContain("adequacy-columns");
    expect(html).toContain("cd-arc");
    expect(html).toContain("cd-legend");
    expect(html).toContain("Surplus wilayah lain");
    // Geometri lama sudah tidak dipakai: satu bahasa grafik untuk dua kartu.
    expect(html).not.toContain("supply-adequacy");
    expect(html).not.toContain("sa-rows");
    expect(html).not.toContain("sr-row-btn");
    expect(html).not.toContain("rc-arc");
  });

  it("satu irisan per komoditas, satu warna per komoditas, angka server apa adanya", () => {
    const html = render({});
    // Total kartu (server, id-ID dua desimal) di tengah donat.
    expect(html).toContain("3.782,74 kg");
    expect(html).toMatch(/cd-total-angka/);
    // Komoditas penyumbang muncul sebagai baris legenda dengan kg masing-masing.
    expect(html).toMatch(/cd-name">beras</);
    expect(html).toMatch(/cd-name">telur</);
    expect(html).toContain("Jawa Barat");
    expect(html).toContain("DKI Jakarta");
    expect(html).toContain("2 wilayah");
    // Warna = identitas komoditas (beras biru, telur amber), bukan warna status.
    expect(html).toContain("sr-komod-blue");
    expect(html).toContain("sr-komod-amber");
    expect(html).not.toMatch(/NaN|undefined|Infinity/);
  });

  it("busur proporsional terhadap kg komoditas, bukan selebar kartu", () => {
    const html = render({});
    const busur = [...html.matchAll(/class="cd-arc [^"]*"[^>]*stroke-dasharray="([\d.]+) /g)].map((m) =>
      Number(m[1])
    );
    expect(busur.length).toBeGreaterThan(1);
    // Irisan terbesar > irisan terkecil, dan semuanya positif.
    expect(Math.max(...busur)).toBeGreaterThan(Math.min(...busur));
    expect(busur.every((b) => b > 0)).toBe(true);
    // Nama wilayah tetap disebut di baris kaki donat.
    expect(html).toContain("cd-wilayah");
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
    // Tanpa wilayah tidak ada plot kosong: sebabnya yang tampil.
    expect(html).not.toContain("ac-plot");
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
    // Kerangka memuat memakai kolom hantu yang sama dengan kartu kecukupan.
    expect(html).toContain("ac-skeleton");
    expect(html).not.toContain("ac-plot");
  });

  it("galat: pesan server + tombol coba lagi", () => {
    const html = render({ error: "Surplus wilayah tidak tersedia.", onRetry: () => {} });
    expect(html).toContain("Surplus wilayah tidak tersedia.");
    expect(html).toContain("Coba lagi");
    expect(html).toContain('role="alert"');
  });

  it("nama komoditas hanya muncul di legenda donat, sekali per komoditas", () => {
    const html = render({ commodities: ["beras", "telur"] });
    // Legenda donat menggantikan chip "Dari komoditas": satu daftar, satu baris
    // per komoditas penyumbang, tanpa pengulangan di baris lain.
    expect(html).not.toContain("sr-mix");
    expect(html).not.toContain("sr-legend");
    const nama = [...html.matchAll(/class="cd-name">([^<]+)</g)].map((m) => m[1].toLowerCase());
    expect(nama).toContain("beras");
    expect(nama).toContain("telur");
    // Tidak ada komoditas yang tercetak dua kali.
    expect(new Set(nama).size).toBe(nama.length);
  });

  it("satuan kg disebut sekali per baris legenda, bukan berulang di nama", () => {
    const html = render({});
    const awal = html.indexOf('class="cd-legend"');
    const legenda = html.slice(awal, html.indexOf("</ul>", awal));
    const baris = legenda.split("</li>").slice(0, -1);
    expect(baris.length).toBeGreaterThan(1);
    // Tiap baris: nama tanpa satuan, nilai di kolom kanan dengan satu "kg".
    for (const satu of baris) {
      const teks = teksTercetak(satu);
      expect((teks.match(/kg/g) ?? []).length).toBe(1);
      expect(teks).toMatch(/\d/);
    }
    expect(html).toContain("beras 1.572,41 kg");
  });

  it("teks panel: satu baris sub, tanpa catatan kaki", () => {
    const html = render({});
    const tercetak = teksTercetak(html);
    // 29 Okt 2026: "dihitung server" adalah penjelasan mekanisme; kalimatnya
    // diganti bahasa pengguna yang tetap menyebut asal angkanya.
    expect(tercetak).toContain("dari data tercatat");
    expect(tercetak).not.toContain("dihitung server");
    // Jam tidak dicetak di sub panel (28 Okt 2026).
    expect(tercetak).not.toMatch(/\d\d\.\d\d WIB/);
    // Catatan kaki dihapus; kalimat panjangnya hidup di `title` kartu (hover).
    expect(html).not.toContain("sa-foot");
    expect(html).not.toContain("peta akun SPPG");
    expect(html).toMatch(/title="Angka = pasokan tercatat[^\"]*dijumlahkan per wilayah \(peta hanya memuat lokasi sendiri\)/);
    expect(tercetak).not.toContain("oleh server");
  });

  it("kartu tetap ringkas: teks tercetak di bawah 300 karakter", () => {
    const tercetak = teksTercetak(render({}));
    expect(tercetak.length).toBeLessThan(300);
  });

  it("BGN nasional (tanpa exclude): judul & keterangan ikut cakupan", () => {
    const html = render({
      payload: { ...PAYLOAD, excluded_location: null },
      locationName: "seluruh jaringan",
    });
    expect(html).toContain("Surplus per wilayah");
    expect(html).toContain("seluruh jaringan");
    expect(html).not.toContain("Surplus wilayah lain");
    expect(html).toContain("seluruh jaringan · dari data tercatat");
  });

  it("wilayah di bawah ambang tetap jadi kolom pucat, bukan baris teks terpisah", () => {
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
        totals: { ...PAYLOAD.totals, surplus_kg: 3792.8, regions: 3 },
      },
    });
    // Tiga wilayah tetap disebut semuanya di baris kaki donat, termasuk yang
    // 10 kg — wilayah kecil tidak boleh hilang.
    expect(teksTercetak(html)).toContain("Jawa Tengah");
    expect(html).toContain("di bawah ambang");
    expect(html).not.toContain("sr-tail");
  });

  it("semua wilayah di bawah ambang: busur pucat + sebabnya tertulis", () => {
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
    expect(html).toContain("di bawah ambang");
    expect(html).toContain("cd-wilayah");
    // Angka wilayah tertulis di baris kaki, bukan "0 kg layak dialihkan".
    expect(teksTercetak(html)).toMatch(/90\s*kg/);
    expect(html).toContain("Bali");
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
    // Dua kartu satu baris: tepi bawah harus rata.
    expect(blok![1]).toContain("align-items: stretch");
  });

  it("menumpuk satu kolom di layar sempit", () => {
    expect(css).toMatch(
      /@media \(max-width: 1180px\)[\s\S]*?\.ov-pasokan-grid\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)/
    );
  });

  it("kartu sempit menurunkan ukuran angka (query kontainer), bukan mengganti bentuk", () => {
    expect(css).toContain("container-type: inline-size");
    expect(css).toMatch(/@container \(max-width: 520px\)[\s\S]*?ac-value strong/);
  });

  it("batang wilayah memakai aksen, bukan warna status", () => {
    // Hijau/merah/kuning tetap berarti aman/bahaya di seluruh aplikasi.
    const kolom = css.slice(css.indexOf(".sr-col {"));
    expect(kolom).toContain("--ac-bar: color-mix(in srgb, var(--accent)");
    expect(css).not.toContain("--status-safe");
    expect(css).not.toContain("--status-danger");
    expect(css).not.toContain("--status-warning");
  });

  it("tanpa gradasi (permintaan pemilik 28 Okt 2026)", () => {
    expect(css).not.toMatch(/gradient/);
  });
});
