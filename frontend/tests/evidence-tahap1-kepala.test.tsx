// TAHAP 1 redesign Decision & Evidence (29 Okt 2026): kepala kartu + bilah
// kendali + navigasi bagian.
//
// Lingkup tahap ini SEMPIT dan sengaja dipaku begitu:
//   1. kepala memakai pola kartu Overview (judul + penjelas kiri, penanda kanan);
//   2. pemilih keputusan pindah dari kepala ke bilah kendalinya sendiri;
//   3. navigasi bagian tetap EMPAT tujuan dengan jangkar yang sama seperti
//      sebelumnya — tahap 1 tidak boleh mengubah sasaran nav.
// Isi halaman di bawah nav (ringkasan, keputusan, bukti, jejak) belum berubah;
// tes di sini tidak memakunya supaya tahap 2–5 bebas mengubahnya.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import DecisionEvidence from "../components/DecisionEvidence";

const root = join(__dirname, "..");
const css = readFileSync(join(root, "app/evidence-dossier.css"), "utf8");

const NOW = new Date("2026-10-11T02:30:00Z");
const SELECTED = {
  decision_id: "d1",
  decision_type: "regional_balance",
  status: "pending_approval",
  quantity_kg: 600,
  created_at: "2026-10-07T02:16:47Z",
  expires_at: "2026-10-11T02:16:47.973521+00:00",
};
const DAFTAR = [
  { decision_id: "d1", decision_type: "regional_balance", status: "pending_approval" },
];

function html(over: Record<string, unknown> = {}) {
  return renderToStaticMarkup(
    <DecisionEvidence
      decisions={DAFTAR as never}
      selected={SELECTED as never}
      selectedId="d1"
      onSelect={() => {}}
      chain={[]}
      summary={null}
      supplierContext={null}
      role="sppg_head"
      token="t"
      now={NOW}
      {...over}
    />
  );
}

describe("kepala: pola kartu bersama", () => {
  // 30 Okt 2026 — kepala halaman diseragamkan: TIDAK ada lagi pola kedua
  // (`.page-header`). Halaman ini memakai `PageHeader` yang sama dengan
  // tujuh tab lain, jadi bentuknya tetap kartu tapi komponennya satu.
  it("memakai PageHeader bersama, bukan penanda kepala kedua", () => {
    const out = html();
    expect(out).toContain('class="page-header"');
    expect(out).toContain("page-header-text");
    expect(out).toContain("page-header-meta");
    // Penanda kepala KEDUA sudah tidak ada: satu pola untuk semua halaman.
    expect(out).not.toMatch(/overview-header/);
  });

  it("judul halaman dirender sebagai h1 yang menamai section", () => {
    const out = html();
    expect(out).toMatch(/<h1 id="judul-bukti">Decision &amp; Evidence<\/h1>/);
    expect(out).toContain('aria-labelledby="judul-bukti"');
  });

  it("penanda kanan: data simulasi, status keputusan, nomor keputusan", () => {
    const out = html();
    expect(out).toContain("Data simulasi");
    expect(out).toContain("evidence-header-status");
    expect(out).toContain('data-status="pending_approval"');
    expect(out).toContain("#d1");
  });

  it("tanpa keputusan terpilih: status & nomor tidak dikarang", () => {
    const out = html({ selected: null, selectedId: null });
    expect(out).toContain("Data simulasi");
    expect(out).not.toContain("evidence-header-status");
    expect(out).not.toContain("#d1");
  });
});

// 30 Okt 2026 — KEPUTUSAN PEMILIK MEMBALIK TAHAP 1: pemilih "Keputusan yang
// diperiksa" DIPISAH dari kartu kepala dan diletakkan di BAWAH navigasi bagian.
// Urutan baca yang diminta: kepala → "Bagian: Ringkasan · Persetujuan · Bukti
// biaya · Keamanan & pemasok · Jejak & integritas" → pemilih → isi halaman.
describe("pemilih keputusan dipisah ke bawah nav bagian", () => {
  it("pemilih berada DI LUAR kepala dan SESUDAH nav bagian", () => {
    const out = html();
    const kepalaTutup = out.indexOf("</header>");
    const nav = out.indexOf('aria-label="Bagian halaman Decision &amp; Evidence"');
    const pemilih = out.indexOf('id="pilih-keputusan"');
    expect(kepalaTutup).toBeGreaterThan(-1);
    expect(nav).toBeGreaterThan(-1);
    expect(pemilih).toBeGreaterThan(-1);
    expect(pemilih).toBeGreaterThan(kepalaTutup);
    expect(pemilih).toBeGreaterThan(nav);
  });

  it("kepala tidak lagi membawa bilah kendali di dalamnya", () => {
    const out = html();
    const kepala = out.slice(0, out.indexOf("</header>"));
    expect(kepala).not.toContain("evidence-controls");
    expect(kepala).not.toContain("pilih-keputusan");
  });

  it("tanpa keputusan terpilih pemilih tetap ada (jalan memilih keputusan)", () => {
    // Nav bagian tidak dirender saat belum ada keputusan, jadi pemilih tidak
    // boleh ikut hilang — kalau hilang, tidak ada cara memilih keputusan.
    const out = html({ selected: null, selectedId: null });
    expect(out).not.toContain('aria-label="Bagian halaman Decision &amp; Evidence"');
    expect(out).toContain('id="pilih-keputusan"');
  });

  it("CSS: bilah kembali berbentuk kartu, aturan penempelan ke kepala dicabut", () => {
    // Selektor lama `.evidence-page .page-header .evidence-controls` sudah
    // tidak punya sasaran; kalau tertinggal, ia menipu pembaca berikutnya.
    expect(css).not.toContain(".evidence-page .page-header .evidence-controls");
    expect(css).toMatch(
      /\.evidence-page \.evidence-controls \.dpick \{\s*max-width: none/
    );
  });

  it("di layar sempit kepala kembali satu kolom", () => {
    expect(css).toMatch(
      /@media \(max-width: 640px\) \{\s*\.evidence-page \.page-header \{[^}]*grid-template-columns: minmax\(0, 1fr\)/
    );
  });
});

describe("navigasi bagian & kerangka kosong", () => {
  // 29 Okt 2026: pemilik memilih mengosongkan seluruh isi halaman lebih dulu
  // ("hapus semua, sisakan kerangka, bangun ulang dari nol"). Selama isi belum
  // dipasang lagi, nav bagian TIDAK dirender: empat tujuannya menunjuk jangkar
  // yang belum ada, dan tautan mati lebih buruk daripada tanpa nav.
  it("nav dipasang kembali: syaratnya keputusan terpilih, bukan gerbang isi", () => {
    // Tahap 1–6 menyembunyikan nav selama isi dikosongkan supaya tidak ada
    // tautan mati. Tahap 7 mengembalikannya: semua jangkar kini ada, jadi
    // syaratnya kembali ke kenyataan (ada keputusan, daftar tidak dimuat).
    const out = html();
    expect(out).toContain('aria-label="Bagian halaman Decision &amp; Evidence"');
    expect(out).toContain('href="#ringkasan"');
  });

  it("kepala & pemilih keputusan tetap bekerja walau isi kosong", () => {
    const out = html();
    expect(out).toContain('id="judul-bukti"');
    expect(out).toContain('id="pilih-keputusan"');
    expect(out).toContain("Data simulasi");
  });
});

describe("tokens & aksesibilitas", () => {
  it("pil status tidak membungkus dua baris", () => {
    const blok = css.slice(css.indexOf(".evidence-header-status {"));
    expect(blok.slice(0, blok.indexOf("}"))).toContain("white-space: nowrap");
  });

  it("nada pil memakai token status yang sudah ada, bukan hex baru", () => {
    const warna = css.slice(css.indexOf('.evidence-header-status[data-status="pending_approval"]'));
    const potongan = warna.slice(0, warna.indexOf(".evidence-controls"));
    expect(potongan).toContain("var(--warn-bg)");
    expect(potongan).toContain("var(--ok-bg)");
    expect(potongan).toContain("var(--danger-bg)");
    expect(potongan).not.toMatch(/#[0-9a-fA-F]{3,6}/);
  });

  it("irama halaman 14 px seperti Overview", () => {
    expect(css).toMatch(/\.evidence-page\s*\{\s*gap: 14px;/);
  });

  it("tidak ada istilah internal di kepala baru", () => {
    const out = html();
    for (const kata of ["/decisions", "backend", "endpoint", "agent_traces"]) {
      expect(out.slice(0, out.indexOf("</header>"))).not.toContain(kata);
    }
  });
});
