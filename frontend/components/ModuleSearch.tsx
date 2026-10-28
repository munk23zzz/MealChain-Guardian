"use client";

// ModuleSearch — pencarian keputusan di tab Agent Log (dokumen 06 §1).
//
// Dua hal yang dijaga:
// 1. Kalimat "pencarian menyaring DAFTAR KEPUTUSAN, bukan langkah trace" harus
//    terlihat (§4.2): kalau pengguna mengetik nama komoditas lalu daftar
//    langkah tidak berubah, itu bukan bug.
// 2. Penyaring status memakai `aria-pressed` + jumlah, bukan warna saja.

import type { VerificationKey } from "../lib/decision-table";
import { VERIFICATION_OPTIONS } from "../lib/decision-table";

export default function ModuleSearch({
  query,
  onQuery,
  commodity,
  onCommodity,
  verification,
  onVerification,
  commodities,
  counts,
  total,
}: {
  query: string;
  onQuery: (value: string) => void;
  commodity: string | null;
  onCommodity: (value: string | null) => void;
  verification: VerificationKey;
  onVerification: (value: VerificationKey) => void;
  commodities: { value: string; label: string; count: number }[];
  counts: Record<VerificationKey, number>;
  total: number;
}) {
  const aktif = Boolean(query.trim()) || Boolean(commodity) || verification !== "all";

  return (
    <section className="aa-search" aria-labelledby="aa-search-title">
      <div className="aa-search-row">
        <label className="aa-search-field">
          <span className="aa-search-label" id="aa-search-title">
            Cari keputusan
          </span>
          <input
            type="search"
            className="aa-search-input"
            value={query}
            placeholder="Jenis, status, komoditas, pemasok, atau ID…"
            aria-describedby="aa-search-note"
            onChange={(e) => onQuery(e.target.value)}
          />
        </label>

        <label className="aa-search-field aa-search-field-sempit">
          <span className="aa-search-label">Komoditas</span>
          <select
            className="aa-search-select"
            value={commodity ?? ""}
            onChange={(e) => onCommodity(e.target.value || null)}
          >
            <option value="">Semua komoditas</option>
            {commodities.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label} ({c.count})
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="aa-search-filters" role="group" aria-label="Status verifikasi">
        {VERIFICATION_OPTIONS.map((opt) => (
          <button
            key={opt.key}
            type="button"
            className={`filter-chip${verification === opt.key ? " filter-chip-active" : ""}`}
            aria-pressed={verification === opt.key}
            onClick={() => onVerification(opt.key)}
          >
            {opt.label}
            <span className="legend-count">
              {opt.key === "all" ? total : counts[opt.key]}
            </span>
          </button>
        ))}
        {aktif ? (
          <button
            type="button"
            className="aa-search-reset"
            onClick={() => {
              onQuery("");
              onCommodity(null);
              onVerification("all");
            }}
          >
            Kosongkan filter
          </button>
        ) : null}
      </div>

      <p className="aa-search-note" id="aa-search-note">
        Pencarian dan filter bekerja pada <strong>daftar keputusan</strong>, bukan
        pada langkah trace. Pilih satu keputusan untuk melihat tahap dan langkahnya.
      </p>
    </section>
  );
}
