"use client";

// ModuleSearch — pencarian keputusan di tab Agent Log (dokumen 06 §1).
//
// Dua hal yang dijaga:
// 1. Kalimat "pencarian menyaring DAFTAR KEPUTUSAN, bukan langkah trace" harus
//    terlihat (§4.2): kalau pengguna mengetik nama komoditas lalu daftar
//    langkah tidak berubah, itu bukan bug.
// 2. Penyaring status memakai `aria-pressed` + jumlah, bukan warna saja.

import type { ReactNode } from "react";

import type { VerificationKey } from "../lib/decision-table";
import { VERIFICATION_OPTIONS } from "../lib/decision-table";

export default function ModuleSearch({
  query,
  onQuery,
  commodity,
  onCommodity,
  verification,
  onVerification,
  attention = false,
  onAttention,
  attentionCount = 0,
  commodities,
  counts,
  total,
  shown,
  period = null,
}: {
  query: string;
  onQuery: (value: string) => void;
  commodity: string | null;
  onCommodity: (value: string | null) => void;
  verification: VerificationKey;
  onVerification: (value: VerificationKey) => void;
  /**
   * Triage (UI-1, 29 Okt 2026): hanya keputusan yang ditandai verifikator atau
   * lewat tenggat. Dihitung dari baris yang sama dengan tabel, bukan angka
   * karangan.
   */
  attention?: boolean;
  onAttention?: (value: boolean) => void;
  attentionCount?: number;
  commodities: { value: string; label: string; count: number }[];
  counts: Record<VerificationKey, number>;
  total: number;
  /**
   * Jumlah baris yang LOLOS filter (Tahap 2 redesign, 29 Okt 2026). Dipakai
   * untuk kalimat "12 dari 64 keputusan" — angka yang menjawab "apakah filter
   * saya menyembunyikan sesuatu?" tanpa membuka tabel. `undefined` = pemanggil
   * tidak mengirimnya (mis. tes lama), dan kalimatnya tidak dicetak.
   */
  shown?: number;
  /** Pemilih periode, dirender sebagai field ketiga di baris yang sama (29 Okt
   *  2026). Dulu ia duduk di barisnya sendiri di bawah kartu pencarian: tiga blok
   *  bertumpuk sebelum satu baris data terlihat. */
  period?: ReactNode;
}) {
  const aktif =
    Boolean(query.trim()) ||
    Boolean(commodity) ||
    verification !== "all" ||
    attention;

  const kosongkan = () => {
    onQuery("");
    onCommodity(null);
    onVerification("all");
    onAttention?.(false);
  };

  // Yang benar-benar aktif, disebut namanya: saran "hapus filter" tanpa menyebut
  // filter mana hanya menambah tebakan.
  const aktifBernama: string[] = [];
  if (query.trim()) aktifBernama.push(`pencarian "${query.trim()}"`);
  if (commodity) {
    const label = commodities.find((c) => c.value === commodity)?.label ?? commodity;
    aktifBernama.push(`komoditas ${label}`);
  }
  if (verification !== "all") {
    const label = VERIFICATION_OPTIONS.find((o) => o.key === verification)?.label;
    if (label) aktifBernama.push(`status ${label.toLowerCase()}`);
  }
  if (attention) aktifBernama.push("perlu perhatian");

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

        {period ? (
          <div className="aa-search-field aa-search-field-periode">{period}</div>
        ) : null}

        {/* Ringkasan hasil (Tahap 2 redesign): angka "berapa yang lolos" duduk di
            ujung baris filter, bukan sebagai baris baru. `role=status` supaya
            pembaca layar mendengar perubahannya tanpa kehilangan fokus. */}
        {typeof shown === "number" ? (
          <p className="aa-search-count" role="status" aria-atomic="true">
            {shown} dari {total} keputusan
          </p>
        ) : null}
      </div>

      <div className="aa-search-filters" role="group" aria-label="Saring daftar keputusan">
        {onAttention ? (
          <button
            type="button"
            className={`filter-chip filter-chip-attention${
              attention ? " filter-chip-active filter-chip-warn" : ""
            }`}
            aria-pressed={attention}
            onClick={() => onAttention(!attention)}
            title="Keputusan yang ditandai verifikator atau tenggatnya sudah lewat"
          >
            Perlu perhatian
            <span className="legend-count">{attentionCount}</span>
          </button>
        ) : null}
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
          <button type="button" className="aa-search-reset" onClick={kosongkan}>
            Kosongkan filter
          </button>
        ) : null}
      </div>

      {/* Keadaan "tidak ada hasil" (Tahap 2). Aturan UI/UX Pro Max `No Results`:
          jangan layar kosong atau sekadar "0 hasil" — sebut apa yang menyaring,
          dan sediakan aksi untuk kembali melihat semuanya. */}
      {aktif && shown === 0 ? (
        <div className="aa-search-empty" role="status">
          <p>
            Tidak ada keputusan yang cocok dengan {aktifBernama.join(" + ")}.{" "}
            {total} keputusan tetap ada.
          </p>
          <button type="button" className="aa-search-reset" onClick={kosongkan}>
            Kosongkan filter
          </button>
        </div>
      ) : null}

      <p className="aa-search-note" id="aa-search-note">
        Filter menyaring daftar keputusan, bukan langkah trace.
      </p>
    </section>
  );
}
