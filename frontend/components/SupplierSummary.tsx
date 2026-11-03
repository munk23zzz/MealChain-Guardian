"use client";

// Kartu Ringkasan halaman Pemasok — satu baris angka besar (KPI strip).
//
// Bentuk ini dipilih pemilik 29 Okt 2026, menggantikan dua percobaan sebelumnya
// (daftar fakta datar; papan sorotan dengan tile, bar, dan chip). Aturannya
// sekarang sederhana: kartu ini HANYA DIBACA. Tidak ada tombol, tidak ada
// sorotan, tidak ada status — angkanya untuk dilihat sekilas sebelum membaca
// tabel di bawahnya, dan satu-satunya penyaring tetap tombol "Hanya dalam
// jangkauan" milik tabel.

import { kpiRingkasan } from "../lib/supplier-summary";
import type { DirectoryMetrics } from "../lib/suppliers-board";

export default function SupplierSummary({
  metrics,
  reachKm = null,
  loading = false,
}: {
  metrics: DirectoryMetrics;
  reachKm?: number | null;
  loading?: boolean;
}) {
  const kpi = kpiRingkasan(metrics, reachKm);

  return (
    <article className="card supplier-summary" aria-busy={loading || undefined}>
      <div className="card-header summary-head">
        <h2>Ringkasan</h2>
      </div>

      <ul className="summary-kpi">
        {kpi.map((item) => (
          <li
            key={item.label}
            className="summary-kpi-item"
            data-tone={item.tone}
            // S2 (29 Okt 2026): satu angka dipromosikan — dibaca lebih dulu,
            // dicetak lebih besar lewat `[data-lead="true"]` di CSS.
            data-lead={item.lead ? "true" : undefined}
          >
            <b className="summary-kpi-value">{item.value}</b>
            <span className="summary-kpi-label">{item.label}</span>
          </li>
        ))}
      </ul>
    </article>
  );
}
