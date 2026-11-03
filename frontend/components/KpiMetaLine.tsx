"use client";

// KpiMetaLine — baris meta satu kontrol untuk halaman "Performance & Audit".
//
// Tahap 2 redesign (29 Okt 2026). Sebelumnya empat PIL di kepala halaman
// mengulang apa yang sudah bisa dipilih di bawahnya:
//   - pil periode   ↔ tombol periode (jendela yang sama, dua tempat)
//   - pil cakupan   ↔ toggle cakupan
//   - pil mode data ↔ judul grup "Simulasi"/"Operasional"
//   - pil dihitung  ↔ tidak ada duplikatnya, tapi ikut terpencil di kepala
//
// Sekarang satu baris meta, duduk di ujung bilah kontrol yang sama dengan
// tombol periode dan toggle cakupan. Yang dipertahankan hanya INFORMASI yang
// tidak bisa dipilih (siapa cakupannya, mode data mana, kapan dihitung), plus
// satu ringkasan keadaan metrik supaya pembaca tahu ada berapa yang kosong
// tanpa menggulir tujuh kartu.
//
// `data-testid` lama (`kpi-scope`, `kpi-data-mode`, `kpi-computed-at`) tetap
// dipasang — tes provenance & kesegaran angka menguncinya.

import { scopeLabel } from "../lib/kpi-provenance";
import { formatClockWib } from "../lib/datetime";
import { roleLabel } from "../lib/settings";

const URUTAN_KEADAAN = ["available", "no_data", "unavailable"] as const;

const LABEL_KEADAAN: Record<string, string> = {
  available: "tersedia",
  no_data: "belum ada data",
  unavailable: "tidak tersedia",
};

/** "7 metrik · 5 tersedia · 1 belum ada data" — nol tidak dicetak. */
export function ringkasMetrik(metrics: any[]): string | null {
  if (metrics.length === 0) return null;
  const hitung: Record<string, number> = {};
  for (const m of metrics) {
    const k = String(m?.state ?? "");
    hitung[k] = (hitung[k] ?? 0) + 1;
  }
  const bagian = [`${metrics.length} metrik`];
  for (const k of URUTAN_KEADAAN) {
    const n = hitung[k] ?? 0;
    if (n > 0) bagian.push(`${n} ${LABEL_KEADAAN[k]}`);
  }
  // Keadaan di luar tiga nama yang dikenal tetap dihitung, bukan disembunyikan.
  const lain = metrics.length - URUTAN_KEADAAN.reduce((a, k) => a + (hitung[k] ?? 0), 0);
  if (lain > 0) bagian.push(`${lain} keadaan lain`);
  return bagian.join(" · ");
}

export default function KpiMetaLine({ kpi }: { kpi: any | null }) {
  if (!kpi) return null;
  const metrics: any[] = Array.isArray(kpi.metrics) ? kpi.metrics : [];
  const dihitung = formatClockWib(kpi.computed_at);
  const ringkas = ringkasMetrik(metrics);

  return (
    <p className="kpi-meta-line">
      <span className="kpi-meta-item" data-testid="kpi-scope" title={kpi.scope?.location_id ?? undefined}>
        Cakupan: {kpi.scope?.role ? roleLabel(kpi.scope.role) : "—"}
      </span>
      <span className="kpi-meta-item" data-testid="kpi-data-mode">
        {scopeLabel(kpi.data_mode)}
      </span>
      {/* Kesegaran angka (UI-2, 29 Okt 2026): `computed_at` dari server, bukan
          jam klien. Tanpa nilai yang sah, butirnya tidak dirender. */}
      {dihitung !== "—" ? (
        <span
          className="kpi-meta-item"
          data-testid="kpi-computed-at"
          title="Waktu angka di halaman ini dihitung"
        >
          Dihitung {dihitung} WIB
        </span>
      ) : null}
      {ringkas ? (
        <span className="kpi-meta-count" role="status" aria-atomic="true" data-testid="kpi-ringkasan">
          {ringkas}
        </span>
      ) : null}
    </p>
  );
}
