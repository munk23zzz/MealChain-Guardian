// Render kartu keempat ("Perkiraan N hari") di pop-up Pasokan & permintaan.
//
// Kontrak berubah 29 Okt 2026 atas permintaan pemilik. Sebelumnya kartu mencetak
// tiga kode teknis berderet — `sap_rpt_1_6 · keyakinan 94,2% · SAP-RPT-1.6` —
// dan itu terbaca sebagai kebocoran backend, bukan penjelasan. Yang dikunci:
//   1. nama metode mentah TIDAK pernah muncul di layar;
//   2. kode sumber tetap tersedia sebagai atribut `data-source` (jejak audit
//      tidak hilang, hanya tidak dicetak);
//   3. kalimat yang MEMANG mengubah cara membaca angka ("dasar tipis",
//      "cadangan statistik dipakai") tetap tampil.
//
// Tes ini merender komponen sungguhan (bukan salinan markup) lewat
// `renderToStaticMarkup`, dengan detail yang dibentuk oleh
// `buildSupplyDemandDetail` — jalur yang sama dipakai halaman.

import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import SupplyDemandPanel from "../components/SupplyDemandPanel";
import { buildSupplyDemandDetail } from "../lib/supply-demand";

const DASAR = {
  location: "Bandung",
  commodity: "ayam",
  balance: { shortage_kg: 780, surplus_kg: 0 },
  supply: { quantity_kg: 300, recorded_at: "2026-10-28T15:00:00Z", source: "mock_sap" },
  demand: { quantity_kg: 1080, needed_by: "2026-10-31T15:00:00Z" },
  batches: [],
};

function render(forecast: Record<string, unknown> | null): string {
  const detail = buildSupplyDemandDetail({ ...DASAR, forecast });
  return renderToStaticMarkup(
    <SupplyDemandPanel detail={detail} commodity="ayam" />
  );
}

describe("SupplyDemandPanel — label sumber perkiraan", () => {
  it("tidak mencetak nama metode atau kode sumber di layar", () => {
    const html = render({
      forecast_qty_kg: 2106.13,
      method: "sap_rpt_1_6",
      confidence: 0.9422267935248946,
      source: "SAP-RPT-1.6",
      fallback_used: false,
      sample_count: 28,
    });

    expect(html).toContain("Perkiraan 7 hari");
    expect(html).toContain("2.106,13"); // angkanya tetap terbaca
    expect(html).not.toContain("sap_rpt_1_6");
    expect(html).not.toContain("keyakinan 94.2%");
    // Kode sumber hanya boleh hidup di atribut audit, tidak dicetak sebagai teks.
    expect(html).not.toContain(">SAP-RPT-1.6<");
    // Bukan "dasar tipis": angka keyakinan model bukan penanda riwayat tipis.
    expect(html).not.toContain("dasar tipis");
    expect(html).toContain('data-source="SAP-RPT-1.6"');
  });

  it("menyebut cadangan statistik dipakai — itu mengubah cara membaca angka", () => {
    const html = render({
      forecast_qty_kg: 2171.45,
      method: "statistical_fallback",
      confidence: 1,
      source: "statistical_fallback",
      fallback_used: true,
      reason: "dimatikan oleh FORECAST_PROVIDER",
    });

    expect(html).toContain("cadangan statistik");
    expect(html).not.toContain(">statistical_fallback<");
    expect(html).toContain('data-source="statistical_fallback"');
    expect(html).not.toContain("SAP-RPT-1.6");
  });

  it("tidak mengarang label saat server tidak menyebut sumber", () => {
    const html = render({ forecast_qty_kg: 10, method: "statistical_fallback", confidence: 1 });

    expect(html).not.toContain("sumber tidak dilaporkan");
    expect(html).toContain('data-source="unknown"');
    expect(html).toContain("10");
  });
});
