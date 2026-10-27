// Panel review sembilan agen di tab Agent Log (P5): tujuh analitik + supervisor + verifier.
// Satu run = sembilan kartu (urutan pipeline: worker → SUPERVISE → audit). Kartu tanpa
// baris trace ditulis "Belum tercatat" — bukan diisi angka/enum karangan.
//
// Supervisor kini kartu kelas satu (datanya dari `run.supervisor`); blok di bawah grid
// hanya memuat veto & kontradiksi yang tidak muat di kartu, supaya narasinya tidak
// tercetak dua kali.

import {
  latestSwarmRun,
  shortRunId,
  supervisorSummary,
  swarmCards,
} from "../lib/agent-swarm";

export default function AgentSwarmPanel({
  steps,
  decisionId = null,
}: {
  steps: any[];
  /** null = belum ada keputusan yang dipilih. */
  decisionId?: string | null;
}) {
  const run = latestSwarmRun(steps);
  if (!run) {
    return (
      <p className="empty-state">
        {decisionId
          ? "Belum ada review sembilan agen untuk keputusan ini."
          : "Pilih keputusan dulu untuk melihat review sembilan agen."}
      </p>
    );
  }

  const cards = swarmCards(run);
  const summary = supervisorSummary(run);
  const recorded = cards.filter((card) => card.row).length;
  const warningsOf = (row: any): string[] =>
    Array.isArray(row?.output_summary?.warnings)
      ? row.output_summary.warnings.filter(
          (warning: unknown) => typeof warning === "string"
        )
      : [];

  return (
    <section className="swarm-panel" aria-labelledby="swarm-title">
      <div className="swarm-head">
        <div>
          <p className="swarm-kicker">Review sembilan agen · advisory</p>
          <h2 id="swarm-title">Pemeriksaan lintas domain</h2>
        </div>
        <div className="swarm-meta">
          <span className="swarm-run">run {shortRunId(run.runId)}</span>
          <span className="swarm-count">
            {recorded}/{cards.length} tercatat
          </span>
        </div>
      </div>
      <p className="swarm-note">
        Tujuh worker membaca data dan memeriksa keputusan deterministik; supervisor
        merangkum temuannya, verifier mengaudit hasilnya. Panel ini bukan approval dan
        tidak mengeksekusi apa pun.
      </p>

      <div className="swarm-grid">
        {cards.map((card) => (
          <article
            key={card.key}
            className="swarm-card"
            data-state={card.status}
            aria-labelledby={`swarm-agent-${card.key}`}
          >
            <div className="swarm-card-head">
              <span className="swarm-dot" aria-hidden="true" />
              <h3 id={`swarm-agent-${card.key}`}>{card.label}</h3>
              <span className="swarm-status">{card.statusLabel}</span>
            </div>
            <dl className="swarm-facts">
              <div>
                <dt>Durasi</dt>
                <dd>{card.duration}</dd>
              </div>
              <div>
                <dt>Confidence</dt>
                <dd>{card.confidence}</dd>
              </div>
              <div>
                <dt>Sitasi</dt>
                <dd>{card.citations}</dd>
              </div>
              <div>
                <dt>Peringatan</dt>
                <dd>{card.warningCount === null ? "—" : card.warningCount}</dd>
              </div>
            </dl>
            {card.row ? (
              <details className="swarm-detail">
                <summary>Detail {card.label}</summary>
                <p className="swarm-summary-text">{card.summary}</p>
                {warningsOf(card.row).length > 0 ? (
                  <ul className="swarm-warnings">
                    {warningsOf(card.row).map((warning, index) => (
                      <li key={index}>{warning}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="swarm-muted">Tidak ada peringatan.</p>
                )}
                {card.row.output_summary?.facts ? (
                  <pre className="swarm-facts-json">
                    {JSON.stringify(card.row.output_summary.facts)}
                  </pre>
                ) : null}
              </details>
            ) : (
              <p className="swarm-muted">Baris trace agen ini belum tercatat.</p>
            )}
          </article>
        ))}
      </div>

      {/* Veto & kontradiksi dari baris SUPERVISE. Narasi tidak diulang di sini:
          ia sudah ada di detail kartu Supervisor. */}
      <div className="swarm-supervisor">
        <div className="swarm-card-head">
          <h3>Catatan supervisor</h3>
          <span className="swarm-status">{summary.status}</span>
        </div>
        <dl className="swarm-facts swarm-facts-wide">
          <div>
            <dt>Safety veto</dt>
            <dd>{summary.veto}</dd>
          </div>
          <div>
            <dt>Kontradiksi</dt>
            <dd>{summary.contradictions}</dd>
          </div>
        </dl>
      </div>
    </section>
  );
}
