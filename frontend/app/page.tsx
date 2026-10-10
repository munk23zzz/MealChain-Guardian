"use client";

// S4-06 polish (arah Roy 2026-10-08): layout sidebar per role — teks ramai
// dipindah/dipangkas, tab nav per role, peta Indonesia + grafik stok.
// SEMUA fitur lama tetap ada (wiring test mem-pin): KPI, OpsConsole,
// Event2Panel, feed, detail, trace, provider panel, approval modal.
// Konsol operasi & analisis HANYA untuk role approver (bgn_monitor
// read-only: tab analisis tidak ditampilkan).

import { useCallback, useEffect, useState } from "react";

import {
  login,
  fetchDecisions,
  fetchDecisionTraces,
  fetchDecisionChain,
  fetchApprovalSummary,
  fetchKpis,
  fetchBalanceMap,
  fetchComplianceDossier,
  seedDemo,
} from "../lib/api";
import { decodeRole } from "../lib/auth";
import StatusBadge from "../components/StatusBadge";
import NavIcon, {
  ChevronIcon,
  LogoMark,
  LogoutIcon,
  SeedIcon,
} from "../components/NavIcon";
import RecommendationCard from "../components/RecommendationCard";
import AgentTraceViewer from "../components/AgentTraceViewer";
import IntegrityPanel from "../components/IntegrityPanel";
import ChaosPanel from "../components/ChaosPanel";
import DecisionActions from "../components/DecisionActions";
import DecisionChain from "../components/DecisionChain";
import ProviderPanel from "../components/ProviderPanel";
import RoleHero from "../components/RoleHero";
import KPIDashboard from "../components/KPIDashboard";
import KpiTargets from "../components/KpiTargets";
import OpsConsole from "../components/OpsConsole";
import SupplyMap from "../components/SupplyMap";
import StockChart from "../components/StockChart";
import OverviewLocationBreakdown from "../components/OverviewLocationBreakdown";
import { formatKg, sumFiniteKg } from "../lib/overview-format";
import { SupplierExclusionView } from "../components/SupplierExclusionPanel";
import { fetchSupplierContext, type SupplierContext } from "../lib/supplier-exclusions";
import ComplianceEvidencePanel from "../components/ComplianceEvidencePanel";
import { dossierToCsv, dossierToJson, downloadText } from "../lib/export";
import type { ComplianceDossier } from "../lib/evidence";

const APPROVER_ROLES = new Set(["sppg_head", "sppg_nutritionist"]);

// Panel provider dihitung dari trace aktual (VERIFY/PREDICT/SUPERVISE);
// tanpa karangan — agen tanpa langkah model tampil UNAVAILABLE.
function providersFromTraces(steps: any[]): Record<string, any> {
  const out: Record<string, any> = {};
  for (const s of steps ?? []) {
    const outSum = s.output_summary ?? {};
    if (s.step_name === "VERIFY") {
      out.verifier = {
        status: outSum.verdict === "UNAVAILABLE" ? "unavailable" : "ok",
        provider: outSum.provider ?? null,
        fallback_used: outSum.fallback_used ?? false,
        attempts: (outSum.attempts ?? []).length,
      };
    }
    if (s.step_name === "PREDICT") {
      const stat = outSum.method === "statistical_fallback";
      out.forecast = {
        status: stat ? "fallback" : outSum.provider ? "ok" : "unavailable",
        provider: outSum.provider ?? null,
        fallback_used: outSum.fallback_used ?? stat,
        attempts: (outSum.attempts ?? []).length,
      };
    }
    if (s.step_name === "SUPERVISE") {
      out.supervisor = {
        status: outSum.status === "narrated" ? "ok" : outSum.status,
        provider: outSum.provider ?? null,
        fallback_used: outSum.fallback_used ?? false,
        attempts: (outSum.attempts ?? []).length,
      };
    }
  }
  return out;
}

type Decision = {
  decision_id: string;
  decision_type: string;
  status: string;
  quantity_kg: number | null;
  safe_delivered_cost: number | null;
  expires_at: string;
  valid: boolean;
};

// Persona label sesuai PRD 2.4 §2 (Judul resmi, Indonesia pada sub-label).
const ROLE_LABEL: Record<string, string> = {
  sppg_head: "SPPG Operations Lead",
  sppg_nutritionist: "Food Safety Officer",
  bgn_monitor: "National Inspector",
};

const COMMODITIES = ["telur", "ayam", "beras", "wortel"];

export default function Home() {
  const [token, setToken] = useState<string | null>(null);
  const [role, setRole] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  // PRD 2.4 (arah Roy 2026-10-09): navigasi = 5 tab sesuai 7 screen PRD
  // (login terpisah; decision detail gabung di recommendations).
  const [tab, setTab] = useState<
    "overview" | "kpi" | "recommendations" | "agent-log" | "demo-control"
  >("overview");
  const [mapCommodity, setMapCommodity] = useState("telur");
  const [mapData, setMapData] = useState<any>(null);
  const [mapError, setMapError] = useState<string | null>(null);
  const [mapRefresh, setMapRefresh] = useState(0);
  // Waktu pembaruan peta terakhir (acuan menampilkan "terakhir diperbarui").
  const [mapUpdatedAt, setMapUpdatedAt] = useState<number | null>(null);
  // Kerangka acuan: rail bisa dilipat (lebar 68px, label disembunyikan).
  const [sideCollapsed, setSideCollapsed] = useState(false);
  useEffect(() => {
    if (!token || tab !== "overview") return;
    let stopped = false;
    const loadMap = async () => {
      try {
        const data = await fetchBalanceMap(mapCommodity, token);
        if (!stopped) {
          setMapData(data);
          setMapError(null);
          setMapUpdatedAt(Date.now());
        }
      } catch (error) {
        if (!stopped) setMapError(error instanceof Error ? error.message : "Peta tidak tersedia.");
      }
    };
    loadMap();
    const interval = setInterval(loadMap, 5000);
    return () => {
      stopped = true;
      clearInterval(interval);
    };
  }, [mapCommodity, mapRefresh, tab, token]);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [traces, setTraces] = useState<any[]>([]);
  const [chain, setChain] = useState<any[]>([]);
  // S4-04: read model kanonik dari /approval-summary — sumber tunggal modal.
  const [approvalSummary, setApprovalSummary] = useState<any>(null);
  const [supplierContext, setSupplierContext] = useState<SupplierContext | null>(null);
  const [complianceDossier, setComplianceDossier] = useState<ComplianceDossier | null>(null);
  // S4-03: envelope GET /kpi — loading/error state eksplisit, tanpa fake 0.
  const [kpi, setKpi] = useState<any>(null);
  const [kpiLoading, setKpiLoading] = useState(false);
  const [kpiError, setKpiError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Feed traceable (arah Roy 2026-10-09): filter status = visual only;
  // EXPIRED TIDAK disembunyikan. Hook di level atas (rules-of-hooks).
  const [statusFilter, setStatusFilter] = useState<string | null>(null);

  const isApprover = APPROVER_ROLES.has(role ?? "");

  const loadDecisions = useCallback(async (t: string) => {
    try {
      const data = await fetchDecisions(t);
      setDecisions(data.items ?? []);
      setError(null);
    } catch (e: any) {
      setError(String(e.message ?? e));
    }
  }, []);

  // Polling 5 detik (design.md §5 — tanpa WebSocket untuk MVP).
  useEffect(() => {
    if (!token) return;
    loadDecisions(token);
    const iv = setInterval(() => loadDecisions(token), 5000);
    return () => clearInterval(iv);
  }, [token, loadDecisions]);

  // S4-03: muat KPI sekali per login (periode 24 jam berakhir sekarang;
  // scope ditentukan backend — SPPG own, monitor global) + retry manual.
  const loadKpi = useCallback(async (t: string) => {
    setKpiLoading(true);
    setKpiError(null);
    try {
      const end = new Date();
      const start = new Date(end.getTime() - 24 * 60 * 60 * 1000);
      const data = await fetchKpis(start.toISOString(), end.toISOString(), t);
      setKpi(data);
    } catch (e: any) {
      setKpiError(String(e.message ?? e));
      setKpi(null);
    } finally {
      setKpiLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!token) return;
    loadKpi(token);
  }, [token, loadKpi]);


  useEffect(() => {
    if (!token || !selectedId) return;
    let stopped = false;
    const load = async () => {
      try {
        const data = await fetchDecisionTraces(selectedId, token);
        if (!stopped) setTraces(data.steps ?? []);
      } catch {
        /* feed tetap jalan; error trace tidak fatal */
      }
      try {
        const data = await fetchDecisionChain(selectedId, token);
        if (!stopped) setChain(data.chain ?? []);
      } catch {
        /* chain opsional; kegagalan tidak fatal */
      }
      try {
        // S4-04: summary kanonik mengikuti decision terpilih (poll ikut
        // menyegarkan approval_state/expiry saat pihak lain approve).
        const data = await fetchApprovalSummary(selectedId, token);
        if (!stopped) setApprovalSummary(data);
      } catch {
        /* summary opsional untuk feed; modal tetap menolak tanpa data */
        if (!stopped) setApprovalSummary(null);
      }
      try {
        const data = await fetchSupplierContext(selectedId, token);
        if (!stopped) setSupplierContext(data);
      } catch {
        if (!stopped) setSupplierContext(null);
      }
      try {
        const data = await fetchComplianceDossier(selectedId, token);
        if (!stopped) setComplianceDossier(data);
      } catch {
        if (!stopped) setComplianceDossier(null);
      }
    };
    load();
    const iv = setInterval(load, 5000);
    return () => {
      stopped = true;
      clearInterval(iv);
      setSupplierContext(null);
      setComplianceDossier(null);
    };
  }, [token, selectedId]);

  async function onSeedDemo() {
    if (!token) return;
    try {
      await seedDemo(token, true);
      await loadDecisions(token);
    } catch (e: any) {
      setError(String(e.message ?? e));
    }
  }

  async function onLogin(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      const data = await login(email, password);
      setToken(data.access_token);
      // Role dari JWT hanya untuk display; otorisasi tetap di backend.
      setRole(decodeRole(data.access_token));
      setLoginError(null);
    } catch (e: any) {
      setLoginError(
        e?.message
          ? String(e.message)
          : "Login gagal — periksa koneksi ke server API."
      );
    } finally {
      setSubmitting(false);
    }
  }

  if (!token) {
    const demoAccounts = [
      { label: "SPPG Head", email: "sppg.head@demo.local", password: "Demo#SPPG2026" },
      { label: "Nutritionist", email: "sppg.nutritionist@demo.local", password: "Demo#Nut2026" },
      { label: "BGN Monitor", email: "bgn.monitor@demo.local", password: "Demo#BGN2026" },
    ];
    return (
      <main className="login-shell">
        {/* Panel brand: dunia subject — rantai dingin SPPG, angka dari data demo asli */}
        <section className="login-brand" aria-label="Tentang MealChain Guardian">
          <p className="brand-eyebrow">Badan Gizi Nasional · Program SPPG</p>
          <h1 className="brand-title">MealChain Guardian</h1>
          <p className="brand-tagline">
            Agentic AI untuk cross-regional food supply balancing — memantau
            kesegaran, stok, dan keputusan distribusi antar SPPG.
          </p>
        </section>

        <section className="login-panel">
          <form onSubmit={onLogin} className="login-form">
            <h2>Masuk ke konsol</h2>
            <p className="login-sub">Gunakan akun SPPG atau BGN yang terdaftar.</p>
            <label className="field">
              <span>Email</span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="username"
                required
              />
            </label>
            <label className="field">
              <span>Password</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
              />
            </label>
            {loginError && (
              <p className="status-danger login-error" role="alert">
                {loginError}
              </p>
            )}
            <button className="button login-submit" type="submit" disabled={submitting}>
              {submitting ? "Memeriksa…" : "Masuk"}
            </button>
            <div className="demo-block">
              {/* Demo accounts jadi inline text-link — bukan chip/kartu
                  (arah Roy 2026-10-10: login jangan penuh "item"). */}
              <p className="demo-hint">Demo:</p>
              <p className="demo-links">
                {demoAccounts.map((acc, i) => (
                  <span key={acc.email}>
                    {i > 0 && " · "}
                    <button
                      type="button"
                      className="demo-link"
                      onClick={() => {
                        setEmail(acc.email);
                        setPassword(acc.password);
                        setLoginError(null);
                      }}
                    >
                      {acc.label}
                    </button>
                  </span>
                ))}
              </p>
            </div>
          </form>
        </section>
      </main>
    );
  }

  const selected = decisions.find((d) => d.decision_id === selectedId) ?? null;
  // Turunan data peta untuk banner + judul (dipakai tab Overview).
  const mapShortage: any[] = (mapData?.locations ?? []).filter(
    (l: any) => l.status === "shortage"
  );
  const roleLabel = ROLE_LABEL[role ?? ""] ?? (role ?? "user");

  // Feed traceable (arah Roy 2026-10-09): EXPIRED TIDAK disembunyikan.
  // Filter status hanya menyaring TAMPILAN; count = data live penuh.
  const statusCounts = decisions.reduce<Record<string, number>>((acc, d) => {
    const s = (d.status ?? "").toUpperCase();
    acc[s] = (acc[s] ?? 0) + 1;
    return acc;
  }, {});
  const visibleDecisions = statusFilter
    ? decisions.filter((d) => (d.status ?? "").toUpperCase() === statusFilter)
    : decisions;

  // PRD 2.4: nav 5 tab; demo-control approver-only; agent-log semua role
  // (monitor read-only justru butuh observability).
  const navItems: {
    id: "overview" | "kpi" | "recommendations" | "agent-log" | "demo-control";
    label: string;
  }[] = [
    { id: "overview", label: "Overview" },
    { id: "kpi", label: "KPI" },
    {
      id: "recommendations",
      label: `Recommendations${decisions.length ? ` (${decisions.length})` : ""}`,
    },
    { id: "agent-log", label: "Agent Log" },
    ...(isApprover
      ? [{ id: "demo-control" as const, label: "Demo Control" }]
      : []),
  ];

  // Inisial avatar di kaki rail (acuan: inisial nama; app ini tidak menyimpan
  // nama pemakai, jadi dipakai email login dengan fallback label peran).
  const initials = (email || roleLabel)
    .split(/[\s@._-]+/)
    .filter(Boolean)
    .map((word) => word[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  const onLogout = () => {
    setToken(null);
    setRole(null);
    setSelectedId(null);
    setTab("overview");
  };

  return (
    <main className="app-shell">
      {/* Sidebar mengikuti acuan: rail biru brand, ikon per tujuan, identitas
          pemakai di kaki rail, tombol lipat di baris brand. */}
      <aside
        className={`side-nav${sideCollapsed ? " side-nav-collapsed" : ""}`}
        aria-label="Navigasi konsol"
      >
        <div className="side-brand">
          <span className="side-logo">
            <LogoMark />
          </span>
          <strong>MealChain Guardian</strong>
          <button
            type="button"
            className="side-collapse"
            onClick={() => setSideCollapsed((v) => !v)}
            aria-label={sideCollapsed ? "Buka sidebar" : "Tutup sidebar"}
            aria-expanded={!sideCollapsed}
            title={sideCollapsed ? "Buka sidebar" : "Tutup sidebar"}
          >
            <ChevronIcon collapsed={sideCollapsed} />
          </button>
        </div>
        <nav className="side-tabs" aria-label="Bagian konsol">
          {navItems.map((n) => (
            <button
              key={n.id}
              type="button"
              className={`side-tab${tab === n.id ? " side-tab-active" : ""}`}
              onClick={() => setTab(n.id)}
              title={sideCollapsed ? n.label : undefined}
            >
              <NavIcon id={n.id} />
              <span className="side-tab-label">{n.label}</span>
            </button>
          ))}
        </nav>
        <div className="side-user">
          <span className="side-avatar" aria-hidden="true">
            {initials}
          </span>
          <span className="side-user-meta">
            <span className="side-user-name">{roleLabel}</span>
            <span className="side-user-sub">{email || "Sesi demo"}</span>
          </span>
          <button
            type="button"
            className="side-logout"
            onClick={onLogout}
            aria-label="Keluar"
            title="Keluar"
          >
            <LogoutIcon />
          </button>
        </div>
        <div className="side-actions">
          {isApprover && (
            <button
              type="button"
              className="button-secondary button"
              onClick={onSeedDemo}
              title="Muat ulang 4 kasus demo (idempotent)"
            >
              <SeedIcon />
              <span className="side-action-label">Muat kasus demo</span>
            </button>
          )}
        </div>
      </aside>

      <div className="app-content">
        {tab === "overview" && (
          <div className="overview-page">
            {/* Tata letak mengikuti dashboard acuan: header halaman → strip
                peran → strip KPI → banner lokasi kritis → kartu filter →
                peta (2/3) + grafik stok (1/3) → kartu Status Lokasi.
                Angka dihitung dari data peta real (mapData), tanpa karangan. */}
            <section
              className="overview-header"
              aria-label="Ringkasan peta pasokan"
            >
              <div className="overview-header-main">
                <h1>Overview Pasokan &amp; Distribusi</h1>
                <p className="overview-header-sub">
                  Peta {(mapData?.locations ?? []).length} lokasi SPPG — hijau
                  surplus, merah shortage, abu seimbang. Klik kartu Status
                  Lokasi untuk melihat angka pasokan dan kebutuhan.
                </p>
              </div>
              <div className="overview-header-status">
                <span className="overview-live-pill">
                  <span className="overview-live-dot" aria-hidden="true" />
                  Live Sync (5s)
                </span>
                {mapUpdatedAt !== null && (
                  <span className="overview-updated" aria-live="polite">
                    terakhir diperbarui{" "}
                    {new Date(mapUpdatedAt).toLocaleTimeString("id-ID")}
                  </span>
                )}
              </div>
            </section>

            <RoleHero role={role ?? "sppg_head"} />

            {/* Strip KPI: dihitung dari data peta real (tanpa fake 0) */}
            <section className="overview-kpis" aria-label="KPI ringkas">
              <div className="kpi-card">
                <span className="kpi-card-label">Volume Komoditas Aktif</span>
                <span className="kpi-card-value">
                  {formatKg(sumFiniteKg(mapData?.locations ?? []))}
                </span>
                <span className="kpi-card-foot">total pasokan lokasi terpetakan</span>
              </div>
              <div className="kpi-card">
                <span className="kpi-card-label">Lokasi Surplus</span>
                <span className="kpi-card-value kpi-card-safe">
                  {mapData
                    ? (mapData.locations ?? []).filter(
                        (l: any) => l.status === "surplus"
                      ).length
                    : "—"}
                </span>
                <span className="kpi-card-foot">siap jadi sumber distribusi</span>
              </div>
              <div className="kpi-card">
                <span className="kpi-card-label">Lokasi Shortage</span>
                <span className="kpi-card-value kpi-card-danger">
                  {mapData
                    ? (mapData.locations ?? []).filter(
                        (l: any) => l.status === "shortage"
                      ).length
                    : "—"}
                </span>
                <span className="kpi-card-foot">butuh penyeimbangan</span>
              </div>
            </section>

            {/* Banner peringatan ala acuan: lokasi kritis disebut namanya,
                angkanya dari data peta real (bukan karangan). */}
            {mapShortage.length > 0 && (
              <div className="overview-alert" role="alert">
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
                  <path d="M12 9v4M12 17h.01" />
                </svg>
                <p>
                  <strong>{mapShortage.length} lokasi shortage</strong>{" "}
                  — {mapShortage.map((l: any) => l.location).join(", ")}. Cek
                  rekomendasi agent untuk alokasi ulang.
                </p>
              </div>
            )}

            {/* Filter pill komoditas di dalam kartu (acuan: kartu filter) */}
            <div
              className="commodity-filters filter-card"
              role="group"
              aria-label="Komoditas peta"
            >
              <span className="commodity-filters-label">Komoditas:</span>
              {COMMODITIES.map((c) => (
                <button
                  key={c}
                  type="button"
                  className={`commodity-pill${mapCommodity === c ? " commodity-pill-active" : ""}`}
                  aria-pressed={mapCommodity === c}
                  onClick={() => setMapCommodity(c)}
                >
                  {c}
                </button>
              ))}
              {mapError && (
                <p className="status-danger map-error" role="alert">
                  {mapError}{" "}
                  <button
                    type="button"
                    onClick={() => setMapRefresh((value) => value + 1)}
                  >
                    Coba lagi
                  </button>
                </p>
              )}
            </div>

            {/* Split 60/40 ala mockup: peta gelap kiri, telemetri kanan */}
            <section
              className="overview-split"
              aria-label="Peta dan grafik stok"
            >
              <div className="map-panel-dark">
                <div className="map-panel-dark-head">
                  <span className="map-panel-dark-dot" aria-hidden="true" />
                  <span className="map-panel-dark-title">
                    Koridor Pasokan Aktif: Jawa Barat &amp; DKI Jakarta
                  </span>
                  <span className="map-panel-dark-count">
                    {(mapData?.locations ?? []).length} Lokasi
                  </span>
                </div>
                <div className="map-panel-dark-body">
                  <SupplyMap
                    locations={mapData?.locations ?? []}
                    commodity={mapData?.commodity}
                  />
                </div>
              </div>
              <div className="overview-side">
                <div className="map-panel">
                  <h3>Pasokan per Lokasi</h3>
                  <StockChart locations={mapData?.locations ?? []} />
                </div>
              </div>
            </section>

            {/* Rincian angka per lokasi — kartu selebar halaman supaya lima
                kolomnya tidak terpotong (di acuan, angka ini ada di kartu
                Status lokasi). */}
            <section className="map-panel" aria-label="Rincian pasokan per lokasi">
              <h3>Rincian Pasokan per Lokasi</h3>
              <OverviewLocationBreakdown locations={mapData?.locations ?? []} loading={!mapData && !mapError} />
            </section>
          </div>
        )}

        {tab === "kpi" && (
          <>
            <KPIDashboard
              kpi={kpi}
              loading={kpiLoading}
              error={kpiError}
              onRetry={() => token && loadKpi(token)}
            />
            {/* PRD 2.4 §5: strip target demo — berlabel eksplisit,
                BUKAN angka live (KPI live tetap jujur di atas). */}
            <KpiTargets />
          </>
        )}

        {tab === "demo-control" && isApprover && (
          /* PRD 2.4 Screen 7: harness demo — konsol analisis (Event 1/2/3)
             + seed kasus. Aksi tetap via API resmi; tidak ada chaos
             injection di luar kontrak backend (arsitektur tidak diubah). */
          <section className="demo-control-section">
            <h2>Demo Control Panel</h2>
            <p className="section-sub">
              Skenario deterministik untuk demo day — jalankan lewat API resmi
              (tanpa mock): muat kasus, picu Event 2 (price anomaly) &amp;
              Event 3 (thermal excursion) dari konsol, lalu lihat hasilnya di
              tab Recommendations &amp; Agent Log.
            </p>
            <button
              type="button"
              className="button"
              onClick={onSeedDemo}
              title="Muat ulang 4 kasus demo (idempotent)"
            >
              Scenario 00 — Muat kasus demo
            </button>
            <OpsConsole
              role={role ?? "sppg_head"}
              token={token}
              onSubmitted={() => {
                if (token) loadDecisions(token);
                setTab("recommendations");
              }}
            />
            <ChaosPanel
              role={role ?? "sppg_head"}
              token={token}
              onDecisionCreated={() => {
                if (token) loadDecisions(token);
              }}
            />
          </section>
        )}

        {tab === "recommendations" && (
          <>
            <section className="feed-section">
              <h2>Recommendation Feed</h2>
              {error && (
                <p className="status-danger">
                  Gagal memuat data: {error}{" "}
                  <button
                    type="button"
                    onClick={() => token && loadDecisions(token)}
                  >
                    Coba lagi
                  </button>
                </p>
              )}
              {decisions.length === 0 && !error && (
                <p className="empty-state">
                  Belum ada rekomendasi aktif — jalankan analisis di tab
                  Analisis
                  {isApprover
                    ? " atau muat kasus demo di sidebar."
                    : " oleh approver SPPG."}
                </p>
              )}

              {/* Filter status: semua status punya chip + count (traceable;
                  EXPIRED tetap ada, tidak pernah disembunyikan by default). */}
              {decisions.length > 0 && (
                <div className="feed-filters" aria-label="Filter status">
                  <button
                    type="button"
                    className={`filter-chip${statusFilter === null ? " filter-chip-active" : ""}`}
                    onClick={() => setStatusFilter(null)}
                  >
                    Semua
                    <span className="legend-count">{decisions.length}</span>
                  </button>
                  {Object.entries(statusCounts)
                    .sort(([a], [b]) => a.localeCompare(b))
                    .map(([s, n]) => (
                      <button
                        key={s}
                        type="button"
                        className={`filter-chip${statusFilter === s ? " filter-chip-active" : ""}`}
                        onClick={() =>
                          setStatusFilter(statusFilter === s ? null : s)
                        }
                      >
                        {s}
                        <span className="legend-count">{n}</span>
                      </button>
                    ))}
                </div>
              )}

              <div className="feed">
                {visibleDecisions.map((d) => (
                  <div key={d.decision_id}>
                    <button
                      type="button"
                      className="link-button"
                      onClick={() => setSelectedId(d.decision_id)}
                    >
                      <RecommendationCard
                        decision={d}
                        mockSourced={d.status === "executed"}
                      />
                    </button>
                  </div>
                ))}
              </div>
            </section>

            {selected && (
              <section className="detail-section">
                <h2>Decision Detail</h2>
                <RecommendationCard decision={selected} mockSourced={false} />
                <DecisionChain chain={selectedId ? chain : []} />
                <DecisionActions
                  decisionId={selected.decision_id}
                  role={role ?? ""}
                  status={selected.status}
                  token={token}
                  summary={approvalSummary}
                />
                {supplierContext && (
                  <SupplierExclusionView
                    key={selected.decision_id}
                    context={supplierContext}
                    role={role ?? ""}
                    token={token}
                    onCreated={(decisionId) => {
                      void loadDecisions(token);
                      setSelectedId(decisionId);
                    }}
                  />
                )}
                {complianceDossier && (
                  <>
                    <ComplianceEvidencePanel dossier={complianceDossier} />
                    <div className="decision-export-actions">
                      <button type="button" className="button-secondary button" onClick={() => downloadText(`decision-${selected.decision_id}.json`, dossierToJson(complianceDossier), "application/json")}>Export JSON</button>
                      <button type="button" className="button-secondary button" onClick={() => downloadText(`decision-${selected.decision_id}.csv`, dossierToCsv(complianceDossier), "text/csv;charset=utf-8")}>Export CSV</button>
                    </div>
                  </>
                )}
              </section>
            )}
          </>
        )}

        {/* PRD 2.4 Screen 5: Agent Activity Log & Traces Console — tab
            tersendiri (terpisah dari decision detail). Semua role bisa
            melihat observability; pilih decision di dropdown bila belum
            ada yang terpilih. */}
        {tab === "agent-log" && (
          <section className="agent-log-section">
            <h2>Agent Activity Log</h2>
            {!selected && (
              <p className="section-sub">
                Pilih keputusan untuk melihat trace reasoning agent-nya:
                <select
                  aria-label="Pilih keputusan"
                  value=""
                  onChange={(e) => setSelectedId(e.target.value)}
                >
                  <option value="">— pilih —</option>
                  {decisions.map((d) => (
                    <option key={d.decision_id} value={d.decision_id}>
                      {(d.decision_type ?? "keputusan")} · {d.status} ·{" "}
                      {d.decision_id.slice(0, 8)}
                    </option>
                  ))}
                </select>
              </p>
            )}
            {selected && (
              <p className="section-sub">
                Trace untuk{" "}
                <strong>{selected.decision_type ?? "keputusan"}</strong>{" "}
                ({selected.decision_id.slice(0, 8)}) — status {selected.status}.
              </p>
            )}
            <ProviderPanel providers={providersFromTraces(traces)} />
            <AgentTraceViewer steps={traces} />
            {selected && (
              <IntegrityPanel token={token ?? ""} decisionId={selected.decision_id} />
            )}
          </section>
        )}
      </div>
    </main>
  );
}
