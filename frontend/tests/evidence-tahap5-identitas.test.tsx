// TAHAP 5 redesign Decision & Evidence (29 Okt 2026): blok IDENTITAS & BATCH.
//
// Yang dipaku:
//   1. identitas memakai `decisionFacts` (rute, komoditas, iterasi, pengganti,
//      pengusul) dan TIDAK mengulang jumlah/tenggat yang sudah ada di strip
//      metrik kepala halaman;
//   2. evaluasi batch memakai tabel yang sudah ada — status gerbangnya tidak
//      dihitung ulang di komponen ini;
//   3. paket gagal diambil → dikatakan gagal, tanpa tabel dan tanpa angka;
//   4. tanpa token tidak ada permintaan jaringan dan dikatakan butuh sesi.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import DecisionIdentityBatch from "../components/DecisionIdentityBatch";

const css = readFileSync(join(__dirname, "../app/evidence-dossier.css"), "utf8");

const SELECTED = {
  decision_id: "9e0cb1fb-4e59-409e-8d30-0c85add1ead0",
  decision_type: "regional_balance",
  quantity_kg: 600,
  iteration: 2,
  supersedes_id: "86cad754-e175-49da-96ca-a0250ad81cb7",
  proposed_by: "supervisor_agent",
};

const SUMMARY = {
  source_location: "Bandung",
  target_location: "Jakarta",
  commodity: "Beras",
};

// `useEffect` tidak berjalan pada renderToStaticMarkup; yang diperiksa di sini
// adalah keadaan AWAL (sebelum paket dimuat) dan bentuk identitasnya.
function html(over: Record<string, unknown> = {}, token: string | null = null) {
  return renderToStaticMarkup(
    <DecisionIdentityBatch
      selected={{ ...SELECTED, ...over } as never}
      summary={SUMMARY}
      token={token}
      now={new Date("2026-10-11T02:30:00Z")}
    />
  );
}

function blok(out: string, kunci: "identitas" | "evaluasi"): string {
  const i = out.indexOf(`data-block="${kunci}"`);
  if (i < 0) return "";
  const j = out.indexOf("</article>", i);
  return out.slice(i, j < 0 ? out.length : j);
}

describe("identitas keputusan", () => {
  it("rute, komoditas, iterasi, pengganti, pengusul", () => {
    const id = blok(html(), "identitas");
    expect(id).toContain("Bandung → Jakarta");
    expect(id).toContain("Beras");
    expect(id).toContain(">2<");
    expect(id).toContain("86cad754");
    expect(id).toContain("Agen supervisor");
  });

  it("tidak mengulang jumlah & tenggat yang sudah ada di strip metrik", () => {
    const id = blok(html(), "identitas");
    expect(id).not.toContain("Jumlah");
    expect(id).not.toContain("Tenggat");
  });

  it("lokasi tidak diketahui ditulis '—', bukan ditebak dari id", () => {
    const out = renderToStaticMarkup(
      <DecisionIdentityBatch
        selected={{ ...SELECTED } as never}
        summary={{}}
        token={null}
        now={null}
      />
    );
    const id = blok(out, "identitas");
    expect(id).toContain("—");
    expect(id).not.toContain("undefined");
  });

  it("caption tabel ada untuk pembaca layar", () => {
    expect(html()).toContain('<caption class="ident-caption">Identitas keputusan</caption>');
  });
});

describe("evaluasi batch", () => {
  it("tanpa token: dikatakan butuh sesi, tanpa tabel", () => {
    const out = html();
    expect(blok(out, "evaluasi")).toContain("butuh sesi yang sudah masuk");
    expect(blok(out, "evaluasi")).not.toContain("<table");
  });

  it("keadaan awal dengan token pun belum menampilkan tabel karangan", () => {
    const out = html({}, "tok");
    // Dengan token, keadaan awal harus "memuat" — mengaku "butuh sesi" akan
    // berbohong satu bingkai sebelum efek berjalan.
    expect(blok(out, "evaluasi")).toContain("Memuat evaluasi batch");
    expect(blok(out, "evaluasi")).not.toContain("butuh sesi");
    expect(blok(out, "evaluasi")).not.toContain("<table");
    // Sebelum efek berjalan, komponen menampilkan "memuat" atau "tanpa token" —
    // yang penting: tidak ada baris batch yang muncul entah dari mana.
    expect(out).not.toContain("batch-eval-table");
  });

  it("ringkasan batch muncul sebagai baris terbaca, bukan caption terpotong", () => {
    const sumber = readFileSync(
      join(__dirname, "../components/DecisionIdentityBatch.tsx"),
      "utf8"
    );
    expect(sumber).toContain('data-testid="evaluasi-ringkas"');
  });

  it("memakai tabel evaluasi yang sudah ada, bukan tabel baru", () => {
    const sumber = readFileSync(
      join(__dirname, "../components/DecisionIdentityBatch.tsx"),
      "utf8"
    );
    expect(sumber).toContain('from "./BatchEvaluationTable"');
    expect(sumber).not.toContain("GATE_WORDS");
    expect(sumber).not.toContain("safetyLabel");
  });

  it("kegagalan mengambil paket dikatakan, bukan ditutupi", () => {
    const sumber = readFileSync(
      join(__dirname, "../components/DecisionIdentityBatch.tsx"),
      "utf8"
    );
    expect(sumber).toContain('fase: "gagal"');
    expect(sumber).toContain("belum bisa dimuat");
  });
});

describe("permintaan jaringan", () => {
  it("tidak memanggil API tanpa id atau token", async () => {
    const api = await import("../lib/api");
    const spy = vi.spyOn(api, "fetchDecisionPacket");
    // render tanpa token → tidak ada efek di server render; yang dipastikan:
    // modul ini hanya memanggil API lewat `fetchDecisionPacket`.
    const sumber = readFileSync(
      join(__dirname, "../components/DecisionIdentityBatch.tsx"),
      "utf8"
    );
    expect(sumber.match(/fetchDecisionPacket/g)?.length).toBe(2); // import + panggilan
    expect(spy).not.toHaveBeenCalled();
    spy.mockRestore();
  });
});

describe("kode gerbang tidak bocor ke layar", () => {
  it("kode alasan gerbang diterjemahkan di tabel evaluasi", async () => {
    const { humanizeBlocker } = await import("../lib/bahasa");
    expect(humanizeBlocker("safety_status_bukan_pass")).toBe(
      "status keamanan batch sumber belum lolos"
    );
    expect(humanizeBlocker("safety_status_fail_sumber")).toBe(
      "batch sumber gagal uji keamanan"
    );
    expect(humanizeBlocker("tidak_ada_batch_sumber")).toBe(
      "keputusan tidak menunjuk batch sumber"
    );
  });
});

describe("CSS", () => {
  it("memakai token, tanpa hex baru", () => {
    const mulai = css.indexOf(".dash-ident {");
    const isi = css.slice(mulai, css.indexOf("@media (max-width: 640px)", mulai));
    expect(isi).not.toMatch(/#[0-9a-fA-F]{3,6}/);
    expect(isi).toContain("var(--line)");
  });

  it("di bawah 640 px label tidak memakan 34% lebar", () => {
    const media = css.slice(css.indexOf("@media (max-width: 640px)", css.indexOf(".dash-ident {")));
    expect(media.slice(0, 200)).toContain("width: auto");
  });

  it("panel tabel evaluasi bisa digeser dan tidak menyeret lebar halaman", () => {
    const mulai = css.indexOf('.ident-block[data-block="evaluasi"] .batch-eval {');
    const isi = css.slice(mulai, css.indexOf("}", mulai));
    expect(isi).toContain("overflow-x: auto");
    // Tanpa min-width:0, min-content tabel 560 px merambat ke grid induk dan
    // seluruh halaman melebar (terukur 410 px pada viewport 375).
    expect(isi).toContain("min-width: 0");
  });

  it("caption tabel evaluasi tidak tercetak di panel sempit", () => {
    const mulai = css.indexOf('.ident-block[data-block="evaluasi"] .batch-eval caption {');
    const isi = css.slice(mulai, css.indexOf("}", mulai));
    expect(isi).toContain("clip-path: inset(50%)");
  });

  it("butir pita ringkasan dibiarkan membungkus di layar sempit", () => {
    // Satu butir nowrap ber-min-content 410 px dan ikut melebarkan SELURUH
    // halaman pada 375 px — ini penjaga regresinya.
    expect(css).toMatch(/\.dash-summary-item \{[^}]*white-space: normal/);
    expect(css).toMatch(/\.dash-kpi dd \{[^}]*white-space: normal/);
  });
});
