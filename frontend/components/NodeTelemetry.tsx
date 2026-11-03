"use client";

// Telemetri node — kolom kanan panel peta, meniru kartu "Node Quick Telemetry
// Ledger" di mockup `mockupui/overview_map_supply_status` (kartu terang dengan
// batang aksen gelap di kiri, judul node + badge status, baris angka mono).
//
// Semua angka datang dari GET /balance/map (read model yang sama dengan peta,
// jadi tidak ada rumus kedua). Lokasi yang tidak dipilih / tidak ada di data
// ditulis apa adanya — bukan ditebak dan bukan diisi 0.
import {
  formatBalanceGap,
  formatBalanceStatus,
  formatKg,
  type BalanceMapLocation,
} from "../lib/overview-format";
import { nodeGauges, pinTone } from "../lib/map-console";
import { ALL_LOCATIONS } from "../lib/topbar";
import { LoadingState } from "./LoadingState";
import { kodeWilayah } from "../lib/wilayah";

function coordinate(value: number | string | null | undefined): string {
  const numeric = Number(value);
  return value == null || value === "" || !Number.isFinite(numeric) ? "—" : numeric.toFixed(4);
}

export default function NodeTelemetry({
  locations,
  activeLocation,
  loading = false,
}: {
  locations: readonly BalanceMapLocation[];
  /** Nilai dropdown cakupan top bar; ALL_LOCATIONS berarti tanpa sorotan. */
  activeLocation: string | null;
  loading?: boolean;
}) {
  const rows = locations ?? [];
  const requested =
    activeLocation && activeLocation !== ALL_LOCATIONS ? activeLocation : null;
  const selected = requested ? rows.find((row) => row.location === requested) ?? null : null;
  const gauges = selected ? nodeGauges(selected) : null;

  return (
    <section className="card node-telemetry" aria-label="Telemetri node">
      <div className="card-header">
        <h3>Telemetri Node</h3>
      </div>
      <div className="node-telemetry-body">
        {!requested && (
          <p className="node-telemetry-empty">
            {loading
              ? <LoadingState label="Memuat kondisi lokasi…" />
              : "Belum ada lokasi yang disorot. Pilih lokasi lewat dropdown cakupan di bar atas untuk membuka telemetri node ini."}
          </p>
        )}
        {requested && !selected && (
          <p className="node-telemetry-empty">
            {`Lokasi "${requested}" tidak ada di data koridor komoditas ini.`}
          </p>
        )}
        {selected && gauges && (
          <>
            <div className="node-telemetry-title">
              <span className="node-telemetry-name">{kodeWilayah(selected.location)}</span>
              <span className={`node-badge node-badge-${pinTone(selected.status)}`}>
                {formatBalanceStatus(selected.status)}
              </span>
            </div>
            <p className="node-telemetry-meta">
              {`Wilayah: ${selected.region ?? "—"} · Koordinat: ${coordinate(selected.latitude)}, ${coordinate(selected.longitude)}`}
            </p>
            <dl className="node-gauge-list">
              <div className="node-gauge">
                <dt>Pasokan</dt>
                <dd>{formatKg(gauges.supply.value)}</dd>
                <div className="node-gauge-track" aria-hidden="true">
                  <span
                    className="node-gauge-bar node-gauge-bar-supply"
                    style={{ width: `${gauges.supply.share}%` }}
                  />
                </div>
              </div>
              <div className="node-gauge">
                <dt>Kebutuhan</dt>
                <dd>{formatKg(gauges.demand.value)}</dd>
                <div className="node-gauge-track" aria-hidden="true">
                  <span
                    className="node-gauge-bar node-gauge-bar-demand"
                    style={{ width: `${gauges.demand.share}%` }}
                  />
                </div>
              </div>
            </dl>
            <p className="node-telemetry-gap">
              {`Selisih: ${formatBalanceGap(selected)}`}
            </p>
          </>
        )}
      </div>
    </section>
  );
}
