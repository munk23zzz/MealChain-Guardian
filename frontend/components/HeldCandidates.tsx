"use client";

// HeldCandidates — kandidat yang TERTAHAN gerbang hierarki (Fase 6 butir 1 & 7).
//
// Kenapa komponen sendiri: sebelumnya kandidat yang gagal bukti/keamanan/
// tenggat HILANG dari layar (`generate_candidates` menyaringnya tanpa jejak),
// sehingga penyetuju melihat "tidak ada usulan" tanpa tahu sebabnya. Sekarang
// server mengirim `held[]` berisi status, lapisan hierarki, kode alasan, dan
// langkah berikutnya; komponen ini hanya MENAMPILKAN, tidak menghitung ulang
// kelayakan batch (satu evaluator: `core/batch_eligibility`).
//
// Aturan tampilan:
//   - tidak ada tombol "Ajukan": kandidat tertahan bukan usulan;
//   - kode alasan diterjemahkan lewat `lib/bahasa` (satu kamus), bukan tebakan;
//   - angka kg ditampilkan sebagai "fisik", bukan "tersedia" — kilogram yang
//     tertahan tidak boleh terbaca seolah bisa dikirim.

import { humanizeBlocker } from "../lib/bahasa";

export type HeldCandidateView = {
  source_location?: string | null;
  destination_location?: string | null;
  commodity?: string | null;
  quantity_kg?: string | number | null;
  status?: string | null;
  blocking_reasons?: string[] | null;
  next_step?: string | null;
  layer?: number | null;
  layer_name?: string | null;
  batch_ids?: string[] | null;
  is_candidate?: boolean;
};

const STATUS_WORDS: Record<string, string> = {
  on_hold: "ditahan — menunggu bukti",
  rejected: "ditolak gerbang",
  quarantined: "dikarantina",
};

export default function HeldCandidates({ held }: { held?: HeldCandidateView[] | null }) {
  const daftar = Array.isArray(held) ? held : [];
  if (daftar.length === 0) return null;

  return (
    <section className="ops-held" aria-label="Kandidat ditahan">
      <div className="card-header">
        <h4>Kandidat ditahan ({daftar.length})</h4>
      </div>
      <p className="ops-held-note">
        Hierarki keputusan berjalan sebelum peringkat: keselamatan/bukti →
        kecukupan bahan &amp; tenggat → kontinuitas → invoice/SDC → mitigasi
        susut. Kandidat di bawah ini TIDAK diajukan karena gate-nya belum
        terpenuhi — bukan karena harganya kalah.
      </p>
      <ul className="ops-held-list">
        {daftar.map((h, i) => {
          const alasan = (h.blocking_reasons ?? [])
            .map((kode) => humanizeBlocker(kode) ?? kode)
            .join("; ");
          const status = STATUS_WORDS[String(h.status ?? "")] ?? String(h.status ?? "");
          const kg = h.quantity_kg ?? "-";
          return (
            <li
              key={`${h.source_location}-${h.destination_location}-${h.commodity}-${i}`}
              className={`ops-held-item ops-held-${h.status ?? "unknown"}`}
            >
              <div className="ops-held-head">
                <strong>
                  {h.source_location} → {h.destination_location}
                </strong>
                <span className="ops-held-status">{status}</span>
              </div>
              <dl className="ops-facts">
                <dt>Komoditas</dt>
                <dd>{h.commodity ?? "-"}</dd>
                <dt>Fisik tertahan</dt>
                <dd>{kg} kg</dd>
                <dt>Lapisan</dt>
                <dd>
                  {h.layer != null ? `${h.layer}. ` : ""}
                  {h.layer_name ?? "-"}
                </dd>
              </dl>
              <p className="ops-held-reason">
                {alasan || "alasan tidak tercatat"}
              </p>
              {h.next_step && (
                <p className="ops-held-next">Langkah berikutnya: {h.next_step}</p>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
