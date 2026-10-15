// Pemilih keputusan (dropdown "Pilih keputusan" di halaman Decision & Evidence
// dan Agent Log) — logika murni, bisa diuji tanpa DOM.
//
// Kenapa ada: satu <option> per keputusan dengan istilah backend mentah
// ("regional_balance · proposed · ef347f91"), berurutan apa adanya, membuat
// pengguna tidak tahu mana yang perlu ditindak dan apa arti tiap barisnya.
// Modul ini menyusun ulang menjadi kelompok berurut + label bahasa manusia.
//
// Aturan yang dipegang:
//   - tidak ada istilah baru yang dikarang: kata jenis keputusan datang dari
//     DECISION_TYPE_LABELS (satu sumber, dipakai kartu feed & "Hari Ini"), dan
//     "menunggu tindakan" memakai isActionable() — definisi yang sama dengan
//     notifikasi top bar;
//   - urutan di dalam kelompok "menunggu tindakan" memakai pendingDecisions():
//     sudah lewat dulu (paling baru lewat), lalu jatuh tempo terdekat, lalu
//     yang tanggalnya tidak terbaca;
//   - status tak dikenal ditulis apa adanya (garis bawah → spasi), tidak ditebak;
//   - nilai waktu hanya dicetak kalau bisa dibaca; selain itu bagiannya
//     dihilangkan, bukan ditulis "—" (opsi select tidak boleh penuh tanda pisah);
//   - keputusan tanpa id dilewati supaya tidak ada opsi palsu.

import { DECISION_TYPE_LABELS } from "../components/RecommendationCard";
import { shortId } from "./agent-quality";
import { formatDateTime } from "./datetime";
import { dueLabel, pendingDecisions, type TodayDecision } from "./today";

export type PickerOption = { value: string; label: string };
export type PickerGroup = {
  id: "action" | "proposed" | "rest";
  label: string;
  options: PickerOption[];
};

/** Status backend → bahasa manusia. Tak dikenal jatuh ke bentuk apa adanya. */
export const STATUS_WORDS: Record<string, string> = {
  proposed: "diusulkan",
  pending_approval: "menunggu persetujuan",
  needs_verification: "perlu verifikasi",
  verifier_flagged: "ditandai verifier",
  approved: "disetujui",
  executed: "dieksekusi",
  expired: "kedaluwarsa",
  rejected: "ditolak",
};

const DASH = "—";
const SEP = " · ";

/** Jenis keputusan → bahasa manusia (peta milik RecommendationCard; jangan diduplikasi). */
export function typeWord(decisionType: unknown): string {
  const key = String(decisionType ?? "").trim();
  if (!key) return "keputusan";
  return DECISION_TYPE_LABELS[key] ?? key.replace(/_/g, " ");
}

/** Status → bahasa manusia; tak dikenal ditulis apa adanya. */
export function statusWord(status: unknown): string {
  const key = String(status ?? "")
    .trim()
    .toLowerCase();
  if (!key) return DASH;
  return STATUS_WORDS[key] ?? key.replace(/_/g, " ");
}

const statusOf = (decision: TodayDecision): string =>
  String(decision?.status ?? "")
    .trim()
    .toLowerCase();

function timeOf(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const ms = Date.parse(String(value));
  return Number.isFinite(ms) ? ms : null;
}

/** Terbaru dulu; tanggal tak terbaca diletakkan di akhir tanpa diacak. */
function byNewest(list: TodayDecision[], key: "created_at" | "expires_at"): TodayDecision[] {
  return list
    .map((decision, index) => ({ decision, index, ms: timeOf(decision?.[key]) }))
    .sort((a, b) => {
      if (a.ms === null && b.ms === null) return a.index - b.index;
      if (a.ms === null) return 1;
      if (b.ms === null) return -1;
      return b.ms - a.ms;
    })
    .map((row) => row.decision);
}

/** Bagian label yang hanya dicetak kalau nilainya bisa dibaca. */
function timePart(label: string): string[] {
  return label === DASH ? [] : [label];
}

/**
 * Susun kelompok opsi untuk <select>. `now` boleh null (jam klien belum siap):
 * kalau null, tidak ada klaim sisa waktu sama sekali.
 */
export function decisionGroups(decisions: unknown, now: Date | null): PickerGroup[] {
  const list = (Array.isArray(decisions) ? decisions : []).filter(
    (row): row is TodayDecision =>
      typeof (row as TodayDecision | null)?.decision_id === "string" &&
      Boolean((row as TodayDecision).decision_id)
  );

  const actionable = pendingDecisions(list, now ?? new Date(0)).items;
  const proposed = byNewest(
    list.filter((decision) => statusOf(decision) === "proposed"),
    "created_at"
  );
  const terpakai = new Set(
    [...actionable, ...proposed].map((decision) => decision.decision_id as string)
  );
  const rest = byNewest(
    list.filter((decision) => !terpakai.has(decision.decision_id as string)),
    "created_at"
  );

  const groups: PickerGroup[] = [];

  if (actionable.length) {
    groups.push({
      id: "action",
      label: `Menunggu tindakan (${actionable.length})`,
      options: actionable.map((decision) => ({
        value: decision.decision_id as string,
        label: [
          typeWord(decision.decision_type),
          // Tanpa jam klien (now null) tidak ada klaim sisa waktu sama sekali.
          ...(now ? timePart(dueLabel(decision.expires_at, now)) : []),
          shortId(decision.decision_id),
        ].join(SEP),
      })),
    });
  }

  if (proposed.length) {
    groups.push({
      id: "proposed",
      label: `Diusulkan, belum masuk persetujuan (${proposed.length})`,
      options: proposed.map((decision) => ({
        value: decision.decision_id as string,
        label: [
          typeWord(decision.decision_type),
          ...timePart(formatDateTime(String(decision.created_at ?? ""))),
          shortId(decision.decision_id),
        ].join(SEP),
      })),
    });
  }

  if (rest.length) {
    groups.push({
      id: "rest",
      label: `Tidak menunggu tindakan (${rest.length})`,
      options: rest.map((decision) => ({
        value: decision.decision_id as string,
        label: [
          typeWord(decision.decision_type),
          statusWord(decision.status),
          ...timePart(formatDateTime(String(decision.created_at ?? ""))),
          shortId(decision.decision_id),
        ].join(SEP),
      })),
    });
  }

  return groups;
}
