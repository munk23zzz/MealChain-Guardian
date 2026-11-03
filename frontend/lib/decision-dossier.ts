// Penyusun halaman "Decision & Evidence" — satu keputusan, satu dossier.
//
// Rencana lengkap: docs/plans/decision-evidence-rebuild.md. Berkas ini sengaja
// MURNI (tanpa React, tanpa fetch) supaya aturan halaman bisa diuji tanpa DOM:
//
//   1. Lima bagian dengan urutan tetap; tidak ada bagian yang muncul/hilang
//      menurut selera tata letak.
//   2. Bagian yang datanya tidak ada WAJIB menyebut sebabnya ("belum ada …"),
//      bukan tampil kosong tanpa alasan. Ini yang mencegah layar menampilkan
//      "0" atau "—" yang membuat pembaca mengira sudah dihitung.
//   3. Yang boleh tampil hanya data milik keputusan yang sedang dibuka. PO
//      disaring `decision_id`; ceklis disaring `batch_id` milik keputusan itu.
//      Tidak ada daftar jaringan di sini (itu halaman Pemasok/PO).

export const ID_BAGIAN = ["kepala", "keputusan", "jalur", "bukti", "jejak"] as const;

export type BagianId = (typeof ID_BAGIAN)[number];

export type Bagian = {
  id: BagianId;
  label: string;
  /** `null` = bagian punya isi. Selain null = sebab bagian masih kosong. */
  kosong: string | null;
  /** Kekurangan yang TIDAK mengosongkan bagian (mis. batch belum tertaut). */
  catatan: string | null;
};

export type DossierInput = {
  decision?: unknown;
  summary?: unknown;
  chain?: unknown;
  packet?: unknown;
  purchaseOrders?: unknown;
  receipts?: unknown;
  /** Dipakai bila id keputusan datang dari pemilih, bukan dari objek keputusan. */
  decisionId?: string | null;
};

export type PoKeputusan = {
  poNumber: string;
  status: string;
  createdAt: string | null;
};

export type RingkasCeklis = {
  batchIds: string[];
  /** Batch yang SUDAH punya baris ceklis (status apa pun). */
  terisi: number;
  /** Baris ceklis yang sudah diputuskan Kepala SPPG. */
  disetujui: number;
  /** Baris ceklis yang sudah diisi pemeriksa, belum diputuskan. */
  menunggu: number;
  /** Batch yang tertaut keputusan tetapi belum punya baris ceklis sama sekali. */
  belumDiisi: number;
  /** `true` = keputusan tidak menautkan batch, jadi ceklis tidak bisa diminta. */
  tanpaTautan: boolean;
};

const LABEL: Record<BagianId, string> = {
  kepala: "Kepala",
  keputusan: "Keputusan",
  jalur: "Jalur",
  bukti: "Bukti",
  jejak: "Jejak & hasil",
};

function objek(nilai: unknown): Record<string, unknown> | null {
  return nilai && typeof nilai === "object" && !Array.isArray(nilai)
    ? (nilai as Record<string, unknown>)
    : null;
}

function daftar(nilai: unknown): Record<string, unknown>[] {
  const langsung = Array.isArray(nilai) ? nilai : objek(nilai)?.items;
  if (!Array.isArray(langsung)) return [];
  return langsung.filter((baris) => objek(baris) !== null) as Record<string, unknown>[];
}

function teks(nilai: unknown): string | null {
  return typeof nilai === "string" && nilai.trim() !== "" ? nilai : null;
}

function idKeputusan(input: DossierInput): string | null {
  const dariKeputusan = objek(input.decision);
  return (
    teks(dariKeputusan?.decision_id) ??
    teks(dariKeputusan?.id) ??
    teks(input.decisionId)
  );
}

/** PO yang tampil halaman ini HANYA milik keputusan yang dibuka. */
export function poKeputusan(
  purchaseOrders: unknown,
  decisionId: string | null | undefined
): PoKeputusan | null {
  const id = teks(decisionId);
  if (!id) return null;
  const milikSendiri = daftar(purchaseOrders).filter(
    (baris) => teks(baris.decision_id) === id
  );
  if (milikSendiri.length === 0) return null;
  // Server tidak menjamin urutan; yang terbaru yang ditampilkan.
  const terbaru = milikSendiri.reduce((pilih, baris) => {
    const jam = teks(baris.created_at) ?? "";
    const jamPilih = teks(pilih.created_at) ?? "";
    return jam > jamPilih ? baris : pilih;
  });
  return {
    poNumber: teks(terbaru.po_number) ?? "(tanpa nomor)",
    status: teks(terbaru.status) ?? "tidak diketahui",
    createdAt: teks(terbaru.created_at),
  };
}

/** Batch yang ditautkan keputusan (dari paket bukti), bukan semua batch jaringan. */
function batchKeputusan(packet: unknown): string[] {
  const paket = objek(packet);
  if (!paket) return [];
  const kandidat = [
    daftar(paket.batches),
    daftar(objek(paket.cost)?.batches),
    daftar(objek(paket.costs)?.batches),
  ];
  const hasil: string[] = [];
  for (const grup of kandidat) {
    for (const baris of grup) {
      const id = teks(baris.batch_id) ?? teks(baris.id);
      if (id && !hasil.includes(id)) hasil.push(id);
    }
  }
  if (Array.isArray(paket.batch_ids)) {
    for (const nilai of paket.batch_ids) {
      const id = teks(nilai);
      if (id && !hasil.includes(id)) hasil.push(id);
    }
  }
  return hasil;
}

export function ringkasCeklis({
  packet,
  receipts,
}: {
  packet?: unknown;
  receipts?: unknown;
}): RingkasCeklis {
  const batchIds = batchKeputusan(packet);
  const barisCeklis = daftar(receipts);
  let terisi = 0;
  let disetujui = 0;
  let menunggu = 0;
  for (const id of batchIds) {
    // Ceklis batch lain tidak dihitung. Satu batch bisa punya riwayat beberapa
    // baris (mis. ditolak lalu diisi ulang), jadi yang dibaca baris TERAKHIR.
    const milik = barisCeklis
      .filter((baris) => teks(baris.batch_id) === id)
      .sort((a, b) => (teks(a.recorded_at) ?? "").localeCompare(teks(b.recorded_at) ?? ""));
    const terakhir = milik[milik.length - 1];
    if (!terakhir) continue;
    terisi += 1;
    // Kosakata status dari model `BatchReceipt`: menunggu → disetujui/ditolak.
    const status = (teks(terakhir.status) ?? "").toLowerCase();
    if (status === "disetujui") disetujui += 1;
    else if (status === "menunggu") menunggu += 1;
  }
  return {
    batchIds,
    terisi,
    disetujui,
    menunggu,
    belumDiisi: batchIds.length - terisi,
    tanpaTautan: batchIds.length === 0,
  };
}

export function susunBagian(input: DossierInput): Bagian[] {
  const id = idKeputusan(input);
  const ringkasan = objek(input.summary);
  const jalur = daftar(input.chain);
  const paket = objek(input.packet);
  const po = poKeputusan(input.purchaseOrders, id);
  const ceklis = ringkasCeklis({ packet: input.packet, receipts: input.receipts });

  const kosong: Record<BagianId, string | null> = {
    kepala: id ? null : "keputusan belum dipilih — pilih satu dari daftar di atas",
    keputusan: ringkasan
      ? null
      : "ringkasan persetujuan belum terbaca — aksi tidak ditampilkan sebelum angkanya ada",
    jalur: jalur.length > 0 ? null : "belum ada jejak persetujuan untuk keputusan ini",
    bukti: paket ? null : "belum ada paket bukti untuk keputusan ini",
    jejak:
      po || ceklis.terisi > 0
        ? null
        : "belum ada PO untuk keputusan ini dan ceklisnya belum ada",
  };
  const catatan: Record<BagianId, string | null> = {
    kepala: null,
    keputusan: null,
    jalur: null,
    bukti: null,
    jejak: catatanJejak(ceklis),
  };

  return ID_BAGIAN.map((bagian) => ({
    id: bagian,
    label: LABEL[bagian],
    kosong: kosong[bagian],
    catatan: catatan[bagian],
  }));
}

function catatanJejak(ceklis: RingkasCeklis): string | null {
  if (ceklis.tanpaTautan) {
    return "keputusan ini belum menautkan batch — ceklis belum bisa diminta";
  }
  if (ceklis.belumDiisi > 0) {
    return `${ceklis.belumDiisi} dari ${ceklis.batchIds.length} batch belum punya ceklis penerimaan`;
  }
  if (ceklis.menunggu > 0) {
    return `${ceklis.menunggu} ceklis sudah diisi, menunggu keputusan Kepala SPPG`;
  }
  return null;
}
