// Kontrak markup halaman "Keamanan Pangan" (halaman sidebar acuan /compliance).
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import FoodSafetyBoard from "../components/FoodSafetyBoard";

const NOW = new Date("2026-10-11T06:00:00Z");
const BATCHES = [
  { id: "b1", location: "Cianjur", commodity: "telur", quantity_kg: 400, safety_status: "pass", freshness_score: 0.69, usable_until: "2026-10-11T18:00:00Z" },
  { id: "b2", location: "Surabaya", commodity: "ayam", quantity_kg: 120, safety_status: "fail", freshness_score: null, usable_until: null },
];

function render(props: Partial<Parameters<typeof FoodSafetyBoard>[0]> = {}) {
  return renderToStaticMarkup(
    <FoodSafetyBoard batches={BATCHES} now={NOW} {...props} />
  );
}

describe("FoodSafetyBoard", () => {
  it("judul + ringkasan pengawasan tampil dengan angka dari batch", () => {
    const html = render();
    expect(html).toContain("Keamanan Pangan");
    expect(html).toContain("Ringkasan pengawasan");
    expect(html).toContain("Batch diperiksa");
    expect(html).toContain("Gagal uji");
    expect(html).toContain("120 kg");
  });

  it("batch gagal dinyatakan terang-terangan beserta lokasinya", () => {
    const html = render();
    expect(html).toContain("Batch gagal uji: Surabaya");
    expect(html).toContain("tidak boleh dialokasikan");
  });

  it("tabel per batch memuat status, kesegaran, dan sisa masa", () => {
    const html = render();
    expect(html).toContain("Status keamanan per batch");
    expect(html).toContain("Aman");
    expect(html).toContain("69%");
    expect(html).toContain("12 jam lagi");
    expect(html).toContain("—"); // batch tanpa skor/tanggal
  });

  it("nilai kosong tidak diganti angka nol", () => {
    const html = render({
      batches: [{ id: "x", location: "Bogor", commodity: "telur", quantity_kg: 10, safety_status: null }],
    });
    expect(html).toContain("0"); // hitungan aman 0 memang benar
    expect(html).not.toMatch(/>0 kg</);
    expect(html).toContain("—");
  });

  it("galat pemuatan dijelaskan, bukan halaman kosong", () => {
    const html = render({ batches: null, error: "batches 500" });
    expect(html).toContain("Tidak bisa memuat batch");
    expect(html).toContain("batches 500");
  });

  it("tidak ada catatan internal (path API / nama kolom) di layar", () => {
    const html = render();
    expect(html).not.toContain("Catatan sumber");
    expect(html).not.toContain("/batches");
    expect(html).not.toContain("usable_until");
  });
});

// ── Fase 11 — cakupan kepala SPPG (permintaan pemilik: "data harus akurat,
//    fitur harus jalan dengan backend") ───────────────────────────────────────
describe("FoodSafetyBoard — cakupan lokasi sendiri", () => {
  const JAKARTA = [
    {
      id: "j1",
      location: "Jakarta",
      commodity: "telur",
      quantity_kg: 800,
      safety_status: "pass",
      freshness_score: 0.9,
      usable_until: "2026-11-07T12:00:00Z",
    },
  ];
  const ROUTES = {
    routes: [
      {
        id: "r1",
        batch_id: null,
        supplier_id: "s1",
        supplier_name: "Supplier A Cianjur",
        origin: { latitude: -6.854, longitude: 107.1306, name: "Supplier A Cianjur" },
        destination_id: "loc-jkt",
        destination_name: "Jakarta",
        destination: { latitude: -6.2088, longitude: 106.8456, name: "Jakarta" },
        commodity: "telur",
        quantity_kg: 800,
        usable_until: "2026-11-07T12:00:00+00:00",
        safety_status: "pass",
        straight_km: 78.35,
        road: {
          distance_km: 110.4,
          duration_min: 84.3,
          ratio_vs_straight: 1.41,
          geometry: { type: "LineString", coordinates: [[107.13, -6.85], [106.84, -6.2]] },
          source: "osrm",
          fetched_at: null,
        },
      },
    ],
  };
  const BALANCE = {
    commodity: "telur",
    locations: [
      { location: "Jakarta", region: "DKI Jakarta", supply_kg: 300, demand_kg: 1080, surplus_kg: 0, shortage_kg: 780 },
    ],
  };
  const DECISIONS = [
    {
      decision_id: "d1",
      decision_type: "safety_disruption",
      status: "proposed",
      quantity_kg: 492,
      valid: false,
      seconds_remaining: 0,
      created_at: "2026-10-16T09:27:02Z",
    },
    { decision_id: "d2", decision_type: "regional_balance", status: "proposed", quantity_kg: 600, valid: false },
    {
      decision_id: "d3",
      decision_type: "safety_disruption",
      status: "rejected",
      quantity_kg: 80,
      valid: false,
      created_at: "2026-10-15T09:00:00Z",
    },
  ];

  function renderOwn(props: Partial<Parameters<typeof FoodSafetyBoard>[0]> = {}) {
    return renderToStaticMarkup(
      <FoodSafetyBoard
        batches={JAKARTA}
        now={NOW}
        ownLocation="Jakarta"
        routes={ROUTES}
        balance={BALANCE}
        decisions={DECISIONS}
        {...props}
      />
    );
  }

  it("kartu Pasokan masuk menyebut pemasok, jalur jalan, dan kekurangan dari server", () => {
    const html = renderOwn();
    expect(html).toContain("Pasokan masuk menuju Jakarta");
    expect(html).toContain("Supplier A Cianjur");
    expect(html).toContain("110,4 km");
    // Kartu kiriman menyebut waktu tempuh dengan `durationLabel` (jam+menit),
    // bukan "84 menit" — angka server 84,3 menit yang sama, dibaca lebih enak.
    expect(html).toContain("1 jam 24 menit");
    expect(html).toContain("1,41× jarak lurus");
    expect(html).toContain("Kebutuhan 1.080 kg");
    expect(html).toContain("menutup kekurangan (+20 kg)");
  });

  it("kartu Pasokan masuk memakai stepper tahap perjalanan (bukan daftar angka saja)", () => {
    const html = renderOwn();
    expect(html).toContain("shipment-steps");
    expect(html).toContain("Dipanen");
    expect(html).toContain("Rincian kiriman");
    // Jalur belum dilaporkan server → kartu menyebut sebabnya, bukan mengarang.
    expect(html).toContain("Perjalanan belum dilaporkan server");
  });

  it("kolom tabel jadi Asal (pemasok) saat ber-scope lokasi sendiri", () => {
    const html = renderOwn();
    expect(html).toContain("Asal");
    expect(html).toContain("Supplier A Cianjur");
  });

  it("batch kedaluwarsa ditandai keadaan, bukan hanya 'kesegaran 0%'", () => {
    const html = renderToStaticMarkup(
      <FoodSafetyBoard
        batches={[
          {
            id: "e1",
            location: "Jakarta",
            commodity: "telur",
            quantity_kg: 250,
            safety_status: "pass",
            freshness_score: 0,
            usable_until: "2026-09-10T12:00:00Z",
          },
        ]}
        now={NOW}
        ownLocation="Jakarta"
      />
    );
    expect(html).toContain("Kedaluwarsa");
    expect(html).toContain("lewat");
  });

  it("keputusan keamanan: hanya jenis keamanan, dan dikatakan kalau tidak ada yang berlaku", () => {
    const html = renderOwn();
    expect(html).toContain("Keputusan keamanan lokasi ini");
    expect(html).toContain("2 keputusan keamanan");
    expect(html).toContain("1 ditolak (bisa diajukan ulang)");
    expect(html).toContain("menurut aturan server hanya keputusan yang");
    expect(html).toContain("Gangguan keamanan");
    expect(html).toContain("492 kg");
  });

  it("tombol Ajukan ulang hanya untuk keputusan yang DITOLAK (kontrak /actions/repropose)", () => {
    const html = renderOwn({ canMutate: true, onRepropose: async () => "x" });
    // hanya satu dari dua baris yang boleh punya tombol: yang ditolak
    expect(html.match(/Ajukan ulang/g) ?? []).toHaveLength(1);
  });

  it("tombol tindakan hanya muncul untuk peran yang boleh menulis", () => {
    expect(renderOwn({ canMutate: true, onRecheck: async () => null as never })).toContain("Uji ulang");
    expect(renderOwn({ canMutate: false })).not.toContain("Uji ulang");
    expect(renderOwn({ canMutate: true, onRepropose: async () => "x" })).toContain("Ajukan ulang");
  });

  it("tanpa cakupan lokasi (pengawas nasional) kolom Lokasi tetap dipakai", () => {
    const html = renderToStaticMarkup(<FoodSafetyBoard batches={JAKARTA} now={NOW} />);
    expect(html).toContain("Lokasi");
    expect(html).not.toContain("Pasokan masuk");
    expect(html).not.toContain("Penerimaan barang");
  });

  it("kartu Penerimaan barang: lima titik periksa + kalimat kemajuan", () => {
    const html = renderOwn({ canMutate: true, onRecheck: async () => null as never });
    expect(html).toContain("Penerimaan barang");
    expect(html).toContain("daftar periksa petugas");
    expect(html).toContain("0 dari 5 titik periksa sudah ditandai");
    expect(html).toContain("Catat hasil terima");
    expect(html).toContain("Nomor lot");
  });

  it("opsi Lainnya: petugas bisa menulis keadaan di luar daftar, bukan titik periksa ke-6", () => {
    const html = renderOwn({
      canMutate: true,
      onRecheck: async () => null as never,
      onRecordReceipt: async () => ({}) as never,
      loadReceipts: async () => ({ items: [] }),
    });
    expect(html).toContain("Lainnya — tuliskan keadaan yang tidak ada di daftar");
    expect(html).toContain("<textarea");
    // Contoh keadaan nyata, supaya petugas tahu apa yang boleh ditulis.
    expect(html).toContain("karung lapis kedua basah");
    // Hitungan titik periksa TIDAK ikut bertambah oleh opsi ini.
    expect(html).toContain("0 dari 5 titik periksa sudah ditandai");
    // Kartu menyatakan terang-terangan apa yang disimpan.
    expect(html).toContain("menyimpan DUA hal ke database");
  });

  it("tanpa jalur simpan, kartu tidak menjanjikan catatan tersimpan", () => {
    const html = renderOwn({ canMutate: true, onRecheck: async () => null as never });
    expect(html).toContain("<textarea");
    expect(html).toContain("Catatan ini tersimpan ke database");
  });

  it("tanpa izin menulis, kartu penerimaan menyatakan batasnya (bukan tombol mati)", () => {
    const html = renderOwn({ canMutate: false });
    expect(html).toContain("Hanya kepala SPPG dan ahli gizi");
    expect(html).not.toContain("Catat hasil terima");
  });

  it("tombol Ajukan keputusan hanya untuk baris GAGAL UJI (dan hanya Kepala SPPG)", () => {
    const ajukan = (batch: Record<string, unknown>, canPropose = true) =>
      renderToStaticMarkup(
        <FoodSafetyBoard
          batches={[batch]}
          now={NOW}
          ownLocation="Jakarta"
          canMutate
          canPropose={canPropose}
          onTriggerDisruption={async () => ({ status: "disruption", decision_id: "d1" })}
        />
      );
    const gagal = ajukan({
      id: "f1",
      location: "Jakarta",
      commodity: "ayam",
      quantity_kg: 100,
      safety_status: "fail",
      freshness_score: 0.5,
      usable_until: "2026-10-20T12:00:00Z",
    });
    expect(gagal).toContain("Ajukan keputusan");
    // Ahli gizi (canMutate true, canPropose false) tidak melihat tombol usul.
    expect(
      ajukan(
        {
          id: "f2",
          location: "Jakarta",
          commodity: "ayam",
          quantity_kg: 100,
          safety_status: "fail",
          freshness_score: 0.5,
          usable_until: "2026-10-20T12:00:00Z",
        },
        false
      )
    ).not.toContain("Ajukan keputusan");
    const aman = ajukan({
      id: "a1",
      location: "Jakarta",
      commodity: "telur",
      quantity_kg: 100,
      safety_status: "pass",
      freshness_score: 0.9,
      usable_until: "2026-10-20T12:00:00Z",
    });
    expect(aman).not.toContain("Ajukan keputusan");
  });
});
