// Tile "Pengadaan & eksekusi" di Overview (laporan pemilik 27 Okt 2026).
//
// Diukur pada basis data demo: satu siklus approve+execute mengubah
// decisions.status → executed, menerbitkan satu baris sap_mock_purchase_orders
// (Rp 9.750.000), menulis satu jejak agent_traces step ACT, dan menambah tiga
// blok ledger — tetapi TIDAK mengubah stok (stok baru bertambah saat penerimaan
// disetujui). Tiga kartu Overview lama hanya membaca pasokan/kebutuhan, jadi
// eksekusi tidak terlihat. Kontrak yang dipaku di sini:
//
//  1. angka berasal dari data (count/nilai), bukan karangan;
//  2. satuan dan rentang waktu ditulis eksplisit ("PO", "hari ini (WIB)");
//  3. keadaan "belum tahu" (memuat/galat) ditulis "—", keadaan "memang kosong"
//     ditulis "belum ada" — tidak pernah "0" palsu;
//  4. nilai komitmen memakai angka server apa adanya (Rp, tanpa pembulatan liar).
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import ProcurementToday from "../components/ProcurementToday";
import {
  procurementTiles,
  rentangLabel,
  type ProcurementSummary,
} from "../lib/procurement-today";

const SUMMARY: ProcurementSummary = {
  period: {
    key: "today",
    label: "Hari ini",
    timezone: "Asia/Jakarta",
    start: "2026-10-26T17:00:00+00:00",
    end: "2026-10-27T08:30:00+00:00",
  },
  scope: { location_id: "loc-1", role: "sppg_head" },
  purchase_orders: {
    state: "available",
    count: 2,
    total_value: "19500000.00",
    currency: "IDR",
    by_status: { draft: 0, submitted: 2, confirmed: 0 },
    last: {
      po_number: "MC-3E2E3CC7F53E",
      status: "submitted",
      created_at: "2026-10-27T08:30:51.308507+00:00",
      value: "9750000.00",
    },
  },
  decisions_executed: {
    state: "available",
    count: 2,
    last_step_at: "2026-10-27T08:30:51.320000+00:00",
  },
  batches_dispatched: {
    state: "available",
    count: 1,
    last_dispatched_at: "2026-10-27T08:30:51.330000+00:00",
  },
  receipts: {
    state: "available",
    count: 3,
    kg: "425.50",
    unit: "kg",
    last: { kg: "125.50", reviewed_at: "2026-10-27T08:30:51.340000+00:00" },
  },
};

describe("procurementTiles — kejujuran angka", () => {
  it("memuat → semua nilai '—', bukan 0", () => {
    const tiles = procurementTiles(null, { loading: true });
    expect(tiles).toHaveLength(4);
    for (const tile of tiles) {
      expect(tile.value).toBe("—");
      expect(tile.foot.toLowerCase()).toContain("memuat");
    }
  });

  it("galat → '—' dan alasannya disebut", () => {
    const tiles = procurementTiles(null, { error: "HTTP 500" });
    for (const tile of tiles) {
      expect(tile.value).toBe("—");
      expect(tile.foot.toLowerCase()).toContain("gagal");
    }
  });

  it("periode kosong → 'belum ada', bukan '0'", () => {
    const kosong: ProcurementSummary = {
      ...SUMMARY,
      purchase_orders: {
        ...SUMMARY.purchase_orders,
        count: 0,
        total_value: "0.00",
        last: null,
      },
      decisions_executed: { state: "available", count: 0, last_step_at: null },
      batches_dispatched: { state: "available", count: 0, last_dispatched_at: null },
      receipts: { state: "available", count: 0, kg: "0.00", unit: "kg", last: null },
    };
    const tiles = procurementTiles(kosong);
    for (const tile of tiles) expect(tile.value).toBe("belum ada");
    expect(tiles[0].foot).toContain("tidak ada PO");
  });

  it("angka + satuan + rentang waktu ditulis eksplisit", () => {
    const [po, eksekusi, truk, terima] = procurementTiles(SUMMARY);
    expect(po.value).toBe("2");
    expect(po.unit).toBe("PO");
    expect(po.label).toContain("PO terbit");
    expect(po.label).toContain("hari ini (WIB)");
    expect(po.foot).toContain("Rp19.500.000");
    expect(po.mini).toContain("MC-3E2E3CC7F53E");

    expect(eksekusi.value).toBe("2");
    expect(eksekusi.unit).toBe("keputusan");
    expect(eksekusi.label).toContain("hari ini (WIB)");

    expect(truk.value).toBe("1");
    expect(truk.unit).toBe("batch");
    expect(truk.label).toContain("Truk berangkat");

    // Kg diterima: satu-satunya angka yang bergerak setelah penerimaan disetujui.
    expect(terima.value).toBe("425,5");
    expect(terima.unit).toBe("kg");
    expect(terima.label).toContain("Kg diterima");
    expect(terima.label).toContain("hari ini (WIB)");
    expect(terima.foot).toContain("3 penerimaan disetujui");
    expect(terima.mini).toContain("125,5 kg");
  });

  it("jendela lain memakai label jendelanya, bukan 'hari ini'", () => {
    const tujuh: ProcurementSummary = {
      ...SUMMARY,
      period: { ...SUMMARY.period, key: "7d", label: "7 hari" },
    };
    expect(rentangLabel("7d")).toBe("7 hari (WIB)");
    expect(procurementTiles(tujuh)[0].label).toContain("7 hari (WIB)");
    expect(procurementTiles(tujuh)[0].label).not.toContain("hari ini");
  });
});

describe("ProcurementToday — yang benar-benar tertulis di layar", () => {
  it("merender angka, satuan, dan sumbernya", () => {
    const html = renderToStaticMarkup(
      <ProcurementToday data={SUMMARY} loading={false} error={null} />
    );
    expect(html).toContain("PO terbit");
    expect(html).toContain(">2<");
    expect(html).toContain("Rp19.500.000");
    expect(html).toContain("hari ini (WIB)");
    expect(html).toContain("Truk berangkat");
    expect(html).toContain("Kg diterima");
    expect(html).toContain("425,5");
  });

  it("tanpa data menulis '—' dan tidak mengaku nol", () => {
    const html = renderToStaticMarkup(
      <ProcurementToday data={null} loading={false} error={null} />
    );
    expect(html).toContain("—");
    expect(html).not.toContain(">0<");
  });

  it("satu kalimat per kartu — detail baris kedua menempel sebagai tooltip", () => {
    // Permintaan pemilik 29 Okt 2026: rel "1. PO terbit … 4. Kg diterima"
    // dipendekkan, cukup kalimat baris pertama yang tampak.
    const html = renderToStaticMarkup(
      <ProcurementToday data={SUMMARY} loading={false} error={null} />
    );
    expect(html).not.toContain("kpi-card-mini");
    // Informasi baris kedua tidak hilang: ia jadi title pada kalimat pertama.
    const foot = html.match(/class="kpi-card-foot" title="([^"]+)"/);
    expect(foot?.[1]).toContain("·");
    expect((foot?.[1] ?? "").length).toBeGreaterThan(20);
  });

  it("menyebut periode dan zona waktunya", () => {
    const html = renderToStaticMarkup(
      <ProcurementToday data={SUMMARY} loading={false} error={null} />
    );
    expect(html).toContain("Pengadaan");
    expect(html).toContain("WIB");
  });
});
