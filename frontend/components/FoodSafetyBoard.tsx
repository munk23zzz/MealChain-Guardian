"use client";

// Halaman "Keamanan Pangan" — halaman sidebar acuan /compliance, disesuaikan
// ke data repo ini (/batches). Papan CCP per-alat, bank sampel, dan jejak lot
// EPCIS dari acuan TIDAK dipakai karena tidak ada sumbernya di backend ini.

import PageHeader from "./PageHeader";
import FactList from "./FactList";
import {
  FOOD_SAFETY_SOURCE_NOTE,
  hoursLabel,
  safetyRows,
  safetySummary,
  type SafetyRow,
} from "../lib/food-safety";
import { formatKg } from "../lib/overview-format";

export default function FoodSafetyBoard({
  batches,
  now,
  commodity,
  loading = false,
  error = null,
  onRetry,
}: {
  batches: unknown[] | null;
  now: Date | null;
  commodity?: string | null;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
}) {
  const clock = now ?? new Date(0);
  const summary = safetySummary(batches);
  const rows = safetyRows(batches, clock);

  return (
    <section className="board-page">
      <PageHeader
        title="Keamanan Pangan"
        description="Status keamanan tiap batch, kesegaran, dan sisa masa layak pakai — dibaca langsung dari /batches. Batch gagal uji diblokir dari alokasi."
        meta={
          <span className="page-header-pills">
            <span className="commodity-pill">{summary.total} batch</span>
            {commodity ? <span className="commodity-pill">Komoditas {commodity}</span> : null}
          </span>
        }
      />

      {error ? (
        <article className="card">
          <h2>Tidak bisa memuat batch</h2>
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
          <h2>Ringkasan pengawasan</h2>
          <FactList
            rows={[
              { label: "Batch diperiksa", value: loading && !batches ? "…" : String(summary.total) },
              { label: "Aman", value: String(summary.safe), tone: "ok" },
              {
                label: "Gagal uji",
                value: String(summary.failed),
                tone: summary.failed ? "danger" : "plain",
                hint: summary.failed ? "tidak boleh dialokasikan" : null,
              },
              { label: "Perlu verifikasi", value: String(summary.needsVerification), tone: summary.needsVerification ? "warn" : "plain" },
              { label: "Belum diuji", value: String(summary.unchecked) },
              {
                label: "Berat batch gagal",
                value: summary.failedKg === null ? "—" : formatKg(summary.failedKg),
                tone: summary.failedKg === null ? "plain" : "danger",
              },
            ]}
          />
          {summary.hasFail ? (
            <p className="board-alert">
              Batch gagal uji: {summary.failedLocations.join(", ")} — alokasi hanya boleh memakai batch
              berstatus aman.
            </p>
          ) : (
            <p className="evidence-note">
              Tidak ada batch gagal uji pada data yang termuat saat ini.
            </p>
          )}
        </article>

        <article className="card">
          <h2>Batch perlu segera dipakai</h2>
          {rows.filter((row) => row.hoursLeft !== null && row.hoursLeft <= 48).length === 0 ? (
            <p className="evidence-note">
              Tidak ada batch yang sudah lewat batas layak atau tersisa ≤ 48 jam (sebagian batch mungkin belum punya tanggal).
            </p>
          ) : (
            <ul className="board-list">
              {rows
                .filter((row) => row.hoursLeft !== null && row.hoursLeft <= 48)
                .sort((a, b) => (a.hoursLeft ?? 0) - (b.hoursLeft ?? 0))
                .map((row) => (
                  <li key={`${row.location}-${row.commodity}-${row.id}`}>
                    <span className="board-list-title">
                      {row.location} · {row.commodity}
                    </span>
                    <span className="board-list-meta">
                      {row.kg === null ? "—" : formatKg(row.kg)} · {row.hoursLabel}
                    </span>
                  </li>
                ))}
            </ul>
          )}
        </article>
      </div>

      <article className="card">
        <h2>Status keamanan per batch</h2>
        {rows.length === 0 ? (
          <p className="evidence-note">
            {loading ? "Memuat batch…" : "Belum ada batch pada cakupan Anda."}
          </p>
        ) : (
          <>
              <div className="board-table-wrap">
              <table className="location-table">
            <thead>
              <tr>
                <th scope="col">Lokasi</th>
                <th scope="col">Komoditas</th>
                <th scope="col" className="num">
                  Jumlah
                </th>
                <th scope="col">Status keamanan</th>
                <th scope="col" className="num">
                  Kesegaran
                </th>
                <th scope="col">Layak sampai</th>
                <th scope="col">Sisa masa</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row: SafetyRow) => (
                <tr key={row.id ?? `${row.location}-${row.commodity}`}>
                  <td>{row.location}</td>
                  <td>{row.commodity}</td>
                  <td className="num">{row.kg === null ? "—" : formatKg(row.kg)}</td>
                  <td>
                    <span className={`board-badge board-badge-${row.tone}`}>{row.statusLabel}</span>
                  </td>
                  <td className="num">{row.freshness}</td>
                  <td>{row.usableUntil}</td>
                  <td>{row.hoursLabel}</td>
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
        <h2>Catatan sumber</h2>
        <p className="evidence-note">{FOOD_SAFETY_SOURCE_NOTE}</p>
        <p className="evidence-note">
          Kesegaran ditulis sebagai persen skor batch; sisa masa dihitung dari kolom{" "}
          <code>usable_until</code> relatif terhadap jam perangkat Anda. Nilai yang tidak ada di
          backend ditulis “—”.
        </p>
      </article>
    </section>
  );
}
