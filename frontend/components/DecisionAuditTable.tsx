"use client";

// DecisionAuditTable — tabel keputusan untuk tab Agent Log (dokumen 06 §2.5).
//
// Keterangan tabel wajib ada: "Pilih satu keputusan, langkah yang dijalankan
// agent tampil di bawah". Tanpa itu tabel terbaca sebagai laporan, bukan
// pemilih.
//
// Tidak ada sel yang diisi tebakan: kuantitas/biaya kosong ditulis "—", status
// memakai label manusia, dan baris yang dipilih ditandai `aria-current` +
// kelas visual (bukan warna saja).

import { klikBaris } from "../lib/baris-klik";
import Pager from "./Pager";
import { isOverdue } from "../lib/agent-execution";
import {
  DECISION_PAGE_SIZE,
  labelVerifikasi,
  decisionTypeLabel,
  statusLabel,
  verificationState,
  type AuditDecision,
} from "../lib/decision-table";
import { paginate } from "../lib/pagination";

/* Label lama mencetak kunci mentah ("menunggu") di sebelah "Menunggu
   persetujuan" — dua gaya label di satu baris. Sejak audit 29 Okt 2026 label
   hidup di `labelVerifikasi` (satu tempat, bisa diuji). */

function kg(nilai: number | null | undefined): string {
  if (nilai === null || nilai === undefined || !Number.isFinite(nilai)) return "—";
  return `${new Intl.NumberFormat("id-ID", { maximumFractionDigits: 1 }).format(nilai)} kg`;
}

function rupiah(nilai: number | null | undefined): string {
  if (nilai === null || nilai === undefined || !Number.isFinite(nilai)) return "—";
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0,
  }).format(nilai);
}

function waktu(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("id-ID", {
    timeZone: "Asia/Jakarta",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(d);
}

export default function DecisionAuditTable({
  rows,
  total,
  page,
  onPage,
  selectedId,
  onSelect,
  summary,
  now = null,
}: {
  rows: ReadonlyArray<AuditDecision>;
  total: number;
  page: number;
  onPage: (page: number) => void;
  selectedId: string | null;
  onSelect: (decisionId: string) => void;
  summary: string;
  /** Jam acuan untuk menandai baris yang lewat tenggat; `null` = tidak ditandai. */
  now?: Date | null;
}) {
  const halaman = paginate(rows, page, DECISION_PAGE_SIZE);

  return (
    <section className="aa-table-wrap" aria-labelledby="aa-table-title">
      <div className="aa-table-head">
        <div>
          <h3 id="aa-table-title">Daftar keputusan</h3>
          <p className="aa-table-note">
            Pilih satu keputusan, langkah yang dijalankan agent tampil di bawah.
          </p>
        </div>
        <p className="aa-table-sum" role="status" aria-atomic="true">
          {summary}
        </p>
      </div>

      {rows.length === 0 ? (
        <p className="aa-table-empty">
          Tidak ada keputusan yang cocok dengan filter ini. Jumlah total pada
          periode ini tetap {total}.
        </p>
      ) : (
        <div className="board-table-wrap aa-table-scroll">
          <table className="location-table aa-table">
            <caption className="aa-sr">
              Keputusan pada periode terpilih. Memilih satu baris menampilkan
              jejak langkah agent di bawahnya.
            </caption>
            <thead>
              <tr>
                {/* Urutan kolom (Tahap 3 redesign, 29 Okt 2026): yang paling
                    menentukan tindakan lebih dulu — Status, lalu Tenggat, lalu
                    bukti (Verifikasi). Identitas keputusan ada di kolom keempat
                    karena dipakai untuk MENGENALI baris, bukan untuk memutuskan. */}
                <th scope="col">Status</th>
                <th scope="col">Tenggat</th>
                <th scope="col">Verifikasi</th>
                <th scope="col">Keputusan</th>
                <th scope="col">Komoditas</th>
                <th scope="col" className="num">
                  Kuantitas
                </th>
                <th scope="col" className="num">
                  Biaya aman
                </th>
                <th scope="col">
                  <span className="aa-sr">Aksi</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {halaman.items.map((row) => {
                const dipilih = row.decision_id === selectedId;
                const verif = verificationState(row);
                // Baris yang DITOLAK ditandai merah (permintaan pemilik
                // 29 Okt 2026): penolakan adalah keadaan yang benar-benar
                // gugur, bukan sekadar peringatan — dan harus terbaca sekilas
                // tanpa membaca lencana status.
                const kelasBaris = [
                  row.status === "rejected" ? "aa-row-rejected" : null,
                  dipilih ? "aa-row-selected" : null,
                ]
                  .filter(Boolean)
                  .join(" ");
                return (
                  <tr
                    key={row.decision_id}
                    className={kelasBaris || undefined}
                    aria-current={dipilih ? "true" : undefined}
                    /* Klik baris = pilih keputusan (29 Okt 2026). Tombol di
                       kolom terakhir tetap ada dan tetap jalur papan ketik. */
                    data-klik-baris="true"
                    onClick={(e) => klikBaris(e, () => onSelect(row.decision_id))}
                  >
                    <td className="aa-col-status">
                      <span className={`aa-status aa-status-${row.status}`}>
                        {statusLabel(row.status)}
                      </span>
                    </td>
                    <td className="aa-col-waktu">
                      {waktu(row.expires_at)}
                      {now && isOverdue(row, now) ? (
                        <span className="aa-late" title="Masih menunggu tindakan padahal tenggatnya sudah lewat">
                          lewat tenggat
                        </span>
                      ) : null}
                    </td>
                    <td className={`aa-verif aa-verif-${verif}`}>
                      {labelVerifikasi(verif)}
                    </td>
                    <td>
                      <span className="cell-stack">
                        <span className="cell-name">
                          {decisionTypeLabel(row.decision_type)}
                        </span>
                        <span className="cell-meta">
                          {row.decision_id.slice(0, 8)}
                          {row.target_location_name
                            ? ` · ${row.target_location_name}`
                            : ""}
                        </span>
                      </span>
                    </td>
                    <td>{row.commodity_name ?? "—"}</td>
                    <td className="num">{kg(row.quantity_kg)}</td>
                    <td className="num">{rupiah(row.safe_delivered_cost)}</td>
                    <td className="aa-col-action">
                      <button
                        type="button"
                        className="board-link aa-row-link"
                        aria-pressed={dipilih}
                        onClick={() => onSelect(row.decision_id)}
                      >
                        {dipilih ? "Dipilih" : "Lihat jejak"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <Pager page={halaman} onChange={onPage} label="daftar keputusan" />
    </section>
  );
}
