// Satu tempat menerjemahkan blok biaya backend ke tampilan Fase 9.
//
// Aturan yang dijaga di sini:
//   1. PO/invoice = bahan + transportasi + handling. Penalti risiko TIDAK ikut.
//   2. SDC = invoice + expected loss + risiko kesegaran + penalti keamanan.
//   3. `null` (payload tidak ada) berarti "tidak berlaku" — bukan Rp 0.
//      Field kosong di dalam payload berarti "tidak tercatat".
//   4. Tidak ada perhitungan biaya di browser; semua angka sudah dari server.

export type RiskMethodKind =
  | "simulated_policy"
  | "calibrated_model"
  | "unavailable";

export type CommercialCostPayload = {
  purchase_total: string;
  transport_total: string;
  handling_total: string;
  invoice_total: string;
  invoice_unit_price: string;
  expected_loss?: string | null;
  freshness_risk?: string | null;
  safety_penalty?: string | null;
  sdc_total: string | null;
  sdc_unit_price: string | null;
  risk_method: {
    kind: string;
    source: string;
    version: string;
    period?: string | null;
    baseline?: string | null;
  };
};

export type CostRow = { label: string; value: string; note?: string };

export type CostBlock = {
  key: "po" | "sdc";
  title: string;
  caption: string;
  rows: CostRow[];
};

export type CostStatus = "tersedia" | "tidak_tercatat" | "tidak_berlaku";

export type RiskMethodView = {
  kind: RiskMethodKind;
  label: string;
  source: string;
  version: string;
  period: string | null;
  baseline: string | null;
};

export type CostView = {
  status: CostStatus;
  blocks: CostBlock[];
  riskMethod: RiskMethodView;
  message?: string;
};

const TIDAK_TERCATAT = "tidak tercatat";

export function labelRiskMethod(kind: string): string {
  switch (kind) {
    case "simulated_policy":
      return "Kebijakan simulasi";
    case "calibrated_model":
      return "Model terkalibrasi";
    default:
      return "Tidak tersedia";
  }
}

/** Format rupiah dari string desimal server. Tidak menghitung ulang biaya. */
export function formatRupiah(
  value: string | number | null | undefined
): string {
  if (value === null || value === undefined || value === "") {
    return TIDAK_TERCATAT;
  }
  const angka = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(angka)) return TIDAK_TERCATAT;
  const adaPecahan = Math.abs(angka - Math.round(angka)) > 1e-9;
  const formatter = new Intl.NumberFormat("id-ID", {
    minimumFractionDigits: adaPecahan ? 2 : 0,
    maximumFractionDigits: 2,
  });
  return `Rp ${formatter.format(angka)}`;
}

function _riskView(
  mentah: CommercialCostPayload["risk_method"] | null | undefined
): RiskMethodView {
  const kind: RiskMethodKind =
    mentah?.kind === "simulated_policy" || mentah?.kind === "calibrated_model"
      ? mentah.kind
      : "unavailable";
  return {
    kind,
    label: labelRiskMethod(kind),
    source: mentah?.source?.trim() || TIDAK_TERCATAT,
    version: mentah?.version?.trim() || TIDAK_TERCATAT,
    period: mentah?.period?.trim() || null,
    baseline: mentah?.baseline?.trim() || null,
  };
}

export type MarketReference = {
  source: string;
  price_per_kg: number | string;
  recorded_at?: string | null;
};

export function buildCostView(
  payload: CommercialCostPayload | null | undefined,
  market?: MarketReference | null
): CostView {
  if (!payload) {
    return {
      status: "tidak_berlaku",
      blocks: [],
      riskMethod: _riskView(null),
      message: "Biaya tidak berlaku untuk keputusan ini",
    };
  }

  // Referensi pasar adalah pembanding HARGA BAHAN (PIHPS), bukan komponen PO.
  // Tidak ada acuan → "tidak tercatat"; Rp 0 akan terbaca sebagai acuan gratis.
  const acuanPasar =
    market && Number.isFinite(Number(market.price_per_kg))
      ? {
          label: "Referensi pasar",
          value: `${formatRupiah(market.price_per_kg)} per kg`,
          note: "harga acuan PIHPS — pembanding bahan, bukan biaya PO",
        }
      : {
          label: "Referensi pasar",
          value: TIDAK_TERCATAT,
          note: "tidak ada acuan PIHPS untuk lokasi + komoditas ini",
        };

  const po: CostBlock = {
    key: "po",
    title: "Biaya PO",
    caption: "Yang ditagihkan: bahan, transportasi, dan handling.",
    rows: [
      { label: "Bahan", value: formatRupiah(payload.purchase_total) },
      { label: "Transportasi", value: formatRupiah(payload.transport_total) },
      { label: "Handling", value: formatRupiah(payload.handling_total) },
      acuanPasar,
      {
        label: "Harga satuan PO",
        value: formatRupiah(payload.invoice_unit_price),
        note: "per kg",
      },
      { label: "Total PO", value: formatRupiah(payload.invoice_total) },
    ],
  };

  const sdc: CostBlock = {
    key: "sdc",
    title: "SDC analitis",
    caption:
      "Penalti risiko internal untuk membandingkan pilihan. Tidak ditagihkan ke pemasok.",
    rows: [
      {
        label: "Expected loss",
        value: formatRupiah(payload.expected_loss ?? null),
      },
      {
        label: "Risiko kesegaran",
        value: formatRupiah(payload.freshness_risk ?? null),
      },
      {
        label: "Penalti keamanan",
        value: formatRupiah(payload.safety_penalty ?? null),
      },
      {
        label: "Total SDC",
        value:
          payload.sdc_total === null
            ? TIDAK_TERCATAT
            : formatRupiah(payload.sdc_total),
        note:
          payload.sdc_unit_price === null
            ? undefined
            : `${formatRupiah(payload.sdc_unit_price)} per kg`,
      },
    ],
  };

  return {
    status: payload.sdc_total === null ? "tidak_tercatat" : "tersedia",
    blocks: [po, sdc],
    riskMethod: _riskView(payload.risk_method),
    message:
      payload.sdc_total === null
        ? "Komponen penalti risiko tidak tercatat untuk keputusan ini"
        : undefined,
  };
}

/**
 * Tempelkan blok biaya dari DETAIL ke baris DAFTAR keputusan.
 *
 * Kenapa perlu: `GET /decisions` (daftar) tidak memuat `commercial_cost`;
 * payload biaya hanya ada di `GET /decisions/{id}`. Halaman Decision & Evidence
 * memberi komponen baris daftar, sehingga sebelum ini blok biaya selalu
 * "tidak berlaku" di browser walaupun server mengirim angkanya.
 *
 * Aturan (dikunci `tests/decision-detail-cost.test.ts`):
 *  - `detail` null (gagal dibaca) → baris dikembalikan APA ADANYA; kegagalan
 *    sudah dilaporkan terpisah, jangan berubah jadi klaim "tidak berlaku";
 *  - kunci tidak ada di detail (backend lama) → nilai baris dipertahankan;
 *  - `commercial_cost: null` dari server → tetap null: keputusan administratif
 *    memang tidak punya transfer, dan UI menulis "tidak berlaku".
 */
export type WithCost<T> = T & {
  commercial_cost?: CommercialCostPayload | null;
  market_reference?: MarketReference | null;
};

export function withDetailCost<T extends object>(
  baris: T | null,
  detail: Record<string, unknown> | null,
): WithCost<T> | null {
  if (!baris || !detail) return baris;
  const hasil = { ...baris } as WithCost<T>;
  if ("commercial_cost" in detail) {
    hasil.commercial_cost = (detail.commercial_cost ?? null) as CommercialCostPayload | null;
  }
  if ("market_reference" in detail) {
    hasil.market_reference = (detail.market_reference ?? null) as MarketReference | null;
  }
  return hasil;
}
