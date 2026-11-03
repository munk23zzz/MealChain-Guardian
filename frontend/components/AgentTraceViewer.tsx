// AgentTraceViewer — activity log dari trace AKTUAL (design.md §3.4).
// Data ditarik dari GET /decisions/{id}/traces (AgentTrace DB), bukan
// log buatan. Timestamp ditampilkan UTC agar bisa dibandingkan lintas hop.
// Restyle Stitch: console terminal gelap (#0F172A) + accent #2DD4BF.

import { formatTraceWib } from "../lib/datetime";
import {
  catatanAwalJejak,
  isNewStep,
  isRunningStep,
  jejakSebelumKeputusan,
  stepAgeLabel,
  stepDurationLabel,
} from "../lib/agent-trace";
import { toolLabel } from "../lib/bahasa";

// Icon status langkah — inline SVG, bukan emoji (DESIGN.md).
function StepIcon({ done }: { done?: boolean }) {
  return done ? (
    <svg className="agent-console-ico" viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">
      <circle cx="8" cy="8" r="7" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path d="M4.5 8.5l2.2 2.2L11 6" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ) : (
    <svg className="agent-console-ico" viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">
      <circle cx="8" cy="8" r="7" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="8" cy="8" r="2" fill="currentColor" />
    </svg>
  );
}

export default function AgentTraceViewer({
  steps,
  decisionId = null,
  createdAt = null,
  now = null,
  stageFilter = null,
  onClearStageFilter = null,
}: {
  steps: any[];
  /** Keputusan yang sedang dipilih; null = belum ada yang dipilih. */
  decisionId?: string | null;
  /** `created_at` keputusan terpilih — dipakai memeriksa urutan waktu jejak. */
  createdAt?: string | null;
  /** Jam klien (pola yang sama dengan halaman lain): dipakai HANYA untuk umur
   *  langkah. null = jam belum siap → umur tidak diklaim, jejaknya tetap utuh. */
  now?: Date | null;
  /** Saringan tahap dari chip strip pipeline (Tahap 4 redesign); null = semua. */
  stageFilter?: string | null;
  onClearStageFilter?: (() => void) | null;
}) {
  if (!steps || steps.length === 0) {
    // Dua keadaan yang BERBEDA, dua pesan yang berbeda (WS-C, QA 16 Okt).
    // Dulu satu pesan untuk keduanya: sebelum pengguna memilih apa pun, layar
    // sudah mengklaim "belum ada langkah agent ... untuk keputusan ini" —
    // seolah ada keputusan yang dipilih dan jejaknya hilang.
    return (
      <p className="empty-state">
        {decisionId
          ? "Belum ada langkah agent yang tercatat untuk keputusan ini."
          : "Pilih keputusan dulu untuk melihat jejak langkah agent."}
      </p>
    );
  }
  const last = steps[steps.length - 1];
  // Saringan tahap (Tahap 4 redesign): daftar langkah mengikuti chip yang diklik.
  // Catatan sebab-akibat (`sebelum`, `awalTakLengkap`) tetap dihitung dari SELURUH
  // jejak — yang disaring hanya yang ditampilkan, bukan yang dinilai.
  const tampil = stageFilter
    ? (steps as any[]).filter(
        (s) => String(s?.step_name ?? "").toLowerCase() === stageFilter.toLowerCase(),
      )
    : (steps as any[]);
  const umur = stepAgeLabel(last?.step_at, now);
  // Sebagian data demo mencatat langkah LEBIH DULU daripada keputusannya
  // dibuat. Selama itu terjadi, halaman menyebutnya — bukan menyembunyikannya
  // di balik jam tanpa tanggal.
  const sebelum = jejakSebelumKeputusan(createdAt, steps);
  const awalTakLengkap = catatanAwalJejak(steps);
  const adaYangBaru = Boolean(umur) && Boolean(isNewStep(last?.step_at, now));
  return (
    <div className="agent-console">
      {/* Chrome ala jendela terminal Stitch (agent_activity_log_traces) */}
      <div className="agent-console-bar">
        <span className="agent-console-dots" aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
        <span className="agent-console-title">agent-core@mealchain:~ — trace log</span>
        {/* Umur langkah terakhir — fakta waktu dari step_at, bukan klaim bahwa
            agen masih bekerja (itu hanya boleh datang dari data langkahnya). */}
        {umur ? (
          <span className="agent-console-age" data-live={adaYangBaru ? "true" : undefined}>
            <span className="agent-console-age-dot" aria-hidden="true" />
            {umur}
          </span>
        ) : null}
      </div>
      {sebelum.jumlah > 0 ? (
        <p className="trace-causality" role="note">
          {sebelum.jumlah === steps.length
            ? `Seluruh ${sebelum.jumlah} langkah bertanggal SEBELUM keputusan ini dibuat`
            : `${sebelum.jumlah} dari ${steps.length} langkah bertanggal SEBELUM keputusan ini dibuat`}
          {sebelum.pertama && createdAt
            ? ` (langkah pertama ${formatTraceWib(sebelum.pertama, now ?? undefined)}, keputusan dibuat ${formatTraceWib(createdAt, now ?? undefined)})`
            : ""}
          . Waktunya berasal dari data demo, jadi urutan ini bukan urutan kejadian
          sebenarnya.
        </p>
      ) : null}
      {awalTakLengkap ? (
        <p className="trace-causality" role="note">
          {awalTakLengkap}
        </p>
      ) : null}
      {stageFilter ? (
        <p className="trace-filter" role="status" aria-atomic="true">
          {tampil.length > 0
            ? `Saringan tahap ${stageFilter}: ${tampil.length} dari ${steps.length} langkah.`
            : `Tidak ada langkah tahap ${stageFilter} di jejak ini (${steps.length} langkah tercatat).`}
          {onClearStageFilter ? (
            <button type="button" className="aa-link" onClick={onClearStageFilter}>
              Tampilkan semua langkah
            </button>
          ) : null}
        </p>
      ) : null}
      {tampil.length > 0 ? (
      <ol className="trace-timeline">
        {tampil.map((s: any, i: number) => {
          const berjalan = isRunningStep(s);
          const baru =
            !berjalan && i === tampil.length - 1 && isNewStep(s.step_at, now);
          const durasi = stepDurationLabel(s);
          const toolHuman = toolLabel(s.tool_called);
          const sudahRingkas = typeof s.output_summary?.summary === "string" && Boolean(s.output_summary.summary.trim());
          return (
            <li key={i} className="trace-item">
              {/* Satu langkah = satu baris ringkas yang bisa dibuka (Tahap 5
                  redesign, 29 Okt 2026). `<details>` asli, bukan state React:
                  bisa dibuka papan ketik, terbaca pembaca layar, dan tetap
                  berfungsi tanpa JavaScript. Isi mentah tidak hilang — hanya
                  tidak lagi mendorong sepuluh baris ke bawah layar. */}
              <details
                className={`trace-step step-${s.step_name}`}
                data-state={berjalan ? "berjalan" : baru ? "baru" : "selesai"}
              >
                <summary className="trace-step-head">
                  <span className="trace-dot" aria-hidden="true" />
                  <StepIcon done={!berjalan} />
                  <span className="trace-step-name">{s.step_name}</span>
                  {berjalan ? (
                    <span className="trace-chip trace-chip-running">sedang berjalan</span>
                  ) : baru ? (
                    <span className="trace-chip trace-chip-new">baru masuk</span>
                  ) : null}
                  {durasi ? <span className="trace-duration">{durasi}</span> : null}
                  {/* Tanggal WAJIB ikut (audit 29 Okt 2026): jam saja membuat
                      langkah kemarin terbaca sebagai langkah hari ini. Nilai ISO
                      utuh tetap ada di `title` untuk yang butuh presisi. */}
                  <time dateTime={s.step_at ?? undefined} title={s.step_at ?? undefined}>
                    {formatTraceWib(s.step_at, now ?? undefined)}
                  </time>
                  <span className="trace-chevron" aria-hidden="true" />
                </summary>
                <div className="trace-step-body">
                  {/* Alat internal hanya ditampilkan bila punya sebutan manusia.
                      Slug seperti `evaluate_safety` dulu tampil apa adanya dan
                      terbaca sebagai kebocoran istilah teknis; yang tidak dikenal
                      disembunyikan, bukan dibiarkan. */}
                  {toolHuman !== null && toolHuman !== s.tool_called ? (
                    <div className="trace-tool">{toolHuman}</div>
                  ) : null}
                  {/* W-5: nomor PO yang diterbitkan langkah ACT. Sebelumnya hanya
                      nama tool yang tampil, sehingga PO yang terbit tidak bisa
                      ditunjukkan dari jejak agent. */}
                  {s.step_name === "ACT" && s.output_summary?.po_number ? (
                    <div className="trace-po">
                      PO {s.output_summary.po_number} diterbitkan (mock SAP)
                    </div>
                  ) : null}
                  {s.step_name === "SUPERVISE" &&
                    s.output_summary?.provider && (
                      <div className="trace-model">
                        Model: {s.output_summary.provider}
                      </div>
                    )}
                  {/* Audit data 26 Okt 2026: jejak membawa `summary` yang sudah
                      berbentuk kalimat, jadi yang dibaca lebih dulu kalimatnya.
                      JSON mentah tetap ada di balik "Data mentah" supaya tidak ada
                      yang hilang — sekarang SELALU bisa dibuka, termasuk saat
                      kalimatnya tidak ada (dulu JSON langsung tercetak penuh). */}
                  {sudahRingkas ? (
                    <p className="trace-summary">{s.output_summary.summary}</p>
                  ) : null}
                  <details className="trace-raw">
                    <summary>Data mentah</summary>
                    <pre className="trace-output">
                      {JSON.stringify(s.output_summary ?? {})}
                    </pre>
                  </details>
                </div>
              </details>
            </li>
          );
        })}
      </ol>
      ) : null}
    </div>
  );
}
