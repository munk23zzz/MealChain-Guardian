// Upgrade kartu "Bukti suhu" (29 Okt 2026, lanjutan).
//
// Tiga tambahan, semuanya dari blok `evidence` server — tidak ada hitungan baru:
//
//   1. Kebaruan bukti per baris: `observed_at` sudah dikirim tetapi tidak pernah
//      dicetak, padahal bukti suhu yang berumur dua hari menjawab pertanyaan
//      "masih berlaku?" secara berbeda dari yang berumur sepuluh menit.
//   2. Penanda "wajib dingin" untuk baris yang `cold_chain_required` = true:
//      alasan kenapa bukti kurang itu penting ada di data, bukan di kalimat
//      statis kartu.
//   3. Jumlah sampel total di kaki kartu, supaya "cukup bukti" punya ukuran
//      berapa pembacaan yang menopangnya.
//
// Yang TIDAK diubah: bar tersegmen, legenda berangka, urutan "paling perlu
// tindakan lebih dulu", dan pemotongan 6 baris — kontrak 27 Okt.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import TemperatureEvidenceCard from "../components/TemperatureEvidenceCard";
import type { EvidenceRow, EvidenceSummary } from "../lib/food-safety";

function baris(over: Partial<EvidenceRow> = {}): EvidenceRow {
  const dasar: EvidenceRow = {
    id: "b1",
    commodity: "telur",
    observation: "observed",
    observationLabel: "Teramati",
    state: "sufficient",
    stateLabel: "Bukti cukup",
    tone: "ok",
    sufficient: true,
    sampleCount: 4,
    observedAt: "2026-10-29T02:12:00Z",
    source: "seed",
    sourceLabel: "log simulasi",
    profileVersion: "sim-2026-10-27.v1",
    policyKind: "simulated_policy",
    coldChainRequired: true,
    reasons: [],
  };
  return { ...dasar, ...over };
}

function ringkasan(rows: readonly EvidenceRow[]): EvidenceSummary {
  const out: EvidenceSummary = {
    total: rows.length,
    sufficient: 0,
    insufficient: 0,
    ambiguous: 0,
    unknown: 0,
    perluVerifikasi: 0,
  };
  for (const row of rows) {
    out[row.state] += 1;
    if (!row.sufficient && row.coldChainRequired !== false) out.perluVerifikasi += 1;
  }
  return out;
}

function render(rows: EvidenceRow[]): string {
  return renderToStaticMarkup(
    <TemperatureEvidenceCard rows={rows} summary={ringkasan(rows)} />
  );
}

describe("bukti suhu — kebaruan pembacaan", () => {
  it("mencetak waktu pembacaan terakhir bila server mengirimnya", () => {
    const html = render([baris()]);
    expect(html).toContain("dibaca");
    expect(html).toContain("09.12"); // WIB dari 02.12Z
  });

  it("tidak mengarang waktu saat observed_at kosong", () => {
    const html = render([baris({ observedAt: null })]);
    expect(html).not.toContain("dibaca");
  });
});

describe("bukti suhu — alasan bukti dituntut", () => {
  it("menandai baris yang wajib rantai dingin", () => {
    expect(render([baris({ coldChainRequired: true })])).toContain("wajib dingin");
  });

  it("tidak menandai komoditas yang tidak wajib dingin", () => {
    expect(render([baris({ coldChainRequired: false })])).not.toContain("wajib dingin");
  });
});

describe("bukti suhu — ukuran bukti", () => {
  it("menjumlahkan sampel yang tercatat di kaki kartu", () => {
    const html = render([baris(), baris({ id: "b2", sampleCount: 2 })]);
    expect(html).toContain("6 sampel tercatat");
  });

  it("tidak menulis nol sampel bila server tidak mengirim jumlahnya", () => {
    const html = render([baris({ sampleCount: null })]);
    expect(html).not.toContain("0 sampel tercatat");
    expect(html).not.toContain("sampel tercatat");
  });
});
