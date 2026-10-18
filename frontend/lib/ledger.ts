// Ringkasan keterkaitan blok ledger untuk UI (audit A4, 18 Okt 2026).
//
// `/ledger/verify` menjawab dua hal berbeda: `valid` = integritas rantai hash,
// dan `orphan_blocks` = blok yang menunjuk entitas (keputusan/batch) yang sudah
// dihapus. Tanpa baris kedua, "✅ Rantai valid" terbaca sebagai "semua bukti
// lengkap" padahal 99% blok bisa saja yatim.

export type LedgerCoverage = {
  valid?: boolean;
  blocks?: number;
  entity_blocks?: number;
  linked_blocks?: number;
  orphan_blocks?: number;
  coverage_warning?: string | null;
};

/** Kalimat peringatan cakupan; `null` bila semua blok masih tertaut. */
export function coverageNote(ledger: LedgerCoverage | null | undefined): string | null {
  const warning = ledger?.coverage_warning;
  if (!warning) return null;
  const linked = ledger?.linked_blocks;
  const total = ledger?.entity_blocks;
  if (typeof linked === "number" && typeof total === "number") {
    return `${warning} (${linked} dari ${total} blok masih tertaut)`;
  }
  return warning;
}
