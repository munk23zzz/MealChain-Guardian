// Perakitan detail satu lokasi untuk pop-up "Pasokan & permintaan"
// (dokumen 03 §3–§4, 28 Okt 2026). Murni: tidak memanggil jaringan, sehingga
// setiap aturan di bawah bisa diuji tanpa server.
//
// Aturan yang dijaga (semuanya berasal dari dokumen 03):
//   - 404 ≠ 0. Lokasi tanpa catatan menulis "tidak ada catatan", bukan 0 kg —
//     angka 0 yang dikarang akan terbaca sebagai "permintaannya nol".
//   - Selisih TIDAK dihitung di sini: `shortage_kg`/`surplus_kg` datang dari
//     `GET /balance/{loc}/{com}` (backend `app/core/gaps.py`).
//   - Perkiraan kebutuhan 7 hari datang dari `GET /demand/forecast/{loc}/{com}`
//     (dokumen 03 §3 butir 3, §4). Metode dan keyakinannya ikut ditampilkan;
//     dasar tipis (kurang dari 3 catatan permintaan) dinyatakan, bukan
//     disembunyikan. Tetap tidak ada angka perkiraan yang dihitung di sini.
//   - Batch disaring di browser karena `GET /batches` belum menerima filter
//     lokasi/komoditas; kalau daftar yang diterima menyentuh plafon, UI
//     menyatakan bahwa batch lebih lama tidak ikut terhitung (§7).

export type BatchRow = {
  id?: string;
  location?: string | null;
  commodity?: string | null;
  quantity_kg?: number | string | null;
  safety_status?: string | null;
  /** `"quarantined"` = ditahan; server mengirimnya, jadi jangan dibuang. */
  quarantine_status?: string | null;
  freshness_score?: number | string | null;
  usable_until?: string | null;
};

/** `true` bila batch sedang ditahan dan tidak boleh dihitung sebagai stok siap. */
export function isQuarantined(batch: BatchRow): boolean {
  return (batch.quarantine_status ?? "").trim().toLowerCase() === "quarantined";
}

export type FailedPart = "balance" | "supply" | "demand" | "batches" | "forecast";

export type SupplyRecordView = {
  quantityKg: number | null;
  recordedAt: string | null;
  source: string | null;
};

export type DemandRecordView = {
  quantityKg: number | null;
  neededBy: string | null;
};


export type GapView = {
  /** "kurang 780 kg" / "lebih 400 kg" / "seimbang" / "—" */
  text: string;
  tone: "danger" | "safe" | "neutral" | "unknown";
};

export type BatchSummary = {
  total: number;
  /** Lolos uji DAN tidak sedang ditahan. */
  pass: number;
  fail: number;
  /**
   * Batch yang sedang ditahan (`quarantine_status === "quarantined"`). Ia tidak
   * boleh dibaca sebagai stok layak pakai — `backend/app/api/batches.py`
   * menyatakan aturan itu, dan tabel yang menuliskannya "Aman" seperti stok
   * biasa akan menyesatkan.
   */
  quarantined: number;
  /** Status lain disebut namanya, tidak dilebur ke PASS/FAIL. */
  others: { status: string; count: number }[];
};

/**
 * Perkiraan kebutuhan untuk satu horizon (dokumen 03 §3 butir 3).
 *
 * `quantityKg` boleh null: server bisa menjawab tanpa angka, dan kartu harus
 * menulis "—" — bukan 0 kg yang terbaca sebagai "kebutuhannya nol".
 */
export type ForecastView = {
  quantityKg: number | null;
  horizonDays: number;
  /** Nama metode mentah dari server, disimpan untuk jejak. */
  method: string | null;
  /** Terjemahan metode untuk dibaca ("perkiraan statistik"). */
  methodLabel: string;
  confidence: number | null;
  confidenceLabel: string;
  /** Kalimat jujur ketika dasarnya tipis atau angkanya tidak ada. */
  note: string | null;
};

export type SupplyDemandDetail = {
  location: string;
  commodity: string;
  supply: SupplyRecordView | null;
  demand: DemandRecordView | null;
  /** Perkiraan kebutuhan 7 hari; null bila server tidak punya perkiraan. */
  forecast: ForecastView | null;
  gap: GapView | null;
  /** Satu baris per bagian yang tidak bisa dibaca, dengan sebabnya. */
  notes: string[];
  batches: BatchRow[];
  batchSummary: BatchSummary;
  /** `true` bila daftar batch yang diterima menyentuh plafon server. */
  batchesTruncated: boolean;
  batchCap: number;
};

const BATCH_CAP = 500;

function toNumber(raw: number | string | null | undefined): number | null {
  if (raw === null || raw === undefined) return null;
  if (typeof raw === "string" && !raw.trim()) return null;
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

export function formatKg(value: number | null): string {
  if (value === null) return "—";
  return `${value.toLocaleString("id-ID", { maximumFractionDigits: 2 })} kg`;
}

function gapFromBalance(balance: Record<string, unknown> | null): GapView | null {
  if (!balance) return null;
  const shortage = toNumber(balance.shortage_kg as number | string | null);
  const surplus = toNumber(balance.surplus_kg as number | string | null);
  if (shortage === null && surplus === null) {
    return { text: "—", tone: "unknown" };
  }
  if ((shortage ?? 0) > 0) {
    return { text: `kurang ${formatKg(shortage)}`, tone: "danger" };
  }
  if ((surplus ?? 0) > 0) {
    return { text: `lebih ${formatKg(surplus)}`, tone: "safe" };
  }
  return { text: "seimbang", tone: "neutral" };
}

/** Pesan untuk bagian yang gagal dibaca — dibedakan dari "tidak ada catatan". */
function missingNote(part: FailedPart, message: string | undefined): string {
  const label =
    part === "balance"
      ? "Saldo"
      : part === "supply"
        ? "Catatan pasokan"
        : part === "demand"
          ? "Catatan permintaan"
          : part === "forecast"
            ? "Perkiraan kebutuhan"
            : "Daftar batch";
  if (!message) return `${label} tidak tersedia.`;
  if (message.includes("404")) return `${label} tidak ada untuk lokasi ini.`;
  return `${label} gagal dimuat.`;
}

const HORIZON_HARI = 7;

/** Terjemahan metode perkiraan; nama asing diteruskan apa adanya. */
function methodLabel(method: string | null): string {
  if (!method) return "metode tidak tercatat";
  if (method === "statistical_fallback") return "perkiraan statistik";
  if (method === "provider_forecast") return "perkiraan penyedia";
  return method;
}

/**
 * Membaca balasan `GET /demand/forecast/{loc}/{com}` menjadi kartu keempat.
 *
 * Keyakinan < 1 berarti dasar catatannya kurang dari tiga — itu dinyatakan di
 * kartu, karena angka tujuh hari dari dua catatan mudah terbaca sebagai ramalan
 * yang lebih kuat daripada kenyataannya.
 */
export function buildForecastView(raw: Record<string, unknown> | null | undefined): ForecastView | null {
  if (!raw) return null;
  const quantityKg = toNumber(
    (raw.forecast_qty_kg ?? raw.quantity_kg ?? null) as number | string | null
  );
  const method = typeof raw.method === "string" && raw.method.trim() ? raw.method.trim() : null;
  const confidence = toNumber(raw.confidence as number | string | null);
  const horizonDays = toNumber(raw.horizon_days as number | string | null) ?? HORIZON_HARI;

  const tipis = confidence !== null && confidence < 1;
  const confidenceLabel = tipis
    ? "dasar tipis"
    : confidence === null
      ? "keyakinan tidak dilaporkan"
      : "keyakinan penuh";

  let note: string | null = null;
  if (tipis) note = "dasar tipis — kurang dari 3 catatan permintaan, jadi arahnya lebih pasti daripada angkanya.";
  else if (quantityKg === null) note = "tidak ada angka perkiraan dari server.";

  return {
    quantityKg,
    horizonDays,
    method,
    methodLabel: methodLabel(method),
    confidence,
    confidenceLabel,
    note,
  };
}

export function summarizeBatches(batches: readonly BatchRow[]): BatchSummary {
  let pass = 0;
  let fail = 0;
  let quarantined = 0;
  const others = new Map<string, number>();
  for (const batch of batches) {
    const status = (batch.safety_status ?? "").trim().toLowerCase();
    const ditahan = isQuarantined(batch);
    if (ditahan) quarantined += 1;
    if (status === "pass") {
      // Lolos uji tetapi ditahan bukan stok siap pakai: ia dihitung di
      // `quarantined`, bukan di `pass`.
      if (!ditahan) pass += 1;
    } else if (status === "fail") fail += 1;
    else if (status) others.set(status, (others.get(status) ?? 0) + 1);
    else others.set("tidak tercatat", (others.get("tidak tercatat") ?? 0) + 1);
  }
  return {
    total: batches.length,
    pass,
    fail,
    quarantined,
    others: Array.from(others.entries())
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .map(([status, count]) => ({ status, count })),
  };
}

export function buildSupplyDemandDetail(input: {
  location: string;
  commodity: string;
  balance?: Record<string, unknown> | null;
  supply?: Record<string, unknown> | null;
  demand?: Record<string, unknown> | null;
  forecast?: Record<string, unknown> | null;
  batches?: readonly BatchRow[] | null;
  failed?: Partial<Record<FailedPart, string>>;
}): SupplyDemandDetail {
  const failed = input.failed ?? {};
  const notes: string[] = [];

  const balance = input.balance ?? null;
  const supplyRaw = input.supply ?? null;
  const demandRaw = input.demand ?? null;

  if (balance === null) notes.push(missingNote("balance", failed.balance));
  if (supplyRaw === null) notes.push(missingNote("supply", failed.supply));
  if (demandRaw === null) notes.push(missingNote("demand", failed.demand));

  // Perkiraan yang tidak ada sudah dinyatakan kartunya sendiri ("—"),
  // jadi tidak diulang sebagai catatan.
  const forecast = buildForecastView(input.forecast ?? null);
  if (forecast?.note) notes.push(forecast.note);

  const supply: SupplyRecordView | null = supplyRaw
    ? {
        quantityKg: toNumber(supplyRaw.quantity_kg as number | string | null),
        recordedAt: (supplyRaw.recorded_at as string | undefined) ?? null,
        source: (supplyRaw.source as string | undefined) ?? null,
      }
    : null;

  const demand: DemandRecordView | null = demandRaw
    ? {
        quantityKg: toNumber(demandRaw.quantity_kg as number | string | null),
        neededBy: (demandRaw.needed_by as string | undefined) ?? null,
      }
    : null;

  // Batch satu lokasi + satu komoditas. `GET /batches` mengirim baris terbaru
  // lintas lokasi; penyaringan ini yang membuat tabel benar, dan plafon yang
  // tersentuh harus dinyatakan.
  const semuaBatch = input.batches ?? [];
  const kapasitasTerpakai = semuaBatch.length >= BATCH_CAP;
  const batches = semuaBatch.filter(
    (batch) =>
      (batch.location ?? "") === input.location &&
      (batch.commodity ?? "") === input.commodity
  );

  if (failed.batches) notes.push(missingNote("batches", failed.batches));
  if (kapasitasTerpakai && batches.length > 0) {
    notes.push(
      `Daftar batch dibatasi ${BATCH_CAP} baris terbaru dari server; batch yang lebih lama untuk lokasi ini tidak ikut terhitung.`
    );
  }

  return {
    location: input.location,
    commodity: input.commodity,
    supply,
    demand,
    gap: gapFromBalance(balance),
    forecast,
    notes,
    batches: [...batches].sort(
      (a, b) => Date.parse(b.usable_until ?? "") - Date.parse(a.usable_until ?? "")
    ),
    batchSummary: summarizeBatches(batches),
    batchesTruncated: kapasitasTerpakai,
    batchCap: BATCH_CAP,
  };
}
