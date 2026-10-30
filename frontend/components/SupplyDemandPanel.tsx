"use client";

// Isi rincian "Pasokan & permintaan" untuk satu lokasi (dokumen 03 §3–§4).
// Sejak 28 Okt 2026 bagian ini dirender di dalam POP-UP (`Popup`) yang dibuka
// dari halaman Location Network — satu instance untuk seluruh konsol, bukan
// panel yang menempel di halaman.
//
// Urutannya sengaja mengikuti pertanyaan pengguna: berapa pasokannya, berapa
// kebutuhannya, jadi selisihnya apa, lalu batch apa saja di lokasi itu. Kartu
// keempat (perkiraan) membaca `GET /demand/forecast`; metode dan keyakinannya
// ikut ditulis supaya dasar yang tipis tidak terbaca sebagai ramalan kuat.
//
// Angka yang tidak ada ditulis "—" dengan sebabnya ("tidak ada catatan"),
// karena 0 kg akan terbaca sebagai "kebutuhannya nol". Nilai mentah backend
// (mis. `mock_sap`) tidak pernah dicetak ke layar.

import { expiryState, hoursLabel, safetyLabel, safetyTone } from "../lib/food-safety";
import { formatKg, isQuarantined, type SupplyDemandDetail } from "../lib/supply-demand";
import { ageLabel } from "../lib/location-network";
import { formatDate } from "../lib/datetime";
import ScrollHint from "./ScrollHint";
import styles from "./SupplyDemandPanel.module.css";

function hoursUntil(stamp: string | null | undefined): number | null {
  if (!stamp) return null;
  const parsed = Date.parse(stamp);
  if (!Number.isFinite(parsed)) return null;
  return (parsed - Date.now()) / 3_600_000;
}



/** "dibutuhkan 7 Nov 2026 (9 hari lagi)" — tanggal jatuh tempo, bukan jam mesin. */
function neededByLabel(stamp: string | null): string {
  const jam = hoursUntil(stamp);
  if (jam === null) return "waktu tidak tercatat";
  const tanggal = formatDate(stamp);
  if (jam <= 0) return `lewat ${tanggal}`;
  const hari = Math.max(1, Math.round(jam / 24));
  return `${hari} hari lagi · ${tanggal}`;
}

export default function SupplyDemandPanel({
  detail,
  loading,
  error,
  commodity,
}: {
  detail: SupplyDemandDetail | null;
  loading?: boolean;
  error?: string | null;
  commodity?: string;
}) {
  if (error) {
    return (
      <p className={styles.error} role="status">
        Detail lokasi gagal dimuat: {error}
      </p>
    );
  }
  if (!detail) {
    return <p className={styles.notice}>{loading ? "Memuat pasokan dan permintaan…" : "Belum ada lokasi yang dipilih."}</p>;
  }

  const { supply, demand, gap, forecast, batchSummary } = detail;

  return (
    <div className={styles.panel} data-testid="supply-demand-panel">
      <dl className={styles.cards}>
        <div className={styles.card} data-tone="supply">
          <dt>Pasokan terakhir</dt>
          <dd>{supply ? formatKg(supply.quantityKg) : "—"}</dd>
          <span>
            {supply
              ? ageLabel(supply.recordedAt) ?? "waktu catatan tidak dikirim"
              : "tidak ada catatan"}
          </span>
        </div>
        <div className={styles.card} data-tone="demand">
          <dt>Kebutuhan</dt>
          <dd>{demand ? formatKg(demand.quantityKg) : "—"}</dd>
          <span>{demand ? neededByLabel(demand.neededBy) : "tidak ada catatan"}</span>
        </div>
        {/* `data-lead` (L4): selisih adalah angka yang dicari lebih dulu, jadi
            ia dipromosikan seperti angka utama di strip ringkasan halaman
            Pemasok. Dipasang sebagai atribut supaya ukurannya bisa ditata dari
            globals (kelas modul di-hash dan tidak terbaca pratinjau statis). */}
        <div className={styles.card} data-tone={gap?.tone ?? "unknown"} data-lead="true">
          <dt>Selisih</dt>
          <dd>{gap ? gap.text : "—"}</dd>
          <span>{gap ? "" : "saldo tidak terbaca"}</span>
        </div>
        {/* Kartu ke-4 §3 butir 3: perkiraan kebutuhan 7 hari. Angkanya datang
            dari `GET /demand/forecast/{loc}/{com}` (metode statistik); metode
            dan keyakinannya ditampilkan supaya dasar yang tipis tidak terbaca
            sebagai ramalan yang kuat. */}
        <div
          className={styles.card}
          data-tone={forecast ? "forecast" : "unknown"}
          data-testid="supply-demand-forecast"
          data-source={forecast?.source ?? "unknown"}
        >
          <dt>{forecast ? `Perkiraan ${forecast.horizonDays} hari` : "Perkiraan 7 hari"}</dt>
          <dd>{forecast ? formatKg(forecast.quantityKg) : "—"}</dd>
          {/* Metode mentah ("sap_rpt_1_6 · keyakinan 42,7% · SAP-RPT-1.6")
              DIHAPUS 29 Okt 2026 atas permintaan pemilik: tiga kode teknis
              berderet di bawah satu angka terbaca sebagai kebocoran backend,
              bukan penjelasan. Yang tersisa hanya kalimat yang memang mengubah
              cara membaca angka (mis. "dasar tipis"), dan itu pun opsional. */}
          {forecast?.note ? (
            <span data-testid="supply-demand-forecast-source">{forecast.note}</span>
          ) : forecast?.fallbackUsed ? (
            // Cadangan statistik dipakai = angka ini bukan keluaran model.
            // Satu frasa, tanpa nama metode/kode sumber.
            <span data-testid="supply-demand-forecast-source">
              cadangan statistik — model tidak dipakai
            </span>
          ) : !forecast ? (
            <span data-testid="supply-demand-forecast-source">
              {`belum ada perkiraan ${commodity ?? "komoditas ini"}`}
            </span>
          ) : null}
        </div>
      </dl>

      {detail.notes.length > 0 ? (
        <ul className={styles.notes} data-testid="supply-demand-notes">
          {detail.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      ) : null}

      <section className={styles.batches}>
        <h4>Batch</h4>
        <p className={styles.batchSummary}>
          {batchSummary.total === 0
            ? "Tidak ada batch untuk lokasi dan komoditas ini."
            : [
                `${batchSummary.total} batch`,
                // "3 lolos uji" + tiga badge "Aman" di bawahnya = fakta yang sama dua kali.
                batchSummary.pass > 0 && (batchSummary.fail > 0 || batchSummary.quarantined > 0)
                  ? `${batchSummary.pass} lolos uji`
                  : null,
                batchSummary.quarantined > 0 ? `${batchSummary.quarantined} ditahan` : null,
                batchSummary.fail > 0 ? `${batchSummary.fail} gagal` : null,
                ...batchSummary.others.map((other) => `${other.count} ${other.status}`),
              ]
                .filter(Boolean)
                .join(" · ")}
        </p>
        {batchSummary.total > 0 ? (
          <>
            <div className={styles.tableScroll}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th scope="col">Batch</th>
                    <th scope="col" className={styles.num}>Jumlah</th>
                    <th scope="col">Keamanan</th>
                    <th scope="col" className={styles.num}>Masa layak</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.batches.map((batch, index) => {
                    const layak = expiryState(hoursUntil(batch.usable_until));
                    return (
                      <tr key={batch.id ?? `${index}`}>
                        <th scope="row">
                          {batch.id ? batch.id.slice(0, 8) : `batch ${index + 1}`}
                        </th>
                        <td data-label="Jumlah" className={styles.num}>{formatKg(
                          batch.quantity_kg === null || batch.quantity_kg === undefined
                            ? null
                            : Number(batch.quantity_kg)
                        )}</td>
                        <td data-label="Keamanan">
                          {isQuarantined(batch) ? (
                            <span className={styles.badge} data-tone="watch">
                              Ditahan
                            </span>
                          ) : (
                            <span
                              className={styles.badge}
                              data-tone={safetyTone(batch.safety_status)}
                            >
                              {safetyLabel(batch.safety_status)}
                            </span>
                          )}
                        </td>
                        <td data-label="Masa layak" className={styles.num}>
                          {/* Satu keterangan saja: kalau ada angka pastinya, angka
                              itu yang ditulis — bukan ember "≤ 7 hari" DAN angka. */}
                          <span className={styles.expiry} data-state={layak.key}>
                            {layak.detail ?? layak.label}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {/* Petunjuk geser untuk tabel batch: pada 390 px kolom "Masa layak"
                terpotong di tengah ("26 hari 22 ja…") tanpa petunjuk apa pun. */}
            <ScrollHint kelasWadah={styles.tableScroll} />
          </>
        ) : null}
        {detail.batchesTruncated ? (
          <p className={styles.truncated}>
            Daftar batch dibatasi {detail.batchCap} baris terbaru; batch yang lebih lama tidak ikut
            di tabel ini.
          </p>
        ) : null}
      </section>
    </div>
  );
}
