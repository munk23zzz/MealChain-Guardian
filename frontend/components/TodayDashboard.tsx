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
import TodayAgendaCalendar from "./TodayAgendaCalendar";
import TodaySummary, { jumpToSection } from "./TodaySummary";
import { type AgendaPickerProps } from "./AgendaDatePicker";
import { clampDayStep, type AgendaPayload } from "../lib/agenda";
import { RANGE_MAX, RANGE_MIN } from "../lib/demo-data";
import { fmtValue, unitLabel, STATE_LABEL } from "./KPIDashboard";
import { DECISION_TYPE_LABELS } from "./RecommendationCard";
import { formatKg } from "../lib/overview-format";
import { kodeWilayah } from "../lib/wilayah";
import {
  DUE_SOON_HOURS,
  batchExpiry,
  dueLabel,
  freshnessLabel,
  kpiPeriodLabel,
  ledgerSummary,
  pendingDecisions,
  shortageSummary,
  summaryTiles,
  updatedLabel,
  type TodayBatch,
  type TodayDecision,
  type TodayLocation,
} from "../lib/today";
import { LoadingState } from "./LoadingState";

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

// Jumlah agenda yang ditampilkan; dipakai di slice DAN di kalimat "+N lain"
// supaya angka di layar tidak bisa menyimpang dari daftar yang benar-benar
// dirender saat batas ini diubah (audit angka 18 Okt 2026).
const MAKS_AGENDA_KEPUTUSAN = 6;

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

/** Sapaan dari jam KLIEN. null = jam belum siap → tidak menyapa (jangan menebak pagi/siang). */
function greeting(now: Date | null, name?: string | null): string | null {
  if (!now) return null;
  const jam = now.getHours();
  const waktu = jam < 11 ? "pagi" : jam < 15 ? "siang" : jam < 19 ? "sore" : "malam";
  return `Selamat ${waktu}${name ? `, ${name}` : ""}`;
}

type DueTone = "over" | "soon" | "none";

/**
 * Nada chip sisa waktu — dari tanggal yang benar-benar ada:
 * "over" = sudah lewat (diputuskan pemanggil, karena urutan daftar sudah
 * memisahkan yang lewat), "soon" = ≤ DUE_SOON_HOURS (ambang 48 jam yang sudah
 * dipakai batch di halaman ini — bukan ambang baru), "none" = masih jauh ATAU
 * tanggalnya tidak terbaca ATAU jam klien belum siap.
 */
function dueTone(value: unknown, now: Date | null, over: boolean): DueTone {
  if (over) return "over";
  if (!now) return "none";
  const ms = new Date(String(value ?? "")).getTime();
  if (!Number.isFinite(ms)) return "none";
  return ms - now.getTime() <= DUE_SOON_HOURS * 60 * 60 * 1000 ? "soon" : "none";
}

function dueClass(tone: DueTone): string {
  return tone === "none" ? "today-due" : `today-due today-due-${tone}`;
}

export default function TodayDashboard({
  decisions,
  batches,
  locations,
  commodity,
  kpi,
  ledger,
  now,
  greetingName = null,
  batchesLoading = false,
  batchesError = null,
  onRetry,
  agenda = null,
  agendaLoading = false,
  agendaError = null,
  agendaDate,
  agendaToday,
  agendaMonth,
  agendaPicker,
  onAgendaSelect = () => {},
  onAgendaShiftDay = () => {},
  onAgendaRetry,
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
  /** Nama peran untuk sapaan header (mis. "SPPG Operations Lead"). */
  greetingName?: string | null;
  batchesLoading?: boolean;
  batchesError?: string | null;
  onRetry?: () => void;
  /** Agenda harian (kalender) — data dari GET /agenda lewat hook halaman. */
  agenda?: AgendaPayload;
  agendaLoading?: boolean;
  agendaError?: string | null;
  /** Tanggal terpilih + "hari ini" menurut WIB (keduanya dari halaman). */
  agendaDate?: string;
  agendaToday?: string;
  agendaMonth?: { year: number; month: number };
  /** Popup pemilih tanggal (permintaan pemilik 2026-10-17) — bulan draft, data
   *  bulan itu, dan aksinya. Dirakit halaman; kalender tidak memuat data sendiri. */
  agendaPicker?: AgendaPickerProps;
  onAgendaSelect?: (date: string) => void;
  /** Langkah HARI (bukan bulan) di kepala kartu Agenda harian — grid bulan besar
   *  sudah dihapus, jadi ‹ › berarti sehari. */
  onAgendaShiftDay?: (delta: number) => void;
  onAgendaRetry?: () => void;
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

  // Desain ulang 2026-10-17: status dulu (strip ringkasan) → pengecualian →
  // rincian. Tiles dihitung di `lib/today.ts` (diuji tanpa DOM) supaya aturan
  // "— bukan 0" tidak ditulis ulang di JSX.
  const tiles = summaryTiles({
    pending,
    batch: batchState,
    batchLoaded: batches !== null,
    shortage,
    metrics: metrics as { value?: string | null }[],
    ledger: ledgerState,
  });
  // Tombol ‹ › agenda mati di tepi rentang data: melangkah ke luar rentang hanya
  // menampilkan hari kosong yang tampak seperti "tidak ada operasi hari itu".
  const hariTerpilih = agendaDate ?? null;
  const hariKiriMati =
    !hariTerpilih || clampDayStep(hariTerpilih, -1, RANGE_MIN, RANGE_MAX) === null;
  const hariKananMati =
    !hariTerpilih || clampDayStep(hariTerpilih, 1, RANGE_MIN, RANGE_MAX) === null;
  // Periode KPI dari datanya sendiri (bukan "24 jam terakhir" yang ditebak).
  const periodeKpi = kpiPeriodLabel(kpi?.period);

  return (
    <section className="today-page">
      <PageHeader
        title="Hari Ini"
        eyebrow={greeting(now, greetingName)}
        description="Status hari berjalan lebih dulu, lalu yang perlu tindakan, lalu rinciannya — semua dari API."
        meta={
          <span className="page-header-pills">
            <span className="commodity-pill">{todayLabel(now)}</span>
            <span className="commodity-pill">
              Komoditas {commodity ? commodity : "—"}
            </span>
            {/* Kapan data ini diambil. Dashboard yang menampilkan angka tanpa
                memberi tahu usianya membuat orang bertindak atas data basi. */}
            {now ? <span className="commodity-pill">{updatedLabel(now)}</span> : null}
          </span>
        }
      />

      <TodaySummary tiles={tiles} onJump={jumpToSection} />

      {/* Kalender lama (grid bulan besar) DIHAPUS dari posisi ini — pemilik:
          "hapus untuk kalender agenda yang yang bukan pop up namun untuk
          informasinya tetap di pakai". Kartu "Agenda harian" (info hari
          terpilih + ikon pemilih tanggal) kini berdiri setelah daftar
          pengecualian, sesuai hierarki: status → pengecualian → agenda → rincian. */}

      <div className="today-grid">
        {/* 1. Keputusan yang menunggu tindakan manusia */}
        <article className="card today-card today-pending" id="today-action" tabIndex={-1}>
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
              {pending.items.slice(0, MAKS_AGENDA_KEPUTUSAN).map((decision, index) => {
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
                    <span className={dueClass(dueTone(decision.expires_at, now, expired))}>
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
              {pending.items.length > MAKS_AGENDA_KEPUTUSAN && (
                <li className="today-more">
                  <span>
                    +{pending.items.length - MAKS_AGENDA_KEPUTUSAN} keputusan lain
                    menunggu tindakan
                  </span>
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

        {/* 2. Agenda harian (desain ulang 2026-10-17): grid bulan besar dibuang,
            info hari terpilih tetap — itulah yang dicari pengguna tiap hari.
            Pindah hari lewat ‹ › ; tanggal jauh lewat popup pemilih tanggal.
            Muncul hanya bila halaman mengirim state kalender, supaya komponen
            ini tetap bisa dirender tes lama tanpa state kalender. */}
        {agendaDate && agendaMonth && agendaPicker ? (
          <TodayAgendaCalendar
            agenda={agenda}
            loading={agendaLoading}
            error={agendaError}
            selected={agendaDate}
            today={agendaToday}
            prevDisabled={hariKiriMati}
            nextDisabled={hariKananMati}
            onSelect={onAgendaSelect}
            onShiftDay={onAgendaShiftDay}
            onRetry={onAgendaRetry}
            picker={agendaPicker}
          />
        ) : null}

        <div className="today-detail-grid">
        {/* 3. Batch yang sudah/akan kedaluwarsa */}
        <article className="card today-card today-batches" id="today-batches" tabIndex={-1}>
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
            <p className="today-card-note"><LoadingState label="Memuat data batch…" /></p>
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
                          {kodeWilayah(batch.location)} · {batch.commodity ?? "—"}
                        </span>
                        <span className="today-row-meta">
                          {[
                            formatKg(batch.quantity_kg as number),
                            freshnessLabel(batch.freshness_score) !== "—"
                              ? `kesegaran ${freshnessLabel(batch.freshness_score)}`
                              : null,
                            batch.safety_status
                              ? (SAFETY_LABELS[String(batch.safety_status)] ??
                                String(batch.safety_status))
                              : null,
                          ]
                            .filter(Boolean)
                            .join(" · ")}
                        </span>
                      </div>
                      <span className={dueClass(dueTone(batch.usable_until, now, isExpired))}>
                        {dueLabel(batch.usable_until, clock)}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </>
          )}
        </article>

        {/* 4. KPI 24 jam terakhir */}
        <article className="card today-card today-kpi" id="today-kpi" tabIndex={-1}>
          <div className="today-card-head">
            <h2>KPI 24 jam</h2>
            <span className="today-count">
              {metrics.filter((m) => m.value !== null && m.value !== undefined).length}/
              {metrics.length || "—"}
            </span>
          </div>
          <p className="today-card-note">
            {periodeKpi ? `${periodeKpi}. ` : ""}
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
                      {shown === null ? "—" : `${shown} ${unitLabel(metric.unit)}`}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </article>

        {/* 5. Lokasi yang kekurangan (komoditas aktif) */}
        <article className="card today-card today-shortage" id="today-shortage" tabIndex={-1}>
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
                    <span className="today-row-title">{kodeWilayah(row.location)}</span>
                    <span className="today-row-meta">{row.region ?? "—"}</span>
                  </div>
                  {/* Bukan label waktu: ini besar kekurangan. Kelasnya sendiri
                      supaya "merah" di sini berarti "kekurangan", bukan "lewat
                      tenggat" — dan jam klien belum siap tidak mengubahnya. */}
                  <span className="today-due today-due-short">{row.label}</span>
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

        {/* 6. Rantai audit (Merkle ledger) */}
        <article className="card today-card today-ledger" id="today-ledger" tabIndex={-1}>
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
              </div>
              <span className="today-value">{ledgerState.blocksLabel}</span>
            </li>
            <li className="today-row">
              <div className="today-row-main">
                <span className="today-row-title">Head hash</span>
              </div>
              <span className="today-value today-value-mono">{ledgerState.headShort}</span>
            </li>
          </ul>
        </article>
        </div>
      </div>
    </section>
  );
}
