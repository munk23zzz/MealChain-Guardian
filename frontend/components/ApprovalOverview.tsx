"use client";

/**
 * ApprovalOverview — kepala modul persetujuan halaman "Decision & Evidence".
 *
 * Susunannya mengikuti dokumen `02-approval-action.md` §7: satu kepala yang
 * menjawab TIGA hal (apa menahan · siapa dibutuhkan · apa terjadi setelah ini),
 * lalu keadaan keputusan, daftar penyetuju berjam, dan langkah-langkahnya.
 * Sebelumnya informasi yang sama tersebar di lima blok (chip, progres, daftar
 * fakta, penghalang, tombol) sehingga pembaca harus menyusun sendiri
 * kesimpulannya.
 *
 * Prinsip yang menjaga kejujuran tampilan:
 *  - setiap kalimat berasal dari `lib/approval-panel` yang membaca read model
 *    server — komponen ini tidak menghitung kewenangan;
 *  - status langkah dibawa TEKS ("tersedia"/"tertutup") plus tanda bentuk,
 *    bukan warna saja; keadaan per peran diumumkan lewat `.sr-only`;
 *  - peran pengawas tidak melihat tombol, tetapi melihat ALASANNYA (§7.5) —
 *    "tombol absen" tidak boleh menjadi lubang tanpa penjelasan.
 */

import {
  fasePersetujuan,
  langkahPersetujuan,
  ledgerPenyetuju,
  tigaJawaban,
  type Langkah,
} from "../lib/approval-panel";

const FASE_MARK: Record<string, string> = {
  tidak_diketahui: "?",
  belum_lengkap: "○",
  bisa_setujui: "●",
  menunggu_review_po: "◐",
  selesai: "✓",
  ditolak: "✕",
  kedaluwarsa: "⏱",
};

function LangkahBaris({ langkah }: { langkah: Langkah }) {
  return (
    <li className="approval-step" data-tersedia={langkah.tersedia ? "true" : "false"}>
      <span className="approval-step-mark" aria-hidden="true">
        {langkah.tersedia ? "▸" : "▹"}
      </span>
      <span className="approval-step-body">
        <span className="approval-step-label">{langkah.label}</span>
        <span className="approval-step-pill" data-tersedia={langkah.tersedia ? "true" : "false"}>
          {langkah.tersedia ? "tersedia" : "tertutup"}
        </span>
        {/* Alasan tertulis WAJIB ada saat langkah tertutup: tombol/keadaan
            yang mati tanpa sebab adalah temuan UX yang sudah berulang. */}
        {!langkah.tersedia && langkah.alasan ? (
          <span className="approval-step-reason">{langkah.alasan}</span>
        ) : null}
      </span>
    </li>
  );
}

export default function ApprovalOverview({
  summary,
  role,
  now,
}: {
  summary: unknown;
  role: string;
  /** Jam halaman; dipakai agar tidak ada dua sumber waktu di satu layar. */
  now: Date | null;
}) {
  const fase = fasePersetujuan({ summary, role });
  const jawab = tigaJawaban({ summary, role, now });
  const penyetuju = ledgerPenyetuju({ summary, now });
  const langkah = langkahPersetujuan({ summary, role });

  return (
    <div className="approval-overview" data-fase={fase.kode}>
      {/* Satu kalimat kesimpulan + sebabnya. Inilah yang dibaca lebih dulu. */}
      <div className="approval-phase" data-nada={fase.nada} role="status">
        <span className="approval-phase-mark" aria-hidden="true">
          {FASE_MARK[fase.kode] ?? "•"}
        </span>
        <span className="approval-phase-text">
          <strong className="approval-phase-label">{fase.label}</strong>
          <span className="approval-phase-sebab">{fase.sebab}</span>
        </span>
      </div>

      <dl className="approval-answers">
        <div className="approval-answer" data-jenis="menahan">
          <dt>Yang menahan</dt>
          <dd>
            {jawab.menahan.length === 0 ? (
              <span className="approval-none">
                Tidak ada penghalang yang dilaporkan backend.
              </span>
            ) : (
              <ul className="approval-blockers">
                {jawab.menahan.map((alasan) => (
                  <li key={alasan}>{alasan}</li>
                ))}
              </ul>
            )}
          </dd>
        </div>
        <div className="approval-answer" data-jenis="dibutuhkan">
          <dt>Siapa yang dibutuhkan</dt>
          <dd>{jawab.dibutuhkan}</dd>
        </div>
        <div className="approval-answer" data-jenis="setelah">
          <dt>Setelah ini</dt>
          <dd>{jawab.setelah}</dd>
        </div>
      </dl>

      <div className="approval-ledger">
        <h3 className="approval-ledger-title">Penyetuju</h3>
        {penyetuju.length === 0 ? (
          <p className="approval-none">Belum ada syarat peran yang tercatat untuk keputusan ini.</p>
        ) : (
          <ul className="approval-ledger-list">
            {penyetuju.map((baris) => (
              <li
                key={baris.roles.join("+")}
                className="approval-ledger-row"
                data-done={baris.done ? "true" : "false"}
              >
                <span className="approval-ledger-mark" aria-hidden="true">
                  {baris.done ? "✓" : "○"}
                </span>
                <span className="approval-ledger-body">
                  <span className="approval-ledger-role">{baris.label}</span>
                  {baris.nama ? <span className="approval-ledger-name">{baris.nama}</span> : null}
                  {baris.jam ? <span className="approval-ledger-time">{baris.jam}</span> : null}
                  {baris.catatan ? (
                    <span className="approval-ledger-note">{baris.catatan}</span>
                  ) : null}
                </span>
                <span className="sr-only">
                  {baris.done
                    ? `sudah menyetujui${baris.nama ? ` oleh ${baris.nama}` : ""}${
                        baris.jam ? ` pada ${baris.jam}` : ""
                      }`
                    : "belum menyetujui"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="approval-steps-block">
        <h3 className="approval-steps-title">Langkah</h3>
        <ol className="approval-steps">
          <LangkahBaris langkah={langkah.menyetujui} />
          <LangkahBaris langkah={langkah.terbitkanPo} />
          <LangkahBaris langkah={langkah.reviewPo} />
        </ol>
      </div>
    </div>
  );
}
