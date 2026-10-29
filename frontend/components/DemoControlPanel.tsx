"use client";

// Demo Control sederhana (keputusan Roy 2026-10-19).
//
// Bentuknya tiga blok, tanpa Event 1/2/3:
//   1. Muat demo         -> POST /demo/session/start (mode realtime; jangkar = waktu muat)
//                           atau POST /demo/refresh bila jendela sesi mati
//   2. Jalankan agent     -> POST /demo/agent/run (semua komoditas / satu komoditas + lokasi akun sendiri)
//   3. Bukti agent        -> GET  /demo/agent/last-run (dibaca ulang dari DB)
//
// Yang dijaga:
// - **Bukti tidak diambil dari respons tombol, tapi dari DB** sesudah putaran
//   selesai. Respons tombol bisa hilang saat halaman dimuat ulang; baris
//   `agent_traces` tidak. Karena itu blok bukti tetap terisi setelah refresh.
// - **Tidak ada progres palsu.** Server tidak mengirim progres per langkah,
//   jadi yang ditampilkan hanya waktu berjalan (jam klien) — bukan bar yang
//   bergerak seolah tahu langkah mana yang sedang dieksekusi.
// - **Tidak ada angka karangan.** Semua nilai berasal dari payload backend
//   (lihat lib/demo-agent.ts untuk peringkasannya, murni & teruji).
import { useCallback, useEffect, useRef, useState } from "react";

import { LoadingState } from "./LoadingState";
import {
  ApiError,
  endDemoSession,
  extendDemoSession,
  fetchApprovalSummary,
  fetchDemoAgentCommodities,
  fetchDemoAgentLastRun,
  fetchDemoDataStatus,
  fetchDemoSession,
  labelModeSesi,
  rebuildDemoTemplate,
  refreshDemoToToday,
  runDemoAgent,
  startDemoSession,
  streamDemoAgent,
} from "../lib/api";
import { catatanAliranPutus } from "../lib/agent-stream-note";
import type { LangkahAgent } from "../lib/agent-stream";
import AgentRunTerminal from "./AgentRunTerminal";
import { batchGateView, type BatchGateView } from "../lib/safety-gate";
import {
  formatSisa,
  jangkarSesi,
  keadaanSesi,
  modeSesi,
  pesanSesi,
  peringatanWaktu,
  ringkasSesi,
  sisaDetik,
  type StatusSesiDemo,
} from "../lib/demo-session";
import {
  agentReviewLine,
  demoAgentCards,
  defaultCommodity,
  elapsedLine,
  proofFacts,
  ringkasPutaran,
  idKeputusanPutaran,
  ringkasSatuKomoditas,
  runButtonLabel,
  stepNames,
  supervisorLine,
  type AgentRun,
} from "../lib/demo-agent";
import {
  adaBaris,
  rebuildLine,
  rebuildWarning,
  refreshLine,
  refreshWarning,
  statusLine,
  type RebuildSummary,
} from "../lib/demo-data";
import { formatDateTime } from "../lib/datetime";

const ROLE_JALAN = "sppg_head";
const ROLE_LIHAT = ["sppg_head", "sppg_nutritionist"];

/**
 * Isi blok bukti untuk satu putaran agent yang SUDAH ada.
 *
 * Dipisah dari panel supaya bisa dirender & diuji tanpa jaringan/efek: yang
 * diuji adalah kontrak tampilannya, bukan perilaku fetch.
 */
/** Token kanal kemajuan — cukup unik, tidak perlu rahasia (bukan kredensial). */
function buatTokenJalankan(): string {
  const kripto = globalThis.crypto;
  if (kripto && typeof kripto.randomUUID === "function") return kripto.randomUUID();
  return `run-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

/** Galat kanal → satu kalimat. Alasan server dipakai bila ada. */
function pesanAliran(e: unknown): string {
  if (e instanceof ApiError && e.detail) return e.detail;
  const pesan = (e as { message?: unknown })?.message;
  return typeof pesan === "string" && pesan.trim() ? pesan : "kanal log terputus";
}

export function DemoProof({
  run,
  running = false,
  langkahHidup = [],
  galatAliran = null,
  onOpenDecision,
  onOpenAgentLog,
  onRefresh,
}: {
  run: AgentRun;
  running?: boolean;
  /** Langkah yang sedang disiarkan server selama putaran berjalan. */
  langkahHidup?: LangkahAgent[];
  /** Galat kanal kemajuan; `null` = kanal sehat. */
  galatAliran?: string | null;
  onOpenDecision?: (decisionId: string) => void;
  onOpenAgentLog?: () => void;
  onRefresh?: () => void;
}) {
  const langkah = stepNames(run);
  const fakta = proofFacts(run);
  const narasi = run.supervisor?.summary ?? null;
  const kartu = demoAgentCards(run, running);
  const adaAgen = kartu.some((k) => k.state !== "idle");
  const adaLog = langkahHidup.length > 0 || galatAliran !== null;

  return (
    <>
      <dl className="dc-facts">
        {fakta.map((f) => (
          <div className="dc-fact" key={f.label}>
            <dt>{f.label}</dt>
            <dd>{f.value}</dd>
          </div>
        ))}
        <div className="dc-fact">
          <dt>Keputusan</dt>
          <dd>
            <code className="dc-id" title={run.decision_id ?? ""}>
              {(run.decision_id ?? "").slice(0, 8)}
            </code>
          </dd>
        </div>
        <div className="dc-fact">
          <dt>Dibuat</dt>
          <dd>{formatDateTime(run.created_at)}</dd>
        </div>
      </dl>


      {/* Selama putaran berjalan, bagian ini adalah LOG PENGAMBILAN DATA —
          bukan sembilan kartu. Kartu dibaca dari baris review yang ditulis
          SEKALI di akhir putaran: selama putaran ia hanya berisi "Berjalan",
          dan sebelum baris baru ditulis ia masih memuat hasil putaran
          SEBELUMNYA ("Selesai · Durasi 5,3 dtk"). Pemilik 29 Okt 2026 meminta
          bagian ini berubah menjadi log realtime saat "Jalankan agent". */}
      {running ? (
        <section className="dc-log-live" aria-labelledby="dc-live-judul">
          <div className="dc-log-live-head">
            <h3 id="dc-live-judul">Log proses pengambilan data</h3>
            <p className="dc-log-live-note">
              Kartu sembilan agen muncul lagi setelah putaran ditutup.
            </p>
          </div>
          <AgentRunTerminal langkah={langkahHidup} aktif galat={galatAliran} />
        </section>
      ) : (
        kartu.length > 0 && (
          <>
            <div className="dc-agents" role="list" aria-label="Sembilan agen review">
              {kartu.map((agen) => (
                <article
                  className="dc-agent"
                  data-state={agen.state}
                  data-agent={agen.key}
                  role="listitem"
                  key={agen.key}
                >
                  <div className="dc-agent-head">
                    <span className="dc-agent-dot" aria-hidden="true" />
                    <h3>{agen.label}</h3>
                  </div>
                  <span className="dc-agent-status">{agen.statusLabel}</span>
                  <dl className="dc-agent-meta">
                    {/* Baris fakta datang dari lib/demo-agent: worker memakai
                        Durasi/Peringatan, supervisor memakai Provider — supaya
                        kartu supervisor tidak memalsukan durasi yang tidak ada. */}
                    {agen.meta.map((f) => (
                      <div key={f.label}>
                        <dt>{f.label}</dt>
                        <dd>{f.value}</dd>
                      </div>
                    ))}
                  </dl>
                  {agen.note && (
                    <p className="dc-agent-note" title={agen.note}>
                      {agen.note}
                    </p>
                  )}
                </article>
              ))}
            </div>
            <p className="dc-line dc-line--muted">
              {run.agents_run_id
                ? "Status dibaca dari baris review tersimpan."
                : "Review sembilan agen belum tercatat."}
            </p>
          </>
        )
      )}

      {/* Log putaran yang barusan ditutup: dilipat supaya tidak memakan tinggi
          blok, tapi isinya tetap di DOM untuk dibaca ulang tanpa membuka Agent
          Log. Muncul hanya bila ada langkah — kotak kosong tidak ditampilkan. */}
      {!running && adaLog && (
        <details className="dc-log-fold">
          <summary>
            Log proses pengambilan data
            <span className="dc-fold-count">{langkahHidup.length}</span>
          </summary>
          <AgentRunTerminal langkah={langkahHidup} aktif={false} galat={galatAliran} />
        </details>
      )}

      {/* Daftar langkah dilipat: dibaca sesekali, tapi memakan ~1/4 tinggi blok.
          <details>/<summary> bawaan peramban — nol state, isi tetap di DOM. */}
      <details className="dc-steps-fold">
        <summary>
          Langkah pipeline <span className="dc-fold-count">{langkah.length}</span>
        </summary>
        <ol className="dc-steps" aria-label="Langkah pipeline yang tercatat">
          {langkah.map((nama, i) => (
            <li className="dc-step" key={`${nama}-${i}`}>
              <span className="dc-step-name">{nama}</span>
            </li>
          ))}
        </ol>
      </details>

      {run.supervisor?.status && run.supervisor.status !== "missing" && (
        <p className="dc-line">{supervisorLine(run.supervisor)}</p>
      )}
      {!adaAgen && (
        <p className="dc-line dc-line--muted">{agentReviewLine(run.agent_review)}</p>
      )}

      {narasi && (
        <details className="dc-narration">
          <summary>Hasil supervisor</summary>
          <p>{narasi}</p>
        </details>
      )}

      <div className="dc-links">
        <button
          type="button"
          className="button button-secondary dc-open-decision"
          onClick={() => run.decision_id && onOpenDecision?.(run.decision_id)}
          disabled={!onOpenDecision}
        >
          Buka keputusan
        </button>
        <button
          type="button"
          className="button button-secondary dc-open-log"
          onClick={() => onOpenAgentLog?.()}
          disabled={!onOpenAgentLog}
        >
          Buka Agent Log
        </button>
        <button
          type="button"
          className="button button-secondary dc-refresh-proof"
          onClick={() => onRefresh?.()}
          disabled={!onRefresh}
        >
          Segarkan bukti
        </button>
      </div>
    </>
  );
}


/**
 * Blok "bangun ulang data" — hanya muncul saat sesi berjalan.
 *
 * Kenapa dipisah: kontrak tampilannya harus bisa diuji tanpa jaringan/efek
 * (pola yang sama dengan `DemoProof`). Konfirmasi dua langkah dipilih supaya
 * aksi destruktif tidak berjalan karena salah klik, tanpa memakai `confirm()`
 * bawaan browser yang tidak bisa digayakan dan memblokir panggung.
 */
export function DemoRebuild({
  aktif,
  sibuk = false,
  detik = 0,
  onRebuild,
}: {
  aktif: boolean;
  sibuk?: boolean;
  detik?: number;
  onRebuild?: () => void;
}) {
  const [konfirmasi, setKonfirmasi] = useState(false);
  if (!aktif) return null;
  return (
    <div className="dc-rebuild" data-keadaan={sibuk ? "jalan" : konfirmasi ? "konfirmasi" : "diam"}>
      <p className="dc-rebuild-sub">
        Mengembalikan angka ke keadaan awal tanpa menutup sesi. Langkah terberatnya
        mengambil ulang rute jalan; panel ini tidak menampilkan perkiraan — hitungan detik
        berjalan selama proses dan durasi akhir dilaporkan setelah selesai.
      </p>
      {sibuk ? (
        <p className="dc-rebuild-line" role="status" aria-live="polite">
          Membangun ulang… {detik} detik
        </p>
      ) : konfirmasi ? (
        <div className="dc-rebuild-actions">
          <button
            type="button"
            className="button button-danger"
            onClick={() => {
              setKonfirmasi(false);
              onRebuild?.();
            }}
            title="Menghapus baris operasional lalu menyemai template lagi"
          >
            Ya, bangun ulang
          </button>
          <button type="button" className="button button-quiet" onClick={() => setKonfirmasi(false)}>
            Batal
          </button>
        </div>
      ) : (
        <div className="dc-rebuild-actions">
          <button
            type="button"
            className="button button-quiet"
            onClick={() => setKonfirmasi(true)}
            title="Angka kembali ke keadaan awal; sesi tetap berjalan"
          >
            Bangun ulang data
          </button>
        </div>
      )}
    </div>
  );
}

export default function DemoControlPanel({
  token,
  role,
  locationName,
  onOpenDecision,
  onOpenAgentLog,
}: {
  token: string | null;
  role: string;
  locationName?: string | null;
  onOpenDecision?: (decisionId: string) => void;
  onOpenAgentLog?: () => void;
}) {
  const [status, setStatus] = useState<any>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [bukti, setBukti] = useState<AgentRun | null>(null);
  // Id keputusan yang BARU dibuat tombol Jalankan (28 Okt 2026). Disimpan di
  // ref supaya `muatBukti()` langsung memakainya pada render yang sama —
  // membaca lewat state bisa memakai nilai lama dan meninggalkan kartu kosong.
  const idBuktiRef = useRef<string | null>(null);
  const [buktiError, setBuktiError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"data" | "agent" | "bangun" | null>(null);
  const [detik, setDetik] = useState(0);
  const [hasilData, setHasilData] = useState<string | null>(null);
  const [peringatanData, setPeringatanData] = useState<string | null>(null);
  const [pesan, setPesan] = useState<string | null>(null);
  // Log langsung (29 Okt 2026): baris yang SUDAH disiarkan server untuk putaran
  // yang sedang berjalan. Dikosongkan di awal setiap putaran supaya log lama
  // tidak menyamar sebagai log baru.
  const [langkahHidup, setLangkahHidup] = useState<LangkahAgent[]>([]);
  const [galatAliran, setGalatAliran] = useState<string | null>(null);
  // Sesi demo (024/025): status dari SERVER + hitungan mundur lokal yang
  // diselaraskan ulang tiap 20 detik. Tidak ada timer yang "menebak" waktu.
  const [sesi, setSesi] = useState<StatusSesiDemo | null>(null);
  const [tickSesi, setTickSesi] = useState(0);
  const [busySesi, setBusySesi] = useState<"mulai" | "tambah" | "tutup" | null>(null);
  // Pilihan komoditas datang dari DB (GET /demo/agent/commodities). Pilihan
  // "Semua komoditas" DIHAPUS 28 Okt 2026 atas permintaan pemilik: operator
  // harus menyebut komoditas yang dinilai, sehingga hasil satu putaran tidak
  // tertukar dengan komoditas lain. Sebelum daftar termuat, belum ada pilihan
  // (tombol agent menunggu), bukan menebak "beras".
  const [daftarKomoditas, setDaftarKomoditas] = useState<string[]>([]);
  const [komoditas, setKomoditas] = useState<string>("");
  // Ringkasan hasil putaran, diambil dari payload server (bukan dihitung ulang).
  const [hasilAgent, setHasilAgent] = useState<string | null>(null);
  // Kesiapan eksekusi kasus yang terakhir dianalisis (Fase 10 MG butir 3).
  // Sumbernya read model kanonik server (`/decisions/{id}/approval-summary`);
  // `can_execute` + `blocking_reasons` dipakai APA ADANYA, lalu diterjemahkan
  // peta kode yang SAMA dengan popup governance (`lib/safety-gate.ts`). Panel
  // tidak menghitung ulang aturan: dua tempat menghitung = dua kebenaran.
  const [kesiapan, setKesiapan] = useState<BatchGateView | null>(null);
  const [kesiapanError, setKesiapanError] = useState<string | null>(null);

  const bolehJalankan = role === ROLE_JALAN;
  const bolehLihatBukti = ROLE_LIHAT.includes(role);

  const muatStatus = useCallback(async () => {
    if (!token) return;
    setStatusError(null);
    try {
      setStatus(await fetchDemoDataStatus(token));
    } catch (e: any) {
      setStatus(null);
      setStatusError(String(e?.message ?? e));
    }
  }, [token]);

  const muatSesi = useCallback(async () => {
    if (!token) return;
    try {
      const r = (await fetchDemoSession(token)) as StatusSesiDemo;
      setSesi(r);
      setTickSesi(0);
    } catch {
      // Status sesi gagal dibaca bukan alasan menghentikan panel: kartu sesi
      // tetap tersembunyi (null) dan blok lain bekerja seperti biasa.
      setSesi((lama) => lama);
    }
  }, [token]);

  const muatBukti = useCallback(async () => {
    if (!token || !bolehLihatBukti) return;
    setBuktiError(null);
    try {
      // Bukti harus milik komoditas yang barusan dijalankan, bukan sekadar
      // putaran terbaru (satu putaran bisa menulis beberapa keputusan).
      // Bila tombol Jalankan baru saja berhasil, id keputusannya dipakai
      // eksplisit: server bisa menyelesaikan commit jejak beberapa milidetik
      // setelah balasan HTTP, sehingga pencarian "terbaru" bisa kosong.
      const hasil = await fetchDemoAgentLastRun(
        token,
        komoditas || undefined,
        idBuktiRef.current ?? undefined,
      );
      setBukti(hasil);
      if (!hasil?.found && idBuktiRef.current) {
        // Satu kesempatan lagi: jejak biasanya sudah terlihat setelah jeda ini.
        await new Promise((r) => setTimeout(r, 700));
        setBukti(
          await fetchDemoAgentLastRun(token, komoditas || undefined, idBuktiRef.current),
        );
      }
    } catch (e: any) {
      setBukti(null);
      setBuktiError(String(e?.message ?? e));
    }
  }, [token, bolehLihatBukti, komoditas]);

  const muatKomoditas = useCallback(async () => {
    if (!token || !bolehLihatBukti) return;
    try {
      const r = await fetchDemoAgentCommodities(token);
      const daftar: string[] = Array.isArray(r?.commodities) ? r.commodities : [];
      setDaftarKomoditas(daftar);
      setKomoditas((sekarang) =>
        daftar.includes(sekarang) ? sekarang : defaultCommodity(daftar)
      );
    } catch {
      // Daftar gagal dimuat bukan alasan mengarang pilihan: dropdown tetap
      // kosong dan tombol agent memakai bawaan backend (beras).
      setDaftarKomoditas([]);
    }
  }, [token, bolehLihatBukti]);

  const idKeputusan =
    bukti?.found && bukti?.decision_id ? String(bukti.decision_id) : null;

  const muatKesiapan = useCallback(async () => {
    if (!token || !idKeputusan) {
      // Tanpa putaran agent belum ada kasus yang bisa dinilai: blok ini
      // disembunyikan, BUKAN diisi "siap" sebagai tebakan.
      setKesiapan(null);
      setKesiapanError(null);
      return;
    }
    setKesiapanError(null);
    try {
      setKesiapan(batchGateView(await fetchApprovalSummary(idKeputusan, token)));
    } catch (e: any) {
      setKesiapan(null);
      setKesiapanError(String(e?.message ?? e));
    }
  }, [token, idKeputusan]);

  useEffect(() => {
    void muatStatus();
    void muatBukti();
    void muatKomoditas();
    void muatSesi();
  }, [muatStatus, muatBukti, muatKomoditas, muatSesi]);

  // Dijalankan ulang setiap kali keputusan yang ditampilkan berganti (mis.
  // sesudah seed berikutnya): kesiapan sesi lama tidak boleh menempel.
  useEffect(() => {
    void muatKesiapan();
  }, [muatKesiapan]);

  // Hitungan mundur sesi: tick lokal 1 detik, diselaraskan ulang tiap 20 detik
  // dengan `remaining_seconds` server (jam browser tidak dipercaya).
  useEffect(() => {
    if (!token) return;
    const selaras = window.setInterval(() => void muatSesi(), 20000);
    return () => window.clearInterval(selaras);
  }, [token, muatSesi]);

  const sesiAktif = Boolean(sesi?.active);
  useEffect(() => {
    if (!sesiAktif) return;
    const tick = window.setInterval(() => setTickSesi((n) => n + 1), 1000);
    return () => window.clearInterval(tick);
  }, [sesiAktif, sesi?.session_id]);

  // Sesi baru saja habis di layar: minta status sekali lagi supaya backend ikut
  // menutup dan membersihkan; jangan mengandalkan jam klien untuk mengubah data.
  const sisaSekarang = sisaDetik(sesi, tickSesi);
  const habisDiLayar = sesiAktif && sisaSekarang <= 0;
  useEffect(() => {
    if (habisDiLayar) void muatSesi();
  }, [habisDiLayar, muatSesi]);

  // Waktu berjalan hanya hidup selama tombol sibuk; tidak ada timer menganggur.
  useEffect(() => {
    if (busy !== "agent" && busy !== "bangun") {
      setDetik(0);
      return;
    }
    const mulai = Date.now();
    const jam = window.setInterval(() => {
      setDetik(Math.floor((Date.now() - mulai) / 1000));
    }, 1000);
    return () => window.clearInterval(jam);
  }, [busy]);

  /**
   * Tombol "Muat Demo" — satu-satunya jalan memuat dataset dari panel ini.
   *
   * Keputusan Roy 28 Okt 2026: pilihan dua mode dihapus dari UI. Dataset replay
   * (jangkar kanon 8 Okt) tidak lagi bisa dimuat dari tombol mana pun; yang
   * dimuat SELALU dataset yang dibangun pada saat tombol ditekan — jangkar =
   * waktu sekarang, sama seperti konsep awal sebelum dua tombol Fase 10.
   *
   * `replace: true` karena arti tombol ini memang "pakai dataset ini": sesi
   * bermode lain (mis. sisa replay dari sesi sebelumnya) ditutup server lalu
   * dibangun ulang, supaya layar tidak diam-diam bercampur dua jangkar.
   */
  async function onMuatDemo() {
    if (!token || !bolehJalankan || busy !== null) return;
    setBusy("data");
    setPesan(null);
    setHasilData(null);
    try {
      // Mode sesi mati (pengembangan tanpa DEMO_SESSION_ENFORCE): tidak ada
      // jendela waktu untuk dibuka, jadi cukup isi data untuk hari ini.
      if (!sesi?.enforced) {
        const r = await refreshDemoToToday(token);
        setHasilData(refreshLine(r));
        // Peringatan backend ditampilkan APA ADANYA — bukan diringkas klien.
        setPeringatanData(
          typeof r?.warning === "string" && r.warning ? r.warning : refreshWarning()
        );
        await muatStatus();
        await muatBukti();
        return;
      }
      const r = await startDemoSession(token, undefined, {
        mode: "realtime",
        replace: true,
      });
      setSesi(r as StatusSesiDemo);
      setTickSesi(0);
      const konflik = (r as { conflict?: { requested_mode?: string; active_mode?: string } })
        ?.conflict;
      if (konflik) {
        // Server menolak mengganti sesi: katakan apa adanya, jangan menampilkan
        // mode yang diminta seolah-olah sudah aktif.
        setPesan(
          `Sesi ${konflik.active_mode ?? "lain"} sedang berjalan — permintaan ${konflik.requested_mode ?? "realtime"} tidak menggantikannya.`
        );
        await muatStatus();
        return;
      }
      if (r?.created) {
        // Dataset baru tumbuh di bawah sesi ini: muat ulang supaya SEMUA tab
        // membaca sesi yang baru, bukan sisa render lama.
        window.location.reload();
        return;
      }
      setHasilData("Dataset sudah aktif — data tidak dibangun ulang.");
      await muatStatus();
      await muatBukti();
    } catch (e: any) {
      const detail = e instanceof ApiError && e.detail ? e.detail : null;
      setPesan(detail ?? String(e?.message ?? e));
    } finally {
      setBusy(null);
    }
  }

  async function onPerpanjang() {
    if (!token || busySesi !== null) return;
    setBusySesi("tambah");
    setPesan(null);
    try {
      const r = await extendDemoSession(token, 30);
      setSesi(r as StatusSesiDemo);
      setTickSesi(0);
      setHasilData(`Sesi diperpanjang 30 menit — sisa ${formatSisa(r?.remaining_seconds ?? 0)}.`);
    } catch (e: any) {
      setPesan(String(e?.message ?? e));
    } finally {
      setBusySesi(null);
    }
  }

  async function onAkhiri() {
    if (!token || busySesi !== null) return;
    setBusySesi("tutup");
    setPesan(null);
    try {
      await endDemoSession(token);
      // Data sesi dibersihkan server; muat ulang supaya semua tab jujur kosong.
      window.location.reload();
    } catch (e: any) {
      setPesan(String(e?.message ?? e));
      setBusySesi(null);
    }
  }

  async function onBangunUlang() {
    if (!token || busy !== null) return;
    setBusy("bangun");
    setPesan(null);
    try {
      const r = (await rebuildDemoTemplate(token)) as RebuildSummary;
      setHasilData(rebuildLine(r));
      setPeringatanData(rebuildWarning());
      // Data diganti seluruhnya: muat ulang supaya SEMUA tab membaca baris baru,
      // bukan sisa render lama (sama seperti tombol "Muat Demo").
      window.location.reload();
    } catch (e: any) {
      const detail = e instanceof ApiError && e.detail ? e.detail : null;
      setPesan(detail ?? String(e?.message ?? e));
      setBusy(null);
    }
  }

  async function onJalankan() {
    if (!token || !bolehJalankan || busy !== null) return;
    setBusy("agent");
    setPesan(null);
    setHasilAgent(null);
    setLangkahHidup([]);
    setGalatAliran(null);

    // Kanal kemajuan dibuka SEBELUM POST (29 Okt 2026). Urutannya penting:
    // kanal harus ada saat pipeline mulai menyiarkan langkah pertama. Server
    // mengirim `: siap` begitu kanal terbuka, jadi kita menunggu penanda itu —
    // dengan batas 2 detik supaya proxy yang memblokir streaming tidak
    // menahan tombol yang seharusnya tetap berfungsi seperti dulu.
    const runToken = buatTokenJalankan();
    const kendali = new AbortController();
    // Penjaga diam: kalau server tidak menjawab dalam 3 menit (mis. proses
    // di-restart di tengah putaran), tombol tidak boleh tertinggal "berjalan"
    // selamanya — operator harus tahu ia boleh mencoba lagi.
    const penjaga = setTimeout(() => {
      kendali.abort();
      setGalatAliran("tidak ada jawaban dalam 3 menit — putaran dihentikan dari peramban");
      setPesan("Putaran tidak menjawab dalam 3 menit. Periksa Agent Log sebelum mencoba lagi.");
      setBusy(null);
    }, 180_000);
    let galatTercatat = false;
    const siap = new Promise<void>((selesai) => {
      void streamDemoAgent(token, runToken, {
        signal: kendali.signal,
        onSiap: () => selesai(),
        onLangkah: (langkah) => setLangkahHidup((sebelum) => [...sebelum, langkah]),
      })
        .catch((e: unknown) => {
          galatTercatat = true;
          if (!kendali.signal.aborted) setGalatAliran(pesanAliran(e));
        })
        .finally(() => {
          selesai();
          // Kanal yang tertutup SEBELUM kita menutupnya = server berhenti
          // menyiarkan sementara POST masih berjalan. Tanpa satu baris pun,
          // terminal membeku dan operator mengira putaran masih berjalan.
          const catatan = catatanAliranPutus({
            dibatalkan: kendali.signal.aborted,
            galatTercatat,
          });
          if (catatan) setGalatAliran(catatan);
        });
    });
    await Promise.race([siap, new Promise<void>((selesai) => setTimeout(selesai, 2000))]);

    try {
      // Sesi WAJIB hidup sebelum agent dijalankan: server menolak 409 dan
      // keputusan harus terikat sesi. Sebelum ini panel membiarkan operator
      // menekan tombol setelah "Akhiri sesi"/sesi kedaluwarsa, lalu ia hanya
      // membaca 409 dan mengira fiturnya rusak (terukur 28 Okt 2026). Sesi
      // dibuka di sini SEKALI, dengan `replace:false`, supaya data yang ada
      // tidak dibangun ulang tanpa diminta.
      let sesiId = sesi?.session_id ?? null;
      if (!sesiId) {
        // Tanya server dulu SEBELUM membuka sesi. `startDemoSession` tanpa sesi
        // aktif akan MEMBANGUN template baru, dan jangkar waktunya menjadi
        // "sekarang" — jam demo seolah di-restart hanya karena menekan
        // Jalankan agent (terukur 28 Okt 2026 saat demo: panel tidak memegang
        // id sesi walau server masih punya sesi aktif).
        const aktif = (await fetchDemoSession(token)) as StatusSesiDemo;
        if (aktif?.active !== false && aktif?.session_id) {
          setSesi(aktif);
          setTickSesi(0);
          sesiId = aktif.session_id;
        }
      }
      if (!sesiId) {
        const baru = (await startDemoSession(token, undefined, {
          mode: modeSesi(sesi) ?? "realtime",
        })) as StatusSesiDemo;
        if (baru?.session_id) {
          setSesi(baru);
          setTickSesi(0);
          sesiId = baru.session_id;
        }
      }
      const hasil = await runDemoAgent(token, {
        // Komoditas WAJIB disebut: tidak ada lagi mode "semua komoditas" di
        // panel, supaya satu klik = satu komoditas yang bisa diperiksa.
        commodity: komoditas,
        // Fase 2 MG: analisis dijalankan ATAS SESI yang sedang dipilih panel,
        // dan modenya ikut dikirim supaya server bisa menolak bila berbeda.
        demoSession: sesiId ?? undefined,
        mode: modeSesi(sesi) ?? "realtime",
        // Token yang sama dengan kanal di atas: server menyiarkan langkah ke
        // kanal ini sementara POST berjalan. Tanpa token, putaran berjalan
        // persis seperti sebelumnya (tanpa siaran).
        runToken,
      });
      // Ringkasan dibaca dari payload server (created/skipped). Backend lama
      // belum mengirim kedua kunci itu; tanpa cadangan, putaran yang BERHASIL
      // tampak seperti tidak terjadi apa-apa (gejala 28 Okt 2026: "tidak bisa
      // menjalankan agent" padahal keputusan lahir).
      setHasilAgent(ringkasPutaran(hasil) ?? ringkasSatuKomoditas(hasil, komoditas));
      // Id keputusan dari payload server (created[0] untuk backend baru,
      // decision_id untuk yang lama) → dipakai muatBukti di bawah.
      idBuktiRef.current = idKeputusanPutaran(hasil);
      // Sumber kebenaran blok bukti adalah DB, bukan respons tombol di atas.
      await muatBukti();
      await muatStatus();
    } catch (e: any) {
      const detail = e instanceof ApiError && e.detail ? e.detail : null;
      setPesan(detail ?? String(e?.message ?? e));
    } finally {
      // Kanal ditutup setelah putaran selesai; tanpa ini koneksi menggantung
      // sampai batas 5 menit di server.
      clearTimeout(penjaga);
      kendali.abort();
      setBusy(null);
    }
  }

  const adaBukti = Boolean(bukti?.found && bukti?.decision_id);
  // Satu ringkasan untuk seluruh blok sesi: mode, jangkar, versi dataset, dan
  // label simulasi dihitung di `lib/demo-session.ts` (satu sumber format).
  const ringkasan = ringkasSesi(sesi);

  return (
    <section className="demo-control-section" aria-label="Demo Control">
      {/* 1 ─ Muat demo ---------------------------------------------------- */}
      <section className="card dc-block dc-hero" aria-label="Muat demo">
        <div className="dc-head">
          <span className="dc-stepno" aria-hidden="true">
            1
          </span>
          <h2 className="dc-title">Muat demo</h2>
          <span className={`badge ${adaBaris(status) ? "status-safe" : "status-neutral"}`}>
            {adaBaris(status) ? "data siap" : "belum ada data"}
          </span>
          {sesi?.active && <span className="badge status-safe dc-live">sesi berjalan</span>}
        </div>
        <p className="dc-sub">
          Data dibangun saat tombol ditekan — jangkar waktu = sekarang.
        </p>
        <div className="dc-primary">
          <button
            type="button"
            className="button button-primary dc-prepare"
            onClick={onMuatDemo}
            disabled={!token || !bolehJalankan || busy !== null}
            title="Membangun data demo pada waktu sekarang (realtime), lalu memuatnya"
          >
            {busy === "data" ? "Memuat…" : "Muat Demo"}
          </button>
          {sesi?.active && (
            <div className="dc-chips" aria-label="Konteks dataset">
              {sesi.enforced && (
                <span className="dc-chip" data-testid="demo-session-mode">
                  {labelModeSesi(ringkasan.mode)}
                </span>
              )}
              <span className="dc-chip dc-chip--timer" role="timer" aria-live="off">
                {formatSisa(sisaSekarang)}
              </span>
            </div>
          )}
        </div>
        {ringkasan.baris && <p className="dc-dataset-line">{ringkasan.baris}</p>}
        {sesi?.enforced && (
          <div className="dc-session" data-keadaan={keadaanSesi(sesi)}>
            <p className="dc-session-line" role="status" aria-live="polite">
              {pesanSesi(sesi, tickSesi)}
            </p>
            {sesi.active && (
              <div className="dc-session-actions">
                <button
                  type="button"
                  className="button button-secondary"
                  onClick={onPerpanjang}
                  disabled={!token || busySesi !== null || !bolehJalankan}
                  title="Menambah 30 menit tanpa mengubah data yang sedang berjalan"
                >
                  {busySesi === "tambah" ? "Menambah…" : "Perpanjang 30 menit"}
                </button>
                <button
                  type="button"
                  className="button button-quiet"
                  onClick={onAkhiri}
                  disabled={!token || busySesi !== null || !bolehJalankan}
                  title="Menutup sesi sekarang; data sesi dibersihkan"
                >
                  {busySesi === "tutup" ? "Menutup…" : "Akhiri sesi"}
                </button>
              </div>
            )}
            {sesi.active && peringatanWaktu(sisaSekarang) && (
              <p className="dc-session-warn">{peringatanWaktu(sisaSekarang)}</p>
            )}
          </div>
        )}
        <div className="dc-foot">
          {(!sesi?.enforced || sesi.active) && (
            <p className="dc-status" role="status" aria-live="polite">
              {status ? (
                sesi?.enforced ? (
                  "Data demo siap dipakai selama sesi ini."
                ) : (
                  statusLine(status)
                )
              ) : statusError ? (
                <span className="status-danger">Status data gagal dibaca: {statusError}</span>
              ) : (
                <LoadingState label="Memuat status data demo" />
              )}
            </p>
          )}
        </div>
        <details className="dc-advanced">
          <summary>Opsi lanjutan</summary>
          <DemoRebuild
            // Aksi destruktif = hanya kepala SPPG (sama seperti tombol lain di blok ini);
            // ahli gizi melihat catatan mode baca, bukan tombol yang pasti 403.
            aktif={Boolean(sesi?.active) && bolehJalankan}
            sibuk={busy === "bangun"}
            detik={detik}
            onRebuild={onBangunUlang}
          />
        </details>
        {hasilData && <p className="dc-result">{hasilData}</p>}
        {peringatanData && (
          <details className="dc-note">
            <summary>Yang berubah dan yang tidak</summary>
            <p>{peringatanData}</p>
          </details>
        )}
        {!bolehJalankan && (
          <p className="dc-readonly">
            Mode baca — hanya Kepala SPPG yang boleh memuat data dan menjalankan agent.
          </p>
        )}
      </section>

      {/* 2 ─ Jalankan agent ---------------------------------------------- */}
      <section className="card dc-block" aria-label="Jalankan agent">
        <div className="dc-head">
          <span className="dc-stepno" aria-hidden="true">
            2
          </span>
          <h2 className="dc-title">Jalankan agent</h2>
          <span
            className={`badge ${busy === "agent" ? "status-warning" : "status-neutral"}`}
          >
            {busy === "agent" ? "berjalan" : "siap dijalankan"}
          </span>
        </div>
        <p className="dc-sub">
          Satu putaran pipeline di server; keputusan lahir berstatus <code>proposed</code> —
          tanpa approve otomatis.
        </p>
        <div className="dc-actions">
          <button
            type="button"
            className="button button-primary dc-run"
            onClick={onJalankan}
            disabled={!token || !bolehJalankan || busy !== null || !komoditas}
            aria-busy={busy === "agent"}
            title="Jalankan pipeline agent untuk komoditas yang dipilih, di lokasi SPPG Anda"
          >
            {runButtonLabel(busy === "agent")}
          </button>
          <label className="dc-params">
            <span className="dc-params-label">Komoditas</span>
            <select
              className="dc-select"
              aria-label="Komoditas"
              value={komoditas}
              onChange={(e) => {
                // Penanda keputusan hanya berlaku untuk putaran yang barusan
                // dijalankan; ganti komoditas = bukti dibaca ulang dari DB.
                idBuktiRef.current = null;
                setKomoditas(e.target.value);
              }}
              disabled={!token || !bolehJalankan || busy !== null || daftarKomoditas.length === 0}
              title="Komoditas yang punya data di database — wajib dipilih sebelum menjalankan agent"
            >
              {daftarKomoditas.length === 0 ? (
                // Belum ada daftar dari server: jangan mengarang nama, dan
                // jangan menawarkan "semua" yang sudah dihapus dari panel.
                <option value="">Belum ada komoditas</option>
              ) : (
                daftarKomoditas.map((nama) => (
                  <option key={nama} value={nama}>
                    {nama}
                  </option>
                ))
              )}
            </select>
            <span className="dc-param-sep" aria-hidden="true">
              ·
            </span>
            <span className="dc-param">{locationName || "lokasi akun Anda"}</span>
          </label>
        </div>
        {hasilAgent && (
          <p className="dc-result" role="status">
            {hasilAgent}
          </p>
        )}
        {busy === "agent" && (
          <p className="dc-progress" role="status" aria-live="polite">
            {elapsedLine(detik)}
            <span className="dc-progress-note">
              Langkah disiarkan langsung di blok Bukti agent.
            </span>
          </p>
        )}
        {pesan && (
          <p className="dc-error" role="alert">
            {pesan}
          </p>
        )}
      </section>

      {/* 3 ─ Bukti agent -------------------------------------------------- */}
      <section className="card dc-block dc-proof" aria-label="Bukti agent">
        <div className="dc-head">
          <span className="dc-stepno" aria-hidden="true">
            3
          </span>
          <h2 className="dc-title">Bukti agent</h2>
          <span
            className={`badge ${
              busy === "agent" ? "status-warning" : adaBukti ? "status-safe" : "status-neutral"
            }`}
          >
            {/* Saat putaran berjalan, hitungan jejak TERSIMPAN bukan angka yang
                sedang tumbuh di terminal — menampilkan keduanya berdampingan
                membuat operator membaca dua angka berbeda untuk hal yang
                dikiranya sama. */}
            {busy === "agent"
              ? "putaran berjalan"
              : adaBukti
                ? `${stepNames(bukti).length} langkah tercatat`
                : "belum ada jejak"}
          </span>
        </div>

        {/* Log proses pengambilan data (29 Okt 2026).
            Pemiliknya adalah `DemoProof` (bagian yang sama dengan sembilan
            kartu), supaya saat "Jalankan agent" bagian itu BERGANTI menjadi
            log — bukan log kecil di atas kartu-kartu basi. Salinan di sini
            hanya untuk keadaan yang tidak punya bukti untuk dirender sama
            sekali (belum pernah ada putaran / bukti masih dimuat / gagal
            dibaca): tanpa ini log hilang justru pada putaran PERTAMA. */}
        {(busy === "agent" || galatAliran) && !adaBukti && (
          <AgentRunTerminal
            langkah={langkahHidup}
            aktif={busy === "agent"}
            galat={galatAliran}
          />
        )}

        {buktiError ? (
          <p className="dc-error" role="alert">
            Bukti gagal dibaca: {buktiError}
          </p>
        ) : !bolehLihatBukti ? (
          <p className="dc-readonly">Mode baca — bukti agent hanya untuk peran SPPG.</p>
        ) : bukti === null ? (
          <LoadingState label="Memuat bukti agent" />
        ) : !adaBukti ? (
          <p className="dc-empty">
            {/* Audit data 26 Okt 2026: kalimat lama ("belum ada jejak agent di
                database") terlalu luas — database tetap menyimpan jejak dari
                putaran sebelumnya; yang kosong hanyalah putaran TERAKHIR. */}
            Belum ada putaran agent di mesin ini. Tekan <strong>Jalankan agent</strong>;
            jejak putaran lama tetap ada di tab Agent Log.
          </p>
        ) : (
          <>
            {/* Kesiapan eksekusi (Fase 10 MG butir 3): satu label yang
                membedakan siap / ditahan / karantina / selesai, plus SEBABNYA
                dan langkah berikutnya. Tanpa ini operator harus menebak dari
                status mentah dan alasan hold tidak pernah terbaca. */}
            {kesiapanError && (
              <p className="dc-error" role="alert">
                Kesiapan kasus gagal dibaca: {kesiapanError}
              </p>
            )}
            {kesiapan && (
              <div
                className="dc-readiness"
                data-kind={kesiapan.kind}
                data-testid="demo-case-readiness"
              >
                <p className="dc-readiness-label">
                  Kesiapan kasus: <strong>{kesiapan.label}</strong>
                </p>
                {kesiapan.reasons.length > 0 && (
                  <ul className="dc-readiness-reasons">
                    {kesiapan.reasons.map((alasan) => (
                      <li key={alasan}>{alasan}</li>
                    ))}
                  </ul>
                )}
                {kesiapan.nextStep && (
                  <p className="dc-readiness-next">Langkah: {kesiapan.nextStep}</p>
                )}
              </div>
            )}
            <DemoProof
              run={bukti as AgentRun}
              running={busy === "agent"}
              langkahHidup={langkahHidup}
              galatAliran={galatAliran}
              onOpenDecision={onOpenDecision}
              onOpenAgentLog={onOpenAgentLog}
              onRefresh={() => void muatBukti()}
            />
          </>
        )}
      </section>
    </section>
  );
}
