"use client";

// Kartu "Batch perlu perhatian" — SATU tabel untuk tiga pertanyaan sekaligus:
// apakah bukti suhunya cukup, masih layak berapa lama, dan seberapa segar.
//
// Menggantikan tiga kartu yang membaca array batch yang sama (29 Okt 2026):
//   "Bukti suhu" + "Batch perlu segera dipakai" + "Kesegaran terendah".
// Satu batch yang sama muncul di tiga tempat dengan tiga bahasa; sekarang ia
// satu baris dengan tiga kolom. Teks sengaja sedikit: angka dan satu alasan
// pendek per baris, sisanya (alasan utuh dari server) ada di tooltip.
//
// Yang TIDAK ada di sini: perhitungan ulang status bukti, angka karangan, dan
// kalimat penjelas panjang. Register lengkap tetap tabel "Status keamanan per
// batch" di bawah — kartu ini alat pindai 6 baris terburuk.

import type { EvidenceRow, EvidenceSummary, SafetyRow } from "../lib/food-safety";
import { batchPerhatian, durasiManusia } from "../lib/batch-perhatian";
import styles from "./BatchPerhatianCard.module.css";

/** Baris yang dipamerkan; register lengkap ada di tabel bawah. */
const MAKS_BARIS = 6;

export default function BatchPerhatianCard({
  safetyRows,
  evidence,
  summary,
  tautanTabel = "#safety-batch",
}: {
  safetyRows: readonly SafetyRow[];
  evidence: readonly EvidenceRow[];
  summary: EvidenceSummary;
  /** Jangkar ke tabel register lengkap. */
  tautanTabel?: string;
}) {
  const baris = batchPerhatian(safetyRows, evidence, { maks: MAKS_BARIS });
  const total = summary.total;

  // Sumber log & profil hampir selalu seragam; kalau seragam dicetak SEKALI di
  // kaki kartu, bukan diulang di setiap baris seperti versi sebelumnya.
  const sumber = seragam(evidence.map((row) => row.sourceLabel));
  const profil = seragam(
    evidence.map((row) => (row.profileVersion ? `profil ${row.profileVersion}` : null))
  );
  const simulasi = evidence.length > 0 && evidence.every((row) => row.policyKind === "simulated_policy");
  // Lokasi hampir selalu seragam pada satu cakupan. Kalau seragam, ia dicetak
  // SEKALI di kaki kartu — bukan enam kali di bawah nama komoditas.
  const lokasiSeragam = seragam(baris.map((row) => row.location));

  const ringkasAria =
    `${total} batch diperiksa: ` +
    `${summary.sufficient} bukti cukup, ${summary.insufficient} bukti kurang, ` +
    `${summary.ambiguous} bukti bertentangan, ${summary.unknown} tidak tercatat.`;

  return (
    <article className="card jump-target" id="safety-bukti-suhu">
      <div className="board-card-head">
        <h2>Batch perlu perhatian</h2>
        {total > 0 ? (
          <span
            className={summary.perluVerifikasi > 0 ? "board-badge board-badge-warn" : "board-badge board-badge-ok"}
          >
            {summary.sufficient} dari {total} cukup bukti
          </span>
        ) : null}
      </div>

      {total === 0 ? (
        <p className="evidence-note">Belum ada batch pada cakupan ini.</p>
      ) : (
        <>
          {/* Satu bar tetap: proporsi bukti terbaca dalam sekali lihat, tanpa
              empat angka legenda yang dua di antaranya biasanya nol. */}
          <div className={styles.meter} role="img" aria-label={ringkasAria}>
            {summary.sufficient > 0 ? (
              <span className={styles.segmen} data-tone="ok" style={{ flexGrow: summary.sufficient }} />
            ) : null}
            {summary.insufficient > 0 ? (
              <span className={styles.segmen} data-tone="warn" style={{ flexGrow: summary.insufficient }} />
            ) : null}
            {summary.ambiguous > 0 ? (
              <span
                className={styles.segmen}
                data-tone="danger"
                style={{ flexGrow: summary.ambiguous }}
              />
            ) : null}
            {summary.unknown > 0 ? (
              <span className={styles.segmen} data-tone="muted" style={{ flexGrow: summary.unknown }} />
            ) : null}
          </div>

          {/* Cukup satu baris: "104 cukup · 34 kurang". Angka yang sama tidak
              diulang sebagai kalimat ("34 batch belum bisa dialokasikan"). */}
          <p className={styles.ringkas}>{ringkasKategori(summary)}</p>

          {baris.length === 0 ? (
            <p className="evidence-note">
              Semua batch cukup bukti, masih layak, dan skor kesegarannya di atas 50%.
            </p>
          ) : (
            <>
              <div className={styles.bungkus}>
                <table className={`location-table ${styles.tabel}`}>
                  <thead>
                    <tr>
                      <th scope="col">Batch</th>
                      <th scope="col">Bukti suhu</th>
                      <th scope="col">Sisa layak</th>
                      <th scope="col" className="num">
                        Segar
                      </th>
                      <th scope="col">Kenapa</th>
                    </tr>
                  </thead>
                  <tbody>
                    {baris.map((row) => (
                      <tr key={`perhatian-${row.id ?? `${row.location}-${row.commodity}`}`}>
                        <td data-label="Batch" className={styles.selBatch}>
                          <span className={styles.komoditas}>
                            {row.commodity}
                            {row.id ? <span className={styles.kode}>{row.id.slice(0, 8)}</span> : null}
                          </span>
                          {lokasiSeragam ? null : <span className={styles.lokasi}>{row.location}</span>}
                        </td>
                        <td data-label="Bukti suhu">
                          <span className={`board-badge board-badge-${row.buktiTone}`}>
                            {row.buktiLabel}
                          </span>
                        </td>
                        <td data-label="Sisa layak" className={styles.sisa}>
                          {row.sisa}
                        </td>
                        <td data-label="Segar" className={`num ${styles.segar}`}>
                          {row.segar}
                        </td>
                        <td data-label="Kenapa" className={styles.kenapa}>
                          {row.kenapa ? (
                            <span title={row.penuh.join("; ")}>{row.kenapa}</span>
                          ) : (
                            <span className={styles.kosong}>—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <p className={`evidence-note ${styles.kaki}`}>
                {baris.length < jumlahPerhatian(safetyRows, evidence)
                  // Frasa sengaja BUKAN "perlu tindakan": chip saringan di tabel
                  // memakai istilah itu untuk himpunan yang lain (gagal/
                  // verifikasi/karantina = 22 baris), sedangkan di sini
                  // kriterianya bukti suhu, sisa layak, dan kesegaran (audit
                  // 29 Okt 2026: 39 vs 22 untuk frasa yang sama).
                  ? `Menampilkan ${baris.length} dari ${jumlahPerhatian(safetyRows, evidence)} batch dengan bukti atau kesegaran bermasalah, paling mendesak lebih dulu. `
                  : `${baris.length} batch dengan bukti atau kesegaran bermasalah, paling mendesak lebih dulu. `}
                <a className="board-link" href={tautanTabel}>
                  Tabel di bawah memuat seluruh batch
                </a>
                .
              </p>
            </>
          )}

          {lokasiSeragam ? (
            <p className={`evidence-note ${styles.kaki}`}>Semua batch di {lokasiSeragam}.</p>
          ) : null}

          {baris.some((row) => row.segar === "—") ? (
            <p className={`evidence-note ${styles.kaki}`}>
              Skor kesegaran yang tidak dikirim server ditulis “—” — tidak pernah dibaca sebagai 0.
            </p>
          ) : null}

          {sumber || profil ? (
            <p className={`evidence-note ${styles.kaki}`}>
              {[sumber, profil].filter(Boolean).join(" · ")}
              {simulasi ? " — simulasi, bukan standar regulasi." : "."}
            </p>
          ) : null}
        </>
      )}
    </article>
  );
}

/** Kategori yang jumlahnya nol tidak dicetak: nol bukan berita di kartu ini. */
function ringkasKategori(summary: EvidenceSummary): string {
  const bagian: string[] = [`${summary.sufficient} cukup`];
  if (summary.insufficient > 0) bagian.push(`${summary.insufficient} kurang`);
  if (summary.ambiguous > 0) bagian.push(`${summary.ambiguous} bertentangan`);
  if (summary.unknown > 0) bagian.push(`${summary.unknown} tidak tercatat`);
  return bagian.join(" · ");
}

function jumlahPerhatian(safety: readonly SafetyRow[], evidence: readonly EvidenceRow[]): number {
  return batchPerhatian(safety, evidence).length;
}

function seragam(nilai: readonly (string | null)[]): string | null {
  const bersih = nilai.filter((n): n is string => Boolean(n && n !== "—"));
  if (!bersih.length) return null;
  const pertama = bersih[0];
  return bersih.every((n) => n === pertama) ? pertama : null;
}

export { durasiManusia };
