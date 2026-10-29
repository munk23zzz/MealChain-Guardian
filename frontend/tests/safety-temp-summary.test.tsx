// Ringkasan pengawasan — kecukupan bukti suhu masuk ringkasan (29 Okt 2026).
//
// Kenapa: "pengawasan" bukan hanya status uji keamanan. Batch yang LULUS uji
// tetap tidak boleh dialokasikan bila rantai dinginnya tidak terbukti, dan
// angka itu dulu hanya terbaca setelah menggulir ke kartu "Bukti suhu".
// Sekarang ringkasan menyebutnya satu baris, dengan tautan ke rinciannya.
//
// Dua hal yang dikunci:
//   1. Angka kecukupan dihitung dari blok `evidence` server (bukan tebakan UI).
//   2. Daftar lokasi batch gagal TIDAK mengulang nama lokasi yang sama.

import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import FoodSafetyBoard from "../components/FoodSafetyBoard";
import { safetySummaryOfRows } from "../lib/food-safety";

const NOW = new Date("2026-10-29T01:00:00Z");

function batch(over: Record<string, unknown>) {
  return {
    id: "b1",
    location: "Jakarta",
    commodity: "telur",
    quantity_kg: 100,
    safety_status: "pass",
    freshness_score: 0.9,
    usable_until: "2026-11-05T12:00:00Z",
    ...over,
  };
}

const buktiCukup = {
  temperature_observation: "observed",
  evidence_state: "sufficient",
  source: "seed",
  source_label: "log simulasi",
  observed_at: "2026-10-29T00:30:00Z",
  sample_count: 6,
  evidence_sufficient: true,
};

const buktiKurang = {
  temperature_observation: "stale",
  evidence_state: "insufficient",
  source: "seed",
  source_label: "log simulasi",
  observed_at: null,
  sample_count: 1,
  evidence_sufficient: false,
};

describe("Ringkasan pengawasan — baris bukti suhu", () => {
  it("mencetak angka kecukupan + tautan ke rincian", () => {
    const html = renderToStaticMarkup(
      <FoodSafetyBoard
        batches={[
          batch({ id: "b1" }),
          batch({ id: "b2", commodity: "wortel", evidence: buktiCukup }),
          batch({ id: "b3", commodity: "ayam", evidence: buktiKurang }),
        ]}
        now={NOW}
      />
    );
    expect(html).toContain('class="safety-temp"');
    expect(html).toContain("Bukti suhu");
    // Angka kecukupan datang dari blok `evidence` server; dua dari tiga batch
    // di fixture ini tidak cukup (satu bukti kurang, satu tidak tercatat).
    expect(html).toContain("1 dari 3");
    expect(html).toContain("belum cukup");
    expect(html).toContain('href="#safety-bukti-suhu"');
  });

  it("tanpa batch, baris tidak dicetak (tidak ada angka karangan)", () => {
    const html = renderToStaticMarkup(<FoodSafetyBoard batches={[]} now={NOW} />);
    expect(html).not.toContain('class="safety-temp"');
  });
});

describe("Ringkasan pengawasan — lokasi batch gagal tidak diulang", () => {
  it("dua batch gagal di lokasi yang sama disebut satu kali", () => {
    const ringkas = safetySummaryOfRows([
      { location: "Jakarta", tone: "danger" },
      { location: "Jakarta", tone: "danger" },
      { location: "Bandung", tone: "ok" },
    ] as never);
    expect(ringkas.failed).toBe(2);
    expect(ringkas.failedLocations).toEqual(["Jakarta"]);
  });
});
