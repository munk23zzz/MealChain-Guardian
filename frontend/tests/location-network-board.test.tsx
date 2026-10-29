// Kontrak markup halaman gabungan Location Network (dokumen 03 §3, §6.3, §6.5).
// Bentuk: satu kartu ringkasan + satu tabel yang barisnya membuka rincian di
// tempat. Tidak ada peta, tidak ada koridor, tidak ada jendela terpisah.
//
// Yang dijaga di sini bukan tata letak, melainkan hal yang mudah rusak tanpa
// terlihat: nama field mentah yang bocor ke layar, "0 kg" untuk data yang tidak
// ada, kesimpulan yang dicetak sebelum data datang, dan peta/popup yang
// diam-diam kembali.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import LocationNetworkBoard from "../components/LocationNetworkBoard";
import SupplyDemandPanel from "../components/SupplyDemandPanel";
import { buildSupplyDemandDetail } from "../lib/supply-demand";
import type { BalanceMapLocation } from "../lib/overview-format";

const LOCATIONS: BalanceMapLocation[] = [
  {
    location: "Jakarta",
    region: "DKI Jakarta",
    latitude: -6.2088,
    longitude: 106.8456,
    supply_kg: 2150,
    demand_kg: 2930,
    status: "shortage",
    shortage_kg: 780,
    surplus_kg: 0,
    supply_state: "terukur",
    demand_state: "terukur",
    supply_recorded_at: "2026-10-28T08:00:00Z",
    demand_recorded_at: "2026-10-27T02:00:00Z",
  } as BalanceMapLocation,
  {
    location: "Cianjur",
    region: "Jawa Barat",
    latitude: -6.8219,
    longitude: 107.1444,
    supply_kg: 2292,
    demand_kg: null,
    status: "surplus",
    shortage_kg: 0,
    surplus_kg: 2292,
    supply_state: "terukur",
    demand_state: "tidak_ada_baris",
    supply_recorded_at: "2026-10-28T09:30:00Z",
    demand_recorded_at: null,
  } as BalanceMapLocation,
  {
    location: "Medan",
    region: "Sumatera Utara",
    latitude: null,
    longitude: null,
    supply_kg: 300,
    demand_kg: 300,
    status: "balanced",
    shortage_kg: 0,
    surplus_kg: 0,
    supply_state: "terukur",
    demand_state: "terukur",
    supply_recorded_at: "2026-10-28T07:00:00Z",
    demand_recorded_at: "2026-10-28T07:00:00Z",
  } as BalanceMapLocation,
];

const DETAIL = buildSupplyDemandDetail({
  location: "Jakarta",
  commodity: "telur",
  balance: { shortage_kg: 780, surplus_kg: 0 },
  supply: { quantity_kg: 2150, recorded_at: "2026-10-28T08:00:00Z", source: "mock_sap" },
  demand: { quantity_kg: 2930, needed_by: "2026-10-31T00:00:00Z" },
  batches: [
    {
      id: "0746863c-f9bb-4038",
      location: "Jakarta",
      commodity: "telur",
      quantity_kg: 400,
      safety_status: "pass",
      usable_until: "2026-11-02T00:00:00Z",
    },
    {
      id: "d480a218-1111-2222",
      location: "Jakarta",
      commodity: "telur",
      quantity_kg: 600,
      safety_status: "pass",
      quarantine_status: "quarantined",
      usable_until: "2027-04-23T00:00:00Z",
    },
  ],
});

function renderBoard(over: Partial<Parameters<typeof LocationNetworkBoard>[0]> = {}) {
  return renderToStaticMarkup(
    <LocationNetworkBoard
      locations={LOCATIONS}
      commodity="telur"
      selected="Jakarta"
      onSelect={() => {}}
      detail={DETAIL}
      {...over}
    />
  );
}

const JAKARTA_SAJA = [LOCATIONS[0]];

describe("LocationNetworkBoard — halaman gabungan", () => {
  it("kalimat ringkasan membawa nada bahaya yang benar-benar terpasang", () => {
    const html = renderBoard({ locations: JAKARTA_SAJA });
    expect(html).toContain("1 lokasi kekurangan");
    // Nada lewat atribut: kelas global yang ditempel ke elemen ber-CSS-module
    // tidak pernah cocok, sehingga penekanan bahaya hilang tanpa error.
    expect(html).toMatch(/data-tone="danger"[\s\S]*?lokasi kekurangan/);
  });

  it("tidak memasang peta, koridor, atau jendela terpisah", () => {
    const html = renderBoard();
    expect(html).not.toContain("maplibregl");
    expect(html).not.toContain("map-shell");
    expect(html).not.toContain('aria-haspopup="dialog"');
    expect(html).not.toContain('role="dialog"');
  });

  it("lokasi tampil sebagai tabel urut dari yang terparah, bukan deretan chip", () => {
    const html = renderBoard();
    expect(html).toContain('data-testid="location-network-table"');
    // L3: tabel ini juga membawa kelas papan sendiri (`network-table`) untuk
    // mode kartu di layar sempit; kelas dasarnya tetap `location-table`.
    expect(html).toMatch(/class="location-table network-table"/);
    expect(html).toContain(">Wilayah<");
    expect(html.indexOf("Jakarta")).toBeLessThan(html.indexOf("Cianjur"));
    expect(html.indexOf("Cianjur")).toBeLessThan(html.indexOf("Medan"));
  });

  it("baris terpilih terbuka (aria-expanded) dan rinciannya ada di halaman yang sama", () => {
    const html = renderBoard();
    // L3: pola disclosure — `aria-expanded`, bukan `aria-pressed`.
    expect(html).toContain('aria-expanded="true"');
    expect(html).toContain('id="rincian-lokasi"');
    expect(html).toContain('data-testid="supply-demand-panel"');
    expect(html).toContain("2.150 kg");
    expect(html).toContain("kurang 780 kg");
    // Batch lokasi ini ikut di tabel yang sama — tidak di balik jendela.
    expect(html).toContain("0746863c");
  });

  it("baris lain tetap tertutup supaya hanya satu rincian tampil", () => {
    const html = renderBoard();
    expect((html.match(/aria-expanded="true"/g) ?? []).length).toBe(1);
    expect((html.match(/aria-expanded="false"/g) ?? []).length).toBe(LOCATIONS.length - 1);
  });

  it("tanpa pilihan, semua baris tertutup", () => {
    const html = renderBoard({ selected: null });
    expect(html).not.toContain('aria-expanded="true"');
    expect(html).not.toContain('id="rincian-lokasi"');
  });

  it("angka jaringan ditulis SEKALI, tidak diulang di baris angka", () => {
    const html = renderBoard({ locations: JAKARTA_SAJA });
    // Kalimat ringkasan sudah menyebut "1 lokasi kekurangan 780 kg"; tidak ada
    // baris kedua yang mengulang "1 kekurangan · 780 kg".
    expect(html).not.toContain('data-testid="location-network-stats"');
    expect((html.match(/kekurangan 780 kg/g) ?? []).length).toBe(1);
    expect(html).not.toMatch(/>0 kg</);
  });

  it("selama memuat tidak ada kesimpulan yang dicetak", () => {
    const html = renderBoard({ locations: [], loading: true });
    expect(html).toContain("Memuat saldo lokasi");
    expect(html).not.toContain("Tidak ada lokasi");
    expect(html).not.toContain("Belum ada lokasi");
  });

  it("saat gagal: pesan galat + tombol coba lagi, tanpa kesimpulan", () => {
    const html = renderBoard({ locations: [], error: "jaringan terputus", onRetry: () => {} });
    expect(html).toContain("Tidak bisa memuat saldo lokasi");
    expect(html).toContain("Coba lagi");
    expect(html).not.toContain("Tidak ada lokasi kekurangan");
    expect(html).not.toContain("Belum ada lokasi");
  });

  it("tanpa lokasi: menyebut data belum masuk, bukan 'tidak ada kekurangan'", () => {
    const html = renderBoard({ locations: [] });
    expect(html).toContain("Belum ada lokasi");
    expect(html).not.toContain("Tidak ada lokasi kekurangan");
  });

  it("kelengkapan hanya muncul bila ada yang perlu diketahui", () => {
    // Data bersih (catatan segar, semua ada): tidak ada kotak "semua aman" yang
    // hanya mengulang kalimat ringkasan.
    const segar = {
      ...LOCATIONS[0],
      supply_recorded_at: new Date().toISOString(),
      demand_recorded_at: new Date().toISOString(),
    } as BalanceMapLocation;
    expect(renderBoard({ locations: [segar] })).not.toContain(
      'data-testid="location-network-completeness"'
    );
    // Cianjur tanpa catatan permintaan + Jakarta punya catatan basi: baru muncul.
    const ada = renderBoard();
    expect(ada).toContain('data-testid="location-network-completeness"');
    expect(ada).toContain("1 tanpa catatan permintaan");
  });

  it("kolom catatan tidak dipasang bila semua baris lengkap", () => {
    expect(renderBoard({ locations: JAKARTA_SAJA })).not.toContain("tanpa permintaan");
    expect(renderBoard()).toContain("bertanda");
  });

  it("jumlah lokasi dan jam pengambilan tidak diulang di kepala halaman", () => {
    const html = renderBoard({ snapshot: "Data per 28 Okt 2026" });
    expect(html).toContain("Data per 28 Okt 2026");
    // Jumlah lokasi muncul sekali (pil kepala), jam pengambilan tidak ada sama sekali.
    expect((html.match(/3 lokasi/g) ?? []).length).toBe(1);
    expect(html).not.toContain("Sinkron");
  });

  it("komoditas bisa diganti dari halaman ini", () => {
    const html = renderToStaticMarkup(
      <LocationNetworkBoard
        locations={LOCATIONS}
        commodity="telur"
        commodities={["telur", "ayam", "beras"]}
        onCommodityChange={() => {}}
        selected={null}
        onSelect={() => {}}
        detail={null}
      />
    );
    expect(html).toContain('aria-pressed="true"');
    expect(html).toContain("ayam");
    expect(html).toContain("beras");
  });

  it("tidak membocorkan nama field mentah atau nilai kosong ke layar", () => {
    const html = renderBoard();
    for (const forbidden of [
      "shortage_kg",
      "demand_state",
      "supply_kg",
      "tidak_ada_baris",
      "null",
      "undefined",
      "NaN",
      "mock_sap",
    ]) {
      expect(html).not.toContain(forbidden);
    }
  });

  it("lokasi tanpa koordinat dan tanpa catatan ditandai di barisnya", () => {
    const html = renderBoard();
    expect(html).toContain("Cianjur");
    expect(html).toContain("tanpa catatan permintaan");
    expect(html).toContain("tanpa koordinat");
  });
});

describe("SupplyDemandPanel — §3–§4", () => {
  it("empat kartu: pasokan, kebutuhan, selisih, perkiraan", () => {
    const html = renderToStaticMarkup(<SupplyDemandPanel detail={DETAIL} commodity="telur" />);
    for (const label of ["Pasokan terakhir", "Kebutuhan", "Selisih", "Perkiraan"]) {
      expect(html).toContain(label);
    }
  });

  it("kebutuhan ditulis sebagai tanggal jatuh tempo, bukan jam mesin", () => {
    const html = renderToStaticMarkup(<SupplyDemandPanel detail={DETAIL} />);
    // Tanggal jatuh tempo di kartu kebutuhan; masa layak batch boleh punya angka jam.
    expect(html).toMatch(/<dt>Kebutuhan<\/dt><dd>[^<]*<\/dd><span>\d+ hari lagi · .*2026<\/span>/);
    expect(html).not.toMatch(/dibutuhkan \d+ hari \d+ jam lagi/);
  });

  it("sumber catatan tidak dicetak: yang perlu dibaca hanya umur catatan", () => {
    const html = renderToStaticMarkup(<SupplyDemandPanel detail={DETAIL} />);
    expect(html).not.toContain("mock_sap");
    expect(html).not.toContain("catatan simulasi");
  });

  it("batch yang ditahan ditandai dan tidak dihitung sebagai lolos uji", () => {
    const html = renderToStaticMarkup(<SupplyDemandPanel detail={DETAIL} />);
    expect(html).toContain("Ditahan");
    expect(html).toContain("1 ditahan");
    expect(html).toContain("1 lolos uji");
  });

  it("kata 'Aman' tidak diulang di kolom masa layak", () => {
    const html = renderToStaticMarkup(<SupplyDemandPanel detail={DETAIL} />);
    // Badge keamanan menulis "Aman"; kolom masa layak hanya durasi.
    expect((html.match(/>Aman</g) ?? []).length).toBeLessThanOrEqual(2);
    expect(html).toMatch(/\d+ hari lagi/);
  });

  it("404 ditulis 'tidak ada catatan', dan batch lokasi lain tidak ikut", () => {
    const detail = buildSupplyDemandDetail({
      location: "Jakarta",
      commodity: "telur",
      balance: { shortage_kg: 780 },
      supply: { quantity_kg: 2150, recorded_at: null, source: null },
      demand: null,
      batches: [
        {
          id: "a1",
          location: "Bandung",
          commodity: "telur",
          quantity_kg: 120,
          safety_status: "fail",
        },
      ],
      failed: { demand: "404 tidak ada catatan" },
    });
    const html = renderToStaticMarkup(<SupplyDemandPanel detail={detail} />);
    expect(html).toContain("Catatan permintaan tidak ada untuk lokasi ini.");
    expect(html).toContain("Tidak ada batch untuk lokasi dan komoditas ini.");
    expect(html).not.toContain("Bandung");
  });

  it("detail kosong tidak menampilkan angka karangan", () => {
    const kosong = buildSupplyDemandDetail({
      location: "Jakarta",
      commodity: "telur",
      balance: null,
      supply: null,
      demand: null,
      batches: [],
      failed: { balance: "404", supply: "404", demand: "404" },
    });
    const html = renderToStaticMarkup(<SupplyDemandPanel detail={kosong} />);
    expect(html).toContain("—");
    expect(html).not.toContain("0 kg");
  });

  it("kegagalan semua bagian dinyatakan, bukan deretan tanda hubung tanpa sebab", () => {
    const html = renderToStaticMarkup(
      <SupplyDemandPanel detail={null} error="pasokan tidak terjawab server" />
    );
    expect(html).toContain("Detail lokasi gagal dimuat");
  });
});
