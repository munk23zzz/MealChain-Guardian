// S4-01 UI — panel Event 2 (price anomaly) di OpsConsole.
// Kontrak plan :421: approver pilih quote → run event API; monitor hanya
// read feed. Wording review, bukan tuduhan fraud. Semua angka dari backend.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import OpsConsole from "../components/OpsConsole";

const QUOTES = {
  location: "Jakarta",
  commodity: "telur",
  quotes: [
    {
      id: "q-anomali",
      supplier_id: "s1",
      supplier_name: "Supplier Jakarta-1",
      price_per_kg: 38100,
      recorded_at: "2026-10-08T01:00:00+00:00",
    },
    {
      id: "q-normal",
      supplier_id: "s2",
      supplier_name: "Supplier Jakarta-2",
      price_per_kg: 30200,
      recorded_at: "2026-10-08T01:05:00+00:00",
    },
  ],
  reference: {
    id: "ref-1",
    price_per_kg: 30200,
    recorded_at: "2026-10-08T00:30:00+00:00",
  },
};

const RESULT_ANOMALI = {
  status: "anomaly",
  decision_id: "d-123",
  event_type: "price_anomaly",
  deviation_pct: "26.16",
  classification: "anomalous",
  quote_id: "q-anomali",
  reference_id: "ref-1",
  message: "Procurement price deviation detected — review required",
};

const RESULT_NORMAL = {
  status: "no_anomaly",
  decision_id: null,
  deviation_pct: "0.00",
  classification: "normal",
  message: "Harga dalam batas normal — tidak perlu tindakan",
};

describe("OpsConsole — Event 2 price anomaly", () => {
  it("approver melihat panel Event 2 dengan pilihan quote dari backend", () => {
    const html = renderToStaticMarkup(
      <OpsConsole
        role="sppg_head"
        token="t"
        priceQuotes={QUOTES}
        event2={null}
      />
    );
    expect(html).toContain("event2-panel");
    expect(html).toContain("Supplier Jakarta-1");
    expect(html).toContain("Supplier Jakarta-2");
    expect(html).toContain("Rp38.100");
    // Reference tampil (bukti pembanding, bukan angka karangan)
    expect(html).toContain("30.200");
  });

  it("monitor read-only: panel Event 2 tanpa tombol jalankan", () => {
    const html = renderToStaticMarkup(
      <OpsConsole
        role="bgn_monitor"
        token="t"
        priceQuotes={QUOTES}
        event2={null}
      />
    );
    expect(html).toContain("event2-panel");
    expect(html).not.toContain("event2-run");
  });

  it("hasil anomali: review-required wording, deviation, decision link, TANPA tuduhan fraud", () => {
    const html = renderToStaticMarkup(
      <OpsConsole
        role="sppg_head"
        token="t"
        priceQuotes={QUOTES}
        event2={RESULT_ANOMALI}
      />
    );
    expect(html).toContain("review required");
    expect(html).toContain("26,16%"); // format id-ID
    expect(html).toContain("Masuk review queue");
    // Tidak ada kata tuduhan.
    const lower = html.toLowerCase();
    expect(lower).not.toContain("fraud");
    expect(lower).not.toContain("curang");
    expect(lower).not.toContain("janggal");
  });

  it("hasil no-anomaly: tampil 200-style message tanpa decision", () => {
    const html = renderToStaticMarkup(
      <OpsConsole
        role="sppg_head"
        token="t"
        priceQuotes={QUOTES}
        event2={RESULT_NORMAL}
      />
    );
    expect(html).toContain("batas normal");
    expect(html).not.toContain("Masuk review queue");
  });
});
