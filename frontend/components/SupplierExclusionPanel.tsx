"use client";

import { useRef, useState, type FormEvent } from "react";
import {
  proposeSupplierExclusion, proposeSupplierRestoration,
  type EvidenceRef, type SupplierContext, type SupplierExclusion,
} from "../lib/supplier-exclusions";
import { safetyLabel } from "../lib/bahasa";
import styles from "./SupplierExclusionPanel.module.css";

type Props = {
  context: SupplierContext;
  role: string;
  token: string;
  onCreated: (decisionId: string) => void;
};
type Submit = (operation: () => Promise<string>, success: string) => Promise<boolean>;
const evidenceKey = (ref: EvidenceRef) => `${ref.type}:${ref.id}`;

function RestorationForm({ exclusion, supplier, disabled, submit, token }: {
  exclusion: SupplierExclusion;
  supplier: SupplierContext["suppliers"][number];
  disabled: boolean;
  submit: Submit;
  token: string;
}) {
  const [reason, setReason] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [referenceType, setReferenceType] = useState<EvidenceRef["type"]>("batch");
  const [referenceId, setReferenceId] = useState("");
  const available = supplier.evidence_refs.filter(ref => !exclusion.evidence_refs.some(old => old.id.toLowerCase() === ref.id.toLowerCase()));
  const refs = available.filter(ref => selected.includes(evidenceKey(ref)));
  const validId = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(referenceId);
  const oldId = exclusion.evidence_refs.some(ref => ref.id.toLowerCase() === referenceId.toLowerCase());
  const invalidReference = !!referenceId && (!validId || oldId);
  if (referenceId && !invalidReference && !refs.some(ref => ref.type === referenceType && ref.id.toLowerCase() === referenceId.toLowerCase())) refs.push({ type: referenceType, id: referenceId });
  async function restore(event: FormEvent) {
    event.preventDefault();
    if (disabled || invalidReference || !reason.trim() || !refs.length) return;
    const created = await submit(async () => {
      const result = await proposeSupplierRestoration(exclusion.id, { reason: reason.trim(), evidence_refs: refs }, token);
      if (!result.restoration_decision_id) throw new Error("Respons tidak memuat ID keputusan pemulihan. Muat ulang sebelum mencoba kembali.");
      return result.restoration_decision_id;
    }, "Usulan pemulihan dibuat; verifikasi dan approval baru tetap wajib. Exclusion masih aktif.");
    if (created) { setReason(""); setSelected([]); setReferenceId(""); }
  }
  return <form onSubmit={restore} className={styles.form} aria-label={`Pemulihan ${supplier.name} ${exclusion.id}`}>
    <fieldset disabled={disabled} className={styles.fields}>
      <label className={styles.field}><span>Alasan pemulihan</span><textarea required maxLength={4000} value={reason} onChange={event => setReason(event.target.value)} /></label>
      <fieldset className={styles.evidence}>
        <legend>Pilih bukti baru yang tersimpan</legend>
        {available.map(ref => <label className={styles.choice} key={evidenceKey(ref)}>
          <input type="checkbox" checked={selected.includes(evidenceKey(ref))} onChange={event => setSelected(current => event.target.checked ? [...current, evidenceKey(ref)] : current.filter(key => key !== evidenceKey(ref)))} />
          <span>{ref.type}: {ref.id}</span>
        </label>)}
        {!available.length && <p>Belum ada bukti baru pada keputusan ini. Bukti exclusion lama tidak dapat digunakan kembali.</p>}
      </fieldset>
      <label className={styles.field}><span>Jenis bukti tersimpan</span><select value={referenceType} onChange={event => {
        const value = event.target.value;
        if (value === "batch" || value === "incident" || value === "decision") setReferenceType(value);
      }}><option value="batch">Batch</option><option value="incident">Insiden suhu (DecisionEvidence)</option><option value="decision">Keputusan dengan bukti batch</option></select></label>
      <label className={styles.field}><span>ID bukti tersimpan (opsional bila memilih di atas)</span><input value={referenceId} onChange={event => setReferenceId(event.target.value)} aria-invalid={invalidReference} placeholder="UUID bukti baru" /></label>
      <p>ID harus sudah tersimpan dan terkait supplier ini; server memvalidasi relasinya. Form ini tidak membuat bukti baru.</p>
      {invalidReference && <p className={styles.error}>{oldId ? "Bukti exclusion lama tidak dapat digunakan kembali." : "ID bukti harus berupa UUID yang valid."}</p>}
      <button className="button button-secondary" type="submit" disabled={disabled || invalidReference || !reason.trim() || !refs.length}>Ajukan pemulihan</button>
    </fieldset>
  </form>;
}

export function SupplierExclusionView({ context, role, token, onCreated }: Props) {
  const [supplierId, setSupplierId] = useState(context.suppliers[0]?.id ?? "");
  const [reason, setReason] = useState("");
  const [notice, setNotice] = useState<{ kind: "error" | "success"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const approver = role === "sppg_head" || role === "sppg_nutritionist";
  const canMutate = approver && context.can_propose && !!context.scope_location_id && !!token;
  const supplier = context.suppliers.find(item => item.id === supplierId);

  const submit: Submit = async (operation, success) => {
    if (!canMutate || pending.current) return false;
    pending.current = true; setBusy(true); setNotice(null);
    let decisionId: string;
    try {
      decisionId = await operation();
      setNotice({ kind: "success", text: success });
    } catch (error) {
      setNotice({ kind: "error", text: error instanceof Error ? error.message : "Usulan tidak dapat dibuat." });
      return false;
    } finally { pending.current = false; setBusy(false); }
    onCreated(decisionId);
    return true;
  };
  async function submitExclusion(event: FormEvent) {
    event.preventDefault();
    if (!canMutate || !supplier || !context.scope_location_id || !reason.trim() || !supplier.evidence_refs.length) return;
    const scope = context.scope_location_id;
    const created = await submit(async () => {
      const result = await proposeSupplierExclusion({ supplier_id: supplier.id, scope_location_id: scope, reason: reason.trim(), evidence_refs: supplier.evidence_refs }, token);
      return result.source_decision_id;
    }, "Usulan exclusion dibuat dan menunggu verifikasi serta approval manusia.");
    if (created) setReason("");
  }

  return <section className={styles.panel} aria-label="Supplier exclusion" aria-busy={busy}>
    <div className={styles.header}><h3>Supplier governance</h3><span className={styles.badge}>Lingkup lokal · SPPG</span></div>
    <p>
      SPPG penerima:{" "}
      {context.scope_location_id ? `#${String(context.scope_location_id).slice(0, 8)}` : "tidak tersedia"}.
    </p>
    <p className={styles.safety}>
      Pemulihan administratif tidak mengubah status keamanan batch. Batch yang gagal
      pemeriksaan tetap tidak bisa dipakai.
    </p>
    {context.suppliers.map(item => <div className={styles.record} key={item.id}>
      <strong>{item.name}</strong><span>Supplier: {item.id}</span>
      {item.batches.map(batch => <span key={batch.id}>Batch {batch.id} · Keamanan: <strong>{safetyLabel(batch.safety_status) ?? "status belum ada"}</strong></span>)}
    </div>)}
    {context.reason_unavailable && <p>{context.reason_unavailable}</p>}
    {!canMutate && <p>Hanya Kepala SPPG atau Ahli Gizi pada SPPG tujuan yang berwenang mengusulkan. Tampilan ini hanya baca.</p>}
    {canMutate && <form onSubmit={submitExclusion} className={styles.form} aria-label="Usulan exclusion">
      <fieldset disabled={busy} className={styles.fields}>
        <label className={styles.field}><span>Supplier</span><select value={supplierId} onChange={event => { setSupplierId(event.target.value); setReason(""); }}>
          {context.suppliers.map(item => <option value={item.id} key={item.id}>{item.name}</option>)}
        </select></label>
        <label className={styles.field}><span>Alasan exclusion</span><textarea required maxLength={4000} value={reason} onChange={event => setReason(event.target.value)} /></label>
        <p>Bukti tersimpan: {supplier?.evidence_refs.map(evidenceKey).join(", ") || "tidak tersedia"}</p>
        <button className="button" type="submit" disabled={busy || !reason.trim() || !supplier?.evidence_refs.length}>Ajukan exclusion</button>
      </fieldset>
      <p>Usulan hanya masuk approval. Tidak ada auto execute.</p>
    </form>}
    {context.exclusions.map(exclusion => {
      const linkedSupplier = context.suppliers.find(item => item.id === exclusion.supplier_id);
      const canRestore = canMutate && exclusion.status === "active" && exclusion.scope_location_id === context.scope_location_id && linkedSupplier;
      return <article className={styles.record} key={exclusion.id}>
        <strong>{exclusion.status === "active" ? "Exclusion aktif" : `Exclusion ${exclusion.status}`} · {linkedSupplier?.name ?? exclusion.supplier_id}</strong>
        <span>Scope: {exclusion.scope_location_id}</span><span>{exclusion.reason}</span>
        <span>Bukti exclusion: {exclusion.evidence_refs.map(evidenceKey).join(", ")}</span>
        <button type="button" className={styles.link} disabled={busy} onClick={() => onCreated(exclusion.source_decision_id)}>Lihat keputusan exclusion</button>
        {exclusion.restoration_decision_id && <button type="button" className={styles.link} disabled={busy} onClick={() => { if (exclusion.restoration_decision_id) onCreated(exclusion.restoration_decision_id); }}>Lihat keputusan pemulihan</button>}
        {exclusion.revocation_reason && <span>Alasan pencabutan: {exclusion.revocation_reason}</span>}
        {canRestore && <RestorationForm exclusion={exclusion} supplier={linkedSupplier} disabled={busy} submit={submit} token={token} />}
      </article>;
    })}
    {busy && <p role="status">Mengirim usulan…</p>}
    {notice && <p role={notice.kind === "error" ? "alert" : "status"} className={notice.kind === "error" ? styles.error : styles.notice}>{notice.text}</p>}
  </section>;
}
