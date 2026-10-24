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
