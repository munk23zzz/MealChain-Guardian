// Dokumen `07-safety-evidence.md` §4.2 — empat perbaikan yang menyentuh
// halaman "Keamanan Pangan" (`components/FoodSafetyBoard.tsx`):
//
//   butir 1  postur → gerbang: baris batch bisa menyaring daftar keputusan
//            keamanan menurut komoditasnya (data klien, tanpa endpoint baru);
//   butir 3  kesegaran: tiga skor terendah terbuka + sisanya di lipatan,
//            dengan catatan "skor kosong ≠ 0" dan batas data;
//   butir 5  keterangan cakupan: satu baris yang menegaskan bahwa saringan di
//            bilah alat hanya menyaring BATCH, sedangkan daftar keputusan punya
//            saringan sendiri;
//   butir 6  ekspor baca-saja CSV/JSON dari nilai yang tampil.
//
// Butir 4 (penanda mendekati kedaluwarsa) TIDAK diuji ulang di sini: perilakunya
// sudah ada (`expiryState` + kolom "Sisa masa") dan tesnya ada di
// `food-safety.test.ts` / `food-safety-board.test.tsx`.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import FoodSafetyBoard from "../components/FoodSafetyBoard";

const NOW = new Date("2026-10-11T06:00:00Z");

const BATCHES = [
  {
    id: "b1",
    location: "Cianjur",
    commodity: "telur",
    quantity_kg: 400,
    safety_status: "pass",
    freshness_score: 0.69,
    usable_until: "2026-10-11T18:00:00Z",
  },
  {
    id: "b2",
    location: "Cianjur",
    commodity: "ayam",
    quantity_kg: 120,
    safety_status: "fail",
    freshness_score: 0.31,
    usable_until: "2026-10-12T18:00:00Z",
  },
  {
    id: "b3",
    location: "Cianjur",
    commodity: "beras",
    quantity_kg: 300,
    safety_status: "pass",
    freshness_score: null,
    usable_until: null,
  },
  {
    id: "b4",
    location: "Cianjur",
    commodity: "wortel",
    quantity_kg: 90,
    safety_status: "pass",
    freshness_score: 0.55,
    usable_until: "2026-10-13T18:00:00Z",
  },
];

const DECISIONS = [
  {
    decision_id: "d1",
    decision_type: "safety_disruption",
    status: "pending_approval",
    quantity_kg: 492,
    valid: true,
    seconds_remaining: 600,
    created_at: "2026-10-11T05:00:00Z",
    commodity_name: "ayam",
  },
  {
    decision_id: "d2",
    decision_type: "safety_disruption",
    status: "rejected",
    quantity_kg: 80,
    valid: false,
    seconds_remaining: 0,
    created_at: "2026-10-11T04:00:00Z",
    commodity_name: "telur",
  },
];

function render(props: Partial<Parameters<typeof FoodSafetyBoard>[0]> = {}) {
  return renderToStaticMarkup(<FoodSafetyBoard batches={BATCHES} now={NOW} {...props} />);
}

function kartu(html: string, id: string): string {
  const mulai = html.indexOf(`id="${id}"`);
  expect(mulai, `kartu #${id} tidak dirender`).toBeGreaterThan(-1);
  return html.slice(mulai, html.indexOf("</article>", mulai));
}

describe("butir 1 — baris batch menyaring daftar keputusan keamanan", () => {
  it("pilihan saringan memuat komoditas yang ada di keputusan", () => {
    const html = kartu(render({ decisions: DECISIONS }), "safety-keputusan");
    expect(html).toContain("Semua komoditas");
    expect(html).toContain("ayam");
    expect(html).toContain("telur");
    // Tidak ada komoditas yang tidak punya keputusan keamanan.
    expect(html).not.toContain("wortel");
  });

  it("baris batch ber-komoditas ber-keputusan mendapat tombol lompat", () => {
    const html = render({ decisions: DECISIONS });
    expect(html).toContain('aria-label="Lihat keputusan keamanan telur"');
    expect(html).toContain('aria-label="Lihat keputusan keamanan ayam"');
    // beras tidak punya keputusan keamanan → tombolnya tidak dipasang.
    expect(html).not.toContain('aria-label="Lihat keputusan keamanan beras"');
  });

  it("tanpa data keputusan, tidak ada tombol lompat yang menjanjikan tujuan kosong", () => {
    const html = render();
    expect(html).not.toContain("Lihat keputusan keamanan");
    expect(html).not.toContain("Semua komoditas");
  });
});

// Butir 3 versi 29 Okt 2026: tiga kartu (bukti suhu / segera dipakai /
// kesegaran terendah) menjadi SATU kartu "Batch perlu perhatian" — satu baris
// per batch dengan kolom bukti, sisa layak, dan segar. Kontrak lama "tiga
// terendah terbuka + sisanya di lipatan" otomatis gugur bersama kartunya;
// yang dijaga sekarang: kesegaran rendah muncul di kolom Segar, dan skor yang
// tidak dikirim server tetap ditulis "—", bukan 0.
describe("butir 3 — kesegaran rendah terbaca di kolom Segar", () => {
  it("batch berskor segar rendah tampil di tabel perhatian", () => {
    const html = kartu(render(), "safety-bukti-suhu");
    expect(html).toContain("Batch perlu perhatian");
    expect(html).toContain(">Segar<");
    // b2 (31%) paling rendah, jadi wajib muncul.
    expect(html).toContain("31%");
  });

  it("kartu lama tidak lagi dirender (tidak ada dua tempat untuk satu batch)", () => {
    const html = render();
    expect(html).not.toContain("Kesegaran terendah");
    expect(html).not.toContain("Batch perlu segera dipakai");
    expect(html).not.toContain('id="safety-segar"');
    expect(html).not.toContain('id="safety-segera"');
  });

  it("skor kosong ditulis '—' dan dijelaskan, tidak dibaca sebagai 0", () => {
    const html = kartu(render(), "safety-bukti-suhu");
    expect(html).toContain("tidak pernah dibaca sebagai 0");
  });
});

describe("butir 5 — keterangan cakupan dua penyaring berbeda", () => {
  // Kalimat "Cakupan, saringan keadaan, dan pencarian hanya menyaring daftar
  // batch di bawah; …" dibuang 29 Okt 2026: ia menjelaskan mekanisme saringan,
  // bukan keadaan data. Kontraknya kini: kalimat itu TIDAK dicetak, dan dua
  // saringan tetap bisa dibedakan dari labelnya sendiri.
  it("tidak lagi mencetak kalimat cakupan saringan, label saringan tetap berbeda", () => {
    const html = kartu(render({ decisions: DECISIONS }), "safety-batch");
    expect(html).not.toContain("hanya menyaring daftar batch");
    expect(html).not.toContain("saringan komoditas sendiri");
    // Dua saringan tetap bisa dibedakan: bilah batch punya grup sendiri …
    expect(html).toContain('aria-label="Saring batch menurut keadaan"');
  });
});

describe("butir 6 — ekspor baca-saja", () => {
  // 29 Okt 2026 (redesign tahap 3): dua tombol ekspor di kepala kartu bersaing
  // dengan pertanyaan utama halaman, jadi dipindah ke SATU pemicu popup.
  // Kontrak yang dijaga sekarang: kepala kartu punya tepat satu tombol ekspor
  // ber-`aria-haspopup`, dan kedua format tetap tersedia di dalamnya
  // (isi popup diuji lewat interaksi di `safety-table-detail-export.test.tsx`).
  it("ekspor pindah ke satu pemicu popup, bukan dua tombol terpisah", () => {
    const html = kartu(render(), "safety-batch");
    expect(html).toContain("Ekspor…");
    expect(html).toContain('aria-haspopup="dialog"');
    expect(html).not.toContain("Ekspor CSV");
    expect(html).not.toContain("Ekspor JSON");
  });
});
