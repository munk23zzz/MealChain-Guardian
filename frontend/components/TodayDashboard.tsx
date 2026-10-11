"use client";

// Langkah 3 (arah Roy 2026-10-11): halaman "Hari Ini" — rekap operasional hari
// berjalan dari data NYATA, bukan angka karangan:
//   /decisions     → keputusan yang menunggu tindakan manusia + sisa waktunya
//   /batches       → batch yang sudah/akan kedaluwarsa (<48 jam)
//   /balance/map   → lokasi yang sedang kekurangan (komoditas yang dipilih)
//   /kpi           → tujuh indikator 24 jam terakhir
//   /ledger/verify → status rantai audit
//
// Aturan tampilan: nilai yang tidak diketahui ditulis "—" dan tidak pernah
// diganti 0. Jam sisa dihitung dari `now` (dari pemanggil) supaya tidak ada
// selisih hidrasi antara HTML server dan render klien.

import PageHeader from "./PageHeader";
import { fmtValue, STATE_LABEL } from "./KPIDashboard";
import { DECISION_TYPE_LABELS } from "./RecommendationCard";
import { formatKg } from "../lib/overview-format";
import {
  batchExpiry,
  dueLabel,
  freshnessLabel,
  ledgerSummary,
  pendingDecisions,
  shortageSummary,
  type TodayBatch,
  type TodayDecision,
  type TodayLocation,
} from "../lib/today";

type KpiEnvelope = {
  metrics?: {
    name?: string;
    unit?: string;
    value?: string | null;
    state?: string;
    reason?: string | null;
  }[];
  period?: { start?: string | null; end?: string | null };
} | null;

const STATUS_LABELS: Record<string, string> = {
  PENDING_APPROVAL: "Menunggu persetujuan",
  NEEDS_VERIFICATION: "Menunggu verifikasi",
  VERIFIER_FLAGGED: "Ditandai verifikator",
};

const SAFETY_LABELS: Record<string, string> = {
  pass: "lolos uji",
  fail: "gagal uji",
  pending: "uji tertunda",
};

function statusLabel(status: unknown): string {
  const key = String(status ?? "").toUpperCase();
  return STATUS_LABELS[key] ?? (key ? key.replace(/_/g, " ").toLowerCase() : "—");
}

function typeLabel(decisionType: unknown): string {
  const key = String(decisionType ?? "");
  return DECISION_TYPE_LABELS[key] ?? (key ? key.replace(/_/g, " ") : "Rekomendasi");
}

/** Tanggal hari ini dalam bahasa manusia; "—" kalau jam klien belum siap. */
function todayLabel(now: Date | null): string {
  if (!now) return "—";
  return now.toLocaleDateString("id-ID", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export default function TodayDashboard({
  decisions,
  batches,
  locations,
  commodity,
  kpi,
  ledger,
  now,
  batchesLoading = false,
  batchesError = null,
  onRetry,
  onOpenDecision,
  onOpenAllDecisions,
  onOpenLocation,
}: {
  decisions: TodayDecision[];
  batches: TodayBatch[] | null;
  locations: TodayLocation[];
  commodity?: string | null;
  kpi: KpiEnvelope;
  ledger: unknown;
  now: Date | null;
  batchesLoading?: boolean;
  batchesError?: string | null;
  onRetry?: () => void;
  onOpenDecision?: (decisionId: string) => void;
  onOpenAllDecisions?: () => void;
  onOpenLocation?: (location: string) => void;
}) {
  // Semua turunan dihitung dari `now` yang sama; kalau jam belum siap, label
  // waktu ditulis "—" (bukan jam mesin server yang bisa menyesatkan).
  const clock = now ?? new Date(0);
  const pending = pendingDecisions(decisions, clock);
  const batchState = batchExpiry(batches ?? [], clock);
  const shortage = shortageSummary(locations);
  const ledgerState = ledgerSummary(ledger);
  const metrics = Array.isArray(kpi?.metrics) ? kpi!.metrics! : [];

  return (
    <section className="today-page">
      <PageHeader
        title="Hari Ini"
        description="Rekap operasional hari berjalan: keputusan yang menunggu tindakan, batch yang mendekati kedaluwarsa, lokasi kekurangan, KPI 24 jam, dan status rantai audit — semua dari API."
        meta={
          <span className="page-header-pills">
            <span className="commodity-pill">{todayLabel(now)}</span>
            <span className="commodity-pill">
              Komoditas {commodity ? commodity : "—"}
            </span>
          </span>
        }
      />

      <div className="today-grid">
        {/* 1. Keputusan yang menunggu tindakan manusia */}
        <article className="card today-card today-pending">
          <div className="today-card-head">
            <h2>Menunggu tindakan</h2>
            <span className="today-count">{pending.count}</span>
          </div>
          <p className="today-card-note">
            {pending.count === 0
              ? "Tidak ada keputusan yang menunggu tindakan manusia."
              : [
                  pending.nextDueLabel !== "—"
                    ? `Agenda terdekat ${pending.nextDueLabel}`
                    : "Tidak ada agenda yang belum lewat tenggat",
                  pending.overdueCount ? `${pending.overdueCount} sudah lewat tenggat` : null,
                ]
                  .filter(Boolean)
                  .join(" · ")}
          </p>
          {pending.items.length > 0 && (
            <ul className="today-list">
              {pending.items.slice(0, 6).map((decision, index) => {
                const expired =
                  pending.overdueCount > 0 && index < pending.overdueCount;
                return (
                  <li key={String(decision.decision_id ?? index)} className="today-row">
                    <div className="today-row-main">
                      <span className="today-row-title">{typeLabel(decision.decision_type)}</span>
                      <span className="today-row-meta">
                        {formatKg(decision.quantity_kg as number)} · {statusLabel(decision.status)}
                      </span>
                    </div>
                    <span className={`today-due${expired ? " today-due-over" : ""}`}>
                      {dueLabel(decision.expires_at, clock)}
                    </span>
                    {onOpenDecision && decision.decision_id && (
                      <button
                        type="button"
                        className="button today-row-action"
                        onClick={() => onOpenDecision(String(decision.decision_id))}
                      >
                        Buka
                      </button>
                    )}
                  </li>
                );
              })}
              {pending.items.length > 6 && (
                <li className="today-more">
                  <span>+{pending.items.length - 6} keputusan lain menunggu tindakan</span>
                  {onOpenAllDecisions && (
                    <button
                      type="button"
                      className="button today-row-action"
                      onClick={onOpenAllDecisions}
                    >
                      Lihat semua
                    </button>
                  )}
                </li>
              )}
            </ul>
          )}
        </article>

        {/* 2. Batch yang sudah/akan kedaluwarsa */}
        <article className="card today-card today-batches">
          <div className="today-card-head">
            <h2>Batch mendekati kedaluwarsa</h2>
            <span className="today-count">
              {batches ? batchState.expired.length + batchState.dueSoon.length : "—"}
            </span>
          </div>
          {batchesError ? (
            <p className="today-card-note today-error" role="alert">
              Gagal memuat batch: {batchesError}
              {onRetry && (
                <button type="button" className="button today-row-action" onClick={onRetry}>
                  Coba lagi
                </button>
              )}
            </p>
          ) : batchesLoading || !batches ? (
            <p className="today-card-note">Memuat data batch…</p>
          ) : (
            <>
              <p className="today-card-note">
                {batchState.expired.length + batchState.dueSoon.length === 0
                  ? "Tidak ada batch kedaluwarsa atau mendekati kedaluwarsa (<48 jam)."
                  : [
                      batchState.expired.length
                        ? `Kedaluwarsa ${batchState.expired.length} batch (${formatKg(
                            batchState.expiredKg
                          )})`
                        : null,
                      batchState.dueSoon.length
                        ? `segera ${batchState.dueSoon.length} batch (${formatKg(
                            batchState.dueSoonKg
                          )})`
                        : null,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
              </p>
              <ul className="today-list">
                {[...batchState.expired, ...batchState.dueSoon].slice(0, 6).map((batch, index) => {
                  const isExpired = index < batchState.expired.length;
                  return (
                    <li
                      key={String(batch.id ?? index)}
                      className={`today-row${isExpired ? " today-row-expired" : ""}`}
                    >
                      <div className="today-row-main">
                        <span className="today-row-title">
                          {batch.location ?? "—"} · {batch.commodity ?? "—"}
                        </span>
                        <span className="today-row-meta">
                          {[
                            formatKg(batch.quantity_kg as number),
                            freshnessLabel(batch.freshness_score) !== "—"
                              ? `kesegaran ${freshnessLabel(batch.freshness_score)}`
                              : null,
                            batch.food_safety_status
                              ? (SAFETY_LABELS[String(batch.food_safety_status)] ??
                                String(batch.food_safety_status))
                              : null,
                          ]
                            .filter(Boolean)
                            .join(" · ")}
                        </span>
                      </div>
                      <span className={`today-due${isExpired ? " today-due-over" : ""}`}>
                        {dueLabel(batch.usable_until, clock)}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </>
          )}
        </article>

        {/* 3. Lokasi yang kekurangan (komoditas aktif) */}
        <article className="card today-card today-shortage">
          <div className="today-card-head">
            <h2>Lokasi shortage</h2>
            <span className="today-count">{shortage.count}</span>
          </div>
          <p className="today-card-note">
            {shortage.count === 0
              ? "Tidak ada lokasi kekurangan untuk komoditas ini."
              : `Total kekurangan ${formatKg(shortage.totalKg)} (komoditas ${commodity ?? "—"})`}
          </p>
          {shortage.items.length > 0 && (
            <ul className="today-list">
              {shortage.items.slice(0, 6).map((row) => (
                <li key={String(row.location)} className="today-row">
                  <div className="today-row-main">
                    <span className="today-row-title">{row.location ?? "—"}</span>
                    <span className="today-row-meta">{row.region ?? "—"}</span>
                  </div>
                  <span className="today-due today-due-over">{row.label}</span>
                  {onOpenLocation && row.location && (
                    <button
                      type="button"
                      className="button today-row-action"
                      onClick={() => onOpenLocation(String(row.location))}
                    >
                      Lihat di peta
                    </button>
                  )}
                </li>
              ))}
              {shortage.items.length > 6 && (
                <li className="today-more">
                  +{shortage.items.length - 6} lokasi lain kekurangan (lihat peta)
                </li>
              )}
            </ul>
          )}
        </article>

        {/* 4. KPI 24 jam terakhir */}
        <article className="card today-card today-kpi">
          <div className="today-card-head">
            <h2>KPI 24 jam</h2>
            <span className="today-count">
              {metrics.filter((m) => m.value !== null && m.value !== undefined).length}/
              {metrics.length || "—"}
            </span>
          </div>
          <p className="today-card-note">
            {metrics.length === 0
              ? "Belum ada jawaban /kpi untuk periode ini."
              : "Metrik yang belum punya data ditulis “—” (tidak diganti 0)."}
          </p>
          {metrics.length > 0 && (
            <ul className="today-list">
              {metrics.map((metric, index) => {
                const shown = fmtValue(String(metric.unit ?? ""), metric.value ?? null);
                return (
                  <li key={String(metric.name ?? index)} className="today-row">
                    <div className="today-row-main">
                      <span className="today-row-title">{metric.name ?? "—"}</span>
                      <span className="today-row-meta">
                        {STATE_LABEL[String(metric.state ?? "")] ??
                          (metric.state ?? "keadaan tidak diketahui")}
                      </span>
                    </div>
                    <span className={`today-value${shown === null ? " today-value-none" : ""}`}>
                      {shown === null ? "—" : `${shown} ${metric.unit === "IDR" ? "" : metric.unit}`}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </article>

        {/* 5. Rantai audit (Merkle ledger) */}
        <article className="card today-card today-ledger">
          <div className="today-card-head">
            <h2>Rantai audit</h2>
            <span className={`today-badge today-badge-${ledgerState.ok === true ? "ok" : ledgerState.ok === false ? "bad" : "unknown"}`}>
              {ledgerState.statusLabel}
            </span>
          </div>
          <ul className="today-list">
            <li className="today-row">
              <div className="today-row-main">
                <span className="today-row-title">Blok terverifikasi</span>
                <span className="today-row-meta">GET /ledger/verify</span>
              </div>
              <span className="today-value">{ledgerState.blocksLabel}</span>
            </li>
            <li className="today-row">
              <div className="today-row-main">
                <span className="today-row-title">Head hash</span>
                <span className="today-row-meta">dipotong 10 karakter pertama</span>
              </div>
              <span className="today-value today-value-mono">{ledgerState.headShort}</span>
            </li>
          </ul>
        </article>
      </div>
    </section>
  );
}
