// Kontrak render kartu bar vertikal "Kecukupan pasokan" (28 Okt 2026).
// Fokus: bentuk kolom, arah pertumbuhan batang, penanda kebutuhan, keadaan
// kosong/muat-muat/galat, dan pemasangan di Overview (dua grafik lama dilepas
// dari Overview, tetap ada di repo).
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { readFileSync } from "node:fs";
import path from "node:path";

import AdequacyColumns from "../components/AdequacyColumns";
import { buildAdequacyRows } from "../lib/supply-adequacy";

const NOW = new Date("2026-10-20T12:00:00Z");
const AKAR = path.resolve(__dirname, "..");

function batch(commodity: string, kg: number, hari: number) {
  return {
    location: "Bandung",
    commodity,
    quantity_kg: kg,
    safety_status: "pass",
    quarantine_status: "none",
    usable_until: new Date(NOW.getTime() + hari * 86_400_000).toISOString(),
  };
}

const MAP = {
  telur: [
    {
      location: "Bandung",
      demand_kg: 1080,
      supply_kg: 700,
      demand_state: "terukur",
      status: "shortage",
    },
  ],
  beras: [
    {
      location: "Bandung",
      demand_kg: 500,
      supply_kg: 900,
      demand_state: "terukur",
      status: "surplus",
    },
  ],
  ayam: [
    {
      location: "Bandung",
      demand_kg: 300,
      supply_kg: 100,
      demand_state: "terukur",
      status: "shortage",
    },
  ],
  wortel: [],
};

function rows() {
  return buildAdequacyRows({
    commodities: ["telur", "beras", "ayam", "wortel"],
    byCommodity: MAP as never,
    batches: [batch("telur", 700, 6), batch("beras", 900, 6), batch("ayam", 100, 6)],
    location: "Bandung",
    now: NOW,
  });
}

const DASAR = {
  role: "sppg_head",
  locationName: "Bandung",
  updatedAt: NOW.getTime(),
  now: NOW,
};

function render(extra: Record<string, unknown> = {}) {
  return renderToStaticMarkup(
    <AdequacyColumns mode="commodity" rows={rows()} {...DASAR} {...extra} />
  );
}

/** Keliling lingkaran cincin (r=40 pada viewBox 100×100) — dasar dasharray. */
const KELILING_CINCIN = 2 * Math.PI * 40;

/** Panjang busur ke-n sebagai persen keliling: bukti busur = angka cakupan. */
function busurPct(html: string, ke = 1): number {
  const semua = [...html.matchAll(/class="rc-arc"[^>]*stroke-dasharray="([\d.]+) /g)].map((m) =>
    Number(m[1])
  );
  const nilai = semua[ke - 1];
  if (nilai === undefined) throw new Error(`busur ke-${ke} tidak ada (total ${semua.length})`);
  return (nilai / KELILING_CINCIN) * 100;
}

describe("AdequacyColumns — mode komoditas", () => {
  it("menggambar satu donat berisi 4 komoditas, dengan total di tengah", () => {
    const html = render();
    // Satu diagram; wortel (tanpa kebutuhan) tidak jadi irisan tapi tetap
    // punya baris legenda, jadi 3 busur + 4 baris.
    expect(html.match(/class="cd-arc /g)).toHaveLength(3);
    expect(html.match(/class="cd-row /g)).toHaveLength(4);
    expect(html).toContain("Kecukupan pasokan");
    expect(html).toContain("Bandung");
    expect(html).toContain("cd-total-angka");
    // Angka cakupan per komoditas tetap tercetak di legenda.
    expect(html).toContain("65%");
  });

  it("besar irisan = kg yang dihitung; tiap komoditas punya warna sendiri", () => {
    const html = render();
    const busur = [...html.matchAll(/class="cd-arc [^"]*"[^>]*stroke-dasharray="([\d.]+) /g)].map((m) =>
      Number(m[1])
    );
    expect(busur).toHaveLength(3);
    expect(busur.every((b) => b > 0)).toBe(true);
    // Irisan terbesar (beras 900 kg) jauh lebih besar dari yang terkecil (ayam).
    expect(Math.max(...busur)).toBeGreaterThan(Math.min(...busur) * 2);
    // Warna = identitas komoditas, bukan warna status.
    expect(html).toContain("sr-komod-blue");
    expect(html).toContain("sr-komod-amber");
    expect(html).not.toContain("ac-seg");
  });

  it("komoditas tanpa kebutuhan tetap punya baris legenda bernada 'belum tercatat'", () => {
    const html = render();
    // wortel tidak punya kebutuhan: tidak digambar sebagai irisan 0%, tetapi
    // namanya tidak boleh hilang dari legenda.
    expect(html).toMatch(/cd-name">wortel</);
    expect(html).toContain("belum tercatat");
    // Kalimat lengkapnya tetap dibawa pembaca layar.
    expect(html).toMatch(/wortel:[^"]*belum tercatat/);
  });

  it("kolom bisa diklik untuk menampilkan komoditas di peta", () => {
    const html = render({ onSelect: () => {} });
    expect(html).toContain("<button");
    expect(html).toContain("Tampilkan di peta");
  });

  it("tanpa onSelect tetap dirender sebagai grup statis (bukan tombol mati)", () => {
    const html = render();
    expect(html).not.toContain("Tampilkan di peta");
    expect(html).toContain('role="img"');
  });

  it("pil lensa tampil dengan pilihan awal sesuai peran", () => {
    const html = render({ role: "sppg_nutritionist" });
    expect(html).toContain("Kuantitas");
    expect(html).toContain("Kesegaran");
    expect(html).toMatch(/aria-pressed="true"[^>]*>Kesegaran|Kesegaran<\/button>/);
  });

  it("keadaan muat-muat: aria-busy + kolom hantu, bukan kartu kosong", () => {
    const html = render({ loading: true });
    expect(html).toContain('aria-busy="true"');
    expect(html).toContain("ac-skeleton");
  });

  it("keadaan galat: pesan + tombol coba lagi", () => {
    const html = render({ error: "Peta pasokan gagal dimuat.", onRetry: () => {} });
    expect(html).toContain("Peta pasokan gagal dimuat.");
    expect(html).toContain("Coba lagi");
  });
});

describe("AdequacyColumns — mode lokasi", () => {
  const LOKASI = [
    {
      location: "Bandung",
      region: "Jawa Barat",
      demand_kg: 1000,
      supply_kg: 400,
      demand_state: "terukur",
      supply_state: "terukur",
      status: "shortage",
    },
    {
      location: "Cianjur",
      region: "Jawa Barat",
      demand_kg: 400,
      supply_kg: 800,
      demand_state: "terukur",
      supply_state: "terukur",
      status: "surplus",
    },
  ];

  it("judul dan sumbu berganti, cincin memakai nada cakupan", () => {
    const html = renderToStaticMarkup(
      <AdequacyColumns
        mode="location"
        locations={LOKASI}
        commodity="telur"
        {...DASAR}
      />
    );
    expect(html).toContain("Pasokan per Lokasi");
    expect(html).toContain("telur");
    // Cincin mode lokasi memakai satu warna status per lokasi, bukan segmen.
    expect(html).toContain("rc-item ac-tone-danger");
    expect(html).toContain("rc-item ac-tone-safe");
  });

  it("tanpa lokasi: pesan jelas, bukan bidang kosong", () => {
    const html = renderToStaticMarkup(
      <AdequacyColumns mode="location" locations={[]} commodity="telur" {...DASAR} />
    );
    expect(html).toContain("Belum ada lokasi");
  });
});

describe("kartu sederhana (permintaan pemilik: simple, tidak banyak teks)", () => {
  /** Teks yang benar-benar tercetak — atribut (title/aria) dibuang. */
  function teksTercetak(html: string): string {
    return html
      .replace(/<[^>]*>/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  it("tidak ada paragraf penjelasan panjang di kartu", () => {
    const teks = teksTercetak(render());
    // Judul, sub satu baris, "2/4 kurang", legenda 5 kata, empat angka, empat
    // nama, empat selisih, satu baris petunjuk.
    expect(teks.length).toBeLessThan(320);
    expect(teks).not.toContain("Tinggi batang =");
    expect(teks).not.toContain("garis dalam batang");
    // Dasar kartu boleh punya baris keterangan (legenda garis acuan), tetapi
    // hanya itu: satu baris pendek, tanpa paragraf.
    const foot = (html: string) => {
      const awal = html.indexOf('class="ac-foot"');
      return awal < 0 ? null : html.slice(awal, html.indexOf("</div>", awal));
    };
    // Bentuk donat tidak punya kaki bergaris acuan; keterangannya satu baris
    // caption di bawah diagram.
    const caption = (html: string) => {
      const awal = html.indexOf('class="cd-caption"');
      return awal < 0 ? null : html.slice(awal, html.indexOf("</p>", awal));
    };
    void foot;
    const kaki = caption(render());
    expect(kaki).not.toBeNull();
    expect(kaki!).toContain("irisan = kg yang dihitung");
    expect(kaki!).toContain("warna = komoditas");
    expect(kaki!).not.toContain("<p");
  });

  it("rincian panjang tetap ada untuk pembaca layar & tooltip", () => {
    const html = render();
    // Kalimat lengkap tiap komoditas dibawa aria donat (bukan aria-label per
    // kolom lagi): kebutuhan dan selisih tetap disebut.
    expect(html).toMatch(/ayam: stok layak[^"]*kebutuhan/);
    // Sub menyimpan keterangan lengkap di title.
    expect(html).toMatch(/title="Bandung · 4 komoditas ·[^"]*dihitung/);
  });

  it("kepala kartu komoditas tanpa baris lokasi/jam", () => {
    const html = render();
    // Permintaan pemilik 28 Okt 2026: baris kecil "Bandung · 22.00" di bawah
    // judul dihapus — lokasi & jam sudah ada di bar atas halaman.
    expect(html).not.toContain('class="ac-sub"');
    // Keterangan lengkap tetap ada sebagai tooltip judul.
    expect(html).toMatch(/<h3 id="ac-title" title="Bandung · 4 komoditas/);
  });

  it("ringkasan cukup satu pasangan angka + kata", () => {
    const html = render();
    expect(html).toContain("ac-count");
    // 29 Okt 2026: "2/3 kurang" diganti "2 dari 3 kurang" — pecahan miring
    // terbaca sebagai tanggal/rasio oleh pembaca non-teknis.
    expect(html).toContain("<strong>2 dari 3</strong> kurang");
  });
});

describe("CSS kartu bar vertikal", () => {
  const css = readFileSync(path.join(AKAR, "app/adequacy-columns.css"), "utf8");

  it("plot tumbuh mendatar, batang tumbuh ke atas dari dasar kotak", () => {
    expect(css).toMatch(/\.ac-plot\s*\{[^}]*repeat\(var\(--ac-kolom/);
    expect(css).toMatch(/\.ac-fill\s*\{[^}]*position:\s*absolute/);
    expect(css).toMatch(/\.ac-fill\s*\{[^}]*bottom:\s*0/);
    // Satu warna status, bukan tumpukan segmen.
    expect(css).not.toContain(".ac-seg");
  });

  it("tinggi plot dipatok supaya kartu tidak membengkak", () => {
    expect(css).toMatch(/\.ac-track\s*\{[^}]*height:\s*168px/);
  });

  it("tanpa gradasi: semua isian warna solid (permintaan pemilik 28 Okt 2026)", () => {
    expect(css).not.toMatch(/gradient/);
    // Panel surplus memakai bahasa yang sama: warna solid, kedalaman dari bayangan.
    const sr = readFileSync(path.join(AKAR, "app/surplus-regions.css"), "utf8");
    expect(sr).not.toMatch(/gradient/);
  });

  it("memakai bahasa soft UI: kartu membulat, bayangan lembut, tanpa garis keras", () => {
    expect(css).toMatch(/\.adequacy-columns\s*\{[^}]*border-radius:\s*var\(--radius-dock\)/);
    expect(css).toMatch(/\.adequacy-columns\s*\{[^}]*box-shadow:\s*var\(--shadow-2\)/);
    expect(css).not.toMatch(/border-bottom:\s*1px solid var\(--line-strong\)/);
  });
});

describe("geometri plot kolom (redesign 29 Okt 2026)", () => {
  const css = readFileSync(path.join(AKAR, "app/adequacy-columns.css"), "utf8");

  it("satu bidang plot: track transparan, bukan empat kotak terbenam", () => {
    const track = css.match(/\.ac-track\s*\{([^}]*)\}/);
    expect(track, "blok .ac-track hilang").not.toBeNull();
    // Latar transparan — kotak terbenam membuat plot terbaca sebagai kolom formulir.
    expect(track![1]).toMatch(/background:\s*transparent/);
    expect(track![1]).not.toContain("--surface-sunken");
    expect(track![1]).not.toContain("shadow-inset");
  });

  it("garis acuan di puncak track + sumbu di dasarnya", () => {
    // Garis putus-putus = 100% (kebutuhan / wilayah terbesar).
    expect(css).toMatch(/\.ac-track\s*\{[^}]*border-top:\s*1\.5px dashed/);
    expect(css).toMatch(/\.ac-track\s*\{[^}]*border-bottom:\s*1px solid/);
    // Kolom tanpa jarak supaya garis acuan & sumbu menyambung satu garis.
    expect(css).toMatch(/\.ac-plot\s*\{[^}]*gap:\s*0/);
  });

  it("pita angka dipatok supaya garis acuan semua kolom satu ketinggian", () => {
    expect(css).toMatch(/\.ac-value\s*\{[^}]*height:\s*28px/);
    expect(css).not.toMatch(/\.ac-value\s*\{[^}]*min-height/);
  });

  it("batang memakai satu warna solid per status tanpa celah kotak", () => {
    const fill = css.match(/\.ac-fill\s*\{([^}]*)\}/);
    expect(fill![1]).toMatch(/left:\s*20%/);
    expect(fill![1]).toMatch(/right:\s*20%/);
    // Sudut atas membulat lewat token (gerbang radius menolak nilai mentah).
    expect(fill![1]).toMatch(/border-radius:\s*var\(--radius-chip\)/);
  });

  it("teks selisih memakai tinta status (AA), batang memakai warna terpisah", () => {
    // Satu variabel untuk dua peran adalah bug aksesibilitas: campuran batang
    // 88% hanya 3–4:1, sedangkan teks 12 px wajib >= 4,5:1.
    expect(css).toMatch(/\.ac-gap\s*\{[^}]*color:\s*var\(--ac-ink/);
    for (const tone of ["safe", "warning", "danger", "muted"]) {
      const blok = css.match(new RegExp(`\\.ac-tone-${tone}\\s*\\{([^}]*)\\}`));
      expect(blok, `blok .ac-tone-${tone} hilang`).not.toBeNull();
      expect(blok![1]).toContain("--ac-bar");
      expect(blok![1]).toContain("--ac-ink");
    }
  });

  it("pasokan melebihi kebutuhan ditandai caret di atas garis acuan", () => {
    expect(css).toMatch(/\.ac-col\.is-over \.ac-fill::after/);
    expect(css).toMatch(/\.ac-track\s*\{[^}]*overflow:\s*visible/);
  });

  it("kolom dibatasi lebarnya: satu kolom tidak boleh selebar kartu", () => {
    expect(css).toMatch(/\.ac-plot\s*\{[^}]*repeat\(var\(--ac-kolom[^)]*\),\s*minmax\(0,\s*140px\)\)/);
    expect(css).toMatch(/\.ac-plot\s*\{[^}]*justify-content:\s*center/);
  });
});

describe("Pemasangan di Overview", () => {
  const page = readFileSync(path.join(AKAR, "app/page.tsx"), "utf8");

  it("kartu kecukupan memakai AdequacyColumns (bar vertikal)", () => {
    expect(page).toContain("<AdequacyColumns");
    expect(page).toContain('mode={pakaiGrafikKecukupan ? "commodity" : "location"}');
  });

  it("dua grafik bentuk lama tidak lagi dipasang di Overview (file tetap ada)", () => {
    expect(page).not.toContain("<SupplyAdequacyChart");
    expect(page).not.toContain("<SupplyBalanceChart");
  });
});
