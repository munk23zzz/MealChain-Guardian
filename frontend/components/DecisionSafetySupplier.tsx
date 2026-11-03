"use client";

// DecisionSafetySupplier — blok KEAMANAN & PEMASOK halaman Decision & Evidence
// (TAHAP 4, 29 Okt 2026, gaya clean dashboard).
//
// Yang dipisah di sini adalah dua pertanyaan berbeda yang dulu tercampur dalam
// satu daftar fakta:
//   1. Apakah isinya aman?  → putusan keamanan + bukti pemeriksaannya.
//   2. Siapa yang mengirim? → pemasok terpilih dan pemasok yang sedang
//      dikecualikan untuk lokasi ini.
//
// Semua nilai dari `safetyBadge`/`safetyFacts`/`supplierFact` dan dari
// `supplierContext` yang sudah diambil halaman. Komponen ini TIDAK menghitung
// ulang status keamanan dan tidak mengubah nada warna: status mentah dari server
// tetap diterjemahkan oleh helper, bukan di sini.
import type { SupplierContext } from "../lib/supplier-exclusions";
import { safetyBadge, safetyFacts, supplierFact } from "../lib/evidence";

const TONE_KELAS: Record<string, string> = {
  ok: "ok",
  warn: "warn",
  danger: "danger",
  muted: "muted",
};

function namaPemasok(context: SupplierContext, id: string): string {
  const ketemu = context.suppliers.find((s) => s.id === id);
  return ketemu?.name ?? `pemasok ${id.slice(0, 8)}`;
}

const STATUS_KATA: Record<string, string> = {
  active: "Berlaku",
  proposed: "Diusulkan",
  rejected: "Ditolak",
  revoked: "Dicabut",
};

export default function DecisionSafetySupplier({
  summary,
  context,
}: {
  summary: unknown;
  context: SupplierContext | null;
}) {
  const badge = safetyBadge(summary);
  // Jumlah batch naik ke lencana; jangan dicetak dua kali sebagai baris.
  const fakta = safetyFacts(summary, { countInBadge: true });
  const pemasok = supplierFact(summary);
  const pengecualian = context?.exclusions ?? [];

  return (
    <section
      className="dash-safety"
      id="keamanan" data-bagian="keamanan"
      aria-labelledby="judul-keamanan"
      data-testid="keamanan-pemasok"
    >
      <header className="dash-safety-head">
        <h2 className="dash-safety-title" id="judul-keamanan">
          Keamanan &amp; pemasok
        </h2>
        <p className="dash-safety-lead">
          Dua pertanyaan terpisah: apakah isinya aman, dan siapa yang mengirim.
        </p>
      </header>

      <div className="safety-grid">
        <article className="safety-block" data-block="keamanan">
          <div className="safety-block-head">
            <h3 className="safety-block-title">Keamanan pangan</h3>
            {/* Kelas lencana yang SUDAH ada di app/globals.css — satu bentuk
                lencana untuk seluruh aplikasi, bukan lencana baru di sini. */}
            {badge ? (
              <span
                className={`board-badge board-badge-${TONE_KELAS[badge.tone] ?? "muted"}`}
                data-testid="safety-verdict-badge"
              >
                {badge.text}
              </span>
            ) : null}
          </div>
          <table className="safety-table">
            <caption className="safety-caption">Keamanan pangan</caption>
            <tbody>
              {fakta.map((row) => (
                <tr className="safety-row" key={row.label}>
                  <th scope="row">{row.label}</th>
                  <td data-tone={row.tone ?? "muted"}>
                    {row.value}
                    {row.hint ? <span className="safety-note">{row.hint}</span> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>

        <article className="safety-block" data-block="pemasok">
          <h3 className="safety-block-title">Pemasok</h3>
          <table className="safety-table">
            <caption className="safety-caption">Pemasok</caption>
            <tbody>
              <tr className="safety-row">
                <th scope="row">{pemasok.label}</th>
                <td data-tone="muted">
                  {pemasok.value}
                  {pemasok.hint ? <span className="safety-note">{pemasok.hint}</span> : null}
                </td>
              </tr>
              <tr className="safety-row">
                <th scope="row">Pemasok dikecualikan</th>
                <td data-tone={pengecualian.length > 0 ? "warn" : "muted"}>
                  {context === null ? "—" : pengecualian.length}
                </td>
              </tr>
            </tbody>
          </table>

          {context === null ? (
            <p className="safety-kosong" data-testid="pemasok-belum-dimuat">
              Daftar pemasok untuk lokasi ini belum dimuat, jadi pengecualian
              belum bisa dipastikan.
            </p>
          ) : context.reason_unavailable ? (
            <p className="safety-kosong" data-testid="pemasok-alasan">
              {context.reason_unavailable}
            </p>
          ) : pengecualian.length === 0 ? (
            <p className="safety-kosong" data-testid="pemasok-kosong">
              Tidak ada pemasok yang sedang dikecualikan untuk lokasi ini.
            </p>
          ) : (
            <ul className="safety-exclusions" data-testid="pemasok-pengecualian">
              {pengecualian.map((item) => (
                <li key={item.id}>
                  {/* Nama dari daftar pemasok yang dikirim server; id mentah
                      hanya dipakai bila namanya tidak ikut terkirim. */}
                  <strong>{namaPemasok(context, item.supplier_id)}</strong>
                  <span className="safety-exclusion-status">
                    {STATUS_KATA[item.status] ?? item.status}
                  </span>
                  <span className="safety-exclusion-reason">{item.reason}</span>
                </li>
              ))}
            </ul>
          )}
        </article>
      </div>
    </section>
  );
}
