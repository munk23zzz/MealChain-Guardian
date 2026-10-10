import type { ReactNode } from "react";
import {
  formatBalanceGap,
  formatBalanceStatus,
  formatKg,
  summarizeBalanceStatus,
  type BalanceMapLocation,
} from "../lib/overview-format";
import styles from "./OverviewLocationBreakdown.module.css";

type Props = {
  locations: readonly BalanceMapLocation[];
  loading?: boolean;
};

function StatusBadge({ status }: Pick<BalanceMapLocation, "status">) {
  const known = status === "shortage" || status === "surplus" || status === "balanced";
  return (
    <span className={`${styles.status} ${known ? styles[status] : styles.unknown}`}>
      <span className={styles.statusDot} aria-hidden="true" />
      {formatBalanceStatus(status)}
    </span>
  );
}

function Value({ label, value, emphasis = false }: { label: string; value: string; emphasis?: boolean }) {
  return (
    <span className={emphasis ? styles.gap : undefined} aria-label={`${label}: ${value}`}>
      <span className={styles.mobileLabel}>{label}: </span>{value}
    </span>
  );
}

function EmptyState({ loading }: { loading: boolean }) {
  return (
    <div className={styles.empty} aria-busy={loading || undefined}>
      <p>{loading ? "Memuat data lokasi…" : "Belum ada data lokasi"}</p>
      <span>{loading ? "Mengambil kondisi pasokan terbaru." : "Belum ada snapshot pasokan untuk ditampilkan."}</span>
      {loading && (
        <div className="skeleton-rows" aria-hidden="true">
          <div className="skeleton skeleton-row" />
          <div className="skeleton skeleton-row" />
          <div className="skeleton skeleton-row" />
        </div>
      )}
    </div>
  );
}

export default function OverviewLocationBreakdown({ locations, loading = false }: Props) {
  let content: ReactNode;
  if (!locations.length) {
    content = <EmptyState loading={loading} />;
  } else {
    content = (
      <>
        <p className={styles.summary} aria-label="Ringkasan status lokasi">
          {summarizeBalanceStatus(locations)}
        </p>
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr><th>Lokasi</th><th>Status</th><th>Pasokan</th><th>Kebutuhan</th><th>Selisih</th></tr>
            </thead>
            <tbody>
              {locations.map((location, index) => (
                <tr key={`${location.location}-${index}`} data-location-row={location.location}>
                  <th scope="row">{location.location}</th>
                  <td><StatusBadge status={location.status} /></td>
                  <td><Value label="Pasokan" value={formatKg(location.supply_kg)} /></td>
                  <td><Value label="Kebutuhan" value={formatKg(location.demand_kg)} /></td>
                  <td><Value label="Selisih" value={formatBalanceGap(location)} emphasis /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </>
    );
  }
  return <section className={styles.breakdown} aria-label="Breakdown lokasi">{content}</section>;
}
