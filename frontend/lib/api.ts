// API client MealChain Guardian — kontrak backend aktual (S3-12).
// Tanpa karangan: hanya endpoint yang benar-benar ada di backend.

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request(path: string, init: RequestInit): Promise<any> {
  const resp = await fetch(`${API_URL}${path}`, init);
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}: ${path}`);
  }
  return resp.json();
}

export async function login(email: string, password: string) {
  return request("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export async function fetchDecisions(token: string) {
  return request("/decisions", {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function fetchDecision(decisionId: string, token: string) {
  return request(`/decisions/${decisionId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function fetchDecisionTraces(decisionId: string, token: string) {
  return request(`/decisions/${decisionId}/traces`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function approveAction(
  decisionId: string,
  approved: boolean,
  token: string,
  comment?: string
) {
  return request("/actions/approve", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ decision_id: decisionId, approved, comment }),
  });
}

export async function executeAction(decisionId: string, token: string) {
  return request("/actions/execute", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ decision_id: decisionId }),
  });
}

export async function verifyAction(
  decisionId: string,
  verdict: string,
  token: string
) {
  return request("/actions/verify", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ decision_id: decisionId, verdict }),
  });
}

export async function reproposeAction(decisionId: string, token: string) {
  return request("/actions/repropose", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ decision_id: decisionId }),
  });
}

// /actions/propose — angkat "proposed" → "pending_approval" agar bisa
// di-approve (material_number = candidate_id, jejak sumber tetap jelas).
export async function proposeAction(
  decisionId: string,
  materialNumber: string,
  token: string
) {
  return request("/actions/propose", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      decision_id: decisionId,
      material_number: materialNumber,
    }),
  });
}

export async function fetchDecisionChain(
  decisionId: string,
  token: string
) {
  return request(`/decisions/${decisionId}/chain`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function seedDemo(token: string, force = false) {
  return request("/demo/seed", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ force }),
  });
}

// --- Ops Console (interaksi sebelum hasil — arah Roy 2026-10-07) ---

export async function fetchBalance(
  location: string,
  commodity: string,
  token: string
) {
  return request(`/balance/${location}/${commodity}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function runAnalysis(token: string) {
  return request("/balance/analyze", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

// POST /decisions — snapshot rekomendasi dipersist (status "proposed").
// TTL default 60 menit (agar usulan tidak mati di tengah demo).
export async function createDecision(
  recommendation: any,
  ttlMinutes: number,
  token: string
) {
  return request("/decisions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      recommendation,
      ttl_minutes: ttlMinutes,
      decision_type: "regional_balance",
    }),
  });
}
