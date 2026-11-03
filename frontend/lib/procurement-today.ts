/**
 * Tile "Pengadaan & eksekusi" di Overview — satu tempat untuk angka + kalimat.
 *
 * Kenapa modul murni: sama seperti `overview-kpi.ts`, aturan kejujuran angka
 * harus bisa diuji tanpa DOM. Kesepuluh aturannya:
 *
 *  1. angka hanya dari data server (`/procurement/summary`), tidak ada proksi;
 *  2. periode dan zona waktu ditulis di label tile, bukan disembunyikan;
 *  3. satuan ditulis ("PO", "keputusan", "batch");
 *  4. keadaan belum tahu (memuat/galat/belum ada data) = "—";
 *  5. keadaan memang kosong = "belum ada", BUKAN "0" yang terbaca "tidak ada
 *     pekerjaan" padahal artinya "belum pernah terjadi";
 *  6. nilai komitmen ditulis dalam rupiah penuh apa adanya dari server;
 *  7. "terakhir" hanya ditulis kalau server memang mengirimnya.
 */
import { formatDateTime } from "./datetime";

export type ProcurementSummary = {
  period: {
    key: string | null;
    label: string | null;
    timezone: string;
    start: string;
    end: string;
  };
  scope: { location_id: string | null; role: string };
  purchase_orders: {
    state: string;
    count: number;
    total_value: string;
    currency: string;
    by_status: Record<string, number>;
    last: {
      po_number: string;
      status: string;
      created_at: string;
      value: string;
    } | null;
  };
  decisions_executed: {
    state: string;
    count: number;
    last_step_at: string | null;
  };
  batches_dispatched: {
    state: string;
    count: number;
    last_dispatched_at: string | null;
  };
  /** Kg yang benar-benar masuk stok: hanya penerimaan berstatus disetujui. */
  receipts: {
    state: string;
    count: number;
    kg: string;
    unit: string;
    last: { kg: string; reviewed_at: string } | null;
  };
};

export type ProcurementTile = {
  id: "po" | "eksekusi" | "truk" | "terima";
  label: string;
  value: string;
  unit: string;
  foot: string;
  mini: string;
  tone: "neutral" | "ok";
};

/** Label rentang yang dipakai tile — satuan waktunya eksplisit. */
export function rentangLabel(kunci: string | null | undefined): string {
  switch (kunci) {
    case "today":
      return "hari ini (WIB)";
    case "7d":
      return "7 hari (WIB)";
    case "1bulan":
      return "1 bulan (WIB)";
    default:
      return "periode ini";
  }
}

/** Angka apa adanya; nilai tak terbaca TIDAK diubah jadi 0. */
function hitung(nilai: unknown): number | null {
  const n = typeof nilai === "string" ? Number(nilai) : (nilai as number);
  if (typeof n !== "number" || !Number.isFinite(n)) return null;
  return Math.max(0, Math.trunc(n));
}

/** "9750000.00" → "Rp9.750.000". Nilai tak terbaca → "—". */
export function formatRupiah(nilai: unknown): string {
  const n = typeof nilai === "string" ? Number(nilai) : (nilai as number);
  if (typeof n !== "number" || !Number.isFinite(n)) return "—";
  return `Rp${n.toLocaleString("id-ID", { maximumFractionDigits: 0 })}`;
}

/** "425.50" → "425,5" (kg). Nilai tak terbaca → "—". */
export function formatKg(nilai: unknown): string {
  const n = typeof nilai === "string" ? Number(nilai) : (nilai as number);
  if (typeof n !== "number" || !Number.isFinite(n)) return "—";
  return n.toLocaleString("id-ID", { maximumFractionDigits: 2 });
}

/**
 * Isi tiga tile. `loading` mengalahkan `data` (angka lama tidak boleh tampil
 * seolah angka sekarang); `error` juga, supaya kegagalan tidak terbaca "kosong".
 */
export function procurementTiles(
  data: ProcurementSummary | null,
  opsi: { loading?: boolean; error?: string | null } = {}
): ProcurementTile[] {
  const rentang = rentangLabel(data?.period?.key ?? "today");
  const belumTahu = opsi.loading
    ? "memuat angka pengadaan…"
    : opsi.error
      ? "gagal memuat angka pengadaan"
      : "belum ada data pengadaan";

  if (opsi.loading || opsi.error || !data) {
    return [
      {
        id: "po",
        label: `PO terbit · ${rentang}`,
        value: "—",
        unit: "PO",
        foot: belumTahu,
        mini: "—",
        tone: "neutral",
      },
      {
        id: "eksekusi",
        label: `Keputusan dieksekusi · ${rentang}`,
        value: "—",
        unit: "keputusan",
        foot: belumTahu,
        mini: "—",
        tone: "neutral",
      },
      {
        id: "truk",
        label: `Truk berangkat · ${rentang}`,
        value: "—",
        unit: "batch",
        foot: belumTahu,
        mini: "—",
        tone: "neutral",
      },
      {
        id: "terima",
        label: `Kg diterima · ${rentang}`,
        value: "—",
        unit: "kg",
        foot: belumTahu,
        mini: "—",
        tone: "neutral",
      },
    ];
  }

  const po = hitung(data.purchase_orders?.count);
  const eksekusi = hitung(data.decisions_executed?.count);
  const truk = hitung(data.batches_dispatched?.count);
  // Kg bukan hitungan: nilai pecahan ("425.50") harus tetap terbaca 425,5 kg,
  // dan nilai tak terbaca TIDAK boleh menjadi 0.
  const terimaKg = Number.isFinite(Number(data.receipts?.kg))
    ? Math.max(0, Number(data.receipts?.kg))
    : null;
  const terima = hitung(data.receipts?.count);
  const diterimaTerakhir = data.receipts?.last ?? null;
  const nilai = formatRupiah(data.purchase_orders?.total_value);
  const terakhirPo = data.purchase_orders?.last ?? null;

  return [
    {
      id: "po",
      label: `PO terbit · ${rentang}`,
      value: po === null ? "—" : po === 0 ? "belum ada" : String(po),
      unit: "PO",
      foot:
        po === null
          ? "jumlah PO tidak terbaca"
          : po === 0
            ? `tidak ada PO pada ${rentang}`
            : `nilai komitmen ${nilai} pada ${rentang}`,
      mini:
        po === null
          ? "—"
          : terakhirPo
            ? `terakhir ${terakhirPo.po_number} · ${formatDateTime(terakhirPo.created_at)}`
            : "belum ada PO tercatat",
      tone: po !== null && po > 0 ? "ok" : "neutral",
    },
    {
      id: "eksekusi",
      label: `Keputusan dieksekusi · ${rentang}`,
      value:
        eksekusi === null
          ? "—"
          : eksekusi === 0
            ? "belum ada"
            : String(eksekusi),
      unit: "keputusan",
      foot:
        eksekusi === null
          ? "jumlah eksekusi tidak terbaca"
          : eksekusi === 0
            ? `tidak ada jejak ACT pada ${rentang}`
            : `jejak ACT tercatat untuk ${eksekusi} keputusan`,
      mini:
        data.decisions_executed?.last_step_at
          ? `terakhir ${formatDateTime(data.decisions_executed.last_step_at)}`
          : "—",
      tone: eksekusi !== null && eksekusi > 0 ? "ok" : "neutral",
    },
    {
      id: "truk",
      label: `Truk berangkat · ${rentang}`,
      value: truk === null ? "—" : truk === 0 ? "belum ada" : String(truk),
      unit: "batch",
      foot:
        truk === null
          ? "jumlah batch tidak terbaca"
          : truk === 0
            ? `tidak ada batch diberangkatkan pada ${rentang}`
            : `${truk} batch diberangkatkan (garis kiriman di peta)`,
      mini: "hanya batch terikat keputusan yang diberangkatkan; batch gagal gerbang keselamatan ditahan",
      tone: truk !== null && truk > 0 ? "ok" : "neutral",
    },
    {
      id: "terima",
      label: `Kg diterima · ${rentang}`,
      value: terimaKg === null ? "—" : terimaKg === 0 ? "belum ada" : formatKg(terimaKg),
      unit: "kg",
      foot:
        terimaKg === null
          ? "berat penerimaan tidak terbaca"
          : terimaKg === 0
            ? `tidak ada penerimaan disetujui pada ${rentang}`
            : `dari ${terima === null ? "—" : terima} penerimaan disetujui`,
      mini: diterimaTerakhir
        ? `terakhir ${formatKg(diterimaTerakhir.kg)} kg · ${formatDateTime(diterimaTerakhir.reviewed_at)}`
        : "stok hanya bertambah setelah penerimaan disetujui",
      tone: terimaKg !== null && terimaKg > 0 ? "ok" : "neutral",
    },
  ];
}
