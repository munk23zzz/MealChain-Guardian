// TAHAP 4 redesign Decision & Evidence (29 Okt 2026): blok KEAMANAN & PEMASOK.
//
// Yang dipaku:
//   1. dua pertanyaan terpisah — keamanan pangan dan pemasok — bukan satu
//      daftar fakta campur;
//   2. lencana putusan memakai kelas lencana aplikasi (`board-badge`), dan
//      jumlah batch tidak dicetak dua kali (lencana + baris);
//   3. nada status hanya mengubah warna teks nilai, tidak membuat latar;
//   4. pemasok dikecualikan memakai NAMA, bukan id mentah;
//   5. keadaan yang tidak diketahui dikatakan ("belum dimuat"), bukan dikarang
//      jadi "tidak ada pengecualian".
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import DecisionSafetySupplier from "../components/DecisionSafetySupplier";

const css = readFileSync(join(__dirname, "../app/evidence-dossier.css"), "utf8");

const SUMMARY = {
  safety: { worst_status: "PASS", batches_checked: 3, blocked: false },
  verifier: { verdict: "consistent", verified_by: "verifier_agent" },
  supplier: { name: "CV Sumber Pangan", reliability_score: 0.94 },
  material_number: "MAT-001",
  execution_target: "sap_po_draft",
};

const CONTEXT = {
  suppliers: [
    { id: "sup-1", name: "CV Sumber Pangan", batch_ids: ["b1"], evidence_refs: [], batches: [] },
    { id: "sup-2", name: "UD Tani Makmur", batch_ids: ["b2"], evidence_refs: [], batches: [] },
  ],
  scope_location_id: "loc-1",
  can_propose: true,
  reason_unavailable: null,
  exclusions: [
    {
      id: "exc-1",
      supplier_id: "sup-2",
      scope_location_id: "loc-1",
      status: "active" as const,
      reason: "suhu kiriman tidak tercatat pada dua penerimaan terakhir",
      evidence_refs: [],
      source_decision_id: "d-1",
      restoration_decision_id: null,
      activated_at: "2026-10-01T00:00:00Z",
      revoked_at: null,
      revocation_reason: null,
    },
  ],
};

function html(summary: unknown = SUMMARY, context: unknown = CONTEXT) {
  return renderToStaticMarkup(
    <DecisionSafetySupplier summary={summary as never} context={context as never} />
  );
}

function blok(out: string, kunci: "keamanan" | "pemasok"): string {
  const i = out.indexOf(`data-block="${kunci}"`);
  if (i < 0) return "";
  const j = Math.min(
    ...[out.indexOf('data-block="pemasok"', i + 1), out.indexOf("</section>", i)]
      .filter((n) => n > i)
      .concat([out.length])
  );
  return out.slice(i, j);
}

describe("dua pertanyaan, dua kolom", () => {
  it("blok keamanan dan blok pemasok terpisah, dengan jangkar #keamanan", () => {
    const out = html();
    expect(out).toContain('id="keamanan"');
    expect(blok(out, "keamanan")).toContain("Keamanan pangan");
    expect(blok(out, "pemasok")).toContain("Pemasok");
  });

  it("keamanan tidak memuat baris pemasok dan sebaliknya", () => {
    expect(blok(html(), "keamanan")).not.toContain("CV Sumber Pangan");
    expect(blok(html(), "pemasok")).not.toContain("Status keamanan terburuk");
  });
});

describe("putusan keamanan", () => {
  it("lencana memakai kelas aplikasi dan memuat status + jumlah batch", () => {
    const out = html();
    expect(out).toContain("board-badge board-badge-ok");
    expect(out).toContain("Lolos · 3 batch diperiksa");
  });

  it("jumlah batch tidak dicetak dua kali", () => {
    const keamanan = blok(html(), "keamanan");
    expect(keamanan).not.toContain("<th scope=\"row\">Batch diperiksa");
    expect((keamanan.match(/3 batch diperiksa/g) ?? []).length).toBe(1);
  });

  it("status gagal memakai nada bahaya tanpa latar berwarna", () => {
    const out = html({ ...SUMMARY, safety: { worst_status: "FAIL", batches_checked: 4, blocked: true } });
    expect(out).toContain("board-badge-danger");
    expect(out).toContain('data-tone="danger"');
    const blokCss = css.slice(css.lastIndexOf('.safety-row td[data-tone="danger"] {'));
    expect(blokCss.slice(0, blokCss.indexOf("}"))).not.toContain("background");
  });

  it("tanpa putusan keamanan: lencana tidak dirender, bukan lencana kosong", () => {
    const out = html({ ...SUMMARY, safety: null });
    expect(out).not.toContain("safety-verdict-badge");
    expect(blok(out, "keamanan")).toContain("Status keamanan terburuk");
  });
});

describe("pemasok", () => {
  it("nama pemasok + keandalan dari server", () => {
    const pemasok = blok(html(), "pemasok");
    expect(pemasok).toContain("CV Sumber Pangan");
    expect(pemasok).toContain("keandalan 94%");
  });

  it("pengecualian memakai nama pemasok, bukan id", () => {
    const out = html();
    expect(out).toContain("UD Tani Makmur");
    expect(out).toContain("Berlaku");
    expect(out).toContain("suhu kiriman tidak tercatat");
    expect(out).not.toContain("sup-2");
  });

  it("tanpa pengecualian: dikatakan kosong, bukan baris hilang", () => {
    const out = html(SUMMARY, { ...CONTEXT, exclusions: [] });
    expect(out).toContain("Tidak ada pemasok yang sedang dikecualikan");
    expect(out).toContain('data-tone="muted"');
  });

  it("konteks belum dimuat: 'belum dimuat', bukan 'tidak ada pengecualian'", () => {
    const out = html(SUMMARY, null);
    expect(out).toContain("Daftar pemasok untuk lokasi ini belum dimuat");
    expect(out).not.toContain("Tidak ada pemasok yang sedang dikecualikan");
  });

  it("server punya alasan tidak tersedia: alasannya yang ditampilkan", () => {
    const out = html(SUMMARY, {
      ...CONTEXT,
      exclusions: [],
      reason_unavailable: "Peran Anda tidak mencakup lokasi keputusan ini.",
    });
    expect(out).toContain("Peran Anda tidak mencakup lokasi keputusan ini.");
  });
});

describe("kebersihan teks & CSS", () => {
  it("tanpa istilah internal", () => {
    const out = html().toLowerCase();
    for (const kata of ["backend", "endpoint", "null", "worst_status", "supplier_id", "reliability_score"]) {
      expect(out).not.toContain(kata);
    }
  });

  it("nada memakai token, bukan hex", () => {
    const mulai = css.indexOf(".safety-row td[data-tone=");
    const isi = css.slice(mulai, css.indexOf(".safety-note {"));
    expect(isi).not.toMatch(/#[0-9a-fA-F]{3,6}/);
    expect(isi).toContain("var(--danger-ink)");
  });

  it("di bawah 640 px dua kolom jadi satu", () => {
    const media = css.slice(css.indexOf("@media (max-width: 640px)", css.indexOf(".safety-grid {")));
    expect(media.slice(0, 260)).toContain("grid-template-columns: 1fr");
  });
});
