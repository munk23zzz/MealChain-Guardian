// API client MealChain Guardian — kontrak backend aktual (S3-12).
// Tanpa karangan: hanya endpoint yang benar-benar ada di backend.

import { metodeMenulis, segarkanSetelahTulis } from "./refresh";
import { balancePath } from "./balance-url";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Galat HTTP backend yang membawa status. Pemanggil bisa membedakan 401 (sesi
 *  tidak sah → sesi perlu dibuang) dari galat lain TANPA mencocokkan teks pesan.
 *  Pesannya tetap "HTTP <status>: <path>" seperti sebelumnya. */
export class ApiError extends Error {
  readonly status: number;
  /** Alasan dari server (`detail`), apa adanya; null bila tak ada/tak terbaca.
   *  Audit M9: dulu hanya `HTTP 409: /actions/approve` yang sampai ke layar,
   *  sehingga pengguna tidak tahu APA yang menahan (mis. "verdict sudah
   *  tercatat — hasil audit tidak bisa ditimpa"). */
  readonly detail: string | null;
  constructor(status: number, path: string, detail?: string | null) {
    super(detail && detail.trim() ? detail : `HTTP ${status}: ${path}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail && detail.trim() ? detail : null;
  }
}

/** `detail` FastAPI → satu kalimat yang bisa dibaca.
 *
 *  String dikembalikan apa adanya. Daftar validasi (422) diringkas menjadi
 *  "field: pesan" — kalau daftarnya dibiarkan, UI menampilkan [object Object].
 *  Bentuk lain (objek, dsb.) tidak ditebak: null, supaya pemanggil memakai
 *  pesan status yang jujur. */
function pesanDetail(body: unknown): string | null {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const bagian = detail
      .map((baris) => {
        const isi = baris as { loc?: unknown; msg?: unknown };
        const loc = Array.isArray(isi?.loc)
          ? isi.loc.filter((x) => x !== "body" && x !== "query" && x !== "path").join(".")
          : "";
        const msg = typeof isi?.msg === "string" ? isi.msg : "";
        if (!msg) return "";
        return loc ? `${loc}: ${msg}` : msg;
      })
      .filter(Boolean);
    return bagian.length ? bagian.join("; ") : null;
  }
  return null;
}

export async function request(path: string, init: RequestInit): Promise<any> {
  const resp = await fetch(`${API_URL}${path}`, init);
  // Body dibaca SEKALI, untuk sukses maupun galat: alasan server ikut dibawa
  // ke layar (audit M9), dan body tidak bisa dibaca dua kali.
  const text = await resp.text();
  let hasil: unknown;
  let jsonSah = true;
  try {
    hasil = JSON.parse(text);
  } catch {
    jsonSah = false;
  }
  if (!resp.ok) {
    // Backend kadang membalas HTML (proxy/error page): jangan menebak alasan,
    // pakai pesan status yang jujur.
    throw new ApiError(resp.status, path, jsonSah ? pesanDetail(hasil) : null);
  }
  // Backend kadang membalas HTML pada status 200 — pesan parse mentah
  // ("Unexpected token '<'...") jangan sampai tampil di UI.
  if (!jsonSah) {
    throw new Error(`Respons bukan JSON dari ${path} (HTTP ${resp.status})`);
  }
  // Satu-satunya tempat semua tulis lewat: begitu server menerima perubahan,
  // SELURUH cache data disegarkan (lihat `lib/refresh.ts`). Tanpa ini, tiap
  // komponen harus ingat me-refetch query-nya sendiri — dan yang lupa akan
  // menampilkan angka lama.
  if (metodeMenulis(init.method)) segarkanSetelahTulis();
  return hasil;
}

export async function login(email: string, password: string) {
  return request("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
 });
}

// GET /auth/me — identitas kanonik pemakai (role + lokasi). Dipakai top bar:
// dropdown cakupan peran SPPG harus terkunci ke SPPG pemakainya, dan itu
// ditentukan server, bukan ditebak dari JWT.
export async function fetchMe(token: string) {
  return request("/auth/me", {
    headers: { Authorization: `Bearer ${token}` },
 });
}

// GET /integrations/status — papan status integrasi per komponen (read-only).
// Status = JENIS BUKTI (env/artefak/kontrak), bukan klaim operasional: backend
// tidak menjalankan probe apa pun, jadi tidak ada label hijau tanpa bukti
// (PLAN-012). Butuh akar "integrations" di next.config.js (API_ROOTS).
export function fetchIntegrationStatus(token: string): Promise<any> {
  return request("/integrations/status", {
    headers: { Authorization: `Bearer ${token}` },
 });
}

// /sap/purchase-orders — sisi BACA purchase order SAP simulasi (W-5, 2026-10-17).
// PO-nya sendiri ditulis `actions.py` saat eksekusi; endpoint ini hanya membaca
// tabel `sap_mock_purchase_orders`. Balasan selalu membawa `source`, dan UI
// wajib menyebutnya apa adanya: data SAP simulasi, bukan SAP S/4HANA produksi.
// (19 Okt 2026: penanda dipindah ke chip "SAP simulasi" — labelnya tetap, hanya
// bahasanya tidak lagi menyebut tabel/DB internal.)
export function fetchPurchaseOrders(
  token: string,
  opts: { status?: string; decisionId?: string; limit?: number } = {}
): Promise<any> {
  const qs = new URLSearchParams();
  if (opts.status) qs.set("status", opts.status);
  if (opts.decisionId) qs.set("decision_id", opts.decisionId);
  if (opts.limit) qs.set("limit", String(opts.limit));
  const akhiran = qs.toString() ? `?${qs.toString()}` : "";
  return request(`/sap/purchase-orders${akhiran}`, {
    headers: { Authorization: `Bearer ${token}` },
 });
}

export function fetchPurchaseOrderSummary(token: string): Promise<any> {
  return request("/sap/purchase-orders/summary", {
    headers: { Authorization: `Bearer ${token}` },
 });
}

/**
 * Dokumen PO (PDF) — berkas biner, jadi tidak lewat `request` yang membaca body
 * sebagai teks. Alasannya tetap sama: alasan galat dari server harus sampai ke
 * layar ("keputusan menunggu persetujuan"), bukan "gagal" tanpa sebab.
 */
export async function fetchPurchaseOrderPdf(poNumber: string, token: string): Promise<Blob> {
  const path = `/sap/purchase-orders/${encodeURIComponent(poNumber)}/pdf`;
  const resp = await fetch(`${API_URL}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
 });
  if (!resp.ok) {
    let detail: string | null = null;
    try {
      detail = pesanDetail(await resp.json());
    } catch {
      detail = null;
    }
    throw new ApiError(resp.status, path, detail);
  }
  return resp.blob();
}

export function fetchComplianceDossier(decisionId: string, token: string): Promise<any> {
  return request(`/decisions/${encodeURIComponent(decisionId)}/compliance`, {
    headers: { Authorization: `Bearer ${token}` },
 });
}

export async function fetchDecisions(
  token: string,
  window?: string | null
) {
  return request(`/decisions${window ? `?window=${encodeURIComponent(window)}` : ""}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function fetchDecision(decisionId: string, token: string) {
  return request(`/decisions/${decisionId}`, {
    headers: { Authorization: `Bearer ${token}` },
 });
}

export async function fetchDecisionTraces(decisionId: string, token: string) {
  return request(`/decisions/${decisionId}/traces`, {
    headers: { Authorization: `Bearer ${token}` },
 });
}

export async function approveAction(
  decisionId: string,
  approved: boolean,
  token: string,
  comment?: string
) {
  return request("/actions/approve", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ decision_id: decisionId, approved, comment }),
 });
}

export async function executeAction(decisionId: string, token: string) {
  return request("/actions/execute", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ decision_id: decisionId }),
 });
}

export async function verifyAction(decisionId: string, token: string) {
  // O-SEC-3: verdict TIDAK dikirim dari browser — server menjalankan
  // verifier independen dari data kanonik (plan Sprint 4 §10).
  return request("/actions/verify", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ decision_id: decisionId }),
 });
}

export async function reproposeAction(decisionId: string, token: string) {
  return request("/actions/repropose", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ decision_id: decisionId }),
 });
}

// POST /safety/evaluate + /freshness/evaluate (Fase 11 — halaman Keamanan
// Pangan). Keduanya MENGUKUR ULANG dari data yang tersimpan di server (log suhu
// batch + umur panen) lalu MENULIS hasilnya ke DB — jadi angka di layar setelah
// menekan tombol datang dari perhitungan server, bukan dari UI. Hanya peran
// pemutasi (kepala SPPG / ahli gizi) yang boleh memanggilnya; BGN Monitor
// read-only, dan itu ditegakkan di server, bukan hanya disembunyikan di layar.
export type SafetyCheck = {
  safety_status: string;
  reasons: string[];
  excursion_minutes: number;
};

export async function evaluateSafety(batchId: string, token: string): Promise<SafetyCheck> {
  return request("/safety/evaluate", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ batch_id: batchId }),
 });
}

export type KarantinaAksi = "tahan" | "lepas" | "gagal";

export type KarantinaResult = {
  batch_id: string;
  quarantine_status: "none" | "quarantined" | "released" | "failed";
  quarantine_reason: string;
  quarantined_at: string | null;
  quarantine_updated_at: string;
  safety_status: string;
  ledger_height: number;
  ledger_hash: string;
};

/**
 * Karantina batch: keputusan manusia, bukan langkah agent.
 * `alasan` wajib — ia ikut tersimpan sebagai blok evidence ledger di server.
 */
export async function ubahKarantina(
  batchId: string,
  aksi: KarantinaAksi,
  alasan: string,
  token: string
): Promise<KarantinaResult> {
  return request(`/batches/${batchId}/quarantine`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ aksi, alasan }),
 });
}

export type FreshnessCheck = {
  freshness_score: number;
  status: string;
  usable_until: string;
};

export async function evaluateFreshness(batchId: string, token: string): Promise<FreshnessCheck> {
  return request("/freshness/evaluate", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ batch_id: batchId }),
 });
}

// /events/safety-disruption — jalankan Event 3 untuk SATU batch dari halaman
// Keamanan Pangan. Server menghitung ulang keamanan dari log suhu tersimpan:
//   • batch FAIL  → 201: keputusan `safety_disruption` + bukti suhu + trace
//                   DETECT/OPTIMIZE (decision_id terisi);
//   • batch aman  → 200: `no_disruption`, decision_id null (tidak mengarang
//                   keputusan);
//   • 409: operation_key dipakai batch lain, atau tidak ada alternatif eligible.
// `operationKey` = kunci idempotensi: kirim kunci yang SAMA untuk batch yang
// sama saat mengulang — server melayani dari catatan, bukan membuat keputusan
// kembar. Lokasi tujuan WAJIB lokasi SPPG pemanggil (ruling 2026-10-14), batch
// pemicu boleh milik lokasi lain (sisi sumber).
export type DisruptionEventResult = {
  status: string;
  decision_id: string | null;
  message?: string;
  safety_status?: string;
  excursion_minutes?: number;
};

// POST /events/safety-disruption — pemicu Event 3 (thermal excursion).
// Body PERSIS field yang diterima backend (SafetyDisruptionRequest memakai
// extra="forbid"): batch_id + target_location_id + operation_key. TIDAK ada
// field tingkat gangguan — besar gangguan dinilai server dari temperature_log
// batch terpilih (mengirim field tambahan = 422, dan itu memang benar).
export async function triggerSafetyDisruption(
  batchId: string,
  targetLocationId: string,
  operationKey: string,
  token: string
): Promise<DisruptionEventResult> {
  return request("/events/safety-disruption", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      batch_id: batchId,
      target_location_id: targetLocationId,
      operation_key: operationKey,
    }),
 });
}

// /receipts — catatan penerimaan barang (migrasi 016). Inilah rumah jujur untuk
// isian manual petugas, termasuk opsi "Lainnya" (keadaan yang tidak ada di
// daftar periksa). Server menyimpan snapshot titik periksa apa adanya, mencatat
// siapa & kapan, dan MENGHITUNG sendiri jumlah titik yang benar-benar dicentang.
export type ReceiptRow = {
  id: string;
  batch_id: string;
  checked: Record<string, boolean>;
  checked_count: number;
  other_note: string | null;
  recorded_by: string;
  recorded_by_name: string | null;
  recorded_at: string;
  // ---- keputusan (migrasi 026) ----
  status: "menunggu" | "disetujui" | "ditolak";
  reviewed_by: string | null;
  reviewed_by_name: string | null;
  reviewed_at: string | null;
  review_note: string | null;
  supply_record_id: string | null;
  stock_kg: number | null;
};

export async function recordReceipt(
  batchId: string,
  checked: Record<string, boolean>,
  otherNote: string,
  token: string
): Promise<ReceiptRow> {
  return request("/receipts", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ batch_id: batchId, checked, other_note: otherNote }),
 });
}

export async function fetchReceipts(
  batchId: string,
  token: string,
  limit = 5
): Promise<{ items: ReceiptRow[] }> {
  return request(`/receipts?batch_id=${encodeURIComponent(batchId)}&limit=${limit}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export type PendingReceiptRow = {
  id: string;
  batch_id: string;
  commodity: string;
  quantity_kg: number;
  location: string;
  safety_status: string | null;
  checked_count: number;
  recorded_by_name: string | null;
  recorded_at: string;
};

/** Catatan penerimaan yang sudah dibuat tetapi belum diputuskan (antrean approval). */
export async function fetchPendingReceipts(
  token: string
): Promise<{ items: PendingReceiptRow[]; total: number }> {
  return request("/receipts/menunggu", {
    headers: { Authorization: `Bearer ${token}` },
  });
}

/** Kepala SPPG menyetujui penerimaan → barang masuk stok (idempoten di server). */
export async function approveReceipt(
  receiptId: string,
  token: string
): Promise<ReceiptRow & { sudah?: boolean }> {
  return request(`/receipts/${encodeURIComponent(receiptId)}/approve`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

/** Kepala SPPG menolak penerimaan; alasan wajib (server menolak yang kosong). */
export async function rejectReceipt(
  receiptId: string,
  note: string,
  token: string
): Promise<ReceiptRow & { sudah?: boolean }> {
  return request(`/receipts/${encodeURIComponent(receiptId)}/reject`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ note }),
  });
}

// /actions/propose — angkat "proposed" → "pending_approval" agar bisa
// di-approve. `materialNumber` opsional (18 Okt 2026): UI tidak tahu kode
// material, jadi server menurunkannya dari komoditas (`MAT-<KOMODITAS>`).
export async function proposeAction(
  decisionId: string,
  materialNumber: string | null,
  token: string
) {
  return request("/actions/propose", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      decision_id: decisionId,
      ...(materialNumber ? { material_number: materialNumber } : {}),
    }),
 });
}

export async function fetchDecisionChain(
  decisionId: string,
  token: string
) {
  return request(`/decisions/${decisionId}/chain`, {
    headers: { Authorization: `Bearer ${token}` },
 });
}

// S4-04: read model kanonik approval — modal TIDAK menghitung requirement;
// semua field (verifier, matrix, expiry, readiness) dari server.
export async function fetchApprovalSummary(
  decisionId: string,
  token: string
) {
  return request(`/decisions/${decisionId}/approval-summary`, {
    headers: { Authorization: `Bearer ${token}` },
 });
}

export async function seedDemo(token: string, force = false) {
  return request("/demo/seed", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ force }),
 });
}

// --- Data & rentang waktu (Fase 5) — panel Demo Control ---
// Rentang dikirim sebagai ISO dengan offset eksplisit (`<input type="date">`
// hanya punya tanggal); kontrak ini yang menolak waktu tanpa offset (422).

function authHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}

/** `GET /demo/data-status` — keadaan DB sekarang (bukan ingatan klien). */
export async function fetchDemoDataStatus(token: string) {
  return request("/demo/data-status", { headers: authHeaders(token) });
}

/** `GET /demo/preview` — hitungan baris yang AKAN ditambah; tidak menulis apa pun. */
export async function fetchDemoPreview(
  startIso: string,
  endIso: string,
  token: string,
  intervalHours = 12
) {
  const qs = new URLSearchParams({
    start: startIso,
    end: endIso,
    interval_hours: String(intervalHours),
 });
  return request(`/demo/preview?${qs.toString()}`, { headers: authHeaders(token) });
}

/** `POST /demo/timeseries` — tambah/perbarui baris `origin='demo'` (idempoten). */
export async function runDemoTimeseries(
  startIso: string,
  endIso: string,
  token: string,
  { force = false, intervalHours = 12 }: { force?: boolean; intervalHours?: number } = {}
) {
  return request("/demo/timeseries", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify({
      start: startIso,
      end: endIso,
      interval_hours: intervalHours,
      force,
    }),
 });
}

/** `POST /demo/timeseries/purge` — hapus HANYA baris demo; kanonik tidak disentuh. */
export async function purgeDemoTimeseries(token: string) {
  return request("/demo/timeseries/purge", { method: "POST", headers: authHeaders(token) });
}

/**
 * `POST /demo/refresh` — tombol hari demo: seeder relatif `now` + muat ulang
 * 4 kasus skrip. Akun demo tidak direset, baris deret waktu demo tidak dihapus.
 */
export async function refreshDemoToToday(token: string) {
  return request("/demo/refresh", { method: "POST", headers: authHeaders(token) });
}

// --- Sesi demo (migrasi 024/025) -------------------------------------------
// Kontrak: `remaining_seconds` dihitung SERVER; UI hanya menguranginya dengan
// waktu yang berjalan di layar, lalu menyelaraskan lagi tiap 20 detik.

/** `GET /demo/session` — status + hitungan mundur (aman dipanggil berulang). */
export async function fetchDemoSession(token: string) {
  return request("/demo/session", { headers: authHeaders(token) });
}

/** `POST /demo/session/start` — buat sesi, semai data, aktifkan jendela waktu. */
export async function startDemoSession(token: string, menit?: number) {
  return request("/demo/session/start", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify(menit ? { menit } : {}),
  });
}

/** `POST /demo/session/extend` — tambah waktu; sesi & data tidak diganti. */
export async function extendDemoSession(token: string, menit = 30) {
  return request("/demo/session/extend", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify({ menit }),
  });
}

/** `POST /demo/session/end` — tutup sesi sekarang; data sesi dibersihkan. */
export async function endDemoSession(token: string) {
  return request("/demo/session/end", { method: "POST", headers: authHeaders(token) });
}

/**
 * `POST /demo/template/rebuild` — bangun ulang SELURUH data demo (terukur 41 detik).
 *
 * Beda dari `startDemoSession`: jendela waktu sesi tidak disentuh, dan panggilan
 * ini memang menghapus baris operasional lalu menyemai ulang template. Dipakai
 * saat geladi berulang supaya angka kembali ke keadaan awal tanpa menutup sesi.
 * Permintaan kedua saat proses masih berjalan dijawab 409 oleh server.
 */
export async function rebuildDemoTemplate(token: string) {
  return request("/demo/template/rebuild", { method: "POST", headers: authHeaders(token) });
}


/**
 * `POST /demo/event1` — jalankan Event 1 PENUH di backend
 * (DETECT → VERIFY → TRACE → PREDICT → OPTIMIZE → DECIDE → SUPERVISE).
 *
 * Bedanya dari "Jalankan agent" (`POST /balance/analyze`): yang itu hanya
 * meminta rekomendasi deterministik (belum menulis apa pun), sedangkan yang ini
 * membuat keputusan berstatus `proposed` BESERTA seluruh jejak langkahnya —
 * termasuk narasi supervisor — sehingga muncul di Recommendation Feed dan
 * Agent Log. Tidak ada approval/eksekusi otomatis.
 */
export async function runEvent1(
  commodity: string,
  targetLocation: string,
  token: string,
  ttlMinutes = 30
) {
  return request("/demo/event1", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      commodity,
      target_location: targetLocation,
      ttl_minutes: ttlMinutes,
    }),
 });
}

// --- Ops Console (interaksi sebelum hasil — arah Roy 2026-10-07) ---

export async function fetchBalance(
  location: string,
  commodity: string,
  token: string,
  /** `as_of` dari respons peta: panel detail membaca snapshot yang SAMA. */
  asOf?: string | null
) {
  return request(balancePath(location, commodity, asOf), {
    headers: { Authorization: `Bearer ${token}` },
 });
}

export async function runAnalysis(token: string, commodity?: string) {
  return request("/balance/analyze", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    // Ruling S4-05 p10: kirim komoditas panel agar pipeline difilter
    // (proposal mengikuti komoditas yang dianalisis, bukan rank-1 global).
    body: JSON.stringify({ commodity: commodity ?? null }),
 });
}

// POST /decisions — snapshot rekomendasi dipersist (status "proposed").
// TTL default 60 menit (agar usulan tidak mati di tengah demo).
export async function createDecision(
  recommendation: any,
  ttlMinutes: number,
  token: string
) {
  return request("/decisions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      recommendation,
      ttl_minutes: ttlMinutes,
      decision_type: "regional_balance",
    }),
 });
}

// --- Event 2 (Sprint 4) — price anomaly review-only ---

// GET /price/quotes/{loc}/{com} — daftar quote + referensi PIHPS terkini
// (read-only, semua role; data untuk pemilihan di panel Event 2).
export async function fetchPriceQuotes(
  location: string,
  commodity: string,
  token: string
) {
  return request(`/price/quotes/${location}/${commodity}`, {
    headers: { Authorization: `Bearer ${token}` },
 });
}

// POST /events/price-anomaly — 201 decision price_anomaly / 200 no-anomaly
// (tanpa write) / 409 operation_key dipakai untuk payload berbeda.
// operation_key dibuat client SAAT quote dipilih (idempotensi per aksi);
// angka deviasi tetap dihitung backend — browser tidak menghitung apa pun.
export async function triggerPriceAnomaly(
  quoteId: string,
  targetLocationId: string,
  operationKey: string,
  token: string
) {
  return request("/events/price-anomaly", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      quote_id: quoteId,
      target_location_id: targetLocationId,
      operation_key: operationKey,
    }),
 });
}

// Rencana alokasi surplus lintas lokasi (GET /surplus/allocations, 20 Okt 2026).
// Dihitung SERVER karena /balance/map dibatasi cakupan peran: peran SPPG hanya
// menerima lokasinya sendiri, sehingga panel "Rencana alokasi surplus" selalu
// kosong kalau pasangannya dirakit di klien.
export async function fetchSurplusAllocations(
  token: string,
  commodity: string,
  limit = 6
) {
  const params = new URLSearchParams({ commodity, limit: String(limit) });
  return request(`/surplus/allocations?${params.toString()}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

// S4-03: KPI tujuh metrik — envelope {period, scope, computed_at,
// data_source, metrics[]}. Nilai null/state unavailable dirender apa
// adanya (TANPA fake 0); scope SPPG = own location, monitor = global.
/** Ringkasan limbah + mitra pengolahan (GET /waste/summary). */
export async function fetchWasteSummary(token: string, days = 30) {
  const params = new URLSearchParams({ days: String(days) });
  return request(`/waste/summary?${params.toString()}`, {
    headers: { Authorization: `Bearer ${token}` },
 });
}

export async function fetchKpis(
  periode: string,
  token: string,
  locationId?: string,
  provenance?: { includeDemo?: boolean; demoSessionId?: string }
) {
  const params = new URLSearchParams({ periode });
  if (locationId) params.set("location_id", locationId);
  // Cakupan data (Fase 8): `include_demo=false` (bawaan server) = fakta kerja
  // saja. Simulasi WAJIB menyebut sesi eksplisit — server menolak 422 bila
  // `include_demo=true` tanpa `demo_session_id`, supaya tidak ada tebakan
  // "sesi terbaru" yang mencampur data sesi lain.
  if (provenance?.includeDemo) {
    params.set("include_demo", "true");
    if (provenance.demoSessionId) {
      params.set("demo_session_id", provenance.demoSessionId);
    }
  }
  return request(`/kpi?${params.toString()}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

// GET /batches — inventaris batch (lokasi, komoditas, kg, kesegaran, batas
// pakai). Dipakai halaman "Hari Ini" untuk daftar batch yang akan kedaluwarsa.
// Backend membalas {batches: [...]} — envelope itu dibuka di sini supaya
// pemanggil tidak perlu tahu bentuk amplopnya.
export async function fetchBatches(token: string) {
  // Plafon server 500. Tanpa `limit`, server memakai 50 baris terbaru dan
  // barang baru datang (mis. ayam 90 kg) bisa tidak ikut terkirim sama sekali —
  // kartu Penerimaan lalu tampak tidak punya batch padahal DB punya.
  const data = await request("/batches?limit=500", {
    headers: { Authorization: `Bearer ${token}` },
 });
  return Array.isArray(data) ? data : (data?.batches ?? []);
}

// Kalender agenda harian (langkah 2, 2026-10-16): rentang tanggal masuk query
// string; backend membatasinya 62 hari dan menolak rentang terbalik (422).
export async function fetchAgenda(token: string, start: string, end: string) {
  const data = await request(`/agenda?start=${start}&end=${end}`, {
    headers: { Authorization: `Bearer ${token}` },
 });
  return data ?? null;
}

// S4-06 polish (arah Roy 2026-10-08): kondisi SEMUA lokasi untuk peta +
// grafik stok — satu panggilan GET /balance/map (read-only, data REAL,
// formula gap = panel snapshot, koordinat dari DB).
export async function fetchBalanceMap(commodity: string, token: string) {
  return request(`/balance/map?commodity=${encodeURIComponent(commodity)}`, {
    headers: { Authorization: `Bearer ${token}` },
 });
}

// GET /suppliers — daftar pemasok + profil peta (Fase 2, 2026-10-14). Dipakai
// layer pemasok di peta dan halaman Pemasok. Data ini nyaris statis: diambil
// SEKALI per sesi (staleTime panjang, tanpa polling) — alasan pemasok tidak
// ditempelkan ke payload `GET /balance/map` yang di-poll berkala.
//
// `maxDistanceKm` (Fase 7b): memakai penyaring server supaya jumlah yang
// disembunyikan datang dari server (`reach.excluded_out_of_reach`), bukan dari
// hitungan UI. Tanpa parameter ini seluruh tabel dikirim (jarak tetap dilaporkan
// per baris), dan UI-lah yang memutuskan apa yang ditampilkan.
//
// `commodity` (Fase 7b): ikut dikirim ke server supaya `reach.excluded_out_of_reach`
// berlaku untuk SUBSET yang sedang dilihat. Kalau penyaringan komoditas dilakukan
// di klien setelah server menyaring jarak, angka "N di luar jangkauan" akan
// bercerita tentang komoditas lain — angka yang tidak boleh tampil di layar.
export async function fetchSuppliers(
  token: string,
  maxDistanceKm?: number | null,
  commodity?: string | null
) {
  const jarak = typeof maxDistanceKm === "number" ? `&max_distance_km=${maxDistanceKm}` : "";
  const komoditas = commodity ? `&commodity=${encodeURIComponent(commodity)}` : "";
  return request(`/suppliers?limit=200${komoditas}${jarak}`, {
    headers: { Authorization: `Bearer ${token}` },
 });
}

// GET /supplier-routes — garis JALUR KIRIMAN pemasok → tujuan (Fase 10).
// Geometrinya datang dari cache OSRM di server (diisi saat sinkronisasi), jadi
// peta tidak pernah memanggil OSRM sendiri dan demo tetap jalan tanpa internet.
export async function fetchSupplierRoutes(
  token: string,
  commodity?: string | null,
  location?: string | null
) {
  const komoditas = commodity ? `&commodity=${encodeURIComponent(commodity)}` : "";
  const lokasi = location ? `&location=${encodeURIComponent(location)}` : "";
  return request(`/supplier-routes?limit=200${komoditas}${lokasi}`, {
    headers: { Authorization: `Bearer ${token}` },
 });
}

// --- P1 Merkle ledger (paket 1-6, keputusan Roy 2026-10-09) ---

// GET /ledger/verify — verifikasi rantai hash dari genesis (read-only).
// {valid, blocks, head?, broken_at?, reason?}
export async function verifyLedger(token: string) {
  return request("/ledger/verify", {
    headers: { Authorization: `Bearer ${token}` },
 });
}

// --- P2/P3 dossier konten-addressed + ECDSA ---

// GET /decisions/{id}/dossier — bukti keputusan + alamat konten + ttd.
export async function fetchDossier(decisionId: string, token: string) {
  return request(`/decisions/${decisionId}/dossier`, {
    headers: { Authorization: `Bearer ${token}` },
 });
}

// --- Admin / Pengaturan (S4-11) -------------------------------------------
// Backend membalas snake_case (kontrak domain); komponen memakai camelCase.

function mapAdminUser(raw: any) {
  return {
    id: String(raw.id),
    name: String(raw.name ?? ""),
    email: String(raw.email ?? ""),
    role: String(raw.role ?? ""),
    locationId: raw.location_id === null || raw.location_id === undefined ? null : String(raw.location_id),
    locationName: raw.location_name ?? null,
  };
}

function mapAdminLocation(raw: any) {
  return {
    id: String(raw.id),
    name: String(raw.name ?? ""),
    region: String(raw.region ?? ""),
    latitude: Number(raw.latitude),
    longitude: Number(raw.longitude),
  };
}

export async function fetchAdminUsers(token: string) {
  const body = await request("/admin/users", {
    headers: { Authorization: `Bearer ${token}` },
 });
  return (body.users ?? []).map(mapAdminUser);
}

export async function fetchAdminLocations(token: string) {
  const body = await request("/admin/locations", {
    headers: { Authorization: `Bearer ${token}` },
 });
  return (body.locations ?? []).map(mapAdminLocation);
}

export async function updateAdminUser(
  userId: string,
  payload: Record<string, string | null>,
  token: string,
) {
  const body = await request(`/admin/users/${userId}`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
 });
  return mapAdminUser(body.user);
}

export async function updateAdminLocation(
  locationId: string,
  payload: Record<string, string | number>,
  token: string,
) {
  const body = await request(`/admin/locations/${locationId}`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
 });
  return mapAdminLocation(body.location);
}

// --- Demo Control sederhana (keputusan Roy 2026-10-19) ---
// Panel demo tidak lagi memilih skenario: satu tombol menjalankan agent, satu
// endpoint membaca buktinya dari DB. Komoditas & lokasi TIDAK dikirim dari UI
// secara bawaan — backend memakai `beras` + lokasi SPPG akun yang login, supaya
// cakupan peran tidak bisa dilanggar lewat payload.

/**
 * `POST /demo/agent/run` — jalankan pipeline agent penuh (DETECT → SUPERVISE).
 * Tidak ada approval/eksekusi: keputusan lahir `proposed`.
 */
export async function runDemoAgent(
  token: string,
  { commodity, ttlMinutes }: { commodity?: string; ttlMinutes?: number } = {}
) {
  const payload: Record<string, unknown> = {};
  if (commodity) payload.commodity = commodity;
  if (ttlMinutes) payload.ttl_minutes = ttlMinutes;
  return request("/demo/agent/run", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify(payload),
 });
}

/** `GET /demo/agent/commodities` — pilihan dropdown: nama yang ADA di database. */
export async function fetchDemoAgentCommodities(token: string) {
  return request("/demo/agent/commodities", { headers: authHeaders(token) });
}

/** `GET /demo/agent/last-run` — bukti putaran agent terakhir, dibaca dari DB. */
export async function fetchDemoAgentLastRun(token: string) {
  return request("/demo/agent/last-run", { headers: authHeaders(token) });
}
