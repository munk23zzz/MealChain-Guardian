// Tahap 6 redesign Keamanan Pangan (30 Okt 2026): daftar keputusan keamanan
// menjadi TABEL dengan pola kepala yang sama seperti tabel batch, dan saringan
// komoditas menjadi `select` (bukan deretan pill).
//
// Kenapa diuji: yang berubah di sini bukan tampilan saja — pembaca harus tetap
// mendapat komoditas, kg, status, dan sisa masa berlaku di kolomnya sendiri, dan
// pilihan saringan harus dibangun dari data yang benar-benar ada.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import FoodSafetyBoard from "../components/FoodSafetyBoard";

const NOW = new Date("2026-10-30T03:00:00Z");

const BATCHES = [
  {
    id: "b1",
    location: "Jakarta",
    commodity: "telur",
    quantity_kg: 400,
    safety_status: "pass",
    freshness_score: 0.8,
    usable_until: "2026-11-20T00:00:00Z",
  },
];

const DECISIONS = [
  {
    decision_id: "d-telur",
    decision_type: "safety_disruption",
    status: "proposed",
    quantity_kg: 100,
    valid: true,
    seconds_remaining: 7200,
    created_at: "2026-10-30T01:00:00Z",
    commodity_name: "telur",
  },
  {
    decision_id: "d-ayam",
    decision_type: "safety_disruption",
    status: "rejected",
    quantity_kg: 40,
    valid: false,
    created_at: "2026-10-29T01:00:00Z",
    commodity_name: "ayam",
  },
  {
    // Bukan keputusan keamanan: tidak boleh ikut tabel ini.
    decision_id: "d-balance",
    decision_type: "regional_balance",
    status: "proposed",
    quantity_kg: 900,
    valid: true,
    seconds_remaining: 3600,
  },
];

function render() {
  return renderToStaticMarkup(
    <FoodSafetyBoard batches={BATCHES} now={NOW} ownLocation="Jakarta" decisions={DECISIONS} />
  );
}

function kartuKeputusan(html: string): string {
  const mulai = html.indexOf('id="safety-keputusan"');
  expect(mulai, "kartu keputusan tidak dirender").toBeGreaterThan(-1);
  return html.slice(mulai);
}

describe("keputusan keamanan — tabel & select", () => {
  it("saringan komoditas berupa select berlabel, opsinya dari data keputusan", () => {
    const html = kartuKeputusan(render());
    expect(html).toContain('id="saring-komoditas-keputusan"');
    expect(html).toContain('for="saring-komoditas-keputusan"');
    expect(html).toContain(">Komoditas<");
    // Opsi: "semua" + komoditas yang benar-benar muncul (urut abjad), tanpa
    // komoditas karangan.
    const opsi = Array.from(
      html.matchAll(/<option[^>]*value="([^"]*)"[^>]*>([^<]*)<\/option>/g)
    ).map((m) => [
      m[1],
      m[2],
    ]);
    expect(opsi).toEqual([
      ["", "Semua komoditas"],
      ["ayam", "ayam"],
      ["telur", "telur"],
    ]);
  });

  it("memakai pola tabel yang sama dengan tabel batch (kepala berlingkup kolom)", () => {
    const html = kartuKeputusan(render());
    expect(html).toContain('<table class="location-table safety-table">');
    expect(html).toContain('<div class="board-table-wrap">');
    const kepala = Array.from(html.matchAll(/<th scope="col"[^>]*>([^<]*)<\/th>/g)).map((m) => m[1]);
    expect(kepala).toEqual([
      "Dibuat",
      "Komoditas",
      "Jumlah",
      "Status",
      "Masa berlaku",
      "Aksi",
    ]);
  });

  it("setiap sel membawa data-label supaya menjadi kartu di layar sempit", () => {
    const html = kartuKeputusan(render());
    const sel = Array.from(html.matchAll(/<td data-label="([^"]+)"/g)).map((m) => m[1]);
    // Dua baris keputusan keamanan × enam kolom.
    expect(sel).toHaveLength(12);
    expect(new Set(sel)).toEqual(
      new Set(["Dibuat", "Komoditas", "Jumlah", "Status", "Masa berlaku", "Aksi"])
    );
  });

  it("komoditas dan kg dicetak di kolomnya sendiri, bukan digabung ke judul", () => {
    const html = kartuKeputusan(render());
    expect(html).toContain('<td data-label="Komoditas">telur</td>');
    expect(html).toContain('<td data-label="Komoditas">ayam</td>');
    expect(html).toContain("100 kg");
    expect(html).toContain("40 kg");
    // Keputusan non-keamanan tidak ikut.
    expect(html).not.toContain("900 kg");
  });

  it("masa berlaku ditulis apa adanya: sisa jam, atau 'lewat' bila tidak berlaku", () => {
    const html = kartuKeputusan(render());
    expect(html).toContain("2 jam lagi");
    expect(html).toContain("lewat");
    // Status tetap terbaca tanpa warna: label status + kata keadaan.
    expect(html).toContain("Diusulkan");
    expect(html).toContain("Ditolak");
    expect(html).toContain("masih berlaku");
    expect(html).toContain("kedaluwarsa");
  });
});
