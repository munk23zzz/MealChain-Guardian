"use client";

// KPIDashboard (S4-03) — tujuh KPI dari GET /kpi via fetchKpis().
// Presentational murni: envelope dari server dirender apa adanya.
// Null TIDAK diganti 0 (ruling O-KPI); state available/no_data/
// unavailable selalu terlihat + reason bila bukan available.
// Angka format id-ID; SDC format IDR.
//
// Restyle 2026-10-10: layout mengikuti mockup Stitch
// (mockupui/kpi_analytics_dashboard/code.html) — header konsol dengan
// breadcrumb, bento grid kartu (dua baris × empat), ikon inline SVG.
// Kontrak markup untuk test TIDAK berubah (class kpi-* dipin).

import { useEffect, useRef, useState } from "react";

import KpiDetailPanel from "./KpiDetailPanel";
import KpiMetaLine from "./KpiMetaLine";
import PageHeader from "./PageHeader";
import EmptyState from "./EmptyState";
import {
  bulletOf,
  directionLabel,
  KPI_WINDOWS,
  metricDescription,
  rapikanTeksBackend,
  type KpiWindowKey,
} from "../lib/kpi";
import {
  KPI_SCOPES,
  provenanceLines,
  scopeLabel,
  type KpiScope,
} from "../lib/kpi-provenance";

/** Deskripsi halaman — satu teks, dipakai kepala halaman di sini DAN di
 *  `PageShell` tab gabungan, supaya dua tempat tidak menulis dua kalimat. */
export const DESKRIPSI_HALAMAN =
  "Tujuh indikator kontinuitas pangan. Angka yang belum bisa dihitung ditulis alasannya.";

const UNIT_FMT: Record<string, (v: string) => string> = {
  IDR: (v) =>
    "Rp" + Number(v).toLocaleString("id-ID", { maximumFractionDigits: 0 }),
};

/** Format nilai metrik KPI (id-ID; SDC memakai IDR). Diekspor supaya halaman
 *  "Hari Ini" memakai format yang SAMA — dua format persen di satu aplikasi
 *  akan terbaca seperti dua sumber data. */
export function fmtValue(unit: string, value: string | null): string | null {
  if (value === null) return null;
  const fmt = UNIT_FMT[unit];
  return fmt ? fmt(value) : Number(value).toLocaleString("id-ID", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/** Nama satuan untuk LAYAR. Nilai `unit` dari server tidak diubah — hanya
 *  namanya yang diterjemahkan, supaya kontrak API tetap dan fixture tetap sah
 *  (WS-C, QA 16 Okt: layar menampilkan "percent" berbahasa Inggris).
 *  Satuan tak dikenal ditampilkan apa adanya — jangan mengarang nama. */
const UNIT_LABELS: Record<string, string> = {
  IDR: "", // nilainya sudah berawalan Rp — jangan ditulis dua kali
  percent: "persen",
  percentage: "persen",
  pct: "persen",
  minutes: "menit",
};

export function unitLabel(unit: unknown): string {
  const key = String(unit ?? "").trim();
  if (!key) return "";
  return key in UNIT_LABELS ? UNIT_LABELS[key] : key;
}

/** Keadaan metrik dari backend (kata apa adanya, tidak dikarang). Diekspor
 *  untuk halaman "Hari Ini" supaya istilahnya sama dengan tab KPI. */
export const STATE_LABEL: Record<string, string> = {
  available: "tersedia",
  no_data: "belum ada data",
  unavailable: "tidak tersedia",
};

/**
 * Pil cakupan data: operasional vs simulasi (Fase 8).
 *
 * Kenapa ada: sejak kartu KPI memisahkan fakta demo dari fakta kerja, pembaca
 * harus tahu angka mana yang sedang ia lihat. Komponen ini hanya MEMILIH
 * cakupan; ia tidak menghitung apa pun dan tidak menebak mode dari angka.
 *
 * `aria-describedby` + teks penjelas dipakai supaya perbedaannya tidak hanya
 * tersirat dari warna pil (pembaca layar tidak melihat warna).
 */
export function KpiScopeToggle({
  scope,
  onScopeChange,
  disabled = false,
  disabledReason = null,
}: {
  scope: KpiScope;
  onScopeChange?: (scope: KpiScope) => void;
  /** Simulasi butuh sesi demo aktif; tanpa sesi, pilihannya dimatikan. */
  disabled?: boolean;
  disabledReason?: string | null;
}) {
  const aktif = KPI_SCOPES.find((s) => s.key === scope) ?? KPI_SCOPES[0];
  return (
    <div
      className="kpi-scope-toggle"
      role="group"
      aria-label="Cakupan data KPI"
      data-testid="kpi-scope-toggle"
      data-scope={scope}
      aria-describedby="kpi-scope-explanation"
    >
      <span className="kpi-period-label">Cakupan data:</span>
      {KPI_SCOPES.map((s) => {
        const dipilih = s.key === scope;
        return (
          <button
            key={s.key}
            type="button"
            className={`commodity-pill kpi-scope-pill${dipilih ? " is-active" : ""}`}
            data-scope-option={s.key}
            aria-pressed={dipilih}
            disabled={disabled && s.key === "demo"}
            onClick={() => onScopeChange?.(s.key)}
          >
            {s.label}
          </button>
        );
      })}
      <span id="kpi-scope-explanation" className="kpi-scope-hint">
        {disabled && disabledReason ? `${disabledReason} ` : ""}
        {aktif.hint}
      </span>
    </div>
  );
}

function trendClass(trend: string | null): string | null {
  if (trend === "up") return "trend-up";
  if (trend === "down") return "trend-down";
  if (trend === "flat") return "trend-flat";
  return null;
}

// Ikon inline SVG kecil per metrik — tanpa emoji, mengikuti mockup Stitch
// (restaurant/eco/sync_alt/wallet/gavel/timer/verified_user disederhanakan).
function MetricIcon({ name }: { name: string }) {
  const n = name.toLowerCase();
  let d = "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm0 3v7"; // fallback: titik lingkaran
  if (n.includes("continuity")) {
    // piring + garis menu (restaurant)
    d = "M3 13h18a9 9 0 0 1-18 0ZM7 4v6M10 4v6M10 7H7M17 4c-1.5 1-2 3-2 6";
  } else if (n.includes("avoidable") || n.includes("loss")) {
    // daun (eco)
    d = "M6 20c0-8 4-12 12-12 0 8-4 12-12 12Zm0 0c2-4 5-6 9-7";
  } else if (n.includes("imbalance") || n.includes("rebalance")) {
    // panah bolak-balik (sync_alt)
    d = "M7 8h11m0 0-3-3m3 3-3 3M17 16H6m0 0 3-3m-3 3 3 3";
  } else if (n.includes("cost") || n.includes("delivered")) {
    // dompet (account_balance_wallet)
    d = "M3 7a2 2 0 0 1 2-2h12v3h3a1 1 0 0 1 1 1v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Zm13 6h4";
  } else if (n.includes("procurement") || n.includes("deviation")) {
    // palu hakim (gavel)
    d = "M14 3l7 7-2 2-7-7 2-2Zm-3 5 5 5-8 8H3v-5l8-8Z";
  } else if (n.includes("decision") || n.includes("time")) {
    // stopwatch (timer)
    d = "M12 8a7 7 0 1 1 0 14 7 7 0 0 1 0-14Zm0 3v4l3 2M9 2h6";
  } else if (n.includes("evidence") || n.includes("completeness")) {
    // perisai centang (verified_user)
    d = "M12 2l8 3v6c0 5-3.5 9-8 11-4.5-2-8-6-8-11V5l8-3Zm-3 10 2.5 2.5L16 10";
  }
  return (
    <span className="kpi-icon" aria-hidden="true">
      <svg
        viewBox="0 0 24 24"
        width="20"
        height="20"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d={d} />
      </svg>
    </span>
  );
}

export default function KPIDashboard({
  kpi,
  loading = false,
  error = null,
  onRetry,
  windowKey = "today",
  onWindowChange,
  scope = "operational",
  onScopeChange,
  scopeDisabledReason = null,
  showHeader = true,
}: {
  kpi: any | null;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  /** Jendela yang sedang diminta PARENT (halaman) — komponen tidak menyimpan
   *  state sendiri, supaya angka di layar dan label periode tidak bisa berbeda. */
  windowKey?: KpiWindowKey;
  onWindowChange?: (key: KpiWindowKey) => void;
  /** Cakupan data yang diminta halaman: fakta kerja atau satu sesi demo. */
  scope?: KpiScope;
  onScopeChange?: (scope: KpiScope) => void;
  /** Diisi halaman bila tidak ada sesi demo aktif (simulasi tidak bisa dipilih). */
  scopeDisabledReason?: string | null;
  /** `false` = kepala halaman tidak dirender karena cangkang halaman
   *  (`PageShell`) sudah memilikinya. Default `true` supaya pemakaian
   *  sendirian tetap punya judul. */
  showHeader?: boolean;
}) {
  // Satu panel penjelasan untuk SATU kartu (permintaan pemilik 29 Okt 2026:
  // "ketika KPI diklik muncul penjelasan detail di bawah sub sub KPI, ada 1
  // shape informasi dari KPI yang diklik"). `null` = tidak ada panel sama
  // sekali — blok kosong permanen hanya menambah tinggi halaman.
  const [terpilih, setTerpilih] = useState<string | null>(null);
  // Simpan tombol per nama kartu: setelah panel ditutup, fokus kembali ke
  // tombol yang tadi diklik. Tanpa ini pengguna papan ketik/pembaca layar
  // kehilangan tempatnya dan mulai dari awal bagian.
  const kartuRef = useRef<Record<string, HTMLElement | null>>({});
  // Panel rincian hidup DI BAWAH grid (bukan di dalam kartu). Pada layar biasa
  // kartu baris pertama berakhir sekitar 606 px sementara panel mulai di
  // 873 px — jadi tanpa digulir, membuka rincian tampak seperti klik yang mati.
  const panelRef = useRef<HTMLElement | null>(null);

  // Tahap 3 redesign (29 Okt 2026): saat panel dibuka, panel digulir ke layar
  // dan fokus pindah ke judulnya. Menggulir saja tidak cukup untuk pengguna
  // papan ketik (Tab berikutnya akan kembali ke tempat lama), dan memindahkan
  // fokus saja tidak cukup untuk pengguna tetikus. Gerak halus dihormati:
  // `prefers-reduced-motion: reduce` memakai lompatan langsung.
  useEffect(() => {
    if (!terpilih) return;
    const panel = panelRef.current;
    if (!panel) return;
    const kurangiGerak =
      typeof window !== "undefined" &&
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    panel.scrollIntoView?.({
      block: "start",
      behavior: kurangiGerak ? "auto" : "smooth",
    });
    panel.querySelector<HTMLElement>(".kpi-detail-title")?.focus({ preventScroll: true });
  }, [terpilih]);

  function tutupPanel() {
    const nama = terpilih;
    setTerpilih(null);
    if (nama) kartuRef.current[nama]?.focus();
  }

  if (loading) {
    return (
      <section className="kpi-dashboard" aria-busy="true">
        {showHeader ? (
          <PageHeader title="Performance & Audit" description={DESKRIPSI_HALAMAN} />
        ) : null}
        {/* Kelas kpi-loading tetap ada (dipin tes) tetapi hanya untuk pembaca
            layar: tampilannya kini skeleton, bukan teks "Memuat…" berkedip. */}
        <p className="kpi-loading sr-only" aria-live="polite">
          Memuat KPI…
        </p>
        <div className="skeleton-grid" aria-hidden="true">
          <div className="skeleton skeleton-card" />
          <div className="skeleton skeleton-card" />
          <div className="skeleton skeleton-card" />
          <div className="skeleton skeleton-card" />
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="kpi-dashboard">
        {showHeader ? (
          <PageHeader title="Performance & Audit" description={DESKRIPSI_HALAMAN} />
        ) : null}
        <p className="kpi-error status-danger" role="alert">
          {error}
        </p>
        {onRetry && (
          <button type="button" className="button kpi-retry" onClick={onRetry}>
            Coba lagi
          </button>
        )}
      </section>
    );
  }

  // Tahap 6 (29 Okt 2026): dulu `return null` — bagian berjudul tanpa isi,
  // tanpa sebab, tanpa jalan keluar. Sekarang keadaan kosong menjelaskan apa
  // yang tidak ada dan menawarkan dua tindakan yang benar-benar tersedia:
  // ganti periode di bilah kendali, atau muat ulang.
  if (!kpi || !Array.isArray(kpi.metrics)) {
    return (
      <section className="kpi-dashboard">
        {showHeader ? (
          <PageHeader title="Performance & Audit" description={DESKRIPSI_HALAMAN} />
        ) : null}
        <EmptyState
          kode="kpi"
          judul="Belum ada angka KPI"
          sebab="Respons KPI untuk periode ini belum memuat satu metrik pun, jadi tidak ada yang bisa ditampilkan tanpa mengarang angka."
          saran="Coba periode lain di bilah kendali di atas (Hari ini · 7 hari · 1 bulan), lalu muat ulang bila masih kosong."
          aksi={
            onRetry ? (
              <button type="button" className="button kpi-retry" onClick={onRetry}>
                Muat ulang
              </button>
            ) : null
          }
        />
      </section>
    );
  }

  return (
    <section className="kpi-dashboard">
      {/* Kepala halaman hanya dirender bila komponen ini berdiri sendiri.
          Di dalam tab gabungan, kepala halaman milik `PageShell` (Tahap 1
          redesign "Performance & Audit", 29 Okt 2026) — satu judul, satu
          deskripsi, satu tempat. */}
      {showHeader ? (
        <PageHeader title="Performance & Audit" description={DESKRIPSI_HALAMAN} />
      ) : null}
      {/* SATU bilah kontrol (Tahap 2 redesign, 29 Okt 2026): periode, cakupan,
          dan meta (siapa cakupannya · mode data · kapan dihitung · ringkasan
          keadaan metrik) dalam satu baris. Sebelumnya pemilih periode dan
          toggle cakupan adalah dua baris terpisah, sementara pil di kepala
          halaman mengulang keduanya. Kontrol ini TIDAK menghitung KPI; ia
          hanya memberi tahu HALAMAN apa yang harus dimuat. */}
      <div className="kpi-controls" role="group" aria-label="Kendali Performance & Audit">
        <div className="kpi-period" role="group" aria-label="Jendela periode KPI">
          <span className="kpi-period-label">Periode</span>
          {KPI_WINDOWS.map((w) => {
            const aktif = w.key === windowKey;
            return (
              <button
                key={w.key}
                type="button"
                className={`commodity-pill kpi-period-pill${aktif ? " is-active" : ""}`}
                data-window={w.key}
                aria-pressed={aktif}
                onClick={() => onWindowChange?.(w.key)}
              >
                {w.label}
              </button>
            );
          })}
        </div>
        {/* Cakupan data (Fase 8): operasional vs simulasi. Angka kedua cakupan
            TIDAK boleh tercampur — backend menyaring baris sesi demo di SQL. */}
        <KpiScopeToggle
          scope={scope}
          onScopeChange={onScopeChange}
          disabled={Boolean(scopeDisabledReason)}
          disabledReason={scopeDisabledReason}
        />
        <KpiMetaLine kpi={kpi} />
      </div>
      {/* Grup terpisah: angka simulasi tidak boleh terbaca sebagai hasil
          operasional, jadi judulnya menyebut mode data yang dikirim backend. */}
      <section
        className="kpi-group"
        data-mode={String(kpi.data_mode ?? "")}
        aria-label={scopeLabel(kpi.data_mode)}
      >
        {/* Label cakupan = SUB-judul di bawah judul bagian halaman, jadi h3:
            halaman sudah punya satu h1 (PageShell) dan satu h2 per bagian. */}
        <h3 className="kpi-group-title">{scopeLabel(kpi.data_mode)}</h3>
        {String(kpi.data_mode) === "demo" ? (
          <p className="kpi-group-note" data-testid="kpi-demo-note">
            Angka simulasi, bukan hasil lapangan.
          </p>
        ) : null}
        {/* Batas domain (Fase 6 butir 6): yang diukur adalah BAHAN untuk rencana
            dan catatan pengiriman — bukan porsi yang sudah dimasak/disajikan.
            Sistem ini tidak mencatat fakta memasak/distribusi per porsi, jadi
            klaim "makanan tersaji" tidak boleh lahir dari angka di bawah. */}
        {/* Batas domain tetap dinyatakan (kejujuran data), tetapi cukup satu
            baris: paragraf panjang di atas semua kartu hanya dibaca sekali. */}
        <p className="kpi-group-note" data-testid="kpi-domain-note">
          Dihitung dari <strong>bahan rencana</strong> dan catatan kirim, bukan
          porsi tersaji.
        </p>
      {/* Grid datar: hanya kartu KPI, tanpa judul domain (permintaan pemilik
          29 Okt 2026). Urutan kartu mengikuti `metrics[]` backend apa adanya. */}
      <div className="kpi-grid">
        {kpi.metrics.map((m: any) => {
          const shown = fmtValue(m.unit, m.value);
          const trend = trendClass(m.trend);
          const bullet = bulletOf(m);
          const arah = bullet ? directionLabel(bullet.direction) : null;
          const prov = provenanceLines(m);
          const desc = metricDescription(m.name);
          const buka = terpilih === String(m.name);
          const alihkan = () => setTerpilih(buka ? null : String(m.name));
          return (
            <article
              key={m.name}
              className={`kpi-card card kpi-${m.state}`}
              /* SELURUH kartu yang bisa diklik (revisi 29 Okt 2026) — bukan hanya
                 namanya. `details` di dalam kartu sudah dihapus, jadi tidak ada
                 lagi segitiga buka-tutup dan tidak ada kontrol bersarang. */
              role="button"
              tabIndex={0}
              aria-expanded={buka}
              aria-controls="kpi-detail"
              data-aktif={buka ? "true" : undefined}
              onClick={alihkan}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " " || e.key === "Spacebar") {
                  e.preventDefault();
                  alihkan();
                }
              }}
              ref={(el) => {
                kartuRef.current[String(m.name)] = el;
              }}
            >
              <div className="kpi-card-top">
                {/* Nama metrik sengaja ENGLISH (istilah kanonik dari server):
                    istilah ini dipakai lintas laporan/Joule, dan terjemahannya
                    dulu membuat satu metrik punya dua nama. Terjemahan Indonesia
                    hidup di panel penjelasan. */}
                <span className="kpi-card-name" title={m.name} lang="en">
                  {String(m.name)}
                </span>
                <MetricIcon name={m.name} />
              </div>
              {desc ? (
                <p className="kpi-card-desc" lang="en">
                  {desc}
                </p>
              ) : null}
              {shown !== null ? (
                <p className="kpi-value">
                  {shown}
                  <small> {unitLabel(m.unit)}</small>
                </p>
              ) : (
                <p className="kpi-value kpi-value-none">—</p>
              )}
              {/* Bar skala tetap terlihat, tetapi label "0 … maks" dibuang: satu
                  baris angka kecil di bawah setiap bar hanya menambah derau, dan
                  skalanya sudah dibawa `aria-label` untuk pembaca layar. */}
              {bullet && bullet.pct !== null ? (
                <div
                  className="kpi-bullet"
                  data-over={bullet.overMax ? "true" : undefined}
                  role="img"
                  aria-label={`${shown} ${unitLabel(m.unit)} dari skala 0–${bullet.max}${
                    bullet.overMax ? " (melewati skala)" : ""
                  }`}
                >
                  <span className="kpi-bullet-track" aria-hidden="true">
                    <span
                      className="kpi-bullet-fill"
                      style={{ width: `${bullet.pct}%` }}
                    />
                  </span>
                </div>
              ) : null}
              {/* Satu baris keadaan: status + arah + tingkat bukti (wajib
                  terbaca tanpa klik). */}
              <p className="kpi-card-flags">
                <span className={`kpi-state kpi-state-${m.state}`}>
                  {STATE_LABEL[m.state] ?? m.state}
                </span>
                {" "}
                {trend && (
                  <span className={`kpi-trend ${trend}`}>
                    {m.trend === "up" ? "▲ naik" : m.trend === "down" ? "▼ turun" : "■ datar"}
                    {arah ? ` · ${arah}` : ""}
                  </span>
                )}
                {" "}
                {prov.length ? (
                  <span className="kpi-prov-evidence">
                    Bukti:{" "}
                    <strong>
                      {prov.find((l) => l.key === "evidence")?.value ?? "—"}
                    </strong>
                  </span>
                ) : null}
              </p>
              {m.reason && <p className="kpi-reason">{rapikanTeksBackend(m.reason)}</p>}
            </article>
          );
        })}
      </div>

      {/* Panel penjelasan tunggal, tepat di bawah grid kartu ("di bawah sub sub
          KPI"). Satu metrik pada satu waktu; isinya berasal dari amplop yang
          sama dengan kartu, jadi angkanya tidak bisa berbeda. */}
      {terpilih
        ? (() => {
            const metrik = (kpi.metrics as any[]).find(
              (x) => String(x?.name ?? "") === terpilih,
            );
            if (!metrik) return null;
            return (
              <KpiDetailPanel
                metric={metrik}
                windowKey={windowKey}
                onClose={tutupPanel}
                panelRef={panelRef}
              />
            );
          })()
        : null}
      </section>
    </section>
  );
}
