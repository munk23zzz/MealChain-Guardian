// Kontrak markup halaman "Surplus & Limbah" (halaman sidebar acuan /surplus).
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import SurplusBoard from "../components/SurplusBoard";

const LOCATIONS = [
  { location: "Cianjur", region: "Jawa Barat", latitude: -6.8168, longitude: 107.1425, surplus_kg: 1400, shortage_kg: 0, status: "surplus" },
  { location: "Jakarta", region: "DKI Jakarta", latitude: -6.2088, longitude: 106.8456, surplus_kg: 0, shortage_kg: 780, status: "shortage" },
];

function render(props: Partial<Parameters<typeof SurplusBoard>[0]> = {}) {
  return renderToStaticMarkup(<SurplusBoard locations={LOCATIONS} commodity="telur" {...props} />);
}

describe("SurplusBoard", () => {
  it("judul, neraca, dan rencana alokasi tampil", () => {
    const html = render();
    expect(html).toContain("Surplus &amp; Limbah");
    expect(html).toContain("Neraca hari ini");
    expect(html).toContain("1.400 kg");
    expect(html).toContain("780 kg");
    expect(html).toContain("Rencana alokasi surplus");
  });

  it("pasangan alokasi ditulis dari → tujuan beserta jarak", () => {
    const html = render();
    expect(html).toContain("Cianjur");
    expect(html).toContain("Jakarta");
    expect(html).toMatch(/km</);
  });

  it("bagian limbah jujur: '—' dengan alasan, bukan 0 kg", () => {
    const html = render();
    expect(html).toContain("Pencatatan limbah");
    expect(html).toContain("belum dicatat");
    expect(html).not.toContain(">0 kg<");
  });

  it("tanpa surplus: halaman menjelaskan keadaannya", () => {
    const html = render({ locations: [{ location: "Jakarta", shortage_kg: 10, status: "shortage" }] });
    expect(html).toContain("Tidak ada pasangan surplus→kekurangan");
  });

  it("tombol peta hanya muncul kalau pemanggil menyediakan penanganannya", () => {
    expect(render()).not.toContain("Lihat di peta");
    expect(render({ onOpenLocation: () => {} })).toContain("Lihat di peta");
  });

  it("tidak ada catatan internal (path API) di layar", () => {
    const html = render();
    expect(html).not.toContain("/balance/map");
    expect(html).not.toContain("/surplus/allocations");
    expect(html).not.toContain("Catatan sumber");
  });

  // Regresi 20 Okt 2026: peta peran SPPG hanya memuat lokasinya sendiri, jadi
  // rencana yang dirakit dari peta selalu kosong. Baris dari server harus tetap
  // tampil walau `locations` cuma berisi satu kota yang kekurangan.
  it("rencana dari server tampil walau peta hanya memuat satu lokasi", () => {
    const html = render({
      locations: [
        { location: "Bandung", region: "Jawa Barat", surplus_kg: 0, shortage_kg: 138, status: "shortage" },
      ],
      plan: {
        available: true,
        reason: null,
        pairs: [
          { from: "Cianjur", to: "Bandung", kg: 138, distance_km: 90, region: "Jawa Barat" },
        ],
      },
    });
    expect(html).toContain("Cianjur");
    expect(html).toContain("138 kg");
    expect(html).not.toContain("Tidak ada pasangan");
  });

  it("rencana kosong menyebut sebab dari server", () => {
    const html = render({
      locations: [{ location: "Bandung", shortage_kg: 138, status: "shortage" }],
      plan: { available: false, reason: "tidak_ada_surplus_terukur", pairs: [] },
    });
    expect(html).toContain("Tidak ada lokasi bersurplus terukur");
  });

  it("lencana surplus memakai angka jaringan, bukan peta yang terbatas", () => {
    const html = render({
      locations: [{ location: "Bandung", surplus_kg: 0, shortage_kg: 138, status: "shortage" }],
      plan: {
        available: true,
        surplus_locations: 3,
        shortage_locations: 7,
        pairs: [
          { from: "Cianjur", to: "Bandung", kg: 138, distance_km: 90, region: "Jawa Barat", cost_share_pct: 4.4 },
        ],
      },
    });
    expect(html).toContain("3 lokasi surplus jaringan");
    expect(html).toContain("4,4%");
  });
});
