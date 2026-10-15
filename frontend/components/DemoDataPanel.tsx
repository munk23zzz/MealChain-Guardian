"use client";

// Panel "Data & rentang waktu" (Fase 5, 2026-10-15) — tab Demo Control.
//
// Yang dijaga panel ini:
// - **Tidak ada angka karangan.** Tiap kalimat berasal dari payload backend
//   (`/demo/preview`, `/demo/timeseries`, `/demo/timeseries/purge`,
//   `/demo/refresh`, `/demo/data-status`); perhitungan kalimatnya ada di
//   lib/demo-data.ts (murni, teruji terpisah).
// - **Peringatan jujur tampil SEBELUM tombol dijalankan**, bukan sesudah:
//   apa yang dihapus, apa yang tidak disentuh, dan apa yang tidak dijanjikan.
// - **Hapus butuh dua langkah** (tombol → konfirmasi) karena aksinya merusak
//   dan tidak bisa dibatalkan dari UI.
//
// Cakupan peran mengikuti backend (require_roles sppg_head/sppg_nutritionist):
// pemantau BGN tidak melihat kontrol, hanya catatan mode baca.
import { useCallback, useEffect, useState } from "react";

import { LoadingState } from "./LoadingState";
import {
  DEFAULT_RANGE,
  INTERVAL_HOURS,
  RANGE_MAX,
  RANGE_MIN,
  buildLine,
  canSubmit,
  formatShortDate,
  honestNote,
  previewLine,
  purgeLine,
  purgeWarning,
  rangeError,
  refreshLine,
  refreshWarning,
  spanDays,
  statusLine,
  toIsoDateTime,
} from "../lib/demo-data";
import {
  fetchDemoDataStatus,
  fetchDemoPreview,
  purgeDemoTimeseries,
  refreshDemoToToday,
  runDemoTimeseries,
} from "../lib/api";

const GENERATOR_ROLES = ["sppg_head", "sppg_nutritionist"];

type Aksi = "preview" | "generate" | "purge" | "refresh";

export default function DemoDataPanel({
  token,
  role,
  onDataChanged,
}: {
  token: string | null;
  role: string;
  onDataChanged?: () => void;
}) {
  const [start, setStart] = useState<string>(DEFAULT_RANGE.start);
  const [end, setEnd] = useState<string>(DEFAULT_RANGE.end);
  const [force, setForce] = useState(false);
  const [status, setStatus] = useState<any>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [preview, setPreview] = useState<any>(null);
  const [hasil, setHasil] = useState<string | null>(null);
  const [hasilPeringatan, setHasilPeringatan] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [konfirmasiHapus, setKonfirmasiHapus] = useState(false);
  const [busy, setBusy] = useState<Aksi | null>(null);

  const canRun = Boolean(token) && GENERATOR_ROLES.includes(role);
  const galatRentang = rangeError(start, end);
  const bolehKirim = canSubmit(start, end, busy !== null);
  const hari = spanDays(start, end);

  const muatStatus = useCallback(async () => {
    if (!token) return;
    setStatusError(null);
    try {
      setStatus(await fetchDemoDataStatus(token));
    } catch (e: any) {
      setStatus(null);
      setStatusError(String(e?.message ?? e));
    }
  }, [token]);

  useEffect(() => {
    void muatStatus();
  }, [muatStatus]);

  /** Rentang berubah → hasil lama tidak lagi menggambarkan rentang di layar. */
  function ubahRentang(berikut: () => void) {
    berikut();
    setPreview(null);
    setHasil(null);
    setHasilPeringatan(null);
    setKonfirmasiHapus(false);
  }

  async function onPreview() {
    if (!token || !bolehKirim) return;
    setBusy("preview");
    setMsg(null);
    try {
      setPreview(
        await fetchDemoPreview(
          toIsoDateTime(start),
          toIsoDateTime(end),
          token,
          INTERVAL_HOURS
        )
      );
    } catch (e: any) {
      setMsg(String(e?.message ?? e));
    } finally {
      setBusy(null);
    }
  }

  async function onGenerate() {
    if (!token || !bolehKirim) return;
    setBusy("generate");
    setMsg(null);
    try {
      const r = await runDemoTimeseries(
        toIsoDateTime(start),
        toIsoDateTime(end),
        token,
        { force, intervalHours: INTERVAL_HOURS }
      );
      setHasil(buildLine(r));
      setHasilPeringatan(null);
      setPreview(null);
      await muatStatus();
      onDataChanged?.();
    } catch (e: any) {
      setMsg(String(e?.message ?? e));
    } finally {
      setBusy(null);
    }
  }

  async function onHapus() {
    if (!token || busy !== null) return;
    setBusy("purge");
    setMsg(null);
    try {
      const r = await purgeDemoTimeseries(token);
      setHasil(purgeLine(r));
      setHasilPeringatan(null);
      setPreview(null);
      setKonfirmasiHapus(false);
      await muatStatus();
      onDataChanged?.();
    } catch (e: any) {
      setMsg(String(e?.message ?? e));
    } finally {
      setBusy(null);
    }
  }

  async function onSegarkan() {
    if (!token || busy !== null) return;
    setBusy("refresh");
    setMsg(null);
    try {
      const r = await refreshDemoToToday(token);
      setHasil(refreshLine(r));
      // Peringatan backend ditampilkan APA ADANYA — bukan diringkas klien.
      setHasilPeringatan(
        typeof r?.warning === "string" && r.warning ? r.warning : refreshWarning()
      );
      setPreview(null);
      await muatStatus();
      onDataChanged?.();
    } catch (e: any) {
      setMsg(String(e?.message ?? e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <section
      className="card demo-data-panel"
      aria-label="Data & rentang waktu"
      aria-busy={busy !== null}
    >
      <div className="card-header">
        <h4>Data &amp; rentang waktu</h4>
        <span className="demo-data-tag">deret waktu demo</span>
      </div>
      <p className="section-sub">
        Riwayat data demo (pasokan, harga, rencana menu) dibangun di sini —
        rentang {formatShortDate(RANGE_MIN)} sampai {formatShortDate(RANGE_MAX)},
        selang {INTERVAL_HOURS} jam. Panel ini memakai API resmi; angka yang tampil
        selalu berasal dari server.
      </p>

      <div className="demo-data-grid">
        <label className="field">
          <span>Mulai</span>
          <input
            type="date"
            className="demo-data-start"
            value={start}
            min={RANGE_MIN}
            max={RANGE_MAX}
            onChange={(e) => ubahRentang(() => setStart(e.target.value))}
            disabled={!canRun || busy !== null}
          />
        </label>
        <label className="field">
          <span>Selesai</span>
          <input
            type="date"
            className="demo-data-end"
            value={end}
            min={RANGE_MIN}
            max={RANGE_MAX}
            onChange={(e) => ubahRentang(() => setEnd(e.target.value))}
            disabled={!canRun || busy !== null}
          />
        </label>
        <p className="field-note demo-data-span">
          {galatRentang
            ? galatRentang
            : `Rentang ${hari} hari — ${formatShortDate(start)} sampai ${formatShortDate(end)}.`}
        </p>
      </div>

      {canRun && (
        <div className="demo-data-actions">
          <button
            type="button"
            className="button button-secondary demo-data-preview"
            onClick={onPreview}
            disabled={!bolehKirim}
            title="Hitung berapa baris yang akan ditambah — tidak menulis apa pun"
          >
            {busy === "preview" ? "Menghitung…" : "Pratinjau"}
          </button>
          <button
            type="button"
            className="button button-primary demo-data-generate"
            onClick={onGenerate}
            disabled={!bolehKirim}
            title="Buat/perbarui baris deret waktu demo (idempoten)"
          >
            {busy === "generate" ? "Membangun…" : "Buat/perbarui data"}
          </button>
          <label className="demo-data-force">
            <input
              type="checkbox"
              checked={force}
              onChange={(e) => setForce(e.target.checked)}
              disabled={busy !== null}
            />
            <span>Bangun ulang dari nol (hapus baris demo dulu)</span>
          </label>
        </div>
      )}

      {hasil && <p className="demo-data-result">{hasil}</p>}
      {hasilPeringatan && (
        <p className="demo-data-warning" role="alert">
          {hasilPeringatan}
        </p>
      )}
      {msg && <p className="action-message">{msg}</p>}

      {canRun && (
        <div className="demo-data-refresh">
          <button
            type="button"
            className="button button-secondary demo-data-refresh-button"
            onClick={onSegarkan}
            disabled={busy !== null}
            title="Jalankan seeder relatif hari ini + muat ulang 4 kasus skrip"
            aria-describedby="demo-data-refresh-warning"
          >
            {busy === "refresh" ? "Menyegarkan…" : "Segarkan ke hari ini"}
          </button>
          <p id="demo-data-refresh-warning" className="demo-data-warning">
            {refreshWarning()}
          </p>
        </div>
      )}

      {canRun && (
        <div className="demo-data-purge">
          <button
            type="button"
            className="button button-secondary demo-data-purge-button"
            onClick={() => setKonfirmasiHapus(true)}
            disabled={busy !== null || konfirmasiHapus}
            title="Hapus semua baris deret waktu demo"
            aria-describedby="demo-data-purge-warning"
          >
            Bersihkan data demo
          </button>
          <p id="demo-data-purge-warning" className="demo-data-note">
            {purgeWarning()}
          </p>
          {konfirmasiHapus && (
            <p className="demo-data-confirm" role="alert">
              Yakin menghapus seluruh baris deret waktu demo?
              <button
                type="button"
                className="button demo-data-purge-confirm"
                onClick={onHapus}
                disabled={busy !== null}
              >
                {busy === "purge" ? "Menghapus…" : "Ya, hapus baris demo"}
              </button>
              <button
                type="button"
                className="button button-secondary demo-data-purge-cancel"
                onClick={() => setKonfirmasiHapus(false)}
                disabled={busy !== null}
              >
                Batal
              </button>
            </p>
          )}
        </div>
      )}

      <div className="demo-data-status" role="status" aria-live="polite">
        {status ? (
          <p>{statusLine(status)}</p>
        ) : statusError ? (
          <p className="status-danger">Status data gagal dibaca: {statusError}</p>
        ) : (
          <LoadingState label="Memuat status data demo" />
        )}
        {preview && <p className="demo-data-preview-line">{previewLine(preview)}</p>}
      </div>

      <p className="demo-data-honest">{honestNote()}</p>
      {!canRun && (
        <p className="demo-data-readonly">
          Mode baca — hanya kepala SPPG dan ahli gizi SPPG yang boleh membangun
          atau membersihkan data demo.
        </p>
      )}
    </section>
  );
}
