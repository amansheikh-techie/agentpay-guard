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

// ── Policy (Phase 2 & 2.0) ───────────────────────────────────────────────────
export interface Policy {
  id: number;
  total_budget_cents: number;
  max_per_order_cents: number;
  daily_limit_cents?: number;
  monthly_limit_cents?: number;
  currency: string;
  approved_merchant_ids: string[];
  blocked_categories?: string[];
  require_approval: boolean;
  agent_enabled?: boolean;
  policy_version?: number;
  successful_spend_cents: number;
  remaining_budget_cents: number;
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
  category?: string;
  features: string[];
  active: boolean;
}

// ── Proposal / Decision (Phase 3 & 2.0) ───────────────────────────────────────
export type PolicyDecision = 'ALLOWED' | 'BLOCKED';

export interface ExtractedRequirements {
  category?: string | null;
  max_price_cents?: number | null;
  features: string[];
}

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
  block_explanation?: string | null;
  alternatives?: Proposal[];
  extracted_requirements?: ExtractedRequirements | null;
  rank?: number;
  matched_requirements?: string[];
  unmet_requirements?: string[];
  price_difference_cents?: number | null;
  candidates?: Proposal[];
  created_at: string;
}

// ── Payment (Phase 4 & 2.0) ───────────────────────────────────────────────────
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

export interface PaymentListItem {
  id: string;
  proposal_id: string;
  paypal_order_id: string | null;
  amount_cents: number;
  currency: string;
  status: PaymentStatus;
  paypal_capture_id: string | null;
  product_name: string | null;
  merchant_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface MerchantSpendSummary {
  merchant_id: string;
  merchant_name: string;
  total_cents: number;
  order_count: number;
}

export interface SummaryResponse {
  completed_cents: number;
  reserved_cents: number;
  remaining_cents: number;
  daily_spent_cents: number;
  monthly_spent_cents: number;
  blocked_count: number;
  completed_count: number;
  failed_count: number;
  by_merchant: MerchantSpendSummary[];
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
