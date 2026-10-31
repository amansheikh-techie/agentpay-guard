// components/DecisionCard.tsx — Displays AI proposal, authoritative product details, policy verdict & PayPal Sandbox checkout
import { useState, useEffect } from 'react';
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
  onSelectAlternative?: (alt: Proposal) => void;
}

export default function DecisionCard({ proposal: initialProposal, onPaymentSuccess, onSelectAlternative }: Props) {
  const [currentProposal, setCurrentProposal] = useState<Proposal | null>(initialProposal);
  const [creatingOrder, setCreatingOrder] = useState(false);
  const [orderError, setOrderError] = useState<string | null>(null);
  const [createdOrder, setCreatedOrder] = useState<{
    payment_id: string;
    paypal_order_id: string;
    approve_url: string;
  } | null>(null);
  const [buyerApproved, setBuyerApproved] = useState(false);
  const [capturing, setCapturing] = useState(false);
  const [captureSuccess, setCaptureSuccess] = useState<string | null>(null);

  useEffect(() => {
    setCurrentProposal(initialProposal);
    setCreatedOrder(null);
    setOrderError(null);
    setCaptureSuccess(null);
  }, [initialProposal]);

  const proposal = currentProposal;

  // On mount or when the page regains focus, check URL params for PayPal
  // return. PayPal redirects back with ?payment_status=approved&payment_id=...
  // after the buyer completes the approval flow.
  useEffect(() => {
    const checkPayPalReturn = () => {
      const params = new URLSearchParams(window.location.search);
      const paymentStatus = params.get('payment_status');
      if (paymentStatus === 'approved') {
        setBuyerApproved(true);
        // Clean up the URL without reload
        const url = new URL(window.location.href);
        url.searchParams.delete('payment_status');
        url.searchParams.delete('payment_id');
        window.history.replaceState({}, '', url.pathname);
      }
    };

    checkPayPalReturn();

    // Also recheck when the window regains focus (buyer returns from PayPal tab)
    const handleFocus = () => checkPayPalReturn();
    window.addEventListener('focus', handleFocus);
    return () => window.removeEventListener('focus', handleFocus);
  }, []);

  if (!proposal) {
    return (
      <div className="card">
        <div className="card-header">
          <div className="card-icon">
            <ClipboardList size={18} />
          </div>
          <h2>Policy Decision &amp; Proposal</h2>
        </div>
        <div className="decision-empty" style={{ padding: '3.5rem 1.5rem', textAlign: 'center' }}>
          <div className="decision-empty-icon" style={{ fontSize: '3rem', marginBottom: '0.5rem', opacity: 0.85 }}>🛡️</div>
          <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '0.35rem' }}>
            No Active Shopping Proposal
          </h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', maxWidth: '340px', margin: '0 auto', lineHeight: 1.5 }}>
            Pick a demo scenario on the left or enter a custom request to trigger the AI shopping agent and deterministic policy guardrails.
          </p>
        </div>
      </div>
    );
  }

  const isAllowed = proposal.policy_decision === 'ALLOWED';
  const product = proposal.product;
  const priceFormatted = product ? `$${(product.price_cents / 100).toFixed(2)} ${product.currency}` : '—';

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

  const handleChooseAlternative = (alt: Proposal) => {
    setCurrentProposal(alt);
    setCreatedOrder(null);
    setOrderError(null);
    setCaptureSuccess(null);
    if (onSelectAlternative) {
      onSelectAlternative(alt);
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
        <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', fontFamily: 'monospace' }}>
          {proposal.id}
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', width: '100%', minWidth: 0 }}>
        {/* AI Mode badge */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.5rem 0.75rem', background: 'var(--bg-input)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)', flexWrap: 'wrap', gap: '0.5rem' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
            Recommendation Engine:
          </span>
          {proposal.ai_mode === 'fallback' ? (
            <span style={{ fontSize: '0.72rem', padding: '0.2rem 0.5rem', borderRadius: '4px', background: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
              <Info size={12} />
              Demo Fallback Mode (Deterministic Keyword Matcher)
            </span>
          ) : (
            <span style={{ fontSize: '0.72rem', padding: '0.2rem 0.5rem', borderRadius: '4px', background: 'rgba(45, 212, 191, 0.15)', color: 'var(--accent)', fontWeight: 600 }}>
              🤖 Live AI Model Recommendation
            </span>
          )}
        </div>

        {/* AI Rationale */}
        <div style={{ fontSize: '0.82rem', background: 'var(--bg-surface)', padding: '0.75rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)', width: '100%', minWidth: 0 }}>
          <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.25rem' }}>
            Agent Rationale:
          </div>
          <div style={{ color: 'var(--text-secondary)', lineHeight: 1.45 }}>
            {proposal.rationale}
          </div>
        </div>

        {/* Authoritative Product Card */}
        {product ? (
          <div style={{ padding: '0.875rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)', background: 'var(--bg-input)', width: '100%', minWidth: 0 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '0.5rem' }}>
              <div style={{ minWidth: 0 }}>
                <h3 style={{ fontSize: '0.98rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                  {product.name}
                </h3>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '0.25rem', marginBottom: '0.5rem', lineHeight: 1.4 }}>
                  {product.description}
                </p>
              </div>
              <div style={{ textAlign: 'right', whiteSpace: 'nowrap', flexShrink: 0 }}>
                <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--accent)' }}>
                  {priceFormatted}
                </div>
                <div style={{ fontSize: '0.68rem', color: 'var(--text-secondary)' }}>
                  Authoritative Price
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', marginTop: '0.5rem', paddingTop: '0.5rem', borderTop: '1px solid var(--border-subtle)', fontSize: '0.76rem', color: 'var(--text-secondary)' }}>
              <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                <Store size={13} color="var(--accent)" />
                <span>Merchant: <strong style={{ color: 'var(--text-primary)' }}>{product.merchant_name}</strong> ({product.merchant_id})</span>
              </div>
              <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                <Tag size={13} color="var(--accent)" />
                <span>Product ID: <code>{product.id}</code></span>
              </div>
            </div>

            {product.features && product.features.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem', marginTop: '0.5rem' }}>
                {product.features.map((feat, idx) => (
                  <span key={idx} style={{ fontSize: '0.7rem', padding: '0.15rem 0.4rem', borderRadius: '4px', background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', color: 'var(--text-secondary)' }}>
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
          <div style={{ border: '2px solid rgba(52, 211, 153, 0.5)', borderRadius: 'var(--radius-lg)', padding: '1.25rem', background: 'rgba(52, 211, 153, 0.08)', boxShadow: '0 0 20px rgba(52, 211, 153, 0.08)', width: '100%', minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
                <ShieldCheck size={26} color="var(--success)" />
                <span style={{ fontWeight: 800, color: 'var(--success)', fontSize: '1.1rem', letterSpacing: '0.04em' }}>
                  ALLOWED BY POLICY
                </span>
              </div>
              <span className="badge badge-success" style={{ fontSize: '0.75rem', padding: '0.25rem 0.65rem' }}>
                ✓ PASSED ALL CHECKS
              </span>
            </div>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.45 }}>
              All policy checks passed: within per-order cap, merchant is allowlisted, and sufficient budget remains.
            </p>

            <div style={{ marginTop: '0.875rem', padding: '0.6rem 0.85rem', background: 'rgba(52, 211, 153, 0.12)', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.78rem', color: 'var(--text-primary)' }}>
              <Lock size={15} color="var(--success)" style={{ flexShrink: 0 }} />
              <span>
                <strong>Mandatory Approval Gate</strong>: Autonomous spending is strictly blocked. Requires explicit user action before creating a PayPal Sandbox order.
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

            {/* PayPal Sandbox Checkout Action Area — Primary CTA visually strongest */}
            {!createdOrder ? (
              <div style={{ marginTop: '1.25rem' }}>
                <button
                  id="approve-paypal-btn"
                  type="button"
                  className="btn btn-primary btn-full btn-lg"
                  onClick={handleApproveAndPay}
                  disabled={creatingOrder}
                  style={{
                    gap: '0.625rem',
                    fontSize: '1.05rem',
                    fontWeight: 700,
                    padding: '0.875rem 1.5rem',
                    boxShadow: '0 4px 20px rgba(45, 212, 191, 0.35)',
                    letterSpacing: '-0.01em',
                  }}
                >
                  <CreditCard size={20} />
                  {creatingOrder ? 'Creating Sandbox Order…' : `Explicitly Approve & Pay ${priceFormatted}`}
                </button>
                <p style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', textAlign: 'center', marginTop: '0.5rem' }}>
                  PayPal Sandbox test transaction only. No real money will be charged.
                </p>
              </div>
            ) : (
              <div style={{ marginTop: '1rem', padding: '0.875rem', background: 'var(--bg-surface)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
                  <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                    PayPal Sandbox Order:
                  </span>
                  <code style={{ fontSize: '0.75rem', color: 'var(--accent)' }}>
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
                  {!buyerApproved ? (
                    <div style={{
                      display: 'flex', alignItems: 'center', gap: '0.4rem',
                      padding: '0.5rem 0.75rem', marginBottom: '0.5rem',
                      background: 'rgba(245, 158, 11, 0.12)', border: '1px solid rgba(245, 158, 11, 0.3)',
                      borderRadius: 'var(--radius-sm)', fontSize: '0.75rem', color: '#fbbf24',
                    }}>
                      <AlertCircle size={14} style={{ flexShrink: 0 }} />
                      <span>
                        <strong>Step 1:</strong> Click the link above to approve payment in PayPal Sandbox.
                        <strong> Step 2:</strong> After approval, return here and click Capture below.
                      </span>
                    </div>
                  ) : (
                    <div style={{
                      display: 'flex', alignItems: 'center', gap: '0.4rem',
                      padding: '0.5rem 0.75rem', marginBottom: '0.5rem',
                      background: 'rgba(52, 211, 153, 0.15)', border: '1px solid rgba(52, 211, 153, 0.35)',
                      borderRadius: 'var(--radius-sm)', fontSize: '0.75rem', color: 'var(--success)',
                    }}>
                      <CheckCircle2 size={14} style={{ flexShrink: 0 }} />
                      <span>
                        <strong>Buyer Approval Detected!</strong> Click &ldquo;Verify &amp; Capture&rdquo; below to complete the transaction on the backend.
                      </span>
                    </div>
                  )}
                  <button
                    type="button"
                    className={`btn ${buyerApproved ? 'btn-primary' : 'btn-ghost'} btn-sm btn-full`}
                    onClick={() => handleCapture(createdOrder.paypal_order_id)}
                    disabled={capturing}
                    style={{ fontSize: '0.82rem', padding: '0.6rem 1rem' }}
                  >
                    {capturing ? (
                      <>
                        <span className="spinner" />
                        <span>Verifying &amp; Capturing on Backend…</span>
                      </>
                    ) : (
                      'Verify & Capture Sandbox Payment on Backend'
                    )}
                  </button>
                  <p style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', textAlign: 'center', marginTop: '0.35rem' }}>
                    Capture strictly checks server status. Never marks success from frontend redirects alone.
                  </p>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div style={{ border: '2px solid rgba(248, 113, 113, 0.5)', borderRadius: 'var(--radius-lg)', padding: '1.25rem', background: 'rgba(248, 113, 113, 0.08)', boxShadow: '0 0 20px rgba(248, 113, 113, 0.08)', width: '100%', minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
                <ShieldX size={26} color="var(--danger)" />
                <span style={{ fontWeight: 800, color: 'var(--danger)', fontSize: '1.1rem', letterSpacing: '0.04em' }}>
                  BLOCKED BY POLICY ENGINE
                </span>
              </div>
              <span className="badge badge-danger" style={{ fontSize: '0.75rem', padding: '0.25rem 0.65rem' }}>
                ⛔ POLICY VIOLATION
              </span>
            </div>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.75rem', lineHeight: 1.45 }}>
              This purchase was blocked by deterministic backend policy enforcement:
            </p>

            {/* Reason codes — Prominent readable chips */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.45rem', marginBottom: '0.75rem' }}>
              {proposal.decision_reasons.map((r, i) => (
                <span key={i} className="reason-chip">
                  {r}
                </span>
              ))}
            </div>

            {/* Explanations list */}
            <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.82rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
              {proposal.decision_explanations.map((exp, i) => (
                <li key={i}>{exp}</li>
              ))}
            </ul>

            <div style={{ marginTop: '0.875rem', padding: '0.6rem 0.85rem', background: 'rgba(239, 68, 68, 0.12)', borderRadius: 'var(--radius-md)', fontSize: '0.78rem', color: 'var(--danger)', fontWeight: 600 }}>
              ⛔ Checkout Disabled: The backend strictly forbids creating a PayPal order for a blocked proposal.
            </div>

            {/* Plain-English block explanation */}
            {proposal.block_explanation && (
              <div style={{
                marginTop: '0.875rem',
                padding: '0.75rem 0.85rem',
                borderRadius: 'var(--radius-md)',
                background: 'var(--bg-input)',
                border: '1px solid var(--border-subtle)',
                fontSize: '0.82rem',
                color: 'var(--text-secondary)',
                lineHeight: 1.45,
              }}>
                <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.25rem' }}>
                  Why this was blocked:
                </div>
                <div>{proposal.block_explanation}</div>
              </div>
            )}

            {/* Smart Alternatives — Clear cards */}
            {proposal.alternatives && proposal.alternatives.length > 0 && (
              <div style={{ marginTop: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                  <ShieldCheck size={20} color="var(--success)" />
                  <span style={{ fontSize: '0.92rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                    Agent suggests these within policy:
                  </span>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {proposal.alternatives.map((alt) => {
                    const altProd = alt.product;
                    const altPriceFormatted = altProd
                      ? `$${(altProd.price_cents / 100).toFixed(2)} ${altProd.currency}`
                      : '—';

                    return (
                      <div key={alt.id} className="alt-card">
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '0.75rem' }}>
                          <div style={{ minWidth: 0 }}>
                            <div style={{ fontSize: '0.92rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                              {altProd ? altProd.name : alt.selected_product_id}
                            </div>
                            <div style={{ fontSize: '0.76rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
                              Merchant: <strong style={{ color: 'var(--text-primary)' }}>{altProd?.merchant_name || 'Approved'}</strong> <span style={{ color: 'var(--text-muted)' }}>({altProd?.merchant_id})</span>
                            </div>
                          </div>
                          <div style={{ textAlign: 'right', whiteSpace: 'nowrap', flexShrink: 0 }}>
                            <div style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--accent)' }}>
                              {altPriceFormatted}
                            </div>
                            <span className="badge badge-success" style={{ fontSize: '0.68rem', padding: '0.15rem 0.45rem', marginTop: '0.2rem' }}>
                              IN POLICY
                            </span>
                          </div>
                        </div>

                        {alt.rationale && (
                          <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', fontStyle: 'italic', marginTop: '0.15rem', lineHeight: 1.4 }}>
                            &ldquo;{alt.rationale}&rdquo;
                          </div>
                        )}

                        <div style={{ marginTop: '0.35rem', paddingTop: '0.5rem', borderTop: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'flex-end' }}>
                          <button
                            type="button"
                            className="btn btn-primary btn-sm"
                            onClick={() => handleChooseAlternative(alt)}
                            style={{ fontSize: '0.8rem', gap: '0.4rem', padding: '0.4rem 0.85rem' }}
                          >
                            Review this instead →
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
