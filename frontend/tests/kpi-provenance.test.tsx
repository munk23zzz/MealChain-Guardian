// @vitest-environment jsdom
//
// Fase 8 — provenance KPI. Yang dipaku di sini adalah ATURAN yang membuat angka
// kartu bisa dipertanggungjawabkan, bukan bentuk markupnya:
//
// - angka proyeksi selalu berawalan "estimasi" (tidak pernah terbaca sebagai
//   hasil lapangan);
// - baseline yang tidak ada ditulis "tanpa baseline — <alasan>", TIDAK PERNAH
//   "0" atau target karangan (`Number(null) is 0` adalah cacat yang dijaga di
//   sini: nilai kosong harus tetap kosong);
// - mode data dibaca dari `data_mode` backend, dan kartu simulasi berada di grup
//   berlabel simulasi + catatan yang menyebutnya;
// - pemilih cakupan bisa diklik dan tahu kapan simulasi tidak bisa dipilih
//   (tanpa sesi demo aktif);
// - kartu dengan provenance lengkap menampilkan SEMUA label yang dijanjikan
//   (tingkat bukti, sumber, basis periode, metode, pembanding, definisi, rumus).
import { act } from "react";
import type { Root } from "react-dom/client";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import KPIDashboard, { KpiScopeToggle } from "../components/KPIDashboard";
import { queryKeys } from "../lib/query";
import {
  baselineText,
  estimateLine,
  evidenceLabel,
  scopeLabel,
} from "../lib/kpi-provenance";

/* ------------------------------------------------------------------ fixture */

/** Provenance LENGKAP: semua field yang dijanjikan kontrak ada. */
const PROV_LENGKAP = {
  evidence_kind: "recorded_fact",
  source: "safe_delivered_cost.cost_idr",
  period: {
    start: "2026-10-07T17:00:00+07:00",
    end: "2026-10-08T17:00:00+07:00",
    basis: "recorded_at",
  },
  method_version: "sdc-v2",
  baseline: { kind: "no_baseline", value: null, reason: "target belum disepakati pemilik" },
  definition: "Biaya per porsi aman sampai titik konsumsi.",
  formula: "sum(cost_idr) / sum(portions_safe)",
};

const METRIK_ESTIMASI = {
  name: "Safe Delivered Cost",
  unit: "IDR",
  state: "available",
  value: "15496548.14",
  reason: null,
  sample_count: 12,
  coverage: "1.00",
  previous_value: null,
  trend: null,
  provenance: PROV_LENGKAP,
  estimate: {
    state: "available",
    value: "16250000",
    unit: "IDR",
    definition: "proyeksi biaya kirim pekan depan",
    coverage: "12 kiriman",
  },
};

const METRIK_ESTIMASI_KOSONG = {
  name: "Procurement Price Deviation",
  unit: "percent",
  state: "no_data",
  value: null,
  reason: "tidak ada kutipan harga pada periode ini",
  sample_count: 0,
  coverage: null,
  previous_value: null,
  trend: null,
  provenance: {
    ...PROV_LENGKAP,
    evidence_kind: "simulated_estimate",
    source: "price_quotes.unit_price_idr",
  },
  estimate: {
    state: "no_data",
    value: null,
    unit: "percent",
    reason: "belum ada kutipan pembanding",
  },
};

/** Tanpa blok `estimate` sama sekali → kartu tidak boleh mengarang baris. */
const METRIK_TANPA_ESTIMASI = {
  name: "Decision Time",
  unit: "minutes",
  state: "available",
  value: "120.00",
  reason: null,
  sample_count: 4,
  coverage: "0.50",
  previous_value: null,
  trend: null,
  provenance: PROV_LENGKAP,
};

const METRIK_TANPA_PROV = {
  name: "Avoidable Food Loss",
  unit: "kg",
  state: "unavailable",
  value: null,
  reason: "disposal event tidak tersedia di schema",
  sample_count: 0,
  coverage: null,
  previous_value: null,
  trend: null,
};

function envelope(dataMode: "demo" | "operational") {
  return {
    period: {
      start: "2026-10-07T17:00:00+07:00",
      end: "2026-10-08T17:00:00+07:00",
    },
    scope: { location_id: "loc-1", role: "sppg_head" },
    data_mode: dataMode,
    computed_at: "2026-10-08T17:00:00+07:00",
    metrics: [METRIK_ESTIMASI, METRIK_ESTIMASI_KOSONG, METRIK_TANPA_ESTIMASI, METRIK_TANPA_PROV],
  };
}

/* ------------------------------------------------------------- jsdom helper */

let root: Root | null = null;
let host: HTMLDivElement | null = null;

function mount(node: React.ReactElement) {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  act(() => {
    root!.render(node);
  });
  return host;
}

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
  root = null;
  host = null;
  vi.unstubAllGlobals();
});

function kartu(dom: HTMLElement, name: string): HTMLElement {
  const found = Array.from(dom.querySelectorAll<HTMLElement>("article.kpi-card")).find(
    (a) => a.querySelector(".kpi-card-name")?.getAttribute("title") === name,
  );
  if (!found) throw new Error(`kartu ${name} tidak dirender`);
  return found;
}

/* --------------------------------------------------------------- (a) unit  */

describe("kpi-provenance — label bukti", () => {
  it("menerjemahkan simulated_estimate menjadi 'estimasi simulasi'", () => {
    expect(evidenceLabel("simulated_estimate")).toBe("estimasi simulasi");
    expect(evidenceLabel("recorded_fact")).toBe("fakta tercatat");
  });

  it("label tak dikenal dikembalikan apa adanya (tidak dikarang)", () => {
    expect(evidenceLabel("sensor_calibrated")).toBe("sensor_calibrated");
    expect(evidenceLabel(null)).not.toBe("estimasi simulasi");
  });
});

describe("kpi-provenance — baseline", () => {
  it("no_baseline ditulis 'tanpa baseline' + alasan, dan TIDAK mengandung 0", () => {
    const teks = baselineText({
      kind: "no_baseline",
      value: null,
      reason: "target belum disepakati pemilik",
    });
    expect(teks).toContain("tanpa baseline");
    expect(teks).toContain("target belum disepakati pemilik");
    // Inti pitfall `Number(null) is 0`: baseline kosong tidak boleh jadi angka.
    expect(teks).not.toContain("0");
  });

  it("baseline yang benar-benar ada ditulis sebagai nilainya", () => {
    expect(baselineText({ kind: "value", value: "85", reason: null })).toBe(
      "baseline 85",
    );
  });
});

describe("kpi-provenance — baris estimasi", () => {
  it("state available berawalan 'estimasi' (tidak pernah terbaca hasil lapangan)", () => {
    const teks = estimateLine({
      estimate: { state: "available", value: "12.5", unit: "kg" },
    })!;
    expect(teks.startsWith("estimasi")).toBe(true);
    expect(teks).toContain("12,5");
    expect(teks).toContain("kg");
  });

  it("state no_data berbunyi 'estimasi tidak tersedia'", () => {
    const teks = estimateLine({
      estimate: { state: "no_data", value: null, reason: "belum ada kutipan" },
    })!;
    expect(teks).toContain("estimasi tidak tersedia");
    expect(teks).toContain("belum ada kutipan");
  });

  it("nilai null dengan state available TIDAK menjadi 'estimasi 0'", () => {
    const teks = estimateLine({ estimate: { state: "available", value: null } })!;
    expect(teks).toContain("estimasi tidak tersedia");
    expect(teks).not.toMatch(/estimasi 0\b/);
  });

  it("metrik tanpa blok estimate tidak menghasilkan baris", () => {
    expect(estimateLine({ name: "Decision Time" })).toBeNull();
  });
});

describe("kpi-provenance — label cakupan", () => {
  it("dibaca dari data_mode, bukan ditebak", () => {
    expect(scopeLabel("demo")).toBe("Simulasi (sesi demo)");
    expect(scopeLabel("operational")).toBe("Hasil operasional");
    expect(scopeLabel(undefined)).toBe("Cakupan tidak disebutkan");
  });
});

/* ------------------------------------------------- (b) render mode simulasi */

describe("KPIDashboard — mode demo", () => {
  it("grup berlabel simulasi tampil beserta catatan demo", () => {
    const dom = mount(<KPIDashboard kpi={envelope("demo")} />);
    const grup = dom.querySelector<HTMLElement>("section.kpi-group");
    expect(grup).not.toBeNull();
    expect(grup!.getAttribute("data-mode")).toBe("demo");
    expect(grup!.querySelector(".kpi-group-title")?.textContent).toBe(
      "Simulasi (sesi demo)",
    );
    expect(dom.querySelector('[data-testid="kpi-demo-note"]')).not.toBeNull();
  });

  it("kartu yang punya estimate merender baris 'estimasi'", () => {
    const dom = mount(<KPIDashboard kpi={envelope("demo")} />);
    const est = kartu(dom, "Safe Delivered Cost").querySelector(
      '[data-testid="kpi-estimate"]',
    );
    expect(est).not.toBeNull();
    expect(est!.textContent).toContain("estimasi");
    expect(est!.textContent).toContain("proyeksi biaya kirim pekan depan");
  });

  it("estimate tak tersedia tetap muncul sebagai estimasi tidak tersedia", () => {
    const dom = mount(<KPIDashboard kpi={envelope("demo")} />);
    const est = kartu(dom, "Procurement Price Deviation").querySelector(
      '[data-testid="kpi-estimate"]',
    );
    expect(est!.textContent).toContain("estimasi tidak tersedia");
  });

  it("kartu tanpa estimate tidak merender baris estimasi apa pun", () => {
    const dom = mount(<KPIDashboard kpi={envelope("demo")} />);
    expect(
      kartu(dom, "Decision Time").querySelector('[data-testid="kpi-estimate"]'),
    ).toBeNull();
    expect(
      kartu(dom, "Avoidable Food Loss").querySelector('[data-testid="kpi-estimate"]'),
    ).toBeNull();
  });

  it("amplop menampilkan mode data yang dikirim backend", () => {
    const dom = mount(<KPIDashboard kpi={envelope("demo")} />);
    expect(dom.querySelector('[data-testid="kpi-data-mode"]')?.textContent).toBe(
      "Simulasi (sesi demo)",
    );
  });
});

/* -------------------------------------------------- (c) render operational  */

describe("KPIDashboard — mode operasional", () => {
  it("tanpa catatan demo dan berlabel Hasil operasional", () => {
    const dom = mount(<KPIDashboard kpi={envelope("operational")} />);
    expect(dom.querySelector('[data-testid="kpi-demo-note"]')).toBeNull();
    const grup = dom.querySelector<HTMLElement>("section.kpi-group")!;
    expect(grup.getAttribute("data-mode")).toBe("operational");
    expect(grup.querySelector(".kpi-group-title")?.textContent).toBe(
      "Hasil operasional",
    );
  });

  it("pil cakupan role di header (data-testid=kpi-scope) tetap ada", () => {
    const dom = mount(<KPIDashboard kpi={envelope("operational")} />);
    expect(dom.querySelector('[data-testid="kpi-scope"]')).not.toBeNull();
  });
});

/* ---------------------------------------------- (d) pemilih cakupan (klik)  */

describe("KpiScopeToggle", () => {
  it("menandai cakupan aktif dan mengirim pilihan saat diklik", () => {
    const onScopeChange = vi.fn();
    const dom = mount(
      <KpiScopeToggle scope="operational" onScopeChange={onScopeChange} />,
    );
    const operasional = dom.querySelector<HTMLButtonElement>(
      '[data-scope-option="operational"]',
    )!;
    const demo = dom.querySelector<HTMLButtonElement>('[data-scope-option="demo"]')!;

    expect(operasional.getAttribute("aria-pressed")).toBe("true");
    expect(demo.getAttribute("aria-pressed")).toBe("false");

    act(() => demo.click());
    expect(onScopeChange).toHaveBeenCalledWith("demo");
  });

  it("tanpa sesi demo: tombol simulasi dimatikan dan alasannya terbaca", () => {
    const onScopeChange = vi.fn();
    const alasan = "Simulasi butuh sesi demo aktif — jalankan sesi dulu.";
    const dom = mount(
      <KpiScopeToggle
        scope="operational"
        onScopeChange={onScopeChange}
        disabled
        disabledReason={alasan}
      />,
    );
    const demo = dom.querySelector<HTMLButtonElement>('[data-scope-option="demo"]')!;

    expect(demo.disabled).toBe(true);
    // Tombol nonaktif tidak boleh mengirim pilihan.
    act(() => demo.click());
    expect(onScopeChange).not.toHaveBeenCalled();

    const penjelas = dom.querySelector("#kpi-scope-explanation")!;
    expect(penjelas.textContent).toContain(alasan);
    // aria-describedby harus menunjuk teks yang benar-benar ada.
    expect(
      dom.querySelector('[data-testid="kpi-scope-toggle"]')?.getAttribute(
        "aria-describedby",
      ),
    ).toBe("kpi-scope-explanation");
  });

  it("KPIDashboard meneruskan alasan itu ke pil cakupan", () => {
    const dom = mount(
      <KPIDashboard
        kpi={envelope("operational")}
        scope="operational"
        scopeDisabledReason="belum ada sesi demo aktif"
      />,
    );
    const demo = dom.querySelector<HTMLButtonElement>('[data-scope-option="demo"]')!;
    expect(demo.disabled).toBe(true);
    expect(dom.querySelector("#kpi-scope-explanation")?.textContent).toContain(
      "belum ada sesi demo aktif",
    );
  });
});

/* ------------------------------------------------ (e) regresi provenance    */

describe("KPIDashboard — provenance lengkap (regresi)", () => {
  it("semua label provenance tampil di kartu", () => {
    const dom = mount(<KPIDashboard kpi={envelope("demo")} />);
    const prov = kartu(dom, "Safe Delivered Cost").querySelector(
      '[data-testid="kpi-provenance"]',
    );
    expect(prov).not.toBeNull();
    const teks = prov!.textContent ?? "";
    for (const label of [
      "Tingkat bukti",
      "Sumber",
      "Basis periode",
      "Metode",
      "Pembanding",
      "Definisi",
      "Rumus",
    ]) {
      expect(teks).toContain(label);
    }
    // Nilainya ikut, bukan hanya labelnya.
    expect(teks).toContain("safe_delivered_cost.cost_idr");
    expect(teks).toContain("recorded_at");
    expect(teks).toContain("sdc-v2");
    // Baseline kosong = "tanpa baseline" + alasan, bukan 0.
    expect(teks).toContain("tanpa baseline");
    expect(teks).toContain("target belum disepakati pemilik");
  });

  it("metrik tanpa provenance tidak merender blok provenance", () => {
    const dom = mount(<KPIDashboard kpi={envelope("demo")} />);
    expect(
      kartu(dom, "Avoidable Food Loss").querySelector(
        '[data-testid="kpi-provenance"]',
      ),
    ).toBeNull();
  });

  it("tingkat bukti ditulis di luar <details> supaya terbaca tanpa klik", () => {
    const dom = mount(<KPIDashboard kpi={envelope("demo")} />);
    const kartuEstimasi = kartu(dom, "Procurement Price Deviation");
    const ringkas = kartuEstimasi.querySelector(".kpi-prov-evidence");
    expect(ringkas?.textContent).toContain("estimasi simulasi");
    expect(ringkas?.closest("details")).toBeNull();
  });

  it("markup statis tetap memuat grup dan provenance (SSR)", () => {
    const html = renderToStaticMarkup(
      <KPIDashboard kpi={envelope("demo")} scope="demo" />,
    );
    expect(html).toContain("kpi-group");
    expect(html).toContain("Simulasi (sesi demo)");
    expect(html).toContain("kpi-demo-note");
    expect(html).toContain("Tingkat bukti");
  });
});

/* ------------------------------------------------- kunci cache antar-sesi
 *
 * Dua sesi demo berbagi `mode` yang sama ("demo"). Kalau id sesinya tidak ikut
 * kunci cache, panel bisa menyajikan angka sesi A sebagai jawaban untuk sesi B
 * sampai polling berikutnya — angka milik sesi lain di bawah label sesi ini,
 * persis cacat yang ditutup cakupan eksplisit di backend.
 */
describe("kunci cache KPI memisahkan sesi demo", () => {
  it("dua sesi demo berbeda menghasilkan kunci berbeda", () => {
    expect(queryKeys.kpiLive("loc", "today", "demo", "sesi-a")).not.toEqual(
      queryKeys.kpiLive("loc", "today", "demo", "sesi-b")
    );
  });

  it("cakupan operasional tidak membawa id sesi", () => {
    expect(queryKeys.kpiLive("loc", "today", "operational", "sesi-a")).toEqual(
      queryKeys.kpiLive("loc", "today", "operational", null)
    );
  });
});
