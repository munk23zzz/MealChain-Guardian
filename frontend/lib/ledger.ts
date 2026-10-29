// Ringkasan keterkaitan blok ledger untuk UI (audit A4, 18 Okt 2026).
//
// `/ledger/verify` menjawab dua hal berbeda: `valid` = integritas rantai hash,
// dan `orphan_blocks` = blok yang menunjuk entitas (keputusan/batch) yang sudah
// dihapus. Tanpa baris kedua, "✅ Rantai valid" terbaca sebagai "semua bukti
// lengkap" padahal 99% blok bisa saja yatim.

export type LedgerCoverage = {
  valid?: boolean;
  blocks?: number;
  /** Generasi data demo aktif; blok generasi lama tidak dinilai cakupannya. */
  generation?: number;
  entity_blocks?: number;
  linked_blocks?: number;
  orphan_blocks?: number;
  /** Blok generasi lama: entitasnya dibersihkan reset demo, bloknya sengaja
   *  tidak dihapus supaya rantai hash tetap utuh (audit N3, 24 Okt 2026). */
  archived_blocks?: number;
  coverage_warning?: string | null;
  /** Perbandingan dengan checkpoint di LUAR database (Fase 11 MG, butir 2).
   *  `match: null` = belum ada checkpoint / dimatikan — bukan "cocok". */
  anchor?: {
    configured?: boolean;
    match?: boolean | null;
    reason?: string | null;
    height?: number | null;
    payload_hash?: string | null;
    created_at?: string | null;
  } | null;
};

/** Kalimat status cakupan; `null` bila tidak ada yang perlu dikatakan. */
export function coverageNote(ledger: LedgerCoverage | null | undefined): string | null {
  if (!ledger) return null;
  const bagian: string[] = [];
  const warning = ledger.coverage_warning;
  if (warning) {
    const linked = ledger.linked_blocks;
    const total = ledger.entity_blocks;
    bagian.push(
      typeof linked === "number" && typeof total === "number"
        ? `${warning} (${linked} dari ${total} blok masih tertaut)`
        : warning
    );
  }
  const arsip = ledger.archived_blocks ?? 0;
  if (arsip > 0) {
    bagian.push(`${arsip} blok generasi lama diarsipkan (rantai tetap terverifikasi)`);
  }
  return bagian.length > 0 ? bagian.join(" · ") : null;
}

/**
 * Kalimat status anchor eksternal (Fase 11 MG, butir 2); `null` bila tidak ada
 * yang perlu dikatakan.
 *
 * Kenapa ada: `valid: true` hanya berarti hash di database saling menyambung —
 * siapa pun yang bisa menulis tabel dapat menghitung ulang seluruh rantai.
 * Yang membuktikan riwayat tidak ditulis ulang adalah kecocokan dengan
 * checkpoint yang disimpan di luar database. Karena itu "belum ada checkpoint"
 * TIDAK boleh tampil sebagai "aman".
 */
export function anchorNote(ledger: LedgerCoverage | null | undefined): string | null {
  const anchor = ledger?.anchor;
  if (!anchor) return null;
  if (anchor.match === false) {
    const alasan = anchor.reason ?? "isi checkpoint tidak sama dengan catatan aslinya";
    return `Anchor eksternal TIDAK cocok — riwayat ledger mungkin ditulis ulang. ${alasan}`;
  }
  if (anchor.match === null) {
    return anchor.configured
      ? "Checkpoint eksternal belum dibuat — integritas baru diperiksa di dalam."
      : "Anchor eksternal belum dipasang — integritas hanya diperiksa di dalam.";
  }
  const tinggi = anchor.height;
  return typeof tinggi === "number"
    ? `Cocok dengan checkpoint eksternal pada blok ${tinggi}.`
    : "Cocok dengan checkpoint eksternal.";
}
