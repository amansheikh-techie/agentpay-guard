// components/DecisionCard.tsx — Displays AI proposal, authoritative product details, and policy verdict
import { ClipboardList, ShieldX, ShieldCheck, Tag, Store, Info, Lock } from 'lucide-react';
import type { Proposal } from '../types';

interface Props {
  proposal: Proposal | null;
}

export default function DecisionCard({ proposal }: Props) {
  if (!proposal) {
    return (
      <div className="card">
        <div className="card-header">
          <div className="card-icon">
            <ClipboardList size={18} />
          </div>
          <h2>Policy Decision</h2>
        </div>
        <div className="decision-empty">
          <div className="decision-empty-icon">🛡️</div>
          <p style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>
            No active proposal
          </p>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', maxWidth: '320px', margin: '0 auto' }}>
            Submit a shopping request on the left to see the AI agent recommendation and deterministic policy decision.
          </p>
        </div>
      </div>
    );
  }

  const isAllowed = proposal.policy_decision === 'ALLOWED';
  const product = proposal.product;
  const priceFormatted = product ? `$${(product.price_cents / 100).toFixed(2)}` : '—';

  return (
    <div className="card">
      <div className="card-header" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
          <div className="card-icon">
            <ClipboardList size={18} />
          </div>
          <h2>Policy Decision &amp; Proposal</h2>
        </div>
        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
          {proposal.id}
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {/* AI Mode badge */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.5rem 0.75rem', background: 'var(--bg-input)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
            Recommendation Engine:
          </span>
          {proposal.ai_mode === 'fallback' ? (
            <span style={{ fontSize: '0.72rem', padding: '0.2rem 0.5rem', borderRadius: '4px', background: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
              <Info size={12} />
              Demo Fallback Mode (Deterministic Keyword Matcher)
            </span>
          ) : (
            <span style={{ fontSize: '0.72rem', padding: '0.2rem 0.5rem', borderRadius: '4px', background: 'rgba(14, 165, 233, 0.15)', color: 'var(--primary)', fontWeight: 600 }}>
              🤖 Live AI Model Recommendation
            </span>
          )}
        </div>

        {/* AI Rationale */}
        <div style={{ fontSize: '0.82rem', background: 'var(--bg-surface)', padding: '0.75rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
          <div style={{ fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>
            Agent Rationale:
          </div>
          <div style={{ color: 'var(--text-muted)', lineHeight: 1.45 }}>
            {proposal.rationale}
          </div>
        </div>

        {/* Authoritative Product Card */}
        {product ? (
          <div style={{ padding: '0.875rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)', background: 'var(--bg-input)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '0.5rem' }}>
              <div>
                <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                  {product.name}
                </h3>
                <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '0.25rem', marginBottom: '0.5rem' }}>
                  {product.description}
                </p>
              </div>
              <div style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                <div style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--accent)' }}>
                  {priceFormatted}
                </div>
                <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
                  Authoritative Price
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', marginTop: '0.5rem', paddingTop: '0.5rem', borderTop: '1px solid var(--border-subtle)', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
              <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                <Store size={13} color="var(--primary)" />
                <span>Merchant: <strong>{product.merchant_name}</strong> ({product.merchant_id})</span>
              </div>
              <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                <Tag size={13} color="var(--primary)" />
                <span>Product ID: <code>{product.id}</code></span>
              </div>
            </div>

            {product.features && product.features.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem', marginTop: '0.5rem' }}>
                {product.features.map((feat, idx) => (
                  <span key={idx} style={{ fontSize: '0.7rem', padding: '0.15rem 0.4rem', borderRadius: '4px', background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
                    {feat}
                  </span>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div style={{ padding: '0.75rem', background: 'rgba(239,68,68,0.1)', borderRadius: 'var(--radius-md)', color: 'var(--danger)', fontSize: '0.8rem' }}>
            Product could not be resolved from authoritative catalogue.
          </div>
        )}

        {/* Policy Decision Banner */}
        {isAllowed ? (
          <div style={{ border: '1px solid rgba(52, 211, 153, 0.4)', borderRadius: 'var(--radius-md)', padding: '1rem', background: 'rgba(52, 211, 153, 0.08)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem' }}>
              <ShieldCheck size={22} color="var(--success)" />
              <span style={{ fontWeight: 800, color: 'var(--success)', fontSize: '1rem', letterSpacing: '0.04em' }}>
                ALLOWED BY POLICY
              </span>
            </div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: 0 }}>
              All policy checks passed: within per-order cap, merchant is allowlisted, and sufficient budget remains.
            </p>
            <div style={{ marginTop: '0.75rem', padding: '0.5rem 0.75rem', background: 'rgba(52, 211, 153, 0.12)', borderRadius: 'var(--radius-sm)', display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.75rem', color: 'var(--text-primary)' }}>
              <Lock size={14} color="var(--success)" />
              <span>
                <strong>Next Step (Phase 4)</strong>: Explicit user approval is required before initiating PayPal Sandbox checkout.
              </span>
            </div>
          </div>
        ) : (
          <div style={{ border: '1px solid rgba(248, 113, 113, 0.4)', borderRadius: 'var(--radius-md)', padding: '1rem', background: 'rgba(248, 113, 113, 0.08)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem' }}>
              <ShieldX size={22} color="var(--danger)" />
              <span style={{ fontWeight: 800, color: 'var(--danger)', fontSize: '1rem', letterSpacing: '0.04em' }}>
                BLOCKED BY POLICY ENGINE
              </span>
            </div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
              This purchase was blocked by deterministic backend policy enforcement:
            </p>

            {/* Reason codes */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem', marginBottom: '0.625rem' }}>
              {proposal.decision_reasons.map((r, i) => (
                <span key={i} style={{ fontSize: '0.72rem', fontWeight: 700, padding: '0.2rem 0.45rem', borderRadius: '4px', background: 'rgba(239, 68, 68, 0.2)', color: 'var(--danger)', fontFamily: 'monospace' }}>
                  {r}
                </span>
              ))}
            </div>

            {/* Explanations list */}
            <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.78rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
              {proposal.decision_explanations.map((exp, i) => (
                <li key={i}>{exp}</li>
              ))}
            </ul>

            <div style={{ marginTop: '0.75rem', fontSize: '0.72rem', color: 'var(--text-muted)' }}>
              ⛔ <strong>Enforcement Guarantee</strong>: Payment creation is strictly forbidden for blocked proposals.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
