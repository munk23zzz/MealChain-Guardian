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
  fetchDemoAgentCommodities,
  fetchDemoAgentLastRun,
  fetchDemoDataStatus,
  refreshDemoToToday,
  runDemoAgent,
} from "../lib/api";
import {
  agentReviewLine,
  demoAgentCards,
  defaultCommodity,
  elapsedLine,
  proofFacts,
  runButtonLabel,
  stepChips,
  supervisorLine,
  type AgentRun,
} from "../lib/demo-agent";
import { refreshLine, refreshWarning, statusLine } from "../lib/demo-data";
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
  const langkah = stepChips(run);
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
          <div className="dc-agents" role="list" aria-label="Tujuh agen review">
            {kartu.map((agen) => (
              <article
                className="dc-agent"
                data-state={agen.state}
                role="listitem"
                key={agen.key}
              >
                <div className="dc-agent-head">
                  <span className="dc-agent-dot" aria-hidden="true" />
                  <h3>{agen.label}</h3>
                </div>
                <span className="dc-agent-status">{agen.statusLabel}</span>
                <dl className="dc-agent-meta">
                  <div>
                    <dt>Durasi</dt>
                    <dd>{agen.duration}</dd>
                  </div>
                  <div>
                    <dt>Peringatan</dt>
                    <dd>{agen.warnings}</dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
          <p className="dc-line dc-line--muted">
            {running
              ? "Putaran baru sedang berjalan — ketujuh kartu menyala sampai review menutup putaran."
              : run.agents_run_id
                ? "Status dibaca dari baris review yang tersimpan, bukan dari langkah pipeline."
                : "Review 7 agen belum pernah tercatat untuk keputusan ini."}
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
          {langkah.map((l) => (
            <li className="dc-step" key={`${l.nama}-${l.alat}`}>
              <span className="dc-step-name">{l.nama}</span>
              <span className="dc-step-tool">{l.alat}</span>
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
          <summary>Narasi supervisor (apa adanya dari model)</summary>
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
  const [busy, setBusy] = useState<"data" | "agent" | null>(null);
  const [detik, setDetik] = useState(0);
  const [hasilData, setHasilData] = useState<string | null>(null);
  const [peringatanData, setPeringatanData] = useState<string | null>(null);
  const [pesan, setPesan] = useState<string | null>(null);
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
  }, [muatStatus, muatBukti, muatKomoditas]);

  // Waktu berjalan hanya hidup selama tombol sibuk; tidak ada timer menganggur.
  useEffect(() => {
    if (busy !== "agent") {
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

  async function onJalankan() {
    if (!token || !bolehJalankan || busy !== null) return;
    setBusy("agent");
    setPesan(null);
    try {
      await runDemoAgent(token, komoditas ? { commodity: komoditas } : {});
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

  return (
    <section className="demo-control-section" aria-label="Demo Control">
      {/* 1 ─ Siapkan data ------------------------------------------------ */}
      <section className="card dc-block" aria-label="Siapkan data demo">
        <div className="dc-head">
          <span className="dc-stepno" aria-hidden="true">
            1
          </span>
          <h2 className="dc-title">Siapkan data demo</h2>
          <span className={`badge ${status ? "status-safe" : "status-neutral"}`}>
            {status ? "data siap" : "belum dimuat"}
          </span>
        </div>
        <p className="dc-sub">
          Menyegarkan snapshot kanonik ke tanggal hari ini dan memuat ulang empat
          kasus skrip. Aman dijalankan berulang sebelum demo.
        </p>
        <div className="dc-actions">
          <button
            type="button"
            className="button button-secondary dc-prepare"
            onClick={onSiapkan}
            disabled={!token || !bolehJalankan || busy !== null}
            title="Seeder relatif hari ini + muat ulang 4 kasus skrip"
          >
            {busy === "data" ? "Menyiapkan…" : "Siapkan data demo"}
          </button>
          <p className="dc-status" role="status" aria-live="polite">
            {status ? (
              statusLine(status)
            ) : statusError ? (
              <span className="status-danger">
                Status data gagal dibaca: {statusError}
              </span>
            ) : (
              <LoadingState label="Memuat status data demo" />
            )}
          </p>
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
            {adaBukti ? `${stepChips(bukti).length} langkah tercatat` : "belum ada jejak"}
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
            Belum ada jejak agent di database. Tekan <strong>Jalankan agent</strong> —
            sesudah putaran selesai, langkah yang benar-benar tertulis muncul di sini.
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
