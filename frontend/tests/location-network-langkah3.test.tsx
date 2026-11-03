// Langkah 3 rencana `docs/plans/location-network-page-plan.md` — copy & keadaan.
//
// Yang dijaga di sini adalah hal yang tidak terlihat di tangkapan layar:
//   * satu halaman hanya punya SATU baris filter dan SATU pil tanggal;
//   * kalimat kepala tidak boleh lebih panjang dari 120 karakter (paragraf
//     penjelas di dalam kartu sudah dua kali dikeluhkan pemilik);
//   * selama memuat / saat gagal / saat kosong, halaman tidak mencetak angka
//     yang terbaca sebagai hasil pengukuran ("0 lokasi", "Belum ada lokasi"
//     ganda), dan tabel kosong diganti kerangka tiga baris;
//   * istilah dan kaki keterangan tidak mengulang rumus di baris baca.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import AllocationTable from "../components/AllocationTable";
import LocationNetworkBoard from "../components/LocationNetworkBoard";
import type { BalanceMapLocation } from "../lib/overview-format";

const JAM = 3_600_000;
const SEKARANG = Date.now();

function lokasi(over: Partial<BalanceMapLocation> & { location: string }): BalanceMapLocation {
  return {
    region: "DKI Jakarta",
    latitude: -6.2,
    longitude: 106.8,
    supply_kg: 2150,
    demand_kg: 2930,
    status: "shortage",
    shortage_kg: 780,
    surplus_kg: 0,
    supply_state: "terukur",
    demand_state: "terukur",
    supply_recorded_at: new Date(SEKARANG - JAM).toISOString(),
    demand_recorded_at: new Date(SEKARANG - JAM).toISOString(),
    ...over,
  } as BalanceMapLocation;
}

const JAKARTA = lokasi({ location: "Jakarta" });
const CIANJUR = lokasi({
  location: "Cianjur",
  region: "Jawa Barat",
  latitude: -6.82,
  longitude: 107.14,
  status: "surplus",
  supply_kg: 2292,
  demand_kg: 900,
  shortage_kg: 0,
  surplus_kg: 1392,
});
const MEDAN = lokasi({
  location: "Medan",
  region: "Sumatera Utara",
  status: "balanced",
  supply_kg: 300,
  demand_kg: 300,
  shortage_kg: 0,
  surplus_kg: 0,
});

const RENCANA = {
  available: true,
  min_surplus_kg: 150,
  pairs: [{ from: "Cianjur", to: "Jakarta", kg: 685, distance_km: 76, cost_share_pct: 0.8 }],
};

function renderBoard(over: Partial<Parameters<typeof LocationNetworkBoard>[0]> = {}) {
  return renderToStaticMarkup(
    <LocationNetworkBoard
      locations={[JAKARTA, CIANJUR, MEDAN]}
      commodity="telur"
      selected={null}
      onSelect={() => {}}
      detail={null}
      {...over}
    />
  );
}

/** Isi teks tiap <p> — dipakai memeriksa panjang kalimat. */
function paragraf(html: string): string[] {
  return Array.from(html.matchAll(/<p[^>]*>([\s\S]*?)<\/p>/g), (match) =>
    match[1].replace(/<[^>]+>/g, "").trim()
  );
}

describe("Langkah 3 — satu kepala, satu filter, kalimat pendek", () => {
  it("hanya satu baris filter komoditas dan satu pil tanggal", () => {
    const html = renderBoard({
      snapshot: "Data per 28 Okt 2026",
      commodities: ["telur", "ayam", "beras"],
      onCommodityChange: () => {},
    });
    expect((html.match(/aria-label="Komoditas"/g) ?? []).length).toBe(1);
    expect((html.match(/Data per 28 Okt 2026/g) ?? []).length).toBe(1);
  });

  it("tidak ada paragraf penjelas lebih dari 120 karakter", () => {
    const html = renderBoard({ snapshot: "Data per 28 Okt 2026", plan: RENCANA });
    for (const teks of paragraf(html)) {
      expect(teks.length, `paragraf terlalu panjang: ${teks}`).toBeLessThanOrEqual(120);
    }
  });

  it("kalimat kepala memakai istilah yang sama dengan tabel, tanpa kata proses", () => {
    const html = renderBoard();
    expect(html).toContain(
      "Siapa kekurangan, siapa kelebihan, apa yang dialihkan, dan apa yang terbuang."
    );
    expect(html).not.toContain("isi catatan tiap lokasi");
    expect(html).not.toContain("dihitung server");
  });
});

describe("Langkah 3 — keadaan memuat, kosong, gagal", () => {
  it("memuat: kerangka tiga baris, tanpa pil jumlah, tanpa kesimpulan", () => {
    const html = renderBoard({ locations: [], loading: true });
    expect(html).toContain("Memuat saldo lokasi");
    expect((html.match(/class="skeleton skeleton-line"/g) ?? []).length).toBeGreaterThanOrEqual(3);
    expect(html).not.toMatch(/\d+ lokasi</);
    expect(html).not.toContain("Belum ada lokasi");
    expect(html).not.toContain("Tidak ada lokasi");
  });

  it("kosong: satu kalimat saja, tabelnya tidak dirender", () => {
    const html = renderBoard({ locations: [] });
    expect((html.match(/Belum ada lokasi/g) ?? []).length).toBe(1);
    expect(html).not.toContain('data-testid="location-network-table"');
    expect(html).not.toContain("Tidak ada lokasi kekurangan");
  });

  it("gagal total: satu kartu galat, tanpa angka apa pun", () => {
    const html = renderBoard({ locations: [], error: "jaringan terputus", onRetry: () => {} });
    expect(html).toContain("Tidak bisa memuat saldo lokasi");
    expect(html).toContain("Coba lagi");
    expect(html).not.toMatch(/\d+ lokasi</);
    expect(html).not.toContain("Keadaan jaringan");
    expect(html).not.toContain("Rencana alih");
    expect(html).not.toContain("Limbah");
  });

  it("gagal sebagian: blok yang gagal menyebut sebabnya satu baris di kartunya", () => {
    const html = renderBoard({
      planError: "rencana tidak terjawab",
      wasteError: "limbah tidak terjawab",
    });
    expect(html).toContain("Rencana alih tidak bisa dimuat: rencana tidak terjawab");
    expect(html).toContain("Limbah tidak bisa dimuat: limbah tidak terjawab");
    // Blok yang berhasil tetap tampil — kegagalan satu blok tidak mengosongkan halaman.
    expect(html).toContain('data-testid="location-network-table"');
  });

  it("cakupan satu lokasi: catatan kaki, bukan paragraf di kepala", () => {
    expect(renderBoard({ locations: [JAKARTA] })).toContain(
      "Akun ini hanya mencakup satu lokasi."
    );
    expect(renderBoard()).not.toContain("Akun ini hanya mencakup satu lokasi.");
  });

  it("rencana kosong menyebut alasan dari server, bukan 'kosong'", () => {
    const html = renderBoard({ plan: { available: false, reason: "surplus_di_bawah_ambang" } });
    expect(html).toContain("Tidak ada lokasi dengan surplus 150 kg atau lebih");
  });
});

describe("Langkah 3 — kelengkapan & kaki keterangan", () => {
  it("catatan basi menyebut jumlahnya", () => {
    const html = renderBoard({
      locations: [
        lokasi({
          location: "Jakarta",
          supply_recorded_at: new Date(SEKARANG - 30 * JAM).toISOString(),
          demand_recorded_at: new Date(SEKARANG - JAM).toISOString(),
        }),
      ],
    });
    expect(html).toContain("1 catatan lebih dari 24 jam");
    expect(html).not.toContain("catatan > 24 jam");
  });

  it("rencana alih: tabel bersih, rumus biaya di tooltip judul kolom", () => {
    const html = renderToStaticMarkup(<AllocationTable plan={RENCANA} />);
    // L5: kalimat ambang pindah ke kepala kartu; yang diuji di sini cuma
    // kebersihan badan tabel.
    expect(html).not.toContain("Hanya surplus ≥");
    expect(html).not.toContain("Biaya = angkut");
    expect(html).toContain('title="Angkut + penanganan ÷ nilai barang"');
  });

  it("blok limbah menyebut jendelanya sekali, sebagai pil di kepala", () => {
    const html = renderBoard({ wasteDays: 30 });
    expect(html).toContain("<h2>Limbah</h2>");
    expect(html).toContain(">30 hari</span>");
    expect(html).not.toContain("Limbah · ");
  });
});

describe("Langkah 3 — layar sempit (390 px, terukur di browser)", () => {
  it("kepala kolom Wilayah ikut disembunyikan bersama selnya", () => {
    const html = renderBoard();
    // Kalau hanya <td> yang disembunyikan (media query ≤640 px), judul "Wilayah"
    // tetap tampil dan SELURUH angka bergeser satu kolom ke kiri — terukur pada
    // 390 px di Edge headless: "kurang 780 kg" duduk di bawah judul "Wilayah".
    expect(html).toMatch(/<th scope="col" class="[^"]*region[^"]*">Wilayah<\/th>/);
  });

  it("tabel lokasi membawa petunjuk geser yang mengukur dirinya sendiri", () => {
    const html = renderBoard();
    expect(html).toContain("board-scroll-hint");
    expect(html).toContain("Geser tabel ke samping");
  });
});
