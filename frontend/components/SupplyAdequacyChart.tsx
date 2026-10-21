"use client";

import { useEffect, useMemo, useState, type CSSProperties } from "react";

import { formatClockWib, formatDateTime } from "../lib/datetime";
import { formatKg } from "../lib/overview-format";
import {
  adequacySummary,
  formatCoverage,
  formatSignedKg,
  gapFor,
  metricFor,
  sortAdequacyRows,
  type AdequacyLens,
  type CommodityAdequacy,
  type SupplyTone,
} from "../lib/supply-adequacy";

type Props = {
  rows: readonly CommodityAdequacy[];
  role: string | null;
  locationName: string;
  updatedAt: number | null;
  /** Tanggal sumber pasokan/permintaan, mis. "Data per 8 Okt 2026". */
  sourceNote?: string | null;
  now: Date | null;
  loading?: boolean;
  error?: string | null;
  onSelect?: (commodity: string) => void;
  onRetry?: () => void;
};

const LABEL_LENS: Record<AdequacyLens, string> = {
  quantity: "Kuantitas",
  freshness: "Kesegaran",
};

function toneClass(tone: SupplyTone) {
  return `sa-tone-${tone}`;
}

function rowAria(row: CommodityAdequacy, lens: AdequacyLens) {
  const kebutuhan =
    row.demandKg === null ? "belum tercatat" : formatKg(row.demandKg);
  return [
    `${row.commodity}: ${
      lens === "freshness"
        ? `stok segar ${formatKg(row.buckets.freshKg)} (layak ${formatKg(row.buckets.usableKg)})`
        : `stok layak ${formatKg(row.buckets.usableKg)}`
    } dari kebutuhan ${kebutuhan}`,
    `cakupan ${formatCoverage(metricFor(row, lens))}`,
    `selisih ${formatSignedKg(gapFor(row, lens))}`,
    `segar ${formatKg(row.buckets.freshKg)}`,
    `mendekati batas ${formatKg(row.buckets.nearKg)}`,
    `tidak layak ${formatKg(row.buckets.unsafeKg)}`,
    `belum terverifikasi ${formatKg(row.buckets.unverifiedKg)}`,
  ].join(". ");
}

export default function SupplyAdequacyChart({
  rows,
  role,
  locationName,
  updatedAt,
  sourceNote = null,
  now,
  loading = false,
  error = null,
  onSelect,
  onRetry,
}: Props) {
  const preferred: AdequacyLens =
    role === "sppg_nutritionist" ? "freshness" : "quantity";
  const [lens, setLens] = useState<AdequacyLens>(preferred);
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);
  useEffect(() => setLens(preferred), [preferred]);

  const urut = useMemo(() => sortAdequacyRows(rows, lens), [rows, lens]);
  const ringkas = adequacySummary(urut, lens);
  const labelLens = lens === "freshness" ? "segar" : "cakupan";
  const labelRingkas =
    lens === "freshness"
      ? "komoditas dengan stok segar di bawah kebutuhan"
      : "komoditas di bawah kebutuhan";

  const tanggal = updatedAt
    ? formatDateTime(new Date(updatedAt).toISOString())
    : "—";
  const jamSumber = updatedAt
    ? formatClockWib(new Date(updatedAt).toISOString())
    : null;

  if (loading || !now) {
    return (
      <section
        className="supply-adequacy"
        aria-label="Kecukupan pasokan"
        aria-busy="true"
      >
        <header className="sa-head">
          <div className="sa-title">
            <h3>Kecukupan pasokan</h3>
            <p className="sa-sub">
              {locationName || "SPPG"} · memuat empat komoditas…
            </p>
          </div>
        </header>
        <div className="sa-skeleton" aria-hidden="true">
          {[0, 1, 2, 3].map((i) => (
            <div className="sa-skeleton-row" key={i}>
              <span className="sa-skeleton-name" />
              <span className="sa-skeleton-track" />
              <span className="sa-skeleton-gap" />
            </div>
          ))}
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="supply-adequacy" aria-label="Kecukupan pasokan">
        <header className="sa-head">
          <div className="sa-title">
            <h3>Kecukupan pasokan</h3>
            <p className="sa-sub">{locationName || "SPPG"}</p>
          </div>
        </header>
        <p className="status-danger sa-error" role="alert">
          {error}{" "}
          {onRetry && (
            <button type="button" onClick={onRetry}>
              Coba lagi
            </button>
          )}
        </p>
      </section>
    );
  }

  if (!rows.length) return null;

  return (
    <section
      className={`supply-adequacy${mounted ? " is-mounted" : ""}`}
      aria-labelledby="sa-title"
    >
      <header className="sa-head">
        <div className="sa-title">
          <h3 id="sa-title">Kecukupan pasokan</h3>
          <p className="sa-sub">
            {locationName || "SPPG"} · 4 komoditas ·{" "}
            {sourceNote
              ? `${sourceNote}${jamSumber ? ` · dihitung ${jamSumber} WIB` : ""}`
              : `dihitung ${tanggal}`}
          </p>
        </div>
        <div className="sa-summary" aria-live="polite">
          <span className="sa-summary-count">
            {ringkas.measured ? ringkas.short : "—"}
            <em>/{ringkas.measured || "—"}</em>
          </span>
          <span className="sa-summary-label">{labelRingkas}</span>
          {ringkas.worst && (
            <span className={`sa-worst ${toneClass(ringkas.worst.tone)}`}>
              {ringkas.worst.commodity}{" "}
              {formatSignedKg(gapFor(ringkas.worst, lens))}
            </span>
          )}
        </div>
      </header>

      <div className="sa-tools">
        <div
          className="sa-toggle"
          role="group"
          aria-label="Sudut pandang kecukupan"
        >
          {(["quantity", "freshness"] as const).map((pilihan) => (
            <button
              key={pilihan}
              type="button"
              aria-pressed={lens === pilihan}
              onClick={() => setLens(pilihan)}
            >
              {LABEL_LENS[pilihan]}
            </button>
          ))}
        </div>
        <div className="sa-legend" aria-label="Legenda kualitas stok">
          <span>
            <i className="sa-dot sa-dot-fresh" aria-hidden="true" /> Segar
          </span>
          <span>
            <i className="sa-dot sa-dot-near" aria-hidden="true" /> ≤48 jam
          </span>
          <span>
            <i className="sa-dot sa-dot-unsafe" aria-hidden="true" /> Tidak
            layak
          </span>
          <span>
            <i className="sa-dot sa-dot-unverified" aria-hidden="true" /> Belum
            terverifikasi
          </span>
          <span className="sa-legend-demand">
            <i aria-hidden="true" /> Kebutuhan
          </span>
        </div>
      </div>

      <ol className="sa-rows">
        {urut.map((row, index) => {
          const tone = lens === "freshness" ? row.freshTone : row.tone;
          const nilai = metricFor(row, lens);
          const selisih = gapFor(row, lens);
          const total = row.buckets.totalKg;
          const skala = Math.max(row.demandKg ?? 0, total, 1) * 1.04;
          const lebar = (kg: number) => `${Math.min(100, (kg / skala) * 100)}%`;
          const kebutuhanPct =
            row.demandKg !== null && row.demandKg > 0
              ? Math.min(100, (row.demandKg / skala) * 100)
              : null;
          // Numerator mengikuti lensa: kuantitas memakai stok layak, kesegaran
          // hanya memakai stok yang masih >48 jam. Tanpa ini baris bisa
          // menulis "80 / 215" padahal cakupan segarnya 0%.
          const numerator =
            lens === "freshness" ? row.buckets.freshKg : row.buckets.usableKg;
          const isi = (
            <>
              <span className="sa-name">
                <span className="sa-commodity">{row.commodity}</span>
                <span className="sa-stock">
                  {lens === "freshness"
                    ? row.buckets.freshKg === row.buckets.usableKg
                      ? `${formatKg(row.buckets.freshKg)} segar`
                      : `${formatKg(row.buckets.freshKg)} segar · ${formatKg(row.buckets.usableKg)} layak`
                    : `${formatKg(row.buckets.usableKg)} layak`}
                  {row.supplyRecordKg !== null &&
                    ` · ${formatKg(row.supplyRecordKg)} tercatat`}
                </span>
                {row.buckets.batchCount === 0 &&
                  (row.supplyRecordKg ?? 0) > 0 && (
                    <span
                      className="sa-nobatch"
                      title="Pasokan tercatat ada, tetapi tidak ada baris batch di lokasi ini"
                    >
                      tanpa batch
                    </span>
                  )}
                {row.buckets.nearCount > 0 && (
                  <span className="sa-near-note">
                    {row.buckets.nearCount} batch ≤48 jam
                  </span>
                )}
              </span>

              <span className="sa-coverage">
                <strong>{formatCoverage(nilai)}</strong>
                <span>{labelLens}</span>
              </span>

              <span
                className={`sa-track${row.dataState !== "terukur" ? " sa-track-neutral" : ""}`}
                aria-hidden="true"
              >
                <span className="sa-track-fill">
                  {row.buckets.freshKg > 0 && (
                    <span
                      className="sa-seg sa-seg-fresh"
                      style={{
                        width: lebar(row.buckets.freshKg),
                        minWidth: 2,
                      }}
                    />
                  )}
                  {row.buckets.nearKg > 0 && (
                    <span
                      className="sa-seg sa-seg-near"
                      style={{ width: lebar(row.buckets.nearKg), minWidth: 2 }}
                    />
                  )}
                  {row.buckets.unsafeKg > 0 && (
                    <span
                      className="sa-seg sa-seg-unsafe"
                      style={{
                        width: lebar(row.buckets.unsafeKg),
                        minWidth: 2,
                      }}
                    />
                  )}
                  {row.buckets.unverifiedKg > 0 && (
                    <span
                      className="sa-seg sa-seg-unverified"
                      style={{
                        width: lebar(row.buckets.unverifiedKg),
                        minWidth: 2,
                      }}
                    />
                  )}
                </span>
                {kebutuhanPct !== null && (
                  <span
                    className="sa-demand"
                    style={{ left: `${kebutuhanPct}%` }}
                  />
                )}
              </span>

              <span
                className={`sa-gap${selisih !== null && selisih >= 0 ? " sa-gap-ok" : ""}`}
              >
                <strong>{formatSignedKg(selisih)}</strong>
                <small>
                  {row.demandKg === null
                    ? "kebutuhan belum tercatat"
                    : `${formatKg(numerator)} / ${formatKg(row.demandKg)}`}
                </small>
              </span>
            </>
          );

          return (
            <li
              key={row.commodity}
              className={`sa-row ${toneClass(tone)}`}
              style={{ "--i": index } as CSSProperties}
            >
              {onSelect ? (
                <button
                  type="button"
                  className="sa-row-btn"
                  aria-label={rowAria(row, lens)}
                  title={`Tampilkan ${row.commodity} di peta`}
                  onClick={() => onSelect(row.commodity)}
                >
                  {isi}
                </button>
              ) : (
                <div
                  className="sa-row-btn sa-row-static"
                  role="group"
                  aria-label={rowAria(row, lens)}
                >
                  {isi}
                </div>
              )}
            </li>
          );
        })}
      </ol>

      <p className="sa-foot">
        Stok layak = batch aman, tidak ditahan, dan belum lewat masa layak.
        Stok ini dibatasi angka pasokan tercatat, jadi tidak ada klaim stok di
        luar pembukuan. Pada sudut pandang <strong>Kesegaran</strong>, “segar”
        berarti sisa masa layak lebih dari 48 jam; batch ≤48 jam tetap layak
        tetapi tidak dihitung segar.
      </p>
    </section>
  );
}
