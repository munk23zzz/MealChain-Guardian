"use client";

// Halaman "Keamanan Pangan" — halaman sidebar acuan /compliance, disesuaikan
// ke data repo ini (/batches). Papan CCP per-alat, bank sampel, dan jejak lot
// EPCIS dari acuan TIDAK dipakai karena tidak ada sumbernya di backend ini.
//
// Fase 11 (permintaan pemilik): halaman ini juga dipakai KEPALA SPPG — satu
// lokasi, satu dapur — bukan hanya pengawas nasional. Aturan yang dipegang:
//   - Cakupan: batch lokasi sendiri jadi default peran SPPG; tampilan jaringan
//     tetap tersedia lewat pemilih cakupan yang DINYATAKAN (tidak dicampur).
//   - Kiriman yang sedang menuju lokasi ini (`GET /supplier-routes`) dan satu
//     kalimat kebutuhan-vs-kiriman (`GET /balance/map`) — inilah yang menentukan
//     apakah stok cukup, bukan daftar batch milik SPPG lain.
//   - Tindakan menulis ke backend: "Periksa kiriman" / "Uji ulang" memanggil
//     POST /freshness/evaluate + POST /safety/evaluate (server menghitung ulang
//     dari log suhu & umur panen yang tersimpan, lalu menyimpan hasilnya), dan
//     "Ajukan ulang" memakai POST /actions/repropose.
//   - Masa layak diterjemahkan jadi keadaan (Kedaluwarsa / ≤48 jam / ≤7 hari),
//     bukan sekadar angka "kesegaran 0%".

import { useEffect, useRef, useState } from "react";

import PageHeader from "./PageHeader";
import FactList from "./FactList";
import {
  balanceForLocation,
  checkedForReceipt,
  coverageSentence,
  expiryState,
  incomingBatchId,
  incomingShipments,
  ownLocationRows,
  receiptRows,
  RECEIVING_CHECKS,
  RECEIVING_OTHER,
  receivingSentence,
  receivingState,
  safetyDecisions,
  safetyRows,
  safetySummaryOfRows,
  quarantineTone,
  sortByDeadline,
  usableLabel,
  type ReceiptCardRow,
  type SafetyRow,
} from "../lib/food-safety";
import { formatKg } from "../lib/overview-format";
import type { SupplierRoute } from "../lib/supplier-routes";
import { LoadingState } from "./LoadingState";
import Popup from "./Popup";
import ShipmentCard from "./ShipmentCard";
import ScrollHint from "./ScrollHint";

export type RecheckResult = {
  safety: { safety_status: string; reasons: string[]; excursion_minutes: number };
  freshness: { freshness_score: number; status: string; usable_until: string };
};

type Aksi = {
  where: "pasokan" | "batch" | "keputusan" | "terima";
  nada: "ok" | "danger";
  teks: string;
};

export default function FoodSafetyBoard({
  batches,
  now,
  loading = false,
  error = null,
  onRetry,
  ownLocation = null,
  ownLocationId = null,
  routes = null,
  balance = null,
  decisions = null,
  canMutate = false,
  canPropose = false,
  onRecheck,
  onRepropose,
  onTriggerDisruption,
  onRecordReceipt,
  loadReceipts,
  onOpenDecisions,
  onKarantina,
}: {
  batches: unknown[] | null;
  now: Date | null;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  /** Nama lokasi sendiri (peran SPPG). null = pengawas nasional. */
  ownLocation?: string | null;
  /** Id lokasi sendiri — dipakai sebagai TUJUAN keputusan keamanan (ruling 2026-10-14). */
  ownLocationId?: string | null;
  /** Payload `GET /supplier-routes` (kiriman yang sedang menuju lokasi). */
  routes?: unknown;
  /** Payload `GET /balance/map` untuk komoditas aktif (kebutuhan/tersedia). */
  balance?: unknown;
  /** Feed `GET /decisions` — sudah ber-scope di server. */
  decisions?: unknown[] | null;
  /** sppg_head / sppg_nutritionist — BGN Monitor read-only. */
  canMutate?: boolean;
  /** Hanya Kepala SPPG: mengajukan keputusan Event 3 = usul (PLAN.md §13.3). */
  canPropose?: boolean;
  onRecheck?: (batchId: string) => Promise<RecheckResult>;
  onRepropose?: (decisionId: string) => Promise<string>;
  /** Event 3 untuk satu batch (kunci idempotensi dibuat & dipegang komponen ini). */
  onTriggerDisruption?: (
    batchId: string,
    operationKey: string
  ) => Promise<{ status: string; decision_id: string | null; message?: string; safety_status?: string }>;
  /** Simpan catatan penerimaan (checklist + isian "Lainnya") ke database. */
  onRecordReceipt?: (
    batchId: string,
    checked: Record<string, boolean>,
    otherNote: string
  ) => Promise<unknown>;
  /** Riwayat catatan penerimaan sebuah batch (dibaca dari server). */
  loadReceipts?: (batchId: string) => Promise<unknown>;
  onOpenDecisions?: () => void;
  /** Karantina: menahan/melapas/menggagalkan batch = keputusan manusia. */
  onKarantina?: (
    batchId: string,
    aksi: "tahan" | "lepas" | "gagal",
    alasan: string
  ) => Promise<void>;
}) {
  const clock = now ?? new Date(0);
  const [scope, setScope] = useState<"own" | "all">(ownLocation ? "own" : "all");
  const [aksi, setAksi] = useState<Aksi | null>(null);
  const [sibuk, setSibuk] = useState<string | null>(null);
  const [centang, setCentang] = useState<Record<string, boolean>>({});
  const [catatan, setCatatan] = useState("");
  const [riwayat, setRiwayat] = useState<ReceiptCardRow[]>([]);
  const [terimaId, setTerimaId] = useState<string | null>(null);
  // Dialog alasan karantina: satu batch + satu aksi pada satu waktu.
  const [karantina, setKarantina] = useState<{
    batchId: string;
    aksi: "tahan" | "lepas" | "gagal";
    label: string;
  } | null>(null);
  const [alasanKarantina, setAlasanKarantina] = useState("");
  const [karantinaSibuk, setKarantinaSibuk] = useState(false);
  const [karantinaGalat, setKarantinaGalat] = useState<string | null>(null);
  // Kunci idempotensi Event 3 per batch: dikirim ULANG saat mengulang, sehingga
  // percobaan kedua dilayani dari catatan server (tidak membuat keputusan kembar).
  const kunciRef = useRef<Record<string, string>>({});
  // Pembaca riwayat catatan disimpan di ref supaya efek di bawah tidak memuat
  // ulang setiap render hanya karena prop-nya berupa fungsi baru.
  const muatRef = useRef(loadReceipts);
  muatRef.current = loadReceipts;

  // Cakupan menyesuaikan begitu identitas pemakai selesai dimuat (sebelum itu
  // `ownLocation` masih null karena /auth/me belum menjawab).
  useEffect(() => {
    setScope(ownLocation ? "own" : "all");
  }, [ownLocation]);

  const rows = safetyRows(batches, clock);
  const jaringan = Boolean(ownLocation) && scope === "all";
  const tampil = jaringan ? rows : ownLocation ? ownLocationRows(rows, ownLocation) : rows;
  const urut = sortByDeadline(tampil);
  const summary = safetySummaryOfRows(tampil);
  const summaryJaringan = safetySummaryOfRows(rows);

  const shipments = incomingShipments(routes, clock);
  const kirimanKe = ownLocation
    ? shipments.filter(
        (ship) => ship.destination.trim().toLowerCase() === ownLocation.trim().toLowerCase()
      )
    : shipments;
  // Cakupan yang SAMA dipakai ulang oleh kartu kiriman di bawah: satu aturan
  // ("kiriman yang menuju lokasi ini"), dua pemakaian — hitungan `masukKg` dan
  // daftar kartu. Penyaringnya diletakkan di logika murni `pickShipments`
  // (diuji), bukan di JSX, supaya hitungan "+N lain" ikut tersaring.
  const hanyaKeLokasi = ownLocation
    ? (row: SupplierRoute) =>
        row.destinationName.trim().toLowerCase() === ownLocation.trim().toLowerCase()
    : undefined;
  const masukKg = kirimanKe.reduce<number | null>(
    (total, ship) => (ship.kg === null ? total : (total ?? 0) + ship.kg),
    null
  );

  const slice = balanceForLocation(balance, ownLocation);
  const kalimat = slice
    ? coverageSentence({
        demandKg: slice.demandKg,
        supplyKg: slice.supplyKg,
        shortageKg: slice.shortageKg,
        incomingKg: masukKg,
      })
    : null;

  const keamanan = safetyDecisions(decisions);
  const kedaluwarsaJumlah = urut.filter((row) => expiryState(row.hoursLeft).key === "expired").length;

  // Batch yang jadi sasaran "Penerimaan barang": kiriman pertama yang bisa
  // dipasangkan dengan batch nyata (rute sering tidak membawa batch_id), kalau
  // tidak ada → batch paling mendesak di cakupan yang sedang dilihat.
  const batchOpsi = urut.filter((row) => Boolean(row.id));
  const terkirim = shipments[0] ?? null;
  const batchKiriman = terkirim
    ? incomingBatchId(rows, { commodity: terkirim.commodity ?? "", kg: terkirim.kg ?? 0 })
    : null;
  const idTerima = terimaId ?? batchKiriman ?? batchOpsi[0]?.id ?? null;

  // Riwayat catatan dimuat dari server setiap batch sasaran berganti (termasuk
  // saat identitas selesai dimuat dan pilihan default baru terbentuk). Hasil
  // pembacaan yang datang terlambat dibuang, supaya daftar tidak menampilkan
  // catatan batch yang sudah tidak dipilih.
  useEffect(() => {
    const batchId = idTerima;
    const baca = muatRef.current;
    if (!batchId || !baca) {
      setRiwayat([]);
      return;
    }
    let batal = false;
    baca(batchId)
      .then((payload) => {
        if (!batal) setRiwayat(receiptRows(payload));
      })
      .catch(() => {
        if (!batal) setRiwayat([]);
      });
    return () => {
      batal = true;
    };
  }, [idTerima]);

  // Karantina: dialog alasan dulu, baru kirim. Tidak ada aksi karantina yang
  // terjadi tanpa alasan tertulis — alasannya ikut masuk evidence ledger.
  function bukaKarantina(
    batchId: string,
    aksi: "tahan" | "lepas" | "gagal",
    label: string
  ) {
    setKarantina({ batchId, aksi, label });
    setAlasanKarantina("");
    setKarantinaGalat(null);
  }

  async function kirimKarantina() {
    if (!karantina || !onKarantina) return;
    const alasan = alasanKarantina.trim();
    if (!alasan) {
      setKarantinaGalat("Alasan wajib diisi.");
      return;
    }
    setKarantinaSibuk(true);
    setKarantinaGalat(null);
    try {
      await onKarantina(karantina.batchId, karantina.aksi, alasan);
      setKarantina(null);
      setAlasanKarantina("");
    } catch (error) {
      setKarantinaGalat(
        error instanceof Error ? error.message : "Gagal menyimpan keputusan karantina."
      );
    } finally {
      setKarantinaSibuk(false);
    }
  }

  async function periksa(id: string, where: Aksi["where"]) {
    if (!onRecheck) return;
    setSibuk(id);
    try {
      const hasil = await onRecheck(id);
      const bagian = [
        `keamanan ${hasil.safety.safety_status}`,
        `kesegaran ${Math.round(Number(hasil.freshness.freshness_score) * 100)}%`,
        `layak s/d ${usableLabel(hasil.freshness.usable_until)}`,
      ];
      const simpang = Number(hasil.safety.excursion_minutes);
      if (Number.isFinite(simpang) && simpang > 0) {
        bagian.push(`penyimpangan suhu ${Math.round(simpang)} menit`);
      }
      const gagal = String(hasil.safety.safety_status).toUpperCase() === "FAIL";
      setAksi({
        where,
        nada: gagal ? "danger" : "ok",
        teks: `Hasil periksa dari server: ${bagian.join(" · ")}.`,
      });
    } catch (err) {
      setAksi({ where, nada: "danger", teks: `Tidak bisa memeriksa: ${pesan(err)}` });
    } finally {
      setSibuk(null);
    }
  }

  async function ajukanUlang(decisionId: string) {
    if (!onRepropose) return;
    setSibuk(decisionId);
    try {
      const baru = await onRepropose(decisionId);
      setAksi({
        where: "keputusan",
        nada: "ok",
        teks: `Keputusan baru dibuat dari ${decisionId.slice(0, 8)}: ${String(baru).slice(0, 8)} (status: diusulkan).`,
      });
    } catch (err) {
      setAksi({
        where: "keputusan",
        nada: "danger",
        teks: `Tidak bisa mengajukan ulang: ${pesan(err)}`,
      });
    } finally {
      setSibuk(null);
    }
  }

  /** UUID v4 — dipakai sebagai kunci idempotensi Event 3 bila peramban tidak
   *  menyediakan `crypto.randomUUID` (mis. konteks non-secure). */
  function uuidAcak(): string {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      return crypto.randomUUID();
    }
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === "x" ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  /** Kunci idempotensi per batch: kunci yang SAMA saat mengulang → server
   *  melayani dari catatan, bukan membuat keputusan kembar (Event 3 §135). */
  function kunciOperasi(batchId: string): string {
    if (!kunciRef.current[batchId]) {
      kunciRef.current[batchId] = uuidAcak();
    }
    return kunciRef.current[batchId];
  }

  /** Event 3 untuk satu batch — batch gagal uji jadi keputusan penanganan
   *  yang menyasar LOKASI SENDIRI; batch aman dijawab "tidak ada keputusan". */
  async function ajukanKeputusan(batchId: string) {
    if (!onTriggerDisruption) return;
    setSibuk(`putus-${batchId}`);
    try {
      const hasil = await onTriggerDisruption(batchId, kunciOperasi(batchId));
      const id = hasil.decision_id ? String(hasil.decision_id) : null;
      setAksi(
        id
          ? {
              where: "batch",
              nada: "ok",
              teks:
                `Keputusan penanganan dibuat: ${id.slice(0, 8)} (status: diusulkan) — menyasar ` +
                `${ownLocation ?? "lokasi Anda"}. Bukti & jejak ada di tab Decision & Evidence.`,
            }
          : {
              where: "batch",
              nada: "ok",
              teks: `${hasil.message ?? "Server tidak menemukan gangguan pada batch ini."} — tidak ada keputusan baru yang dibuat.`,
            }
      );
    } catch (err) {
      setAksi({
        where: "batch",
        nada: "danger",
        teks: `Tidak bisa mengajukan keputusan: ${pesan(err)}`,
      });
    } finally {
      setSibuk(null);
    }
  }

  /** Catat hasil terima: daftar periksa petugas + hitung ulang di server
   *  (hasil hitung ulang inilah yang tersimpan di database). */
  async function catatTerima() {
    if (!onRecheck || !idTerima) return;
    setSibuk("terima");
    try {
      // Dua tulisan nyata, urut jelas: (1) catatan penerimaan (checklist +
      // isian "Lainnya") → `batch_receipts`; (2) hitung ulang keamanan &
      // kesegaran → kolom batch. Kalau (1) gagal, pesannya jujur menyebut
      // bagian mana yang gagal — tidak ada yang diam-diam hilang.
      let tersimpan: string;
      if (onRecordReceipt) {
        try {
          await onRecordReceipt(idTerima, checkedForReceipt(centang), catatan);
          tersimpan = "Catatan penerimaan tersimpan";
        } catch (err) {
          tersimpan = `Catatan penerimaan TIDAK tersimpan (${pesan(err)})`;
        }
      } else {
        tersimpan = "Catatan penerimaan tidak dikirim (jalur simpan belum tersedia)";
      }

      const hasil = await onRecheck(idTerima);
      const bagian = [
        `keamanan ${hasil.safety.safety_status}`,
        `kesegaran ${Math.round(Number(hasil.freshness.freshness_score) * 100)}%`,
        `layak s/d ${usableLabel(hasil.freshness.usable_until)}`,
      ];
      const simpang = Number(hasil.safety.excursion_minutes);
      if (Number.isFinite(simpang) && simpang > 0) {
        bagian.push(`penyimpangan suhu ${Math.round(simpang)} menit`);
      }
      setAksi({
        where: "terima",
        nada:
          String(hasil.safety.safety_status).toUpperCase() === "FAIL" ||
          tersimpan.includes("TIDAK")
            ? "danger"
            : "ok",
        teks: `${tersimpan}. ${receivingSentence(receivingState(centang))} Hasil dari server: ${bagian.join(" · ")}.`,
      });
      await muatRiwayat(idTerima);
    } catch (err) {
      setAksi({
        where: "terima",
        nada: "danger",
        teks: `Tidak bisa mencatat hasil terima: ${pesan(err)}`,
      });
    } finally {
      setSibuk(null);
    }
  }

  /** Riwayat catatan penerimaan dibaca dari server (bukan state layar). */
  async function muatRiwayat(batchId: string) {
    if (!muatRef.current) return;
    try {
      setRiwayat(receiptRows(await muatRef.current(batchId)));
    } catch {
      setRiwayat([]);
    }
  }

  /** Nama pemasok untuk batch yang cocok dengan kiriman (kolom "Asal"). */
  function asal(row: SafetyRow): string {
    const cocok = kirimanKe.find(
      (ship) => (ship.commodity ?? "").trim().toLowerCase() === row.commodity.trim().toLowerCase()
    );
    return cocok ? cocok.supplierName : "Stok sendiri";
  }

  return (
    <section className="board-page" aria-busy={loading || undefined}>
      <PageHeader
        title="Keamanan Pangan"
        description="Status keamanan tiap batch, kesegaran, dan sisa masa layak pakai. Batch gagal uji diblokir dari alokasi."
        meta={
          <span className="page-header-pills">
            <span className="commodity-pill">{summary.total} batch</span>
            <span className="commodity-pill">
              {jaringan ? "Jaringan" : ownLocation ? ownLocation : "Semua lokasi"}
            </span>
          </span>
        }
      />

      {error ? (
        <article className="card">
          <h2>Tidak bisa memuat batch</h2>
          <p className="evidence-note">{error}</p>
          {onRetry ? (
            <button type="button" className="button button-secondary" onClick={onRetry}>
              Coba lagi
            </button>
          ) : null}
        </article>
      ) : null}

      <div className="board-grid board-grid-2">
        <article className="card">
          <h2>Ringkasan pengawasan</h2>
          {/* Fase 5: tiga keadaan yang paling sering ditanya jadi tile angka besar
              dengan tint status; sisanya tetap daftar fakta supaya tidak ada angka
              yang kehilangan keterangan. Fase 11: angkanya mengikuti CAKUPAN yang
              dipilih (lokasi sendiri / jaringan), bukan campuran keduanya. */}
          <div className="stat-tiles">
            <div className="stat-tile stat-tile-ok">
              <span className="stat-tile-value">{loading && !batches ? "…" : String(summary.safe)}</span>
              <span className="stat-tile-label">Aman</span>
            </div>
            <div className={`stat-tile${summary.failed ? " stat-tile-danger" : ""}`}>
              <span className="stat-tile-value">{String(summary.failed)}</span>
              <span className="stat-tile-label">Gagal uji</span>
              {summary.failed ? (
                <span className="stat-tile-note">tidak boleh dialokasikan</span>
              ) : null}
            </div>
            <div className={`stat-tile${summary.needsVerification ? " stat-tile-warn" : ""}`}>
              <span className="stat-tile-value">{String(summary.needsVerification)}</span>
              <span className="stat-tile-label">Perlu verifikasi</span>
            </div>
            <div className={`stat-tile${summary.quarantined ? " stat-tile-danger" : ""}`}>
              <span className="stat-tile-value">{String(summary.quarantined)}</span>
              <span className="stat-tile-label">Ditahan (karantina)</span>
              {summary.quarantined ? (
                <span className="stat-tile-note">
                  {summary.quarantinedKg === null
                    ? "tidak boleh dialokasikan"
                    : `${formatKg(summary.quarantinedKg)} tidak boleh dialokasikan`}
                </span>
              ) : null}
            </div>
            {ownLocation ? (
              <div className={`stat-tile${kedaluwarsaJumlah ? " stat-tile-warn" : ""}`}>
                <span className="stat-tile-value">{String(kedaluwarsaJumlah)}</span>
                <span className="stat-tile-label">Kedaluwarsa</span>
                {kedaluwarsaJumlah ? <span className="stat-tile-note">lewat masa layak</span> : null}
              </div>
            ) : null}
          </div>
          <FactList
            rows={[
              { label: "Batch diperiksa", value: loading && !batches ? "…" : String(summary.total) },
              { label: "Belum diuji", value: String(summary.unchecked) },
              {
                label: "Berat batch gagal",
                value: summary.failedKg === null ? "—" : formatKg(summary.failedKg),
                tone: summary.failedKg === null ? "plain" : "danger",
              },
              ...(slice && slice.shortageKg !== null
                ? [
                    {
                      label: `Kekurangan${slice.commodity ? ` ${slice.commodity}` : ""}`,
                      value: slice.shortageKg > 0 ? formatKg(slice.shortageKg) : "tidak ada",
                      tone: slice.shortageKg > 0 ? ("danger" as const) : ("plain" as const),
                    },
                  ]
                : []),
            ]}
          />
          {summary.hasFail ? (
            ownLocation && !jaringan ? (
              <p className="board-alert">
                Batch gagal uji di lokasi ini: {summary.failedLocations.join(", ")} — alokasi hanya boleh
                memakai batch berstatus aman.
              </p>
            ) : (
              <p className="board-alert">
                Batch gagal uji: {summary.failedLocations.join(", ")} — alokasi hanya boleh memakai batch
                berstatus aman.
              </p>
            )
          ) : summaryJaringan.hasFail ? (
            <p className="evidence-note">
              Batch gagal uji di jaringan: {summaryJaringan.failedLocations.join(", ")} — bukan stok lokasi ini,
              jadi tidak memengaruhi alokasi Anda.
            </p>
          ) : (
            <p className="evidence-note">
              Tidak ada batch gagal uji pada data yang termuat saat ini.
            </p>
          )}
        </article>

        <article className="card">
          <h2>Batch perlu segera dipakai</h2>
          {urut.filter((row) => row.hoursLeft !== null && row.hoursLeft <= 48).length === 0 ? (
            <p className="evidence-note">
              Tidak ada batch yang sudah lewat batas layak atau tersisa ≤ 48 jam (sebagian batch mungkin belum
              punya tanggal).
            </p>
          ) : (
            <ul className="board-list">
              {urut
                .filter((row) => row.hoursLeft !== null && row.hoursLeft <= 48)
                .map((row) => {
                  const state = expiryState(row.hoursLeft);
                  return (
                    <li key={`${row.location}-${row.commodity}-${row.id}`}>
                      <span className="board-list-title">
                        {row.location} · {row.commodity}
                      </span>
                      <span className="board-list-meta">
                        {row.kg === null ? "—" : formatKg(row.kg)} · {row.hoursLabel}
                      </span>
                      <span className={`safety-state safety-state-${state.key}`}>{state.label}</span>
                    </li>
                  );
                })}
            </ul>
          )}
        </article>
      </div>

      {(ownLocation || kirimanKe.length > 0) && (
        <>
          {/* Kartu kiriman (Arah A riset 16 Okt 2026) MENGGANTIKAN daftar ringkas
              "Pasokan masuk" yang lama. Daftar itu menyajikan angka jalur yang
              sama (jarak, waktu tempuh, mutu, masa layak) tetapi halaman ini
              belum punya TAHAP perjalanan — dan menyimpan dua penyaji angka yang
              sama persis adalah kesalahan yang sudah dibuang di Overview. Tombol
              "Periksa kiriman" tetap ada, kini menempel pada kirimannya. */}
          <ShipmentCard
            routes={routes}
            hanya={hanyaKeLokasi}
            title={`Pasokan masuk${ownLocation ? ` menuju ${ownLocation}` : ""}`}
            note={kalimat ?? undefined}
            empty="Tidak ada kiriman aktif yang menuju lokasi ini menurut catatan jalur kiriman."
            action={(row) => {
              const batchId = incomingBatchId(tampil, {
                commodity: row.commodity,
                kg: row.quantityKg,
              });
              if (!batchId || !canMutate || !onRecheck) return null;
              return (
                <button
                  type="button"
                  className="button button-secondary"
                  disabled={sibuk === batchId}
                  onClick={() => void periksa(String(batchId), "pasokan")}
                >
                  {sibuk === batchId ? "Memeriksa…" : "Periksa kiriman"}
                </button>
              );
            }}
          />
          {aksi?.where === "pasokan" ? (
            <p className={aksi.nada === "danger" ? "board-alert" : "evidence-note"}>{aksi.teks}</p>
          ) : null}
        </>
      )}

      {ownLocation && batchOpsi.length > 0 ? (
        <article className="card">
          <div className="board-card-head">
            <h2>Penerimaan barang</h2>
            <span className="board-badge board-badge-muted">daftar periksa petugas</span>
          </div>
          <p className="evidence-note">
            Petugas memeriksa kiriman sebelum barang dipakai. Tombol di bawah menyimpan DUA hal ke
            database: hasil periksa ini (titik yang dicentang + isian &quot;Lainnya&quot;) dan
            hitung ulang keamanan &amp; kesegaran yang dihitung server dari log suhu serta umur
            panen yang tersimpan.
          </p>
          <label className="safety-pick">
            Batch yang diterima
            <select
              value={idTerima ?? ""}
              onChange={(event) => setTerimaId(event.target.value || null)}
            >
              {batchOpsi.map((row) => (
                <option key={String(row.id)} value={String(row.id)}>
                  {row.commodity} · {row.kg === null ? "—" : formatKg(row.kg)} · {row.location}
                </option>
              ))}
            </select>
          </label>
          <ul className="board-list safety-checks">
            {RECEIVING_CHECKS.map((item) => (
              <li key={item.id}>
                <label>
                  <input
                    type="checkbox"
                    checked={centang[item.id] === true}
                    onChange={(event) =>
                      setCentang((lama) => ({ ...lama, [item.id]: event.target.checked }))
                    }
                  />
                  <span>{item.label}</span>
                </label>
              </li>
            ))}
          </ul>
          {/* Permintaan pemilik: keadaan yang tidak ada di daftar harus bisa
              ditulis sendiri. Berdiri sendiri (bukan titik periksa ke-6), dan
              isinya disimpan ke `batch_receipts.other_note` — bukan hilang saat
              halaman dimuat ulang. */}
          <div className="safety-other">
            <label htmlFor={`catatan-${idTerima ?? "kosong"}`}>{RECEIVING_OTHER.label}</label>
            <textarea
              id={`catatan-${idTerima ?? "kosong"}`}
              value={catatan}
              maxLength={500}
              rows={2}
              placeholder={RECEIVING_OTHER.hint}
              onChange={(event) => setCatatan(event.target.value)}
            />
            <span className="evidence-note">
              {catatan.trim()
                ? `${catatan.trim().length} karakter — ikut tersimpan saat dicatat.`
                : `Catatan ini tersimpan ke database. Contoh: ${RECEIVING_OTHER.hint}.`}
            </span>
          </div>
          <p className="evidence-note">{receivingSentence(receivingState(centang))}</p>
          {canMutate && onRecheck && idTerima ? (
            <button
              type="button"
              className="button button-primary"
              disabled={sibuk === "terima"}
              onClick={() => void catatTerima()}
            >
              {sibuk === "terima" ? "Mencatat…" : "Catat hasil terima & hitung ulang"}
            </button>
          ) : (
            <p className="evidence-note">
              Hanya kepala SPPG dan ahli gizi yang bisa mencatat hasil terima.
            </p>
          )}
          {aksi?.where === "terima" ? (
            <p className={aksi.nada === "danger" ? "board-alert" : "evidence-note"}>{aksi.teks}</p>
          ) : null}
          {riwayat.length > 0 ? (
            <>
              <p className="board-subhead">Catatan penerimaan tersimpan (dari database)</p>
              <ul className="board-list safety-notes">
                {riwayat.map((r) => (
                  <li key={r.id}>
                    <span className="board-list-title">
                      {r.note ?? <em>tanpa catatan tambahan</em>}
                    </span>
                    <span className="board-list-meta">
                      {r.checkedCount === null ? "—" : `${r.checkedCount} titik`} ·{" "}
                      {r.byName ?? "—"} · {r.waktuLabel}
                    </span>
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </article>
      ) : null}

      <article className="card">
        <div className="board-card-head">
          <h2>Status keamanan per batch</h2>
          {ownLocation ? (
            <div className="safety-scope" role="group" aria-label="Cakupan lokasi">
              <span className="commodity-filters-label">Cakupan:</span>
              <button
                type="button"
                className={`commodity-pill${scope === "own" ? " commodity-pill-active" : ""}`}
                aria-pressed={scope === "own"}
                onClick={() => setScope("own")}
              >
                Lokasi saya — {ownLocation}
              </button>
              <button
                type="button"
                className={`commodity-pill${scope === "all" ? " commodity-pill-active" : ""}`}
                aria-pressed={scope === "all"}
                onClick={() => setScope("all")}
              >
                Semua lokasi (pengawasan)
              </button>
            </div>
          ) : null}
        </div>
        {urut.length === 0 ? (
          <p className="evidence-note">
            {loading ? <LoadingState label="Memuat batch…" /> : "Belum ada batch pada cakupan Anda."}
          </p>
        ) : (
          <>
            <div className="board-table-wrap">
              <table className="location-table">
                <thead>
                  <tr>
                    <th scope="col">{ownLocation && !jaringan ? "Asal" : "Lokasi"}</th>
                    <th scope="col">Komoditas</th>
                    <th scope="col" className="num">
                      Jumlah
                    </th>
                    <th scope="col">Status keamanan</th>
                    <th scope="col" className="num">
                      Kesegaran
                    </th>
                    <th scope="col">Layak sampai</th>
                    <th scope="col">Sisa masa</th>
                    {canMutate && (onRecheck || onKarantina) ? <th scope="col">Tindakan</th> : null}
                  </tr>
                </thead>
                <tbody>
                  {urut.map((row: SafetyRow) => {
                    const state = expiryState(row.hoursLeft);
                    return (
                      <tr key={row.id ?? `${row.location}-${row.commodity}`}>
                        <td>{ownLocation && !jaringan ? asal(row) : row.location}</td>
                        <td>{row.commodity}</td>
                        <td className="num">{row.kg === null ? "—" : formatKg(row.kg)}</td>
                        <td>
                          <span className={`board-badge board-badge-${row.tone}`}>{row.statusLabel}</span>
                          {row.quarantine !== "none" ? (
                            <>
                              {" "}
                              <span
                                className={`board-badge board-badge-${quarantineTone(row.quarantine)}`}
                                title="Batch ditahan dari kandidat alokasi sampai diverifikasi"
                              >
                                {row.quarantineLabel}
                              </span>
                            </>
                          ) : null}
                        </td>
                        <td className="num">{row.freshness}</td>
                        <td>{row.usableUntil}</td>
                        <td>
                          {state.key === "expired" || state.key === "urgent" || state.key === "watch" ? (
                            <>
                              <span className={`safety-state safety-state-${state.key}`}>{state.label}</span>{" "}
                            </>
                          ) : null}
                          {state.detail}
                        </td>
                        {canMutate && (onRecheck || onTriggerDisruption || onKarantina) ? (
                          <td>
                            <div className="safety-row-actions">
                              {row.id && onRecheck ? (
                                <button
                                  type="button"
                                  className="button button-secondary"
                                  disabled={sibuk === row.id}
                                  onClick={() => void periksa(String(row.id), "batch")}
                                >
                                  {sibuk === row.id ? "Menguji…" : "Uji ulang"}
                                </button>
                              ) : null}
                              {row.id && onTriggerDisruption && canPropose && row.tone === "danger" ? (
                                <button
                                  type="button"
                                  className="button button-secondary"
                                  disabled={sibuk === `putus-${row.id}`}
                                  onClick={() => void ajukanKeputusan(String(row.id))}
                                >
                                  {sibuk === `putus-${row.id}` ? "Mengajukan…" : "Ajukan keputusan"}
                                </button>
                              ) : null}
                              {row.id && onKarantina ? (
                                row.quarantine === "quarantined" ? (
                                  <>
                                    <button
                                      type="button"
                                      className="button button-secondary"
                                      onClick={() =>
                                        bukaKarantina(String(row.id), "lepas", "Lepas dari karantina")
                                      }
                                    >
                                      Lepas
                                    </button>
                                    <button
                                      type="button"
                                      className="button button-secondary"
                                      onClick={() =>
                                        bukaKarantina(String(row.id), "gagal", "Nyatakan gagal")
                                      }
                                    >
                                      Gagal
                                    </button>
                                  </>
                                ) : row.quarantine === "failed" ? null : (
                                  <button
                                    type="button"
                                    className="button button-secondary"
                                    onClick={() =>
                                      bukaKarantina(String(row.id), "tahan", "Tahan batch")
                                    }
                                  >
                                    Tahan
                                  </button>
                                )
                              ) : null}
                              {!row.id ? "—" : null}
                            </div>
                          </td>
                        ) : null}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <ScrollHint />
          </>
        )}
        {aksi?.where === "batch" ? (
          <p className={aksi.nada === "danger" ? "board-alert" : "evidence-note"}>{aksi.teks}</p>
        ) : null}
      </article>

      {karantina ? (
        <Popup
          open
          onClose={() => setKarantina(null)}
          title={karantina.label}
          description="Karantina menahan batch dari kandidat alokasi sampai keputusan Anda tercatat. Alasan wajib diisi dan ikut tersimpan di evidence ledger."
          labelledBy="karantina-title"
        >
          <label className="field">
            <span className="field-label">Alasan (tercatat di ledger)</span>
            <textarea
              value={alasanKarantina}
              onChange={(event) => setAlasanKarantina(event.target.value)}
              rows={3}
              placeholder="mis. log suhu menunjukkan excursion 12 menit, menunggu cek fisik"
            />
          </label>
          {karantinaGalat ? <p className="board-alert">{karantinaGalat}</p> : null}
          <div className="popup-actions">
            <button
              type="button"
              className="button button-secondary"
              onClick={() => setKarantina(null)}
            >
              Batal
            </button>
            <button
              type="button"
              className="button button-primary"
              disabled={karantinaSibuk || !alasanKarantina.trim()}
              onClick={() => void kirimKarantina()}
            >
              {karantinaSibuk ? "Menyimpan…" : "Simpan keputusan"}
            </button>
          </div>
        </Popup>
      ) : null}

      {decisions ? (
        <article className="card">
          <div className="board-card-head">
            <h2>Keputusan keamanan lokasi ini</h2>
            {onOpenDecisions ? (
              <button type="button" className="button button-secondary" onClick={onOpenDecisions}>
                Buka Decision &amp; Evidence
              </button>
            ) : null}
          </div>
          {keamanan.total === 0 ? (
            <p className="evidence-note">
              Belum ada keputusan keamanan untuk lokasi ini pada data yang termuat.
            </p>
          ) : (
            <>
              <p className="evidence-note">
                {keamanan.total} keputusan keamanan · {keamanan.active} masih berlaku ·{" "}
                {keamanan.reproposable} ditolak (bisa diajukan ulang) · {keamanan.expired} sudah lewat
                jendela berlaku
                {keamanan.pendingApproval ? ` · ${keamanan.pendingApproval} menunggu persetujuan` : ""}
                {keamanan.totalKg === null ? "" : ` · total ${formatKg(keamanan.totalKg)}`}. Dari{" "}
                {keamanan.allTotal} keputusan yang menyasar lokasi ini.
              </p>
              {keamanan.active === 0 ? (
                <p className="board-alert">
                  Tidak ada keputusan keamanan yang menunggu tanda tangan Anda saat ini. Yang sudah lewat
                  jendela berlaku tidak bisa diajukan ulang — menurut aturan server hanya keputusan yang
                  DITOLAK yang bisa, dan usulan baru datang dari rantai agen.
                </p>
              ) : null}
              <ul className="board-list">
                {keamanan.rows.slice(0, 5).map((row) => (
                  <li key={row.id}>
                    <span className="board-list-title">
                      Gangguan keamanan · {row.kg === null ? "—" : formatKg(row.kg)}
                    </span>
                    <span className="board-list-meta">
                      {row.statusLabel} · {row.valid ? "masih berlaku" : "kedaluwarsa"} · dibuat{" "}
                      {row.createdLabel}
                    </span>
                    {canMutate && onRepropose && row.canRepropose ? (
                      <button
                        type="button"
                        className="button button-secondary"
                        disabled={sibuk === row.id}
                        onClick={() => void ajukanUlang(row.id)}
                      >
                        {sibuk === row.id ? "Mengajukan…" : "Ajukan ulang"}
                      </button>
                    ) : null}
                  </li>
                ))}
              </ul>
              {keamanan.rows.length > 5 ? (
                <p className="evidence-note">
                  Menampilkan 5 dari {keamanan.rows.length} — sisanya di tab Decision &amp; Evidence.
                </p>
              ) : null}
            </>
          )}
          {aksi?.where === "keputusan" ? (
            <p className={aksi.nada === "danger" ? "board-alert" : "evidence-note"}>{aksi.teks}</p>
          ) : null}
        </article>
      ) : null}
    </section>
  );
}

function pesan(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}
