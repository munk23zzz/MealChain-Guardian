"use client";

// DecisionTraceIntegrity — blok JEJAK & INTEGRITAS (TAHAP 6, 29 Okt 2026).
//
// Tiga pertanyaan, tiga blok, satu urutan cerita:
//   1. Bagaimana keputusan ini sampai di sini? — `auditTimeline()` (lib) merangkai
//      iterasi keluarga, pengajuan, verifikasi, dan tiap persetujuan orang.
//   2. Apa yang diterbitkan dari keputusan ini? — satu PO milik keputusan ini
//      saja (`DecisionPurchaseOrder` sudah memfilter; daftar PO jaringan tidak
//      pernah dipasang di bawah satu keputusan).
//   3. Bisakah catatan itu dipercaya? — rantai Merkle + alamat konten + tanda
//      tangan, dibaca dari API (`IntegrityPanel`).
//
// Aturan yang dipegang:
//   · Tidak ada satu pun angka, verdict, atau tanda tangan yang dikarang di sini:
//     semua datang dari lib yang sudah ada atau dari komponen yang sudah ada.
//   · Keadaan "belum termuat" BUKAN "tidak ada". Daftar PO yang belum tiba tidak
//     boleh tercetak sebagai "belum ada PO"; tanpa sesi, blok integritas tidak
//     memanggil API sama sekali.
import { auditTimeline } from "../lib/evidence";
import DecisionAudit from "./DecisionAudit";
import DecisionPurchaseOrder from "./DecisionPurchaseOrder";
import IntegrityPanel from "./IntegrityPanel";

export default function DecisionTraceIntegrity({
  selected,
  summary,
  chain,
  token,
  purchaseOrders,
}: {
  selected: Record<string, unknown> & { decision_id?: string };
  summary: unknown;
  chain: unknown;
  token: string | null;
  /** Daftar PO jaringan; `undefined` berarti belum termuat, bukan kosong. */
  purchaseOrders?: unknown;
}) {
  const decisionId = selected?.decision_id ?? null;
  const audit = auditTimeline({ decision: selected, summary, chain });
  const dikirim = audit.filter((e) => e.tone === "danger").length;

  return (
    <section
      className="dash-trace"
      id="jejak" data-bagian="jejak"
      aria-labelledby="judul-jejak"
      data-testid="jejak-integritas"
    >
      <header className="dash-trace-head">
        <h2 className="dash-trace-title" id="judul-jejak">
          Jejak &amp; integritas
        </h2>
        <p className="dash-trace-lead">
          Bagaimana keputusan ini terbentuk, apa yang diterbitkan darinya, dan
          bukti bahwa catatannya tidak ditulis ulang.
        </p>
      </header>

      <article className="trace-block" data-block="jejak">
        <div className="trace-block-head">
          <h3 className="trace-block-title">Jejak &amp; riwayat</h3>
          {/* Jumlah catatan menyebut apa adanya; yang gagal/lewat ditonjolkan
              hanya bila memang ada, bukan angka hiasan. */}
          <p className="trace-block-meta" data-testid="jejak-ringkas">
            {audit.length} catatan
            {dikirim > 0 ? ` · ${dikirim} bertanda masalah` : ""}
          </p>
        </div>
        <DecisionAudit events={audit} />
      </article>

      <div className="trace-pair">
        <article className="trace-block" data-block="pesanan">
          <div className="trace-block-head">
            <h3 className="trace-block-title">PO keputusan ini</h3>
          </div>
          {purchaseOrders === undefined ? (
            <p className="trace-kosong" data-testid="po-belum-termuat">
              Daftar PO belum termuat, jadi halaman ini belum bisa memastikan
              ada atau tidaknya PO untuk keputusan ini.
            </p>
          ) : (
            <DecisionPurchaseOrder
              purchaseOrders={purchaseOrders}
              decisionId={decisionId}
              token={token}
              decisionStatus={(selected?.status as string | null) ?? null}
            />
          )}
        </article>

        <article className="trace-block" data-block="integritas">
          {token ? (
            // Key = id keputusan: memastikan dossier & tanda tangan keputusan
            // sebelumnya tidak tertinggal di bawah judul keputusan yang baru.
            <IntegrityPanel
              key={decisionId ?? "tanpa-keputusan"}
              token={String(token)}
              decisionId={decisionId}
            />
          ) : (
            <p className="trace-kosong" data-testid="integritas-tanpa-token">
              Integritas bukti butuh sesi yang sudah masuk; halaman ini tidak
              menampilkan tanda tangan atau hash apa pun tanpa itu.
            </p>
          )}
        </article>
      </div>
    </section>
  );
}
