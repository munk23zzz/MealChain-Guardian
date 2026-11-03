// S5 (29 Okt 2026) — "Riwayat penerimaan" dan "Register eksklusi" dijadikan satu
// keluarga bentuk, lalu form Usul eksklusi ditaruh berdampingan dengan register.
//
// Dua hal yang dijaga di sini:
// 1. Bentuk kepala sama: judul + pil jumlah + SATU kalimat keadaan. Sebelumnya
//    register hanya punya judul, jadi dua register yang bersebelahan di halaman
//    yang sama terbaca seperti dua halaman berbeda.
// 2. Satu kosakata: halaman ini memakai "eksklusi" (Register eksklusi, Usul
//    eksklusi). Panel usul dulu mencampur "Supplier governance", "Alasan
//    exclusion", "Ajukan exclusion", "Tidak ada auto execute".
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import SupplierBoard from "../components/SupplierBoard";
import type { SupplierContext } from "../lib/supplier-exclusions";

const SUPPLIERS = {
  count: 1,
  total: 1,
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
  ],
};

const REGISTER = {
  count: 1,
  total: 1,
  items: [
    {
      id: "ex1",
      supplier_id: "s1",
      supplier: "Wortel Lestari Cianjur",
      reason: "Tiga kiriman berturut-turut di bawah standar",
      status: "active",
      at: "27 Okt 2026 · 09.14",
      decision_id: "d-1234abcd",
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

/** Potong satu blok kartu supaya asersi tidak ikut menilai bagian halaman lain. */
function kartu(html: string, id: string): string {
  const mulai = html.indexOf(`id="${id}"`);
  expect(mulai).toBeGreaterThan(-1);
  const sesudah = html.slice(mulai);
  const akhir = sesudah.indexOf("</article>");
  return sesudah.slice(0, akhir < 0 ? sesudah.length : akhir);
}

describe("S5 — register eksklusi berbentuk sama dengan riwayat penerimaan", () => {
  it("kepala register: judul + pil jumlah di dalam card-header", () => {
    const reg = kartu(render({ exclusions: REGISTER }), "supplier-register");
    expect(reg).toContain('class="card-header"');
    expect(reg).toContain("Register eksklusi");
    expect(reg).toContain('class="count-pill">1 catatan<');
  });

  it("register terisi: satu kalimat keadaan yang menyebut arti barisnya", () => {
    const reg = kartu(render({ exclusions: REGISTER }), "supplier-register");
    expect(reg).toContain('class="register-note"');
    expect(reg).toContain("keputusan yang sudah disetujui");
    // Tanpa pil saat kosong — angka 0 bukan informasi.
    const kosong = kartu(render(), "supplier-register");
    expect(kosong).not.toContain("count-pill");
  });

  it("register kosong: pesan + aksi menuju kotak usul", () => {
    const reg = kartu(render(), "supplier-register");
    expect(reg).toContain("Tidak ada pemasok yang sedang dieksklusi");
    expect(reg).toContain('href="#supplier-usul"');
    expect(reg).toContain("Ajukan eksklusi");
  });
});

describe("S5 — register (baca) dan usul (tulis) satu wadah", () => {
  it("kedua bagian duduk di dalam .register-grid", () => {
    const html = render({ exclusions: REGISTER });
    const mulai = html.indexOf('class="register-grid"');
    expect(mulai).toBeGreaterThan(-1);
    const isi = html.slice(mulai, html.indexOf("</section>", mulai));
    expect(isi).toContain('id="supplier-register"');
    expect(isi).toContain('id="supplier-usul"');
  });

  it("urutan DOM: register dulu (baca), usul sesudahnya (tulis)", () => {
    const html = render({ exclusions: REGISTER });
    expect(html.indexOf('id="supplier-register"')).toBeLessThan(html.indexOf('id="supplier-usul"'));
  });
});

describe("S5 — panel usul memakai satu kosakata (Indonesia)", () => {
  // Peran yang berwenang + `can_propose` benar: hanya di keadaan itu form usul
  // benar-benar dirender (kalau tidak, panelnya cuma kalimat "hanya baca").
  const BOLEH = { ...CONTEXT, can_propose: true } as unknown as SupplierContext;
  const html = render({
    selectedDecisionId: "d-1234abcd",
    supplierContext: BOLEH,
    role: "sppg_head",
  });

  it("tidak ada lagi istilah Inggris yang tercampur", () => {
    for (const kata of ["Supplier governance", "Supplier exclusion", "Alasan exclusion", "Ajukan exclusion", "auto execute", "Exclusion aktif"]) {
      expect(html).not.toContain(kata);
    }
  });

  it("istilah Indonesianya memang tercetak", () => {
    expect(html).toContain("Tata kelola pemasok");
    expect(html).toContain("Alasan eksklusi");
    expect(html).toContain("Ajukan eksklusi");
    expect(html).toContain("Kode pemasok:");
  });

  it("usulan tidak diklaim berjalan sendiri", () => {
    expect(html).toContain("antrean persetujuan");
    expect(html).toContain("tidak ada yang dijalankan otomatis");
  });
});
