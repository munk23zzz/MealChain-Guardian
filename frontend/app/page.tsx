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
  evaluateFreshness,
  evaluateSafety,
  fetchReceipts,
  login,
  recordReceipt,
  ubahKarantina,
  reproposeAction,
  triggerSafetyDisruption,
} from "../lib/api";
import { useBalanceMap } from "../lib/hooks/useBalanceMap";
import { useDecisionDetail } from "../lib/hooks/useDecisionDetail";
import { readDecisionLink, withDecisionLink } from "../lib/decision-link";
import { useExclusions } from "../lib/hooks/useExclusions";
import { useKpi } from "../lib/hooks/useKpi";
import { useWasteSummary } from "../lib/hooks/useWasteSummary";
import { useIntegrationStatus } from "../lib/hooks/useIntegrationStatus";
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
import { useMe } from "../lib/hooks/useMe";
import { useQualitySample } from "../lib/hooks/useQualitySample";
import { useSuppliers } from "../lib/hooks/useSuppliers";
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
import { errorMessage } from "../lib/query";
import {
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
import Pager from "../components/Pager";
import { paginate } from "../lib/pagination";
import IntegrationStatusPanel from "../components/IntegrationStatusPanel";
import PurchaseOrderList from "../components/PurchaseOrderList";
import TopBar from "../components/TopBar";
import {
  ALL_LOCATIONS,
  countActionable,
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
import { StatusLocationList } from "../components/SupplyMap";
import RecommendationCard, { DECISION_TYPE_LABELS } from "../components/RecommendationCard";
import AgentTraceViewer from "../components/AgentTraceViewer";
import AgentSwarmPanel from "../components/AgentSwarmPanel";
import DecisionPicker from "../components/DecisionPicker";
import { defaultAgentLogId } from "../lib/agent-swarm";
import DemoControlPanel from "../components/DemoControlPanel";
import { mapHeaderSubtitle } from "../lib/overview-copy";
import DecisionChain from "../components/DecisionChain";
import ProviderPanel from "../components/ProviderPanel";
import RoleHero from "../components/RoleHero";
import PageHeader from "../components/PageHeader";
import KpiQualityBoard from "../components/KpiQualityBoard";
import SupplyMap from "../components/SupplyMap";
import NodeTelemetry from "../components/NodeTelemetry";
import TodayDashboard from "../components/TodayDashboard";
import StockChart from "../components/StockChart";
import ShipmentCard from "../components/ShipmentCard";
import { focusNote, focusPick, focusRows } from "../lib/route-focus";
import { formatKg, snapshotNote, syncLabel } from "../lib/overview-format";
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
import FoodSafetyBoard from "../components/FoodSafetyBoard";
import SurplusBoard from "../components/SurplusBoard";
import SupplierBoard from "../components/SupplierBoard";
import { runOf, type QualityRun } from "../lib/agent-quality";
import { defaultEvidenceId } from "../lib/evidence";
import { decisionGroups, statusWord, typeWord } from "../lib/decision-picker";

const APPROVER_ROLES = new Set(["sppg_head", "sppg_nutritionist"]);

// Recommendation Feed: 10 kartu per halaman, sama seperti Daftar Pemasok dan
// Papan Kiriman. Semua kartu yang lolos filter tetap bisa dijangkau lewat Pager.
const FEED_PAGE_SIZE = 10;

// Halaman Kualitas Agen & Pemasok menilai SAMPEL keputusan terakhir dalam
// cakupan: jejak agen + putusan verifikator dipanggil per keputusan, jadi
// jumlahnya dibatasi — angkanya ditulis apa adanya di halaman, bukan
// diam-diam dipotong. Halaman Surplus & Limbah ikut aturan acuan: hanya
// peran SPPG yang melihatnya.
const EVALUATED_LIMIT = 8;
const SURPLUS_ROLES = new Set(["sppg_head", "sppg_nutritionist"]);

// Panel provider dihitung dari trace aktual (VERIFY/PREDICT/SUPERVISE);
// tanpa karangan — agen tanpa langkah model tampil "tidak tersedia".
// CATATAN: baris di bawah membandingkan verdict SERVER ("UNAVAILABLE") — itu
// nilai kontrak, bukan label layar. Jangan disamakan dengan teks tampilan.
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
  const [mapCommodity, setMapCommodity] = useState("telur");
  // Lokasi aktif yang disorot di peta, dipilih dari dropdown top bar.
  const [activeLocation, setActiveLocation] = useState<string | null>(null);
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
  // Papan status integrasi (W-3): dipakai panel di tab Agent Log; isinya env +
  // artefak, jadi tidak di-poll.
  const integrationStatus = useIntegrationStatus(token);
  // Purchase order mock SAP (W-5): sisi baca yang selama ini tidak ada. Kunci
  // query memakai `identityScope` karena isinya berbeda per peran.
  const purchaseOrders = usePurchaseOrders(token, identityScope);
  const mapData = mapQuery.data;
  const mapError = mapQuery.error;
  const mapUpdatedAt = mapQuery.updatedAt;
  const decisionsQuery = useDecisions(token, identityScope);
  // Dibungkus useMemo: literal `[]` baru setiap render akan membuat useMemo
  // turunan (sampel → run/pemasok) dihitung ulang tanpa perlu.
  const decisions = useMemo(() => decisionsQuery.data?.items ?? [], [decisionsQuery.data]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
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
  const ledger = todayQuery.data?.ledger ?? null;
  const batchesLoading = todayQuery.isFetching;
  const batchesError = errorMessage(todayQuery.error);
  const decisionsError = errorMessage(decisionsQuery.error);
  const error = decisionsError ?? traceError;
  // Jam klien: null sampai komponen ter-mount supaya HTML server dan render
  // klien tidak berbeda (label waktu ditulis "—" sebelum jam siap).
  const [now, setNow] = useState<Date | null>(null);
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
  // Jalur kiriman (Fase 10): garis jalan pemasok → tujuan. Peta memakai yang
  // sekomoditas dengan tampilan; halaman Pemasok memakai daftar penuh supaya
  // tabel bisa menyebut jalur untuk semua kiriman aktif.
  const mapSupplierRoutesQuery = useSupplierRoutes(
    token,
    identityScope,
    tab,
    mapData?.commodity ?? null
  );
  // Sorotan peta (Arah C): baris yang dipilih + jumlah seluruh kiriman tampilan.
  // Keduanya dari data yang SAMA dengan garis di peta (mapSupplierRoutesQuery).
  const focusRow = focusPick(mapSupplierRoutesQuery.data, focusedRoute);
  const focusTotal = focusRows(mapSupplierRoutesQuery.data).length;
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

  // S4-03: envelope GET /kpi lewat React Query — satu potret per sesi (scope
  // ditentukan backend: SPPG own, monitor global). Loading dan galat dibaca dari
  // status query; tombol "Coba lagi" memanggil refetch().
  //
  // Pemilih periode (2026-10-16): jendela dimiliki HALAMAN, bukan komponen —
  // hook butuh nilainya untuk memuat rentang yang benar, dan komponen butuh
  // nilai yang sama untuk menandai pilihan aktif. Default tetap 24 jam.
  const [kpiWindow, setKpiWindow] = useState<KpiWindowKey>("24h");
  const kpiQuery = useKpi(token, identityScope, tab, kpiWindow);
  // Limbah + mitra pengolahan (18 Okt 2026): panel Surplus & Limbah dulu menulis
  // "—" karena tidak ada sumbernya. Sekarang dari server, dimuat hanya di tab itu.
  const wasteQuery = useWasteSummary(token, identityScope, tab);

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
    const demoAccounts = [
      { label: "SPPG Head", email: "sppg.head@demo.local", password: "Demo#SPPG2026" },
      { label: "Nutritionist", email: "sppg.nutritionist@demo.local", password: "Demo#Nut2026" },
      { label: "BGN Monitor", email: "bgn.monitor@demo.local", password: "Demo#BGN2026" },
    ];
    // Keputusan produk 3A (18 Okt): Bandung & Surabaya punya approver sendiri,
    // jadi alur approval bisa didemokan di kota yang bukan Jakarta.
    const demoKota = [
      { label: "Kepala Bandung", email: "sppg.head.bandung@demo.local", password: "Demo#SPPG2026" },
      {
        label: "Gizi Bandung",
        email: "sppg.nutritionist.bandung@demo.local",
        password: "Demo#Nut2026",
      },
      {
        label: "Kepala Surabaya",
        email: "sppg.head.surabaya@demo.local",
        password: "Demo#SPPG2026",
      },
      {
        label: "Gizi Surabaya",
        email: "sppg.nutritionist.surabaya@demo.local",
        password: "Demo#Nut2026",
      },
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
              {/* Approver Kota lain — supaya alur dua approval bisa dicoba di
                  Bandung/Surabaya, bukan hanya di Jakarta. */}
              <p className="demo-hint demo-hint-kota">Kota lain:</p>
              <p className="demo-links">
                {demoKota.map((acc, i) => (
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
  const notif = notifList(decisions, 4, role);
  const roleLabel = ROLE_LABEL[role ?? ""] ?? (role ?? "user");

  // Feed traceable (arah Roy 2026-10-09): EXPIRED TIDAK disembunyikan — semua
  // status tetap muncul sebagai chip + angka. Chip, penyaring, dan urutan
  // dihitung lib/decision-feed (label bahasa manusia, "Perlu tindakan" dulu).
  // Tanpa useMemo: nilainya kecil (126 baris) dan di bawah ini tidak boleh ada
  // hook baru — komponen sudah punya early return untuk layar login.
  const feedFilter = { scope: feedScope, query: feedQuery };
  const feedChipList = feedChips(decisions);
  const feedRows = sortFeed(feedVisible(decisions, feedFilter), feedSort, now);
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
    { id: "today", label: "Hari Ini" },
    { id: "overview", label: "Overview" },
    {
      // Angka = jumlah yang PERLU DI-APPROVE, bukan seluruh keputusan yang
      // pernah dibuat (dulu 126 dan sulit ditafsirkan).
      id: "recommendations",
      label: `Recommendations${perluKeputusan ? ` (${perluKeputusan})` : ""}`,
      // Angka = yang MASIH bisa ditindak; tunggakan yang lewat tenggat tetap
      // disebut supaya tidak hilang dari pandangan (temuan QA F1).
      title: perluKeputusan
        ? `${perluKeputusan} rekomendasi perlu tindakan${lewatTenggat ? ` · ${lewatTenggat} lewat tenggat` : ""}`
        : lewatTenggat
          ? `Tidak ada yang bisa ditindak · ${lewatTenggat} lewat tenggat`
          : "Tidak ada rekomendasi yang perlu tindakan",
    },
    { id: "evidence", label: "Decision & Evidence" },
    { id: "safety", label: "Keamanan Pangan" },
    { id: "surplus", label: "Surplus & Limbah", roles: Array.from(SURPLUS_ROLES) },
    { id: "suppliers", label: "Pemasok" },
    { id: "agent-log", label: "Agent Log" },
    { id: "kpi-kualitas", label: "KPI & Kualitas Agen" },
    { id: "settings", label: "Pengaturan", roles: Array.from(MANAGE_ROLES) },
    ...(isApprover
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
                    ? mapHeaderSubtitle((mapData.locations ?? []).length)
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
                    {syncLabel(mapUpdatedAt)}
                  </span>
                )}
              </div>
            </section>

            <RoleHero role={role ?? "sppg_head"} />

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
                <span className="kpi-card-value">
                  {decisionsQuery.isLoading ? "—" : notif.total}
                </span>
                <span className="kpi-card-foot">
                  {decisionsQuery.isLoading
                    ? "memuat daftar keputusan"
                    : notif.expired > 0
                      ? `${notif.expired} lewat tenggat — tetap terlihat, tidak disembunyikan`
                      : `${decisions.length} keputusan dipantau`}
                </span>
                <span className="kpi-card-mini">
                  {decisionsQuery.isLoading
                    ? "menunggu data"
                    : notif.rest > 0
                      ? `+${notif.rest} lain menunggu tindakan`
                      : "semua sudah ditindaklanjuti"}
                </span>
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
              className="overview-split"
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
                    <span className="queue-head-count">{notif.total}</span>
                  </div>
                  {notif.shown.length === 0 ? (
                    <p className="queue-empty">
                      Semua keputusan sudah ditindaklanjuti. Permintaan baru
                      muncul di sini.
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
                          <span className="queue-item-main">
                            <span className="queue-item-label">
                              {DECISION_TYPE_LABELS[item.decision_type ?? ""] ??
                                "Rekomendasi baru"}
                            </span>
                            <span className="queue-item-meta">
                              {formatKg(item.quantity_kg)} ·{" "}
                              {formatDateTime(item.created_at)}
                            </span>
                          </span>
                          {item.status && <StatusBadge status={item.status} />}
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
                      Buka tab Recommendations
                    </button>
                  </div>
                </section>
              </div>
            </section>

            {/* Informasi pengiriman (Arah A riset 16 Okt 2026): satu blok per
                kiriman — pil status, stepper tahap, angka kunci, kalimat
                keputusan. Datanya kiriman yang sama dengan garis di peta
                (disaring komoditas tampilan), jadi angka di kartu dan garis di
                peta tidak bisa berbeda cerita. */}
            <ShipmentCard
              routes={mapSupplierRoutesQuery.data}
              hanya={focusRow ? (row) => row.id === focusRow.id : undefined}
              note={`${focusNote(focusRow, focusTotal)} Mengikuti komoditas yang sedang ditampilkan di peta.`}
            />

            {/* Grafik pasokan per lokasi (Fase 2): sebelumnya di kolom samping
                peta — kolom itu hanya ~310px lebar sehingga grafiknya terjepit
                ~70px dan label 10 lokasi saling bertumpuk. Kini selebar halaman
                dengan tinggi tetap 380px, jadi batangnya benar-benar terbaca. */}
            <section className="map-panel" aria-label="Pasokan per lokasi">
              <h3>Pasokan per Lokasi</h3>
              <StockChart locations={mapData?.locations ?? []} />
            </section>

            {/* Dua kartu ringkas BERDAMPINGAN (revisi 16 Okt: "shape terlalu
                besar/kosong"). Sebelumnya Telemetri Node (237 px) dan daftar
                Status Lokasi (203 px) masing-masing selebar halaman padahal
                isinya hanya beberapa baris teks — total 440 px tinggi demi
                ~10 baris. Di >=1100px keduanya berbagi satu baris; di bawah itu
                tetap bertumpuk (lihat `.overview-pair`). */}
            <div className="overview-pair">
              {/* Telemetri Node di bawah baris peta */}
              <section aria-label="Telemetri node">
                <NodeTelemetry
                  locations={mapData?.locations ?? []}
                  activeLocation={activeLocation}
                  loading={!mapData && !mapError}
                />
              </section>

              {/* Status lokasi (tata letak acuan): daftar lokasi + statusnya. */}
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
            </div>
          </div>
        )}


        {tab === "settings" && <SettingsPanel token={token} />}

        {tab === "demo-control" && isApprover && (
          /* Demo Control sederhana (keputusan Roy 2026-10-19): tiga blok —
             siapkan data, jalankan agent, bukti. OpsConsole/ChaosPanel (Event
             1/2/3) sengaja dilepas dari tab ini: panel demo dipakai untuk
             MEMBUKTIKAN agent berjalan, bukan untuk memilih skenario.
             Komponen keduanya tetap ada di repo dan tetap diuji sendiri. */
          <>
            <PageHeader
              title="Demo Control"
              description="Satu tombol menjalankan agent sungguhan (bukan tiruan) untuk komoditas yang Anda pilih: yang dinilai adalah pemasok yang sudah memasok SPPG Anda (stok batch, penawaran harga, jarak pemasok → SPPG). Bukti putaran itu dibaca ulang dari database — langkah yang tercatat, provider yang benar-benar menjawab, dan status keputusan."
            />
            <DemoControlPanel
              token={token}
              role={role ?? "sppg_head"}
              locationName={me?.location_name ?? null}
              onOpenDecision={bukaKeputusanDariPO}
              onOpenAgentLog={() => setTab("agent-log")}
            />
          </>
        )}

        {tab === "recommendations" && (
          <>
            <section className="feed-section">
              <PageHeader
                title="Recommendation Feed"
                description="Satu kartu satu keputusan agent. Yang menunggu tindakan Anda selalu di paling atas, lalu isu keamanan, ketidakseimbangan, terakhir anomali harga."
                meta={
                  <>
                    <span className="commodity-pill">
                      {perluKeputusan} perlu tindakan
                    </span>
                    {lewatTenggat > 0 && (
                      <span className="commodity-pill">
                        {lewatTenggat} lewat tenggat
                      </span>
                    )}
                    <span className="commodity-pill">
                      {decisions.length} total rekomendasi
                    </span>
                  </>
                }
              />
              {error && (
                <p className="status-danger">
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
                  {/* Petunjuk ditaruh SEBELUM daftar: dulu ada di bawah 24 kartu,
                      jadi pembaca baru menemukannya setelah menggulung jauh. */}
                  <p className="feed-hint">
                    Klik kartu untuk membuka{" "}
                    <strong>Decision &amp; Evidence</strong> beserta seluruh bukti
                    keputusan itu.
                  </p>

                  {/* Cari + urutkan: sebelumnya tidak ada sama sekali, jadi 126
                      kartu hanya bisa dipindai satu per satu. */}
                  <div className="feed-toolbar">
                    <div className="feed-field feed-field-search">
                      <label htmlFor="feed-search">Cari rekomendasi</label>
                      <input
                        id="feed-search"
                        type="search"
                        value={feedQuery}
                        placeholder="Jenis, status, kasus, atau ID keputusan…"
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

                  {/* Filter status: semua status punya chip + count (traceable;
                      EXPIRED tetap ada, tidak pernah disembunyikan by default).
                      Label bahasa manusia + aria-pressed supaya pembaca layar
                      tahu mana yang sedang aktif. */}
                  <div className="feed-filters" role="group" aria-label="Filter status">
                    {feedChipList.map((chip) => (
                      <button
                        key={chip.id}
                        type="button"
                        aria-pressed={feedScope === chip.id}
                        className={`filter-chip${
                          feedScope === chip.id ? " filter-chip-active" : ""
                        }`}
                        onClick={() => {
                          setFeedScope(feedScope === chip.id ? FEED_SCOPE_ALL : chip.id);
                          setFeedPage(1);
                        }}
                      >
                        {chip.label}
                        <span className="legend-count">{chip.count}</span>
                      </button>
                    ))}
                  </div>

                  <div className="feed-status-row">
                    <p className="feed-status" role="status" aria-atomic="true">
                      {feedSummary({
                        shown: feedCards.length,
                        total: decisions.length,
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

                  {feedCards.length === 0 ? (
                    <p className="empty-state feed-empty">
                      Tidak ada rekomendasi yang cocok dengan filter atau kata
                      kunci ini. Coba kata lain, atau kosongkan filter untuk
                      melihat seluruh {decisions.length} rekomendasi.
                    </p>
                  ) : (
                    <div className="feed">
                      {feedCards.map((d) => (
                        <div key={d.decision_id}>
                          <button
                            type="button"
                            className="link-button"
                            onClick={() => {
                              setSelectedId(String(d.decision_id));
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
          <DecisionEvidence
            decisions={decisions}
            selected={selected}
            selectedId={selectedId}
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
          {/* W-5: purchase order yang benar-benar terbit setelah eksekusi.
              Dulu hanya toast sesaat, sehingga klaim "PO terbit di SAP" tidak
              bisa ditunjukkan. Panel ini membaca tabel mock SAP dan menyebut
              sumbernya apa adanya. 19 Okt 2026: `decisionId` diteruskan supaya
              baris milik keputusan yang sedang dibuka ditandai "keputusan ini" —
              tanpa itu, panel di bawah detail keputusan terbaca seolah seluruh
              daftar milik keputusan tersebut. */}
          <PurchaseOrderList
            data={purchaseOrders.data}
            summary={purchaseOrders.summary}
            loading={purchaseOrders.isFetching}
            error={purchaseOrders.error}
            decisionId={selectedId}
            token={token}
            onOpenDecision={bukaKeputusanDariPO}
            onRetry={purchaseOrders.refetch}
          />
          </>
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
            onRecordReceipt={(batchId, checked, catatan) =>
              recordReceipt(batchId, checked, catatan, token ?? "")
            }
            loadReceipts={(batchId) => fetchReceipts(batchId, token ?? "")}
            onKarantina={safetyKarantina}
            onOpenDecisions={() => setTab("evidence")}
          />
        )}

        {tab === "surplus" && (
          <SurplusBoard
            locations={mapData?.locations ?? null}
            commodity={mapData?.commodity ?? mapCommodity}
            commodities={COMMODITIES}
            onChangeCommodity={setMapCommodity}
            loading={!mapData && !mapError}
            error={mapError}
            onRetry={() => void mapQuery.refetch()}
            onOpenLocation={(location) => {
              setActiveLocation(location);
              setTab("overview");
            }}
            waste={wasteQuery.data}
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
          <section className="agent-log-section">
            <PageHeader
              title="Agent Activity Log"
              description="Jejak reasoning tiap langkah agen untuk satu keputusan — model, durasi, dan pesan apa adanya dari trace; tidak ada baris yang dikarang."
              meta={
                <DecisionPicker
                  id="pilih-keputusan-log"
                  ariaLabel="Pilih keputusan"
                  groups={decisionGroups(decisions, now)}
                  value={selectedId}
                  onChange={(decisionId) => setSelectedId(decisionId)}
                />
              }
            />
            {selected && (
              <p className="section-sub">
                Trace untuk <strong>{typeWord(selected.decision_type)}</strong> (
                {selected.decision_id.slice(0, 8)}) — status {statusWord(selected.status)}.
              </p>
            )}
            <ProviderPanel providers={providersFromTraces(traces)} />
            <AgentSwarmPanel
              steps={traces}
              decisionId={selected?.decision_id ?? null}
            />
            <AgentTraceViewer
              steps={traces}
              decisionId={selected?.decision_id ?? null}
              now={now}
            />
            {/* W-3 (2026-10-17): bukti integrasi per komponen — panel, bukan tab baru. */}
            <IntegrationStatusPanel
              data={integrationStatus.data}
              loading={integrationStatus.isFetching && !integrationStatus.data}
              error={integrationStatus.error}
              onRetry={() => void integrationStatus.refetch()}
            />
          </section>
        )}
        </div>
      </div>
    </main>
  );
}
