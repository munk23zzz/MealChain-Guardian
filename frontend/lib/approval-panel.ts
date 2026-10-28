/**
 * Modul persetujuan halaman "Decision & Evidence" — satu turunan murni dari
 * read model server, mengikuti dokumen `02-approval-action.md` §7.
 *
 * Kenapa modul terpisah: sebelumnya informasi persetujuan tersebar di lima
 * blok (chip status, progres peran, daftar fakta, penghalang, tombol) sehingga
 * pembaca harus menyusun sendiri kesimpulannya (§7.1). Di sini kesimpulan itu
 * disusun SEKALI, dari data yang sama, dan bisa diuji tanpa DOM.
 *
 * Aturan yang dijaga:
 *  - tidak ada kewenangan yang dihitung di UI: `can_approve`, `can_execute`,
 *    `approval_state.missing`, dan `blocking_reasons` tetap milik server;
 *  - payload yang belum ada TIDAK diartikan "boleh" (§4.3): keadaan
 *    `tidak_diketahui` menyebut datanya belum diterima;
 *  - penolakan dan kedaluwarsa dibedakan nada MAUPUN kalimat (§7.4), karena
 *    tindak lanjutnya berbeda: penolakan bisa diusulkan ulang, kedaluwarsa
 *    tidak;
 *  - nama & jam penyetuju hanya ditampilkan bila server mengirimnya (§7.3).
 */

import { blockingReasons } from "./bahasa";
import { formatDateTime } from "./datetime";
import { governanceView } from "./governance";
import { roleLabel } from "./settings";

export type FaseKode =
  | "tidak_diketahui"
  | "belum_lengkap"
  | "bisa_setujui"
  | "siap_eksekusi"
  | "menunggu_review_po"
  | "selesai"
  | "ditolak"
  | "kedaluwarsa"
  | "hanya_baca";

/**
 * Peran yang boleh menyetujui/menolak. Sama dengan APPROVER_ROLES di
 * `app/core/approval_matrix.py`; salinan ini hanya untuk MEMBACA, bukan
 * penjaga — server tetap yang memutuskan.
 */
const PERAN_PENYETUJU = new Set(["sppg_head", "sppg_nutritionist"]);

export function peranPenyetuju(role: string): boolean {
  return PERAN_PENYETUJU.has(role);
}

/**
 * Nada warna/ikon. `expired` sengaja BUKAN `danger`: kedaluwarsa bukan
 * kegagalan yang dilakukan orang, dan §7.4 meminta keduanya tidak memakai
 * warna/ikon yang sama.
 */
export type Nada = "safe" | "warning" | "danger" | "expired" | "neutral";

export type Fase = {
  kode: FaseKode;
  label: string;
  nada: Nada;
  /** Satu kalimat: kenapa keadaannya begini. */
  sebab: string;
};

export type POInfo = { po_number: string; status: string; created_at?: string | null };

export type BarisPenyetuju = {
  roles: string[];
  label: string;
  done: boolean;
  nama: string | null;
  jam: string | null;
  catatan: string | null;
};

export type Langkah = {
  id: "menyetujui" | "terbitkan_po" | "review_po";
  label: string;
  tersedia: boolean;
  alasan: string | null;
};

export type TigaJawaban = {
  /** Apa yang menahan, sudah diterjemahkan ke bahasa penyetuju. */
  menahan: string[];
  /** Siapa yang dibutuhkan sekarang, dengan progres dari server. */
  dibutuhkan: string;
  /** Apa yang terjadi setelah langkah ini. */
  setelah: string;
};

function obj(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function daftar(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function teks(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  const hasil = String(value).trim();
  return hasil === "" ? null : hasil;
}

/**
 * Apakah PERAN INI sudah tercatat menyetujui? Dipakai membedakan "menunggu
 * rekan" dari "giliran Anda" pada keadaan `sebagian` — keduanya terlihat sama
 * dari `approval_state` saja, dan salah membaca membuat orang menunggu dirinya
 * sendiri (terukur 28 Okt 2026: Ahli Gizi melihat label "Menunggu rekan…"
 * padahal approving tinggal dia).
 */
export function peranSudahSetuju(summary: unknown, role: string): boolean {
  const state = obj(obj(summary)?.approval_state);
  const approved = Array.isArray(state?.approved_roles) ? (state?.approved_roles as unknown[]) : [];
  return approved.some((r) => (Array.isArray(r) ? r.includes(role) : String(r) === role));
}

/** `purchase_order` dari read model — bentuknya dijaga, bukan diasumsikan. */
export function poDari(summary: unknown): POInfo | null {
  const po = obj(obj(summary)?.purchase_order);
  const nomor = teks(po?.po_number);
  const status = teks(po?.status);
  if (!nomor || !status) return null;
  return { po_number: nomor, status: status.toLowerCase(), created_at: teks(po?.created_at) };
}

function adaRingkasan(summary: unknown): boolean {
  const payload = obj(summary);
  return Boolean(payload && Object.keys(payload).length > 0);
}

function kedaluwarsa(summary: unknown): boolean {
  const expiry = obj(obj(summary)?.expiry);
  return expiry?.valid === false;
}

export function fasePersetujuan({
  summary,
  role,
}: {
  summary: unknown;
  role: string;
}): Fase {
  if (!adaRingkasan(summary)) {
    return {
      kode: "tidak_diketahui",
      label: "Belum ada data approval",
      nada: "neutral",
      sebab:
        "Ringkasan persetujuan belum diterima dari server. Tidak ada tombol yang " +
        "ditampilkan sampai datanya ada — UI tidak menyimpulkan sendiri.",
    };
  }
  const payload = obj(summary) ?? {};
  const view = governanceView(summary);
  const po = poDari(summary);
  const status = (teks(payload.status) ?? "").toLowerCase();

  // Urutan sengaja: keadaan final menang atas keadaan antara.
  if (status === "executed" || view.state === "selesai") {
    return {
      kode: "selesai",
      label: "Selesai",
      nada: "safe",
      sebab: po
        ? `PO ${po.po_number} sudah dikirim ke SAP (status ${po.status}).`
        : "Keputusan sudah dieksekusi.",
    };
  }
  if (view.state === "ditolak") {
    return {
      kode: "ditolak",
      label: "Ditolak — bisa diusulkan ulang",
      nada: "danger",
      sebab:
        "Penolakan punya alasan manusia dan menjadi bahan iterasi agent: keputusan " +
        "baru bisa diajukan dengan perbaikan, tanpa membuat ulang dari nol.",
    };
  }
  if (kedaluwarsa(summary)) {
    return {
      kode: "kedaluwarsa",
      label: "Kedaluwarsa — waktu habis",
      nada: "expired",
      sebab:
        "Jendela berlaku keputusan sudah lewat. Ini bukan penolakan: tidak ada " +
        "alasan manusia di dalamnya, dan tidak ada yang bisa diusulkan ulang dari " +
        "keputusan ini.",
    };
  }
  if (po && po.status === "draft") {
    return {
      kode: "menunggu_review_po",
      label: "Menunggu review PO",
      nada: "warning",
      sebab: `PO ${po.po_number} sudah terbit sebagai draft; Kepala SPPG harus mereviewnya sebelum dikirim ke SAP.`,
    };
  }
  // Kelima yang tidak ada di daftar dokumen tapi nyata di lapangan: semua peran
  // sudah menyetujui, PO belum terbit (`can_execute` true). Tanpa cabang ini
  // kepala modul menulis "Belum bisa disetujui" padahal ADA yang bisa
  // dikerjakan — terukur di aplikasi hidup pada keputusan ade9e486 (28 Okt 2026).
  // Pengawas (bgn_monitor) tidak punya giliran apa pun: seluruh panel boleh
  // dibaca, tetapi tidak ada langkah yang "tersedia" untuknya. Sejak 28 Okt 2026
  // read model juga mengirim `can_approve: false` untuk peran ini; cabang ini
  // membuat ALASANNYA terbaca, bukan sekadar tombol yang hilang.
  if (!peranPenyetuju(role)) {
    return {
      kode: "hanya_baca",
      label: "Tampilan hanya-baca",
      nada: "neutral",
      sebab:
        "Peran Anda memantau: bukti dan alasan tertahan tetap dibaca lengkap, " +
        "tetapi menyetujui, menerbitkan PO, dan review PO bukan kewenangan peran ini.",
    };
  }
  if (view.state === "siap") {
    return {
      kode: "siap_eksekusi",
      label: "Siap menerbitkan PO draft",
      nada: "safe",
      sebab:
        "Semua peran syarat sudah menyetujui. Langkah berikutnya menerbitkan PO draft; " +
        "Kepala SPPG lalu mereviewnya sebelum PO dikirim ke SAP.",
    };
  }
  if (view.canApprove) {
    return {
      kode: "bisa_setujui",
      label: "Bisa Anda setujui sekarang",
      nada: "safe",
      sebab: `Syarat persetujuan sudah terpenuhi untuk peran ${roleLabel(role)}; menyetujui tidak menjalankan apa pun — eksekusi tetap langkah terpisah.`,
    };
  }
  return {
    kode: "belum_lengkap",
    label: "Belum bisa disetujui",
    nada: "warning",
    sebab:
      view.blocker[0] ??
      "Server belum menyatakan keputusan ini boleh disetujui oleh peran Anda.",
  };
}

export function tigaJawaban({
  summary,
  role,
  now,
}: {
  summary: unknown;
  role: string;
  now: Date | null;
}): TigaJawaban {
  const fase = fasePersetujuan({ summary, role });
  const view = governanceView(summary);
  const po = poDari(summary);
  const menahan = blockingReasons(summary);
  // `now` diterima supaya pemanggil bisa memakai jam yang sama dengan bagian
  // lain halaman ini; hitungan kedaluwarsa di sini tidak dihitung ulang.
  void now;

  const progres =
    view.total > 0 ? `${view.done} dari ${view.total} peran syarat` : null;
  let dibutuhkan: string;
  if (fase.kode === "menunggu_review_po" && po) {
    dibutuhkan = `Review Kepala SPPG atas PO ${po.po_number}`;
  } else if (fase.kode === "siap_eksekusi") {
    dibutuhkan = [progres ? `${progres} terpenuhi` : null, "tidak ada peran yang kurang"]
      .filter(Boolean)
      .join(" · ");
  } else if (view.missingLabels.length > 0) {
    dibutuhkan = [progres, `menunggu ${view.missingLabels.join(" dan ")}`]
      .filter(Boolean)
      .join(" · ");
  } else if (progres) {
    dibutuhkan = `${progres} terpenuhi`;
  } else {
    dibutuhkan = "Tidak ada peran yang kurang menurut server.";
  }

  let setelah: string;
  switch (fase.kode) {
    case "selesai":
      setelah = po
        ? `PO ${po.po_number} sudah terkirim ke SAP; tidak ada langkah persetujuan lagi.`
        : "Keputusan sudah dieksekusi; tidak ada langkah persetujuan lagi.";
      break;
    case "menunggu_review_po":
      setelah = po
        ? `Setelah PO ${po.po_number} direview Kepala SPPG, PO terkirim ke SAP dan keputusan menjadi selesai.`
        : "Setelah PO direview Kepala SPPG, PO terkirim ke SAP dan keputusan menjadi selesai.";
      break;
    case "siap_eksekusi":
      setelah =
        "Eksekusi menerbitkan PO draft; Kepala SPPG mereview PO itu sebelum dikirim ke SAP.";
      break;
    case "ditolak":
      setelah =
        "Setelah ditolak, agent bisa mengajukan iterasi baru dari alasan penolakan; keputusan ini tetap tersimpan sebagai riwayat.";
      break;
    case "kedaluwarsa":
      setelah =
        "Tidak ada langkah lanjutan: keputusan yang lewat jendela harus diajukan ulang.";
      break;
    default:
      setelah =
        "Setelah approval lengkap, eksekusi hanya menerbitkan PO draft; Kepala SPPG mereview PO itu sebelum dikirim ke SAP.";
  }

  return { menahan, dibutuhkan, setelah };
}

export function ledgerPenyetuju({
  summary,
  now,
}: {
  summary: unknown;
  now: Date | null;
}): BarisPenyetuju[] {
  void now;
  const payload = obj(summary) ?? {};
  const requirement = obj(payload.approval_requirement) ?? {};
  const gruping = daftar(requirement.required_roles)
    .map((grup) => (Array.isArray(grup) ? grup : [grup]))
    .map((grup) => grup.map((r) => String(r)).filter(Boolean))
    .filter((grup) => grup.length > 0);
  const baris = daftar(payload.approvals)
    .map((row) => obj(row))
    .filter((row): row is Record<string, unknown> => row !== null);

  const hasil: BarisPenyetuju[] = gruping.map((roles) => {
    const cocok = baris.find(
      (row) => row.approved === true && roles.includes(String(row.role ?? ""))
    );
    const nama = cocok ? teks(cocok.approved_by_name) : null;
    const jamMentah = cocok ? teks(cocok.approved_at) : null;
    const jam = jamMentah ? formatDateTime(jamMentah) : null;
    return {
      roles,
      label: roles.map((r) => roleLabel(r)).join(" atau "),
      done: Boolean(cocok),
      nama,
      jam: jam === "—" ? null : jam,
      catatan:
        baris.length === 0
          ? "Backend belum mengirim baris persetujuan untuk keputusan ini."
          : null,
    };
  });

  // Server bisa mencatat approval dari peran di luar syarat (mis. data lama
  // sebelum ruling cakupan). Fakta itu ditampilkan, bukan dibuang — tetapi
  // ditandai sebagai di luar syarat supaya tidak terbaca sebagai pemenuhan.
  for (const row of baris) {
    if (row.approved !== true) continue;
    const peran = String(row.role ?? "");
    if (!peran) continue;
    if (hasil.some((item) => item.roles.includes(peran))) continue;
    hasil.push({
      roles: [peran],
      label: roleLabel(peran),
      done: true,
      nama: teks(row.approved_by_name),
      jam: teks(row.approved_at) ? formatDateTime(String(row.approved_at)) : null,
      catatan: "Di luar syarat peran — tidak dihitung sebagai pemenuhan.",
    });
  }

  return hasil;
}

export function langkahPersetujuan({
  summary,
  role,
}: {
  summary: unknown;
  role: string;
}): { menyetujui: Langkah; terbitkanPo: Langkah; reviewPo: Langkah } {
  const view = governanceView(summary);
  const fase = fasePersetujuan({ summary, role });
  const po = poDari(summary);
  const alasanUmum =
    view.blocker[0] ??
    (fase.kode === "tidak_diketahui"
      ? "Belum ada data approval dari server."
      : fase.sebab);

  // Untuk pengawas, "tidak tersedia" bukan karena jendela lewat atau approval
  // kurang — melainkan karena perannya. Alasan yang jujur itu dipakai ulang
  // pada kedua langkah pertama.
  const bukanPenyetuju = !peranPenyetuju(role);
  const alasanPeran = "Peran Anda memantau, bukan menyetujui.";

  const menyetujui: Langkah = {
    id: "menyetujui",
    label: "Menyetujui keputusan",
    tersedia: !bukanPenyetuju && view.canApprove,
    alasan: bukanPenyetuju ? alasanPeran : view.canApprove ? null : alasanUmum,
  };

  const terbitkanPo: Langkah = {
    id: "terbitkan_po",
    label: po ? `Menerbitkan PO untuk ${po.po_number}` : "Menerbitkan PO draft",
    tersedia: !bukanPenyetuju && view.canExecute,
    alasan: bukanPenyetuju ? alasanPeran : view.canExecute ? null : alasanUmum,
  };

  let reviewTersedia = false;
  let reviewAlasan: string | null;
  if (bukanPenyetuju) {
    reviewAlasan = alasanPeran;
  } else if (po == null) {
    reviewAlasan = "Belum ada PO — terbitkan PO dulu lewat eksekusi.";
  } else if (po.status !== "draft") {
    reviewAlasan = `PO ${po.po_number} sudah berstatus ${po.status}; tidak ada review yang tertunda.`;
  } else if (role !== "sppg_head") {
    reviewAlasan = "Hanya Kepala SPPG yang mereview PO.";
  } else {
    reviewTersedia = true;
    reviewAlasan = null;
  }

  const reviewPo: Langkah = {
    id: "review_po",
    label: po ? `Review PO ${po.po_number}` : "Review PO",
    tersedia: reviewTersedia,
    alasan: reviewAlasan,
  };

  return { menyetujui, terbitkanPo, reviewPo };
}
