// components/OverviewTab.tsx — Mission Control Dashboard Tab
import React from 'react';
import type { Policy, SummaryResponse } from '../types';
import { formatCents } from '../lib/format';
import { SpendBar } from './SpendBar';

interface OverviewTabProps {
  policy: Policy | null;
  summary: SummaryResponse | null;
  onNavigateToShopping: () => void;
  onNavigateToPermissions: () => void;
}

export const OverviewTab: React.FC<OverviewTabProps> = ({
  policy,
  summary,
  onNavigateToShopping,
  onNavigateToPermissions,
}) => {
  const totalBudgetCents = policy?.total_budget_cents || 10000;
  const completedCents = summary?.completed_cents ?? (policy?.successful_spend_cents || 0);
  const reservedCents = summary?.reserved_cents || 0;
  const remainingCents = summary?.remaining_cents ?? (policy?.remaining_budget_cents || 0);

  return (
    <div className="overview-tab">
      {/* 1. Spend Visualization Bar */}
      <div className="overview-hero card">
        <SpendBar
          totalBudgetCents={totalBudgetCents}
          completedCents={completedCents}
          reservedCents={reservedCents}
        />
      </div>

      {/* 2. Key Metric Cards */}
      <div className="metric-cards-grid">
        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-icon">💰</span>
            <span className="metric-title">Available Budget</span>
          </div>
          <div className="metric-value highlight-green">{formatCents(remainingCents)}</div>
          <span className="metric-sub">Out of {formatCents(totalBudgetCents)} total budget</span>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-icon">📅</span>
            <span className="metric-title">Daily Spend (Today)</span>
          </div>
          <div className="metric-value">{formatCents(summary?.daily_spent_cents || 0)}</div>
          <span className="metric-sub">
            {policy?.daily_limit_cents && policy.daily_limit_cents > 0
              ? `Limit: ${formatCents(policy.daily_limit_cents)}`
              : 'No daily limit set'}
          </span>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-icon">🛡️</span>
            <span className="metric-title">Violations Intercepted</span>
          </div>
          <div className="metric-value highlight-amber">{summary?.blocked_count || 0}</div>
          <span className="metric-sub">Out-of-policy purchases prevented</span>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-icon">📦</span>
            <span className="metric-title">Completed Purchases</span>
          </div>
          <div className="metric-value">{summary?.completed_count || 0}</div>
          <span className="metric-sub">PayPal Sandbox captures verified</span>
        </div>
      </div>

      {/* 3. Active Policy Limits & Spend by Merchant */}
      <div className="overview-two-col">
        {/* Active Policy Rules Card */}
        <div className="card active-guardrails-card">
          <div className="card-header">
            <h4>Active Guardrails Summary</h4>
            <button
              type="button"
              className="btn btn-sm btn-outline"
              onClick={onNavigateToPermissions}
            >
              Configure →
            </button>
          </div>

          <div className="guardrail-rows">
            <div className="guardrail-row">
              <span className="g-label">Agent Status:</span>
              <span className={`g-val ${policy?.agent_enabled !== false ? 'success-text' : 'danger-text'}`}>
                {policy?.agent_enabled !== false ? '● ACTIVE (Enabled)' : '● DISABLED (Kill-switch ON)'}
              </span>
            </div>
            <div className="guardrail-row">
              <span className="g-label">Per-Order Cap:</span>
              <span className="g-val font-mono">{formatCents(policy?.max_per_order_cents || 4000)} max</span>
            </div>
            <div className="guardrail-row">
              <span className="g-label">Human Consent Gate:</span>
              <span className="g-val">
                {policy?.require_approval ? 'Required before checkout' : 'Bypassed'}
              </span>
            </div>
            <div className="guardrail-row">
              <span className="g-label">Approved Merchants:</span>
              <div className="chips-list">
                {policy?.approved_merchant_ids && policy.approved_merchant_ids.length > 0 ? (
                  policy.approved_merchant_ids.map((m) => (
                    <span key={m} className="tag-chip merchant-tag">✓ {m}</span>
                  ))
                ) : (
                  <span className="muted">None approved</span>
                )}
              </div>
            </div>
            <div className="guardrail-row">
              <span className="g-label">Blocked Categories:</span>
              <div className="chips-list">
                {policy?.blocked_categories && policy.blocked_categories.length > 0 ? (
                  policy.blocked_categories.map((c) => (
                    <span key={c} className="tag-chip blocked-cat-tag">🚫 {c}</span>
                  ))
                ) : (
                  <span className="muted">None (all categories allowed)</span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Spend by Merchant Card */}
        <div className="card merchant-spend-card">
          <div className="card-header">
            <h4>Spend Breakdown by Merchant</h4>
          </div>

          <div className="merchant-spend-list">
            {summary?.by_merchant && summary.by_merchant.length > 0 ? (
              summary.by_merchant.map((m) => (
                <div key={m.merchant_id} className="merchant-spend-row">
                  <div className="m-info">
                    <strong>{m.merchant_name}</strong>
                    <span className="m-orders">{m.order_count} {m.order_count === 1 ? 'order' : 'orders'}</span>
                  </div>
                  <div className="m-amount font-mono">
                    {formatCents(m.total_cents)}
                  </div>
                </div>
              ))
            ) : (
              <div className="empty-state-card">
                <p>No settled merchant payments yet.</p>
                <button
                  type="button"
                  className="btn btn-sm btn-primary"
                  onClick={onNavigateToShopping}
                >
                  Propose First Purchase →
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
