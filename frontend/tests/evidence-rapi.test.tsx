// Kontrak "kerapian" halaman Decision & Evidence (20 Okt 2026).
//
// Keluhan pemilik: "pada page decision & evidence, gunakan skill untuk
// merapikan desain page tersebut". Yang dirapikan di sini bukan palet dan bukan
// struktur besar (itu sudah dikerjakan 17–20 Okt), melainkan sisa
// ketidakseragaman yang terbaca sebagai "kurang rapi":
//
//   1. Sub-judul "Integritas Bukti" 16 px/700 KALIMAT — lebih besar daripada
//      judul panelnya sendiri ("Jejak & riwayat", label kapital 13 px) di
//      panel yang sama. Hierarki terbalik.
//   2. Dua lipatan (`3 rincian lainnya`, `Rincian pengukuran & ekspor bukti`)
//      tanpa penanda bentuk, sementara `Akibat tiap pilihan` punya ▸/▾. Tiga
//      lipatan, dua bahasa.
//   3. Di kepala keputusan, label "RINGKASAN KEPUTUSAN" bisa terpisah 35 px
//      dari judulnya (1440: 15 px, 1280: 35 px) karena dua baris grid direntang
//      kotak "Langkah berikutnya" di sebelahnya. Jaraknya harus tetap.
//
// Semua angka & nama aturan diambil dari pengukuran aplikasi hidup
// (`_qa/decision-evidence-rapi/`), bukan dari kesan pada tangkapan layar.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import DecisionEvidence from "../components/DecisionEvidence";

const dossier = readFileSync(join(__dirname, "..", "app", "evidence-dossier.css"), "utf8");
const globals = readFileSync(join(__dirname, "..", "app", "globals.css"), "utf8");

function blok(css: string, selector: string): string {
  const aman = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const cocok = new RegExp(`(?:^|\\n)\\s*${aman}\\s*\\{([^}]*)\\}`, "s").exec(css);
  if (!cocok) throw new Error(`blok CSS tidak ditemukan: ${selector}`);
  return cocok[1];
}

describe("kerapian — hierarki judul di panel Jejak", () => {
  it("sub-judul Integritas Bukti memakai bahasa label yang sama dengan judul panel", () => {
    const h3 = blok(dossier, ".evidence-block .integrity-panel h3");
    // Sebelumnya --fs-4/16 px tanpa kapital: satu tingkat DI ATAS label panel
    // (--fs-2/13 px kapital) padahal katanya "satu tingkat di bawahnya".
    expect(h3).toContain("font-size: var(--fs-2)");
    expect(h3).toContain("font-weight: 700");
    expect(h3).toContain("letter-spacing: 0.07em");
    expect(h3).toContain("text-transform: uppercase");
    expect(h3).toContain("color: var(--ink-muted)");
  });

  it("titik aksen di depan judul dibuang, garis rambut dipasang seperti label lain", () => {
    // Satu-satunya judul kartu di halaman ini yang memakai titik aksen biru.
    expect(blok(dossier, ".evidence-block .integrity-panel h3::before")).toContain("content: none");
    const garis = blok(dossier, ".evidence-block .integrity-panel h3::after");
    expect(garis).toContain("height: 1px");
    expect(garis).toContain("background: var(--line)");
  });
});

describe("kerapian — penanda lipatan seragam", () => {
  it("lipatan daftar fakta & lipatan bukti punya chevron seperti 'Akibat tiap pilihan'", () => {
    expect(blok(dossier, ".evidence-page .fact-more > summary::before")).toContain('content: "▸"');
    expect(blok(dossier, ".evidence-page .integrity-more > summary::before")).toContain('content: "▸"');
  });

  it("chevron berbalik saat terbuka", () => {
    expect(dossier).toMatch(/\.evidence-page \.fact-more\[open\] > summary::before \{\s*content: "▾"/);
    expect(dossier).toMatch(/\.evidence-page \.integrity-more\[open\] > summary::before \{\s*content: "▾"/);
  });
});

describe("kerapian — kepala keputusan: label menempel judulnya", () => {
  it("label & judul dibungkus satu blok grid (bukan dua baris yang direntang tetangga)", () => {
    const hero = blok(globals, ".evidence-hero");
    expect(hero).toMatch(/"head\s+next"/);
    expect(hero).not.toContain('"eyebrow');
    const kepala = blok(globals, ".evidence-hero-head");
    expect(kepala).toContain("grid-area: head");
    expect(kepala).toMatch(/gap:\s*var\(--space-1\)/);
  });

  it("markup: label lalu judul, di dalam satu pembungkus", () => {
    const html = renderToStaticMarkup(
      <DecisionEvidence
        decisions={[{ decision_id: "d1", decision_type: "regional_balance", status: "pending_approval" }] as any}
        selected={{
          decision_id: "d1",
          decision_type: "regional_balance",
          status: "pending_approval",
          quantity_kg: 600,
          created_at: "2026-10-07T02:16:47Z",
          expires_at: "2026-10-20T02:16:47Z",
        }}
        selectedId="d1"
        onSelect={() => {}}
        chain={[]}
        summary={{ quantity_kg: 600, commodity: "telur", approval_requirement: { min_approvals: 2 } }}
        supplierContext={null}
        role="sppg_head"
        token="t"
        now={new Date("2026-10-20T01:00:00Z")}
      />,
    );
    expect(html).toMatch(
      /class="evidence-hero-head"[^>]*>\s*<p class="evidence-hero-eyebrow"[\s\S]*?<h2 class="evidence-hero-title"/,
    );
  });
});


describe("kerapian — stepper jalur persetujuan sudah tidak ada", () => {
  it("aturan stepper (rata tengah, penanda, garis sambung) tercabut dari dossier", () => {
    // Kartu "Jalur persetujuan" dilepas 29 Okt 2026 beserta CSS-nya; yang
    // dibaca sekarang hanya kartu "Bukti" + blok governance.
    expect(dossier).not.toMatch(/\.evidence-route-(step|mark|body|label|detail)/);
    expect(dossier).not.toContain("evidence-route-step::before");
  });
});
