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
