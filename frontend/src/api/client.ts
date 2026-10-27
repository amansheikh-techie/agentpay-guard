// api/client.ts — Typed API fetchers for backend endpoints
// Never puts secrets in requests; all auth stays on the backend.

import type { HealthStatus } from '../types';

const BASE = '/api'; // proxied to http://localhost:8000 by Vite dev server

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });

  if (!res.ok) {
    let message = `Request failed: ${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      // Never leak stack traces or internal error details
      message = body?.detail ?? body?.message ?? message;
    } catch {
      // ignore parse errors
    }
    throw new Error(message);
  }

  return res.json() as Promise<T>;
}

// ── Health ────────────────────────────────────────────────────────────────────
export const fetchHealth = (): Promise<HealthStatus> => request<HealthStatus>('/health');

// ── Policy (Phase 2) ─────────────────────────────────────────────────────────
// export const fetchPolicy = () => request<Policy>('/policy');
// export const updatePolicy = (body: Partial<Policy>) =>
//   request<Policy>('/policy', { method: 'PUT', body: JSON.stringify(body) });

// ── Products (Phase 2) ───────────────────────────────────────────────────────
// export const fetchProducts = () => request<Product[]>('/products');

// ── Agent propose (Phase 3) ──────────────────────────────────────────────────
// export const propose = (userRequest: string) =>
//   request<Proposal>('/agent/propose', {
//     method: 'POST',
//     body: JSON.stringify({ user_request: userRequest }),
//   });

// ── Payments (Phase 4) ───────────────────────────────────────────────────────
// export const createOrder = (proposalId: string) =>
//   request<{ paypal_order_id: string }>('/payments/create-order', {
//     method: 'POST',
//     body: JSON.stringify({ proposal_id: proposalId }),
//   });

// export const captureOrder = (paypalOrderId: string) =>
//   request<Payment>('/payments/capture-order', {
//     method: 'POST',
//     body: JSON.stringify({ paypal_order_id: paypalOrderId }),
//   });

// ── Audit (Phase 2) ──────────────────────────────────────────────────────────
// export const fetchAudit = () => request<AuditEvent[]>('/audit');
