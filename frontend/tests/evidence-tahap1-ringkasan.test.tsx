// TAHAP 1 redesign Decision & Evidence (29 Okt 2026): ringkasan keputusan —
// pita jawaban + strip angka + triase.
//
// Yang dipaku:
//   1. urutan baca: band keadaan → judul keputusan → angka;
//   2. angka datang dari `lib/evidence` (satuan, pemisah ribuan, "—" untuk
//      nilai kosong) — bukan format baru di komponen;
//   3. "Perlu diperhatikan" HANYA muncul bila ada temuan (keputusan sehat tidak
//      menampilkan blok kosong);
//   4. keadaan yang tidak bisa dihitung dikatakan, bukan dikarang.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import DecisionSummary from "../components/DecisionSummary";

const root = join(__dirname, "..");
const css = readFileSync(join(root, "app/evidence-dossier.css"), "utf8");
const NOW = new Date("2026-10-11T02:30:00Z");

const KEPUTUSAN = {
  decision_id: "9e0cb1fb-4e59-409e-8d30-0c85add1ead0",
  decision_type: "regional_balance",
  status: "pending_approval",
  quantity_kg: 600,
  commodity_name: "Beras",
  from_location_name: "Bandung",
  to_location_name: "Jakarta",
  created_at: "2026-10-07T02:16:47Z",
  expires_at: "2026-10-11T02:16:47.973521+00:00",
  iteration: 1,
};

// `verifier.verified_by` WAJIB terisi untuk keadaan "sehat": tanpa itu helper
// `attentionFlags` menambahkan temuan "Belum diverifikasi" dan blok triase
// memang seharusnya muncul. Fixture sehat harus sehat sungguhan.
const RINGKASAN_KOSONG = {
  verifier: { verified_by: "verifier-demo", verdict: "CONSISTENT" },
  status: "pending_approval",
  approval_requirement: { required_roles: [["sppg_head"]], min_approvals: 1 },
  approval_state: { missing: [["sppg_head"]], approved_roles: [], satisfied: false },
  approvals: [],
  blocking_reasons: [],
};

function html(over: Record<string, unknown> = {}, now: Date | null = NOW) {
  return renderToStaticMarkup(
    <DecisionSummary
      selected={{ ...KEPUTUSAN, ...over } as never}
      summary={RINGKASAN_KOSONG}
      now={now}
    />
  );
}

describe("urutan baca", () => {
  it("band keadaan → judul → angka", () => {
    const out = html();
    const iBand = out.indexOf("dash-summary-bar");
    const iJudul = out.indexOf("dash-summary-title");
    const iAngka = out.indexOf("dash-kpis");
    expect(iBand).toBeGreaterThan(-1);
    expect(iJudul).toBeGreaterThan(iBand);
    expect(iAngka).toBeGreaterThan(iJudul);
  });

  it("judul adalah kalimat keputusan, bukan label seksi", () => {
    // Komoditas muncul bila RINGKASAN membawanya; yang dipaku di sini bentuk
    // kalimatnya (kata kerja + kuantitas), bukan kelengkapan medan server.
    const out = html();
    const judul = out.slice(out.indexOf('class="dash-summary-title"'), out.indexOf("</h2>"));
    expect(judul).toMatch(/Seimbangkan .*600 kg/);
    expect(judul).not.toContain("Ringkasan keputusan");
  });

  it("seksi punya nama aksesibel lewat jangkar ringkasan", () => {
    expect(html()).toContain('id="ringkasan"');
  });
});

describe("band keadaan", () => {
  it("jendela berlaku ditulis dalam kata, bukan jam mentah", () => {
    const out = html();
    expect(out).toContain("Jendela berlaku:");
    expect(out).toContain("Lewat");
    expect(out).not.toContain("02:16:47");
  });

  it("umur jendela memakai persen terpakai, dan lewat tenggat bertanda bahaya", () => {
    const aman = renderToStaticMarkup(
      <DecisionSummary
        selected={{ ...KEPUTUSAN, expires_at: "2026-10-20T02:00:00Z" } as never}
        summary={RINGKASAN_KOSONG}
        now={NOW}
      />
    );
    expect(aman).toMatch(/Jendela terpakai \d+%/);

    const lewat = html();
    expect(lewat).toContain('data-state="lewat"');
  });

  it("tanpa jam acuan: tenggat ditulis '—', bukan angka karangan", () => {
    const out = html({}, null);
    expect(out).toContain("Jendela berlaku:");
    expect(out).not.toContain("Lewat");
  });

  it("nomor keputusan & iterasi ikut di band", () => {
    const out = html();
    expect(out).toContain("#9e0cb1fb");
    expect(out).toContain("iterasi v1");
  });
});

describe("strip angka", () => {
  it("memakai pemisah ribuan dan satuan dari helper", () => {
    const out = html({ safe_delivered_cost: 16206000 });
    expect(out).toContain("Rp16.206.000");
    expect(out).toContain("600 kg");
  });

  it("biaya kosong ditulis '—', bukan Rp0", () => {
    const out = html({ safe_delivered_cost: null });
    expect(out).toContain("Biaya aman terkirim");
    expect(out).not.toContain("Rp0");
  });
});

describe("triase", () => {
  it("keputusan sehat: blok 'Perlu diperhatikan' tidak dirender", () => {
    expect(html()).not.toContain("Perlu diperhatikan");
  });

  it("tanpa verdict verifier: temuan 'Belum diverifikasi' muncul dengan hitungan", () => {
    const out = renderToStaticMarkup(
      <DecisionSummary
        selected={{ ...KEPUTUSAN } as never}
        summary={{ ...RINGKASAN_KOSONG, verifier: null }}
        now={NOW}
      />
    );
    expect(out).toContain("Perlu diperhatikan (1)");
    expect(out).toContain("Belum diverifikasi");
    expect(out).toMatch(/data-tone="warn"/);
  });
});

describe("CSS clean dashboard", () => {
  it("kartu memakai token, angka tabular", () => {
    const blok = css.slice(css.indexOf(".dash-kpi dd {"));
    const isi = blok.slice(0, blok.indexOf("}"));
    expect(isi).toContain("font-variant-numeric: tabular-nums");
    expect(isi).not.toMatch(/#[0-9a-fA-F]{3,6}/);
  });

  it("label KPI kapital kecil, bukan huruf besar-besaran", () => {
    const blok = css.slice(css.indexOf(".dash-kpi dt {"));
    const isi = blok.slice(0, blok.indexOf("}"));
    expect(isi).toContain("text-transform: uppercase");
    expect(isi).toContain("font-size: var(--fs-1)");
  });

  it("strip angka menyesuaikan lebar di bawah 640 px", () => {
    const media = css.slice(css.indexOf("@media (max-width: 640px)", css.indexOf(".dash-kpis {")));
    expect(media.slice(0, 700)).toContain("minmax(140px, 1fr)");
    // Terukur 375 px: kartu 150 px membuat "Rp16.206.000" pada 20 px terpotong,
    // jadi nilainya turun satu langkah. Ini penjaga regresi untuk itu.
    expect(media.slice(0, 700)).toContain("font-size: var(--fs-4)");
  });

  it("tinggi kartu KPI seragam walau label satu/dua baris", () => {
    const blok = css.slice(css.indexOf(".dash-kpis {"));
    expect(blok.slice(0, blok.indexOf("}"))).toContain("grid-auto-rows: 1fr");
  });
});
