"use client";

// S4-06 polish (arah Roy 2026-10-08): layout sidebar per role — teks ramai
// dipindah/dipangkas, tab nav per role, peta Indonesia + grafik stok.
// SEMUA fitur lama tetap ada (wiring test mem-pin): KPI, OpsConsole,
// Event2Panel, feed, detail, trace, provider panel, approval modal.
// Konsol operasi & analisis HANYA untuk role approver (bgn_monitor
// read-only: tab analisis tidak ditampilkan).

import { useCallback, useEffect, useRef, useState } from "react";

import {
  login,
  fetchMe,
  fetchDecisions,
  fetchBatches,
  verifyLedger,
  fetchDecisionTraces,
  fetchDecisionChain,
  fetchApprovalSummary,
  fetchKpis,
  fetchBalanceMap,
  seedDemo,
} from "../lib/api";
import { decodeRole } from "../lib/auth";
import TopBar from "../components/TopBar";
import {
  ALL_LOCATIONS,
  countActionable,
  defaultScope,
  initialsOf,
} from "../lib/topbar";
import StatusBadge from "../components/StatusBadge";
import NavIcon, {
  ChevronIcon,
  LogoMark,
  LogoutIcon,
  SeedIcon,
} from "../components/NavIcon";
import { StatusLocationList } from "../components/SupplyMap";
import RecommendationCard from "../components/RecommendationCard";
import AgentTraceViewer from "../components/AgentTraceViewer";
import ChaosPanel from "../components/ChaosPanel";
import DecisionChain from "../components/DecisionChain";
import ProviderPanel from "../components/ProviderPanel";
import RoleHero from "../components/RoleHero";
import PageHeader from "../components/PageHeader";
import KPIDashboard from "../components/KPIDashboard";
import KpiTargets from "../components/KpiTargets";
import OpsConsole from "../components/OpsConsole";
import SupplyMap from "../components/SupplyMap";
import NodeTelemetry from "../components/NodeTelemetry";
import TodayDashboard from "../components/TodayDashboard";
import StockChart from "../components/StockChart";
import OverviewLocationBreakdown from "../components/OverviewLocationBreakdown";
import { formatKg, sumFiniteKg } from "../lib/overview-format";
import { SupplierExclusionView } from "../components/SupplierExclusionPanel";
import { fetchSupplierContext, type SupplierContext } from "../lib/supplier-exclusions";
import DecisionEvidence from "../components/DecisionEvidence";
import AgentQualityBoard from "../components/AgentQualityBoard";
import FoodSafetyBoard from "../components/FoodSafetyBoard";
import SurplusBoard from "../components/SurplusBoard";
import SupplierBoard from "../components/SupplierBoard";
import { runOf, type QualityRun } from "../lib/agent-quality";
import { fetchExclusions } from "../lib/supplier-exclusions";
import type { SupplierPair } from "../lib/suppliers-board";
import { defaultEvidenceId } from "../lib/evidence";

const APPROVER_ROLES = new Set(["sppg_head", "sppg_nutritionist"]);

// Halaman Kualitas Agen & Pemasok menilai SAMPEL keputusan terakhir dalam
// cakupan: jejak agen + putusan verifikator dipanggil per keputusan, jadi
// jumlahnya dibatasi — angkanya ditulis apa adanya di halaman, bukan
// diam-diam dipotong. Halaman Surplus & Limbah ikut aturan acuan: hanya
// peran SPPG yang melihatnya.
const EVALUATED_LIMIT = 8;
const SURPLUS_ROLES = new Set(["sppg_head", "sppg_nutritionist"]);

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
  // + "today" (halaman "Hari Ini", permintaan Roy 2026-10-11). Halaman yang
  // dibuka setelah login tetap Overview — tab baru tidak mengubah alur demo.
  const [tab, setTab] = useState<
    | "today"
    | "overview"
    | "kpi"
    | "recommendations"
    | "evidence"
    | "safety"
    | "surplus"
    | "suppliers"
    | "agent-log"
    | "quality"
    | "demo-control"
  >("overview");
  const [mapCommodity, setMapCommodity] = useState("telur");
  const [mapData, setMapData] = useState<any>(null);
  const [mapError, setMapError] = useState<string | null>(null);
  const [mapRefresh, setMapRefresh] = useState(0);
  // Waktu pembaruan peta terakhir (acuan menampilkan "terakhir diperbarui").
  const [mapUpdatedAt, setMapUpdatedAt] = useState<number | null>(null);
  // Identitas kanonik dari /auth/me — lokasi pemakai jadi pengunci cakupan
  // dropdown di top bar (peran SPPG tidak boleh memperluas cakupan dari UI).
  const [me, setMe] = useState<{
    location_name?: string | null;
    location_id?: string | null;
    name?: string | null;
  } | null>(null);
  // Lokasi aktif yang disorot di peta, dipilih dari dropdown top bar.
  const [activeLocation, setActiveLocation] = useState<string | null>(null);
  // Kerangka acuan: rail bisa dilipat (lebar 68px, label disembunyikan).
  const [sideCollapsed, setSideCollapsed] = useState(false);
  useEffect(() => {
    // Peta dimuat di SEMUA tab: data lokasinya dipakai top bar (dropdown
    // cakupan + ringkasan jaringan), bukan hanya halaman Overview.
    if (!token) return;
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
  }, [mapCommodity, mapRefresh, token]);

  // Identitas pemakai (server: GET /auth/me) — sumber lokasi pemakai untuk
  // mengunci cakupan peran SPPG di top bar.
  useEffect(() => {
    if (!token) return;
    let stopped = false;
    fetchMe(token)
      .then((data) => {
        if (!stopped) setMe(data);
      })
      .catch(() => {
        // Gagal membaca identitas: top bar gagal-tertutup (dropdown kosong),
        // bukan menampilkan semua lokasi.
        if (!stopped) setMe(null);
      });
    return () => {
      stopped = true;
    };
  }, [token]);

  // Cakupan awal: monitor nasional = semua lokasi, peran SPPG = SPPG-nya.
  useEffect(() => {
    if (!token) return;
    setActiveLocation(defaultScope({ role, ownLocation: me?.location_name ?? null }));
  }, [token, role, me]);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [traces, setTraces] = useState<any[]>([]);
  const [chain, setChain] = useState<any[]>([]);
  // S4-04: read model kanonik dari /approval-summary — sumber tunggal modal.
  const [approvalSummary, setApprovalSummary] = useState<any>(null);
  const [supplierContext, setSupplierContext] = useState<SupplierContext | null>(null);
  // S4-03: envelope GET /kpi — loading/error state eksplisit, tanpa fake 0.
  const [kpi, setKpi] = useState<any>(null);
  const [kpiLoading, setKpiLoading] = useState(false);
  const [kpiError, setKpiError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Langkah 3: data halaman "Hari Ini" — batch (GET /batches) + rantai audit
  // (GET /ledger/verify). Dimuat sekali per login lalu disegarkan tiap 60 detik;
  // nilai kosong tetap "—", bukan 0.
  const [batches, setBatches] = useState<any[] | null>(null);
  const [batchesLoading, setBatchesLoading] = useState(false);
  const [batchesError, setBatchesError] = useState<string | null>(null);
  const [ledger, setLedger] = useState<any>(null);
  // Jam klien: null sampai komponen ter-mount supaya HTML server dan render
  // klien tidak berbeda (label waktu ditulis "—" sebelum jam siap).
  const [now, setNow] = useState<Date | null>(null);
  // Kualitas Agen: run agen (jejak + putusan verifikator) untuk sampel keputusan.
  const [qualityRuns, setQualityRuns] = useState<QualityRun[]>([]);
  const [qualityLoading, setQualityLoading] = useState(false);
  const [qualityError, setQualityError] = useState<string | null>(null);
  // Pemasok: pemasok per keputusan sampel + register eksklusi.
  const [supplierPairs, setSupplierPairs] = useState<SupplierPair[]>([]);
  const [exclusions, setExclusions] = useState<unknown>(null);
  const [supplierLoading, setSupplierLoading] = useState(false);
  const [supplierError, setSupplierError] = useState<string | null>(null);
  const [evaluateTick, setEvaluateTick] = useState(0);
  const evaluatedKey = useRef<string | null>(null);
  // Feed traceable (arah Roy 2026-10-09): filter status = visual only;
  // EXPIRED TIDAK disembunyikan. Hook di level atas (rules-of-hooks).
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  // Feed berisi puluhan keputusan; tampilkan bertahap supaya halaman tidak
  // menjadi gulungan panjang. Jumlah tersisa selalu dinyatakan terang-terangan.
  const [feedLimit, setFeedLimit] = useState(24);

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

  // Langkah 3: data halaman "Hari Ini" — batch + rantai audit Merkle.
  // Kegagalan salah satu panggilan tidak menjatuhkan yang lain, dan tidak
  // pernah diisi angka karangan: kartu menulis "—" atau pesan galat.
  const loadToday = useCallback(async (t: string) => {
    setBatchesLoading(true);
    setBatchesError(null);
    try {
      const rows = await fetchBatches(t);
      setBatches(Array.isArray(rows) ? rows : []);
    } catch (e: any) {
      setBatchesError(String(e.message ?? e));
    } finally {
      setBatchesLoading(false);
    }
    try {
      setLedger(await verifyLedger(t));
    } catch {
      setLedger(null);
    }
  }, []);

  useEffect(() => {
    if (!token) return;
    loadToday(token);
    const iv = setInterval(() => loadToday(token), 60000);
    return () => clearInterval(iv);
  }, [token, loadToday]);

  // Sampel keputusan untuk halaman Kualitas Agen & Pemasok: jejak agen +
  // ringkasan persetujuan (yang memuat pemasok) diambil per keputusan.
  const sampleIds = decisions.slice(0, EVALUATED_LIMIT).map((d) => d.decision_id);
  const sampleKey = sampleIds.join(",");
  useEffect(() => {
    if (!token || !sampleKey) return;
    if (tab !== "quality" && tab !== "suppliers") return;
    const key = `${sampleKey}#${evaluateTick}`;
    // Sampel yang sama tidak dinilai dua kali walau daftar keputusan dipolling.
    if (evaluatedKey.current === key) return;
    evaluatedKey.current = key;
    let stopped = false;
    const run = async () => {
      if (tab === "quality") setQualityLoading(true);
      else setSupplierLoading(true);
      try {
        const rows = await Promise.all(
          sampleIds.map(async (decisionId) => {
            const [trace, summary] = await Promise.all([
              fetchDecisionTraces(decisionId, token).catch(() => null),
              fetchApprovalSummary(decisionId, token).catch(() => null),
            ]);
            return { decisionId, trace, summary };
          })
        );
        if (stopped) return;
        const byId = new Map(decisions.map((d) => [d.decision_id, d]));
        setQualityRuns(
          rows.map(({ decisionId, trace, summary }) => runOf(byId.get(decisionId), trace, summary))
        );
        setSupplierPairs(
          rows.map(({ decisionId, summary }) => ({
            decisionId,
            decisionType: byId.get(decisionId)?.decision_type ?? null,
            commodity: summary?.commodity ?? null,
            supplier: summary?.supplier ?? null,
          }))
        );
        setQualityError(null);
        setSupplierError(null);
        if (tab === "suppliers") {
          setExclusions(await fetchExclusions(token).catch(() => null));
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : "gagal memuat";
        if (stopped) return;
        setQualityError(message);
        setSupplierError(message);
      } finally {
        if (!stopped) {
          setQualityLoading(false);
          setSupplierLoading(false);
        }
      }
    };
    void run();
    return () => {
      stopped = true;
    };
    // decisions cukup lewat sampleKey (isi sampel); evaluatedKey menahan refetch
    // saat daftar keputusan dipolling ulang.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, token, sampleKey, evaluateTick]);

  const evaluatedCount = Math.min(decisions.length, EVALUATED_LIMIT);

  // Jam klien untuk label sisa waktu ("45 mnt lagi"): baru diisi setelah
  // mount supaya HTML server dan render klien sepakat, lalu diperbarui.
  useEffect(() => {
    setNow(new Date());
    const iv = setInterval(() => setNow(new Date()), 30000);
    return () => clearInterval(iv);
  }, []);


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
    };
    load();
    const iv = setInterval(load, 5000);
    return () => {
      stopped = true;
      clearInterval(iv);
      setSupplierContext(null);
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
  // Status yang menunggu tindakan manusia — dipakai sebagai meta kepala feed
  // (acuan: "2 menunggu keputusan · 2 ber-flag Verifier · 1 dieksekusi").
  const perluKeputusan = ["PENDING_APPROVAL", "NEEDS_VERIFICATION", "VERIFIER_FLAGGED"].reduce(
    (total, s) => total + (statusCounts[s] ?? 0),
    0,
  );

  // PRD 2.4: nav 5 tab (overview/kpi/recommendations/agent-log/demo-control)
  // + tab "Hari Ini" (permintaan Roy 2026-10-11) sebagai halaman pertama;
  // demo-control approver-only; agent-log semua role (monitor read-only justru
  // butuh observability).
  // Urutan mengikuti sidebar acuan (HackathonBil/MealchainGuardian): Hari Ini →
  // Overview → Keputusan → Decision & Evidence → Keamanan Pangan → Surplus &
  // Limbah → Pemasok → Agent Log → Kualitas Agen → KPI. Halaman yang di acuan
  // dibatasi peran (Surplus & Limbah = peran SPPG) ikut dibatasi di sini.
  const navItems: {
    id:
      | "today"
      | "overview"
      | "kpi"
      | "recommendations"
      | "evidence"
      | "safety"
      | "surplus"
      | "suppliers"
      | "agent-log"
      | "quality"
      | "demo-control";
    label: string;
    roles?: string[];
  }[] = [
    { id: "today", label: "Hari Ini" },
    { id: "overview", label: "Overview" },
    {
      id: "recommendations",
      label: `Recommendations${decisions.length ? ` (${decisions.length})` : ""}`,
    },
    { id: "evidence", label: "Decision & Evidence" },
    { id: "safety", label: "Keamanan Pangan" },
    { id: "surplus", label: "Surplus & Limbah", roles: Array.from(SURPLUS_ROLES) },
    { id: "suppliers", label: "Pemasok" },
    { id: "agent-log", label: "Agent Log" },
    { id: "quality", label: "Kualitas Agen" },
    { id: "kpi", label: "KPI" },
    ...(isApprover
      ? [{ id: "demo-control" as const, label: "Demo Control" }]
      : []),
  ];
  const visibleNavItems = navItems.filter(
    (item) => !item.roles || (role !== null && item.roles.includes(role))
  );

  // Inisial avatar (rail + top bar) — satu sumber di lib/topbar.ts supaya
  // tidak ada dua cara menghitung yang bisa menyimpang.
  const initials = initialsOf(email, roleLabel);
  // Notifikasi top bar: keputusan yang menunggu tindakan manusia.
  const actionable = countActionable(decisions);

  const onLogout = () => {
    setToken(null);
    setRole(null);
    setSelectedId(null);
    setTab("overview");
    // Bersihkan data konsol: akun berikutnya tidak boleh sempat melihat angka
    // sesi sebelumnya sebelum permintaan barunya selesai (terlihat saat uji
    // skeleton: strip KPI sempat menampilkan nilai lama).
    setMapData(null);
    setMapUpdatedAt(null);
    // Identitas & cakupan ikut direset: lokasi pemakai sebelumnya tidak boleh
    // terbawa ke sesi akun berikutnya.
    setMe(null);
    setActiveLocation(null);
    // Data halaman "Hari Ini" ikut dibersihkan (batch & rantai audit).
    setBatches(null);
    setBatchesError(null);
    setLedger(null);
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
          {visibleNavItems.map((n) => (
            <button
              key={n.id}
              type="button"
              className={`side-tab${tab === n.id ? " side-tab-active" : ""}`}
              onClick={() => {
                setTab(n.id);
                // Halaman bukti tidak boleh terbuka kosong: begitu tabnya ditekan,
                // keputusan yang butuh tindakan langsung dipilih.
                if (n.id === "evidence" && !selectedId) {
                  const fallback = defaultEvidenceId(decisions);
                  if (fallback) setSelectedId(fallback);
                }
              }}
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
        {/* Header global ala mockup acuan (mockupui/…/code.html): brand →
            dropdown cakupan lokasi → pill status jaringan → chip peran →
            lonceng notifikasi → identitas pemakai → keluar. */}
        <TopBar
          role={role}
          roleLabel={roleLabel}
          userName={me?.name ?? (email || roleLabel)}
          userSub={me?.location_name ? `SPPG ${me.location_name}` : null}
          locations={mapData?.locations ?? []}
          activeLocation={activeLocation}
          onSelectLocation={(value) => setActiveLocation(value)}
          ownLocation={me?.location_name ?? null}
          decisions={decisions}
          updatedAtLabel={
            mapUpdatedAt !== null
              ? `Diperbarui ${new Date(mapUpdatedAt).toLocaleTimeString("id-ID")}`
              : null
          }
          onOpenNotifications={() => setTab("recommendations")}
          onLogout={onLogout}
        />
        <div className="app-body">
        {tab === "today" && (
          /* Langkah 3 (permintaan Roy 2026-10-11): rekap operasional hari
             berjalan. Semua angka dari API — keputusan menunggu tindakan,
             batch mendekati kedaluwarsa, lokasi shortage, KPI 24 jam, dan
             status rantai audit. Klik baris membawa ke halaman terkait. */
          <TodayDashboard
            decisions={decisions}
            batches={batches}
            locations={mapData?.locations ?? []}
            commodity={mapData?.commodity ?? mapCommodity}
            kpi={kpi}
            ledger={ledger}
            now={now}
            batchesLoading={batchesLoading}
            batchesError={batchesError}
            onRetry={() => token && loadToday(token)}
            onOpenDecision={(decisionId) => {
              setSelectedId(decisionId);
              setTab("recommendations");
            }}
            onOpenAllDecisions={() => setTab("recommendations")}
            onOpenLocation={(location) => {
              setActiveLocation(location);
              setTab("overview");
            }}
          />
        )}

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
                  {mapData
                    ? `Peta ${(mapData.locations ?? []).length} lokasi SPPG — hijau surplus, merah shortage, abu seimbang.`
                    : "Memuat kondisi pasokan semua lokasi SPPG…"}
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
            <section
              className="overview-kpis"
              aria-label="KPI ringkas"
              aria-busy={!mapData && !mapError}
            >
              <div className="kpi-card">
                <span className="kpi-card-label">Volume Komoditas Aktif</span>
                <span className="kpi-card-value">
                  {mapData ? (
                    formatKg(sumFiniteKg(mapData.locations ?? []))
                  ) : (
                    <span className="skeleton skeleton-value" aria-hidden="true" />
                  )}
                </span>
                <span className="kpi-card-foot">total pasokan lokasi terpetakan</span>
              </div>
              <div className="kpi-card">
                <span className="kpi-card-label">Lokasi Surplus</span>
                <span className="kpi-card-value kpi-card-safe">
                  {mapData ? (
                    (mapData.locations ?? []).filter(
                      (l: any) => l.status === "surplus"
                    ).length
                  ) : (
                    <span className="skeleton skeleton-value" aria-hidden="true" />
                  )}
                </span>
                <span className="kpi-card-foot">siap jadi sumber distribusi</span>
              </div>
              <div className="kpi-card">
                <span className="kpi-card-label">Lokasi Shortage</span>
                <span className="kpi-card-value kpi-card-danger">
                  {mapData ? (
                    mapShortage.length
                  ) : (
                    <span className="skeleton skeleton-value" aria-hidden="true" />
                  )}
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

            {/* Peta gaya acuan (arah Roy 2026-10-11): kanvas terang apa adanya,
                legenda putih kiri-bawah, kontrol MapLibre (zoom + kompas)
                kanan-atas & atribusi kanan-bawah. Tanpa kepala/kaki panel. */}
            <section
              className="overview-split"
              aria-label="Peta dan telemetri node"
            >
              <SupplyMap
                locations={mapData?.locations ?? []}
                commodity={mapData?.commodity}
                activeLocation={activeLocation}
                loading={!mapData && !mapError}
                showStatusList={false}
                showHeader={false}
              />
              <div className="overview-side">
                <NodeTelemetry
                  locations={mapData?.locations ?? []}
                  activeLocation={activeLocation}
                  loading={!mapData && !mapError}
                />
                <div className="map-panel">
                  <h3>Pasokan per Lokasi</h3>
                  <StockChart locations={mapData?.locations ?? []} />
                </div>
              </div>
            </section>

            {/* Status lokasi selebar halaman (tata letak acuan): baris atas
                peta + grafik yang tingginya seimbang, daftar lokasi di bawah. */}
            <section
              className="map-card card status-location-list"
              aria-label="Status lokasi"
              aria-busy={!mapData && !mapError}
            >
              {mapData ? (
                <StatusLocationList locations={mapData.locations ?? []} />
              ) : (
                <>
                  <div className="map-section-head">
                    <h3>Status Lokasi</h3>
                  </div>
                  <p className="sr-only" aria-live="polite">
                    Memuat status lokasi…
                  </p>
                  <div className="skeleton skeleton-map" aria-hidden="true" />
                </>
              )}
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
            <PageHeader
              title="Demo Control Panel"
              description="Skenario deterministik untuk demo day — dijalankan lewat API resmi (tanpa mock): muat kasus, picu Event 2 (price anomaly) &amp; Event 3 (thermal excursion) dari konsol, lalu lihat hasilnya di tab Recommendations &amp; Agent Log."
            />
            <section className="card demo-scenario" aria-label="Skenario demo">
              <div className="card-header">
                <h2>Skenario 00 — muat kasus demo</h2>
              </div>
              <p className="section-sub">
                Memuat ulang empat kasus demo lewat API resmi (idempotent, aman
                dijalankan berkali-kali sebelum demo day). Hasilnya muncul di
                tab Recommendations &amp; Agent Log.
              </p>
              <button
                type="button"
                className="button button-secondary"
                onClick={onSeedDemo}
                title="Muat ulang 4 kasus demo (idempotent)"
              >
                Muat kasus demo
              </button>
            </section>
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
              <PageHeader
                title="Recommendation Feed"
                description="Urutan berdasarkan urgensi: isu keamanan lebih dulu, lalu ketidakseimbangan regional, terakhir anomali harga."
                meta={
                  <>
                    <span className="commodity-pill">
                      {decisions.length} rekomendasi
                    </span>
                    <span className="commodity-pill">
                      {perluKeputusan} menunggu keputusan
                    </span>
                  </>
                }
              />
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
                    onClick={() => {
                      setStatusFilter(null);
                      setFeedLimit(24);
                    }}
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
                        onClick={() => {
                          setStatusFilter(statusFilter === s ? null : s);
                          setFeedLimit(24);
                        }}
                      >
                        {s}
                        <span className="legend-count">{n}</span>
                      </button>
                    ))}
                </div>
              )}

              <div className="feed">
                {visibleDecisions.slice(0, feedLimit).map((d) => (
                  <div key={d.decision_id}>
                    <button
                      type="button"
                      className="link-button"
                      onClick={() => {
                        setSelectedId(d.decision_id);
                        setTab("evidence");
                      }}
                    >
                      <RecommendationCard
                        decision={d}
                        mockSourced={d.status === "executed"}
                      />
                    </button>
                  </div>
                ))}
              </div>
              {visibleDecisions.length > feedLimit && (
                <div className="feed-more">
                  <p>
                    Menampilkan {feedLimit} dari {visibleDecisions.length}{" "}
                    rekomendasi
                    {statusFilter ? ` berstatus ${statusFilter}` : ""}.
                  </p>
                  <button
                    type="button"
                    className="button button-secondary"
                    onClick={() => setFeedLimit(feedLimit + 24)}
                  >
                    Tampilkan{" "}
                    {Math.min(24, visibleDecisions.length - feedLimit)} lagi
                  </button>
                </div>
              )}
            </section>

            {/* Detail keputusan pindah ke tab tersendiri "Decision & Evidence"
                (halaman ke-3 sidebar acuan). Feed kembali fokus pada daftar;
                klik kartu = pilih keputusan + buka halaman buktinya. */}
            <p className="feed-hint">
              Klik kartu untuk membuka halaman <strong>Decision &amp; Evidence</strong>{" "}
              dengan seluruh bukti keputusan itu.
            </p>
          </>
        )}

        {/* Langkah 4 (permintaan Roy 2026-10-11): halaman "Decision & Evidence"
            — halaman ke-3 di sidebar acuan, sebelumnya menempel di bawah feed
            Recommendations. Semua angka dari API; yang tidak ada ditulis "—". */}
        {tab === "evidence" && (
          <DecisionEvidence
            decisions={decisions}
            selected={selected}
            selectedId={selectedId}
            onSelect={(decisionId) => setSelectedId(decisionId)}
            chain={selectedId ? chain : []}
            summary={approvalSummary}
            supplierContext={supplierContext}
            role={role ?? ""}
            token={token}
            now={now}
            onSupplierCreated={(decisionId) => {
              if (token) void loadDecisions(token);
              setSelectedId(decisionId);
            }}
            onOpenRecommendations={() => setTab("recommendations")}
          />
        )}

        {/* Langkah 5 (permintaan Roy 2026-10-11): halaman sidebar ACUAN
            (E:\hackathon\HackathonBil\MealchainGuardian) yang belum ada di repo
            ini — Keamanan Pangan (/compliance), Surplus & Limbah (/surplus),
            Pemasok (/suppliers), Kualitas Agen (/quality) — disesuaikan ke
            endpoint yang benar-benar ada. Angka kosong ditulis "—". */}
        {tab === "safety" && (
          <FoodSafetyBoard
            batches={batches}
            now={now}
            commodity={mapCommodity}
            loading={batchesLoading}
            error={batchesError}
            onRetry={() => token && loadToday(token)}
          />
        )}

        {tab === "surplus" && (
          <SurplusBoard
            locations={mapData?.locations ?? null}
            commodity={mapData?.commodity ?? mapCommodity}
            loading={!mapData && !mapError}
            error={mapError}
            onRetry={() => setMapRefresh((value) => value + 1)}
            onOpenLocation={(location) => {
              setActiveLocation(location);
              setTab("overview");
            }}
          />
        )}

        {tab === "suppliers" && (
          <SupplierBoard
            pairs={supplierPairs}
            exclusions={exclusions}
            selectedDecisionId={selectedId}
            supplierContext={supplierContext}
            role={role ?? ""}
            token={token ?? ""}
            loading={supplierLoading}
            error={supplierError}
            onRetry={() => {
              evaluatedKey.current = null;
              setEvaluateTick((value) => value + 1);
            }}
            onOpenDecision={(decisionId) => {
              if (decisionId) setSelectedId(decisionId);
              setTab("evidence");
            }}
            onExclusionCreated={() => token && loadDecisions(token)}
          />
        )}

        {tab === "quality" && (
          <AgentQualityBoard
            runs={qualityRuns}
            evaluatedCount={evaluatedCount}
            totalDecisions={decisions.length}
            loading={qualityLoading}
            error={qualityError}
            onRetry={() => {
              evaluatedKey.current = null;
              setEvaluateTick((value) => value + 1);
            }}
            onOpenDecision={(decisionId) => {
              setSelectedId(decisionId);
              setTab("evidence");
            }}
          />
        )}

        {/* PRD 2.4 Screen 5: Agent Activity Log & Traces Console — tab
            tersendiri (terpisah dari decision detail). Semua role bisa
            melihat observability; pilih decision di dropdown bila belum
            ada yang terpilih. */}
        {tab === "agent-log" && (
          <section className="agent-log-section">
            <PageHeader
              title="Agent Activity Log"
              description="Jejak reasoning tiap langkah agen untuk satu keputusan — model, durasi, dan pesan apa adanya dari trace; tidak ada baris yang dikarang."
              meta={
                <select
                  className="page-header-select"
                  aria-label="Pilih keputusan"
                  value={selectedId ?? ""}
                  onChange={(e) => setSelectedId(e.target.value)}
                >
                  <option value="">— pilih keputusan —</option>
                  {decisions.map((d) => (
                    <option key={d.decision_id} value={d.decision_id}>
                      {(d.decision_type ?? "keputusan")} · {d.status} ·{" "}
                      {d.decision_id.slice(0, 8)}
                    </option>
                  ))}
                </select>
              }
            />
            {selected && (
              <p className="section-sub">
                Trace untuk{" "}
                <strong>{selected.decision_type ?? "keputusan"}</strong>{" "}
                ({selected.decision_id.slice(0, 8)}) — status {selected.status}.
              </p>
            )}
            <ProviderPanel providers={providersFromTraces(traces)} />
            <AgentTraceViewer steps={traces} />
          </section>
        )}
        </div>
      </div>
    </main>
  );
}
