// Kontrak markup halaman "Pemasok" (halaman sidebar acuan /suppliers).
//
// Fase 3 (2026-10-14): prop `pairs` (sampel keputusan) diganti `suppliers`
// (payload GET /suppliers). Yang diuji di sini adalah KEHORMATAN tampilan:
// angka tidak dikarang, keadaan "belum dimuat" tidak disamarkan sebagai
// "tidak ada data", dan enum internal tidak bocor ke layar.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import SupplierBoard from "../components/SupplierBoard";
import type { SupplierContext } from "../lib/supplier-exclusions";

const SUPPLIERS = {
  count: 3,
  total: 3,
  items: [
    {
      id: "s1",
      name: "Wortel Lestari Cianjur",
      location: "Cianjur",
      commodity: "wortel",
      certification_status: "haccp",
      reliability_score: 0.93,
      latitude: -6.824,
      longitude: 107.1636,
      excluded_at_hub: false,
      excluded_scope_locations: [],
    },
    {
      id: "s2",
      name: "Telur Berkah Cianjur",
      location: "Cianjur",
      commodity: "telur",
      certification_status: "none",
      reliability_score: 0.38,
      latitude: -6.811,
      longitude: 107.1636,
      excluded_at_hub: true,
      excluded_scope_locations: ["Cianjur", "Jakarta"],
    },
    {
      id: "s3",
      name: "Supplier A Cianjur",
      location: "Cianjur",
      commodity: null,
      certification_status: null,
      reliability_score: 0.8,
      latitude: -6.854,
      longitude: 107.1306,
      excluded_at_hub: false,
      excluded_scope_locations: [],
    },
  ],
};

const CONTEXT = {
  suppliers: [
    {
      id: "s1",
      name: "Wortel Lestari Cianjur",
      batch_ids: ["b1"],
      evidence_refs: [{ type: "batch", id: "b1" }],
      batches: [{ id: "b1", safety_status: "pass" }],
    },
  ],
  scope_location_id: "loc-1",
  can_propose: false,
  reason_unavailable: null,
  exclusions: [],
} as unknown as SupplierContext;

function render(props: Record<string, unknown> = {}) {
  return renderToStaticMarkup(
    <SupplierBoard
      suppliers={SUPPLIERS}
      exclusions={{ items: [], count: 0 }}
      selectedDecisionId={null}
      supplierContext={null}
      role="bgn_monitor"
      token="t"
      {...props}
    />
  );
}

describe("SupplierBoard", () => {
  it("judul + ringkasan pemasok dari daftar (bukan sampel keputusan)", () => {
    const html = render();
    expect(html).toContain("Pemasok");
    expect(html).toContain("Pemasok terdaftar");
    expect(html).toContain("Rata-rata keandalan");
    expect(html).toContain("70%"); // (0,93 + 0,38 + 0,80) / 3
    expect(html).toContain("Keandalan rendah (&lt; 60%)");
    expect(html).toContain("Punya titik peta");
    expect(html).toContain("3 dari 3");
    // Tidak ada lagi kolom turunan sampel keputusan.
    expect(html).not.toContain("Keputusan terpindai");
  });

  it("tabel memuat hub, komoditas, sertifikat, koordinat, dan status eksklusi", () => {
    const html = render();
    expect(html).toContain("Daftar pemasok");
    expect(html).toContain("Wortel Lestari Cianjur");
    expect(html).toContain("Cianjur");
    expect(html).toContain("HACCP");
    expect(html).toContain("-6,8240 / 107,1636");
    expect(html).toContain("Aktif");
    expect(html).toContain("Dikecualikan di Cianjur, Jakarta");
    expect(html).toContain("Tidak bersertifikat");
  });

  it("nilai yang tidak ada ditulis '—', bukan 0", () => {
    const html = render();
    expect(html).toContain(">—<");
    // Pemasok kanonik tanpa fokus komoditas.
    expect(html).toContain("Supplier A Cianjur");
    expect(html).not.toContain(">0%<");
  });

  it("daftar belum dimuat: tidak mengklaim 'tidak ada pemasok'", () => {
    const html = render({ suppliers: null });
    expect(html).not.toContain("Tidak ada pemasok yang terdaftar");
    expect(html).toContain("belum dimuat");
  });

  it("daftar dimuat dan kosong: klaim 'tidak ada pemasok' sah", () => {
    const html = render({ suppliers: { items: [], count: 0 } });
    expect(html).toContain("Tidak ada pemasok yang terdaftar");
  });

  it("galat muat: pesan manusia + tombol coba lagi, tanpa bocor path API", () => {
    const html = render({ error: "HTTP 500: /suppliers", onRetry: () => {} });
    expect(html).toContain("Tidak bisa memuat data pemasok");
    expect(html).toContain("Coba lagi");
    expect(html).not.toContain("HTTP 500");
    expect(html).not.toContain("/suppliers");
  });

  it("register eksklusi kosong dijelaskan apa adanya", () => {
    const html = render();
    expect(html).toContain("Register eksklusi");
    expect(html).toContain("Tidak ada pemasok yang sedang dieksklusi");
  });

  it("register eksklusi terisi ditampilkan dengan alasan + kode keputusan", () => {
    const html = render({
      exclusions: {
        items: [
          { id: "e1", supplier_name: "Supplier C Jakarta", reason: "dua kiriman suhu menyimpang", excluded_at: "2026-10-11T02:00:00Z", decision_id: "d9d9d9d9-1111" },
        ],
      },
    });
    expect(html).toContain("Supplier C Jakarta");
    expect(html).toContain("dua kiriman suhu menyimpang");
    expect(html).toContain("d9d9d9d9");
  });

  it("register belum dimuat (exclusions null): TIDAK mengklaim tidak ada eksklusi", () => {
    const html = render({ exclusions: null });
    expect(html).not.toContain("Tidak ada pemasok yang sedang dieksklusi");
    expect(html).toContain("belum dimuat");
  });

  it("tanpa keputusan terpilih: form eksklusi diganti penjelasan", () => {
    const html = render();
    expect(html).toContain("Usul eksklusi");
    expect(html).toContain("Pilih keputusan lebih dulu");
  });

  it("dengan konteks keputusan: panel eksklusi nyata dipasang", () => {
    const html = render({ selectedDecisionId: "d1", supplierContext: CONTEXT, role: "sppg_head" });
    expect(html).toContain("Supplier governance");
  });

  it("tidak ada catatan internal (path API) di layar", () => {
    const html = render();
    expect(html).not.toContain("endpoint");
    expect(html).not.toContain("/supplier-exclusions");
    expect(html).not.toContain("/suppliers");
    expect(html).not.toContain("Dari mana angka ini");
  });
});

const JALUR = {
  routes: [
    {
      batch_id: "b-1",
      supplier_id: "s3",
      supplier_name: "Supplier A Cianjur",
      origin: { latitude: -6.854, longitude: 107.1306, name: "Supplier A Cianjur" },
      destination_id: "l-1",
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
        geometry: {
          type: "LineString",
          coordinates: [
            [107.1306, -6.854],
            [106.8456, -6.2088],
          ],
        },
        source: "osrm",
        fetched_at: "2026-10-16T00:00:00+00:00",
      },
      road_missing_reason: null,
    },
  ],
};

describe("SupplierBoard — kolom \"Jalur kirim\" (lanjutan Fase 10)", () => {
  it("header kolom ada; jalur belum dimuat ditulis \u2026, bukan klaim 'tidak punya jalur'", () => {
    const html = render();
    expect(html).toContain("Jalur kirim");
    expect(html).toContain("\u2026");
    // Ringkasan jalur hanya muncul kalau datanya memang dimuat.
    expect(html).not.toContain("Jalur kiriman (jalan)");
  });

  it("pemasok yang mengirim ditulis tujuan + jarak JALAN, baris lain '\u2014'", () => {
    const html = render({ supplierRoutes: JALUR });
    expect(html).toContain("\u2192 Jakarta \u00b7 110,4 km");
    expect(html).toContain('title="Jakarta 110,4 km (jarak jalan dari OSRM)"');
    expect(html).toContain("\u2014");
    expect(html).toContain("Jalur kiriman (jalan)");
    expect(html).toContain("1 dari 1");
  });

  it("jarak LURUS tidak diduplikasi di kolom jalur (itu urusan kolom Jarak)", () => {
    const html = render({ supplierRoutes: JALUR });
    expect(html).not.toContain("78,35");
  });
});

// Fase 12c (16 Okt 2026) — permintaan pemilik: "anda susun supaya tampilannya
// rapih dan enak di lihat user dan pastikan shape teks harus enak di lihat juga
// tidak kebesaran maupun ke kecilan". Ukuran SEBELUM ada di komentar CSS.
describe("SupplierBoard — kerapian tabel & bentuk pil (Fase 12c)", () => {
  const SHIP = {
    items: [
      {
        id: "s1",
        name: "Wortel Lestari Cianjur",
        location: "Cianjur",
        commodity: "wortel",
        certification_status: "haccp",
        reliability_score: 0.93,
        latitude: -6.824,
        longitude: 107.1636,
        excluded_at_hub: false,
        excluded_scope_locations: [],
        shipping: {
          count: 3,
          total_kg: 1400,
          until: "2026-11-02T12:00:00+00:00",
          commodities: ["wortel"],
          safety_fail_count: 0,
        },
      },
      {
        id: "s2",
        name: "Ayam Segar Subang",
        location: "Subang",
        commodity: "ayam",
        certification_status: null,
        reliability_score: 0.55,
        latitude: -6.57,
        longitude: 107.76,
        excluded_at_hub: false,
        excluded_scope_locations: [],
        shipping: {
          count: 1,
          total_kg: 600,
          until: "2026-10-26T12:00:00+00:00",
          commodities: ["ayam"],
          safety_fail_count: 1,
        },
      },
    ],
  };

  it("kolom Hub & Koordinat dilebur jadi baris kedua sel Pemasok", () => {
    const html = render({ suppliers: SHIP });

    expect(html).not.toContain(">Hub<");
    expect(html).not.toContain(">Koordinat<");
    expect(html).toContain("Cianjur · -6,8240 / 107,1636");
    expect(html).toContain("cell-name");
    expect(html).toContain("cell-meta");
  });

  it("status kiriman jadi pil SATU baris; kalimat penuhnya pindah ke title", () => {
    const html = render({ suppliers: SHIP });

    expect(html).toContain(">Stok layak · 3 kiriman<");
    expect(html).toContain('title="Stok layak · 3 kiriman · 1.400 kg · s/d 2 Nov 2026"');
    // Kalimat panjang TIDAK lagi jadi isi pil — itulah yang membuat bentuknya
    // membungkus 3 baris dan jadi yang paling besar di barisnya.
    expect(html).not.toContain(">Stok layak · 3 kiriman · 1.400 kg · s/d 2 Nov 2026<");
  });

  it("kiriman gagal uji dapat pil bahaya sendiri, bukan ditempel di pil hijau", () => {
    const html = render({ suppliers: SHIP });

    expect(html).toContain("shipping-tag-fail");
    expect(html).toContain(">1 gagal uji<");
    expect(html).toContain("gagal uji keamanan");
  });

  it("pemasok tanpa kiriman tetap 'Aktif' (tanpa pil kosong)", () => {
    const html = render();
    expect(html).toContain("Aktif");
    expect(html).not.toContain("shipping-tag-fail");
  });

  it("berat + batas layak kiriman TERLIHAT di sel, bukan hanya lewat title", () => {
    const html = render({ suppliers: SHIP });

    // Bukti keterlihatan: atribut title dibuang lebih dulu, jadi yang tersisa hanya
    // teks yang benar-benar dirender di halaman.
    const tanpaTitle = html.replace(/title="[^"]*"/g, "");
    expect(tanpaTitle).toContain("1.400 kg · s/d 2 Nov 2026");
    expect(tanpaTitle).toContain("600 kg · s/d 26 Okt 2026");
    expect(html).toContain("shipping-meta");
    // Kalimat panjangnya tetap TIDAK kembali jadi isi pil (itu yang dulu membungkus 3 baris).
    expect(html).not.toContain(">Stok layak · 3 kiriman · 1.400 kg · s/d 2 Nov 2026<");
  });

  it("kartu ringkasan selebar halaman (kelas supplier-summary)", () => {
    const html = render();
    expect(html).toContain("supplier-summary");
    expect(html).not.toContain("board-grid board-grid-2");
  });
});
