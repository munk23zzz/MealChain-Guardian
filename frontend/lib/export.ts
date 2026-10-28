import { evidenceRowsFromDossier, type ComplianceDossier } from "./evidence";
import { fetchDossier, fetchPurchaseOrderPdf } from "./api";

const FORBIDDEN = /^(token|access_token|refresh_token|credential|credentials|private_key|privatekey|secret)$/i;

function withoutSecrets(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(withoutSecrets);
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>)
      .filter(([key]) => !FORBIDDEN.test(key))
      .map(([key, child]) => [key, withoutSecrets(child)])
  );
}

export function dossierToJson(dossier: ComplianceDossier): string {
  return JSON.stringify(withoutSecrets(dossier), null, 2);
}

function csvCell(value: unknown): string {
  const text = value == null ? "" : typeof value === "string" ? value : typeof value === "number" || typeof value === "boolean" ? String(value) : JSON.stringify(value);
  // A spreadsheet may ignore leading spaces/tabs before evaluating a formula.
  // Put the apostrophe before any such padding, while preserving the value.
  const safe = /^[\s\uFEFF]*[=+\-@]/.test(text) ? `'${text}` : text;
  return `"${safe.replace(/"/g, '""')}"`;
}

/**
 * Tabel (kepala kolom + baris) → CSV dengan aturan sel yang SAMA dengan ekspor
 * dossier: setiap sel dikutip, dan sel yang bisa dibaca spreadsheet sebagai
 * formula diberi apostrof. Dipakai modul Keamanan Pangan (ekspor baca-saja).
 */
export function tableToCsv(header: readonly string[], rows: readonly unknown[][]): string {
  const baris = [header.join(","), ...rows.map((row) => row.map(csvCell).join(","))];
  return baris.join("\r\n") + "\r\n";
}

export function dossierToCsv(dossier: ComplianceDossier): string {
  const header = ["decision_id", "content_address", "signature_state", "signature", "signature_public_key", "evidence_id", "evidence_type", "status", "reading", "unit", "source", "provenance", "recorded_at", "rule", "consistency"];
  const signature = dossier.signature ?? {};
  const rows = evidenceRowsFromDossier(dossier).map((row) => [
    dossier.decision_id,
    dossier.content_address ?? null,
    signature.state ?? null,
    signature.signature ?? null,
    signature.public_key ?? null,
    row.id,
    row.evidenceType,
    row.status,
    row.reading,
    row.unit,
    row.source,
    row.provenance,
    row.recordedAt,
    row.rule,
    row.consistency,
  ]);
  return tableToCsv(header, rows);
}

export function downloadText(filename: string, content: string, mime = "text/plain;charset=utf-8"): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

/** Unduh berkas biner yang sudah diterima (dipakai dokumen PO). */
export function downloadBlob(filename: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

/**
 * Nama berkas dokumen PO — ATURAN YANG SAMA dengan `po_document.nama_berkas`
 * di backend (`PO-` + nomor, karakter di luar `A-Za-z0-9-_.` jadi `-`).
 *
 * Disalin, bukan dibaca dari `Content-Disposition`: header itu hanya bisa
 * dibaca lintas-origin bila server mengeksposnya, dan nama berkas tidak boleh
 * bergantung pada konfigurasi CORS.
 */
export function poFileName(poNumber: string): string {
  const bersih = poNumber.replace(/[^A-Za-z0-9\-_.]/g, "-");
  return `PO-${bersih}.pdf`;
}

/**
 * Unduh dokumen PO (PDF) satu nomor PO. Mengembalikan nama berkas supaya UI
 * memberi umpan balik jujur ("terunduh sebagai …"), seperti ekspor dossier.
 */
export async function downloadPoPdf(poNumber: string, token: string): Promise<string> {
  const blob = await fetchPurchaseOrderPdf(poNumber, token);
  const nama = poFileName(poNumber);
  downloadBlob(nama, blob);
  return nama;
}

/**
 * Nama berkas artefak bukti — SATU tempat, supaya ekspor dari kepala halaman dan
 * dari panel bukti tersimpan tidak pernah memberi nama berbeda untuk benda sama.
 */
export function dossierFileName(decisionId: string): string {
  return `dossier-${decisionId}.json`;
}

/**
 * Unduh dossier JSON satu keputusan (bukti tersimpan: alamat konten + tanda
 * tangan). Dipakai tombol "Unduh bukti" di kepala halaman Decision & Evidence;
 * mengembalikan nama berkas supaya UI bisa memberi umpan balik yang jujur.
 */
export async function downloadDossier(decisionId: string, token: string): Promise<string> {
  const dossier = (await fetchDossier(decisionId, token)) as ComplianceDossier;
  const nama = dossierFileName(decisionId);
  downloadText(nama, dossierToJson(dossier), "application/json;charset=utf-8");
  return nama;
}
