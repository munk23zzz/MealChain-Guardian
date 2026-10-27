/**
 * Provenance KPI (Fase 8 MG, 27 Okt 2026) — satu tempat untuk menerjemahkan
 * `provenance`/`estimate` dari `GET /kpi` menjadi kalimat yang bisa dibaca.
 *
 * Kenapa dipisah dari komponen: aturan yang dijaga di sini ("angka ini fakta
 * tercatat atau estimasi?", "baseline-nya ada atau tidak?", "cakupannya data
 * operasional atau sesi demo?") adalah aturan yang harus diuji tanpa DOM. Kalau
 * ia ditulis inline di JSX, satu-satunya cara mengujinya adalah merender kartu.
 *
 * Aturan yang TIDAK boleh dilanggar di sini:
 * - Angka estimasi selalu membawa kata "estimasi"/"proyeksi"; ia tidak pernah
 *   ditampilkan seolah hasil lapangan.
 * - Baseline yang tidak ada ditulis "tanpa baseline" + alasannya dari server.
 *   Jangan mengarang 0 atau target.
 * - Mode data ditampilkan apa adanya (`data_mode` dari backend). Tidak ada
 *   tebakan dari isi angka.
 */

export type KpiEvidenceKind =
  | "recorded_fact"
  | "derived"
  | "simulated_estimate"
  | string;

/** Label bukti untuk layar. Kunci = nilai `evidence_kind` dari backend. */
export const EVIDENCE_LABEL: Record<string, string> = {
  recorded_fact: "fakta tercatat",
  derived: "turunan dari fakta",
  simulated_estimate: "estimasi simulasi",
};

export function evidenceLabel(kind: unknown): string {
  const k = String(kind ?? "").trim();
  if (!k) return "bukti tidak disebutkan";
  return EVIDENCE_LABEL[k] ?? k;
}

export function isEstimate(kind: unknown): boolean {
  return String(kind ?? "").trim() === "simulated_estimate";
}

/* ---------------------------------------------------------------- cakupan */

export type KpiScope = "operational" | "demo";

export const KPI_SCOPES: readonly { key: KpiScope; label: string; hint: string }[] = [
  {
    key: "operational",
    label: "Operasional",
    hint: "Hanya fakta kerja: baris yang bukan milik sesi demo.",
  },
  {
    key: "demo",
    label: "Simulasi (demo)",
    hint: "Hanya fakta sesi demo yang sedang aktif. Angka di sini simulasi, bukan hasil lapangan.",
  },
];

/** Label grup kartu — dibaca dari `data_mode` backend, bukan ditebak. */
export function scopeLabel(mode: unknown): string {
  const m = String(mode ?? "").trim();
  if (m === "demo") return "Simulasi (sesi demo)";
  if (m === "operational") return "Hasil operasional";
  return "Cakupan tidak disebutkan";
}

/** Kalimat penjelas perbedaan dua cakupan — dipakai tooltip toggle. */
export const SCOPE_EXPLANATION =
  "Operasional menghitung fakta kerja (tanpa baris sesi demo). " +
  "Simulasi menghitung satu sesi demo yang sedang aktif, sehingga angkanya " +
  "bukan hasil lapangan dan tidak boleh dibandingkan dengan angka operasional.";

/* --------------------------------------------------------------- baseline */

export type KpiBaseline = {
  kind: "value" | "no_baseline" | string;
  value: string | null;
  reason: string | null;
};

export function baselineOf(metric: any): KpiBaseline | null {
  const b = metric?.provenance?.baseline;
  if (!b || typeof b !== "object") return null;
  return {
    kind: String(b.kind ?? ""),
    value: b.value === undefined || b.value === null ? null : String(b.value),
    reason: b.reason ? String(b.reason) : null,
  };
}

/** "tanpa baseline — <alasan>" atau "baseline <nilai>". */
export function baselineText(baseline: KpiBaseline | null): string {
  if (!baseline) return "tanpa baseline — provenance belum menyebutkannya";
  if (baseline.kind === "value" && baseline.value !== null) {
    return `baseline ${baseline.value}`;
  }
  return `tanpa baseline — ${baseline.reason ?? "tanpa alasan"}`;
}

/* ------------------------------------------------------------- provenance */

export type ProvLine = { key: string; label: string; value: string };

/**
 * Baris provenance untuk satu kartu. Urutannya tetap supaya dua kartu bisa
 * dibandingkan baris per baris. Nilai yang tidak dikirim server dilewati —
 * lebih baik tidak ada baris daripada baris berisi "undefined".
 */
export function provenanceLines(metric: any): ProvLine[] {
  const p = metric?.provenance;
  if (!p || typeof p !== "object") return [];
  const lines: ProvLine[] = [];
  const push = (key: string, label: string, value: unknown) => {
    const v = value === undefined || value === null ? "" : String(value).trim();
    if (v) lines.push({ key, label, value: v });
  };
  push("evidence", "Tingkat bukti", evidenceLabel(p.evidence_kind));
  push("source", "Sumber", p.source);
  push("period", "Basis periode", p.period?.basis);
  push("method", "Metode", p.method_version);
  push("baseline", "Pembanding", baselineText(baselineOf(metric)));
  push("definition", "Definisi", p.definition);
  push("formula", "Rumus", p.formula);
  return lines;
}

export type KpiEstimate = {
  state: string;
  value: string | null;
  unit: string | null;
  reason: string | null;
  definition: string | null;
  method: string | null;
  coverage: string | null;
};

export function estimateOf(metric: any): KpiEstimate | null {
  const e = metric?.estimate;
  if (!e || typeof e !== "object") return null;
  return {
    state: String(e.state ?? "no_data"),
    value: e.value === undefined || e.value === null ? null : String(e.value),
    unit: e.unit ? String(e.unit) : null,
    reason: e.reason ? String(e.reason) : null,
    definition: e.definition ? String(e.definition) : null,
    method: e.method ? String(e.method) : null,
    coverage: e.coverage === undefined || e.coverage === null
      ? null
      : String(e.coverage),
  };
}

/**
 * Satu baris ringkas untuk blok estimasi: selalu berawalan "estimasi" supaya
 * angka proyeksi tidak pernah terbaca sebagai hasil lapangan.
 */
export function estimateLine(metric: any): string | null {
  const e = estimateOf(metric);
  if (!e) return null;
  if (e.state === "available" && e.value !== null) {
    const angka = Number(e.value);
    const teks = Number.isFinite(angka)
      ? angka.toLocaleString("id-ID", { maximumFractionDigits: 2 })
      : e.value;
    const satuan = e.unit ? ` ${e.unit}` : "";
    return `estimasi ${teks}${satuan}`;
  }
  return `estimasi tidak tersedia — ${e.reason ?? "tanpa alasan"}`;
}

/** Fakta pendamping yang dikirim server (mis. harga invoice atau kg dibuang). */
export function factLine(metric: any): string | null {
  const f = metric?.facts;
  if (!f || typeof f !== "object") return null;
  if (f.invoice_unit_price_mean_idr) {
    return (
      "invoice rata-rata Rp" +
      Number(f.invoice_unit_price_mean_idr).toLocaleString("id-ID", {
        maximumFractionDigits: 0,
      }) +
      ` (n=${f.invoice_sample_count ?? 0}) — terpisah dari SDC analitis`
    );
  }
  if (f.disposed_kg !== undefined && f.disposed_kg !== null) {
    const kg = Number(f.disposed_kg).toLocaleString("id-ID", {
      maximumFractionDigits: 2,
    });
    return `disposal tercatat ${kg} kg`;
  }
  return null;
}
