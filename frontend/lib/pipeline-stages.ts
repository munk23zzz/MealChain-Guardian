// Metadata sepuluh tahap pipeline (dokumen `06-agent-log.md` §2.3).
//
// Nama tahap BUKAN karangan UI: ia dipaku `CheckConstraint
// agent_traces_step_name_check` di backend. Tiga tahap melibatkan LLM: VERIFY
// (menilai konsistensi), ANALYZE (hipotesis sebab + rekomendasi), SUPERVISE
// (narasi akhir); sisanya tool deterministik. Karena itu kolom `tool` di sini
// menyebut jenis pelaksananya, bukan nama model.

export interface StageMeta {
  code: string;
  label: string;
  tool: string;
  /** Kalimat rincian saat chip dibuka. */
  detail: string;
}

export const PIPELINE_STAGES: ReadonlyArray<StageMeta> = [
  {
    code: "DETECT",
    label: "Mendeteksi kondisi",
    tool: "Tool deterministik (demand.snapshot, price.signal)",
    detail: "Membaca kebutuhan dan sinyal harga dari catatan transaksi, bukan dari model.",
  },
  {
    code: "VERIFY",
    label: "Verifikasi independen",
    tool: "Verifier Agent (persona skeptis)",
    detail:
      "Agent kedua memeriksa usulan tanpa melihat penalaran Supervisor — pengawasan yang memeriksa dirinya sendiri bukan pengawasan.",
  },
  {
    code: "TRACE",
    label: "Mencatat jejak",
    tool: "Tool deterministik (rekaman langkah)",
    detail: "Menyimpan langkah apa adanya supaya bisa dibaca ulang.",
  },
  {
    code: "PREDICT",
    label: "Memproyeksikan",
    tool: "Tool deterministik (proyeksi)",
    detail: "Perkiraan kebutuhan periode berikutnya dari data tercatat.",
  },
  {
    code: "OPTIMIZE",
    label: "Mengoptimalkan",
    tool: "Tool deterministik (rekomendasi engine)",
    detail: "Menyusun usulan penyeimbangan beserta biaya amannya.",
  },
  {
    code: "ANALYZE",
    label: "Menjelaskan sebab",
    tool: "Analysis Agent (LLM)",
    detail:
      "Model membaca fakta yang sudah dihitung kode (stok, kebutuhan, pemasok terpilih, prakiraan) lalu menyimpulkan sebab kekurangan dan satu rekomendasi. Angka tidak dihitung model; angka yang tidak ada di fakta ditandai di jejak.",
  },
  {
    code: "DECIDE",
    label: "Menetapkan usulan",
    tool: "Tool deterministik (ambang keputusan)",
    detail: "Menetapkan usulan final yang akan dimintakan approval.",
  },
  {
    code: "SUPERVISE",
    label: "Pengawasan agent",
    tool: "Supervisor Agent (LLM)",
    detail:
      "Agent penalar utama menarasikan usulan untuk manusia. Angka safety-critical tetap dari tool deterministik.",
  },
  {
    code: "ACT",
    label: "Mengeksekusi",
    tool: "Tool deterministik + gerbang approval manusia",
    detail:
      "Eksekusi hanya setelah approval. Jejaknya berupa blok ledger `action = execute`, bukan baris agent_traces.",
  },
  {
    code: "LEARN",
    label: "Belajar dari hasil",
    tool: "Tool deterministik (umpan balik)",
    detail: "Mencatat hasil untuk evaluasi berikutnya.",
  },
];

export const STAGE_CODES = PIPELINE_STAGES.map((s) => s.code);

export function stageMeta(code: string): StageMeta | null {
  const target = (code ?? "").toLowerCase();
  return PIPELINE_STAGES.find((s) => s.code.toLowerCase() === target) ?? null;
}
