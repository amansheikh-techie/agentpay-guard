// components/SpendBar.tsx — Multi-segment budget visualization
import React from 'react';
import { formatCents } from '../lib/format';

interface SpendBarProps {
  totalBudgetCents: number;
  completedCents: number;
  reservedCents?: number;
  currency?: string;
}

export const SpendBar: React.FC<SpendBarProps> = ({
  totalBudgetCents,
  completedCents,
  reservedCents = 0,
}) => {
  const safeTotal = Math.max(totalBudgetCents, 1);
  const spentPct = Math.min(100, Math.max(0, (completedCents / safeTotal) * 100));
  const reservedPct = Math.min(100 - spentPct, Math.max(0, (reservedCents / safeTotal) * 100));
  const remainingCents = Math.max(0, totalBudgetCents - completedCents - reservedCents);
  const remainingPct = Math.max(0, 100 - spentPct - reservedPct);

  return (
    <div className="spend-bar-container">
      <div className="spend-bar-header">
        <span className="spend-bar-title">Total Budget Utilization</span>
        <span className="spend-bar-total">{formatCents(totalBudgetCents)} Total</span>
      </div>

      <div className="spend-bar-track" role="progressbar" aria-valuenow={spentPct} aria-valuemin={0} aria-valuemax={100}>
        <div
          className="spend-segment spent"
          style={{ width: `${spentPct}%` }}
          title={`Completed: ${formatCents(completedCents)} (${spentPct.toFixed(1)}%)`}
        />
        {reservedPct > 0 && (
          <div
            className="spend-segment reserved"
            style={{ width: `${reservedPct}%` }}
            title={`Reserved: ${formatCents(reservedCents)} (${reservedPct.toFixed(1)}%)`}
          />
        )}
        <div
          className="spend-segment remaining"
          style={{ width: `${remainingPct}%` }}
          title={`Remaining: ${formatCents(remainingCents)} (${remainingPct.toFixed(1)}%)`}
        />
      </div>

      <div className="spend-bar-legend">
        <div className="legend-item">
          <span className="legend-dot spent-dot" />
          <span className="legend-label">Settled:</span>
          <span className="legend-value">{formatCents(completedCents)}</span>
        </div>
        {reservedCents > 0 && (
          <div className="legend-item">
            <span className="legend-dot reserved-dot" />
            <span className="legend-label">In-flight:</span>
            <span className="legend-value">{formatCents(reservedCents)}</span>
          </div>
        )}
        <div className="legend-item">
          <span className="legend-dot remaining-dot" />
          <span className="legend-label">Available:</span>
          <span className="legend-value success-text">{formatCents(remainingCents)}</span>
        </div>
      </div>
    </div>
  );
};

