// components/ShoppingResults.tsx — Structured understanding and ranked alternative comparison
import React from 'react';
import type { Proposal } from '../types';
import { formatCents } from '../lib/format';
import { ProductImage } from './ProductImage';

interface ShoppingResultsProps {
  proposal: Proposal;
  onSelectAlternative?: (alt: Proposal) => void;
  activeProposalId?: string;
}

export const ShoppingResults: React.FC<ShoppingResultsProps> = ({
  proposal,
  onSelectAlternative,
  activeProposalId,
}) => {
  const reqs = proposal.extracted_requirements;
  const alternatives = proposal.alternatives || proposal.candidates || [];

  return (
    <div className="shopping-results-wrapper">
      {/* 1. What the Agent Understood */}
      <div className="requirements-box">
        <div className="requirements-header">
          <span className="req-icon">🤖</span>
          <span className="req-title">What the Agent Understood</span>
        </div>
        <div className="requirements-chips">
          {reqs?.category && (
            <span className="req-chip category-chip">
              Category: <strong>{reqs.category}</strong>
            </span>
          )}
          {reqs?.max_price_cents && reqs.max_price_cents > 0 ? (
            <span className="req-chip price-chip">
              Target Budget: <strong>≤ {formatCents(reqs.max_price_cents)}</strong>
            </span>
          ) : (
            <span className="req-chip price-chip muted">
              Target Budget: <strong>Policy Default</strong>
            </span>
          )}
          {reqs?.features && reqs.features.length > 0 ? (
            reqs.features.map((f, i) => (
              <span key={i} className="req-chip feature-chip">
                ✓ {f}
              </span>
            ))
          ) : (
            <span className="req-chip feature-chip muted">Standard workspace spec</span>
          )}
        </div>
      </div>

      {/* 2. Candidate Alternatives Comparison (if any) */}
      {alternatives.length > 0 && (
        <div className="alternatives-section">
          <div className="alternatives-header">
            <h4>
              <span>💡</span>
              <span>Available In-Policy Alternatives ({alternatives.length})</span>
            </h4>
            <span className="alternatives-subtitle">
              Pre-screened against active budget & allowlist
            </span>
          </div>

          <div className="alternatives-grid">
            {alternatives.map((alt, idx) => {
              const isSelected = activeProposalId === alt.id;
              const product = alt.product;
              if (!product) return null;

              return (
                <div
                  key={alt.id}
                  className={`alternative-card ${isSelected ? 'selected' : ''}`}
                >
                  <div className="alt-rank-tag">Option #{idx + 2}</div>
                  <div className="alt-card-header">
                    <ProductImage
                      productId={product.id}
                      name={product.name}
                      category={product.category}
                      size="sm"
                    />
                    <div className="alt-card-title">
                      <h5>{product.name}</h5>
                      <span className="alt-merchant">{product.merchant_name}</span>
                    </div>
                  </div>

                  <div className="alt-pricing">
                    <span className="alt-price">{formatCents(product.price_cents)}</span>
                    {alt.price_difference_cents !== undefined && alt.price_difference_cents !== null && alt.price_difference_cents !== 0 && (
                      <span className={`price-diff ${alt.price_difference_cents < 0 ? 'cheaper' : 'pricier'}`}>
                        {alt.price_difference_cents < 0
                          ? `${formatCents(alt.price_difference_cents)} less`
                          : `+${formatCents(alt.price_difference_cents)}`}
                      </span>
                    )}
                  </div>

                  {alt.matched_requirements && alt.matched_requirements.length > 0 && (
                    <div className="alt-matches">
                      {alt.matched_requirements.slice(0, 2).map((m, mIdx) => (
                        <span key={mIdx} className="match-tag">✓ {m}</span>
                      ))}
                    </div>
                  )}

                  <div className="alt-action">
                    <button
                      type="button"
                      className={`btn btn-sm ${isSelected ? 'btn-active' : 'btn-outline'}`}
                      onClick={() => onSelectAlternative && onSelectAlternative(alt)}
                      disabled={isSelected}
                    >
                      {isSelected ? '✓ Current Selection' : 'Review this instead →'}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

