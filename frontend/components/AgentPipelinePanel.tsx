"use client";

// AgentPipelinePanel — banner keadaan trace + strip sembilan tahap
// (dokumen `06-agent-log.md` §2.3–2.4, §2.6–2.7).
//
// Aturan yang tidak boleh disederhanakan:
// - banner tiga keadaan (belum dimuat / kosong / ada) dengan kalimat kejujuran;
// - chip membawa keadaan sendiri + penanda waktu/lambat (ikon, bukan teks);
// - ACT yang hanya punya blok ledger TIDAK ditulis "belum tercatat";
// - provenance (apa yang tercatat) dipisah dari penilaian (benar/salah).

import { useId, useState } from "react";

import {
  buildPipeline,
  jamWib,
  provenanceLine,
  stageMeta,
  stageStateLabel,
  stageStateShort,
  traceBanner,
  type LedgerBlockView,
  type StageView,
  type TraceStep,
} from "../lib/agent-activity";

function nadaTahap(state: StageView["state"]): string {
  if (state === "present" || state === "ledger") return "aa-stage-safe";
  if (state === "absent") return "aa-stage-warning";
  return "aa-stage-muted";
}

export default function AgentPipelinePanel({
  decisionId = null,
  steps,
  ledger,
  onOpenEvidence = null,
  stageFilter = null,
  onStageFilter = null,
}: {
  decisionId?: string | null;
  steps: TraceStep[] | null;
  ledger: LedgerBlockView[] | null;
  onOpenEvidence?: (() => void) | null;
  /** Tahap yang sedang menyaring langkah rinci; `null` = tanpa saringan. */
  stageFilter?: string | null;
  onStageFilter?: ((code: string | null) => void) | null;
}) {
  const id = useId();
  const [terbuka, setTerbuka] = useState<string | null>(null);
  const banner = traceBanner(decisionId, steps);
  const stages = buildPipeline({ steps, ledger });
  const provenance = provenanceLine(steps);
  const lambat = stages.filter((s) => s.slow);
  const aktif = stages.find((s) => s.code === terbuka) ?? null;
  const act = stages.find((s) => s.code === "ACT") ?? null;
  const meta = aktif ? stageMeta(aktif.code) : null;

  return (
    <div className="aa-pipeline">
      <div
        className={`aa-banner aa-banner-${banner.state} aa-tone-${banner.tone}`}
        role="status"
      >
        <p className="aa-banner-label">{banner.label}</p>
        <p className="aa-banner-sentence">{banner.sentence}</p>
        {banner.state === "present" && onOpenEvidence ? (
          <button type="button" className="aa-link" onClick={onOpenEvidence}>
            Nilai benar/salah di Safety &amp; Evidence →
          </button>
        ) : null}
      </div>

      {banner.state === "no_decision" ? null : (
        <>
          <div className="aa-strip-head">
            {lambat.length > 0 ? (
              <p className="aa-slow-note">
                {lambat.length} tahap lebih lambat dari biasanya
              </p>
            ) : null}
            {stageFilter ? (
              <button
                type="button"
                className="aa-link"
                onClick={() => {
                  setTerbuka(null);
                  onStageFilter?.(null);
                }}
              >
                Hapus saringan tahap {stageFilter}
              </button>
            ) : null}
          </div>

          <ol className="aa-strip" aria-label={`${stages.length} tahap pipeline`}>
            {stages.map((tahap, i) => {
              const jam = jamWib(tahap.at);
              const buka = terbuka === tahap.code;
              return (
                <li key={tahap.code} className="aa-stage-item">
                  <button
                    type="button"
                    className={`aa-stage ${nadaTahap(tahap.state)}${
                      buka ? " aa-stage-open" : ""
                    }`}
                    aria-expanded={buka}
                    aria-pressed={stageFilter === tahap.code}
                    aria-controls={`${id}-rincian`}
                    onClick={() => {
                      // Klik chip = dua hal sekaligus (Tahap 4): buka catatan
                      // tahap itu DAN saring langkah rinci di bawah ke tahap
                      // yang sama. Klik kedua menutup keduanya.
                      setTerbuka(buka ? null : tahap.code);
                      onStageFilter?.(buka ? null : tahap.code);
                    }}
                    title={`${tahap.code} · ${tahap.label} — ${stageStateLabel(
                      tahap.state
                    )}${jam ? ` · ${jam} WIB` : ""}${
                      tahap.slow ? " · lebih lambat dari biasanya" : ""
                    }`}
                  >
                    <span className="aa-stage-no" aria-hidden="true">
                      {i + 1}
                    </span>
                    <span className="aa-stage-code">{tahap.code}</span>
                    <span className="aa-stage-state">
                      {stageStateShort(tahap.state)}
                    </span>
                    <span className="aa-stage-marks" aria-hidden="true">
                      {jam ? <i className="aa-mark-time" /> : null}
                      {tahap.slow ? <i className="aa-mark-slow" /> : null}
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>

          {act ? (
            <p
              className={`aa-act-line${
                act.state === "ledger" ? " aa-act-line-ledger" : ""
              }`}
            >
              {act.state === "ledger"
                ? `${act.note.replace(/\.$/, "")} · dasar ledger_blocks (action = execute)`
                : act.state === "present"
                ? "ACT punya baris trace sendiri di jejak agent."
                : act.note}
            </p>
          ) : null}

          <p className="aa-strip-legend">
            <span className="aa-lg">
              <i className="aa-mark-time" aria-hidden="true" /> punya waktu
              tercatat
            </span>
            <span className="aa-lg">
              <i className="aa-mark-slow" aria-hidden="true" /> lebih lambat dari
              biasanya
            </span>
          </p>

          <div
            className="aa-detail"
            id={`${id}-rincian`}
            role="region"
            aria-live="polite"
          >
            {aktif ? (
              <>
                <p className="aa-detail-title">
                  <strong>{aktif.code}</strong> · {aktif.label}
                </p>
                <p className="aa-detail-note">
                  {meta?.detail ?? aktif.note}
                </p>
                <p className="aa-detail-meta">
                  {aktif.tool}
                  {jamWib(aktif.at) ? ` · ${jamWib(aktif.at)} WIB` : ""}
                  {aktif.state === "ledger" ? " · dasar: ledger_blocks" : ""}
                </p>
              </>
            ) : (
              <p className="aa-detail-note">
                Klik satu tahap untuk melihat tool yang dijalankan dan catatannya.
              </p>
            )}
          </div>

          {provenance ? (
            <p className="aa-provenance">Catatan langkah agent · {provenance}</p>
          ) : null}
        </>
      )}
    </div>
  );
}
