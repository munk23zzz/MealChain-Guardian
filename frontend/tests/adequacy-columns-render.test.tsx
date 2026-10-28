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

describe("AdequacyColumns — mode komoditas", () => {
  it("menggambar 4 kolom, satu per komoditas, dengan angka cakupan di atas", () => {
    const html = render();
    expect(html.match(/class="ac-col /g)).toHaveLength(4);
    expect(html).toContain("Kecukupan pasokan");
    expect(html).toContain("Bandung");
    expect(html).toContain("ac-value");
    // Angka cakupan ditulis apa adanya dari modul murni.
    expect(html).toContain("65%");
  });

  it("batang tumbuh dari bawah, tingginya = cakupan, tanpa segmen kualitas", () => {
    const html = render();
    // telur 700/1.080 = 64,8% — angka ini yang dipakai sebagai tinggi isi.
    expect(html).toMatch(/class="ac-fill ac-tone-[a-z]+" style="height:6[45][\d.]*%"/);
    // Beras 900/500 = 180% → mentok 100%, ditandai "is-over".
    expect(html).toMatch(/class="ac-fill ac-tone-[a-z]+" style="height:100%"/);
    expect(html).toContain("is-over");
    // Satu arti per batang: tidak ada lagi segmen kualitas di dalam batang.
    expect(html).not.toContain("ac-seg");
  });

  it("kebutuhan = kotak penuh, tanpa garis acuan tambahan di dalamnya", () => {
    const html = render();
    // Satu kotak per kolom; garis putus-putus di puncak sudah dihapus supaya
    // tidak ada dua acuan yang harus ditafsirkan.
    expect(html.match(/class="ac-track/g)).toHaveLength(4);
    expect(html).not.toContain("ac-ref");
    expect(html).not.toContain("ac-demand");
  });

  it("kekurangan = sisa kotak yang kosong, tanpa lapisan tambahan", () => {
    const html = render();
    // Tidak ada jalur/lapisan pucat: ruang kosong di dalam kotak itu sendiri
    // yang berarti kekurangan. Ini yang dulu membingungkan.
    expect(html).not.toContain("ac-miss");
    expect(html).not.toContain("ac-cover");
    // telur 64,8% → batang berhenti di 64,8%, sisanya kosong.
    expect(html).toMatch(/style="height:6[45][\d.]*%"/);
  });

  it("kolom tanpa kebutuhan tidak digambar sebagai 0% dan tetap diberi nama", () => {
    const html = render();
    expect(html).toContain("ac-track-empty");
    expect(html).toMatch(/ac-name">wortel</);
    // "belum tercatat", bukan "0 kg layak" — stok 0 yang jujur beda dari tak ada data.
    // Sejak redesign "simple" catatan kg tidak dicetak; teksnya hidup di aria-label.
    expect(html).toMatch(/aria-label="wortel:[^"]*belum tercatat/);
    expect(html).toMatch(/aria-label="wortel:[^"]*—/);
  });

  it("kolom bisa diklik untuk menampilkan komoditas di peta", () => {
    const html = render({ onSelect: () => {} });
    expect(html).toContain("<button");
    expect(html).toContain("Tampilkan di peta");
  });

  it("tanpa onSelect tetap dirender sebagai grup statis (bukan tombol mati)", () => {
    const html = render();
    expect(html).not.toContain("Tampilkan di peta");
    expect(html).toContain('role="group"');
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

  it("judul dan sumbu berganti, batang memakai nada cakupan", () => {
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
    // Batang mode lokasi memakai satu warna status, bukan segmen.
    expect(html).toContain("ac-fill ac-tone-danger");
    expect(html).toContain("ac-fill ac-tone-safe");
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
    expect(render()).not.toContain("ac-foot");
  });

  it("rincian panjang tetap ada untuk pembaca layar & tooltip", () => {
    const html = render();
    // aria-label tiap kolom tetap menyebut kebutuhan dan selisih.
    expect(html).toMatch(/aria-label="ayam: stok layak[^"]*kebutuhan/);
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
    expect(css).toMatch(/\.ac-plot\s*\{[^}]*grid-auto-flow:\s*column/);
    expect(css).toMatch(/\.ac-fill\s*\{[^}]*position:\s*absolute/);
    expect(css).toMatch(/\.ac-fill\s*\{[^}]*bottom:\s*0/);
    // Satu warna status, bukan tumpukan segmen.
    expect(css).not.toContain(".ac-seg");
  });

  it("tinggi plot dipatok supaya kartu tidak membengkak", () => {
    expect(css).toMatch(/\.ac-track\s*\{[^}]*height:\s*144px/);
  });

  it("tanpa gradasi: semua isian warna solid (permintaan pemilik 28 Okt 2026)", () => {
    expect(css).not.toMatch(/gradient/);
    // Panel surplus memakai bahasa yang sama: warna solid, kedalaman dari bayangan.
    const sr = readFileSync(path.join(AKAR, "app/surplus-regions.css"), "utf8");
    expect(sr).not.toMatch(/gradient/);
    // Segmen komoditas panel mewarisi gradasi dari `.sa-seg`; di sini dinetralkan.
    expect(sr).toMatch(/\.sr-seg\s*\{[^}]*background-image:\s*none/);
  });

  it("memakai bahasa soft UI: kartu membulat, bayangan lembut, tanpa garis keras", () => {
    expect(css).toMatch(/\.adequacy-columns\s*\{[^}]*border-radius:\s*var\(--radius-dock\)/);
    expect(css).toMatch(/\.adequacy-columns\s*\{[^}]*box-shadow:\s*var\(--shadow-2\)/);
    expect(css).not.toMatch(/border-bottom:\s*1px solid var\(--line-strong\)/);
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
