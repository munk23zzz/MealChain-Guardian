"use client";

// Halaman "Pemasok" — halaman sidebar acuan /suppliers, disesuaikan ke repo ini:
// daftar pemasok disusun dari pemasok pada keputusan terakhir dalam cakupan
// (backend belum punya endpoint daftar pemasok), ditambah register eksklusi
// dari /supplier-exclusions dan form usul eksklusi yang sudah ada.

import PageHeader from "./PageHeader";
import FactList from "./FactList";
import { SupplierExclusionView } from "./SupplierExclusionPanel";
import {
  SUPPLIER_SOURCE_NOTE,
  exclusionRows,
  rosterMetrics,
  supplierRoster,
  type SupplierPair,
} from "../lib/suppliers-board";
import type { SupplierContext } from "../lib/supplier-exclusions";

export default function SupplierBoard({
  pairs,
  exclusions,
  selectedDecisionId,
  supplierContext,
  role,
  token,
  loading = false,
  error = null,
  onRetry,
  onOpenDecision,
  onExclusionCreated,
}: {
  pairs: SupplierPair[];
  exclusions: unknown;
  selectedDecisionId: string | null;
  supplierContext: SupplierContext | null;
  role: string;
  token: string;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  onOpenDecision?: (decisionId: string) => void;
  onExclusionCreated?: () => void;
}) {
  const roster = supplierRoster(pairs);
  const metrics = rosterMetrics(roster);
  const register = exclusionRows(
    exclusions && typeof exclusions === "object" && "items" in (exclusions as object)
      ? (exclusions as { items?: unknown }).items
      : exclusions
  );

  return (
    <section className="board-page">
      <PageHeader
        title="Pemasok"
        description="Kepercayaan pemasok dalam cakupan Anda, register eksklusi, dan usul eksklusi baru — semua lewat endpoint /supplier-exclusions."
        meta={
          <span className="page-header-pills">
            <span className="commodity-pill">{metrics.suppliers} pemasok</span>
            <span className="commodity-pill">{register.length} eksklusi</span>
          </span>
        }
      />

      {error ? (
        <article className="card">
          <h2>Tidak bisa memuat data pemasok</h2>
          <p className="evidence-note">{error}</p>
          {onRetry ? (
            <button type="button" className="button button-secondary" onClick={onRetry}>
              Coba lagi
            </button>
          ) : null}
        </article>
      ) : null}

      <div className="board-grid board-grid-2">
        <article className="card">
          <h2>Ringkasan</h2>
          <FactList
            rows={[
              {
                label: "Pemasok terlibat",
                value: loading && !pairs.length ? "…" : String(metrics.suppliers),
              },
              { label: "Keputusan terpindai", value: String(metrics.totalDecisions) },
              {
                label: "Rata-rata keandalan",
                value: metrics.avgReliabilityLabel,
                tone: metrics.avgReliability === null ? "plain" : metrics.avgReliability >= 0.8 ? "ok" : "warn",
              },
              {
                label: "Pemasok dieksklusi",
                value: String(register.length),
                tone: register.length ? "danger" : "plain",
              },
            ]}
          />
          <p className="evidence-note">
            Eksklusi bukan pelabelan hiasan: pemasok berstatus excluded tidak dipilih lagi untuk
            purchase order oleh backend.
          </p>
        </article>

        <article className="card">
          <h2>Dari mana angka ini</h2>
          <p className="evidence-note">{SUPPLIER_SOURCE_NOTE}</p>
        </article>
      </div>

      <article className="card">
        <h2>Daftar pemasok</h2>
        {roster.length === 0 ? (
          <p className="evidence-note">
            {loading
              ? "Memuat pemasok…"
              : "Belum ada keputusan dengan pemasok pada cakupan ini."}
          </p>
        ) : (
          <>
              <div className="board-table-wrap">
              <table className="location-table">
            <thead>
              <tr>
                <th scope="col">Pemasok</th>
                <th scope="col" className="num">
                  Keandalan
                </th>
                <th scope="col" className="num">
                  Keputusan
                </th>
                <th scope="col">Komoditas</th>
              </tr>
            </thead>
            <tbody>
              {roster.map((row) => (
                <tr key={row.id}>
                  <td>{row.name}</td>
                  <td className="num">{row.reliabilityLabel}</td>
                  <td className="num">{row.decisions}</td>
                  <td>{row.commodities.length ? row.commodities.join(", ") : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
            </div>
            <p className="board-scroll-hint">Geser tabel ke samping untuk melihat kolom lain.</p>
              </>
        )}
      </article>

      <article className="card">
        <h2>Register eksklusi</h2>
        {register.length === 0 ? (
          <p className="evidence-note">
            Tidak ada pemasok yang sedang dieksklusi dalam cakupan Anda.
          </p>
        ) : (
          <>
              <div className="board-table-wrap">
              <table className="location-table">
            <thead>
              <tr>
                <th scope="col">Pemasok</th>
                <th scope="col">Alasan</th>
                <th scope="col">Waktu</th>
                <th scope="col">Keputusan</th>
              </tr>
            </thead>
            <tbody>
              {register.map((row) => (
                <tr key={row.id}>
                  <td>{row.supplier}</td>
                  <td>{row.reason}</td>
                  <td>{row.at}</td>
                  <td>
                    <code>{row.decisionId.slice(0, 8)}</code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
            </div>
            <p className="board-scroll-hint">Geser tabel ke samping untuk melihat kolom lain.</p>
              </>
        )}
      </article>

      {selectedDecisionId && supplierContext ? (
        <SupplierExclusionView
          key={selectedDecisionId}
          context={supplierContext}
          role={role}
          token={token}
          onCreated={onExclusionCreated ?? (() => {})}
        />
      ) : (
        <article className="card">
          <h2>Usul eksklusi</h2>
          <p className="evidence-note">
            Pilih keputusan lebih dulu (tab Decision &amp; Evidence atau tombol di bawah) untuk
            mengusulkan eksklusi pemasok pada keputusan itu.
          </p>
          {onOpenDecision ? (
            <button
              type="button"
              className="button button-secondary"
              onClick={() => onOpenDecision("")}
            >
              Buka Decision &amp; Evidence
            </button>
          ) : null}
        </article>
      )}
    </section>
  );
}
