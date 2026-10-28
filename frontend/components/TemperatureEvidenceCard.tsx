"use client";

// Kartu "Bukti suhu" — TAMPILAN SAJA.
//
// Aturan yang dipegang (Fase 3 MG butir 5): satu-satunya sumber label di sini
// adalah blok `evidence` server (`GET /batches`). Komponen ini tidak menghitung
// ulang kelengkapan bukti, tidak menaikkan status, dan tidak menebak asal log.
//
// Redesign 27 Okt 2026 (permintaan pemilik: hanya bagian ini, hanya frontend).
// Syarat pertama: KONSISTEN dengan design system, bukan tampilan baru yang
// berdiri sendiri. Karena itu kelas yang sudah jadi bahasa halaman ini dipakai
// ulang, bukan ditiru:
//   - `.card` + `.card h2`                   → geometri & tipografi judul kartu
//   - `.board-card-head` + `.board-badge-*`  → kepala kartu + lencana kanan
//   - `.evidence-note`                       → semua catatan
//   - `.board-link`                          → tautan ke tabel lengkap
//   - `.board-list li`                       → geometri baris (border + radius kontrol)
// Yang benar-benar baru hanya yang belum punya padanan di halaman ini: bar
// tersegmen + legenda berangka (komposisi bukti), dan tepi kiri bertone per
// batch supaya baris yang membelokkan alokasi terbaca lebih dulu. Urutan di
// dalam tone yang sama tidak diubah (sort stabil).
//   - Warna hanya dari token: teks peringatan memakai `--warn-ink`, bukan
//     `--status-warning` (tint saja) — ambang kontras grafik 3:1 terpenuhi.

import type { EvidenceRow, EvidenceSummary, SafetyTone } from "../lib/food-safety";
import { evidenceLabel } from "../lib/food-safety";
import styles from "./TemperatureEvidenceCard.module.css";

/** Jumlah baris yang dipamerkan; sisanya di tabel di bawah. */
const MAKS_BARIS = 6;

const LENCANA: Record<SafetyTone, string> = {
  ok: "board-badge board-badge-ok",
  warn: "board-badge board-badge-warn",
  danger: "board-badge board-badge-danger",
  muted: "board-badge board-badge-muted",
};

type Segmen = {
  kunci: string;
  label: string;
  jumlah: number;
  tone: SafetyTone;
};

function segmenDari(summary: EvidenceSummary): Segmen[] {
  return [
    { kunci: "cukup", label: "cukup", jumlah: summary.sufficient, tone: "ok" },
    { kunci: "kurang", label: "kurang", jumlah: summary.insufficient, tone: "warn" },
    { kunci: "bertentangan", label: "bertentangan", jumlah: summary.ambiguous, tone: "danger" },
    { kunci: "tidak-tercatat", label: "tidak tercatat", jumlah: summary.unknown, tone: "muted" },
  ];
}

/** Peringkat keterbacaan tindakan: yang membelokkan alokasi lebih dulu. */
const PERINGKAT: Record<EvidenceRow["state"], number> = {
  insufficient: 0,
  ambiguous: 1,
  unknown: 2,
  sufficient: 3,
};

function urutTindakan(rows: readonly EvidenceRow[]): EvidenceRow[] {
  return rows
    .map((row, indeks) => ({ row, indeks }))
    .sort((a, b) => PERINGKAT[a.row.state] - PERINGKAT[b.row.state] || a.indeks - b.indeks)
    .map((item) => item.row);
}

export default function TemperatureEvidenceCard({
  rows,
  summary,
}: {
  rows: readonly EvidenceRow[];
  summary: EvidenceSummary;
}) {
  const segmen = segmenDari(summary);
  const tampil = urutTindakan(rows).slice(0, MAKS_BARIS);
  const adaKurang = rows.some((row) => !row.sufficient);
  const ringkasAria =
    `${summary.total} batch diperiksa: ` +
    `${summary.sufficient} bukti cukup, ${summary.insufficient} bukti kurang, ` +
    `${summary.ambiguous} bukti bertentangan, ${summary.unknown} tidak tercatat.`;

  return (
    <article className="card jump-target" id="safety-bukti-suhu">
      <div className="board-card-head">
        <h2>Bukti suhu</h2>
        {summary.total > 0 ? (
          <span
            className={
              summary.perluVerifikasi > 0
                ? "board-badge board-badge-warn"
                : "board-badge board-badge-ok"
            }
          >
            {summary.sufficient} dari {summary.total} cukup bukti
          </span>
        ) : null}
      </div>

      {summary.total === 0 ? (
        <p className="evidence-note">Belum ada batch pada cakupan ini.</p>
      ) : (
        <>
          <div className={styles.meter} role="img" aria-label={ringkasAria}>
            {segmen
              .filter((item) => item.jumlah > 0)
              .map((item) => (
                <span
                  key={item.kunci}
                  className={styles.segment}
                  data-tone={item.tone}
                  style={{ flexGrow: item.jumlah }}
                  aria-hidden="true"
                />
              ))}
          </div>

          <ul className={styles.legend}>
            {segmen.map((item) => (
              <li key={item.kunci} className={styles.legendItem}>
                <span className={styles.swatch} data-tone={item.tone} aria-hidden="true" />
                <span>
                  {item.label} <span className={styles.legendCount}>{item.jumlah}</span>
                </span>
              </li>
            ))}
          </ul>

          {summary.perluVerifikasi > 0 ? (
            <p className={styles.pending}>
              <strong>{summary.perluVerifikasi} batch</strong> menuntut bukti suhu tetapi belum cukup
              — lengkapi pembacaan suhu lalu verifikasi sebelum dialokasikan.
            </p>
          ) : (
            <p className="evidence-note">
              Semua batch pada cakupan ini punya bukti suhu yang cukup (atau komoditasnya memang
              tidak diwajibkan bukti suhu).
            </p>
          )}

          {tampil.length > 0 ? (
            <ul className={styles.rows}>
              {tampil.map((row) => (
                <li
                  key={`bukti-${row.id ?? `${row.commodity}-${row.observation}`}`}
                  className={styles.row}
                  data-tone={row.tone}
                >
                  <div className={styles.rowHead}>
                    <span className={styles.commodity}>{row.commodity}</span>
                    <span className={LENCANA[row.tone]}>{row.stateLabel}</span>
                  </div>
                  <p className={styles.rowMeta}>
                    {row.observationLabel}
                    {row.sampleCount === null ? "" : `, ${row.sampleCount} sampel`}
                    {row.sourceLabel ? `, ${row.sourceLabel}` : ""}
                  </p>
                  {row.profileVersion ? (
                    <p className={styles.rowProfile}>
                      Profil {row.profileVersion}
                      {row.policyKind === "simulated_policy"
                        ? " — simulasi, bukan standar regulasi"
                        : ""}
                    </p>
                  ) : (
                    <p className={styles.rowProfile}>
                      Komoditas ini belum punya profil suhu — tidak dinilai.
                    </p>
                  )}
                  {row.reasons.length > 0 ? (
                    <p className={styles.rowReason}>
                      <span className={styles.rowReasonLabel}>Alasan server: </span>
                      {row.reasons.join("; ")}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : null}

          {rows.length > MAKS_BARIS || adaKurang ? (
            <p className={`evidence-note ${styles.foot}`}>
              {rows.length > MAKS_BARIS ? (
                <>
                  Ditampilkan {MAKS_BARIS} dari {rows.length} batch, yang paling perlu tindakan lebih
                  dulu.{" "}
                  <a className="board-link" href="#safety-daftar">
                    Tabel di bawah memuat seluruhnya
                  </a>
                  .{" "}
                </>
              ) : null}
              {adaKurang ? (
                <>
                  Bukti kurang tidak pernah dibaca sebagai aman: statusnya{" "}
                  {evidenceLabel("insufficient").toLowerCase()} sampai pembacaan suhu dilengkapi.
                </>
              ) : null}
            </p>
          ) : null}
        </>
      )}
    </article>
  );
}
