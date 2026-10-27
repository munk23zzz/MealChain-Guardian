"use client";

// Demo Control sederhana (keputusan Roy 2026-10-19).
//
// Bentuknya tiga blok, tanpa Event 1/2/3:
//   1. Siapkan data demo  -> POST /demo/refresh (idempoten; snapshot hari ini)
//   2. Jalankan agent     -> POST /demo/agent/run (beras + lokasi akun sendiri)
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
import { useCallback, useEffect, useState } from "react";

import { LoadingState } from "./LoadingState";
import {
  ApiError,
  endDemoSession,
  extendDemoSession,
  fetchDemoAgentCommodities,
  fetchDemoAgentLastRun,
  fetchDemoDataStatus,
  fetchDemoSession,
  labelModeSesi,
  rebuildDemoTemplate,
  refreshDemoToToday,
  runDemoAgent,
  startDemoSession,
} from "../lib/api";
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
export function DemoProof({
  run,
  running = false,
  onOpenDecision,
  onOpenAgentLog,
  onRefresh,
}: {
  run: AgentRun;
  running?: boolean;
  onOpenDecision?: (decisionId: string) => void;
  onOpenAgentLog?: () => void;
  onRefresh?: () => void;
}) {
  const langkah = stepNames(run);
  const fakta = proofFacts(run);
  const narasi = run.supervisor?.summary ?? null;
  const kartu = demoAgentCards(run, running);
  const adaAgen = kartu.some((k) => k.state !== "idle");

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


      {kartu.length > 0 && (
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
            {running
              ? "Putaran baru sedang berjalan — kesembilan kartu menyala sampai review menutup putaran."
              : run.agents_run_id
                ? "Status dibaca dari baris review yang tersimpan, bukan dari langkah pipeline."
                : "Review sembilan agen belum pernah tercatat untuk keputusan ini."}
          </p>
        </>
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

      <p className="dc-line">{supervisorLine(run.supervisor)}</p>
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
        Mengembalikan angka ke keadaan awal tanpa menutup sesi: batch, keputusan, pesanan,
        bukti, dan ledger dibangun ulang dari template. Terukur 41 detik pada mesin demo
        ini; sediakan waktu sampai sekitar 1 menit di laptop yang lebih lambat.
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
  const [buktiError, setBuktiError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"data" | "agent" | "bangun" | null>(null);
  const [detik, setDetik] = useState(0);
  const [hasilData, setHasilData] = useState<string | null>(null);
  const [peringatanData, setPeringatanData] = useState<string | null>(null);
  const [pesan, setPesan] = useState<string | null>(null);
  // Sesi demo (024/025): status dari SERVER + hitungan mundur lokal yang
  // diselaraskan ulang tiap 20 detik. Tidak ada timer yang "menebak" waktu.
  const [sesi, setSesi] = useState<StatusSesiDemo | null>(null);
  const [tickSesi, setTickSesi] = useState(0);
  const [busySesi, setBusySesi] = useState<"mulai" | "tambah" | "tutup" | null>(null);
  // Pilihan komoditas datang dari DB (GET /demo/agent/commodities). Selama
  // daftarnya belum termuat, dropdown kosong — bukan ditebak "beras".
  const [daftarKomoditas, setDaftarKomoditas] = useState<string[]>([]);
  const [komoditas, setKomoditas] = useState<string>("");

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
      setBukti(await fetchDemoAgentLastRun(token));
    } catch (e: any) {
      setBukti(null);
      setBuktiError(String(e?.message ?? e));
    }
  }, [token, bolehLihatBukti]);

  const muatKomoditas = useCallback(async () => {
    if (!token || !bolehLihatBukti) return;
    try {
      const r = await fetchDemoAgentCommodities(token);
      const daftar: string[] = Array.isArray(r?.commodities) ? r.commodities : [];
      setDaftarKomoditas(daftar);
      setKomoditas((sekarang) =>
        sekarang && daftar.includes(sekarang) ? sekarang : defaultCommodity(daftar)
      );
    } catch {
      // Daftar gagal dimuat bukan alasan mengarang pilihan: dropdown tetap
      // kosong dan tombol agent memakai bawaan backend (beras).
      setDaftarKomoditas([]);
    }
  }, [token, bolehLihatBukti]);

  useEffect(() => {
    void muatStatus();
    void muatBukti();
    void muatKomoditas();
    void muatSesi();
  }, [muatStatus, muatBukti, muatKomoditas, muatSesi]);

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

  async function onSiapkan() {
    if (!token || busy !== null) return;
    setBusy("data");
    setPesan(null);
    try {
      // Mode sesi (024/025): tombol ini MEMULAI sesi — membuatnya, menyemai
      // data, dan menyalakan jendela waktu. Tanpa mode sesi, perilakunya tetap
      // seperti dulu (POST /demo/refresh) supaya pengembangan tidak berubah.
      if (sesi?.enforced) {
        // Fase 2 MG: tombol ini memulai sesi REPLAY — jangkar kanon 8 Okt yang
        // bisa direproduksi. Mode dikirim eksplisit; tombol realtime datang
        // bersama dua tombol Demo Control (Fase 10).
        const r = await startDemoSession(token, undefined, { mode: "replay" });
        setSesi(r as StatusSesiDemo);
        setTickSesi(0);
        if (r?.created) {
          // Data baru tumbuh di bawah sesi ini: muat ulang halaman agar SEMUA
          // tab membaca data sesi, bukan sisa render lama.
          window.location.reload();
          return;
        }
        setHasilData("Sesi demo sudah berjalan — data tidak di-reset.");
        await muatStatus();
        await muatBukti();
        return;
      }
      const r = await refreshDemoToToday(token);
      setHasilData(refreshLine(r));
      // Peringatan backend ditampilkan APA ADANYA — bukan diringkas klien.
      setPeringatanData(
        typeof r?.warning === "string" && r.warning ? r.warning : refreshWarning()
      );
      await muatStatus();
      await muatBukti();
    } catch (e: any) {
      setPesan(String(e?.message ?? e));
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
      // bukan sisa render lama (sama seperti tombol "Siapkan data demo").
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
    try {
      await runDemoAgent(token, {
        commodity: komoditas || undefined,
        // Fase 2 MG: analisis dijalankan ATAS SESI yang sedang dipilih panel.
        demoSession: sesi?.session_id ?? undefined,
      });
      // Sumber kebenaran blok bukti adalah DB, bukan respons tombol di atas.
      await muatBukti();
      await muatStatus();
    } catch (e: any) {
      const detail = e instanceof ApiError && e.detail ? e.detail : null;
      setPesan(detail ?? String(e?.message ?? e));
    } finally {
      setBusy(null);
    }
  }

  const adaBukti = Boolean(bukti?.found && bukti?.decision_id);
  // Satu ringkasan untuk seluruh blok sesi: mode, jangkar, versi dataset, dan
  // label simulasi dihitung di `lib/demo-session.ts` (satu sumber format).
  const ringkasan = ringkasSesi(sesi);

  return (
    <section className="demo-control-section" aria-label="Demo Control">
      {/* 1 ─ Siapkan data ------------------------------------------------ */}
      <section className="card dc-block" aria-label="Siapkan data demo">
        <div className="dc-head">
          <span className="dc-stepno" aria-hidden="true">
            1
          </span>
          <h2 className="dc-title">Siapkan data demo</h2>
          <span className={`badge ${adaBaris(status) ? "status-safe" : "status-neutral"}`}>
            {adaBaris(status) ? "data siap" : "belum ada data"}
          </span>
        </div>
        <p className="dc-sub">
          Mengisi data demo untuk satu jendela waktu: hari ini, empat skenario uji,
          dan hitungan mundur sesi. Menekan lagi saat sesi berjalan tidak memuat
          ulang data — sesi yang sama diteruskan.
        </p>
        {sesi?.enforced && (
          <div className="dc-session" data-keadaan={keadaanSesi(sesi)}>
            <p className="dc-session-line" role="status" aria-live="polite">
              {pesanSesi(sesi, tickSesi)}
            </p>
            {sesi.active && (
              <p className="dc-session-count" role="timer" aria-live="off">
                {formatSisa(sisaSekarang)}
              </p>
            )}
            {/* Fase 2 MG: mode + jangkar ditampilkan APA ADANYA dari sesi.
                Tanpa ini operator tidak bisa membedakan "data kanon 8 Okt"
                dari "sesi yang baru dibuka hari ini" — dua dataset berbeda
                yang angkanya tidak boleh dibandingkan diam-diam. */}
            {sesi.active && (
              <div className="dc-session-dataset">
                <p className="dc-session-mode" data-testid="demo-session-mode">
                  Mode: <strong>{labelModeSesi(ringkasan.mode)}</strong>
                  {ringkasan.anchor ? <> · Jangkar: {ringkasan.anchor}</> : null}
                  {ringkasan.datasetVersion ? (
                    <>
                      {" "}
                      · Dataset: <code>{ringkasan.datasetVersion}</code>
                    </>
                  ) : null}
                </p>
                {ringkasan.baris && (
                  <p className="dc-session-summary">{ringkasan.baris}</p>
                )}
                {/* Label jujur: angka suhu pada dataset demo dibangun ulang
                    oleh penyemai, bukan bacaan sensor. */}
                <p className="dc-session-sim">
                  Dataset demo memakai suhu simulasi, bukan sensor aktif.
                </p>
              </div>
            )}
            {sesi.active && peringatanWaktu(sisaSekarang) && (
              <p className="dc-session-warn">{peringatanWaktu(sisaSekarang)}</p>
            )}
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
          </div>
        )}
        <DemoRebuild
          // Aksi destruktif = hanya kepala SPPG (sama seperti tombol lain di blok ini);
          // ahli gizi melihat catatan mode baca, bukan tombol yang pasti 403.
          aktif={Boolean(sesi?.active) && bolehJalankan}
          sibuk={busy === "bangun"}
          detik={detik}
          onRebuild={onBangunUlang}
        />
        <div className="dc-actions">
          <button
            type="button"
            className="button button-secondary dc-prepare"
            onClick={onSiapkan}
            disabled={!token || !bolehJalankan || busy !== null}
            title="Mengisi data demo hari ini dan memuat empat skenario uji"
          >
            {busy === "data" ? "Menyiapkan…" : "Siapkan data demo"}
          </button>
          {(!sesi?.enforced || sesi.active) && (
            <p className="dc-status" role="status" aria-live="polite">
              {status ? (
                sesi?.enforced ? (
                  "Data demo siap dipakai selama sesi ini."
                ) : (
                  statusLine(status)
                )
              ) : statusError ? (
              <span className="status-danger">
                Status data gagal dibaca: {statusError}
              </span>
            ) : (
                <LoadingState label="Memuat status data demo" />
              )}
            </p>
          )}
        </div>
        {hasilData && <p className="dc-result">{hasilData}</p>}
        {peringatanData && (
          <details className="dc-note">
            <summary>Yang berubah dan yang tidak</summary>
            <p>{peringatanData}</p>
          </details>
        )}
        {!bolehJalankan && (
          <p className="dc-readonly">
            Mode baca — hanya kepala SPPG yang boleh menyiapkan data dan menjalankan
            agent.
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
          Satu putaran penuh pipeline di server: deteksi, verifikasi, prakiraan,
          optimasi, keputusan, lalu narasi supervisor. Tidak ada approve otomatis —
          keputusan lahir berstatus <code>proposed</code>.
        </p>
        <div className="dc-actions">
          <button
            type="button"
            className="button button-primary dc-run"
            onClick={onJalankan}
            disabled={!token || !bolehJalankan || busy !== null}
            aria-busy={busy === "agent"}
            title="Jalankan pipeline agent untuk komoditas beras di lokasi SPPG Anda"
          >
            {runButtonLabel(busy === "agent")}
          </button>
          <label className="dc-params">
            <span className="dc-params-label">Komoditas</span>
            <select
              className="dc-select"
              aria-label="Komoditas"
              value={komoditas}
              onChange={(e) => setKomoditas(e.target.value)}
              disabled={!token || !bolehJalankan || busy !== null || daftarKomoditas.length === 0}
              title="Daftar komoditas yang punya data di database"
            >
              {daftarKomoditas.length === 0 ? (
                <option value="">belum ada pilihan</option>
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
        {busy === "agent" && (
          <p className="dc-progress" role="status" aria-live="polite">
            {elapsedLine(detik)}
            <span className="dc-progress-note">
              Langkah ditulis sekaligus saat putaran selesai — biasanya sekitar satu
              menit.
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
          <span className={`badge ${adaBukti ? "status-safe" : "status-neutral"}`}>
            {adaBukti ? `${stepNames(bukti).length} langkah tercatat` : "belum ada jejak"}
          </span>
        </div>

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
            Belum ada putaran agent yang terekam pada mesin ini. Tekan{" "}
            <strong>Jalankan agent</strong> — sesudah putaran selesai, langkah yang
            benar-benar tertulis muncul di sini. Jejak dari keputusan lama tetap bisa
            dibaca di tab Agent Log.
          </p>
        ) : (
          <DemoProof
            run={bukti as AgentRun}
            running={busy === "agent"}
            onOpenDecision={onOpenDecision}
            onOpenAgentLog={onOpenAgentLog}
            onRefresh={() => void muatBukti()}
          />
        )}
      </section>
    </section>
  );
}
