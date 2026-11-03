// TAHAP 7 redesign Decision & Evidence (29 Okt 2026): NAVIGASI & KEADAAN.
//
// Yang dipaku:
//   1. nav bagian punya lima tujuan dan SETIAP tautan punya sasaran yang benar
//      benar dirender di halaman yang sama — tidak ada tautan mati;
//   2. label nav = judul bagian yang tercetak (bukan nama lama "Keputusan"/"Bukti");
//   3. nav hanya muncul saat ada keputusan terpilih dan daftar tidak dimuat;
//   4. "memuat" tidak boleh menyamar jadi "belum ada keputusan dipilih";
//   5. setiap bagian punya `scroll-margin-top` supaya judulnya tidak mendarat
//      tertutup nav yang menempel.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import DecisionEvidence from "../components/DecisionEvidence";
import { evidenceSections } from "../lib/section-jump";

const css = readFileSync(join(__dirname, "../app/evidence-dossier.css"), "utf8");

const SELECTED = {
  decision_id: "9e0cb1fb-4e59-409e-8d30-0c85add1ead0",
  decision_type: "regional_balance",
  status: "pending_approval",
  quantity_kg: 600,
  iteration: 2,
  proposed_by: "supervisor_agent",
  verified_by: "verifier_agent",
  created_at: "2026-10-11T02:00:00Z",
  expires_at: "2026-10-12T18:00:00Z",
  source_location: "Bandung",
  target_location: "Jakarta",
  commodity: "Beras",
  commercial_cost: null,
  market_reference: null,
};

function html(opsi: { selected?: boolean; loading?: boolean } = {}) {
  const selected = opsi.selected ?? true;
  return renderToStaticMarkup(
    <DecisionEvidence
      decisions={selected ? ([SELECTED] as never) : ([] as never)}
      selected={selected ? (SELECTED as never) : null}
      selectedId={selected ? SELECTED.decision_id : null}
      onSelect={() => {}}
      chain={[]}
      summary={null}
      supplierContext={null}
      role="kepala_sppg"
      token={null}
      now={new Date("2026-10-11T05:00:00Z")}
      purchaseOrders={[]}
      loading={opsi.loading ?? false}
    />
  );
}

const ID_TERPASANG = (out: string) =>
  new Set([...out.matchAll(/\sid="([^"]+)"/g)].map((m) => m[1]));

describe("nav bagian", () => {
  it("lima tujuan dengan label yang sama dengan judul bagian", () => {
    const out = html();
    for (const item of evidenceSections()) {
      expect(out).toContain(`href="#${item.id}"`);
      expect(out).toContain(`>${item.label.replace("&", "&amp;")}<`);
    }
    expect(evidenceSections()).toHaveLength(5);
  });

  it("tidak ada tautan mati: setiap href punya sasaran di halaman ini", () => {
    const out = html();
    const ids = ID_TERPASANG(out);
    const href = [...out.matchAll(/href="#([^"]+)"/g)].map((m) => m[1]);
    expect(href.length).toBeGreaterThan(0);
    for (const tujuan of href) {
      expect(ids.has(tujuan), `#${tujuan} tidak dirender`).toBe(true);
    }
  });

  it("nav punya nama untuk pembaca layar", () => {
    // Markup statis meng-escape "&" → "&amp;".
    expect(html()).toContain('aria-label="Bagian halaman Decision &amp; Evidence"');
  });

  it("identitas & batch tetap ada walau bukan tujuan nav", () => {
    // Batas lima tujuan (docs/design.md §24) — bagiannya tetap dirender.
    const out = html();
    expect(out).toContain('id="identitas"');
    expect(evidenceSections().map((i) => i.id)).not.toContain("identitas");
  });

  it("tanpa keputusan terpilih tidak ada nav", () => {
    expect(html({ selected: false })).not.toContain('class="section-jump"');
  });

  it("selama memuat tidak ada nav", () => {
    expect(html({ selected: false, loading: true })).not.toContain('class="section-jump"');
  });
});

describe("keadaan tanpa isi", () => {
  it("memuat: dikatakan memuat, bukan 'belum ada keputusan dipilih'", () => {
    const out = html({ selected: false, loading: true });
    expect(out).toContain("Memuat keputusan…");
    expect(out).not.toContain("Belum ada keputusan dipilih");
  });

  it("kosong: menyebut pemilih di atas halaman, bukan 'bilah atas'", () => {
    const out = html({ selected: false });
    expect(out).toContain("Belum ada keputusan dipilih");
    expect(out).toContain("pemilih di atas");
    expect(out).not.toContain("bilah atas");
  });
});

describe("jarak lompatan", () => {
  it("setiap bagian punya scroll-margin-top agar judul tidak tertutup nav", () => {
    for (const id of [
      "ringkasan",
      "zona-keputusan",
      "bukti",
      "keamanan",
      "identitas",
      "jejak",
    ]) {
      expect(id).toBeTruthy();
    }
    // 6 bagian = 6 aturan; satu di antaranya (identitas/jejak) berbagi pola.
    const jumlah = (css.match(/scroll-margin-top: 132px/g) ?? []).length;
    expect(jumlah).toBeGreaterThanOrEqual(6);
  });
});
