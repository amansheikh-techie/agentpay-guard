// components/ApprovalQueue.tsx — Pending approval & in-flight order tracker
import React from 'react';
import type { Proposal, PaymentListItem } from '../types';
import { formatCents, formatDateTime } from '../lib/format';
import { ProductImage } from './ProductImage';

interface ApprovalQueueProps {
  currentProposal: Proposal | null;
  pendingPayments: PaymentListItem[];
  onOpenApproval: (proposal: Proposal) => void;
  onCaptureOrder: (paypalOrderId: string) => void;
  onCancelOrder: (paypalOrderId: string) => void;
  loading?: boolean;
}

export const ApprovalQueue: React.FC<ApprovalQueueProps> = ({
  currentProposal,
  pendingPayments,
  onOpenApproval,
  onCaptureOrder,
  onCancelOrder,
  loading = false,
}) => {
  const needsApproval = currentProposal && currentProposal.policy_decision === 'ALLOWED' && currentProposal.status === 'pending';

  return (
    <div className="approvals-queue-card">
      <div className="card-header">
        <div className="header-title">
          <span className="card-icon">📋</span>
          <div>
            <h3>Approvals & In-Flight Orders</h3>
            <p className="card-subtitle">
              Every purchase requires explicit human consent and server-side verification before settlement.
            </p>
          </div>
        </div>
      </div>

      {/* 1. Proposal Awaiting Consent */}
      {needsApproval && currentProposal.product ? (
        <div className="queue-item highlight">
          <div className="queue-item-badge">Needs Human Review</div>
          <div className="queue-item-main">
            <ProductImage
              productId={currentProposal.product.id}
              name={currentProposal.product.name}
              category={currentProposal.product.category}
              size="md"
            />
            <div className="queue-item-details">
              <h4>{currentProposal.product.name}</h4>
              <p className="queue-meta">
                Merchant: <strong>{currentProposal.product.merchant_name}</strong> • Amount: <strong>{formatCents(currentProposal.product.price_cents)}</strong>
              </p>
              <p className="queue-request">User request: "{currentProposal.user_request}"</p>
            </div>
            <div className="queue-item-actions">
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => onOpenApproval(currentProposal)}
                disabled={loading}
              >
                Review & Authorize →
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {/* 2. In-Flight PayPal Orders */}
      {pendingPayments.length > 0 ? (
        <div className="inflight-section">
          <h4>Active PayPal Orders ({pendingPayments.length})</h4>
          <div className="inflight-list">
            {pendingPayments.map((pay) => (
              <div key={pay.id} className="queue-item">
                <div className="queue-item-main">
                  <div className="queue-item-details">
                    <div className="order-title-row">
                      <strong>{pay.product_name || 'PayPal Order'}</strong>
                      <span className={`status-pill ${pay.status}`}>{pay.status.toUpperCase()}</span>
                    </div>
                    <p className="queue-meta">
                      PayPal Order ID: <code>{pay.paypal_order_id || 'N/A'}</code> • Created: {formatDateTime(pay.created_at)}
                    </p>
                    <p className="queue-amount">Reserved Amount: <strong>{formatCents(pay.amount_cents)}</strong></p>
                  </div>
                  <div className="queue-item-actions">
                    {pay.paypal_order_id && (
                      <>
                        <button
                          type="button"
                          className="btn btn-sm btn-primary"
                          onClick={() => onCaptureOrder(pay.paypal_order_id!)}
                          disabled={loading}
                        >
                          Verify & Capture
                        </button>
                        <button
                          type="button"
                          className="btn btn-sm btn-outline danger-text"
                          onClick={() => onCancelOrder(pay.paypal_order_id!)}
                          disabled={loading}
                        >
                          Cancel
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {!needsApproval && pendingPayments.length === 0 && (
        <div className="empty-queue">
          <span className="empty-icon">✓</span>
          <h4>No Pending Approvals</h4>
          <p>The queue is clear. Switch to the <strong>AI Shopping</strong> tab to run a scenario or request an item.</p>
        </div>
      )}
    </div>
  );
};
