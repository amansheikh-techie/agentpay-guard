// types/index.ts — shared TypeScript interfaces mirroring backend Pydantic schemas

export interface HealthStatus {
  status: string;
  app_env: string;
  ai_configured: boolean;
  ai_provider: string;
  paypal_configured: boolean;
  paypal_mode: string;
  paypal_currency: string;
  note: string;
}

// ── Policy (Phase 2) ─────────────────────────────────────────────────────────
export interface Policy {
  id: number;
  total_budget_cents: number;
  max_per_order_cents: number;
  currency: string;
  approved_merchant_ids: string[];
  require_approval: boolean;
  successful_spend_cents: number;
  created_at: string;
  updated_at: string;
}

// ── Product (Phase 2) ────────────────────────────────────────────────────────
export interface Product {
  id: string;
  name: string;
  description: string;
  price_cents: number;
  currency: string;
  merchant_id: string;
  merchant_name: string;
  features: string[];
  active: boolean;
}

// ── Proposal / Decision (Phase 3) ────────────────────────────────────────────
export type PolicyDecision = 'ALLOWED' | 'BLOCKED';

export interface Proposal {
  id: string;
  user_request: string;
  selected_product_id: string | null;
  product: Product | null;
  rationale: string;
  status: string;
  policy_decision: PolicyDecision;
  decision_reasons: string[];
  decision_explanations: string[];
  ai_mode: 'live' | 'fallback';
  created_at: string;
}

// ── Payment (Phase 4) ────────────────────────────────────────────────────────
export type PaymentStatus =
  | 'pending'
  | 'approved'
  | 'captured'
  | 'cancelled'
  | 'failed'
  | 'needs_verification';

export interface Payment {
  id: string;
  proposal_id: string;
  paypal_order_id: string;
  amount_cents: number;
  currency: string;
  status: PaymentStatus;
  paypal_capture_id: string | null;
  created_at: string;
  updated_at: string;
}

// ── Audit (Phase 2+) ─────────────────────────────────────────────────────────
export interface AuditEvent {
  id: number;
  event_type: string;
  proposal_id: string | null;
  payment_id: string | null;
  details: Record<string, unknown>;
  created_at: string;
}
