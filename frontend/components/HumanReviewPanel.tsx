"use client";

// HumanReviewPanel — penerimaan manusia atas bukti batch (Fase 6 butir 3 & 5).
//
// Aturan yang dijaga komponen ini (dan ditegakkan ULANG di server):
//   1. Reviewer TIDAK memilih status. Ia menambahkan bukti (sampel suhu) +
//      alasan + rujukan; server menghitung ulang status lewat
//      `core.safety.evaluate_safety` dengan profil komoditas.
//   2. Tombol kirim mati sampai alasan (≥10 karakter) dan ≥1 rujukan terisi —
//      bukan untuk kenyamanan, tetapi karena server menolaknya 422 dan UI tidak
//      boleh menjanjikan aksi yang pasti gagal.
//   3. Sesudah kirim, hasilnya ditampilkan apa adanya: `status_changed` bisa
//      `false` (bukti belum cukup) dan UI menyebut langkah berikutnya, bukan
//      mengklaim batch sudah aman.
//   4. Peran pembaca (bgn_monitor) hanya melihat daftar review, tanpa form.
//
// Sumber data: `GET /decisions/{id}/packet` (satu read model), bukan merakit
// ulang evaluasi batch di klien.

import { useCallback, useEffect, useState } from "react";

import { fetchDecisionPacket, reviewDecision } from "../lib/api";
import { humanizeBlocker, safetyLabel } from "../lib/bahasa";
import { evidenceLabel } from "../lib/food-safety";
import { REASON_MIN, REVIEW_ROLES, reviewReadiness } from "../lib/review-gate";

type Sample = { timestamp: string; temperature_c: string };

type BatchView = {
  batch_id: string;
  status: string;
  blocking_reasons: string[];
  next_step: string | null;
  safety_status: string | null;
  usable_until: string | null;
  evidence_state: string | null;
};

type ReviewEntry = {
  evidence_id: string;
  batch_id: string | null;
  reviewed_by_user_id: string | null;
  reviewed_by_role: string | null;
  reviewed_at: string | null;
  reason: string | null;
  evidence_refs: string[];
  safety_status_before: string | null;
  safety_status_after: string | null;
};

function waktuLokal(iso: string | null): string {
  if (!iso) return "-";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("id-ID");
}

function rujukanDari(teks: string): string[] {
  return teks
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

export default function HumanReviewPanel({
  decisionId,
  token,
  role,
  packet,
  onReviewed,
  tanpaCatatan = false,
}: {
  decisionId: string | null;
  token: string | null;
  role: string | null;
  /** Paket keputusan yang sudah diambil induk. Bila ada, panel TIDAK mengambil
      ulang — satu pembacaan untuk satu layar (butir 4: satu bentuk data). */
  packet?: any | null;
  /** Halaman bukti memindahkan kalimat metode ke blok "Catatan teknis". */
  tanpaCatatan?: boolean;
  onReviewed?: () => void;
}) {
  const [packetSendiri, setPacketSendiri] = useState<any>(null);
  const [galat, setGalat] = useState<string | null>(null);
  const [batchId, setBatchId] = useState<string>("");
  const [alasan, setAlasan] = useState("");
  const [rujukan, setRujukan] = useState("");
  const [sampel, setSampel] = useState<Sample[]>([]);
  const [busy, setBusy] = useState(false);
  const [hasil, setHasil] = useState<any>(null);

  const muat = useCallback(async () => {
    if (!decisionId || !token) return;
    try {
      const data = await fetchDecisionPacket(decisionId, token);
      setPacketSendiri(data);
      setGalat(null);
    } catch (e: any) {
      setPacketSendiri(null);
      setGalat(String(e?.message ?? e));
    }
  }, [decisionId, token]);

  useEffect(() => {
    setHasil(null);
    setAlasan("");
    setRujukan("");
    setSampel([]);
    if (!packet) void muat();
  }, [muat, packet]);

  // Paket dari induk menang; panel hanya mengambil sendiri bila tidak diberi.
  // Kedua baris di bawah WAJIB membaca `paket` (hasil gabungan), bukan `packet`:
  // saat induk masih mengirim `null` dan unduhan sendiri selesai, `packet`
  // tetap null → render melempar dan seluruh tab Decision & Evidence hilang
  // (terukur di browser 27 Okt 2026; dikunci `tests/human-review-null-packet.test.tsx`).
  const paket = packet ?? packetSendiri;
  const batch: BatchView[] = Array.isArray(paket?.batch_evaluations)
    ? paket.batch_evaluations
    : [];
  const perluTinjau = batch.filter((b) =>
    ["needs_verification", "pending"].includes(String(b.safety_status ?? ""))
  );
  const reviewTercatat: ReviewEntry[] = Array.isArray(paket?.review?.human_reviews)
    ? paket.review.human_reviews
    : [];
  const refs = rujukanDari(rujukan);
  // Satu aturan untuk komponen DAN tes (`lib/review-gate`), sejalan dengan
  // validasi server — UI tidak boleh menjanjikan kiriman yang pasti 422.
  const siap = reviewReadiness({ role, batchId, reason: alasan, evidenceRefs: refs });
  const bolehMeninjau = (REVIEW_ROLES as readonly string[]).includes(String(role ?? ""));
  const bisaKirim = !busy && siap.ok;

  async function kirim() {
    if (!decisionId || !token || !bisaKirim) return;
    setBusy(true);
    setGalat(null);
    try {
      const balasan = await reviewDecision(
        decisionId,
        {
          batch_id: batchId,
          reason: alasan.trim(),
          evidence_refs: refs,
          temperature_samples: sampel
            .filter((s) => s.temperature_c.trim() !== "")
            .map((s) => ({
              timestamp: s.timestamp,
              temperature_c: Number(s.temperature_c),
            })),
        },
        token
      );
      setHasil(balasan);
      setAlasan("");
      setRujukan("");
      setSampel([]);
      await muat();
      onReviewed?.();
    } catch (e: any) {
      setHasil(null);
      setGalat(String(e?.message ?? e));
    } finally {
      setBusy(false);
    }
  }

  if (!decisionId) return null;

  return (
    <article className="card human-review" aria-label="Verifikasi bukti batch">
      <div className="card-header">
        <h2>Verifikasi bukti batch</h2>
        <span className="evidence-note">
          {bolehMeninjau
            ? tanpaCatatan
              ? null
              : "Reviewer menambah bukti; status dihitung server."
            : "Peran ini hanya dapat melihat catatan review (read-only)."}
        </span>
      </div>

      {galat && (
        <p className="review-error" role="alert">
          {galat}
        </p>
      )}

      {batch.length === 0 && (
        <p className="evidence-note">
          Keputusan ini tidak mengikat batch, jadi tidak ada bukti batch untuk
          diverifikasi.
        </p>
      )}

      {perluTinjau.length > 0 && bolehMeninjau && (
        <div className="review-form">
          <label className="field">
            <span>Batch yang ditinjau</span>
            <select
              value={batchId}
              onChange={(e) => setBatchId(e.target.value)}
              disabled={busy}
            >
              <option value="">— pilih batch —</option>
              {perluTinjau.map((b) => (
                <option key={b.batch_id} value={b.batch_id}>
                  {b.batch_id.slice(0, 8)} ·{" "}
                  {safetyLabel(b.safety_status) ?? b.safety_status ?? "-"} ·{" "}
                  {(b.blocking_reasons ?? [])
                    .map((k) => humanizeBlocker(k) ?? k)
                    .join(", ") || "tanpa alasan"}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>Alasan review (wajib, ≥{REASON_MIN} karakter)</span>
            <textarea
              value={alasan}
              onChange={(e) => setAlasan(e.target.value)}
              rows={3}
              disabled={busy}
              placeholder="Contoh: suhu ruang muat dicek ulang, dua sampel baru dicatat dari termometer kalibrasi."
            />
            <small className="field-note">
              {alasan.trim().length}/{REASON_MIN} karakter — &ldquo;aman&rdquo; saja
              bukan alasan.
            </small>
          </label>

          <label className="field">
            <span>Rujukan bukti (wajib, pisahkan dengan koma)</span>
            <input
              type="text"
              value={rujukan}
              onChange={(e) => setRujukan(e.target.value)}
              disabled={busy}
              placeholder="BA-2026-10-27-01, inspeksi-4412"
            />
          </label>

          <div className="review-samples">
            <span>Bukti suhu yang ditambahkan</span>
            {sampel.map((s, i) => (
              <div key={i} className="review-sample-row">
                <input
                  type="datetime-local"
                  value={s.timestamp}
                  onChange={(e) =>
                    setSampel((lama) =>
                      lama.map((x, j) => (j === i ? { ...x, timestamp: e.target.value } : x))
                    )
                  }
                  disabled={busy}
                  aria-label="Waktu sampel"
                />
                <input
                  type="number"
                  step="0.1"
                  value={s.temperature_c}
                  onChange={(e) =>
                    setSampel((lama) =>
                      lama.map((x, j) =>
                        j === i ? { ...x, temperature_c: e.target.value } : x
                      )
                    )
                  }
                  disabled={busy}
                  aria-label="Suhu (C)"
                  placeholder="°C"
                />
                <button
                  type="button"
                  className="button"
                  onClick={() => setSampel((lama) => lama.filter((_, j) => j !== i))}
                  disabled={busy}
                >
                  Hapus
                </button>
              </div>
            ))}
            <button
              type="button"
              className="button"
              disabled={busy}
              onClick={() =>
                setSampel((lama) => [
                  ...lama,
                  {
                    timestamp: new Date().toISOString().slice(0, 16),
                    temperature_c: "",
                  },
                ])
              }
            >
              Tambah sampel
            </button>
            <small className="field-note">
              Sampel ditambahkan ke log batch; tanpa sampel, review tetap dicatat
              tetapi status tidak akan berubah bila bukti belum cukup.
            </small>
          </div>

          <button
            type="button"
            className="button button-primary"
            disabled={!bisaKirim}
            onClick={kirim}
          >
            {busy ? "Menyimpan…" : "Simpan review"}
          </button>
          {!bisaKirim && !busy && (
            <small className="field-note">
              Alasan ≥{REASON_MIN} karakter dan minimal satu rujukan bukti wajib
              diisi (server menolak 422 tanpa keduanya).
            </small>
          )}
        </div>
      )}

      {hasil && (
        <div className="review-result" role="status">
          <p>
            Status batch: <strong>{safetyLabel(hasil.safety_status_before) ?? hasil.safety_status_before}</strong>{" "}
            → <strong>{safetyLabel(hasil.safety_status_after) ?? hasil.safety_status_after}</strong>{" "}
            {hasil.status_changed ? "(berubah)" : "(tidak berubah)"}
          </p>
          <p>
            Keadaan bukti: <strong>{evidenceLabel(hasil.evidence_state)}</strong> · sampel:{" "}
            {hasil.sample_count} · di luar rentang: {hasil.excursion_minutes} menit
          </p>
          {(hasil.blocking_reasons ?? []).length > 0 && (
            <p>
              Sisa penghalang:{" "}
              {(hasil.blocking_reasons as string[])
                .map((k) => humanizeBlocker(k) ?? k)
                .join("; ")}
            </p>
          )}
          {hasil.next_step && <p>Langkah berikutnya: {hasil.next_step}</p>}
        </div>
      )}

      <div className="review-history">
        <h3>Catatan review manusia</h3>
        {reviewTercatat.length === 0 ? (
          <p className="evidence-note">Belum ada review manusia untuk keputusan ini.</p>
        ) : (
          <ul>
            {reviewTercatat.map((r) => (
              <li key={r.evidence_id}>
                <div>
                  <strong>{r.reviewed_by_role ?? "peran tidak tercatat"}</strong>{" "}
                  · {waktuLokal(r.reviewed_at)} · batch{" "}
                  {String(r.batch_id ?? "-").slice(0, 8)}
                </div>
                <div>
                  {safetyLabel(r.safety_status_before) ?? r.safety_status_before} →{" "}
                  {safetyLabel(r.safety_status_after) ?? r.safety_status_after}
                </div>
                <p>{r.reason ?? "alasan tidak tercatat"}</p>
                <p className="evidence-note">
                  Rujukan: {(r.evidence_refs ?? []).join(", ") || "tidak tercatat"}
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </article>
  );
}
