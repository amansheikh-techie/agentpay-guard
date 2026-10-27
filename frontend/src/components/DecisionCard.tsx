// components/DecisionCard.tsx — Displays AI proposal, authoritative product details, policy verdict & PayPal Sandbox checkout
import { useState } from 'react';
import {
  ClipboardList,
  ShieldX,
  ShieldCheck,
  Tag,
  Store,
  Info,
  Lock,
  ExternalLink,
  AlertCircle,
  CheckCircle2,
  CreditCard,
} from 'lucide-react';
import type { Proposal } from '../types';
import { createOrder, captureOrder } from '../api/client';

interface Props {
  proposal: Proposal | null;
  onPaymentSuccess?: () => void;
}

export default function DecisionCard({ proposal, onPaymentSuccess }: Props) {
  const [creatingOrder, setCreatingOrder] = useState(false);
  const [orderError, setOrderError] = useState<string | null>(null);
  const [createdOrder, setCreatedOrder] = useState<{
    payment_id: string;
    paypal_order_id: string;
    approve_url: string;
  } | null>(null);
  const [capturing, setCapturing] = useState(false);
  const [captureSuccess, setCaptureSuccess] = useState<string | null>(null);

  if (!proposal) {
    return (
      <div className="card">
        <div className="card-header">
          <div className="card-icon">
            <ClipboardList size={18} />
          </div>
          <h2>Policy Decision &amp; Proposal</h2>
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

  const handleApproveAndPay = async () => {
    if (!proposal || !isAllowed || creatingOrder) return;
    setCreatingOrder(true);
    setOrderError(null);
    setCreatedOrder(null);
    setCaptureSuccess(null);

    try {
      const order = await createOrder(proposal.id);
      setCreatedOrder(order);
    } catch (err) {
      setOrderError((err as Error).message || 'Failed to create PayPal order.');
    } finally {
      setCreatingOrder(false);
    }
  };

  const handleCapture = async (paypalOrderId: string) => {
    setCapturing(true);
    setOrderError(null);
    try {
      const result = await captureOrder(paypalOrderId);
      setCaptureSuccess(`Payment verified and captured successfully! Capture status: ${result.status}`);
      if (onPaymentSuccess) {
        onPaymentSuccess();
      }
    } catch (err) {
      setOrderError((err as Error).message || 'Failed to capture PayPal order.');
    } finally {
      setCapturing(false);
    }
  };

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
                <strong>Mandatory Approval Gate</strong>: Requires explicit user action before creating a PayPal Sandbox order.
              </span>
            </div>

            {/* Error banner if order creation fails */}
            {orderError && (
              <div style={{ marginTop: '0.75rem', display: 'flex', alignItems: 'flex-start', gap: '0.5rem', padding: '0.625rem', background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 'var(--radius-md)', color: 'var(--danger)', fontSize: '0.78rem' }}>
                <AlertCircle size={15} style={{ flexShrink: 0, marginTop: '2px' }} />
                <div>
                  <div style={{ fontWeight: 600 }}>Checkout Notice:</div>
                  <div>{orderError}</div>
                </div>
              </div>
            )}

            {/* Success banner if capture completed */}
            {captureSuccess && (
              <div style={{ marginTop: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.625rem', background: 'rgba(52,211,153,0.15)', border: '1px solid rgba(52,211,153,0.3)', borderRadius: 'var(--radius-md)', color: 'var(--success)', fontSize: '0.8rem' }}>
                <CheckCircle2 size={16} />
                <span>{captureSuccess}</span>
              </div>
            )}

            {/* PayPal Sandbox Checkout Action Area */}
            {!createdOrder ? (
              <div style={{ marginTop: '1rem' }}>
                <button
                  id="approve-paypal-btn"
                  type="button"
                  className="btn btn-primary btn-full btn-lg"
                  onClick={handleApproveAndPay}
                  disabled={creatingOrder}
                  style={{ gap: '0.5rem' }}
                >
                  <CreditCard size={18} />
                  {creatingOrder ? 'Creating Sandbox Order…' : `Explicitly Approve & Pay ${priceFormatted}`}
                </button>
                <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textAlign: 'center', marginTop: '0.4rem' }}>
                  PayPal Sandbox test transaction only. No real money will be charged.
                </p>
              </div>
            ) : (
              <div style={{ marginTop: '1rem', padding: '0.875rem', background: 'var(--bg-surface)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                    PayPal Sandbox Order:
                  </span>
                  <code style={{ fontSize: '0.75rem', color: 'var(--primary)' }}>
                    {createdOrder.paypal_order_id}
                  </code>
                </div>

                {createdOrder.approve_url && (
                  <a
                    href={createdOrder.approve_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn btn-primary btn-full"
                    style={{ gap: '0.4rem' }}
                  >
                    <ExternalLink size={15} />
                    Complete Buyer Approval in PayPal Sandbox ↗
                  </a>
                )}

                <div style={{ borderTop: '1px dashed var(--border-subtle)', paddingTop: '0.625rem' }}>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm btn-full"
                    onClick={() => handleCapture(createdOrder.paypal_order_id)}
                    disabled={capturing}
                    style={{ border: '1px solid var(--border-subtle)', fontSize: '0.78rem' }}
                  >
                    {capturing ? 'Verifying & Capturing…' : 'Verify & Capture Sandbox Payment on Backend'}
                  </button>
                  <p style={{ fontSize: '0.68rem', color: 'var(--text-muted)', textAlign: 'center', marginTop: '0.3rem' }}>
                    Capture strictly checks server status. Never marks success from frontend redirects alone.
                  </p>
                </div>
              </div>
            )}
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

            <div style={{ marginTop: '0.875rem', padding: '0.5rem 0.75rem', background: 'rgba(239, 68, 68, 0.12)', borderRadius: 'var(--radius-sm)', fontSize: '0.75rem', color: 'var(--danger)', fontWeight: 600 }}>
              ⛔ Checkout Disabled: The backend strictly forbids creating a PayPal order for a blocked proposal.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
