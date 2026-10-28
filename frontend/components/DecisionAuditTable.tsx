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

import {
  decisionTypeLabel,
  pageCount,
  pageSlice,
  statusLabel,
  verificationState,
  type AuditDecision,
} from "../lib/decision-table";

const VERIF_LABEL: Record<string, string> = {
  terverifikasi: "terverifikasi",
  menunggu: "menunggu",
  ditolak: "ditolak",
  lainnya: "—",
};

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
}: {
  rows: ReadonlyArray<AuditDecision>;
  total: number;
  page: number;
  onPage: (page: number) => void;
  selectedId: string | null;
  onSelect: (decisionId: string) => void;
  summary: string;
}) {
  const halaman = pageSlice(rows, page);
  const jumlahHalaman = pageCount(rows.length);

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
        <div className="aa-table-scroll">
          <table className="aa-table">
            <caption className="aa-sr">
              Keputusan pada periode terpilih. Memilih satu baris menampilkan
              jejak langkah agent di bawahnya.
            </caption>
            <thead>
              <tr>
                <th scope="col">Jenis</th>
                <th scope="col">Komoditas</th>
                <th scope="col">Status</th>
                <th scope="col">Verifikasi</th>
                <th scope="col" className="aa-col-num">
                  Kuantitas
                </th>
                <th scope="col" className="aa-col-num">
                  Biaya aman
                </th>
                <th scope="col">Kedaluwarsa</th>
                <th scope="col">
                  <span className="aa-sr">Aksi</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {halaman.map((row) => {
                const dipilih = row.decision_id === selectedId;
                const verif = verificationState(row);
                return (
                  <tr
                    key={row.decision_id}
                    className={dipilih ? "aa-row-selected" : undefined}
                    aria-current={dipilih ? "true" : undefined}
                  >
                    <td>
                      <span className="aa-cell-title">
                        {decisionTypeLabel(row.decision_type)}
                      </span>
                      <span className="aa-cell-sub">
                        {row.decision_id.slice(0, 8)}
                        {row.target_location_name ? ` · ${row.target_location_name}` : ""}
                      </span>
                    </td>
                    <td>{row.commodity_name ?? "—"}</td>
                    <td>
                      <span className={`aa-status aa-status-${row.status}`}>
                        {statusLabel(row.status)}
                      </span>
                    </td>
                    <td className={`aa-verif aa-verif-${verif}`}>
                      {VERIF_LABEL[verif] ?? "—"}
                    </td>
                    <td className="aa-col-num">{kg(row.quantity_kg)}</td>
                    <td className="aa-col-num">{rupiah(row.safe_delivered_cost)}</td>
                    <td>{waktu(row.expires_at)}</td>
                    <td>
                      <button
                        type="button"
                        className={`aa-row-btn${dipilih ? " is-active" : ""}`}
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

      {jumlahHalaman > 1 ? (
        <div className="aa-pager" role="group" aria-label="Halaman keputusan">
          <button
            type="button"
            className="aa-pager-btn"
            disabled={page <= 1}
            onClick={() => onPage(page - 1)}
          >
            Sebelumnya
          </button>
          <span className="aa-pager-info">
            Halaman {Math.min(page, jumlahHalaman)} dari {jumlahHalaman}
          </span>
          <button
            type="button"
            className="aa-pager-btn"
            disabled={page >= jumlahHalaman}
            onClick={() => onPage(page + 1)}
          >
            Berikutnya
          </button>
        </div>
      ) : null}
    </section>
  );
}
