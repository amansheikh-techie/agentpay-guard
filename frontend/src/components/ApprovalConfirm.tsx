// components/ApprovalConfirm.tsx — Explicit human approval binding modal
import React from 'react';
import type { Proposal } from '../types';
import { formatCents } from '../lib/format';
import { ProductImage } from './ProductImage';

interface ApprovalConfirmProps {
  proposal: Proposal;
  isOpen: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  loading?: boolean;
}

export const ApprovalConfirm: React.FC<ApprovalConfirmProps> = ({
  proposal,
  isOpen,
  onConfirm,
  onCancel,
  loading = false,
}) => {
  if (!isOpen) return null;

  const product = proposal.product;
  if (!product) return null;

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title-row">
            <span className="modal-icon">🛡️</span>
            <h3>Explicit Human Approval Required</h3>
          </div>
          <button className="modal-close-btn" onClick={onCancel} disabled={loading}>
            ✕
          </button>
        </div>

        <div className="modal-body">
          <p className="modal-intro">
            AgentPay Guard will strictly bind this payment to the following verified catalogue item.
            The backend guarantees the price cannot be changed in transit.
          </p>

          <div className="binding-card">
            <div className="binding-header">
              <ProductImage
                productId={product.id}
                name={product.name}
                category={product.category}
                size="md"
              />
              <div className="binding-info">
                <h4>{product.name}</h4>
                <div className="binding-meta">
                  <span className="meta-badge">{product.merchant_name}</span>
                  {product.category && (
                    <span className="meta-badge category">{product.category}</span>
                  )}
                </div>
              </div>
            </div>

            <div className="binding-specs">
              <div className="spec-row">
                <span className="spec-label">Authoritative Price:</span>
                <span className="spec-val price-val">{formatCents(product.price_cents)}</span>
              </div>
              <div className="spec-row">
                <span className="spec-label">Currency:</span>
                <span className="spec-val">{product.currency}</span>
              </div>
              <div className="spec-row">
                <span className="spec-label">Proposal ID:</span>
                <span className="spec-val code-val">{proposal.id}</span>
              </div>
              <div className="spec-row">
                <span className="spec-label">Trust Verification:</span>
                <span className="spec-val pass-val">✓ Policy Pre-Checked ALLOWED</span>
              </div>
            </div>
          </div>

          <div className="security-notice">
            <span>🔒</span>
            <span>
              Clicking <strong>Authorize Checkout</strong> creates a PayPal Sandbox order and reserves this amount against your budget.
            </span>
          </div>
        </div>

        <div className="modal-footer">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onCancel}
            disabled={loading}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-primary authorize-btn"
            onClick={onConfirm}
            disabled={loading}
          >
            {loading ? (
              <>
                <span className="spinner" />
                <span>Creating Order...</span>
              </>
            ) : (
              'Authorize Checkout →'
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
