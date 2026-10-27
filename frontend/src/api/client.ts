// api/client.ts — Typed API fetchers for backend endpoints
// Never puts secrets in requests; all auth stays on the backend.

import type { HealthStatus, Policy, Product, Proposal, AuditEvent } from '../types';

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

// ── Policy ───────────────────────────────────────────────────────────────────
export const fetchPolicy = (): Promise<Policy> => request<Policy>('/policy');

export const updatePolicy = (body: Partial<Policy>): Promise<Policy> =>
  request<Policy>('/policy', { method: 'PUT', body: JSON.stringify(body) });

// ── Products ─────────────────────────────────────────────────────────────────
export const fetchProducts = (): Promise<Product[]> => request<Product[]>('/products');

// ── Agent propose ────────────────────────────────────────────────────────────
export const propose = (userRequest: string): Promise<Proposal> =>
  request<Proposal>('/agent/propose', {
    method: 'POST',
    body: JSON.stringify({ user_request: userRequest }),
  });

// ── Audit ────────────────────────────────────────────────────────────────────
export const fetchAudit = (limit = 20): Promise<AuditEvent[]> =>
  request<AuditEvent[]>(`/audit?limit=${limit}`);

// ── Payments (Phase 4) ───────────────────────────────────────────────────────
export const createOrder = (proposalId: string) =>
  request<{ payment_id: string; paypal_order_id: string; approve_url: string; status: string }>(
    '/payments/create-order',
    {
      method: 'POST',
      body: JSON.stringify({ proposal_id: proposalId, user_approved: true }),
    }
  );

export const captureOrder = (paypalOrderId: string) =>
  request<{ status: string; payment_id: string }>('/payments/capture-order', {
    method: 'POST',
    body: JSON.stringify({ paypal_order_id: paypalOrderId }),
  });

export const cancelOrder = (paypalOrderId: string) =>
  request<{ status: string; payment_id: string }>('/payments/cancel', {
    method: 'POST',
    body: JSON.stringify({ paypal_order_id: paypalOrderId }),
  });
