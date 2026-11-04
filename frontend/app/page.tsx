"use client";

// S4-06 polish (arah Roy 2026-10-08): layout sidebar per role — teks ramai
// dipindah/dipangkas, tab nav per role, peta Indonesia + grafik stok.
// SEMUA fitur lama tetap ada (wiring test mem-pin): KPI, OpsConsole,
// Event2Panel, feed, detail, trace, provider panel, approval modal.
// Konsol operasi & analisis HANYA untuk role approver (bgn_monitor
// read-only: tab analisis tidak ditampilkan).

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { MANAGE_ROLES } from "../lib/settings";

import {
  approveReceipt,
  evaluateFreshness,
  evaluateSafety,
  fetchPendingReceipts,
  fetchReceipts,
  fetchReceiptChecklist,
  login,
  recordReceipt,
  rejectReceipt,
  ubahKarantina,
  reproposeAction,
  triggerSafetyDisruption,
} from "../lib/api";
import { useBalanceMap } from "../lib/hooks/useBalanceMap";
// Dokumen 03 §6 (28 Okt 2026): Location Network + pop-up pasokan & permintaan.
import { useSupplyDemand } from "../lib/hooks/useSupplyDemand";
import { sortBySeverity } from "../lib/location-network";
import { useDecisionDetail } from "../lib/hooks/useDecisionDetail";
import { readDecisionLink, withDecisionLink } from "../lib/decision-link";
import { withDetailCost } from "../lib/decision-economics";
import { useExclusions } from "../lib/hooks/useExclusions";
import { useKpi } from "../lib/hooks/useKpi";
import { useDemoSessionId } from "../lib/hooks/useDemoSessionId";
import { useProcurementSummary } from "../lib/hooks/useProcurementSummary";
import { useWasteSummary } from "../lib/hooks/useWasteSummary";
import { useSurplusPlan } from "../lib/hooks/useSurplusPlan";
import { usePurchaseOrders } from "../lib/hooks/usePurchaseOrders";
import { agendaErrorText, useAgenda } from "../lib/hooks/useAgenda";
import {
  clampDayStep,
  gridRange,
  monthGrid,
  monthOf,
  pickerYears,
  shiftMonth,
  wibToday,
} from "../lib/agenda";
// Rentang data yang didukung backend — sumber daftar TAHUN di pemilih tanggal
// (bukan angka karangan): tahun pemilih = tahun yang dicakup rentang ini.
import { RANGE_MAX, RANGE_MIN } from "../lib/demo-data";
import type { KpiWindowKey } from "../lib/kpi";
import type { KpiScope } from "../lib/kpi-provenance";
import { useMe } from "../lib/hooks/useMe";
import { useQualitySample } from "../lib/hooks/useQualitySample";
import { useSuppliers } from "../lib/hooks/useSuppliers";
import { useReceiptHistory } from "../lib/hooks/useReceiptHistory";
import { useSupplierRoutes } from "../lib/hooks/useSupplierRoutes";
// Fase 7b: ambang jangkauan peran (SPPG 150 km, monitor tanpa ambang) — satu
// tempat aturannya, dipakai peta + halaman Pemasok.
import { supplierReachKmForRole } from "../lib/supplier-pins";
import { decodeRole } from "../lib/auth";
import {
  type DecisionRow as Decision,
  useDecisions,
} from "../lib/hooks/useDecisions";
import { useToday } from "../lib/hooks/useToday";
import { errorMessage, MAP_TRUCK_POLL_MS } from "../lib/query";
import { useSupervisorHealth } from "../lib/hooks/useSupervisorHealth";
import {
  DECISION_PAGE_SIZE,
  commodityOptions,
  filterDecisions,
  tableSummary,
  verificationCounts,
  type VerificationKey,
} from "../lib/decision-table";
import {
  FEED_WINDOWS,
  FEED_WINDOW_DEFAULT,
  feedWindowHint,
  feedWindowHintBilaBerbeda,
  feedWindowLabel,
  type FeedWindowKey,
} from "../lib/decisions-window";
import { executionOverview, needsAttention } from "../lib/agent-execution";
import {
  FEED_SCOPE_ACTION,
  FEED_SCOPE_ALL,
  FEED_SORT_LABELS,
  feedChips,
  feedSummary,
  feedVisible,
  hasActiveFilter,
  sortFeed,
  type FeedSort,
} from "../lib/decision-feed";
import { useQueryClient } from "@tanstack/react-query";
import { formatDateTime } from "../lib/datetime";
import SettingsPanel from "../components/SettingsPanel";
import FeedEmptyState from "../components/FeedEmptyState";
import LocationNetworkBoard from "../components/LocationNetworkBoard";
import Pager from "../components/Pager";
import { paginate } from "../lib/pagination";
import TopBar from "../components/TopBar";
import {
  ALL_LOCATIONS,
  countActionable,
  countDraftActionable,
  countExpiredActionable,
  defaultScope,
  initialsOf,
  notifList,
} from "../lib/topbar";
import StatusBadge from "../components/StatusBadge";
import ValidatedField from "../components/ValidatedField";
import {
  ChevronIcon,
  LogoMark,
  LogoutIcon,
  type NavId,
} from "../components/NavIcon";
import SideNav from "../components/SideNav";
import PriceMonitor from "../components/PriceMonitor";
import RecommendationCard, { DECISION_TYPE_LABELS } from "../components/RecommendationCard";
// Satu sumber aturan peran/status: kartu feed tidak boleh menebak sendiri siapa
// yang boleh menyetujui (daftar peran duplikat = dua kebenaran yang menyimpang).
import { visibleActions } from "../components/DecisionActions";
import AgentActivityPanel from "../components/AgentActivityPanel";
import AgentRoster from "../components/AgentRoster";
import AgentRunSummary from "../components/AgentRunSummary";
import IntegrityPanel from "../components/IntegrityPanel";
import ModuleSearch from "../components/ModuleSearch";
import PeriodPicker from "../components/PeriodPicker";
import SupervisorAskPanel from "../components/SupervisorAskPanel";
import SupervisorStatusLine from "../components/SupervisorStatusLine";
import AgentTraceViewer from "../components/AgentTraceViewer";
import { defaultAgentLogId } from "../lib/agent-swarm";
import DemoControlPanel from "../components/DemoControlPanel";
import DemoSessionBanner from "../components/DemoSessionBanner";
import { mapHeaderSubtitle } from "../lib/overview-copy";
import DecisionChain from "../components/DecisionChain";
import PageHeader from "../components/PageHeader";
import PageShell from "../components/PageShell";
import SectionJump from "../components/SectionJump";
import ProcurementToday from "../components/ProcurementToday";
import { overviewSections } from "../lib/section-jump";
import KpiQualityBoard from "../components/KpiQualityBoard";
import SupplyMap from "../components/SupplyMap";
import TodayDashboard from "../components/TodayDashboard";
import AdequacyColumns from "../components/AdequacyColumns";
import SurplusRegionPanel from "../components/SurplusRegionPanel";
import { useCommodityBalance } from "../lib/hooks/useCommodityBalance";
import { useSurplusRegions } from "../lib/hooks/useSurplusRegions";
import { buildAdequacyRows } from "../lib/supply-adequacy";
import { formatKg, snapshotNote, syncLabel } from "../lib/overview-format";
import { pendingKpiCopy, queueQuantityLabel } from "../lib/overview-kpi";
// Jejak kepercayaan (28 Okt 2026): empat bukti di bawah antrean keputusan —
// logika murni di lib/trust-trail.ts (diuji di tests/trust-trail.test.ts).
import { trustTrail } from "../lib/trust-trail";
import TrustTrailCard from "../components/TrustTrailCard";
// Fase 2 bento Overview: selisih hero & pangsa terhadap kebutuhan — logika
// murni di lib/overview-bento.ts (diuji di tests/overview-bento.test.ts).
import {
  demandCoveragePct,
  formatSignedKg,
  gapShareOfDemand,
  heroGap,
  networkTotals,
} from "../lib/overview-bento";
import { SupplierExclusionView } from "../components/SupplierExclusionPanel";
import DecisionEvidence from "../components/DecisionEvidence";
import DecisionDrawer from "../components/DecisionDrawer";
import Popup from "../components/Popup";
import SupplyDemandPanel from "../components/SupplyDemandPanel";
import FoodSafetyBoard from "../components/FoodSafetyBoard";
import SupplierBoard from "../components/SupplierBoard";
import { runOf, type QualityRun } from "../lib/agent-quality";
import { defaultEvidenceId } from "../lib/evidence";
import {
  PAGE_TITLES,
  locationNetworkHint,
  locationNetworkTitle,
} from "../lib/navigation";
import {
  AGENT_LOG_SECTION_IDS,
  agentLogSections,
} from "../lib/section-jump";

const APPROVER_ROLES = new Set(["sppg_head", "sppg_nutritionist"]);

// Recommendation Feed: 10 kartu per halaman, sama seperti Daftar Pemasok dan
// Papan Kiriman. Semua kartu yang lolos filter tetap bisa dijangkau lewat Pager.
const FEED_PAGE_SIZE = 10;

// Antrean "Perlu keputusan" di Overview: barisnya dipadatkan (satu baris teks +
// badge, 56 px) sehingga EMPAT keputusan teratas tetap terlihat dalam tinggi
// separuh kartu lama — yang dipangkas tingginya, bukan jumlah yang bisa
// dibaca. Sisa pekerjaan tetap dinyatakan apa adanya di kaki kartu
// ("+N keputusan lain menunggu tindakan") dan seluruhnya bisa dibuka lewat tab
// Recommendations — tidak ada keputusan yang hilang diam-diam.
const QUEUE_SHOWN = 4;

// Halaman Kualitas Agen & Pemasok menilai SAMPEL keputusan terakhir dalam
// cakupan: jejak agen + putusan verifikator dipanggil per keputusan, jadi
// jumlahnya dibatasi — angkanya ditulis apa adanya di halaman, bukan
// diam-diam dipotong. Halaman Surplus & Limbah ikut aturan acuan: hanya
// peran SPPG yang melihatnya.
const EVALUATED_LIMIT = 8;

// Panel provider dihitung dari trace aktual (VERIFY/PREDICT/SUPERVISE);
// tanpa karangan — agen tanpa langkah model tampil "tidak tersedia".
// CATATAN: baris di bawah membandingkan verdict SERVER ("UNAVAILABLE") — itu
// nilai kontrak, bukan label layar. Jangan disamakan dengan teks tampilan.
/**
 * Berapa langkah trace yang benar-benar berasal dari MODEL (bukan tool).
 * Dipakai AgentRunSummary untuk membedakan "trace ada tapi tanpa langkah model"
 * dari "trace ada dan model ikut menjawab" — dua keadaan yang berbeda.
 */
function modelStepCount(steps: any[]): number {
  return (steps ?? []).filter(
    (s) =>
      ["VERIFY", "SUPERVISE"].includes(s?.step_name) &&
      Boolean(s?.output_summary?.provider || s?.agent_name)
  ).length;
}

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

// Tipe baris feed kini dipegang lib/hooks/useDecisions.ts (`DecisionRow`) supaya
// hook dan halaman memakai kontrak yang sama.

// Persona label sesuai PRD 2.4 §2 (Judul resmi, Indonesia pada sub-label).
const ROLE_LABEL: Record<string, string> = {
  sppg_head: "SPPG Operations Lead",
  sppg_nutritionist: "Food Safety Officer",
  bgn_monitor: "National Inspector",
};

const COMMODITIES = ["telur", "ayam", "beras", "wortel"];

/** Kunci penyimpanan token sesi di browser (keputusan pemilik 2026-10-16).
 *  Token JWT tetap ditandatangani & diverifikasi backend — ini hanya persistensi
 *  tampilan supaya refresh halaman tidak memaksa login ulang di tengah demo. */
const TOKEN_STORAGE_KEY = "mealchain.token";

export default function Home() {
  const [token, setToken] = useState<string | null>(null);
  const [role, setRole] = useState<string | null>(null);
  // Pulihkan sesi tersimpan SETELAH mount (bukan saat render) supaya HTML dari
  // server identik dengan render pertama klien — tidak ada galat hidrasi.
  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(TOKEN_STORAGE_KEY);
      if (saved) {
        setToken(saved);
        setRole(decodeRole(saved));
      }
    } catch {
      // localStorage diblokir (mode privat / kebijakan browser): sesi jatuh ke
      // perilaku lama (hanya di memori). Tidak ada yang gagal diam-diam.
    }
  }, []);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  // PRD 2.4 (arah Roy 2026-10-09): navigasi = 5 tab sesuai 7 screen PRD
  // (login terpisah; decision detail gabung di recommendations).
  // + "today" (halaman "Hari Ini", permintaan Roy 2026-10-11). Halaman yang
  // dibuka setelah login tetap Overview — tab baru tidak mengubah alur demo.
  const [tab, setTab] = useState<NavId>("overview");
  // Periode feed rekomendasi (permintaan pemilik 24 Okt 2026): hari ini /
  // 7 hari / 1 bulan. Dideklarasikan di sini karena query feed di bawah sudah
  // memakainya; angkanya tetap dari backend (`GET /decisions?window=…`).
  const [feedWindow, setFeedWindow] = useState<FeedWindowKey>(FEED_WINDOW_DEFAULT);
  // Tab Agent Log (dokumen `06-agent-log.md`, 28 Okt 2026): pencarian + periode
  // milik modul itu sendiri. Dipisah dari feed rekomendasi supaya mempersempit
  // satu tab tidak diam-diam mengubah tab lain.
  const [logWindow, setLogWindow] = useState<FeedWindowKey>(FEED_WINDOW_DEFAULT);
  const [logQuery, setLogQuery] = useState("");
  const [logCommodity, setLogCommodity] = useState<string | null>(null);
  const [logVerification, setLogVerification] = useState<VerificationKey>("all");
  // Triage Agent Log (UI-1): hanya keputusan yang ditandai verifikator atau
  // lewat tenggat. Saringan ini bekerja pada baris yang sudah dimuat untuk
  // periode terpilih — bukan panggilan server baru, jadi angkanya sama dengan
  // yang terlihat di tabel.
  const [logAttention, setLogAttention] = useState(false);
  const [logPage, setLogPage] = useState(1);
  // Saringan tahap dari chip strip pipeline (Tahap 4 redesign, 29 Okt 2026).
  // Disimpan di halaman karena dua komponen berbeda memakainya: chip ada di
  // panel, sedangkan daftar langkah yang disaring ada di bawahnya.
  const [logStage, setLogStage] = useState<string | null>(null);
  const [mapCommodity, setMapCommodity] = useState("telur");
  // Lokasi aktif yang disorot di peta, dipilih dari dropdown top bar.
  const [activeLocation, setActiveLocation] = useState<string | null>(null);
  // Dokumen 03 §3 (28 Okt 2026) — modul gabungan "Location Network / Pasokan &
  // Kebutuhan". `networkSelected` adalah lokasi yang barisnya sedang terbuka —
  // satu state, karena "yang dipilih" dan "yang dibaca" hal yang sama di sini.
  const [networkSelected, setNetworkSelected] = useState<string | null>(null);
  // Kiriman yang sedang disorot di peta (Arah C riset 16 Okt 2026). `null` =
  // semua kiriman; satu nilai ini dipakai BERSAMA oleh pemilih di peta dan kartu
  // kiriman di bawahnya, jadi angka di kartu dan garis di peta tidak bisa beda
  // cerita. Dikosongkan otomatis saat pemakai berpindah peran/tab? Tidak:
  // id-nya gagal-tertutup (id tak dikenal = tampilan semua), jadi tidak perlu
  // efek pembersih yang bisa lupa dipasang.
  const [focusedRoute, setFocusedRoute] = useState<string | null>(null);
  // Kerangka acuan: rail bisa dilipat (lebar 68px, label disembunyikan).
  const [sideCollapsed, setSideCollapsed] = useState(false);
  // Identitas pemakai (GET /auth/me) lewat React Query (Rules.md §3). Kunci
  // dibedakan per sesi token (potongan akhir, bukan token penuh) supaya cache
  // identitas tidak tertukar antar akun; gagal membaca = gagal-tertutup (null),
  // bukan menampilkan semua lokasi.
  const sesiScope = token ? `sesi:${token.slice(-8)}` : "anon";
  const meQuery = useMe(token, sesiScope);
  const me = meQuery.me;

  // Token tersimpan yang ternyata TIDAK SAH (401 dari /auth/me) dibuang di sini:
  // sesi lama tidak boleh menyisakan dashboard setengah hidup yang semua
  // querynya gagal. Server tetap satu-satunya penentu sah/tidaknya token.
  useEffect(() => {
    if (!meQuery.unauthorized) return;
    try {
      window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    } catch {
      // localStorage diblokir: tidak ada yang perlu dibersihkan.
    }
    setToken(null);
    setRole(null);
  }, [meQuery.unauthorized]);

  // Cakupan awal: monitor nasional = semua lokasi, peran SPPG = SPPG-nya.
  useEffect(() => {
    if (!token) return;
    setActiveLocation(defaultScope({ role, ownLocation: me?.location_name ?? null }));
  }, [token, role, me]);
  // Fase 2 Langkah 4 (Rules.md §3): feed lewat React Query. Cakupan kunci =
  // peran + lokasi (itulah yang menentukan data yang berhak dilihat), dan cache
  // dikosongkan saat keluar sehingga akun berikutnya tidak melihat sisa sesi
  // sebelumnya.
  const identityScope = `${role ?? "anon"}:${me?.location_name ?? "all"}`;
  const queryClient = useQueryClient();
  // Peta dimuat di SEMUA tab: datanya dipakai top bar (dropdown cakupan +
  // ringkasan jaringan), bukan hanya halaman Overview. Stempel "terakhir
  // diperbarui" datang dari React Query, bukan state kedua yang bisa menyimpang.
  const mapQuery = useBalanceMap(token, identityScope, mapCommodity);
  // Rincian lokasi (pasokan/kebutuhan/batch/perkiraan) dimuat untuk baris yang
  // sedang terbuka. `null` = tidak ada baris terbuka → hook tidak memanggil apa pun.
  const supplyDemand = useSupplyDemand(
    token,
    networkSelected ? { location: networkSelected, commodity: mapCommodity } : null
  );
  // Lokasi pertama yang dipilih = yang paling kekurangan, bukan yang kebetulan
  // pertama di daftar server. Hanya SEKALI per kunjungan tab: tanpa penanda ini,
  // menutup baris (selected → null) langsung memicu pemilihan ulang dan baris
  // tidak pernah bisa ditutup (terukur di browser).
  const autoPilihRef = useRef(false);
  useEffect(() => {
    if (tab !== "location-network") {
      autoPilihRef.current = false;
      return;
    }
    if (autoPilihRef.current || networkSelected) return;
    const terparah = sortBySeverity(mapQuery.data?.locations ?? [])[0];
    if (terparah) {
      autoPilihRef.current = true;
      setNetworkSelected(terparah.location);
    }
  }, [tab, networkSelected, mapQuery.data?.locations]);
  // Grafik kecukupan membandingkan EMPAT komoditas sekaligus untuk SATU
  // lokasi. SPPG/gizi selalu memakainya; BGN Monitor memakainya begitu ia
  // memilih lokasi tertentu (bukan "__all__"). Saat BGN masih nasional,
  // grafiknya tetap lintas lokasi (SupplyBalanceChart), jadi empat query
  // tambahan ini tidak dijalankan tanpa guna.
  const peranSpPG = APPROVER_ROLES.has(role ?? "");
  const bgnLokasiSpesifik =
    role === "bgn_monitor" &&
    Boolean(activeLocation) &&
    activeLocation !== ALL_LOCATIONS;
  const pakaiGrafikKecukupan = peranSpPG || bgnLokasiSpesifik;
  const commodityBalance = useCommodityBalance(
    token,
    identityScope,
    COMMODITIES,
    pakaiGrafikKecukupan
  );
  // Panel "Surplus wilayah lain" (28 Okt 2026) — separuh kanan baris grafik
  // kecukupan. Sumber angkanya SERVER (`/surplus/regions`), karena peta akun
  // SPPG hanya memuat lokasinya sendiri: "daerah lain" tidak ada di data klien.
  // - SPPG/gizi & BGN yang memilih lokasi: empat komoditas, lokasi sendiri
  //   dibuang (`exclude`) supaya angka = surplus daerah LAIN.
  // - BGN nasional: satu komoditas yang sedang dipilih di peta, seluruh
  //   jaringan (tanpa exclude) — "daerah lain" tidak punya arti di skala itu.
  const bgnNasional =
    role === "bgn_monitor" && (!activeLocation || activeLocation === ALL_LOCATIONS);
  const komoditasSurplus = useMemo(() => {
    if (pakaiGrafikKecukupan) return [...COMMODITIES];
    // `mapQuery.data` langsung, bukan `mapData`: const itu dideklarasikan
    // SETELAH blok ini (urutan file), dan memakainya di sini adalah TDZ.
    const satu = String(mapQuery.data?.commodity ?? mapCommodity ?? "");
    return satu ? [satu] : [];
  }, [pakaiGrafikKecukupan, mapQuery.data?.commodity, mapCommodity]);
  const lokasiPanel = bgnNasional
    ? null
    : activeLocation && activeLocation !== ALL_LOCATIONS
      ? activeLocation
      : me?.location_name?.trim() || null;
  const surplusRegions = useSurplusRegions(
    token,
    identityScope,
    komoditasSurplus,
    lokasiPanel,
    tab === "overview"
  );
  // Purchase order mock SAP (W-5): sisi baca yang selama ini tidak ada. Kunci
  // query memakai `identityScope` karena isinya berbeda per peran.
  const purchaseOrders = usePurchaseOrders(token, identityScope);
  const mapData = mapQuery.data;
  const mapError = mapQuery.error;
  const mapUpdatedAt = mapQuery.updatedAt;
  const decisionsQuery = useDecisions(token, identityScope);
  // Daftar KHUSUS feed rekomendasi (jendela terpilih). Dipisah dari
  // `decisionsQuery` supaya lonceng notifikasi, badge sidebar, dan KPI tetap
  // memakai seluruh riwayat — mempersempit feed tidak boleh mengubah arti
  // angka "21 menunggu tindakan" di luar feed.
  const feedWindowQuery = useDecisions(
    token,
    identityScope,
    feedWindow,
    tab === "recommendations"
  );
  const feedWindowDecisions = useMemo(
    () => feedWindowQuery.data?.items ?? [],
    [feedWindowQuery.data]
  );
  // Feed KHUSUS tab Agent Log: periode sendiri + hanya jalan saat tab dibuka.
  const agentLogQuery = useDecisions(
    token,
    identityScope,
    logWindow,
    tab === "agent-log"
  );
  const agentLogRows = useMemo(
    () => agentLogQuery.data?.items ?? [],
    [agentLogQuery.data]
  );
  const agentLogFiltered = useMemo(
    () =>
      filterDecisions(agentLogRows, {
        query: logQuery,
        commodity: logCommodity,
        verification: logVerification,
      }),
    [agentLogRows, logQuery, logCommodity, logVerification]
  );
  const agentLogCommodities = useMemo(
    () => commodityOptions(agentLogRows),
    [agentLogRows]
  );
  const agentLogCounts = useMemo(
    () => verificationCounts(agentLogRows),
    [agentLogRows]
  );
  const supervisorHealth = useSupervisorHealth(token, tab === "agent-log");
  // Dibungkus useMemo: literal `[]` baru setiap render akan membuat useMemo
  // turunan (sampel → run/pemasok) dihitung ulang tanpa perlu.
  const decisions = useMemo(() => decisionsQuery.data?.items ?? [], [decisionsQuery.data]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  // Tabel keputusan adalah SATU-SATUNYA pemilih setelah pemilih di kepala
  // halaman dihapus (29 Okt 2026). Kalau keputusan terpilih (dipilih otomatis
  // saat tab dibuka, atau lewat tautan `?keputusan=`) berada di halaman lain,
  // baris "Dipilih" tidak terlihat sama sekali — jadi halaman digeser ke baris
  // yang memuatnya.
  //
  // Penjaga `pageShownFor`: pergeseran hanya terjadi saat ID TERPILIH berubah.
  // Tanpa itu, setiap penyegaran data (daftar tersaring diganti objek baru)
  // akan menarik pengguna kembali dari halaman yang sedang ia buka — terukur di
  // aplikasi hidup: pindah ke halaman 1 lalu data di-seed ulang = kembali ke 2.
  const pageShownFor = useRef<string | null>(null);
  useEffect(() => {
    if (!selectedId || tab !== "agent-log") return;
    if (pageShownFor.current === selectedId) return;
    const indeks = agentLogFiltered.findIndex((row) => row.decision_id === selectedId);
    if (indeks < 0) return;
    pageShownFor.current = selectedId;
    setLogPage(Math.floor(indeks / DECISION_PAGE_SIZE) + 1);
  }, [selectedId, agentLogFiltered, tab]);
  // 28 Okt 2026 (permintaan pemilik): "detail & jejak agen" dibuka sebagai POPUP
  // di atas halaman yang sedang dipakai, bukan dengan berpindah tab. Alasannya
  // praktis: pengguna yang mengklik kartu ke-7 dari feed kehilangan posisi
  // scroll & filter, lalu harus kembali sendiri. Menutup popup mengembalikan
  // fokus ke kartu yang diklik (ref pemicu, lihat `Popup`).
  const [popupKeputusanId, setPopupKeputusanId] = useState<string | null>(null);
  const [popupTampilan, setPopupTampilan] = useState<"rincian" | "persetujuan">("rincian");
  const popupTriggerRef = useRef<HTMLElement | null>(null);
  // Tampilan awal popup dipilih DI KARTU ("Rincian" / "Persetujuan"), bukan
  // dengan tab di dalam popup — permintaan pemilik 28 Okt 2026. Jejak agen
  // bukan tombol kartu lagi; ia tautan tenang di kepala popup.
  const bukaPopupKeputusan = useCallback(
    (
      decisionId: string,
      pemicu: HTMLElement | null,
      tampilan: "rincian" | "persetujuan" = "rincian"
    ) => {
      popupTriggerRef.current = pemicu;
      setPopupTampilan(tampilan);
      setSelectedId(decisionId);
      setPopupKeputusanId(decisionId);
    },
    []
  );
  // ── Deep link `?keputusan=<id>` (Langkah 3) ──────────────────────────────
  // `linkSiap` memastikan pembacaan URL selesai SEBELUM efek penulis berjalan,
  // supaya param yang baru dibuka tidak langsung dihapus pada commit pertama.
  const linkSiap = useRef(false);
  useEffect(() => {
    if (!linkSiap.current) return;
    const sekarang = window.location.search;
    // Param hanya mewakili tab bukti: pindah tab → param dilepas, supaya
    // tautan tidak menunjuk keputusan yang tidak sedang dilihat.
    const berikut = withDecisionLink(sekarang, tab === "evidence" ? selectedId : null);
    if (berikut === sekarang) return;
    window.history.replaceState(
      null,
      "",
      `${window.location.pathname}${berikut}${window.location.hash}`
    );
  }, [selectedId, tab]);
  useEffect(() => {
    const dariUrl = readDecisionLink(window.location.search);
    if (dariUrl) {
      setSelectedId(dariUrl);
      setTab("evidence");
    }
    linkSiap.current = true;
  }, []);
  // Tautan "Lihat keputusan" di panel purchase order. Dulu tautan itu memuat
  // ulang halaman (navigasi penuh): pengguna yang sedang di dasar halaman tetap
  // melihat daftar PO yang sama sehingga terasa "tidak berfungsi" (laporan
  // pemilik, 19 Okt 2026). Sekarang keputusan dipindahkan DI DALAM aplikasi,
  // lalu digulir ke kepala keputusannya — pilihan harus terlihat, bukan hanya
  // tersimpan di URL.
  const bukaKeputusanDariPO = useCallback((decisionId: string) => {
    setSelectedId(decisionId);
    setTab("evidence");
    // Dua frame: satu untuk commit React, satu untuk memastikan kartu keputusan
    // sudah ada di DOM sebelum digulir.
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        document
          .getElementById("ringkasan")
          ?.scrollIntoView({ block: "start", behavior: "smooth" });
      });
    });
  }, []);
  // Detail keputusan terpilih (jejak, rantai, ringkasan kanonik, konteks
  // pemasok) lewat React Query — lihat lib/hooks/useDecisionDetail.ts.
  const detail = useDecisionDetail(token, selectedId, identityScope);
  // Keputusan yang dipilih ternyata sudah tidak ada (404). Jangan biarkan
  // `selectedId` + `?keputusan=` menahan id mati: lepaskan pilihan supaya
  // efek tautan dalam menulis ulang URL dan pemilihan default mengambil alih.
  const [pesanDiganti, setPesanDiganti] = useState<string | null>(null);
  useEffect(() => {
    if (!detail.gone || !selectedId) return;
    setPesanDiganti(
      `Keputusan #${String(selectedId).slice(0, 8)} sudah diganti oleh Muat Demo — ` +
        "pilih keputusan terbaru di kanan atas."
    );
    setSelectedId(null);
  }, [detail.gone, selectedId]);
  const traces = detail.traces;
  const chain = detail.chain;
  // S4-04: read model kanonik dari /approval-summary — sumber tunggal modal.
  const approvalSummary = detail.approvalSummary;
  const supplierContext = detail.supplierContext;
  // Galat yang bukan dari feed keputusan (mis. seed demo gagal) ditampung di
  // sini; galat feed dibaca langsung dari status query.
  const [traceError, setTraceError] = useState<string | null>(null);
  // Fase 2 Langkah 4: data halaman "Hari Ini" (batch + rantai audit) lewat
  // React Query. Nilai kosong tetap "—", bukan 0.
  const todayQuery = useToday(token, identityScope);
  const batches = todayQuery.data?.batches ?? null;
  // Kartu "Batch <48 jam" di halaman Today milik satu SPPG: kiriman kota lain
  // (BDG/SBY/SMG) tidak boleh muncul di sana — juri membacanya sebagai salah
  // cakupan. Panel Food Safety tetap memakai daftar jaringan penuh (ia punya
  // sakelar cakupan sendiri), jadi penyaringan hanya di sini.
  const batchesHariIni = useMemo(() => {
    if (!batches) return batches;
    if (role !== "sppg_head" && role !== "sppg_nutritionist") return batches;
    const sendiri = me?.location_name?.trim().toLowerCase();
    if (!sendiri) return batches;
    return batches.filter(
      (b) => String((b as { location?: string }).location ?? "").trim().toLowerCase() === sendiri
    );
  }, [batches, role, me?.location_name]);
  const ledger = todayQuery.data?.ledger ?? null;
  const batchesLoading = todayQuery.isFetching;
  const batchesError = errorMessage(todayQuery.error);
  const grafikKecukupanError = commodityBalance.error ?? batchesError;
  const decisionsError = errorMessage(decisionsQuery.error);
  const error = decisionsError ?? traceError;
  // Jam klien: null sampai komponen ter-mount supaya HTML server dan render
  // klien tidak berbeda (label waktu ditulis "—" sebelum jam siap).
  const [now, setNow] = useState<Date | null>(null);
  // Baris kecukupan dihitung murni dari empat peta komoditas + batch. `now`
  // menentukan batch mana yang ≤48 jam/kedaluwarsa; sebelum jam siap, grafik
  // menampilkan skeleton (bukan 0% yang menakutkan).
  const adequacyRows = useMemo(() => {
    const lokasi =
      activeLocation && activeLocation !== ALL_LOCATIONS
        ? activeLocation
        : me?.location_name?.trim() || "";
    if (!now || !pakaiGrafikKecukupan || !lokasi) return [];
    return buildAdequacyRows({
      commodities: COMMODITIES,
      byCommodity: commodityBalance.byCommodity,
      batches,
      location: lokasi,
      now,
    });
  }, [
    now,
    activeLocation,
    me?.location_name,
    pakaiGrafikKecukupan,
    commodityBalance.byCommodity,
    batches,
  ]);
  // UI-1 Agent Log (29 Okt 2026): ringkasan eksekusi + saringan triage.
  // Keduanya dihitung dari baris yang SAMA dengan tabel (hasil `/decisions`
  // periode terpilih) — bukan panggilan server baru dan bukan angka karangan.
  const agentLogOverview = useMemo(
    () => (now ? executionOverview(agentLogRows, now) : null),
    [agentLogRows, now]
  );
  const agentLogShown = useMemo(() => {
    // `now` belum siap (render server): jangan saring apa pun, karena
    // "lewat tenggat" tidak bisa dinilai tanpa jam acuan.
    if (!logAttention || !now) return agentLogFiltered;
    return agentLogFiltered.filter((row) => needsAttention(row, now));
  }, [agentLogFiltered, logAttention, now]);
  const agentLogSummary = tableSummary({
    shown: agentLogShown.length,
    total: agentLogRows.length,
    query: logQuery,
    commodity: logCommodity,
    verification: logVerification,
  });
  // 19 Okt 2026: daftar keputusan sering tiba SETELAH tab dibuka (muat awal),
  // sehingga handler SideNav di atas tidak menemukan apa pun dan tab terbuka
  // dengan "Pilih keputusan" padahal daftarnya sudah berisi. Efek ini menjadi
  // jaring kedua: begitu daftar tersedia, keputusan bawaan langsung dipilih.
  useEffect(() => {
    if (selectedId) return;
    const bawaan =
      tab === "evidence"
        ? defaultEvidenceId(decisions, now ?? null)
        : tab === "agent-log"
          ? defaultAgentLogId(decisions, null)
          : null;
    if (bawaan) setSelectedId(bawaan);
  }, [tab, decisions, selectedId, now]);
  // Kualitas Agen & Pemasok: sampel keputusan (jejak agen + ringkasan) dan
  // register eksklusi lewat React Query — dua siklus muat yang berbeda.
  const sampleIds = decisions.slice(0, EVALUATED_LIMIT).map((d) => d.decision_id);
  const sampleQuery = useQualitySample(token, identityScope, tab, sampleIds);
  const exclusions = useExclusions(token, identityScope, tab).data;
  // Daftar pemasok (GET /suppliers) — dipakai DUA permukaan dengan aturan jangkauan
  // berbeda (Fase 7b):
  // - peta Overview: peran SPPG memakai penyaring server 150 km (hanya pemasok
  //   terjangkau yang dikirim, jumlah yang dibuang dilaporkan server di `reach`);
  // - halaman Pemasok: daftar PENUH + kolom jarak + label "di luar jangkauan",
  //   supaya penyaringan tidak pernah berarti penyembunyian.
  const supplierReachKm = useMemo(() => supplierReachKmForRole(role), [role]);
  // Filter komoditas ikut ke server (bukan hanya di klien) supaya "N di luar
  // jangkauan" yang dilaporkan server berlaku untuk komoditas yang dilihat.
  const mapSuppliersQuery = useSuppliers(
    token,
    identityScope,
    tab,
    supplierReachKm,
    mapData?.commodity ?? null
  );
  const suppliersQuery = useSuppliers(token, identityScope, tab);
  // Riwayat penerimaan per pemasok (Dok 05 §8.5): dimuat hanya saat tab Pemasok
  // aktif, sama seperti daftar pemasok — layar lain tidak membayar permintaan ini.
  const receiptHistoryQuery = useReceiptHistory(token, identityScope, tab);
  // Jalur kiriman (Fase 10): garis jalan pemasok → tujuan. Peta memakai yang
  // sekomoditas dengan tampilan; halaman Pemasok memakai daftar penuh supaya
  // tabel bisa menyebut jalur untuk semua kiriman aktif.
  const mapSupplierRoutesQuery = useSupplierRoutes(
    token,
    identityScope,
    tab,
    mapData?.commodity ?? null,
    null,
    false,
    // Denyut khusus peta: 15 detik cukup untuk membuat mobil kiriman maju
    // beberapa persen (animasi geser 700 ms di SupplyMap) tanpa membebani
    // backend saat tab peta tidak dibuka (query-nya memang tidak aktif).
    MAP_TRUCK_POLL_MS
  );
  // Tabel Pemasok menampilkan SEMUA pemasok (tidak disaring komoditas), jadi
  // jalurnya juga daftar penuh — kalau disaring komoditas, baris pemasok lain
  // akan terbaca "tidak punya jalur" padahal jalurnya hanya tidak diminta.
  const supplierRoutesQuery = useSupplierRoutes(token, identityScope, tab);
  // Fase 11 (permintaan pemilik): tab Keamanan Pangan butuh kiriman yang menuju
  // LOKASI SENDIRI — bukan semua jalur seperti halaman Pemasok — supaya kartu
  // "Pasokan masuk" menjawab pertanyaan dapur ini ("apa yang sedang datang ke
  // sini?"). Query hanya berjalan saat tab itu dibuka.
  const safetyRoutesQuery = useSupplierRoutes(
    token,
    identityScope,
    tab,
    null,
    me?.location_name ?? null,
    tab === "safety"
  );

  // Fase 11: dua tindakan nyata dari halaman Keamanan Pangan. Keduanya MENULIS
  // ke backend (bukan pratinjau): /freshness/evaluate + /safety/evaluate
  // menghitung ulang dari log suhu & umur panen yang tersimpan lalu menyimpan
  // hasilnya, dan /actions/repropose membuat keputusan pengganti dari yang sudah
  // kedaluwarsa. Setelah menulis, data diambil ulang dari server — layar tidak
  // pernah menebak hasilnya sendiri.
  const safetyRecheck = async (batchId: string) => {
    if (!token) throw new Error("sesi tidak ada");
    const [safety, freshness] = await Promise.all([
      evaluateSafety(batchId, token),
      evaluateFreshness(batchId, token),
    ]);
    await Promise.all([todayQuery.refetch(), mapQuery.refetch()]);
    return { safety, freshness };
  };

  // Dua loader untuk kartu Penerimaan barang. Identitasnya HARUS stabil
  // (deps `token` saja): fungsi inline membuat FoodSafetyBoard memuat ulang
  // antrean persetujuan dan daftar ceklis pada setiap render — terukur
  // 29 Okt 2026: 30 permintaan dalam 10 detik (15 + 15) selagi tab terbuka.
  const loadReceiptChecklist = useCallback(
    (komoditas: string) => fetchReceiptChecklist(komoditas, token ?? ""),
    [token]
  );
  const loadPendingReceiptsStabil = useCallback(
    () => fetchPendingReceipts(token ?? ""),
    [token]
  );

  // Persetujuan penerimaan (migrasi 026): server menulis stok, lalu Overview,
  // Hari Ini, dan feed keputusan diambil ulang — layar tidak menambah angka
  // sendiri. `stock_kg` dikembalikan agar kartu bisa menyebut kg yang masuk.
  const receiptApprove = async (receiptId: string) => {
    if (!token) throw new Error("sesi tidak ada");
    const hasil = await approveReceipt(receiptId, token);
    await Promise.all([
      todayQuery.refetch(),
      mapQuery.refetch(),
      decisionsQuery.refetch(),
    ]);
    return { stock_kg: hasil?.stock_kg ?? null };
  };

  const receiptReject = async (receiptId: string, note: string) => {
    if (!token) throw new Error("sesi tidak ada");
    const hasil = await rejectReceipt(receiptId, note, token);
    await Promise.all([todayQuery.refetch(), mapQuery.refetch()]);
    return hasil;
  };

  const safetyRepropose = async (decisionId: string) => {
    if (!token) throw new Error("sesi tidak ada");
    const hasil = await reproposeAction(decisionId, token);
    await decisionsQuery.refetch();
    return String(hasil?.decision_id ?? "");
  };

  // Event 3 dari satu baris tabel: batch pemicu boleh milik lokasi lain (sisi
  // sumber), tetapi keputusan yang lahir WAJIB menyasar lokasi pemakai sendiri
  // (ruling 2026-10-14) — karena itu target diambil dari identitas, bukan dari
  // baris yang diklik. Kunci idempotensi dibuat pemanggil (dipakai ulang saat
  // mengulang supaya tidak ada keputusan kembar).
  const safetyTriggerDisruption = async (batchId: string, operationKey: string) => {
    if (!token) throw new Error("sesi tidak ada");
    if (!me?.location_id) throw new Error("lokasi pemakai belum diketahui");
    const hasil = await triggerSafetyDisruption(batchId, me.location_id, operationKey, token);
    await Promise.all([decisionsQuery.refetch(), todayQuery.refetch()]);
    return hasil;
  };

  // Karantina batch (keputusan manusia): simpan alasan → server menulis blok
  // ledger sendiri, lalu data batch dimuat ulang supaya tabel tidak berbohong.
  const safetyKarantina = async (
    batchId: string,
    aksi: "tahan" | "lepas" | "gagal",
    alasan: string
  ) => {
    if (!token) throw new Error("sesi tidak ada");
    await ubahKarantina(batchId, aksi, alasan, token);
    await todayQuery.refetch();
  };

  // Feed (14 Okt 2026): cakupan + pencarian + urutan. Cakupan "action" =
  // keputusan yang benar-benar menunggu tindakan manusia — definisi yang sama
  // dengan lonceng top bar dan angka di sidebar. EXPIRED tetap bisa dilihat
  // lewat chip "Semua"/status (tidak pernah disembunyikan).
  const [feedScope, setFeedScope] = useState<string>(FEED_SCOPE_ALL);
  const [feedQuery, setFeedQuery] = useState("");
  const [feedSort, setFeedSort] = useState<FeedSort>("urgency");
  // Feed berisi puluhan keputusan; tampilkan 10 kartu per halaman supaya
  // halaman tidak menjadi gulungan panjang. Pager menyebut rentang ("1–10 dari
  // 24") dan semua kartu tetap bisa dijangkau — tidak ada yang disembunyikan.
  const [feedPage, setFeedPage] = useState(1);

  const isApprover = APPROVER_ROLES.has(role ?? "");

  // Demo statis (GitHub Pages): tidak ada backend yang bisa menyemai data, jadi
  // sesi demo hanya bisa dimuat dari panel di klien. Kalau tab Demo Control
  // dibatasi peran approver, akun Monitor BGN tidak punya jalan memuat sesi dan
  // banner menyuruh "minta Kepala SPPG" padahal tidak ada server. Karena itu di
  // mode NEXT_PUBLIC_USE_MOCK semua peran demo boleh membuka panel ini; perilaku
  // aplikasi ber-API (flag mati) tidak berubah.
  const DEMO_STATIS = process.env.NEXT_PUBLIC_USE_MOCK === "true";
  const bolehDemoControl = isApprover || (DEMO_STATIS && role !== null);

  // S4-03: envelope GET /kpi lewat React Query — satu potret per sesi (scope
  // ditentukan backend: SPPG own, monitor global). Loading dan galat dibaca dari
  // status query; tombol "Coba lagi" memanggil refetch().
  //
  // Pemilih periode (2026-10-16): jendela dimiliki HALAMAN, bukan komponen —
  // hook butuh nilainya untuk memuat rentang yang benar, dan komponen butuh
  // nilai yang sama untuk menandai pilihan aktif. Default: hari kalender berjalan.
  const [kpiWindow, setKpiWindow] = useState<KpiWindowKey>("today");
  // Cakupan data KPI (Fase 8): fakta kerja (bawaan) atau SATU sesi demo yang
  // eksplisit. Sesi demo aktif dicari lewat hook kecil; tanpa sesi, pilihan
  // "Simulasi" dimatikan dan tidak ada permintaan yang ditembak (server akan
  // menolak `include_demo=true` tanpa `demo_session_id`).
  const [kpiScope, setKpiScope] = useState<KpiScope>("operational");
  const demoSession = useDemoSessionId(token, tab === "kpi-kualitas" || tab === "today");
  const kpiQuery = useKpi(
    token,
    identityScope,
    tab,
    kpiWindow,
    kpiScope,
    demoSession.sessionId
  );
  // Angka pengadaan untuk tile Overview (27 Okt 2026): PO yang benar-benar
  // terbit, keputusan berjejak ACT, dan batch yang berangkat. Inilah yang
  // bergerak saat tombol Eksekusi ditekan — kartu pasokan di atasnya TIDAK,
  // karena stok baru bertambah ketika penerimaan disetujui.
  const procurementQuery = useProcurementSummary(token, identityScope, tab, "today");
  // Limbah + mitra pengolahan (18 Okt 2026): panel Surplus & Limbah dulu menulis
  // "—" karena tidak ada sumbernya. Sekarang dari server, dimuat hanya di tab itu.
  const wasteQuery = useWasteSummary(token, identityScope, tab);
  // Rencana alokasi surplus (20 Okt 2026): dihitung SERVER, lintas lokasi.
  // Panel lama merakit pasangannya dari /balance/map yang dibatasi cakupan peran,
  // sehingga selalu kosong untuk satu-satunya peran yang boleh membuka tab ini.
  const planQuery = useSurplusPlan(token, mapCommodity, tab);

  // Kalender agenda harian (langkah 2, 2026-10-16). Bulan & hari terpilih
  // dimiliki HALAMAN — bukan komponen — supaya rentang yang diminta ke
  // `GET /agenda` dan penanda "hari aktif" di layar tak pernah berbeda sumber.
  // Keduanya `null` sampai jam klien siap (pola `now` di atas) agar HTML server
  // dan render klien tidak berbeda; "hari ini" dihitung menurut WIB.
  const [agendaMonth, setAgendaMonth] = useState<{ year: number; month: number } | null>(
    null,
  );
  const [agendaDate, setAgendaDate] = useState<string | null>(null);
  const agendaDay = agendaDate ?? (now ? wibToday(now) : null);
  const agendaBulan = agendaMonth ?? (agendaDay ? monthOf(agendaDay) : null);
  const agendaRange = agendaBulan
    ? gridRange(monthGrid(agendaBulan.year, agendaBulan.month))
    : { start: "", end: "" };
  const agendaQuery = useAgenda(token, identityScope, tab, agendaRange);
  const agenda = agendaQuery.data ?? null;
  const agendaError = agendaErrorText(agendaQuery.error);

  // Pilih hari: bulan IKUT tanggal terpilih supaya rentang yang diminta ke
  // `GET /agenda` selalu memuat hari itu (rentang = grid bulan dari hari
  // terpilih, jadi setiap hari di bulan itu pasti masuk).
  const selectAgendaDate = (iso: string) => {
    setAgendaDate(iso);
    setAgendaMonth(monthOf(iso));
  };
  // Langkah HARI di kepala kartu Agenda harian (desain ulang 2026-10-17): grid
  // bulan besar dihapus, jadi ‹ › berarti sehari. `clampDayStep` menahan langkah
  // di tepi rentang data (lihat TodayDashboard: tombolnya jadi mati).
  const shiftAgendaDay = (delta: number) => {
    const dasar = agendaDay;
    if (!dasar) return;
    const tujuan = clampDayStep(dasar, delta, RANGE_MIN, RANGE_MAX);
    if (!tujuan) return;
    selectAgendaDate(tujuan);
  };

  // Popup pemilih tanggal (permintaan pemilik 2026-10-17). Kalender lama hanya
  // punya ‹ › dan judul bulan yang mati: melompat setahun = 12 klik. Bulan DRAFT
  // popup dimiliki HALAMAN (bukan komponen) karena rentang draft itulah yang
  // diminta ke `GET /agenda`; memilih tanggal baru mengubah hari & bulan yang
  // dipakai kartu. Rentang draft hanya diambil saat popup terbuka.
  const [agendaPickerOpen, setAgendaPickerOpen] = useState(false);
  const [agendaPickerMonth, setAgendaPickerMonth] = useState<{
    year: number;
    month: number;
  } | null>(null);
  // Jaring pengaman tipe: halaman hanya merender kalender saat bulan grid sudah
  // diketahui, jadi cabang "belum ada jam" ini praktis tak terpakai.
  const bulanDasar = agendaBulan ?? monthOf(agendaDay ?? "2026-10-16");
  const agendaPickerBulan = agendaPickerMonth ?? bulanDasar;
  const agendaPickerRange = agendaPickerBulan
    ? gridRange(monthGrid(agendaPickerBulan.year, agendaPickerBulan.month))
    : { start: "", end: "" };
  const agendaPickerQuery = useAgenda(
    token,
    identityScope,
    tab,
    agendaPickerRange,
    agendaPickerOpen
  );
  // Daftar TAHUN = tahun yang dicakup rentang data backend, ditambah tahun yang
  // sedang dibuka supaya <select> tak pernah menampilkan nilai di luar daftarnya.
  const agendaPickerYears = pickerYears(RANGE_MIN, RANGE_MAX, agendaPickerBulan.year);

  const openAgendaPicker = () => {
    setAgendaPickerMonth(null);
    setAgendaPickerOpen(true);
  };
  const closeAgendaPicker = () => {
    setAgendaPickerOpen(false);
    setAgendaPickerMonth(null);
  };
  const setAgendaPickerBulan = (bulan: { year: number; month: number }) => {
    setAgendaPickerMonth(bulan);
  };
  const shiftAgendaPickerMonth = (delta: number) => {
    setAgendaPickerMonth(shiftMonth(agendaPickerBulan.year, agendaPickerBulan.month, delta));
  };
  /** Pilih hari dari POPUP: hari + bulan ikut pindah, lalu popup ditutup. */
  const pickAgendaDate = (iso: string) => {
    if (!iso) return;
    selectAgendaDate(iso);
    setAgendaPickerOpen(false);
    setAgendaPickerMonth(null);
  };
  const kpi = kpiQuery.data;
  const kpiLoading = kpiQuery.loading;
  const kpiError = kpiQuery.error;

  // Turunan dari sampel: run agen (jejak + putusan verifikator) dan pasangan
  // pemasok. Dihitung dengan useMemo supaya tidak ada penulisan state di dalam
  // efek — satu arah data: query → turunan → tampilan.
  const byDecisionId = useMemo(
    () => new Map(decisions.map((d) => [d.decision_id, d])),
    [decisions]
  );
  const qualityRuns = useMemo<QualityRun[]>(
    () =>
      (sampleQuery.rows ?? []).map(({ decisionId, trace, summary }) =>
        runOf(byDecisionId.get(decisionId), trace, summary)
      ),
    [sampleQuery.rows, byDecisionId]
  );
  const qualityLoading = sampleQuery.loading;
  // Halaman Pemasok tidak lagi menurunkan daftarnya dari sampel keputusan —
  // sumbernya `GET /suppliers` (lihat suppliersQuery di atas).
  const supplierLoading = suppliersQuery.loading;
  const qualityError = sampleQuery.error;
  const supplierError = suppliersQuery.error;

  // Register eksklusi punya siklus muat SENDIRI. Dulu ia diambil di dalam efek
  // sampel di atas, yang ber-penjaga "sampel sudah dinilai" (evaluatedKey):
  // membuka tab Pemasok SETELAH tab Kualitas Agen karena itu tidak pernah
  // memanggil /supplier-exclusions, dan kartu register sempat mengklaim "tidak
  // ada eksklusi" padahal datanya belum dimuat.

  const evaluatedCount = Math.min(decisions.length, EVALUATED_LIMIT);

  // Jam klien untuk label sisa waktu ("45 mnt lagi"): baru diisi setelah
  // mount supaya HTML server dan render klien sepakat, lalu diperbarui.
  useEffect(() => {
    setNow(new Date());
    const iv = setInterval(() => setNow(new Date()), 30000);
    return () => clearInterval(iv);
  }, []);



  async function onLogin(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      const data = await login(email, password);
      setToken(data.access_token);
      // Role dari JWT hanya untuk display; otorisasi tetap di backend.
      setRole(decodeRole(data.access_token));
      // Simpan agar refresh halaman tidak memaksa login ulang (2026-10-16).
      try {
        window.localStorage.setItem(TOKEN_STORAGE_KEY, data.access_token);
      } catch {
        // localStorage diblokir: sesi tetap jalan di memori untuk tab ini.
      }
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
    // 29 Okt 2026: blok akun demo dihapus dari login (permintaan pemilik).
    // Halaman publik hanya memuat form email + sandi; tidak ada label peran
    // yang dicetak dan tidak ada panggilan ke endpoint demo.
    return (
      <main className="login-shell">
        {/* Panel brand: dunia subject — rantai dingin SPPG, angka dari data demo asli */}
        <section className="login-brand" aria-label="Tentang MealChain Guardian">
          <p className="brand-eyebrow">Badan Gizi Nasional · Program SPPG</p>
          <h1 className="brand-title">MealChain Guardian</h1>
          <p className="brand-tagline">
            Agentic AI for Indonesia’s Digital Public Infrastructure for Food
            Supply Balancing, Safety & Swasembada Pangan
          </p>
        </section>

        <section className="login-panel">
          <form onSubmit={onLogin} className="login-form">
            <h2>Masuk ke konsol</h2>
            <p className="login-sub">Gunakan akun SPPG atau BGN yang terdaftar.</p>
            <ValidatedField
              label="Email"
              type="email"
              value={email}
              onChange={setEmail}
              autoComplete="username"
              pesan={{
                kosong: "Isi email dulu.",
                salahFormat: "Format email belum benar — contoh: nama@demo.local.",
              }}
            />
            <ValidatedField
              label="Password"
              type="password"
              value={password}
              onChange={setPassword}
              autoComplete="current-password"
              // type="password" tidak punya batasan format, jadi kedua keadaan
              // berbunyi sama — dan memang itu yang benar untuk pengguna.
              pesan={{ kosong: "Isi password dulu.", salahFormat: "Isi password dulu." }}
            />
            {loginError && (
              <p className="status-danger login-error" role="alert">
                {loginError}
              </p>
            )}
            <button className="button login-submit" type="submit" disabled={submitting}>
              {submitting ? "Memeriksa…" : "Masuk"}
            </button>
          </form>
        </section>
      </main>
    );
  }

  // Fase 9 butir 3: daftar `GET /decisions` tidak membawa `commercial_cost`;
  // biaya hanya ada di `GET /decisions/{id}` (hook detail). Tanpa penggabungan
  // ini blok biaya di layar selalu "tidak berlaku" walaupun server punya angka.
  const selectedBaris = decisions.find((d) => d.decision_id === selectedId) ?? null;
  const selected = withDetailCost(selectedBaris, detail.decision);
  // Turunan data peta untuk banner + judul (dipakai tab Overview).
  const mapShortage: any[] = (mapData?.locations ?? []).filter(
    (l: any) => l.status === "shortage"
  );
  const mapSurplus: any[] = (mapData?.locations ?? []).filter(
    (l: any) => l.status === "surplus"
  );
  // Fase 2 (bento Overview): angka hero, pangsa pasokan, dan antrean keputusan.
  // TANPA hook — di bawah early-return layar login tidak boleh ada hook baru
  // (lihat catatan feed di bawah); semuanya fungsi murni lib/overview-bento
  // dan lib/topbar yang nilainya kecil.
  const hero = heroGap(mapData?.locations ?? [], activeLocation);
  const heroShare = gapShareOfDemand(hero.gapKg, hero.demandKg);
  const networkTotal = networkTotals(mapData?.locations ?? []);
  // Tanggal data yang BENAR-BENAR dipakai peta (dari `*_recorded_at`), supaya
  // angka "pasokan terpantau" tidak dibaca sebagai kondisi hari ini ketika
  // pasokan dan permintaan berasal dari tanggal berbeda.
  const mapSnapshotNote = snapshotNote(mapData?.locations ?? []);
  const coveragePct = demandCoveragePct(
    networkTotal.supplyKg,
    networkTotal.demandKg
  );
  // Antrean keputusan memakai sumber yang SAMA dengan lonceng top bar supaya
  // kedua tempat tidak pernah menampilkan angka berbeda. Peran WAJIB ikut:
  // `proposed` adalah pekerjaan Kepala SPPG (ia yang menekan "Ajukan"), jadi
  // tanpa peran angka di sini 16 sementara lonceng menulis 24 — dua angka
  // untuk hal yang sama (temuan audit 19 Okt 2026).
  //
  // 28 Okt 2026 (permintaan Roy): kartu antrean DIPANGKAS SETENGAH — dua baris,
  // bukan empat — supaya kolom kanan tidak lagi dikuasai satu daftar; sisa
  // tingginya dipakai kartu "Jejak kepercayaan". Batas ini juga dipakai tile
  // "Rekomendasi menunggu" (`pendingKpiCopy`) supaya kalimat "+N lain menunggu
  // tindakan" di tile dan di kaki antrean tidak pernah berbeda angka.
  const notif = notifList(decisions, QUEUE_SHOWN, role);
  const kpiAntrean = pendingKpiCopy({
    total: notif.total,
    monitored: decisions.length,
    limit: QUEUE_SHOWN,
    loading: decisionsQuery.isLoading,
    expired: notif.expired,
  });
  // Empat bukti di kartu "Jejak kepercayaan": ledger, batch, eksekusi, node.
  // Dihitung di lib/trust-trail (murni, diuji) — halaman tidak menghitung ulang.
  const trust = trustTrail({
    ledger,
    batches,
    decisions,
    locations: mapData?.locations ?? [],
  });
  const roleLabel = ROLE_LABEL[role ?? ""] ?? (role ?? "user");

  // Feed traceable (arah Roy 2026-10-09): EXPIRED TIDAK disembunyikan — semua
  // status tetap muncul sebagai chip + angka. Chip, penyaring, dan urutan
  // dihitung lib/decision-feed (label bahasa manusia, "Perlu tindakan" dulu).
  // Tanpa useMemo: nilainya kecil (126 baris) dan di bawah ini tidak boleh ada
  // hook baru — komponen sudah punya early return untuk layar login.
  const feedFilter = { scope: feedScope, query: feedQuery };
  const feedChipList = feedChips(feedWindowDecisions);
  const feedRows = sortFeed(
    feedVisible(feedWindowDecisions, feedFilter),
    feedSort,
    now
  );
  const feedTotal = feedRows.length;
  const feedPageData = paginate(feedRows, feedPage, FEED_PAGE_SIZE);
  const feedCards = feedPageData.items;
  const feedFilterActive = hasActiveFilter(feedFilter);
  // Keputusan yang menunggu tindakan manusia — satu definisi dengan lonceng
  // notifikasi top bar (dulu dihitung sendiri di sini dari statusCounts).
  // Hanya yang MASIH bisa ditindak (backend menolak tindakan atas keputusan
  // lewat tenggat dengan 409); tunggakannya dilaporkan terpisah supaya angkanya
  // jujur tanpa menyembunyikan apa pun (temuan QA F1).
  // Audit M7: `proposed` hanya pekerjaan Kepala SPPG (hanya dia yang bisa
  // menekan "Ajukan"), jadi hitungan per peran — Ahli Gizi tidak dibuat
  // mengejar pekerjaan yang tombolnya tidak ada untuknya.
  const perluKeputusan = countActionable(decisions, undefined, role);
  const lewatTenggat = countExpiredActionable(decisions, undefined, role);
  const drafLewat = countDraftActionable(decisions, undefined, role);
  // Angka untuk kepala tab Recommendations: HARUS sejendela dengan daftar di
  // bawahnya, kalau tidak "21 perlu tindakan" bertengger di atas daftar 27
  // baris "hari ini". Badge sidebar tetap memakai angka seluruh riwayat.
  // 29 Okt 2026: pil "N perlu tindakan" di kepala halaman dilepas karena chip
  // saring "Perlu tindakan N" 20 px di bawahnya menulis angka yang sama (dan
  // chip itu juga bisa diklik). Sisa hitungan jendela = yang lewat tenggat,
  // satu-satunya keadaan yang tidak punya chip.
  const lewatTenggatJendela = countExpiredActionable(
    feedWindowDecisions,
    undefined,
    role
  );

  // PRD 2.4: nav 5 tab (overview/kpi/recommendations/agent-log/demo-control)
  // + tab "Hari Ini" (permintaan Roy 2026-10-11) sebagai halaman pertama;
  // demo-control approver-only; agent-log semua role (monitor read-only justru
  // butuh observability).
  // Urutan mengikuti sidebar acuan (HackathonBil/MealchainGuardian): Hari Ini →
  // Overview → Keputusan → Decision & Evidence → Keamanan Pangan → Surplus &
  // Limbah → Pemasok → Agent Log → KPI & Kualitas Agen (tab gabungan sejak
  // 2026-10-15). Halaman yang di acuan
  // dibatasi peran (Surplus & Limbah = peran SPPG) ikut dibatasi di sini.
  const navItems: {
    id: NavId;
    label: string;
    /** Keterangan tambahan saat kursor berhenti di tab (mis. arti angkanya). */
    title?: string;
    roles?: string[];
  }[] = [
    { id: "today", label: "Today" },
    { id: "overview", label: "Overview" },
    // Dokumen 03 §3/§5 (28 Okt 2026): halaman gabungan jaringan + pasokan &
    // permintaan satu lokasi. Untuk nutritionist — yang menurut §5 tidak
    // memakai pandangan jaringan — nama tabnya menyebut pekerjaannya sendiri,
    // bukan "Location Network": ia membuka halaman ini untuk membaca kecukupan
    // gizi satu lokasi, dan tombol lokasinya tetap ada di dalamnya.
    {
      id: "location-network",
      label: locationNetworkTitle(role),
      title: locationNetworkHint(role),
    },
    {
      // Angka = jumlah yang PERLU DI-APPROVE, bukan seluruh keputusan yang
      // pernah dibuat (dulu 126 dan sulit ditafsirkan).
      id: "recommendations",
      label: `Recommendations${perluKeputusan ? ` (${perluKeputusan})` : ""}`,
      // Angka = yang MASIH bisa ditindak; tunggakan yang lewat tenggat tetap
      // disebut supaya tidak hilang dari pandangan (temuan QA F1). Draf usulan
      // kedaluwarsa dilaporkan terpisah: ia bukan pekerjaan yang bisa
      // diselesaikan, hanya usulan lama yang tidak pernah dimajukan.
      title: perluKeputusan
        ? `${perluKeputusan} recommendations need action${lewatTenggat ? ` · ${lewatTenggat} past due` : ""}${drafLewat ? ` · ${drafLewat} expired drafts` : ""}`
        : lewatTenggat
          ? `Nothing actionable · ${lewatTenggat} past due`
          : drafLewat
            ? `Nothing actionable · ${drafLewat} expired drafts`
            : "No recommendations need action",
    },
    { id: "evidence", label: PAGE_TITLES.evidence },
    { id: "safety", label: PAGE_TITLES.safety },
    { id: "suppliers", label: PAGE_TITLES.suppliers },
    { id: "agent-log", label: PAGE_TITLES.agentLog },
    { id: "kpi-kualitas", label: "Performance & Audit" },
    { id: "settings", label: PAGE_TITLES.settings, roles: Array.from(MANAGE_ROLES) },
    ...(bolehDemoControl
      ? [{ id: "demo-control" as const, label: "Demo Control" }]
      : []),
  ];
  const visibleNavItems = navItems.filter(
    (item) => !item.roles || (role !== null && item.roles.includes(role))
  );

  // Inisial avatar (rail + top bar) — satu sumber di lib/topbar.ts supaya
  // tidak ada dua cara menghitung yang bisa menyimpang.
  const initials = initialsOf(me?.email ?? email, roleLabel);

  const onLogout = () => {
    setToken(null);
    setRole(null);
    // Hapus sesi tersimpan: logout harus benar-benar mengakhiri sesi, bukan
    // hanya menyembunyikannya sampai refresh berikutnya.
    try {
      window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    } catch {
      // localStorage diblokir: tidak ada yang perlu dibersihkan.
    }
    setSelectedId(null);
    setTab("overview");
    // Bersihkan data konsol: akun berikutnya tidak boleh sempat melihat angka
    // sesi sebelumnya sebelum permintaan barunya selesai (terlihat saat uji
    // skeleton: strip KPI sempat menampilkan nilai lama).
    setActiveLocation(null);
    // Cache React Query dibersihkan seluruhnya: akun berikutnya tidak boleh
    // sempat melihat keputusan/batch/KPI sesi sebelumnya (dulu dibersihkan
    // manual satu per satu).
    queryClient.clear();
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
          <span className="side-brand-text">
            <strong>MealChain Guardian</strong>
          </span>
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
        <SideNav
          items={visibleNavItems}
          active={tab}
          collapsed={sideCollapsed}
          onSelect={(id) => {
            setTab(id);
            // Halaman bukti tidak boleh terbuka kosong: begitu tabnya ditekan,
            // keputusan yang butuh tindakan langsung dipilih.
            if (id === "evidence" && !selectedId) {
              const fallback = defaultEvidenceId(decisions, now);
              if (fallback) setSelectedId(fallback);
            }
            // P4: tab Agent Log tidak boleh terbuka pada keputusan yang tidak
            // punya review 7 agen — pilih keputusan terbaru yang punya.
            if (id === "agent-log") {
              const berikut = defaultAgentLogId(decisions, selectedId);
              if (berikut && berikut !== selectedId) setSelectedId(berikut);
            }
          }}
        />
        <div className="side-user">
          <span className="side-avatar" aria-hidden="true">
            {initials}
          </span>
          <span className="side-user-meta">
            <span className="side-user-name">{roleLabel}</span>
            <span className="side-user-sub">{me?.email || email || "Sesi demo"}</span>
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
          onOpenNotifications={() => setTab("recommendations")}
          onLogout={onLogout}
        />
        <div className="app-body">
        {/* Petunjuk global bahwa data memang sengaja kosong (sesi demo). */}
        <DemoSessionBanner
          token={token}
          bolehBuka={bolehDemoControl}
          onOpenDemoControl={() => setTab("demo-control")}
        />
        {tab === "today" && (
          /* Langkah 3 (permintaan Roy 2026-10-11): rekap operasional hari
             berjalan. Semua angka dari API — keputusan menunggu tindakan,
             batch mendekati kedaluwarsa, lokasi shortage, KPI 24 jam, dan
             status rantai audit. Klik baris membawa ke halaman terkait. */
          <TodayDashboard
            decisions={decisions}
            batches={batchesHariIni}
            locations={mapData?.locations ?? []}
            commodity={mapData?.commodity ?? mapCommodity}
            kpi={kpi}
            ledger={ledger}
            now={now}
            agenda={agenda}
            agendaLoading={agendaQuery.isLoading}
            agendaError={agendaError}
            agendaDate={agendaDay ?? undefined}
            agendaToday={now ? wibToday(now) : undefined}
            agendaMonth={agendaBulan ?? undefined}
            agendaPicker={{
              open: agendaPickerOpen,
              month: agendaPickerBulan,
              years: agendaPickerYears,
              agenda: agendaPickerQuery.data ?? null,
              loading: agendaPickerQuery.isLoading,
              error: agendaErrorText(agendaPickerQuery.error),
              today: now ? wibToday(now) : undefined,
              selected: agendaDay ?? "",
              onOpen: openAgendaPicker,
              onClose: closeAgendaPicker,
              onShiftMonth: shiftAgendaPickerMonth,
              onSetMonth: setAgendaPickerBulan,
              onSelect: pickAgendaDate,
              onToday: () => pickAgendaDate(agendaDay ?? ""),
              onRetry: () => void agendaPickerQuery.refetch(),
            }}
            onAgendaSelect={selectAgendaDate}
            onAgendaShiftDay={shiftAgendaDay}
            onAgendaRetry={() => void agendaQuery.refetch()}
            greetingName={roleLabel}
            batchesLoading={batchesLoading}
            batchesError={batchesError}
            onRetry={() => void todayQuery.refetch()}
            onOpenDecision={(decisionId) => {
              setSelectedId(decisionId);
              setTab("recommendations");
            }}
            onOpenAllDecisions={() => setTab("recommendations")}
            onOpenBatches={() => setTab("safety")}
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
            <PageHeader
              id="ov-ringkas"
              className="jump-target"
              ariaLabel="Ringkasan peta pasokan"
              title="Overview Pasokan & Distribusi"
              description={
                mapData
                  ? mapHeaderSubtitle((mapData.locations ?? []).length)
                  : "Memuat kondisi pasokan semua lokasi SPPG…"
              }
              meta={
                <>
                  <span
                    className="overview-demo-chip"
                    title="Data contoh untuk demo, bukan data operasional produksi"
                  >
                    Data simulasi
                  </span>
                  <span className="overview-live-pill" title="Diperbarui setiap 5 detik">
                    <span className="overview-live-dot" aria-hidden="true" />
                    Sinkron otomatis
                  </span>
                  {mapUpdatedAt !== null && (
                    <span className="overview-updated" aria-live="polite">
                      {syncLabel(mapUpdatedAt)}
                    </span>
                  )}
                </>
              }
            />

            {/* Navigasi bagian (komponen bersama): Overview delapan blok dalam
                satu gulungan — peta, kiriman, kecukupan, telemetri. Daftarnya
                dari lib/section-jump (bukan tautan yang ditulis ulang di sini),
                dan tujuan kiriman hanya muncul kalau kartunya memang dirender. */}
            <SectionJump
              items={overviewSections({ isApprover })}
              ariaLabel="Bagian halaman Overview"
            />

            {/* Strip bento (Fase 2, Arah 4): tile hero selisih pasokan + dua
                pendamping dengan bobot berbeda. Semua angka dari data peta
                real; yang belum tersedia ditulis "—" (lib/overview-bento),
                bukan 0. */}
            <section
              className="overview-kpis"
              aria-label="KPI ringkas"
              aria-busy={!mapData && !mapError}
            >
              <div className="kpi-card kpi-card-hero">
                <span className="kpi-card-label">
                  {hero.scope === "location"
                    ? `Selisih pasokan ${hero.name}`
                    : "Selisih pasokan jaringan"}
                </span>
                <span
                  className={`kpi-card-value kpi-card-hero-value is-${hero.tone}`}
                >
                  {mapData ? (
                    formatSignedKg(hero.gapKg)
                  ) : (
                    <span className="skeleton skeleton-value" aria-hidden="true" />
                  )}
                </span>
                <span className="kpi-card-foot">
                  {!mapData
                    ? "menunggu data peta"
                    : heroShare !== null
                      ? `${hero.gapKg !== null && hero.gapKg > 0 ? "lebih" : "kurang"} ${heroShare}% dari kebutuhan`
                      : hero.tone === "balanced"
                        ? "pasokan menutup kebutuhan"
                        : "kebutuhan belum tercatat di data"}
                </span>
                <span className="kpi-card-mini">
                  {mapData
                    ? `${mapSurplus.length} lokasi surplus · ${mapShortage.length} shortage · ${(mapData.locations ?? []).length} terpetakan`
                    : "—"}
                </span>
              </div>

              <div className="kpi-card kpi-card-pasokan">
                <span className="kpi-card-label">Pasokan terpantau</span>
                <span className="kpi-card-value">
                  {mapData ? (
                    formatKg(networkTotal.supplyKg)
                  ) : (
                    <span className="skeleton skeleton-value" aria-hidden="true" />
                  )}
                </span>
                <span className="kpi-card-foot">
                  {coveragePct !== null && networkTotal.demandKg !== null
                    ? `dari ${formatKg(networkTotal.demandKg)} kebutuhan jaringan · ${coveragePct}%`
                    : "kebutuhan jaringan belum lengkap"}
                </span>
                {mapSnapshotNote ? (
                  <span className="kpi-card-mini kpi-card-snapshot">
                    {mapSnapshotNote}
                  </span>
                ) : null}
                <span className="bento-bar" aria-hidden="true">
                  <span
                    className="bento-bar-fill"
                    style={{ width: `${Math.min(coveragePct ?? 0, 100)}%` }}
                  />
                </span>
              </div>

              <div className="kpi-card kpi-card-keputusan">
                <span className="kpi-card-label">Rekomendasi menunggu</span>
                {/* Selama daftar keputusan belum tiba, "0" adalah klaim palsu:
                    pembaca mengira tidak ada pekerjaan. Tampilkan "—". */}
                <span className="kpi-card-value">{kpiAntrean.value}</span>
                <span className="kpi-card-foot">{kpiAntrean.foot}</span>
                <span className="kpi-card-mini">{kpiAntrean.mini}</span>
              </div>
            </section>

            {/* Tile pengadaan (27 Okt 2026): tiga angka yang BENAR-BENAR bergerak
                saat pengadaan dieksekusi — PO terbit + nilai komitmen (dari
                `sap_mock_purchase_orders`), keputusan berjejak ACT, dan batch
                yang berangkat. Tanpa ini satu-satunya angka Overview yang
                berubah saat eksekusi adalah hitungan antrean, sehingga laporan
                "Overview tidak berubah" memang benar. Nilai tak diketahui
                ditulis "—"; periode kosong ditulis "belum ada". */}
            <ProcurementToday
              data={procurementQuery.data}
              loading={procurementQuery.loading}
              error={procurementQuery.error}
            />

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
                  <strong>{mapShortage.length} lokasi shortage</strong> pada{" "}
                  {mapData?.commodity ?? mapCommodity} —{" "}
                  {mapShortage.map((l: any) => l.location).join(", ")}. Tinjau
                  rekomendasi agen untuk alokasi ulang.
                </p>
                <button
                  type="button"
                  className="overview-alert-action"
                  onClick={() => setTab("recommendations")}
                >
                  Tinjau rekomendasi
                </button>
              </div>
            )}

            {/* Filter pill komoditas di dalam kartu (acuan: kartu filter) */}
            <div
              className="commodity-filters"
              role="group"
              aria-label="Komoditas peta"
            >
              <span className="commodity-filters-label">Komoditas:</span>
              {COMMODITIES.map((c) => (
                <button
                  key={c}
                  data-komoditas={c}
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
                    onClick={() => void mapQuery.refetch()}
                  >
                    Coba lagi
                  </button>
                </p>
              )}
            </div>

            {/* Peta gaya acuan (arah Roy 2026-10-11): kanvas terang apa adanya,
                legenda putih kiri-bawah, kontrol MapLibre (zoom + kompas)
                kanan-atas & atribusi kanan-bawah. Tanpa kepala/kaki panel.
                Layout: peta (kiri) + tabel Pasokan per Lokasi (kanan);
                Telemetri Node di bawah peta. */}
            <section
              className="overview-split jump-target"
              id="overview-map"
              aria-label="Peta dan pasokan per lokasi"
            >
              <SupplyMap
                locations={mapData?.locations ?? []}
                commodity={mapData?.commodity}
                activeLocation={activeLocation}
                loading={!mapData && !mapError}
                showStatusList={false}
                showHeader={false}
                suppliers={mapSuppliersQuery.data}
                supplierRoutes={mapSupplierRoutesQuery.data}
                reachKm={supplierReachKm}
                focusedRouteId={focusedRoute}
                onFocusRoute={setFocusedRoute}
              />
              <div className="overview-side">
                {/* Antrean keputusan (Fase 2): 4 teratas + tunggakan dinyatakan
                    apa adanya. Sumber sama dengan lonceng top bar
                    (lib/topbar.notifList) supaya angkanya tidak pernah beda. */}
                <section
                  className="map-panel queue-card"
                  aria-label="Perlu keputusan"
                >
                  <div className="queue-head">
                    <h3>Perlu keputusan</h3>
                    <span className="queue-head-count">{kpiAntrean.value}</span>
                  </div>
                  {notif.shown.length === 0 ? (
                    <p className="queue-empty">
                      {kpiAntrean.value === "—"
                        ? "Belum ada data keputusan untuk ditampilkan."
                        : "Tidak ada keputusan yang menunggu tindakan."}
                    </p>
                  ) : (
                    <ul className="queue-list">
                      {notif.shown.map((item, index) => (
                        <li
                          key={
                            item.decision_id ??
                            `${item.decision_type}-${item.created_at}-${index}`
                          }
                          className="queue-item"
                        >
                          <button
                            type="button"
                            className="queue-item-action"
                            onClick={(event) => {
                              if (item.decision_id) {
                                // 28 Okt 2026: detail & jejak agen jadi popup —
                                // antrean di bawahnya tidak hilang saat dibuka.
                                bukaPopupKeputusan(item.decision_id, event.currentTarget);
                              } else {
                                setTab("recommendations");
                              }
                            }}
                            aria-label={`Tinjau ${DECISION_TYPE_LABELS[item.decision_type ?? ""] ?? "rekomendasi baru"}`}
                          >
                            <span className="queue-item-main">
                              <span className="queue-item-label">
                                {DECISION_TYPE_LABELS[item.decision_type ?? ""] ??
                                  "Rekomendasi baru"}
                              </span>
                              <span className="queue-item-meta">
                                {queueQuantityLabel(item.quantity_kg)} ·{" "}
                                {formatDateTime(item.created_at)}
                              </span>
                            </span>
                            {item.status && <StatusBadge status={item.status} />}
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                  {notif.rest > 0 && (
                    <p className="queue-rest">
                      +{notif.rest} keputusan lain menunggu tindakan
                    </p>
                  )}
                  {notif.expired > 0 && (
                    <p className="queue-rest">
                      +{notif.expired} lewat tenggat — tidak bisa ditindak lagi
                    </p>
                  )}
                  <div className="queue-foot">
                    <button
                      type="button"
                      className="queue-open"
                      onClick={() => setTab("recommendations")}
                    >
                      Lihat semua rekomendasi
                    </button>
                  </div>
                </section>
                {/* Bukti di bawah antrean (28 Okt 2026): antrean hanya
                    bercerita tentang pekerjaan yang BELUM selesai; kartu ini
                    menjawab "kenapa angka di halaman ini bisa dipercaya". */}
                <TrustTrailCard metrics={trust} />
              </div>
            </section>

            {/* Grafik kecukupan + surplus wilayah lain (28 Okt 2026): DUA SISI
                satu neraca dalam satu baris. Kiri = apakah lokasi ini cukup
                (empat komoditas; BGN nasional memakai grafik lintas lokasi).
                Kanan = di WILAYAH mana surplusnya berada. Kolom kanan wajib
                dari server: peta akun SPPG hanya memuat lokasinya sendiri
                (Ruling 2026-10-14), jadi "daerah lain" tidak ada di data klien.
                Diletakkan TEPAT di bawah peta + antrean: ini lapisan "scan"
                sebelum detail kiriman. */}
            <div className="jump-target ov-pasokan-grid" id="ov-kecukupan">
              {/* Bentuk kartu: BAR VERTIKAL ringkas (28 Okt 2026, permintaan
                  pemilik). SupplyAdequacyChart & SupplyBalanceChart TETAP ada di
                  repo dan tetap diuji sendiri; yang dilepas hanya pemasangan di
                  slot ini — sama seperti ShipmentCard saat Monitor harga masuk. */}
              <AdequacyColumns
                mode={pakaiGrafikKecukupan ? "commodity" : "location"}
                rows={pakaiGrafikKecukupan ? adequacyRows : undefined}
                locations={pakaiGrafikKecukupan ? undefined : mapData?.locations ?? []}
                commodity={mapData?.commodity ?? mapCommodity}
                role={role}
                locationName={activeLocation ?? me?.location_name ?? "SPPG"}
                updatedAt={
                  pakaiGrafikKecukupan ? commodityBalance.updatedAt : mapUpdatedAt
                }
                sourceNote={
                  pakaiGrafikKecukupan ? snapshotNote(mapData?.locations ?? []) : null
                }
                now={now}
                loading={
                  pakaiGrafikKecukupan
                    ? !grafikKecukupanError &&
                      (commodityBalance.isLoading || batches === null)
                    : !mapData && !mapError
                }
                error={pakaiGrafikKecukupan ? grafikKecukupanError : mapError}
                onRetry={
                  pakaiGrafikKecukupan
                    ? () => {
                        void commodityBalance.refetch();
                        void todayQuery.refetch();
                      }
                    : () => void mapQuery.refetch()
                }
                onSelect={
                  pakaiGrafikKecukupan
                    ? (commodity) => {
                        setMapCommodity(commodity);
                        // "auto", bukan "smooth": gulir halus membuat kontainer peta
                        // berubah ukuran terus-menerus dan MapLibre melempar error
                        // (terbukti 20 Okt 2026). Lompat sekali = peta tetap hidup.
                        document
                          .getElementById("overview-map")
                          ?.scrollIntoView({ behavior: "auto", block: "center" });
                      }
                    : undefined
                }
              />
              <SurplusRegionPanel
                payload={surplusRegions.data}
                commodities={komoditasSurplus}
                locationName={
                  bgnNasional ? "seluruh jaringan" : lokasiPanel ?? "SPPG"
                }
                sourceNote={snapshotNote(mapData?.locations ?? [])}
                updatedAt={surplusRegions.updatedAt}
                loading={surplusRegions.loading && !surplusRegions.error}
                error={surplusRegions.error}
                onRetry={() => void surplusRegions.refetch()}
              />
            </div>

            {/* Monitor harga komoditas (28 Okt 2026) — menggantikan kartu
                "Informasi pengiriman" (ShipmentCard), "Telemetri Node", dan
                daftar "Status Lokasi" di tab ini. Ketiga komponennya TETAP ada
                di repo dan tetap diuji sendiri; yang dilepas hanya pemasangan
                di Overview. Isi kiriman masih terbaca di tab Pemasok
                (ShipmentBoard) dan jalur persetujuan di Decision & Evidence. */}
            <div className="jump-target" id="ov-harga">
              <PriceMonitor
                token={token}
                activeLocation={activeLocation}
                lokasiSendiri={me?.location_name ?? null}
              />
            </div>
          </div>
        )}


        {tab === "settings" && <SettingsPanel token={token} />}

        {tab === "demo-control" && bolehDemoControl && (
          /* Demo Control sederhana (keputusan Roy 2026-10-19): tiga blok —
             siapkan data, jalankan agent, bukti. OpsConsole/ChaosPanel (Event
             1/2/3) sengaja dilepas dari tab ini: panel demo dipakai untuk
             MEMBUKTIKAN agent berjalan, bukan untuk memilih skenario.
             Komponen keduanya tetap ada di repo dan tetap diuji sendiri. */
          <>
            <PageHeader
              title="Demo Control"
              wideDescription
              className="page-header-space-right"
              description="Satu tombol menjalankan agent sungguhan (bukan tiruan) untuk komoditas yang Anda pilih: yang dinilai adalah pemasok yang sudah memasok SPPG Anda (stok batch, penawaran harga, jarak pemasok → SPPG). Bukti putaran itu dibaca ulang dari database — langkah yang tercatat, provider yang benar-benar menjawab, dan status keputusan."
            />
            <DemoControlPanel
              token={token}
              // Demo statis tidak punya backend yang bisa dilindungi RBAC, dan
              // panel ini satu-satunya jalan memuat sesi demo. Karena itu di
              // mode mock panel diberi peran Kepala SPPG supaya tombol "Muat
              // Demo"/"Jalankan agent" hidup untuk akun demo mana pun; di
              // aplikasi ber-API nilainya tetap peran sebenarnya.
              role={DEMO_STATIS ? "sppg_head" : role ?? "sppg_head"}
              locationName={me?.location_name ?? null}
              onOpenDecision={bukaKeputusanDariPO}
              onOpenAgentLog={() => setTab("agent-log")}
            />
          </>
        )}

        {tab === "recommendations" && (
          <>
            <section>
              <PageHeader
                title="Recommendation Feed"
                // Satu kalimat (29 Okt 2026). Versi sebelumnya 259 karakter dan
                // mengulang tiga hal yang sudah tertulis di kontrol di bawahnya:
                // urutan bawaan (pemilih Urutkan), kata "tinjau" (tombol kartu),
                // dan bahwa halaman Decision & Evidence memuat versi lengkap
                // (tautan di dalam popup). Penjelasan panjang di atas daftar
                // membuat 10 kartu pertama terdorong ke bawah layar.
                description="Satu kartu satu keputusan agen; yang bisa ditindaklanjuti ada di atas."
                meta={
                  <>
                    {lewatTenggatJendela > 0 && (
                      <span className="commodity-pill">
                        {lewatTenggatJendela} lewat tenggat
                      </span>
                    )}
                    <span className="commodity-pill">
                      {feedWindowDecisions.length} rekomendasi ·{" "}
                      {feedWindowLabel(feedWindow).toLowerCase()}
                    </span>
                  </>
                }
              />
              {error && (
                <p className="status-danger" role="alert">
                  Gagal memuat data: {error}{" "}
                  <button
                    type="button"
                    onClick={() => void decisionsQuery.refetch()}
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

              {decisions.length > 0 && (
                <>
                  {/* Petunjuk "Tekan Tinjau…" DIHAPUS 29 Okt 2026: tombolnya
                      sudah ada di setiap kartu dengan nama yang sama, dan
                      kalimatnya (164 karakter) mengulang isi popup — rincian,
                      bukti, persetujuan, serta tautan ke Decision & Evidence.
                      Keterangan yang sama sekarang menempel sebagai `title`
                      pada tombol Tinjau, jadi tetap terbaca saat kursor
                      berhenti di tombol tanpa memakan dua baris di atas
                      daftar. */}

                  {/* Cari + urutkan: sebelumnya tidak ada sama sekali, jadi 126
                      kartu hanya bisa dipindai satu per satu. */}
                  {/* Tahap 1 (30 Okt 2026): EMPAT baris kendali disatukan
                      jadi satu pita — pencarian+urutan, pemilih periode, chip
                      status, dan baris hitungan. Sebelumnya tiap blok membawa
                      margin sendiri (12+12+24+12 px) sehingga sepuluh kartu
                      pertama terdorong ke bawah lipatan layar. Urutan DOM
                      tidak berubah, jadi urutan Tab dan pembaca layar tetap
                      sama seperti sebelumnya. */}
                  <div className="feed-kendali">
                    <div className="feed-toolbar">
                      <div className="feed-field feed-field-search">
                        <label htmlFor="feed-search">Cari rekomendasi</label>
                        <input
                          id="feed-search"
                          type="search"
                          value={feedQuery}
                          placeholder="Jenis, status, komoditas, atau ID keputusan…"
                          onChange={(e) => {
                            setFeedQuery(e.target.value);
                            setFeedPage(1);
                          }}
                        />
                      </div>
                      <div className="feed-field feed-field-sort">
                        <label htmlFor="feed-sort">Urutkan</label>
                        <select
                          id="feed-sort"
                          value={feedSort}
                          onChange={(e) => {
                            setFeedSort(e.target.value as FeedSort);
                            setFeedPage(1);
                          }}
                        >
                          {(["urgency", "due", "newest"] as FeedSort[]).map((mode) => (
                            <option key={mode} value={mode}>
                              {FEED_SORT_LABELS[mode]}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>

                    {/* Pemilih periode (permintaan pemilik 24 Okt 2026).
                        Memakai kontrol yang SAMA dengan pemilih periode KPI
                        (`.kpi-period` + `.commodity-pill` + `aria-pressed`)
                        supaya dua tempat tidak punya bahasa visual berbeda.
                        Tombol asli, bukan div: bisa Tab + Enter, dan keadaan
                        aktif diumumkan ke pembaca layar — bukan hanya warna. */}
                    <div
                      className="kpi-period feed-period"
                      role="group"
                      aria-label="Periode rekomendasi"
                    >
                      <span className="kpi-period-label">Periode:</span>
                      {FEED_WINDOWS.map((w) => {
                        const aktif = w.key === feedWindow;
                        return (
                          <button
                            key={w.key}
                            type="button"
                            className={`commodity-pill kpi-period-pill${
                              aktif ? " is-active" : ""
                            }`}
                            data-window={w.key}
                            aria-pressed={aktif}
                            title={w.hint}
                            onClick={() => {
                              setFeedWindow(w.key);
                              setFeedPage(1);
                            }}
                          >
                            {w.label}
                          </button>
                        );
                      })}
                      {/* Petunjuk hanya bila menambah arti (29 Okt 2026): untuk
                          "7 hari" ia berbunyi "7 hari terakhir" — kalimat yang
                          sama dua kali, dan di layar terbaca seperti chip keempat
                          yang tidak bisa ditekan. */}
                      {feedWindowHintBilaBerbeda(feedWindow) && (
                        <span className="feed-period-hint">
                          {feedWindowHintBilaBerbeda(feedWindow)}
                        </span>
                      )}
                    </div>

                    {/* Filter status: semua status punya chip + count (traceable;
                        EXPIRED tetap ada, tidak pernah disembunyikan by default).
                        Label bahasa manusia + aria-pressed supaya pembaca layar
                        tahu mana yang sedang aktif. */}
                    <div className="feed-filters" role="group" aria-label="Filter status">
                      {feedChipList.map((chip) => {
                        /* Tahap 2 (30 Okt 2026): chip adalah RINGKASAN yang juga
                           bisa ditekan. Tiga hal yang dijaga di sini:
                           1. chip berangka 0 dinonaktifkan — mengkliknya hanya
                              memindahkan pengguna ke daftar kosong, dan angkanya
                              tetap terlihat supaya statusnya tidak "hilang";
                           2. `aria-label` menyebut cakupan + jumlah, karena
                              pembaca layar tidak membaca angka di samping label;
                           3. chip pertama ("Perlu tindakan") ditandai `data-utama`
                              untuk penekanan tipografi, bukan warna baru.
                           Pengumuman perubahan TIDAK memakai live region baru:
                           `feed-status` (role="status" aria-atomic) sudah
                           mengabarkan "Menampilkan X dari Y · filter: …" saat
                           chip ditekan. Dua live region bersaing berisik di
                           pembaca layar dan sulit diuji. */
                        const aktif = feedScope === chip.id;
                        const habis = chip.count === 0;
                        return (
                        <button
                          key={chip.id}
                          type="button"
                          aria-pressed={aktif}
                          /* Chip yang sedang aktif tidak boleh terkunci mati
                             walau angkanya 0 — pengguna harus tetap bisa
                             melepasnya (dan "Kosongkan filter" tetap ada). */
                          disabled={habis && !aktif}
                          aria-label={`Saring daftar ke ${chip.label}: ${chip.count} rekomendasi`}
                          data-utama={chip.id === FEED_SCOPE_ACTION}
                          className={`filter-chip${aktif ? " filter-chip-active" : ""}${
                            habis && !aktif ? " filter-chip-kosong" : ""
                          }`}
                          onClick={() => {
                            setFeedScope(aktif ? FEED_SCOPE_ALL : chip.id);
                            setFeedPage(1);
                          }}
                        >
                          {/* Huruf pertama dikapitalkan di sini, bukan di
                              lib: `feedChips` sengaja mengembalikan label apa
                              adanya (dipakai juga sebagai kata kunci pencarian
                              dan diuji huruf kecil). Tanpa ini deretan chip
                              terbaca "Perlu tindakan · menunggu persetujuan ·
                              ditandai verifier" — satu baris dengan tiga gaya
                              huruf awal. */}
                          {chip.label.charAt(0).toUpperCase() + chip.label.slice(1)}
                          <span className="legend-count">{chip.count}</span>
                        </button>
                        );
                      })}
                    </div>

                    <div className="feed-status-row">
                      {/* Angka "Menampilkan 10 dari 17" hanya dicetak saat ada
                          saringan/pencarian (29 Okt 2026). Tanpa saringan ia
                          persis mengulang "1–10 dari 17" di pager 40 px di
                          bawahnya, sedangkan pembaca layar tetap perlu tahu
                          rentang yang tampil — karena itu saat tidak menyaring
                          barisnya `sr-only`, bukan dihapus. */}
                      <p
                        className={`feed-status${feedFilterActive ? "" : " sr-only"}`}
                        role="status"
                        aria-atomic="true"
                      >
                        {feedSummary({
                          shown: feedCards.length,
                          total: feedWindowDecisions.length,
                          scope: feedScope,
                          query: feedQuery,
                        })}
                      </p>
                      {feedFilterActive && (
                        <button
                          type="button"
                          className="feed-reset"
                          onClick={() => {
                            setFeedScope(FEED_SCOPE_ALL);
                            setFeedQuery("");
                            setFeedPage(1);
                          }}
                        >
                          Kosongkan filter
                        </button>
                      )}
                    </div>
                  </div>


                  {feedCards.length === 0 ? (
                    <FeedEmptyState
                      filterActive={feedFilterActive}
                      windowKey={feedWindow}
                      windowLabel={feedWindowLabel(feedWindow)}
                      windowHint={feedWindowHintBilaBerbeda(feedWindow)}
                      totalInWindow={feedWindowDecisions.length}
                      onResetFilter={() => {
                        setFeedScope(FEED_SCOPE_ALL);
                        setFeedQuery("");
                        setFeedPage(1);
                      }}
                      onWidenWindow={() => {
                        setFeedWindow("30d");
                        setFeedPage(1);
                      }}
                      onRetry={() => void decisionsQuery.refetch()}
                    />
                  ) : (
                    <section className="feed" aria-labelledby="feed-judul">
                      {/* Tahap 3 (30 Okt 2026): daerah daftar diberi satu judul
                          h2 (sr-only, tidak menambah teks di layar) supaya judul
                          kartu yang kini <h3> tidak melompati tingkat heading —
                          h1 → h3 adalah kegagalan urutan heading. Komentar ini
                          sengaja berada DI DALAM elemen: di posisi sebelumnya
                          (tepat setelah `(` cabang ternary) ia bukan JSX dan
                          membuat berkas gagal di-parse. */}
                      <h2 className="sr-only" id="feed-judul">
                        Daftar rekomendasi
                      </h2>
                      {feedCards.map((d) => {
                        // Tombol "Persetujuan" hanya untuk yang benar-benar
                        // boleh menyetujui — peran pemantau dan keputusan yang
                        // sudah selesai tidak ditawari tombol yang akan ditolak.
                        const aksi = visibleActions(role ?? "", String(d.status ?? ""));
                        const bolehSetujui = !aksi.readOnly && aksi.approve;
                        return (
                          <div key={d.decision_id} className="rec-baris">
                            {/* Satu tombol "Tinjau" (permintaan pemilik 28 Okt
                                2026): popup yang dibuka memuat rincian sekaligus
                                panel persetujuan, jadi tidak perlu dua tombol.
                                Pembungkusnya <div> karena <button> tidak boleh
                                bersarang di dalam <button>. */}
                            <RecommendationCard
                              decision={d}
                              mockSourced={d.status === "executed"}
                              onBuka={(tampilan, pemicu) =>
                                bukaPopupKeputusan(String(d.decision_id), pemicu, tampilan)
                              }
                              tampilPersetujuan={bolehSetujui}
                            />
                          </div>
                        );
                      })}
                    </section>
                  )}

                  <Pager
                    page={feedPageData}
                    onChange={setFeedPage}
                    label="rekomendasi"
                  />
                </>
              )}
            </section>
          </>
        )}

        {/* Langkah 4 (permintaan Roy 2026-10-11): halaman "Decision & Evidence"
            — halaman ke-3 di sidebar acuan, sebelumnya menempel di bawah feed
            Recommendations. Semua angka dari API; yang tidak ada ditulis "—". */}
        {tab === "evidence" && (
          <>
          {/* Audit data 26 Okt 2026: kegagalan sebagian dulu ditelan
              `catch(() => null)` sehingga panel kosong tak bisa dibedakan dari
              "memang tidak ada data". Sekarang bagian yang gagal disebut. */}
          {pesanDiganti ? (
            <p className="board-alert" role="status">
              {pesanDiganti}
            </p>
          ) : null}
          {detail.errors.length > 0 && !detail.gone ? (
            <p className="board-alert" role="status">
              Sebagian bukti gagal dibaca: {detail.errors.join(", ")}. Panel di bawah hanya
              menampilkan bagian yang berhasil dimuat.
            </p>
          ) : null}
          <DecisionEvidence
            purchaseOrders={purchaseOrders.data}
            decisions={decisions}
            selected={selected}
            selectedId={selectedId}
            diganti={detail.gone}
            loading={decisionsQuery.isPending}
            onSelect={(decisionId) => setSelectedId(decisionId)}
            chain={selectedId ? chain : []}
            summary={approvalSummary}
            supplierContext={supplierContext}
            role={role ?? ""}
            token={token}
            now={now}
            onSupplierCreated={(decisionId) => {
              if (token) void decisionsQuery.refetch();
              setSelectedId(decisionId);
            }}
            onOpenRecommendations={() => setTab("recommendations")}
            onOpenTraces={() => setTab("agent-log")}
          />
          </>
        )}

        {/* Langkah 5 (permintaan Roy 2026-10-11): halaman sidebar ACUAN
            (E:\hackathon\HackathonBil\MealchainGuardian) yang belum ada di repo
            ini — Keamanan Pangan (/compliance), Surplus & Limbah (/surplus),
            Pemasok (/suppliers), Kualitas Agen (/quality) — disesuaikan ke
            endpoint yang benar-benar ada. Angka kosong ditulis "—". */}
        {tab === "location-network" && (
          <>
          <LocationNetworkBoard
            locations={mapData?.locations ?? []}
            commodity={mapData?.commodity ?? mapCommodity}
            loading={!mapData && !mapError}
            error={mapError}
            onRetry={() => void mapQuery.refetch()}
            selected={networkSelected}
            onSelect={setNetworkSelected}
            detail={supplyDemand.detail}
            detailLoading={supplyDemand.loading}
            detailError={supplyDemand.error}
            snapshot={mapSnapshotNote}
            plan={planQuery.data}
            planLoading={planQuery.loading}
            planError={planQuery.error}
            waste={wasteQuery.data}
            wasteLoading={wasteQuery.loading}
            wasteError={wasteQuery.error}
            batches={batches}
            decisions={decisions}
            now={now}
            commodities={COMMODITIES}
            onCommodityChange={setMapCommodity}
            heading={locationNetworkTitle(role)}
            // Kalimat kepala peran lain memakai bawaan komponen (satu sumber
            // teks): dulu kalimat yang sama ditulis dua kali di sini dan di
            // komponen, dan keduanya sempat berbeda.
            description={
              role === "sppg_nutritionist"
                ? "Pasokan, kebutuhan, selisih, perkiraan, dan batch satu lokasi."
                : undefined
            }
          />
          {/* Surplus & Limbah sudah menjadi blok di dalam board itu sendiri
              (rencana 29 Okt 2026, docs/plans/location-network-page-plan.md):
              satu kepala, satu filter, lalu Lokasi → Rincian → Rencana alih →
              Limbah. Merender <SurplusBoard/> utuh di sini akan mengembalikan
              dua kepala dan dua filter di satu tab. */}
          </>
        )}

        {tab === "safety" && (
          <FoodSafetyBoard
            batches={batches}
            now={now}
            loading={batchesLoading}
            error={batchesError}
            onRetry={() => void todayQuery.refetch()}
            ownLocation={me?.location_name ?? null}
            ownLocationId={me?.location_id ?? null}
            routes={safetyRoutesQuery.data}
            balance={mapData}
            decisions={decisions}
            canMutate={APPROVER_ROLES.has(role ?? "")}
            canPropose={role === "sppg_head"}
            onRecheck={safetyRecheck}
            onRepropose={safetyRepropose}
            onTriggerDisruption={safetyTriggerDisruption}
            onRecordReceipt={(batchId, checked, catatan, dinilai) =>
              recordReceipt(batchId, checked, catatan, token ?? "", dinilai)
            }
            loadReceipts={(batchId) => fetchReceipts(batchId, token ?? "")}
            loadChecklist={loadReceiptChecklist}
            loadPendingReceipts={loadPendingReceiptsStabil}
            onApproveReceipt={receiptApprove}
            onRejectReceipt={receiptReject}
            canApprove={role === "sppg_head"}
            onKarantina={safetyKarantina}
            onOpenDecisions={() => setTab("evidence")}
          />
        )}


        {tab === "suppliers" && (
          <SupplierBoard
            suppliers={suppliersQuery.data}
            exclusions={exclusions}
            selectedDecisionId={selectedId}
            supplierContext={supplierContext}
            role={role ?? ""}
            token={token ?? ""}
            loading={supplierLoading}
            error={supplierError}
            onRetry={() => void suppliersQuery.refetch()}
            reachKm={supplierReachKm}
            onOpenDecision={(decisionId) => {
              if (decisionId) setSelectedId(decisionId);
              setTab("evidence");
            }}
            onExclusionCreated={() => void decisionsQuery.refetch()}
            supplierRoutes={supplierRoutesQuery.data}
            receiptHistory={receiptHistoryQuery.data}
            receiptLoading={receiptHistoryQuery.loading}
            receiptError={receiptHistoryQuery.error}
          />
        )}

        {/* Tab gabungan "KPI & Kualitas Agen" (keputusan pemilik
            2026-10-15): KPI (hasil) dulu, lalu mutu kerja agen (cara).
            Kedua bagian mempertahankan loading/error-nya sendiri supaya satu
            bagian gagal tidak menyembunyikan bagian lain. */}
        {tab === "kpi-kualitas" && (
          <KpiQualityBoard
            kpi={kpi}
            kpiLoading={kpiLoading}
            kpiError={kpiError}
            onRetryKpi={() => void kpiQuery.refetch()}
            windowKey={kpiWindow}
            onWindowChange={setKpiWindow}
            scope={kpiScope}
            onScopeChange={setKpiScope}
            scopeDisabledReason={
              demoSession.active
                ? null
                : "Belum ada sesi demo aktif, jadi cakupan simulasi tidak tersedia."
            }
            runs={qualityRuns}
            evaluatedCount={evaluatedCount}
            totalDecisions={decisions.length}
            qualityLoading={qualityLoading}
            qualityError={qualityError}
            onRetryQuality={() => void sampleQuery.refetch()}
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
          <PageShell
            className="agent-log-section"
            sections={agentLogSections()}
            jumpAriaLabel="Bagian halaman Agent Activity Log"
            title={PAGE_TITLES.agentLog}
            description="Pilih keputusan, klik satu tahap, lihat tool dan catatannya."
          >

            {/* Urutan baca dokumen `06-agent-log.md` §4.3: pencarian → periode →
                tabel keputusan → keadaan trace → strip tahap → langkah rinci →
                konteks (agent, supervisor, status model) → integritas. Semua yang
                bergantung pada satu keputusan berada SETELAH pemilihnya. */}
            {/* Satu bilah filter (29 Okt 2026): pencarian, komoditas, dan periode
                dulu tiga blok bertumpuk (158 px + 28 px + jarak). Kini satu kartu
                — periode duduk sebaris dengan field, chip status + kalimat cakupan
                di bawahnya. */}
            <div className="jump-target" id={AGENT_LOG_SECTION_IDS.pilih}>
            {/* Tahap 1 redesign (29 Okt 2026): delapan blok dulu bertumpuk tanpa
                judul kelompok. Kini tiga kelompok bertajuk — Pilih keputusan,
                Langkah & model, Integritas — supaya pembaca tahu di mana ia
                berada tanpa membaca paragraf penghubung. */}
            <h2 className="log-section-title" id="log-pilih-judul">Pilih keputusan</h2>
            <ModuleSearch
              query={logQuery}
              onQuery={(value) => {
                setLogQuery(value);
                setLogPage(1);
              }}
              commodity={logCommodity}
              onCommodity={(value) => {
                setLogCommodity(value);
                setLogPage(1);
              }}
              verification={logVerification}
              onVerification={(value) => {
                setLogVerification(value);
                setLogPage(1);
              }}
              attention={logAttention}
              onAttention={(value) => {
                setLogAttention(value);
                setLogPage(1);
              }}
              attentionCount={agentLogOverview?.attention ?? 0}
              commodities={agentLogCommodities}
              counts={agentLogCounts}
              total={agentLogRows.length}
              shown={agentLogShown.length}
              period={
                <PeriodPicker
                  value={logWindow}
                  onChange={(value) => {
                    setLogWindow(value);
                    setLogPage(1);
                  }}
                />
              }
            />

            <AgentActivityPanel
              role={role}
              decisions={agentLogShown}
              total={agentLogRows.length}
              page={logPage}
              onPage={setLogPage}
              selectedId={selectedId}
              onSelect={(decisionId) => {
                setSelectedId(decisionId);
                // Keputusan berganti = saringan tahap lama tidak berlaku lagi.
                setLogStage(null);
              }}
              summary={agentLogSummary}
              steps={detail.loading ? null : traces}
              ledger={detail.loading ? null : detail.ledger}
              overview={agentLogOverview}
              periodLabel={feedWindowHint(logWindow)}
              now={now}
              loading={agentLogQuery.isPending}
              onOpenEvidence={() => setTab("evidence")}
              stageFilter={logStage}
              onStageFilter={setLogStage}
            />
            </div>

            <div className="jump-target" id={AGENT_LOG_SECTION_IDS.langkah}>
            {/* Judul kelompok + status supervisor sebaris (permintaan pemilik
                29 Okt 2026: "Agent supervisor" kurang pas kalau jadi kartu
                sendiri di samping roster). Statusnya menerangkan keadaan jejak,
                jadi tempatnya di kepala kelompok, bukan sebagai blok ketiga. */}
            <div className="log-section-head">
              <h2 className="log-section-title" id="log-langkah-judul">Langkah &amp; model</h2>
              <SupervisorStatusLine
                health={supervisorHealth.data ?? null}
                loading={supervisorHealth.isLoading}
              />
            </div>
            <AgentRunSummary
              providers={providersFromTraces(traces)}
              traceCount={traces.length}
              modelSteps={modelStepCount(traces)}
            />

            <AgentTraceViewer
              steps={traces}
              decisionId={selected?.decision_id ?? null}
              createdAt={selected?.created_at ?? null}
              now={now}
              stageFilter={logStage}
              onClearStageFilter={() => setLogStage(null)}
            />

            {/* Roster dua agent (Tahap 5); status supervisor sudah pindah ke
                kepala kelompok di atas. */}
            <AgentRoster />

            </div>

            {selected ? (
              <div className="jump-target" id={AGENT_LOG_SECTION_IDS.integritas}>
                <h2 className="log-section-title" id="log-integritas-judul">Integritas</h2>
                <IntegrityPanel token={token ?? ""} decisionId={selected.decision_id} />
              </div>
            ) : null}

            {/* §2.9: tanya-jawab untuk peran non-approver — PALING BAWAH halaman
                (Tahap 6 redesign). Ia alat bantu penjelajahan, bukan langkah
                pertama: sebelumnya ia duduk di antara pemilih keputusan dan
                tabel, sehingga pembaca yang baru membuka halaman melihat kotak
                tanya-jawab sebelum melihat satu keputusan pun. */}
            {role && !APPROVER_ROLES.has(role) ? (
              <div className="agent-log-ask">
                <SupervisorAskPanel token={token} />
              </div>
            ) : null}
          </PageShell>
        )}
        </div>
      </div>
      {/* Drawer "Detail Keputusan" (dokumen `01-detail-keputusan.md`, 28 Okt
          2026). Satu instance untuk seluruh konsol: yang berganti hanya
          keputusan yang dibuka, jadi panel tidak menumpuk dan kunci gulir tetap
          satu. Ditaruh di akhir <main> supaya tidak ikut tata letak tab mana pun. */}

      <DecisionDrawer
        open={popupKeputusanId !== null}
        onClose={() => setPopupKeputusanId(null)}
        decision={selected}
        summary={approvalSummary}
        tampilanAwal={popupTampilan}
        role={role ?? ""}
        token={token}
        now={now}
        onOpenFullPage={(decisionId) => {
          setPopupKeputusanId(null);
          setSelectedId(decisionId);
          setTab("evidence");
        }}
        returnFocusRef={popupTriggerRef}
      />
    </main>
  );
}
