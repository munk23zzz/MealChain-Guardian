const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Keep backend validation details visible; generic api.request drops them.
async function request<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init);
  const text = await response.text();
  if (!response.ok) {
    let detail = "";
    try {
      const body: unknown = JSON.parse(text);
      if (body && typeof body === "object" && "detail" in body && typeof body.detail === "string") detail = body.detail;
    } catch { /* Non-JSON proxy errors use the HTTP fallback. */ }
    throw new Error(detail ? `HTTP ${response.status}: ${detail}` : `HTTP ${response.status}: Usulan tidak dapat diproses. Muat ulang konteks dan coba kembali.`);
  }
  try { return JSON.parse(text); }
  catch { throw new Error("Respons server bukan JSON. Muat ulang konteks sebelum mencoba kembali."); }
}

export type EvidenceRef = { type: "batch" | "incident" | "decision"; id: string };
export type SupplierExclusion = {
  id: string; supplier_id: string; scope_location_id: string;
  status: "proposed" | "active" | "rejected" | "revoked";
  reason: string; evidence_refs: EvidenceRef[]; source_decision_id: string;
  restoration_decision_id: string | null; activated_at: string | null;
  revoked_at: string | null; revocation_reason: string | null;
};
export type SupplierContext = {
  suppliers: { id: string; name: string; batch_ids: string[]; evidence_refs: EvidenceRef[];
    batches: { id: string; safety_status: string | null }[] }[];
  scope_location_id: string | null; can_propose: boolean;
  reason_unavailable: string | null; exclusions: SupplierExclusion[];
};

function headers(token: string) {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}
export function fetchSupplierContext(decisionId: string, token: string): Promise<SupplierContext> {
  return request(`/supplier-exclusions/context/${encodeURIComponent(decisionId)}`, { headers: headers(token) });
}
export function proposeSupplierExclusion(payload: {
  supplier_id: string; scope_location_id: string; reason: string; evidence_refs: EvidenceRef[];
}, token: string): Promise<SupplierExclusion> {
  return request("/supplier-exclusions/proposals", {
    method: "POST", headers: headers(token), body: JSON.stringify(payload),
  });
}
export function proposeSupplierRestoration(id: string, payload: {
  reason: string; evidence_refs: EvidenceRef[];
}, token: string): Promise<SupplierExclusion> {
  return request(`/supplier-exclusions/${encodeURIComponent(id)}/restore`, {
    method: "POST", headers: headers(token), body: JSON.stringify(payload),
  });
}

/** Register eksklusi (semua pemasok yang sedang/ pernah dieksklusi). */
export function fetchExclusions(token: string): Promise<{ items: SupplierExclusion[]; count: number }> {
  return request(`/supplier-exclusions`, { headers: headers(token) });
}

/** Kapan register eksklusi diambil: hanya saat tab Pemasok terbuka dan token ada.
 *
 *  Dipakai di efek page.tsx supaya pengambilan register TIDAK menumpang efek
 *  sampel (yang punya penjaga "sampel sudah dinilai"): kalau menumpang, membuka
 *  tab Pemasok setelah tab Kualitas Agen membuat register tak pernah diambil.
 */
export function shouldLoadExclusions(tab: string | null | undefined, token: string | null): boolean {
  return Boolean(token) && tab === "suppliers";
}
