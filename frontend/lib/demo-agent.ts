/**
 * Teks blok bukti Demo Control — MURNI (tanpa DOM), supaya bisa diuji vitest.
 *
 * Aturan yang dijaga di sini (sama dengan lib/demo-data.ts):
 * - Tidak ada angka karangan: setiap nilai berasal dari payload
 *   `GET /demo/agent/last-run` (yang membaca DB). Fungsi di sini hanya
 *   MERINGKAS, tidak menambah fakta baru.
 * - Keadaan yang tidak tercatat dikatakan apa adanya ("belum ada",
 *   "tidak tercatat") — bukan disembunyikan atau diganti tanda hubung.
 */

// Urutan & label agen dipakai bersama panel Agent Log: satu sumber kebenaran
// supaya "sembilan agen" tidak berbeda susunannya di dua layar.
import { SWARM_AGENTS } from "./agent-swarm";
import type { LangkahAgent } from "./agent-stream";

export type AgentStep = {
  step_name: string;
  tool_called?: string | null;
  duration_ms?: number | null;
};

export type AgentSupervisor = {
  status?: string | null;
  provider?: string | null;
  fallback_used?: boolean | null;
  summary?: string | null;
};

export type AgentReview = {
  status?: string | null;
  error?: string | null;
  run_id?: string | null;
};

/** Bukti pengadaan pemasok (dibaca dari trace DB, bukan dihitung UI). */
export type AgentSupplier = {
  supplier_id?: string | null;
  name?: string | null;
  leg_km?: string | number | null;
  available_kg?: string | number | null;
  quote_price_per_kg?: string | number | null;
  reliability?: string | number | null;
  capacity_kg_per_week?: string | number | null;
  rank?: number | null;
  candidates_total?: number | null;
};

export type AgentGap = {
  supply_kg?: string | null;
  demand_kg?: string | null;
  gap_kg?: string | null;
  suppliers_total?: number | null;
  suppliers_eligible?: number | null;
};

export type AgentRun = {
  found: boolean;
  mode?: string | null;
  supplier?: AgentSupplier | null;
  supply_gap?: AgentGap | null;
  decision_id?: string | null;
  status?: string | null;
  created_at?: string | null;
  expires_at?: string | null;
  quantity_kg?: string | null;
  commodity?: string | null;
  source_location?: string | null;
  target_location?: string | null;
  verifier_note?: string | null;
  steps?: AgentStep[];
  agents?: DemoAgent[];
  agents_run_id?: string | null;
  supervisor?: AgentSupervisor;
  agent_review?: AgentReview;
};

/**
 * Komoditas awal untuk dropdown: `beras` bila memang ada di daftar server,
 * kalau tidak pilihan PERTAMA dari server (bukan tebakan klien). Daftar kosong
 * → string kosong, supaya UI menampilkan "belum ada pilihan" alih-alih memaksa
 * satu nama yang tidak punya data.
 */
export function defaultCommodity(daftar: string[], disukai = "beras"): string {
  if (!Array.isArray(daftar) || daftar.length === 0) return "";
  return daftar.includes(disukai) ? disukai : daftar[0];
}

// Catatan 28 Okt 2026: penanda "Semua komoditas" DIHAPUS. Panel sekarang selalu
// menyebut satu komoditas nyata; server tetap menerima permintaan tanpa
// `commodity` (perilaku lama dipertahankan untuk pemanggil lain), tetapi UI
// tidak lagi menawarkannya — operator harus tahu komoditas mana yang dinilai.

export type PutaranKomoditas = {
  created?: Array<{ commodity?: string | null; decision_id?: string | null }>;
  skipped?: Array<{ commodity?: string | null; reason?: string | null }>;
};

/**
 * Id keputusan yang lahir dari satu putaran "Jalankan agent", kalau ada.
 *
 * Panel memakainya untuk membaca bukti SECARA EKSPLISIT: pencarian "putaran
 * terbaru" bisa kosong sesaat karena server menyelesaikan commit jejak
 * beberapa milidetik setelah balasan HTTP (gejala 28 Okt 2026: kartu Bukti
 * agent kosong tepat setelah berhasil menjalankan wortel).
 *
 * Backend baru mengirim `created[0].decision_id`; backend lama hanya
 * `decision_id` di akar payload. Selain itu → `null`, bukan tebakan.
 */
export function idKeputusanPutaran(outcome: unknown): string | null {
  if (!outcome || typeof outcome !== "object") return null;
  const isi = outcome as PutaranKomoditas & { decision_id?: string | null };
  const dibuat = Array.isArray(isi.created) ? isi.created : [];
  for (const baris of dibuat) {
    const id = String(baris?.decision_id ?? "").trim();
    if (id) return id;
  }
  const akar = String(isi.decision_id ?? "").trim();
  return akar || null;
}

/**
 * Ringkasan satu putaran "Jalankan agent" untuk dibaca operator.
 *
 * Murni: setiap angka dan nama diambil dari payload server (`created`/
 * `skipped`), tidak ada tebakan. Payload lama (tanpa kedua kunci itu) → `null`
 * supaya panel tidak menampilkan baris kosong yang berpura-pura jadi bukti.
 * Alasan penolakan dipendekkan supaya tidak memenuhi layar, tetapi tidak
 * dihapus seluruhnya — tanpa sebab, "dilewati" tidak bisa diperiksa.
 */
export function ringkasPutaran(outcome: unknown, maksAlasan = 140): string | null {
  if (!outcome || typeof outcome !== "object") return null;
  const isi = outcome as PutaranKomoditas;
  const dibuat = Array.isArray(isi.created) ? isi.created : null;
  const dilewati = Array.isArray(isi.skipped) ? isi.skipped : null;
  if (dibuat === null && dilewati === null) return null;

  const namaDibuat = (dibuat ?? [])
    .map((baris) => String(baris?.commodity ?? "").trim())
    .filter(Boolean);
  const bagian: string[] = [];
  if (namaDibuat.length > 0) {
    bagian.push(
      `${namaDibuat.length} keputusan dibuat${namaDibuat.length <= 4 ? ` (${namaDibuat.join(", ")})` : ""}`
    );
  } else {
    bagian.push("0 keputusan dibuat");
  }
  for (const baris of dilewati ?? []) {
    const nama = String(baris?.commodity ?? "").trim() || "komoditas tanpa nama";
    const alasan = String(baris?.reason ?? "").trim();
    const pendek = alasan.length > maksAlasan ? `${alasan.slice(0, maksAlasan - 1)}…` : alasan;
    bagian.push(pendek ? `${nama} dilewati: ${pendek}` : `${nama} dilewati`);
  }
  return bagian.join(" · ");
}

/** Angka dari DB → label Indonesia. `null` tetap `—`, tidak diubah jadi 0. */
export function quantityLabel(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const angka = typeof value === "number" ? value : Number(String(value));
  if (!Number.isFinite(angka)) return "—";
  const [utuh, desimal] = angka.toFixed(2).split(".");
  const berkelompok = utuh.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  // Dua desimal nol tidak menambah informasi (1.257,00 kg); angka di DB
  // memang dua desimal, jadi yang dipangkas hanya nol yang tidak bermakna.
  const pecahan = desimal === "00" ? "" : `,${desimal}`;
  return `${berkelompok}${pecahan} kg`;
}

/** Angka desimal DB → gaya Indonesia (titik ribuan, koma desimal). */
function angkaIndo(value: string | number, desimal = 2): string | null {
  const angka = typeof value === "number" ? value : Number(String(value));
  if (!Number.isFinite(angka)) return null;
  const [utuh, pecahan] = angka.toFixed(desimal).split(".");
  const berkelompok = utuh.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  const sisa = pecahan && Number(pecahan) !== 0 ? `,${pecahan}` : "";
  return `${berkelompok}${sisa}`;
}

/** Harga penawaran pemasok per kg. `null` tetap "tidak tercatat", bukan Rp 0. */
export function rupiahLabel(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "tidak tercatat";
  const teks = angkaIndo(value);
  return teks === null ? "tidak tercatat" : `Rp ${teks}`;
}

/** Jarak angkut pemasok → SPPG. Kosong berarti koordinat belum lengkap. */
export function kmLabel(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "tidak tercatat";
  const teks = angkaIndo(value, 3);
  return teks === null ? "tidak tercatat" : `${teks} km`;
}

/** `Cianjur → Jakarta`, atau satu sisi saja bila pasangannya kosong. */
export function routeLabel(
  source: string | null | undefined,
  target: string | null | undefined
): string {
  if (source && target) return `${source} → ${target}`;
  return source || target || "—";
}

export type Fact = { label: string; value: string };

/** Fakta ringkas blok bukti. Urutan tetap supaya kartu tidak "melompat". */
export function proofFacts(run: AgentRun | null): Fact[] {
  if (!run || !run.found) return [];
  // Sejak 2026-10-19 pipeline demo menilai PEMASOK → SPPG. Yang ditampilkan
  // adalah pemasok yang benar-benar dinilai beserta jarak angkutnya, bukan
  // rute antar SPPG (kolom `source_location` memang NULL untuk pengadaan).
  if (run.mode === "supplier_procurement") {
    const pemasok = run.supplier ?? null;
    const gap = run.supply_gap ?? null;
    return [
      { label: "Komoditas", value: run.commodity || "—" },
      { label: "Pemasok", value: pemasok?.name || "tidak tercatat" },
      { label: "SPPG", value: run.target_location || "—" },
      { label: "Kuantitas", value: quantityLabel(run.quantity_kg) },
      { label: "Kekurangan", value: quantityLabel(gap?.gap_kg) },
      { label: "Stok pemasok", value: quantityLabel(pemasok?.available_kg) },
      { label: "Jarak pemasok → SPPG", value: kmLabel(pemasok?.leg_km) },
      { label: "Harga penawaran", value: `${rupiahLabel(pemasok?.quote_price_per_kg)} /kg` },
      { label: "Status keputusan", value: run.status || "—" },
      {
        label: "Verdict verifier",
        value: run.verifier_note ? run.verifier_note.toUpperCase() : "tidak tercatat",
      },
    ];
  }
  return [
    { label: "Komoditas", value: run.commodity || "—" },
    { label: "Rute", value: routeLabel(run.source_location, run.target_location) },
    { label: "Kuantitas", value: quantityLabel(run.quantity_kg) },
    { label: "Status keputusan", value: run.status || "—" },
    {
      label: "Verdict verifier",
      value: run.verifier_note ? run.verifier_note.toUpperCase() : "tidak tercatat",
    },
  ];
}

/** Nama langkah pipeline yang BENAR-BENAR tercatat; urutannya dari server.
 *  Slug alat (`tool_called`) sengaja TIDAK ikut: pemilik 21 Okt meminta daftar
 *  ini hanya menampilkan nama langkah/agent, bukan istilah internal seperti
 *  `evaluate_safety` atau `supervisor.narration`. */
export function stepNames(run: AgentRun | null): string[] {
  const langkah = run?.steps ?? [];
  return langkah.map((s) => (s.step_name && s.step_name.trim() ? s.step_name : "—"));
}

/**
 * Langkah TERSIMPAN (`agent_traces`) → baris log proses pengambilan data.
 *
 * Dipakai saat putaran sudah ditutup / halaman dimuat ulang: kanal SSE tidak
 * menyimpan apa pun, yang tersisa hanya baris jejak. Jam (`at`) sengaja string
 * kosong karena `agent_traces` tidak menyimpan waktu per langkah — terminal
 * mencetak kolom jam kosong, bukan jam karangan. `ringkas` juga kosong: server
 * hanya menyiarkan ringkasan pada kanal hidup, tidak menyimpannya per langkah.
 */
export function langkahTersimpan(run: AgentRun | null): LangkahAgent[] {
  const langkah = run?.steps ?? [];
  return langkah.map((s) => ({
    step: s.step_name && s.step_name.trim() ? s.step_name : "—",
    tool: s.tool_called ?? null,
    ringkas: "",
    at: "",
  }));
}

/** Kalimat narasi supervisor — menyebut provider yang benar-benar menjawab. */
export function supervisorLine(sup: AgentSupervisor | null | undefined): string {
  if (!sup || !sup.status || sup.status === "missing") {
    return "Narasi supervisor tidak tercatat pada putaran ini.";
  }
  const provider = sup.provider ? ` · ${sup.provider}` : "";
  const fallback = sup.fallback_used ? " (jalur cadangan dipakai)" : "";
  if (sup.status === "narrated") {
    return `Narasi supervisor selesai${provider}${fallback}.`;
  }
  if (sup.status === "unavailable") {
    return `Narasi supervisor tidak tersedia (provider tidak dikonfigurasi)${provider}.`;
  }
  return `Narasi supervisor berstatus ${sup.status}${provider}${fallback}.`;
}

/** Kalimat review sembilan agen — jujur soal runtime yang tidak terjangkau. */
export function agentReviewLine(review: AgentReview | null | undefined): string {
  const status = review?.status;
  if (!status || status === "missing") {
    return "Review sembilan agen tidak tercatat pada putaran ini.";
  }
  if (status === "completed" || status === "partial") {
    const run = review?.run_id ? ` · run ${review.run_id.slice(0, 8)}` : "";
    return `Review sembilan agen selesai (${status})${run}.`;
  }
  if (status === "vetoed") {
    // Guardian memblokir: review tetap berjalan lengkap, hasilnya tidak boleh
    // dieksekusi. Jangan dilaporkan sebagai "selesai" biasa.
    const run = review?.run_id ? ` · run ${review.run_id.slice(0, 8)}` : "";
    return `Review sembilan agen selesai dengan veto guardian (vetoed)${run}.`;
  }
  if (status === "unavailable") {
    // Detail teknis (alamat runtime) sengaja TIDAK ditampilkan di layar;
    // panel ini membuktikan pipeline utama, bukan kesehatan infrastruktur.
    return "Review sembilan agen tidak terjangkau (unavailable) — pipeline utama di atas tetap selesai.";
  }
  if (status === "disabled") {
    return "Review sembilan agen dimatikan di konfigurasi (disabled).";
  }
  return `Review sembilan agen berstatus ${status} — pipeline utama di atas tetap selesai.`;
}

/** Kalimat progres saat agent bekerja; detik berasal dari jam klien. */
export function elapsedLine(detik: number): string {
  const aman = Number.isFinite(detik) && detik >= 0 ? Math.floor(detik) : 0;
  if (aman < 1) return "Agent mulai bekerja…";
  return `Agent bekerja… ${aman} detik`;
}

/** Nama tombol saat sibuk — satu bentuk, dipakai tombol dan tes. */
export function runButtonLabel(busy: boolean): string {
  return busy ? "Agent bekerja…" : "Jalankan agent";
}

/** Satu worker review seperti dikirim `/demo/agent/last-run`. */
export type DemoAgent = {
  key: string;
  label: string;
  status: string;
  /** Verdict audit (kartu verifier): consistent | flagged | unavailable. */
  verdict?: string | null;
  duration_ms?: number | null;
  warnings?: number | null;
  summary?: string | null;
};

export type DemoAgentCard = {
  key: string;
  label: string;
  state: "ok" | "running" | "limited" | "flagged" | "failed" | "idle";
  statusLabel: string;
  duration: string;
  warnings: string;
  /** Baris fakta kartu. Worker: Durasi + Peringatan. Supervisor: Provider + Peringatan. */
  meta: Fact[];
  /** Ringkasan narasi supervisor; kartu worker/verifier tidak punya (null). */
  note: string | null;
};

const AGEN_STATE: Record<string, DemoAgentCard["state"]> = {
  ok: "ok",
  completed: "ok",
  degraded: "limited",
  limited: "limited",
  error: "failed",
  failed: "failed",
};

const AGEN_LABEL: Record<DemoAgentCard["state"], string> = {
  ok: "Selesai",
  running: "Berjalan",
  limited: "Terbatas",
  // Audit SELESAI dan menandai masalah: itu hasil definitif, bukan "terbatas".
  // Label ini hanya dipakai bila verdict audit benar-benar `flagged`.
  flagged: "Ditinjau",
  failed: "Gagal",
  idle: "Tidak dijalankan",
};

/**
 * Keadaan narasi supervisor. `narrated`/`unavailable` bukan status worker, jadi
 * labelnya pun sendiri — tanpa peta ini narasi yang berhasil tampil "Terbatas".
 */
const SUPERVISOR_STATE: Record<string, DemoAgentCard["state"]> = {
  narrated: "ok",
  unavailable: "limited",
  failed: "failed",
  error: "failed",
};

const SUPERVISOR_LABEL: Record<string, string> = {
  narrated: "Narasi selesai",
  unavailable: "Narasi tidak tersedia",
};

const SUPERVISOR_KEY = "supervisor";

function durasiAgen(ms: number | null | undefined): string {
  if (typeof ms !== "number" || !Number.isFinite(ms) || ms < 0) return "—";
  if (ms < 1000) return `${Math.round(ms)} md`;
  return `${(ms / 1000).toFixed(1).replace(".", ",")} dtk`;
}

function teksAtau(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed || null;
}

function faktaWorker(duration: string, warnings: string): Fact[] {
  return [
    { label: "Durasi", value: duration },
    { label: "Peringatan", value: warnings },
  ];
}

/** Kartu untuk agen yang tidak dikirim payload: tetap ada, tanpa angka. */
function kartuKosong(agent: { key: string; label: string }): DemoAgentCard {
  return {
    key: agent.key,
    label: agent.label,
    state: "idle",
    statusLabel: "Belum tercatat",
    duration: "—",
    warnings: "—",
    meta: faktaWorker("—", "—"),
    note: null,
  };
}

/**
 * Kartu supervisor — sumbernya `run.supervisor` (status narasi, provider,
 * ringkasan), bukan baris worker. Nilai yang tidak ada tetap "—"/"Belum
 * tercatat"; tidak ada 0 atau "0 peringatan" karangan.
 */
function kartuSupervisor(
  sup: AgentSupervisor | null | undefined,
  sedangJalan: boolean
): DemoAgentCard {
  const label = SWARM_AGENTS.find((agent) => agent.key === SUPERVISOR_KEY)?.label ?? "Supervisor";
  const provider = teksAtau(sup?.provider) ?? "—";
  if (sedangJalan) {
    // Putaran baru: narasi lama sudah basi, jangan ditampilkan.
    return {
      key: SUPERVISOR_KEY,
      label,
      state: "running",
      statusLabel: "Berjalan",
      duration: "—",
      warnings: "—",
      meta: [
        { label: "Provider", value: provider },
        { label: "Peringatan", value: "—" },
      ],
      note: null,
    };
  }
  const status = teksAtau(sup?.status)?.toLowerCase() ?? null;
  const dikenal = status ? SUPERVISOR_STATE[status] ?? null : null;
  const state: DemoAgentCard["state"] = dikenal ?? "idle";
  return {
    key: SUPERVISOR_KEY,
    label,
    state,
    statusLabel:
      (status ? SUPERVISOR_LABEL[status] : null) ??
      (dikenal ? AGEN_LABEL[dikenal] : "Belum tercatat"),
    // Payload supervisor tidak membawa durasi/peringatan: "—", bukan 0.
    duration: "—",
    warnings: "—",
    meta: [
      { label: "Provider", value: provider },
      { label: "Peringatan", value: "—" },
    ],
    note: teksAtau(sup?.summary),
  };
}

/**
 * Kartu sembilan agen (dipakai bersama panel Agent Log).
 *
 * 29 Okt 2026: blok "Bukti agent" di Demo Control TIDAK lagi merender kartu
 * ini — panel itu kini hanya terminal "Log proses pengambilan data". Fungsi
 * dipertahankan karena kontrak datanya masih diuji (`demo-agent.test.ts`);
 * menghapusnya butuh pembersihan terpisah bersama tesnya.
 *
 * Urutan
 * pipeline: tujuh worker → supervisor → verifier.
 *
 * Selalu sembilan kartu bila putaran punya baris review. Status hanya dari data
 * yang benar-benar ada:
 * - baris review tersimpan → status aslinya (Selesai/Terbatas/Gagal);
 * - belum ada baris, tetapi putaran sedang berjalan → "Berjalan";
 * - belum ada baris dan tidak ada putaran → "Tidak dijalankan"/"Belum tercatat".
 * Angka kosong tetap "—", bukan 0.
 */
export function demoAgentCards(
  run: AgentRun | null,
  sedangJalan = false
): DemoAgentCard[] {
  const daftar = Array.isArray(run?.agents) ? run!.agents! : [];
  // Tanpa satu pun baris review, blok bukti tidak mengarang kartu: pemanggil
  // menampilkan kalimat "review belum tercatat" alih-alih sembilan kartu kosong.
  if (daftar.length === 0) return [];
  const byKey = new Map<string, DemoAgent>();
  for (const agen of daftar) {
    if (agen?.key) byKey.set(agen.key, agen);
  }
  return SWARM_AGENTS.map((agent) => {
    if (agent.key === SUPERVISOR_KEY) {
      return kartuSupervisor(run?.supervisor, sedangJalan);
    }
    const agen = byKey.get(agent.key);
    if (!agen) return kartuKosong(agent);
    // Putaran baru sedang berjalan: baris review ditulis sekaligus di akhir,
    // jadi selama itu semua kartu jujur berstatus "Berjalan" — bukan hasil
    // putaran sebelumnya yang sudah basi.
    if (sedangJalan) {
      return {
        key: agen.key,
        // Nama agen dari SWARM_AGENTS (English), BUKAN `agen.label` dari
        // payload: backend mengirim label Indonesia, dan dua nama untuk satu
        // agen membuat kartu ini berbeda dari Agent Log.
        label: agent.label,
        state: "running" as const,
        statusLabel: "Berjalan",
        duration: "—",
        warnings: "—",
        meta: faktaWorker("—", "—"),
        note: null,
      };
    }
    const verdict = (agen.verdict || "").toLowerCase();
    // Verdict `flagged` = audit SELESAI dan menandai masalah → label definitif
    // "Ditinjau". Tanpa ini kartu verifier memakai `degraded` → "Terbatas",
    // sama dengan keadaan "model tidak dikonfigurasi" yang belum mengaudit apa pun.
    const state: DemoAgentCard["state"] =
      verdict === "flagged"
        ? "flagged"
        : AGEN_STATE[(agen.status || "").toLowerCase()] ?? "idle";
    const dikenal = state !== "idle";
    const duration = dikenal ? durasiAgen(agen.duration_ms) : "—";
    const warnings =
      dikenal && typeof agen.warnings === "number" ? `${agen.warnings} peringatan` : "—";
    return {
      key: agen.key,
      label: agent.label,
      state,
      statusLabel: AGEN_LABEL[state],
      duration,
      warnings,
      meta: faktaWorker(duration, warnings),
      // Kartu verifier memuat kesimpulan auditnya; kartu worker tidak, karena
      // narasi panjangnya sudah ada di detail Agent Log.
      note: agen.key === "verifier" ? teksAtau(agen.summary) : null,
    };
  });
}

/**
 * Ringkasan cadangan untuk putaran SATU komoditas.
 *
 * Backend yang belum mengirim `created`/`skipped` menjawab dengan
 * `decision_id` + `trace_steps`. Tanpa baris ini, putaran yang berhasil tampak
 * seperti tidak terjadi apa-apa — persis keluhan "tidak bisa menjalankan agent"
 * (28 Okt 2026). Murni: nomor keputusan dan jumlah langkah diambil dari
 * payload; kalau payload tidak punya keduanya, kembalikan `null` (jangan
 * mengarang bukti).
 */
export function ringkasSatuKomoditas(outcome: unknown, komoditas: string): string | null {
  if (!outcome || typeof outcome !== "object") return null;
  const isi = outcome as {
    decision_id?: string | null;
    commodity?: string | null;
    trace_steps?: unknown[] | null;
  };
  const id = String(isi.decision_id ?? "").trim();
  if (!id) return null;
  const nama = String(isi.commodity ?? "").trim() || komoditas || "komoditas";
  const langkah = Array.isArray(isi.trace_steps) ? isi.trace_steps.length : 0;
  return langkah > 0
    ? `1 keputusan dibuat (${nama}) · ${langkah} langkah agent tercatat · id ${id.slice(0, 8)}`
    : `1 keputusan dibuat (${nama}) · id ${id.slice(0, 8)}`;
}
