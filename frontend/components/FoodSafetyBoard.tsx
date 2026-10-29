"use client";

// Halaman "Keamanan Pangan" — halaman sidebar acuan /compliance, disesuaikan
// ke data repo ini (/batches). Papan CCP per-alat, bank sampel, dan jejak lot
// EPCIS dari acuan TIDAK dipakai karena tidak ada sumbernya di backend ini.
//
// Fase 11 (permintaan pemilik): halaman ini juga dipakai KEPALA SPPG — satu
// lokasi, satu dapur — bukan hanya pengawas nasional. Aturan yang dipegang:
//   - Cakupan: DEFAULT-nya SEMUA LOKASI (jaringan) sejak 29 Okt 2026 —
//     permintaan pemilik, karena tabel "Status keamanan per batch" sebelumnya
//     hanya berisi Jakarta sehingga pengawas tidak melihat Bandung/Surabaya.
//     Pemilih cakupan tetap ada untuk menyempitkan ke lokasi sendiri, dan
//     kartu yang MENULIS (Penerimaan barang) tetap dikunci ke lokasi sendiri
//     oleh `receivingCommodityGroups(rows, ownLocation)`.
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

import PageShell from "./PageShell";
import { PAGE_TITLES } from "../lib/navigation";
import SectionJump from "./SectionJump";
import { safetySections } from "../lib/section-jump";
import FactList from "./FactList";
import BatchPerhatianCard from "./BatchPerhatianCard";
import {
  balanceForLocation,
  checkedForReceipt,
  coverageSentence,
  evidenceRows,
  evidenceSummary,
  expiryState,
  incomingBatchId,
  incomingKgForCommodity,
  incomingShipments,
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
  safetyBadge,
  safetyState,
  safetyStatusGroups,
  safetySummaryOfRows,
  safetyLabel,
  quarantineTone,
  sortByDeadline,
  filterSafetyRows,
  safetyFilterCounts,
  type SafetyFilter,
  usableLabel,
  type ReceiptCardRow,
  type SafetyDecisionRow,
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
import type { PendingReceiptRow, ReceiptChecklist, ReceiptRow } from "../lib/api";
// Dok 05 §8.2–§8.3: tiga angka + asal harga satuan. Semua angka dari server;
// komponen ini hanya memilih mana yang ditampilkan dan menulis kalimatnya.
import { receiptFigures, valueOrigin } from "../lib/goods-receipt";
import { formatRupiah } from "../lib/decision-economics";
import { formatMomentWib } from "../lib/datetime";
import ReceiptSheet, { type ReceiptBatchInfo, type ReceiptHasil } from "./ReceiptDrawer";

/**
 * Nilai penerimaan satu baris antrean persetujuan (Dok 05 §8.2–§8.3).
 *
 * Kenapa di sini dan bukan di kartu lain: kepala SPPG memutuskan
 * setuju/tolak, dan yang ia pertimbangkan bukan hanya kg tetapi nilai rupiah
 * yang akan masuk stok. Angka ini PERKIRAAN (kg × harga satuan PO) — nilai
 * pembukuan baru lahir saat persetujuan, dan `accepted_value_idr` tetap satu-
 * satunya angka itu. Asal harganya ditulis supaya pembaca tidak membandingkan
 * dengan harga pasar.
 */
/** Maksimal dua nama lokasi di kalimat putusan; sisanya "+N lokasi". Lima nama
 *  berderet membuat satu kalimat memakan tiga baris dan mengubur pesannya
 *  (redesign 30 Okt 2026). */
/** Sisa masa berlaku keputusan dalam bahasa manusia. `null` = server tidak
 *  mengirim hitungannya; ditulis apa adanya, bukan ditebak nol. */
function masaBerlakuKeputusan(row: SafetyDecisionRow): string {
  if (!row.valid) return "lewat";
  const detik = row.secondsRemaining;
  if (detik === null || !Number.isFinite(detik)) return "—";
  if (detik <= 0) return "lewat";
  const jam = Math.floor(detik / 3600);
  if (jam >= 1) return `${jam} jam lagi`;
  const menit = Math.max(1, Math.round(detik / 60));
  return `${menit} menit lagi`;
}

function daftarLokasiGagal(lokasi: readonly string[]): string {
  const bersih = lokasi.filter((nama) => nama && nama.trim().length > 0);
  if (bersih.length <= 2) return bersih.join(", ");
  return `${bersih.slice(0, 2).join(", ")} +${bersih.length - 2} lokasi`;
}

function NilaiAntrean({ row }: { row: PendingReceiptRow }) {
  const angka = receiptFigures(row);
  const asal = valueOrigin(row);
  return (
    <p className={styles.approvalValue} data-testid="receipt-pending-value">
      <span className={styles.approvalValueLabel}>Nilai bila disetujui</span>
      <strong className={styles.approvalValueNumber} data-status={angka.statusNilai}>
        {formatRupiah(angka.nilaiIdr)}
      </strong>
      {/* Asal harga tetap ditampilkan bila ada. Kalimat "belum terikat PO, jadi
          nilainya belum bisa dihitung" dibuang 29 Okt 2026: label + "tidak
          tercatat" sudah menyatakan hal yang sama tanpa menjelaskan mekanisme. */}
      {asal ? <span className={styles.approvalValueOrigin}>{asal}</span> : null}
    </p>
  );
}

/** Sidik isi antrean: dipakai supaya muat ulang yang isinya sama tidak
 *  memicu render (dan dengan begitu tidak memicu muat ulang berikutnya). */
function kunciAntrean(rows: readonly PendingReceiptRow[]): string {
  return rows.map((row) => `${row.id}:${row.recorded_at}:${row.checked_count}`).join("|");
}

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
  loadChecklist,
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
    otherNote: string,
    /** Jalur baru (Dok 05 §3): jawaban tujuh butir + berat timbangan. */
    dinilai?: { answers: Record<string, string>; acceptedKg: number }
  ) => Promise<ReceiptRow | unknown>;
  /** Riwayat catatan penerimaan sebuah batch (dibaca dari server). */
  loadReceipts?: (batchId: string) => Promise<unknown>;
  /**
   * Daftar butir ceklis dari server (`GET /receipts/checklist`). Bobot dan
   * faktor TIDAK disalin ke layar: kalau bobot berubah di server, layar lama
   * tidak boleh menghitung dengan angka lama (Dok 05 §3).
   */
  loadChecklist?: (komoditas: string) => Promise<ReceiptChecklist>;
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
  const [scope, setScope] = useState<"own" | "all">("all");
  // Prop loader disimpan di REF, bukan dijadikan dependensi efek.
  //
  // Pemanggil mengirim fungsi inline (`() => fetchPendingReceipts(token)`),
  // jadi identitasnya baru setiap render. Selama efek bergantung pada prop itu,
  // setiap render memicu permintaan lagi — terukur 29 Okt 2026: 15 panggilan
  // `/receipts/menunggu` + 15 `/receipts/checklist` dalam 10 detik
  // (satu permintaan ±1,5/detik selama tab terbuka).
  const checklistRef = useRef(loadChecklist);
  checklistRef.current = loadChecklist;
  const antreanRef = useRef(loadPendingReceipts);
  antreanRef.current = loadPendingReceipts;
  const [aksi, setAksi] = useState<Aksi | null>(null);
  const [sibuk, setSibuk] = useState<string | null>(null);
  // Jawaban tujuh butir berbobot (Dok 05 §3): {"suhu": "sesuai", ...}.
  const [jawaban, setJawaban] = useState<Record<string, string>>({});
  // Berat timbangan sebagai TEKS: kosong harus bisa dibedakan dari 0.
  const [berat, setBerat] = useState("");
  const [beratGalat, setBeratGalat] = useState<string | null>(null);
  const [checklist, setChecklist] = useState<ReceiptChecklist | null>(null);
  const [checklistGalat, setChecklistGalat] = useState<string | null>(null);
  const [catatan, setCatatan] = useState("");
  const [riwayat, setRiwayat] = useState<ReceiptCardRow[]>([]);
  const [antrean, setAntrean] = useState<PendingReceiptRow[]>([]);
  const [terimaId, setTerimaId] = useState<string | null>(null);
  // ---- Popup penerimaan barang (Dok 05 §2) --------------------------------
  // `drawerTerbuka` hanya soal tampil; yang menentukan isi langkah 2-3 adalah
  // dua snapshot di bawah, karena setelah ceklis tersimpan batch itu KELUAR
  // dari `batchOpsi` (statusnya berubah) sehingga `batchTerpilih` jadi null.
  const [drawerTerbuka, setDrawerTerbuka] = useState(false);
  const [batchTersimpan, setBatchTersimpan] = useState<ReceiptBatchInfo | null>(null);
  const [hasilTerima, setHasilTerima] = useState<ReceiptHasil | null>(null);
  // Penolakan: satu catatan + satu alasan pada satu waktu (026).
  const [tolakId, setTolakId] = useState<string | null>(null);
  const [alasanTolak, setAlasanTolak] = useState("");
  // Saringan daftar batch: pengguna memilih prioritas, bukan menggulir semua.
  const [saring, setSaring] = useState<SafetyFilter>("semua");
  // Tahap 3 redesign (29 Okt 2026): dua hal yang dulu memakan tempat di kepala
  // kartu tanpa menjadi pertanyaan utama — ekspor (dua tombol) dan detail satu
  // batch (semua detail terbuka di sel). Keduanya dipindah ke popup.
  const [eksporTerbuka, setEksporTerbuka] = useState(false);
  const [detailBaris, setDetailBaris] = useState<SafetyRow | null>(null);
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

  // Cakupan TIDAK lagi direset ke lokasi sendiri saat identitas selesai dimuat
  // (29 Okt 2026): default-nya jaringan, dan perubahan `ownLocation` (mis. sesi
  // berganti peran) tidak boleh diam-diam menyempitkan tabel.

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

  // Daftar butir ceklis dimuat dari server per komoditas (Dok 05 §3): bobot,
  // faktor, dan petunjuk suhu berbeda antar-komoditas (telur rantai dingin,
  // beras suhu ruang). Kegagalan memuat TIDAK dikarang jadi daftar lokal —
  // layar menyebut sebabnya, karena menilai dengan bobot karangan lebih buruk
  // daripada tidak menilai.
  useEffect(() => {
    const baca = checklistRef.current;
    if (!baca || !komoditasTerpilih) return;
    let batal = false;
    setChecklistGalat(null);
    baca(komoditasTerpilih)
      .then((data) => {
        if (!batal) setChecklist(data);
      })
      .catch((err) => {
        if (!batal) {
          setChecklist(null);
          setChecklistGalat(`Daftar butir ceklis tidak bisa dimuat: ${pesan(err)}`);
        }
      });
    return () => {
      batal = true;
    };
    // Deps sengaja TANPA loader: lihat komentar `checklistRef` di atas.
  }, [komoditasTerpilih]);

  // Gerbang tombol simpan: SEMUA butir wajib dijawab (Dok 05 §2) + berat diisi.
  const butirCeklis = checklist?.butir ?? [];
  // Butir "kesesuaian jumlah" tidak dipilih petugas: ia baru TERJAWAB setelah
  // berat timbangan sah. Kalau dihitung terjawab sejak awal, gerbang akan
  // berbunyi "1 dari 7" sebelum apa pun dikerjakan — dan petugas kehilangan
  // petunjuk bahwa berat masih kosong.
  const beratSah = berat.trim() !== "" && !beratGalat;
  const terjawab = butirCeklis.filter((butir) =>
    butir.dari_timbangan ? beratSah : Boolean(jawaban[butir.kunci])
  ).length;
  const totalButir = butirCeklis.length;

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
        teks: `Hasil periksa: ${bagian.join(" · ")}.`,
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
              teks: `${hasil.message ?? "Tidak ada gangguan pada batch ini."} — tidak ada keputusan baru yang dibuat.`,
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
  /**
   * Validasi berat timbangan di layar (Dok 05 §5.1–§5.2).
   *
   * Server tetap memeriksa ulang dan menolak dengan kode `berat_nol` /
   * `berat_lebih`; yang di sini hanya supaya petugas melihat sebabnya sebelum
   * menekan tombol, bukan sesudah menunggu server. Ambang 110% sama dengan
   * `receipt_scoring.validasi_berat` — kalau berubah di server, ubah di sini
   * juga; pesan layar tidak boleh lebih longgar daripada aturan penyimpanan.
   */
  function ubahBerat(nilai: string) {
    setBerat(nilai);
    const teks = nilai.trim().replace(",", ".");
    if (teks === "") {
      setBeratGalat(null);
      return;
    }
    const angka = Number(teks);
    if (!Number.isFinite(angka)) {
      setBeratGalat("Isi angka dalam kg, contoh 149,5.");
      return;
    }
    if (angka <= 0) {
      setBeratGalat("Berat diterima harus lebih dari 0 kg — timbang ulang sebelum mencatat.");
      return;
    }
    const pesanan = batchTerpilih?.kg ?? null;
    if (pesanan !== null && pesanan > 0 && angka > pesanan * 1.1) {
      setBeratGalat(
        `Berat diterima ${formatKg(angka)} kg melebihi 110% pesanan (${formatKg(
          pesanan
        )} kg). Periksa timbangan atau tolak kiriman.`
      );
      return;
    }
    setBeratGalat(null);
  }

  async function catatTerima() {
    if (!onRecheck || !idTerima) return;
    setSibuk("terima");
    try {
      // Dua tulisan nyata, urut jelas: (1) catatan penerimaan (checklist +
      // isian "Lainnya") → `batch_receipts`; (2) hitung ulang keamanan &
      // kesegaran → kolom batch. Kalau (1) gagal, pesannya jujur menyebut
      // bagian mana yang gagal — tidak ada yang diam-diam hilang.
      let tersimpan: string;
      let dinilai: ReceiptRow | null = null;
      if (onRecordReceipt) {
        try {
          // Dok 05 §3–§5: server butuh jawaban tujuh butir DAN berat timbangan.
          // Berat dikirim sebagai angka; kosong/koma sudah dijaga `beratGalat`
          // sebelum tombol ini bisa ditekan.
          const respon = await onRecordReceipt(idTerima, {}, catatan, {
            answers: { ...jawaban },
            acceptedKg: Number(berat.replace(",", ".")),
          });
          dinilai = (respon ?? null) as ReceiptRow | null;
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
      const nilaiPutusan = dinilai?.verdict ?? null;
      setAksi({
        where: "terima",
        nada:
          String(hasil.safety.safety_status).toUpperCase() === "FAIL" ||
          nilaiPutusan === "fail" ||
          tersimpan.includes("TIDAK")
            ? "danger"
            : "ok",
        teks: `${
          tersimpan.includes("TIDAK")
            ? `${tersimpan}. ${totalButir} butir wajib dijawab sebelum dinilai.`
            : `Catatan penerimaan tersimpan: ${terjawab} dari ${totalButir} butir terjawab, ${formatKg(
                Number(berat.replace(",", ".")) || 0
              )} kg diterima.`
        }${
          dinilai?.score !== null && dinilai?.score !== undefined
            ? ` Nilai ceklis ${dinilai.score} dari 100 — ${dinilai.verdict_label ?? ""}.`
            : ""
        } Hasil dari server: ${bagian.join(" · ")}.`,
      });

      if (tersimpan.includes("TIDAK")) {
        // Gagal menyimpan catatan: tetap di langkah 1 supaya petugas bisa
        // memperbaiki. Yang hilang bukan ceklisnya, hanya tulisannya.
        await muatAntrean();
        return;
      }

      // ---- langkah 2 & 3 popup (Dok 05 §2) ---------------------------------
      // Skor, putusan, dan rincian poin datang LANGSUNG dari balasan `POST
      // /receipts` (server yang menghitung). Nilai rupiah dibaca ulang dari
      // `GET /receipts?batch_id=` supaya yang tampil adalah angka tersimpan.
      // Snapshot batch diambil sekarang karena batch ini keluar dari `batchOpsi`
      // begitu statusnya berubah.
      const kgDiterima = Number(berat.replace(",", "."));
      const batchSnapshot: ReceiptBatchInfo = {
        commodity: batchTerpilih?.commodity ?? komoditasTerpilih,
        kgLabel: formatKg(kgDiterima),
        orderedKg: batchTerpilih?.kg ?? null,
        statusLabel: safetyLabel(hasil.safety.safety_status),
        usableUntil: usableLabel(hasil.freshness.usable_until),
        expired: false,
      };
      let barisMentah: Record<string, any> | null = null;
      let riwayatBaru: ReceiptCardRow[] = [];
      if (muatRef.current) {
        try {
          const muatan = await muatRef.current(idTerima);
          riwayatBaru = receiptRows(muatan);
          const items = (muatan as { items?: unknown[] } | null)?.items;
          barisMentah = Array.isArray(items) && items.length > 0
            ? (items[0] as Record<string, any>)
            : null;
        } catch {
          // Riwayat gagal dibaca tidak boleh menjatuhkan langkah 2: angka nilai
          // akan tampil "tidak tercatat" dan sebabnya disebut di layar.
          riwayatBaru = [];
          barisMentah = null;
        }
      }
      const angka = receiptFigures(barisMentah);
      // Nilai rupiah memakai kg DITERIMA (Dok 05 §5.1) — server sudah mengirim
      // `nilai_diterima_idr`; kalau tidak ada (baris lama/tanpa PO) dipakai
      // perhitungan receiptFigures atas kg tersimpan sebagai perkiraan.
      const nilaiDiterima =
        typeof barisMentah?.nilai_diterima_idr === "number"
          ? barisMentah.nilai_diterima_idr
          : angka.nilaiIdr;
      setBatchTersimpan(batchSnapshot);
      setHasilTerima({
        score: dinilai?.score ?? null,
        verdict: dinilai?.verdict ?? "",
        verdictLabel: dinilai?.verdict_label ?? "",
        advice: dinilai?.advice ?? null,
        points: dinilai?.points ?? null,
        orderedKg: dinilai?.ordered_kg ?? batchTerpilih?.kg ?? null,
        acceptedKg: dinilai?.accepted_kg ?? kgDiterima,
        nilaiLabel: formatRupiah(nilaiDiterima),
        nilaiStatus: angka.statusNilai,
        asalHarga: valueOrigin(barisMentah),
        riwayat: riwayatBaru,
      });
      setRiwayat(riwayatBaru);
      setJawaban({});
      setCatatan("");
      setDrawerTerbuka(true);
      // `terimaId` SENGAJA tidak direset: popup masih menunjuk batch ini untuk
      // langkah 2 (nilai) dan langkah 3 (tandai barang). Reset terjadi saat
      // popup ditutup.
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
    const baca = antreanRef.current;
    if (!baca) return;
    try {
      const hasil = await baca();
      const berikut = Array.isArray(hasil?.items) ? hasil.items : [];
      // Bandingkan dulu: setState dengan array baru selalu memicu render, dan
      // render yang memicu muat ulang adalah persis lingkaran yang dihindari.
      setAntrean((kini) => (kunciAntrean(kini) === kunciAntrean(berikut) ? kini : berikut));
    } catch {
      // Antrean gagal dimuat tidak boleh menjatuhkan kartu penerimaan;
      // form tetap bisa dipakai dan galatnya tampil lewat tombol setujui.
      setAntrean([]);
    }
  }, []);

  // Hanya sekali saat kartu dipasang. Muat ulang setelah keputusan dijalankan
  // lewat `muatAntrean()` eksplisit di handler setujui/tolak.
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
      // Popup menutup diri: batch ini sudah tidak punya keputusan tertunda,
      // langkah 3 di dalamnya akan berbunyi "tidak ada yang bisa ditandai".
      setDrawerTerbuka(false);
      setHasilTerima(null);
      setBatchTersimpan(null);
      // Batch yang disetujui keluar dari daftar "perlu diperiksa/dicatat".
      // Pindah ke batch berikutnya supaya <select> tidak menunjuk nilai yang
      // sudah tidak ada; kalimat sukses tetap tampil.
      setJawaban({});
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
      setDrawerTerbuka(false);
      setHasilTerima(null);
      setBatchTersimpan(null);
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

  /**
   * Tutup popup penerimaan barang (Dok 05 §2). Semua jejak langkah 2–3 dibuang:
   * popup yang dibuka lagi untuk batch berikutnya harus mulai dari langkah 1,
   * bukan menampilkan nilai batch sebelumnya.
   */
  function tutupDrawer() {
    setDrawerTerbuka(false);
    setHasilTerima(null);
    setBatchTersimpan(null);
    setJawaban({});
    // Berat ikut dikosongkan: popup berikutnya menunjuk batch lain, dan berat
    // timbangan batch sebelumnya tidak boleh terbawa (Dok 05 §5.1).
    setBerat("");
    setBeratGalat(null);
    setCatatan("");
    setTolakId(null);
    setAlasanTolak("");
    setTerimaId(null);
    setRiwayat([]);
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
  /**
   * Tile ringkasan = tombol saring (redesign 29 Okt 2026, tahap 2).
   *
   * Sebelumnya angka ini pajangan: pembaca melihat "2 gagal uji", lalu harus
   * mencari chip saringan sendiri di bagian bawah halaman. Sekarang tile
   * memindahkan pandangan ke daftar yang sudah tersaring — satu klik, satu
   * tujuan, sama seperti tombol "Tinjau N batch" di kepala kartu.
   *
   * Gulirannya mengikuti `prefers-reduced-motion`: pengguna yang meminta
   * gerakan minimal tidak dipaksa menonton animasi gulir 1.900 px.
   */
  function terapkanSaring(kunci: SafetyFilter) {
    setSaring(kunci);
    setHalaman(1);
    const halus =
      typeof window !== "undefined" &&
      typeof window.matchMedia === "function" &&
      !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    document.getElementById("safety-daftar")?.scrollIntoView({
      behavior: halus ? "smooth" : "auto",
      block: "start",
    });
  }

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
  // Tile "Kedaluwarsa" hanya dirender bila ada isinya: strip tetap terbaca
  // sebagai lima angka pada hari biasa, dan menjadi enam saat memang ada
  // barang yang lewat masa layak.
  const grupStatus = safetyStatusGroups(tampil).filter(
    (grup) => grup.key !== "kedaluwarsa" || grup.value > 0
  );
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
          : grup.key === "kedaluwarsa"
            ? summary.expiredKg
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
    <PageShell
      className="board-page safety-page"
      busy={loading}
      sections={bagianNav}
      jumpAriaLabel="Bagian halaman Keamanan Pangan"
      title={PAGE_TITLES.safety}
        description="Status keamanan tiap batch, kesegaran, dan sisa masa layak pakai. Batch gagal uji diblokir dari alokasi."
        meta={
          <span className="page-header-pills">
            <span className="commodity-pill">{summary.total} batch</span>
            <span className="commodity-pill">
              {jaringan ? "Jaringan" : ownLocation ? ownLocation : "Semua lokasi"}
            </span>
          </span>
        }
      >

      {/* Navigasi bagian kini datang dari PageShell (komponen bersama lima tab).
          Halaman ini lima bagian yang tidak saling menggantikan (ringkasan, batch
          mendesak, penerimaan, tabel status, keputusan), dan aksi tulis tersebar
          di beberapa bagian — setelah satu aksi, pembaca harus bisa kembali ke
          bagian yang tepat tanpa menggulir buta. */}

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

      {/* Tiga zona (redesign 29 Okt 2026). Halaman ini menjawab satu pertanyaan
          lebih dulu ("ada yang harus saya tindak?"), baru menyodorkan tindakan,
          lalu daftar dan bukti. Zona memakai aria-labelledby ke label yang
          terlihat, bukan heading baru: heading di dalamnya sudah h2 dan
          menaikkan zona jadi h2 akan memaksa seluruh isi turun satu tingkat. */}
      <section className={styles.zona} aria-labelledby="zona-a-label">
        <p className={styles.zonaLabel} id="zona-a-label">Putusan hari ini</p>

      <article className="card jump-target safety-band" id="safety-ringkasan" data-tone={nadaBand}>
        <div className="board-card-head">
          <h2>Ringkasan pengawasan</h2>
          {/* Cakupan dinyatakan di kepala kartu (audit 29 Okt 2026): angka
              "112 aman" adalah seluruh jaringan, bukan satu lokasi — tanpa
              label ini Kepala Bandung membaca angka jaringan sebagai miliknya. */}
          <span className="safety-scope" title="Cakupan angka ringkasan">
            {jaringan ? "Seluruh jaringan" : ownLocation ? ownLocation : "Semua lokasi"}
          </span>
          {/* Tombol "Tinjau N batch" DILEPAS 30 Okt 2026: ia melakukan persis
              apa yang dilakukan tile angka di bawah (menyaring daftar lalu
              menggulir ke sana), sehingga kepalanya memuat dua kontrol untuk
              satu tindakan. Tile "Gagal uji"/"Perlu verifikasi" sekarang menjadi
              satu-satunya pintu masuk, dan angkanya ada di tile itu sendiri. */}
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
                  Batch gagal uji di lokasi ini: {daftarLokasiGagal(summary.failedLocations)} — alokasi
                  hanya boleh memakai batch berstatus aman.
                </>
              ) : (
                <>
                  Batch gagal uji: {daftarLokasiGagal(summary.failedLocations)} — alokasi hanya boleh
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

        {/* Angka diumumkan sebagai SATU kalimat utuh saat berubah, bukan enam
            angka telanjang yang saling menimpa (aturan skill: contextual live
            badge — `role="status"` + `aria-atomic`). */}
        <p className="sr-only" role="status" aria-atomic="true">
          {ringkasUji}
        </p>
        <div className="safety-counts" role="list" aria-label={ringkasUji}>
          {tileUji.map((tile) => (
            <div key={tile.key} className={`safety-count is-${tile.tone}`} role="listitem">
              <button
                type="button"
                className={styles.tile}
                aria-pressed={saring === tile.key}
                aria-label={`Saring daftar ke ${tile.label}: ${tile.value} batch`}
                disabled={tile.value === "0" || tile.value === "…"}
                onClick={() => terapkanSaring(tile.key)}
              >
              <span className={styles.tileIcon} aria-hidden="true">
                <IkonStatus keadaan={tile.key} />
              </span>
              <span className="safety-count-value">{tile.value}</span>
              {/* Satu baris: nama kelompok + berat yang tidak boleh dipakai
                  (30 Okt 2026). Dulu berat turun ke baris ketiga sendiri. */}
              <span className={styles.tileLine}>
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
              </span>
              </button>
            </div>
          ))}
        </div>

        {/* Fakta sekunder ditaruh pada SATU baris ringkas di bawah angka
            (redesign 30 Okt 2026). Sebelumnya tenggat, bukti suhu, dan jumlah
            batch menempati tiga baris sendiri-sendiri, sehingga kartu ringkasan
            yang seharusnya menjawab "ada yang perlu saya tindak?" justru lebih
            tinggi daripada tabelnya. Isinya tidak dihapus, hanya dirapatkan. */}
        <div className={styles.glance}>
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

        {/* Kecukupan bukti suhu (29 Okt 2026): "pengawasan" bukan hanya status
            uji keamanan. Kartu Bukti suhu di bawah menjelaskan rinciannya; di
            sini hanya angkanya, satu baris, supaya pembaca tidak perlu
            menggulir untuk tahu apakah rantai dinginnya terbukti. Tidak
            dicetak bila memang tidak ada batch pada cakupan ini. */}
        <div className="safety-counts-foot">
          <span>
            {summary.total > 0 ? `dari ${summary.total} batch` : "belum ada batch"}
          </span>
          <details className="safety-more">
            <summary>Rincian angka</summary>
        {buktiRingkas.total > 0 ? (
              <p
                className="safety-temp"
                data-keadaan={buktiRingkas.perluVerifikasi > 0 ? "kurang" : "cukup"}
              >
                <span className="safety-temp-label">Bukti suhu</span>
                <span className="safety-temp-body">
                  <strong>
                    {buktiRingkas.sufficient} dari {buktiRingkas.total}
                  </strong>{" "}
                  batch cukup bukti
                  {buktiRingkas.perluVerifikasi > 0
                    ? ` · ${buktiRingkas.perluVerifikasi} belum cukup`
                    : ""}
                </span>
                <a className="board-link safety-temp-link" href="#safety-bukti-suhu">
                  Lihat batch
                </a>
              </p>
            ) : null}
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
        </div>
      </article>

      {/* Satu kartu untuk tiga pertanyaan yang dulu tersebar di tiga kartu
          (29 Okt 2026): bukti suhu, segera dipakai, kesegaran terendah. Semua
          membaca array batch yang sama, jadi bentuknya satu tabel: satu baris
          per batch, tiga putusan berdampingan — bukan satu batch muncul tiga
          kali dengan tiga bahasa. Register lengkapnya tetap tabel di bawah. */}
      <BatchPerhatianCard safetyRows={tampil} evidence={bukti} summary={buktiRingkas} />
      </section>

      <section className={styles.zona} aria-labelledby="zona-b-label">
        <p className={styles.zonaLabel} id="zona-b-label">Tindakan</p>

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
                      setJawaban({});
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
                        setJawaban({});
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
          </fieldset>          {/* Dok 05 §2: ceklis hidup di POPUP — kartu ini hanya memilih
              kiriman. Sebelumnya seluruh form (±700 px) terbuka di sini, sehingga
              dua kartu bertindak (Penerimaan & Menunggu persetujuan) berjauhan
              dan halaman terbaca seperti formulir, bukan papan pengawasan. */}
          <div className={styles.receiptOpen}>
            <button
              type="button"
              className="button button-primary"
              disabled={!batchTerpilih}
              onClick={() => {
                setHasilTerima(null);
                setBatchTersimpan(null);
                setDrawerTerbuka(true);
              }}
            >
              {batchTerpilih ? "Periksa & catat kiriman" : "Pilih batch dulu"}
            </button>
          </div>
          {!canMutate ? (
            <p className="evidence-note">
              Hanya kepala SPPG dan ahli gizi yang bisa mencatat hasil terima.
            </p>
          ) : null}
          {aksi?.where === "terima" && !drawerTerbuka ? (
            <p className={aksi.nada === "danger" ? "board-alert" : "evidence-note"}>{aksi.teks}</p>
          ) : null}

        </article>
      ) : null}

      {/* Popup SENGAJA di luar kartu: begitu batch terakhir dicatat, kartu
          Penerimaan berganti ke keadaan kosong dan SELURUH isi kartu — termasuk
          popup di dalamnya — ikut dilepas dari pohon React. Langkah 2 (nilai) dan
          langkah 3 (tandai barang) akan hilang tepat setelah ceklis tersimpan.
          Ditemukan saat verifikasi 29 Okt 2026: dengan satu batch pending, popup
          menutup sendiri sesudah "Catat hasil terima". */}
          <Popup
            open={drawerTerbuka}
            onClose={tutupDrawer}
            title="Penerimaan barang"
            description="Tiga langkah yang tidak boleh dilompati: periksa kondisi, nilai & putusan, tandai barang."
            labelledBy="popup-terima-title"
            className="popup-receipt"
          >
            <ReceiptSheet
              batch={
                batchTersimpan ??
                (batchTerpilih
                  ? {
                      commodity: batchTerpilih.commodity,
                      kgLabel: batchTerpilih.kg === null ? "—" : formatKg(batchTerpilih.kg),
                      orderedKg: batchTerpilih.kg,
                      statusLabel: batchTerpilih.statusLabel,
                      usableUntil: batchTerpilih.usableUntil,
                      expired:
                        batchTerpilih.hoursLeft !== null && batchTerpilih.hoursLeft < 0,
                    }
                  : null)
              }
              bukti={
                buktiTerpilih
                  ? {
                      stateLabel: buktiTerpilih.stateLabel,
                      observationLabel: buktiTerpilih.observationLabel,
                      sourceLabel: buktiTerpilih.sourceLabel,
                      observedAt: buktiTerpilih.observedAt
                        ? formatMomentWib(buktiTerpilih.observedAt)
                        : null,
                      sufficient: buktiTerpilih.sufficient,
                    }
                  : null
              }
              komoditas={komoditasTerpilih}
              checklist={checklist}
              checklistGalat={checklistGalat}
              jawaban={jawaban}
              onJawab={(kunci, opsi) => setJawaban((lama) => ({ ...lama, [kunci]: opsi }))}
              berat={berat}
              onBerat={ubahBerat}
              beratGalat={beratGalat}
              catatan={catatan}
              onCatatan={setCatatan}
              canMutate={canMutate}
              adaJalurSimpan={Boolean(onRecordReceipt && onRecheck && idTerima)}
              menyimpan={sibuk === "terima" || sibuk === "setujui" || sibuk === "tolak"}
              onSimpan={() => void catatTerima()}
              hasil={hasilTerima}
              putusan={{
                pendingId: menunggu?.id ?? null,
                boleh: canApprove && Boolean(onApproveReceipt),
                expired: Boolean(
                  batchTersimpan?.expired ||
                    (batchTerpilih?.hoursLeft != null && batchTerpilih.hoursLeft < 0)
                ),
                alasanTolak,
                onAlasanTolak: setAlasanTolak,
                tolakTerbuka: Boolean(menunggu && tolakId === menunggu.id),
                onBukaTolak: () => {
                  setTolakId(menunggu?.id ?? null);
                  setAlasanTolak("");
                },
                onBatalTolak: () => {
                  setTolakId(null);
                  setAlasanTolak("");
                },
                onSetujui: (id) => void setujuiTerima(id),
                onTolak: (id) => void tolakTerima(id),
              }}
              aksi={aksi?.where === "terima" ? { nada: aksi.nada, teks: aksi.teks } : null}
              terjawab={terjawab}
              totalButir={totalButir}
            />
          </Popup>

      {canApprove && onApproveReceipt && antrean.length > 0 ? (
        <article className="card jump-target" id="safety-persetujuan">
          <div className="board-card-head">
            <h2>Menunggu persetujuan</h2>
            <span className="board-badge board-badge-warn">{antrean.length} catatan</span>
          </div>
          {/* Hanya batch `usable` yang sampai ke daftar ini (server, 29 Okt
              2026): barang yang buktinya belum lengkap atau sudah lewat masa
              layak tidak ditawarkan untuk disetujui. */}
          {aksi?.where === "terima" ? (
            <p className={aksi.nada === "danger" ? "board-alert" : "evidence-note"} aria-live="polite">
              {aksi.teks}
            </p>
          ) : null}
          <ul className={styles.approvalList}>
            {antrean.map((row) => (
              <li key={row.id} className={styles.approvalItem}>
                {/* Tahap 5 (29 Okt 2026): fakta batch dan nilainya duduk sebaris —
                    kiri keterangan, kanan angka rupiah — supaya satu butir antrean
                    cukup 3 baris (judul · meta · aksi), bukan 5 bertumpuk. */}
                <div className={styles.approvalTop}>
                  <div className={styles.approvalFacts}>
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
                  </div>
                  <NilaiAntrean row={row} />
                </div>
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

      </section>

      <section className={styles.zona} aria-labelledby="zona-c-label">
        <p className={styles.zonaLabel} id="zona-c-label">Daftar &amp; bukti</p>

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
            {/* Dua tombol ekspor di kepala kartu bersaing dengan pertanyaan utama
                ("batch mana yang perlu saya tindak"). Sekarang satu pemicu;
                pilihan format ada di dalam popup. */}
            <button
              type="button"
              className="button button-secondary"
              aria-haspopup="dialog"
              onClick={() => setEksporTerbuka(true)}
            >
              Ekspor…
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
                // Tiga chip ini lahir bersama tile yang bisa diklik: tanpa chip,
                // saringan dari tile "Ditahan" tidak punya penanda aktif di bilah
                // alat, jadi pengguna melihat daftar tersaring tanpa tahu sebabnya.
                ["kedaluwarsa", "Kedaluwarsa"],
                ["belum", "Belum diuji"],
                ["ditahan", "Ditahan"],
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
                    <th scope="col">Detail</th>
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
                          {(() => {
                            const badge = safetyBadge(row);
                            return (
                              <span className={`board-badge board-badge-${badge.tone}`}>
                                {badge.label}
                              </span>
                            );
                          })()}
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
                            // Batch yang masa layaknya lewat tidak bisa "diverifikasi
                            // jadi boleh dipakai": dulu barisnya berlabel Kedaluwarsa
                            // tetapi langkahnya masih "Selesaikan verifikasi verifier"
                            // (terlihat 29 Okt 2026). Langkahnya diganti kalimat yang
                            // sesuai keadaan.
                            // Baris kedaluwarsa tidak lagi menambahkan kalimat
                            // ("Masa layak lewat: … ajukan pengganti") — keadaan itu
                            // sudah terbaca dari kolom status; 29 Okt 2026.
                            if (safetyState(row) === "kedaluwarsa") {
                              return null;
                            }
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
                        {/* Progressive disclosure: tabel tetap ringkas untuk
                            dipindai, satu batch dibaca lengkap di popup. */}
                        <td data-label="Detail">
                          <button
                            type="button"
                            className="button button-secondary"
                            aria-label={`Detail batch ${row.commodity} di ${row.location}`}
                            onClick={() => setDetailBaris(row)}
                          >
                            Detail
                          </button>
                        </td>
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
          {/* Saringan komoditas: SELECT, bukan deretan pill (tahap 6, 30 Okt
              2026). Pilihannya bisa lebih dari lima, dan pada deretan pill itu
              pemindaian mata berhenti bekerja — orang harus membaca satu per
              satu. Pilihannya tetap dibangun dari data yang benar-benar ada. */}
          {keamanan.commodities.length > 0 ? (
            <div className={styles.decisionFilter}>
              <label htmlFor="saring-komoditas-keputusan">Komoditas</label>
              <select
                id="saring-komoditas-keputusan"
                value={keamanan.filteredCommodity ?? ""}
                onChange={(event) =>
                  saringKeputusanKomoditas(event.target.value === "" ? null : event.target.value)
                }
              >
                <option value="">Semua komoditas</option>
                {keamanan.commodities.map((nama) => (
                  <option key={nama} value={nama}>
                    {nama}
                  </option>
                ))}
              </select>
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
              {/* Tabel, bukan daftar (tahap 6, 30 Okt 2026): pola kepala dan
                  kolomnya sama dengan tabel status batch di atasnya, supaya zona
                  ini terbaca sebagai satu register, bukan dua bahasa berbeda. */}
              <div className="board-table-wrap">
                <table className="location-table safety-table">
                  <thead>
                    <tr>
                      <th scope="col">Dibuat</th>
                      <th scope="col">Komoditas</th>
                      <th scope="col" className="num">
                        Jumlah
                      </th>
                      <th scope="col">Status</th>
                      <th scope="col">Masa berlaku</th>
                      <th scope="col">Aksi</th>
                    </tr>
                  </thead>
                  <tbody>
                    {keamanan.rows.slice(0, MAKS_BATCH_TERLIHAT).map((row) => (
                      <tr key={row.id}>
                        <td data-label="Dibuat">{row.createdLabel}</td>
                        <td data-label="Komoditas">{row.commodity ?? "—"}</td>
                        <td data-label="Jumlah" className="num">
                          {row.kg === null ? "—" : formatKg(row.kg)}
                        </td>
                        <td data-label="Status">
                          <span className={`board-badge board-badge-${row.valid ? "ok" : "muted"}`}>
                            {row.statusLabel}
                          </span>{" "}
                          <span className="cell-meta">
                            {row.valid ? "masih berlaku" : "kedaluwarsa"}
                          </span>
                        </td>
                        <td data-label="Masa berlaku">{masaBerlakuKeputusan(row)}</td>
                        <td data-label="Aksi">
                          {canMutate && onRepropose && row.canRepropose ? (
                            <button
                              type="button"
                              className="button button-secondary"
                              disabled={sibuk === row.id}
                              onClick={() => void ajukanUlang(row.id)}
                            >
                              {sibuk === row.id ? "Mengajukan…" : "Ajukan ulang"}
                            </button>
                          ) : (
                            <span className="cell-meta">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
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

      <Popup
        open={eksporTerbuka}
        onClose={() => setEksporTerbuka(false)}
        title="Ekspor tabel batch"
        description="Isinya baris yang sedang tampil setelah saringan dan pencarian — bukan seluruh database."
        labelledBy="ekspor-batch-judul"
      >
        <div className="receipt-actions">
          <button
            type="button"
            className="button button-primary"
            onClick={() => {
              setEksporTerbuka(false);
              eksporBatch("csv");
            }}
          >
            Unduh CSV
          </button>
          <button
            type="button"
            className="button button-secondary"
            onClick={() => {
              setEksporTerbuka(false);
              eksporBatch("json");
            }}
          >
            Unduh JSON
          </button>
        </div>
      </Popup>

      <Popup
        open={detailBaris !== null}
        onClose={() => setDetailBaris(null)}
        title={detailBaris ? `${detailBaris.commodity} · ${detailBaris.location}` : "Detail batch"}
        description="Satu batch, dibaca lengkap — termasuk yang tidak muat di kolom tabel."
        labelledBy="detail-batch-judul"
      >
        {detailBaris ? (
          <FactList
            rows={[
              { label: "Status keamanan", value: safetyBadge(detailBaris).label, tone: detailBaris.tone === "danger" ? "danger" : "plain" },
              { label: "Karantina", value: detailBaris.quarantineLabel },
              { label: "Jumlah", value: detailBaris.kg === null ? "tidak tercatat" : formatKg(detailBaris.kg) },
              { label: "Kesegaran", value: detailBaris.freshness },
              { label: "Layak sampai", value: detailBaris.usableUntil },
              { label: "Sisa masa", value: detailBaris.hoursLabel },
              { label: "Penerimaan", value: detailBaris.receiptStatus ?? "belum dicatat" },
            ]}
          />
        ) : null}
      </Popup>
      </section>
    </PageShell>
  );
}

/**
 * Ikon status untuk tile ringkasan — SVG inline 16x16, `aria-hidden`.
 *
 * Aturan skill: jangan pernah menyampaikan status lewat warna saja, dan jangan
 * memakai emoji sebagai ikon. Nama statusnya tetap terbaca dari label tile;
 * ikon hanya mempercepat pemindaian. `stroke="currentColor"` supaya warnanya
 * mengikuti nada tile tanpa hex baru di komponen.
 */
function IkonStatus({ keadaan }: { keadaan: string }) {
  const umum = {
    width: 16,
    height: 16,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 2,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
    focusable: false,
  };
  if (keadaan === "aman") {
    return (
      <svg {...umum}>
        <circle cx="12" cy="12" r="9" />
        <path d="M8.5 12.5l2.5 2.5 4.5-5" />
      </svg>
    );
  }
  if (keadaan === "gagal") {
    return (
      <svg {...umum}>
        <circle cx="12" cy="12" r="9" />
        <path d="M9 9l6 6M15 9l-6 6" />
      </svg>
    );
  }
  if (keadaan === "kedaluwarsa") {
    return (
      <svg {...umum}>
        <rect x="3.5" y="5" width="17" height="15" rx="2" />
        <path d="M8 3v4M16 3v4M3.5 10h17M9 14l6 4M15 14l-6 4" />
      </svg>
    );
  }
  if (keadaan === "verifikasi") {
    return (
      <svg {...umum}>
        <path d="M12 3.5l8.5 15h-17z" />
        <path d="M12 9.5v4M12 16.5v.01" />
      </svg>
    );
  }
  if (keadaan === "ditahan") {
    return (
      <svg {...umum}>
        <rect x="4.5" y="10.5" width="15" height="10" rx="2" />
        <path d="M8 10.5V7a4 4 0 018 0v3.5" />
      </svg>
    );
  }
  return (
    <svg {...umum}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 8v.01M12 11v5" />
    </svg>
  );
}

function pesan(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}
