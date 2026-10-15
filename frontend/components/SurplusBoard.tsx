"use client";

// Halaman "Surplus & Limbah" — halaman sidebar acuan /surplus, disesuaikan ke
// data repo ini (/balance/map). Panel alokasi memakai surplus nyata; bagian
// limbah ditulis "—" karena backend ini tidak punya pencatatan disposal.

import PageHeader from "./PageHeader";
import FactList from "./FactList";
import {
  allocationPlan,
  surplusSummary,
  wasteFacts,
} from "../lib/surplus";
import { formatKg } from "../lib/overview-format";
import { LoadingState } from "./LoadingState";

export default function SurplusBoard({
  locations,
  commodity,
  commodities,
  onChangeCommodity,
  loading = false,
  error = null,
  onRetry,
  onOpenLocation,
}: {
  locations: unknown[] | null;
  commodity?: string | null;
  commodities?: string[];
  onChangeCommodity?: (c: string) => void;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  onOpenLocation?: (location: string) => void;
}) {
  const summary = surplusSummary(locations);
  const plan = allocationPlan(locations, 6);

  return (
    <section className="board-page" aria-busy={loading || undefined}>
      <PageHeader
        title="Surplus & Limbah"
        description="Surplus yang bisa dialihkan antar-SPPG, rencana alokasinya, dan keadaan pencatatan limbah untuk komoditas yang dipilih di peta."
        meta={
          <span className="page-header-pills">
            <span className="commodity-pill">Komoditas {commodity ? commodity : "—"}</span>
            <span className="commodity-pill">{summary.surplusCount} lokasi surplus</span>
          </span>
        }
      />

      {commodities && commodities.length > 0 && onChangeCommodity && (
        <div className="commodity-filters filter-card" role="group" aria-label="Komoditas peta">
          <span className="commodity-filters-label">Komoditas:</span>
          {commodities.map((c) => (
            <button
              key={c}
              type="button"
              className={`commodity-pill${commodity === c ? " commodity-pill-active" : ""}`}
              aria-pressed={commodity === c}
              onClick={() => onChangeCommodity(c)}
            >
              {c}
            </button>
          ))}
        </div>
      )}

      {error ? (
        <article className="card">
          <h2>Tidak bisa memuat neraca lokasi</h2>
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
          <h2>Neraca hari ini</h2>
          <FactList
            rows={[
              {
                label: "Total surplus",
                value: loading && !locations ? "…" : summary.surplusKg === null ? "—" : formatKg(summary.surplusKg),
                tone: summary.surplusKg === null ? "plain" : "ok",
              },
              { label: "Lokasi surplus", value: String(summary.surplusCount) },
              {
                label: "Total kekurangan",
                value: summary.shortageKg === null ? "—" : formatKg(summary.shortageKg),
                tone: summary.shortageKg === null ? "plain" : "warn",
              },
              { label: "Lokasi kekurangan", value: String(summary.shortageCount) },
              { label: "Lokasi seimbang", value: String(summary.balancedCount) },
            ]}
          />
          <p className="evidence-note">
            Surplus = stok − kebutuhan pada satu komoditas. Angka kekurangan di sini juga muncul di
            kartu “lokasi shortage” halaman Hari Ini.
          </p>
        </article>

        <article className="card">
          <h2>Pencatatan limbah</h2>
          <FactList rows={wasteFacts()} />
          <p className="evidence-note">
            Bagian ini sengaja kosong: menuliskan 0 kg akan terbaca “tidak ada limbah”, padahal yang
            benar “belum dicatat”.
          </p>
        </article>
      </div>

      <article className="card">
        <h2>Rencana alokasi surplus</h2>
        {plan.length === 0 ? (
          <p className="evidence-note">
            {loading ? <LoadingState label="Memuat neraca…" /> : "Tidak ada pasangan surplus→kekurangan yang bisa dialokasikan saat ini."}
          </p>
        ) : (
          <>
            <>
              <div className="board-table-wrap">
              <table className="location-table">
              <thead>
                <tr>
                  <th scope="col">Dari</th>
                  <th scope="col">Tujuan</th>
                  <th scope="col" className="num">
                    Jumlah
                  </th>
                  <th scope="col" className="num">
                    Jarak
                  </th>
                  <th scope="col">Wilayah tujuan</th>
                  <th scope="col">Tindakan</th>
                </tr>
              </thead>
              <tbody>
                {plan.map((row) => (
                  <tr key={`${row.from}-${row.to}-${row.kg}`}>
                    <td>{row.from}</td>
                    <td>{row.to}</td>
                    <td className="num">{formatKg(row.kg)}</td>
                    <td className="num">{row.distanceKm === null ? "—" : `${row.distanceKm} km`}</td>
                    <td>{row.region ?? "—"}</td>
                    <td>
                      {onOpenLocation ? (
                        <button
                          type="button"
                          className="button button-secondary"
                          onClick={() => onOpenLocation(row.to)}
                        >
                          Lihat di peta
                        </button>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
            <p className="board-scroll-hint">Geser tabel ke samping untuk melihat kolom lain.</p>
              </>
            <p className="evidence-note">
              Urutan: kebutuhan terbesar diisi surplus terbesar lebih dulu, sampai salah satu sisi
              habis. Jarak memakai koordinat lokasi (jarak lurus, bukan rute jalan).
            </p>
          </>
        )}
      </article>

    </section>
  );
}
