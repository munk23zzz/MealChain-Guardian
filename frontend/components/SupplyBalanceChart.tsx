"use client";

import { useEffect, useMemo, useState, type CSSProperties } from "react";

import { formatDateTime } from "../lib/datetime";
import { formatKg, type BalanceMapLocation } from "../lib/overview-format";
import {
  buildLocationBalanceRows,
  formatCoverage,
  formatSignedKg,
  locationBalanceSummary,
  locationStatusLabel,
  sortLocationBalanceRows,
  type LocationBalanceRow,
} from "../lib/location-balance";
import type { SupplyTone } from "../lib/supply-adequacy";

function toneClass(tone: SupplyTone): string {
  return `sa-tone-${tone}`;
}

function rowAria(row: LocationBalanceRow): string {
  const pasokan =
    row.supplyKg === null ? "belum tercatat" : formatKg(row.supplyKg);
  const kebutuhan =
    row.demandKg === null ? "belum tercatat" : formatKg(row.demandKg);
  return [
    `${row.location}: ${locationStatusLabel(row)}`,
    `pasokan ${pasokan}`,
    `kebutuhan ${kebutuhan}`,
    `cakupan ${formatCoverage(row.coverage)}`,
    `selisih ${formatSignedKg(row.gapKg)}`,
  ].join(". ");
}

export default function SupplyBalanceChart({
  locations,
  commodity,
  updatedAt,
  now,
  loading = false,
  error = null,
  onRetry,
}: {
  locations: readonly BalanceMapLocation[];
  commodity?: string | null;
  updatedAt: number | null;
  now: Date | null;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
}) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const rows = useMemo(
    () => sortLocationBalanceRows(buildLocationBalanceRows(locations)),
    [locations]
  );
  const ringkas = locationBalanceSummary(rows);
  const tanggal = updatedAt
    ? formatDateTime(new Date(updatedAt).toISOString())
    : "—";

  if (!now || loading) {
    return (
      <section
        className="supply-adequacy supply-balance"
        aria-label="Pasokan per lokasi"
        aria-busy="true"
      >
        <header className="sa-head">
          <div className="sa-title">
            <h3>Pasokan per Lokasi</h3>
            <p className="sa-sub">
              {commodity ?? "komoditas"} · memuat lokasi…
            </p>
          </div>
        </header>
        <div className="sa-skeleton" aria-hidden="true">
          {[0, 1, 2, 3, 4, 5].map((i) => (
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
      <section
        className="supply-adequacy supply-balance"
        aria-label="Pasokan per lokasi"
      >
        <header className="sa-head">
          <div className="sa-title">
            <h3>Pasokan per Lokasi</h3>
            <p className="sa-sub">{commodity ?? "komoditas"}</p>
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

  return (
    <section
      className={`supply-adequacy supply-balance${mounted ? " is-mounted" : ""}`}
      aria-labelledby="sb-title"
    >
      <header className="sa-head">
        <div className="sa-title">
          <h3 id="sb-title">Pasokan per Lokasi</h3>
          <p className="sa-sub">
            {commodity ?? "komoditas"} · {rows.length} lokasi · data {tanggal}
          </p>
        </div>
        <div className="sa-summary" aria-live="polite">
          <span className="sa-summary-count">
            {ringkas.measured ? ringkas.shortage : "—"}
            <em>/{ringkas.measured || "—"}</em>
          </span>
          <span className="sa-summary-label">
            {ringkas.measured
              ? "lokasi di bawah kebutuhan"
              : "belum ada lokasi terukur"}
          </span>
          {ringkas.worst && (
            <span className={`sa-worst ${toneClass(ringkas.worst.tone)}`}>
              {ringkas.worst.location}{" "}
              {formatSignedKg(ringkas.worst.gapKg)}
            </span>
          )}
        </div>
      </header>

      <div className="sa-tools">
        <div className="sa-legend" aria-label="Legenda keseimbangan pasokan">
          <span>
            <i className="sa-dot sa-dot-pasokan" aria-hidden="true" /> Pasokan
            tercatat
          </span>
          <span className="sa-legend-demand">
            <i aria-hidden="true" /> Kebutuhan
          </span>
          <span className="sa-legend-note">warna = cakupan</span>
        </div>
      </div>

      {rows.length === 0 ? (
        <p className="sa-empty">
          Belum ada lokasi yang bisa ditampilkan untuk komoditas ini.
        </p>
      ) : (
        <ol className="sa-rows">
          {rows.map((row, index) => {
            const skala =
              Math.max(row.demandKg ?? 0, row.supplyKg ?? 0, 1) * 1.04;
            const supplyPct =
              row.supplyKg !== null
                ? Math.min(100, (row.supplyKg / skala) * 100)
                : 0;
            const demandPct =
              row.demandKg !== null && row.demandKg > 0
                ? Math.min(100, (row.demandKg / skala) * 100)
                : null;
            const detail =
              row.dataState === "tanpa_data"
                ? "kebutuhan belum tercatat"
                : row.dataState === "tanpa_kebutuhan"
                  ? "tidak ada kebutuhan"
                  : row.supplyKg === null
                    ? "pasokan belum tercatat"
                    : `${formatKg(row.supplyKg)} / ${formatKg(row.demandKg)}`;

            return (
              <li
                key={row.location}
                className={`sa-row ${toneClass(row.tone)}`}
                style={{ "--i": index } as CSSProperties}
              >
                <div className="sa-row-btn sa-row-static" role="group" aria-label={rowAria(row)}>
                  <span className="sa-name">
                    <span className="sa-commodity">{row.location}</span>
                    <span className="sa-stock">{locationStatusLabel(row)}</span>
                  </span>

                  <span className="sa-coverage">
                    <strong>{formatCoverage(row.coverage)}</strong>
                    <span>cakupan</span>
                  </span>

                  <span className="sa-track" aria-hidden="true">
                    <span className="sa-track-fill">
                      {row.supplyKg !== null && row.supplyKg > 0 && (
                        <span
                          className="sa-seg sa-seg-pasokan"
                          style={{
                            width: `${supplyPct}%`,
                            minWidth: 2,
                          }}
                        />
                      )}
                    </span>
                    {demandPct !== null && (
                      <span
                        className="sa-demand"
                        style={{ left: `${demandPct}%` }}
                      />
                    )}
                  </span>

                  <span
                    className={`sa-gap${
                      row.gapKg !== null && row.gapKg >= 0 ? " sa-gap-ok" : ""
                    }`}
                  >
                    <strong>{formatSignedKg(row.gapKg)}</strong>
                    <small>{detail}</small>
                  </span>
                </div>
              </li>
            );
          })}
        </ol>
      )}

      <p className="sa-foot">
        Batang = pasokan tercatat, garis = kebutuhan. Lokasi diurutkan dari
        kekurangan terbesar. Angka yang belum tercatat tidak pernah digambar
        sebagai nol yang aman.
      </p>
    </section>
  );
}
