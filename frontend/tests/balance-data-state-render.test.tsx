// Kejujuran angka di halaman "Surplus & Limbah" (PLAN-023 · 2026-10-17).
//
// Tab ini hanya dibuka peran SPPG, dan di demo lokasi mereka (Jakarta) datanya
// lengkap — jadi keadaan "sisi tidak tercatat" tidak bisa dipamerkan dari data
// demo. Kontraknya dipaku di sini: lokasi yang salah satu sisinya belum
// tercatat TIDAK dihitung sebagai surplus, TIDAK dipakai sebagai pemasok
// rencana alokasi, dan jumlahnya DIKATAKAN di header (bukan dihilangkan).
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import SurplusBoard from "../components/SurplusBoard";

const LOKASI = [
  {
    location: "Bandung",
    region: "Jawa Barat",
    latitude: -6.9175,
    longitude: 107.6191,
    surplus_kg: 386.4,
    shortage_kg: 0,
    status: "surplus",
    supply_state: "terukur",
    demand_state: "tidak_ada_baris",
  },
  {
    location: "Bogor",
    region: "Jawa Barat",
    latitude: -6.595,
    longitude: 106.8166,
    surplus_kg: 535.9,
    shortage_kg: 0,
    status: "surplus",
    supply_state: "terukur",
    demand_state: "terukur",
  },
  {
    location: "Jakarta",
    region: "DKI Jakarta",
    latitude: -6.2088,
    longitude: 106.8456,
    surplus_kg: 0,
    shortage_kg: 765.8,
    status: "shortage",
    supply_state: "terukur",
    demand_state: "terukur",
  },
];

function render() {
  return renderToStaticMarkup(<SurplusBoard locations={LOKASI} commodity="telur" />);
}

describe("SurplusBoard — lokasi tanpa catatan lengkap", () => {
  it("hanya menghitung surplus dari permintaan yang terukur", () => {
    const html = render();
    expect(html).toContain("1 lokasi surplus");
    expect(html).toContain("1 lokasi tanpa catatan lengkap");
  });

  it("tidak memakai Bandung sebagai pemasok rencana alokasi", () => {
    const html = render();
    const bagianAlokasi = html.slice(html.indexOf("Rencana alokasi surplus"));
    expect(bagianAlokasi).toContain("Bogor");
    expect(bagianAlokasi).not.toContain("Bandung");
  });

  it("angka nol tetap ditulis `0 kg`, bukan pesan galat", () => {
    const html = render();
    expect(html).toContain("0 kg");
  });
});
