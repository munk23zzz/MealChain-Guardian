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

import { useCallback, useEffect, useRef, useState } from "react";

import PageHeader from "./PageHeader";
import SectionJump from "./SectionJump";
import { safetySections } from "../lib/section-jump";
import FactList from "./FactList";
import TemperatureEvidenceCard from "./TemperatureEvidenceCard";
import {
  balanceForLocation,
  checkedForReceipt,
  coverageSentence,
  evidenceRows,
  evidenceSummary,
  expiryState,
  FRESHNESS_OPEN,
  incomingBatchId,
  incomingKgForCommodity,
  incomingShipments,
  lowestFreshness,
  ownLocationRows,
  receiptRows,
  receivingChecks,
  RECEIVING_OTHER,
  receivingBatchOptions,
  receivingCommodityGroups,
  receiptSavedSentence,
  receivingSentence,
  receivingState,
  safetyDecisionSummaryLine,
  safetyDecisions,
  safetyRows,
  safetyStatusGroups,
  safetySummaryOfRows,
  quarantineTone,
  sortByDeadline,
  filterSafetyRows,
  safetyFilterCounts,
  type SafetyFilter,
  usableLabel,
  type ReceiptCardRow,
  type SafetyRow,
} from "../lib/food-safety";
import { formatKg } from "../lib/overview-format";
import { kodeWilayah } from "../lib/wilayah";
import type { SupplierRoute } from "../lib/supplier-routes";
import { LoadingState } from "./LoadingState";
import Popup from "./Popup";
import ShipmentCard from "./ShipmentCard";
import ScrollHint from "./ScrollHint";
import Pager from "./Pager";
import type { PendingReceiptRow } from "../lib/api";

/** Waktu catatan (WIB) untuk antrean persetujuan — bukan tanggal mentah ISO. */
function waktuCatat(iso: string): string {
  const parsed = Date.parse(iso);
  if (!Number.isFinite(parsed)) return "—";
  return new Date(parsed).toLocaleString("id-ID", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Jakarta",
  });
}
import styles from "./FoodSafetyBoard.module.css";
import { paginate } from "../lib/pagination";
import { rowNextSteps } from "../lib/safety-gate";
import { batchesToCsv, safetyBatchFileName, safetyExportJson } from "../lib/safety-export";
import { downloadText } from "../lib/export";

// Baris batch yang ditampilkan di kartu ringkas; dipakai di slice DAN kalimat
// "Menampilkan N dari M" supaya keduanya tidak bisa menyimpang (audit angka
// 18 Okt 2026).
const MAKS_BATCH_TERLIHAT = 5;

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
  loadPendingReceipts,
  onApproveReceipt,
  onRejectReceipt,
  canApprove = false,
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
  /** Antrean catatan yang sudah dibuat tetapi belum disetujui. */
  loadPendingReceipts?: () => Promise<{ items: PendingReceiptRow[]; total?: number }>;
  /** Kepala SPPG menyetujui penerimaan → stok masuk (server menulis supply). */
  onApproveReceipt?: (receiptId: string) => Promise<{ stock_kg?: number | null }>;
  /** Kepala SPPG menolak penerimaan; alasan wajib diisi. */
  onRejectReceipt?: (receiptId: string, note: string) => Promise<unknown>;
  /** Hanya kepala SPPG yang boleh memutuskan penerimaan (026). */
  canApprove?: boolean;
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
  const [antrean, setAntrean] = useState<PendingReceiptRow[]>([]);
  const [terimaId, setTerimaId] = useState<string | null>(null);
  // Penolakan: satu catatan + satu alasan pada satu waktu (026).
  const [tolakId, setTolakId] = useState<string | null>(null);
  const [alasanTolak, setAlasanTolak] = useState("");
  // Saringan daftar batch: pengguna memilih prioritas, bukan menggulir semua.
  const [saring, setSaring] = useState<SafetyFilter>("semua");
  const [cari, setCari] = useState("");
  const [halaman, setHalaman] = useState(1);
  /**
   * Saringan komoditas untuk daftar "Keputusan keamanan lokasi ini" — diisi dari
   * baris tabel status (dokumen `07-safety-evidence.md` §4.2 butir 1). `null` =
   * tidak disaring. Datanya sudah dimuat klien (`GET /decisions` →
   * `commodity_name`), jadi tidak ada endpoint baru.
   */
  const [komoditasKeputusan, setKomoditasKeputusan] = useState<string | null>(null);
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
  const jumlahPerSaringan = safetyFilterCounts(urut);
  const tersaring = filterSafetyRows(urut, saring, cari);
  const halamanData = paginate(tersaring, halaman, 8);
  const summary = safetySummaryOfRows(tampil);
  const summaryJaringan = safetySummaryOfRows(rows);
  // Bukti suhu mengikuti CAKUPAN baris yang sama dengan tabel status: `own`
  // menyaring lokasi sendiri, `all` memakai seluruh jaringan. Menghitungnya dari
  // daftar penuh akan membuat panel bukti berbeda cakupan dengan tabel di bawah.
  const bukti = evidenceRows(
    Array.isArray(batches)
      ? batches.filter((b) => {
          if (jaringan) return true;
          if (!ownLocation) return true;
          const lokasi = String((b as { location?: unknown })?.location ?? "").trim();
          return lokasi === ownLocation.trim();
        })
      : batches,
  );
  const buktiRingkas = evidenceSummary(bukti);

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
  const slice = balanceForLocation(balance, ownLocation);
  // Hanya kiriman KOMODITAS YANG SAMA yang boleh menutup kekurangan komoditas
  // itu (audit 26 Okt 2026: dulu beras + wortel + ayam ikut dijumlahkan untuk
  // menutup kekurangan telur).
  const masukKg = incomingKgForCommodity(kirimanKe, slice?.commodity ?? null);
  const kalimat = slice
    ? coverageSentence({
        demandKg: slice.demandKg,
        supplyKg: slice.supplyKg,
        shortageKg: slice.shortageKg,
        incomingKg: masukKg,
        commodity: slice.commodity,
        neededBy: slice.demandNeededBy,
      })
    : null;

  const keamanan = safetyDecisions(decisions, komoditasKeputusan);
  // Komoditas yang punya keputusan keamanan — dipakai tabel status untuk
  // memasang tautan "lihat keputusan" HANYA pada baris yang tujuannya ada.
  const komoditasBerKeputusan = keamanan.commodities;
  // Kesegaran: tiga terendah terbuka, sisanya di lipatan (butir 3). Tabel status
  // di bawah tetap menampilkan SEMUA baris tanpa lipatan — tidak ada yang hilang.
  const kesegaran = lowestFreshness(urut, FRESHNESS_OPEN);

  // Batch yang jadi sasaran "Penerimaan barang": SELALU milik dapur sendiri
  // (audit 20 Okt 2026 — cakupan tabel tidak boleh ikut menentukan, sebab batch
  // kota lain ditolak server dengan 403). Kiriman pertama yang bisa dipasangkan
  // dengan batch nyata menentukan pilihan awal; kalau tidak ada, batch paling
  // mendesak di dapur ini.
  const batchOpsi = receivingBatchOptions(rows, ownLocation);
  const grupKomoditas = receivingCommodityGroups(rows, ownLocation);
  const terkirim = shipments[0] ?? null;
  const batchKiriman = terkirim
    ? incomingBatchId(batchOpsi, { commodity: terkirim.commodity ?? "", kg: terkirim.kg ?? 0 })
    : null;
  const idTerima = terimaId ?? batchKiriman ?? batchOpsi[0]?.id ?? null;
  const batchTerpilih = batchOpsi.find((row) => row.id === idTerima) ?? null;
  // Blok bukti batch yang sedang diterima (MG/phase-03 butir 5): diambil dari
  // baris `/batches` mentah, bukan dihitung ulang di layar.
  const buktiTerpilih =
    evidenceRows(batches).find((row) => row.id !== null && row.id === idTerima) ?? null;
  // Dua langkah: komoditas dulu, baru batch. Nilai komoditas mengikuti batch
  // yang sedang terpilih supaya kedua <select> tidak pernah saling bertentangan.
  const komoditasTerpilih = batchTerpilih?.commodity ?? grupKomoditas[0]?.commodity ?? "";
  const batchSatuKomoditas =
    grupKomoditas.find((grup) => grup.commodity === komoditasTerpilih)?.rows ?? [];

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
        // Kalau catatan gagal disimpan, yang perlu dibaca adalah sebabnya + apa
        // yang belum diperiksa. Kalau tersimpan, kalimatnya memakai bentuk
        // lampau (`receiptSavedSentence`) — bukan perintah menandai ulang.
        teks: `${
          tersimpan.includes("TIDAK")
            ? `${tersimpan}. ${receivingSentence(receivingState(centang))}`
            : receiptSavedSentence(receivingState(centang))
        } Hasil dari server: ${bagian.join(" · ")}.`,
      });
      // Batch yang baru dicatat sudah dinilai → keluar dari daftar "belum
      // dinilai" dan muncul di kartu "Menunggu persetujuan". Form pindah ke
      // batch berikutnya supaya tidak menunjuk batch yang sudah tidak ada.
      setCentang({});
      setCatatan("");
      setRiwayat([]);
      setTerimaId(null);
      await muatAntrean();
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

  /** Kepala SPPG menyetujui penerimaan → server menulis stok, lalu angka
   *  Overview/Hari Ini diambil ulang oleh pemanggil (bukan dihitung di layar). */
  const muatAntrean = useCallback(async () => {
    if (!loadPendingReceipts) return;
    try {
      const hasil = await loadPendingReceipts();
      setAntrean(Array.isArray(hasil?.items) ? hasil.items : []);
    } catch {
      // Antrean gagal dimuat tidak boleh menjatuhkan kartu penerimaan;
      // form tetap bisa dipakai dan galatnya tampil lewat tombol setujui.
      setAntrean([]);
    }
  }, [loadPendingReceipts]);

  useEffect(() => {
    void muatAntrean();
  }, [muatAntrean]);

  async function setujuiTerima(receiptId: string) {
    if (!onApproveReceipt) return;
    setSibuk("setujui");
    try {
      const hasil = await onApproveReceipt(receiptId);
      const kg = typeof hasil?.stock_kg === "number" ? hasil.stock_kg : null;
      setAksi({
        where: "terima",
        nada: "ok",
        teks: kg === null
          ? "Penerimaan disetujui. Angka pasokan di Overview dan Hari Ini ikut diperbarui."
          : `Penerimaan disetujui — ${kg.toLocaleString("id-ID")} kg masuk stok. Angka pasokan di Overview dan Hari Ini ikut diperbarui.`,
      });
      setTolakId(null);
      // Batch yang disetujui keluar dari daftar "perlu diperiksa/dicatat".
      // Pindah ke batch berikutnya supaya <select> tidak menunjuk nilai yang
      // sudah tidak ada; kalimat sukses tetap tampil.
      setCentang({});
      setCatatan("");
      const berikut = batchOpsi.find((row) => row.id !== idTerima);
      setTerimaId(null);
      if (berikut?.id) await muatRiwayat(String(berikut.id));
      else setRiwayat([]);
      await muatAntrean();
    } catch (err) {
      setAksi({
        where: "terima",
        nada: "danger",
        teks: `Tidak bisa menyetujui penerimaan: ${pesan(err)}`,
      });
    } finally {
      setSibuk(null);
    }
  }

  /** Tolak penerimaan: alasan wajib — server juga menolak alasan kosong. */
  async function tolakTerima(receiptId: string) {
    if (!onRejectReceipt) return;
    const alasan = alasanTolak.trim();
    if (alasan.length < 3) {
      setAksi({
        where: "terima",
        nada: "danger",
        teks: "Alasan penolakan wajib diisi (minimal 3 karakter) — petugas perlu tahu apa yang harus diperbaiki.",
      });
      return;
    }
    setSibuk("tolak");
    try {
      await onRejectReceipt(receiptId, alasan);
      setAksi({
        where: "terima",
        nada: "ok",
        teks: "Penerimaan ditolak dengan alasan tersimpan. Tidak ada stok yang ditambahkan.",
      });
      setTolakId(null);
      setAlasanTolak("");
      await muatAntrean();
      setRiwayat([]);
      setTerimaId(null);
    } catch (err) {
      setAksi({
        where: "terima",
        nada: "danger",
        teks: `Tidak bisa menolak penerimaan: ${pesan(err)}`,
      });
    } finally {
      setSibuk(null);
    }
  }

  /** Catatan terbaru yang masih menunggu keputusan untuk batch terpilih. */
  const menunggu = riwayat.find((r) => r.status === "menunggu") ?? null;
  const sudahDisetujui = riwayat.find((r) => r.status === "disetujui") ?? null;

  /** Nama pemasok untuk batch yang cocok dengan kiriman (kolom "Asal"). */
  function asal(row: SafetyRow): string {
    const cocok = kirimanKe.find(
      (ship) => (ship.commodity ?? "").trim().toLowerCase() === row.commodity.trim().toLowerCase()
    );
    return cocok ? cocok.supplierName : "Stok sendiri";
  }

  /**
   * Lompat dari baris postur ke gerbang keputusan komoditas itu (butir 1).
   *
   * Tidak ada data baru yang diambil: penyaringnya bekerja pada `decisions` yang
   * sudah dimuat. Kalau komoditas itu tidak punya keputusan keamanan, saringannya
   * tetap dipasang dan daftar menulis apa adanya ("belum ada keputusan") — lebih
   * jujur daripada tombol yang tidak melakukan apa pun.
   */
  function saringKeputusanKomoditas(komoditas: string | null) {
    setKomoditasKeputusan(komoditas);
    document
      .getElementById("safety-keputusan")
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  /**
   * Ekspor baca-saja (butir 6): isinya baris yang SEDANG tampil setelah saringan
   * bilah alat (`tersaring`), bukan seluruh batch yang dimuat — berkas harus bisa
   * dicocokkan baris per baris dengan tabel di layar.
   */
  function eksporBatch(format: "csv" | "json") {
    const nama = safetyBatchFileName(format);
    if (format === "csv") {
      downloadText(nama, batchesToCsv(tersaring), "text/csv;charset=utf-8");
      return;
    }
    downloadText(
      nama,
      safetyExportJson({ rows: tersaring, summary, decisions: keamanan }),
      "application/json;charset=utf-8"
    );
  }

  // Nav "lompat ke bagian": tujuan dibangun dari kondisi render yang SAMA dengan
  // bagiannya, supaya tidak ada tautan yang menunjuk bagian yang tidak dirender.
  // - "Penerimaan barang" hanya untuk peran dengan SPPG sendiri, dan baru muncul
  //   setelah batch selesai dimuat (kedua cabangnya butuh `batches`).
  // - "Keputusan keamanan lokasi ini" hanya bila daftar keputusan tersedia.
  const adaPenerimaan = Boolean(ownLocation) && !loading && Array.isArray(batches);
  // Nada BAND ringkasan (tampilan saja): kartu memakai tint keadaan terburuk
  // supaya halaman menjawab "ada yang gagal?" sebelum angkanya dibaca. Nilainya
  // turunan dari angka server yang sudah dipakai tile — tidak ada hitungan baru.
  const nadaBand =
    summary.failed > 0 || summary.quarantined > 0
      ? "danger"
      : summary.needsVerification > 0
        ? "warn"
        : "ok";
  // Label kepala band sengaja TANPA angka: angkanya sudah ada di tile, dan
  // halaman ini tidak menyimpan dua penyaji angka yang sama.
  const labelBand =
    nadaBand === "danger" ? "Ada batch gagal" : nadaBand === "warn" ? "Perlu verifikasi" : "Semua aman";

  // LIMA kelompok EKSKLUSIF (aman, gagal, perlu verifikasi, belum diuji,
  // ditahan) — jumlahnya selalu = batch yang diperiksa.
  //
  // Mengapa berubah (29 Okt 2026, "desain begitu masih sulit dipahami"):
  // versi lama memakai empat angka yang TIDAK menjumlah ke total (batch
  // karantina tidak masuk "aman" tetapi tetap dihitung "gagal" bila ujinya
  // gagal), lalu menambal selisihnya dengan bar komposisi, persentase per
  // angka, titik warna, dan lipatan "Cara membaca angka ini". Tiga pengkodean
  // untuk satu himpunan data, dan tetap ada angka yang tidak cocok. Sekarang:
  // satu angka satu kelompok, tanpa persentase, tanpa bar, tanpa legenda.
  // `tampil` = baris sesuai CAKUPAN terpilih (lokasi sendiri / jaringan),
  // sama dengan yang dipakai tabel status dan `summary`.
  const grupStatus = safetyStatusGroups(tampil);
  const tileUji = grupStatus.map((grup) => ({
    key: grup.key,
    label: grup.label,
    value: loading && !batches && grup.key === "aman" ? "…" : String(grup.value),
    // Nol tidak diberi warna: angka 0 yang merah/kuning terbaca sebagai
    // peringatan padahal tidak ada yang perlu dikerjakan.
    tone: grup.value > 0 ? grup.tone : ("muted" as const),
    // Berat kelompok (29 Okt 2026): `failedKg` sudah dihitung server, tetapi
    // sebelumnya hanya "Ditahan" yang memperlihatkan berat — angka gagal
    // terbaca tanpa akibatnya. Kelompok lain tidak punya berat di server, jadi
    // `null` (tidak dicetak) dan bukan 0.
    kg:
      grup.key === "gagal"
        ? summary.failedKg
        : grup.key === "ditahan"
          ? summary.quarantinedKg
          : null,
  }));

  // Tenggat terdekat (29 Okt 2026): satu-satunya pertanyaan yang tidak dijawab
  // lima angka — kapan batch yang MASIH boleh dipakai paling cepat kedaluwarsa.
  // Batch gagal dan yang ditahan sengaja tidak ikut: keduanya tidak boleh
  // dialokasikan, sehingga "segera pakai" untuk keduanya adalah kalimat yang
  // menyesatkan. Urutannya memakai `hoursLeft` server, bukan taksiran layar.
  const terdekat =
    tampil
      .filter(
        (row) =>
          row.tone !== "danger" &&
          row.quarantine !== "quarantined" &&
          row.hoursLeft !== null
      )
      .sort((a, b) => (a.hoursLeft as number) - (b.hoursLeft as number))[0] ?? null;
  // Baris yang tanggalnya sudah lewat tetap yang paling perlu perhatian, tetapi
  // labelnya tidak boleh berbunyi "paling mendesak" — kalimat itu terbaca
  // seperti saran memakainya. Label berganti, bukan datanya disembunyikan.
  const tenggatLewat = terdekat !== null && (terdekat.hoursLeft as number) < 0;


  // Satu kalimat keterangan untuk pembaca layar: lima angka + total.
  const ringkasUji =
    `${summary.total} batch diperiksa: ` +
    grupStatus.map((grup) => `${grup.value} ${grup.label.toLowerCase()}`).join(", ") +
    ".";

  const bagianNav = safetySections({
    ownLocation: adaPenerimaan,
    hasDecisions: Boolean(decisions),
  });
  return (
    <section className="board-page safety-page" aria-busy={loading || undefined}>
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

      {/* Navigasi bagian: halaman ini lima bagian yang tidak saling menggantikan
          (ringkasan, batch mendesak, penerimaan, tabel status, keputusan), dan
          aksi tulis tersebar di beberapa bagian — setelah satu aksi, pembaca
          harus bisa kembali ke bagian yang tepat tanpa menggulir buta. */}
      <SectionJump items={bagianNav} ariaLabel="Bagian halaman Keamanan Pangan" />

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

      <article className="card jump-target safety-band" id="safety-ringkasan" data-tone={nadaBand}>
        <div className="board-card-head">
          <h2>Ringkasan pengawasan</h2>
          <span className="safety-head-right">
            {summary.failed + summary.needsVerification + summary.quarantined > 0 ? (
              <button
                type="button"
                className="button button-secondary safety-head-cta"
                onClick={() => {
                  setSaring(summary.failed ? "gagal" : "tindakan");
                  setHalaman(1);
                  document
                    .getElementById("safety-daftar")
                    ?.scrollIntoView({ behavior: "smooth", block: "start" });
                }}
              >
                {summary.failed
                  ? `Tinjau ${summary.failed} batch gagal`
                  : `Tinjau ${
                      summary.needsVerification + summary.quarantined + summary.unchecked
                    } batch perlu tindakan`}
              </button>
            ) : null}
          </span>
        </div>

        {/* Putusan: satu titik status + satu kalimat, TANPA bidang merah selebar
            kartu (29 Okt 2026). Bidang penuh membuat hari yang punya satu batch
            gagal terasa seperti halaman galat, dan ia menenggelamkan lima angka
            di bawahnya. Lencana "Ada batch gagal" juga dilepas: kalimat ini
            sudah menyebut kejadiannya, badge hanya mengulang. */}
        <p className={`safety-verdict is-${nadaBand}`} title={labelBand}>
          <span className="safety-verdict-dot" aria-hidden="true" />
          <span>
            {summary.hasFail ? (
              ownLocation && !jaringan ? (
                <>
                  Batch gagal uji di lokasi ini: {summary.failedLocations.join(", ")} — alokasi
                  hanya boleh memakai batch berstatus aman.
                </>
              ) : (
                <>
                  Batch gagal uji: {summary.failedLocations.join(", ")} — alokasi hanya boleh
                  memakai batch berstatus aman.
                </>
              )
            ) : summaryJaringan.hasFail ? (
              <>
                Batch gagal uji di jaringan: {summaryJaringan.failedLocations.join(", ")} — bukan
                stok lokasi ini, jadi tidak memengaruhi alokasi Anda.
              </>
            ) : (
              <>Tidak ada batch gagal uji pada data yang termuat saat ini.</>
            )}
          </span>
        </p>

        {/* Tenggat terdekat: satu baris yang menjawab "apa yang paling mendesak
            sekarang" tanpa mengulang lima angka di bawahnya. Hanya muncul bila
            ada baris yang benar-benar punya tanggal layak DAN masih boleh
            dipakai — tidak ada tanggal berarti tidak ada kalimat, bukan "—". */}
        {terdekat ? (
          <p className="safety-deadline" data-keadaan={tenggatLewat ? "lewat" : "mendesak"}>
            <span className="safety-deadline-label">
              {tenggatLewat ? "Sudah lewat" : "Paling mendesak"}
            </span>
            <span className="safety-deadline-body">
              <strong>{terdekat.commodity}</strong> · {terdekat.location}
              <span className="safety-deadline-time">{terdekat.hoursLabel}</span>
            </span>
          </p>
        ) : null}

        {/* Lima angka, satu arti per angka. Kelompoknya eksklusif sehingga
            jumlahnya selalu = batch diperiksa; tidak ada bar, persentase, atau
            legenda. Pemisah vertikal menggantikan kotak per angka. */}
        <div className="safety-counts" role="list" aria-label={ringkasUji}>
          {tileUji.map((tile) => (
            <div key={tile.key} className={`safety-count is-${tile.tone}`} role="listitem">
              <span className="safety-count-value">{tile.value}</span>
              <span className="safety-count-label">{tile.label}</span>
              {tile.kg !== null && tile.value !== "0" ? (
                <span
                  className="safety-count-note"
                  title={`${formatKg(tile.kg)} tidak boleh dialokasikan`}
                >
                  {formatKg(tile.kg)}
                </span>
              ) : tile.key === "ditahan" && summary.quarantined > 0 ? (
                // Berat yang tidak dikirim server tetap dinyatakan: "tidak
                // tercatat" berbeda dari "nol kg" dan tetap berarti tidak boleh
                // dialokasikan.
                <span
                  className="safety-count-note"
                  title="Berat tidak tercatat: tidak boleh dialokasikan"
                >
                  berat tidak tercatat
                </span>
              ) : null}
            </div>
          ))}
        </div>

        <div className="safety-counts-foot">
          <span className="safety-counts-total">
            {summary.total > 0 ? `dari ${summary.total} batch` : "belum ada batch"}
          </span>
          <details className="safety-more">
            <summary>Rincian angka</summary>
            <FactList
              rows={[
                { label: "Batch diperiksa", value: String(summary.total) },
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
          </details>
        </div>
      </article>

      <div className="board-grid safety-grid-evidence">

        <TemperatureEvidenceCard rows={bukti} summary={buktiRingkas} />

        <article className="card jump-target" id="safety-segera">
          <div className="board-card-head">
            <h2>Batch perlu segera dipakai</h2>
            <span className="board-badge board-badge-muted">≤ 48 jam</span>
          </div>
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
                        {kodeWilayah(row.location)} · {row.commodity}
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

        {/* Rincian kesegaran (dokumen `07-safety-evidence.md` §4.2 butir 3):
            tiga skor terendah duduk TERBUKA, sisanya di satu lipatan. Tabel
            "Status keamanan per batch" di bawah tetap menampilkan SEMUA baris
            tanpa lipatan — ringkasan ini alat pindai, bukan pengganti tabel. */}
        <article className="card" id="safety-segar">
          <div className="board-card-head">
            <h2>Kesegaran terendah</h2>
            <span className="board-badge board-badge-muted">{FRESHNESS_OPEN} terendah</span>
          </div>
          {urut.length === 0 ? (
            <p className="evidence-note">Belum ada batch pada cakupan Anda.</p>
          ) : kesegaran.open.length === 0 ? (
            <p className="evidence-note">
              Tidak ada batch yang punya skor kesegaran pada data ini — skor kosong ditulis “—” dan
              tidak pernah dibaca sebagai 0.
            </p>
          ) : (
            <>
              <ul className="board-list">
                {kesegaran.open.map((row) => (
                  <li key={`segar-${row.id ?? `${row.location}-${row.commodity}`}`}>
                    <span className="board-list-title">
                      {kodeWilayah(row.location)} · {row.commodity}
                    </span>
                    <span className="board-list-meta">
                      Skor segar {row.freshness} · layak {row.usableUntil}
                    </span>
                  </li>
                ))}
              </ul>
              {kesegaran.rest.length > 0 ? (
                <details className="safety-more">
                  <summary>{kesegaran.rest.length} batch lain</summary>
                  <ul className="board-list">
                    {kesegaran.rest.map((row) => (
                      <li key={`segar-sisa-${row.id ?? `${row.location}-${row.commodity}`}`}>
                        <span className="board-list-title">
                          {kodeWilayah(row.location)} · {row.commodity}
                        </span>
                        <span className="board-list-meta">
                          Skor segar {row.freshness} · layak {row.usableUntil}
                        </span>
                      </li>
                    ))}
                  </ul>
                </details>
              ) : null}
              <p className="evidence-note">
                Skor kosong ditulis “—” dan tidak pernah dibaca sebagai 0. Dihitung dari {urut.length}{" "}
                batch yang termuat (server mengirim maksimum 500 baris terbaru) — bukan seluruh
                riwayat.
              </p>
            </>
          )}
        </article>
      </div>

      {/* Kartu "Pasokan masuk" DIPINDAH ke bawah tabel Status per batch
          (lihat blok bertanda PASOKAN MASUK di dekat akhir render). Alasan
          urutan: halaman ini sekarang mengalir keadaan → bukti → tindakan →
          rujukan → konteks → jejak. Kartu kiriman setinggi ±680 px dan tidak
          memuat aksi, jadi ia dulu memutus dua kartu bertindak (Penerimaan dan
          Menunggu persetujuan) yang sekarang berdampingan. */}

      {ownLocation && !loading && batches && batchOpsi.length === 0 ? (
        <article className="card jump-target" id="safety-terima">
          <h2>Penerimaan barang</h2>
          <p className="evidence-note">
            Tidak ada barang baru yang menunggu diuji di {ownLocation}. Barang yang sudah
            dinilai tidak muncul di sini; catatan yang menunggu persetujuan ada di kartunya
            sendiri.
          </p>
          {aksi?.where === "terima" ? (
            <p className={aksi.nada === "danger" ? "board-alert" : "evidence-note"}>{aksi.teks}</p>
          ) : null}
        </article>
      ) : null}

      {ownLocation && batchOpsi.length > 0 ? (
        <article className="card jump-target" id="safety-terima">
          <div className="board-card-head">
            <h2>Penerimaan barang</h2>
            <span className="board-badge board-badge-muted">daftar periksa petugas</span>
          </div>
          {/* MG/phase-04 poin 7: ceklis penerimaan (`POST /receipts`) dan
              karantina (`POST /batches/{id}/quarantine`) adalah dua tindakan
              berbeda dengan akibat berbeda. Petugas pernah membacanya sebagai
              satu hal, lalu mengira mencentang kotak berarti menahan batch. */}
          <p className="evidence-note">
            Ini ceklis penerimaan, <strong>bukan karantina</strong>: catatan di sini
            tidak menahan batch dan tidak mengubah status keamanannya. Menahan atau
            melepas batch dilakukan lewat tombol karantina di kolom Tindakan.
          </p>
          <p className="evidence-note">
            Petugas memeriksa kiriman sebelum barang dipakai. Tombol di bawah menulis dua hal ke
            database: catatan periksa ini (titik yang dicentang + isian &quot;Lainnya&quot;), lalu
            hasil hitung ulang keamanan &amp; kesegaran dari log suhu dan umur panen yang tersimpan
            — dihitung server, bukan layar.
          </p>
          <fieldset className={styles.pickStep}>
            <legend>1. Komoditas</legend>
            <div className={styles.commodityChips} role="group" aria-label="Pilih komoditas">
              {grupKomoditas.map((grup) => {
                const aktif = grup.commodity === komoditasTerpilih;
                return (
                  <button
                    key={grup.commodity}
                    type="button"
                    className={`commodity-pill${aktif ? " commodity-pill-active" : ""}`}
                    aria-pressed={aktif}
                    onClick={() => {
                      if (aktif) return;
                      const pertama = grup.rows[0];
                      setCentang({});
                      if (pertama?.id) setTerimaId(String(pertama.id));
                    }}
                  >
                    {grup.commodity}
                    <span className="safety-filter-count">{grup.rows.length}</span>
                  </button>
                );
              })}
            </div>
          </fieldset>
          <fieldset className={styles.pickStep}>
            <legend>2. Barang yang belum diuji</legend>
            <p className={`evidence-note ${styles.stepHint}`}>
              Satu batch = satu kiriman dengan berat dan masa layaknya sendiri. Yang sudah punya
              hasil uji (Aman, Gagal uji, Perlu verifikasi) tidak muncul di sini; begitu dicatat,
              barang pindah ke antrean &ldquo;Menunggu persetujuan&rdquo;.
            </p>
            <ul className={styles.batchList}>
              {batchSatuKomoditas.map((row) => (
                <li key={String(row.id)}>
                  <label className={styles.batchItem}>
                    <input
                      type="radio"
                      name="batch-terima"
                      value={String(row.id)}
                      checked={idTerima === row.id}
                      onChange={() => {
                        setCentang({});
                        setTerimaId(String(row.id));
                      }}
                    />
                    <span className={styles.batchBody}>
                      <span className={styles.batchTitle}>
                        {row.kg === null ? "—" : formatKg(row.kg)} · {kodeWilayah(row.location)}
                      </span>
                      <span className={styles.batchMeta}>
                        belum diperiksa · layak s/d {row.usableUntil}
                      </span>
                    </span>
                    <span className={`board-badge board-badge-${row.tone}`}>
                      {row.statusLabel}
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          </fieldset>          {/* Keadaan batch terpilih ditaruh DI LUAR <label>: kalau di dalam, teks
              ini ikut terbaca sebagai nama field. Di ponsel (301 px) pilihan di
              dalam <select> terpotong, jadi keadaan yang membedakan batch
              (keamanan + masa layak) harus terbaca tanpa membuka daftar. */}
          {batchTerpilih ? (
            <p className="evidence-note safety-pick-state">
              Keadaan batch: {batchTerpilih.statusLabel} · layak s/d{" "}
              <span className="safety-nobr">{batchTerpilih.usableUntil}</span>
              {batchTerpilih.hoursLeft !== null && batchTerpilih.hoursLeft < 0
                ? " · sudah kedaluwarsa"
                : ""}
            </p>
          ) : null}
          {/* MG/phase-03 butir 5: "Goods Receipt menjelaskan apakah bukti suhu
              cukup." Penjelasannya memakai blok `evidence` dari server apa
              adanya — asal log, kelengkapan, dan waktu observasi — supaya
              petugas tahu apakah kiriman ini terverifikasi atau menunggu. */}
          {buktiTerpilih ? (
            <p className="evidence-note safety-pick-state" data-role="bukti-terima">
              Bukti suhu kiriman ini: <strong>{buktiTerpilih.stateLabel}</strong>
              {" · "}
              {buktiTerpilih.observationLabel}
              {" · "}
              {buktiTerpilih.sourceLabel}
              {buktiTerpilih.observedAt ? ` · diamati ${buktiTerpilih.observedAt}` : ""}
              {buktiTerpilih.sufficient
                ? " — boleh dicentang dan dipakai."
                : " — periksa dulu sebelum dipakai."}
            </p>
          ) : null}
          <fieldset className="safety-checks-set">
            <legend>Titik periksa</legend>
            <ul className="board-list safety-checks">
              {receivingChecks(komoditasTerpilih).map((item) => (
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
          </fieldset>
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
                : "Ikut tersimpan ke database bersama catatan penerimaan ini."}
            </span>
          </div>
          <p className="evidence-note" aria-live="polite">
            {receivingSentence(receivingState(centang))}
          </p>
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
          {menunggu ? (
            <p className="evidence-note">
              Catatan terbaru berstatus <strong>menunggu persetujuan kepala SPPG</strong> — stok
              belum bertambah sampai disetujui.
            </p>
          ) : null}
          {menunggu && batchTerpilih?.hoursLeft != null && batchTerpilih.hoursLeft < 0 ? (
            <p className="board-alert">
              Batch ini sudah kedaluwarsa — tidak bisa disetujui masuk stok. Tolak penerimaan dan
              minta barang pengganti.
            </p>
          ) : null}
          {canApprove &&
          menunggu &&
          onApproveReceipt &&
          !(batchTerpilih?.hoursLeft != null && batchTerpilih.hoursLeft < 0) ? (
            <div className="safety-approve">
              <p className="evidence-note">
                Menyetujui berarti barang ini masuk stok (dihitung server dari berat batch) dan
                angka pasokan di Overview ikut berubah. Menolak tidak menambah stok.
              </p>
              <div className="safety-approve-actions">
                <button
                  type="button"
                  className="button button-primary"
                  disabled={sibuk !== null}
                  onClick={() => void setujuiTerima(menunggu.id)}
                >
                  {sibuk === "setujui" ? "Menyetujui…" : "Setujui & masukkan stok"}
                </button>
                <button
                  type="button"
                  className="button"
                  disabled={sibuk !== null}
                  aria-expanded={tolakId === menunggu.id}
                  onClick={() => {
                    setTolakId(tolakId === menunggu.id ? null : menunggu.id);
                    setAlasanTolak("");
                  }}
                >
                  Tolak penerimaan
                </button>
              </div>
              {tolakId === menunggu.id ? (
                <div className="safety-other">
                  <label htmlFor={`alasan-${menunggu.id}`}>Alasan penolakan (wajib)</label>
                  <textarea
                    id={`alasan-${menunggu.id}`}
                    value={alasanTolak}
                    maxLength={500}
                    rows={2}
                    placeholder="Contoh: kemasan penyok dan suhu 12 °C — minta ganti barang."
                    onChange={(event) => setAlasanTolak(event.target.value)}
                  />
                  <span className="evidence-note">
                    Tersimpan bersama keputusan; petugas membacanya di riwayat.
                  </span>
                  <button
                    type="button"
                    className="button button-primary"
                    disabled={sibuk !== null}
                    onClick={() => void tolakTerima(menunggu.id)}
                  >
                    {sibuk === "tolak" ? "Mengirim…" : "Kirim penolakan"}
                  </button>
                </div>
              ) : null}
            </div>
          ) : null}
          {canApprove && !menunggu && sudahDisetujui ? (
            <p className="evidence-note">
              Penerimaan batch ini sudah disetujui
              {sudahDisetujui.reviewedByName ? ` oleh ${sudahDisetujui.reviewedByName}` : ""} — stok
              sudah tercatat dan tidak bertambah lagi bila disetujui ulang.
            </p>
          ) : null}
          {riwayat.length > 0 ? (
            <>
              <p className="board-subhead">Catatan penerimaan tersimpan (dari database)</p>
              <ul className="board-list safety-notes">
                {riwayat.map((r) => (
                  <li key={r.id}>
                    <span className="board-list-title">
                      {r.note ?? <em>tanpa catatan tambahan</em>}
                      <span className={`board-badge board-badge-${r.statusNada}`}>
                        {r.statusLabel}
                      </span>
                    </span>
                    <span className="board-list-meta">
                      {r.checkedCount === null ? "—" : `${r.checkedCount} titik`} · dicatat{" "}
                      {r.byName ?? "—"} · {r.waktuLabel}
                    </span>
                    {r.status !== "menunggu" ? (
                      <span className="board-list-meta">
                        {r.statusLabel}
                        {r.reviewedByName ? ` ${r.reviewedByName}` : ""}
                        {r.reviewedLabel ? ` · ${r.reviewedLabel}` : ""}
                        {r.stockKg !== null
                          ? ` · +${r.stockKg.toLocaleString("id-ID")} kg stok`
                          : ""}
                        {r.reviewNote ? ` · alasan: ${r.reviewNote}` : ""}
                      </span>
                    ) : null}
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </article>
      ) : null}

      {canApprove && onApproveReceipt && antrean.length > 0 ? (
        <article className="card jump-target" id="safety-persetujuan">
          <div className="board-card-head">
            <h2>Menunggu persetujuan</h2>
            <span className="board-badge board-badge-warn">{antrean.length} catatan</span>
          </div>
          <p className="evidence-note">
            Barang sudah diperiksa petugas, tetapi stok belum bertambah. Setujui untuk memasukkan
            beratnya ke stok; tolak dengan alasan bila barang tidak sesuai.
          </p>
          {aksi?.where === "terima" ? (
            <p className={aksi.nada === "danger" ? "board-alert" : "evidence-note"} aria-live="polite">
              {aksi.teks}
            </p>
          ) : null}
          <ul className={styles.approvalList}>
            {antrean.map((row) => (
              <li key={row.id} className={styles.approvalItem}>
                <div className={styles.approvalHead}>
                  <span className={styles.batchTitle}>
                    {row.commodity} · {formatKg(row.quantity_kg)} · {kodeWilayah(row.location)}
                  </span>
                  <span className="board-badge board-badge-warn">menunggu</span>
                </div>
                <span className={styles.batchMeta}>
                  {row.checked_count} titik · dicatat {row.recorded_by_name ?? "—"} ·{" "}
                  {waktuCatat(row.recorded_at)}
                </span>
                <div className="safety-row-actions">
                  <button
                    type="button"
                    className="button"
                    disabled={sibuk !== null}
                    onClick={() => void setujuiTerima(row.id)}
                  >
                    {sibuk === "setujui" ? "Menyetujui…" : "Setujui & masukkan stok"}
                  </button>
                  <button
                    type="button"
                    className="button button-secondary"
                    disabled={sibuk !== null}
                    onClick={() => {
                      setTolakId(row.id);
                      setAlasanTolak("");
                    }}
                  >
                    Tolak
                  </button>
                </div>
                {tolakId === row.id ? (
                  <div className="safety-other">
                    <label htmlFor={`alasan-antrean-${row.id}`}>Alasan penolakan (wajib)</label>
                    <textarea
                      id={`alasan-antrean-${row.id}`}
                      value={alasanTolak}
                      maxLength={500}
                      rows={2}
                      placeholder="Contoh: kemasan penyok dan suhu 12 °C — minta ganti barang."
                      onChange={(event) => setAlasanTolak(event.target.value)}
                    />
                    <div className="safety-row-actions">
                      <button
                        type="button"
                        className="button button-primary"
                        disabled={sibuk !== null}
                        onClick={() => void tolakTerima(row.id)}
                      >
                        {sibuk === "tolak" ? "Mengirim…" : "Kirim penolakan"}
                      </button>
                      <button
                        type="button"
                        className="button button-secondary"
                        onClick={() => {
                          setTolakId(null);
                          setAlasanTolak("");
                        }}
                      >
                        Batal
                      </button>
                    </div>
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        </article>
      ) : null}

      <article className="card jump-target" id="safety-batch">
        <div className="board-card-head">
          <h2>Status keamanan per batch</h2>
          {/* Ekspor baca-saja (dokumen `07-safety-evidence.md` §4.2 butir 6):
              isinya baris yang SEDANG tampil setelah saringan, memakai pola
              `lib/export.ts` + `downloadText` yang sudah dipakai dossier.
              Tidak ada tombol tulis di sini — safety adalah gerbang. */}
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
          <span className="safety-head-right">
            <button type="button" className="button button-secondary" onClick={() => eksporBatch("csv")}>
              Ekspor CSV
            </button>
            <button type="button" className="button button-secondary" onClick={() => eksporBatch("json")}>
              Ekspor JSON
            </button>
          </span>
        </div>
        <div className="safety-toolbar" id="safety-daftar">
          <div className="safety-filter" role="group" aria-label="Saring batch menurut keadaan">
            {(
              [
                ["tindakan", "Perlu tindakan"],
                ["gagal", "Gagal uji"],
                ["verifikasi", "Perlu verifikasi"],
                ["aman", "Aman"],
                ["semua", "Semua"],
              ] as const
            ).map(([kunci, label]) => (
              <button
                key={kunci}
                type="button"
                className={`commodity-pill${saring === kunci ? " commodity-pill-active" : ""}`}
                aria-pressed={saring === kunci}
                onClick={() => {
                  setSaring(kunci);
                  setHalaman(1);
                }}
              >
                {label}
                <span className="safety-filter-count">{jumlahPerSaringan[kunci]}</span>
              </button>
            ))}
          </div>
          <label className="safety-search">
            <span className="sr-only">Cari lokasi atau komoditas</span>
            <input
              type="search"
              value={cari}
              placeholder="Cari lokasi atau komoditas…"
              onChange={(e) => {
                setCari(e.target.value);
                setHalaman(1);
              }}
            />
          </label>
        </div>
        {/* Keterangan cakupan (butir 5): dua kontrol berdekatan menyaring DUA
            kumpulan data berbeda — saringan di bilah ini hanya menyentuh tabel
            batch, sedangkan daftar keputusan keamanan punya saringannya sendiri
            di bagian bawah. Satu baris, bukan legenda. */}
        <p className="evidence-note">
          Cakupan, saringan keadaan, dan pencarian hanya menyaring daftar batch di bawah; daftar
          keputusan keamanan punya saringan komoditas sendiri di bagian bawah halaman.
        </p>
        {tersaring.length === 0 ? (
          <p className="evidence-note">
            {loading ? (
              <LoadingState label="Memuat batch…" />
            ) : urut.length === 0 ? (
              "Belum ada batch pada cakupan Anda."
            ) : (
              "Tidak ada batch yang cocok dengan saringan ini."
            )}
          </p>
        ) : (
          <>
            <div className="board-table-wrap">
              <table className="location-table safety-table">
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
                  {halamanData.items.map((row: SafetyRow) => {
                    const state = expiryState(row.hoursLeft);
                    return (
                      <tr key={row.id ?? `${row.location}-${row.commodity}`}>
                        <td data-label={ownLocation && !jaringan ? "Asal" : "Lokasi"}>
                          {ownLocation && !jaringan ? asal(row) : kodeWilayah(row.location)}
                        </td>
                        <td data-label="Komoditas">
                          {/* Butir 1: komoditas yang punya keputusan keamanan
                              menjadi tautan ke gerbang di bawah. Komoditas tanpa
                              keputusan tetap teks biasa — tidak ada tautan yang
                              menjanjikan tujuan kosong. */}
                          {komoditasBerKeputusan.some(
                            (nama) => nama.toLowerCase() === row.commodity.trim().toLowerCase()
                          ) ? (
                            <button
                              type="button"
                              className="board-link"
                              aria-label={`Lihat keputusan keamanan ${row.commodity}`}
                              title={`Saring keputusan keamanan ke komoditas ${row.commodity}`}
                              onClick={() => saringKeputusanKomoditas(row.commodity)}
                            >
                              {row.commodity}
                            </button>
                          ) : (
                            row.commodity
                          )}
                        </td>
                        <td className="num" data-label="Jumlah">
                          {row.kg === null ? "—" : formatKg(row.kg)}
                        </td>
                        <td data-label="Status keamanan">
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
                          {/* MG/phase-04 poin 7: keadaan tertahan harus disertai
                              LANGKAH berikutnya. Batch bisa sekaligus menunggu
                              verifikasi DAN dikarantina, jadi keduanya ditulis
                              terpisah — bukan salah satu menutupi yang lain,
                              dan bukan kode mentah dari evaluator. */}
                          {(() => {
                            const langkah = rowNextSteps(row.safetyStatus, row.quarantine);
                            if (!langkah.safety && !langkah.karantina) return null;
                            return (
                              <span className="cell-meta safety-row-next">
                                {langkah.safety ? <>Langkah: {langkah.safety}.</> : null}
                                {langkah.karantina ? <> Karantina: {langkah.karantina}.</> : null}
                              </span>
                            );
                          })()}
                        </td>
                        <td className="num" data-label="Kesegaran">{row.freshness}</td>
                        <td data-label="Layak sampai">{row.usableUntil}</td>
                        <td data-label="Sisa masa">
                          {state.key === "expired" || state.key === "urgent" || state.key === "watch" ? (
                            <>
                              <span className={`safety-state safety-state-${state.key}`}>{state.label}</span>{" "}
                            </>
                          ) : null}
                          {state.detail}
                        </td>
                        {canMutate && (onRecheck || onTriggerDisruption || onKarantina) ? (
                          <td data-label="Tindakan">
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
            <Pager page={halamanData} onChange={setHalaman} label="status keamanan batch" />
            <ScrollHint />
          </>
        )}
        {aksi?.where === "batch" ? (
          <p className={aksi.nada === "danger" ? "board-alert" : "evidence-note"}>{aksi.teks}</p>
        ) : null}
      </article>

      {/* ── PASOKAN MASUK (dipindah ke bawah tabel, 27 Okt 2026) ──────────────
          Kartu kiriman (Arah A riset 16 Okt 2026) MENGGANTIKAN daftar ringkas
          "Pasokan masuk" yang lama: daftar itu menyajikan angka jalur yang sama
          (jarak, waktu tempuh, mutu, masa layak) tanpa TAHAP perjalanan, dan
          menyimpan dua penyaji angka identik adalah kesalahan yang sudah dibuang
          di Overview. Tombol "Periksa kiriman" menempel pada kirimannya.
          Posisi: setelah rujukan (tabel batch), sebelum jejak audit — kiriman
          adalah konteks, bukan tindakan. */}
      {(ownLocation || kirimanKe.length > 0) && (
        <>
          <ShipmentCard
            routes={routes}
            hanya={hanyaKeLokasi}
            anchor="safety-pasokan"
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
              placeholder="mis. log suhu menunjukkan suhu di luar rentang 12 menit, menunggu cek fisik"
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
        <article className="card jump-target" id="safety-keputusan">
          <div className="board-card-head">
            <h2>Keputusan keamanan lokasi ini</h2>
            {onOpenDecisions ? (
              <button type="button" className="button button-secondary" onClick={onOpenDecisions}>
                Buka Decision &amp; Evidence
              </button>
            ) : null}
          </div>
          {/* Saringan komoditas gerbang (butir 1). Pilihannya dibangun dari
              komoditas yang benar-benar ada di data keputusan, jadi tidak ada
              tombol yang menyaring ke himpunan yang tidak pernah ada. */}
          {keamanan.commodities.length > 0 ? (
            <div className="safety-filter" role="group" aria-label="Saring keputusan menurut komoditas">
              <button
                type="button"
                className={`commodity-pill${komoditasKeputusan === null ? " commodity-pill-active" : ""}`}
                aria-pressed={komoditasKeputusan === null}
                onClick={() => saringKeputusanKomoditas(null)}
              >
                Semua komoditas
              </button>
              {keamanan.commodities.map((nama) => {
                const aktif = (keamanan.filteredCommodity ?? "").toLowerCase() === nama.toLowerCase();
                return (
                  <button
                    key={nama}
                    type="button"
                    className={`commodity-pill${aktif ? " commodity-pill-active" : ""}`}
                    aria-pressed={aktif}
                    onClick={() => setKomoditasKeputusan(nama)}
                  >
                    {nama}
                  </button>
                );
              })}
            </div>
          ) : null}
          {keamanan.total === 0 ? (
            <p className="evidence-note">
              {keamanan.filteredCommodity
                ? `Tidak ada keputusan keamanan komoditas ${keamanan.filteredCommodity} untuk lokasi ini pada data yang termuat.`
                : "Belum ada keputusan keamanan untuk lokasi ini pada data yang termuat."}
            </p>
          ) : (
            <>
              <p className="evidence-note">{safetyDecisionSummaryLine(keamanan)}</p>
              {keamanan.active === 0 ? (
                <p className="board-alert">
                  Tidak ada keputusan keamanan yang menunggu tanda tangan Anda saat ini. Yang sudah lewat
                  jendela berlaku tidak bisa diajukan ulang — menurut aturan server hanya keputusan yang
                  DITOLAK yang bisa, dan usulan baru datang dari rantai agen.
                </p>
              ) : null}
              <ul className="board-list">
                {keamanan.rows.slice(0, MAKS_BATCH_TERLIHAT).map((row) => (
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
              {keamanan.rows.length > MAKS_BATCH_TERLIHAT ? (
                <p className="evidence-note">
                  Menampilkan {MAKS_BATCH_TERLIHAT} dari {keamanan.rows.length} — sisanya
                  di tab Decision &amp; Evidence.
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
