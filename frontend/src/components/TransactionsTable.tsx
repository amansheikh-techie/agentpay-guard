// components/TransactionsTable.tsx — Ledger of all PayPal Sandbox payment records
import React, { useState } from 'react';
import type { PaymentListItem } from '../types';
import { formatCents, formatDateTime } from '../lib/format';

interface TransactionsTableProps {
  payments: PaymentListItem[];
  onRefresh?: () => void;
  loading?: boolean;
}

export const TransactionsTable: React.FC<TransactionsTableProps> = ({
  payments,
  onRefresh,
  loading = false,
}) => {
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const filtered = payments.filter((p) => {
    if (statusFilter === 'all') return true;
    return p.status === statusFilter;
  });

  return (
    <div className="transactions-card">
      <div className="card-header">
        <div className="header-title">
          <span className="card-icon">💳</span>
          <div>
            <h3>Payment Ledger & Transactions</h3>
            <p className="card-subtitle">
              Every PayPal Sandbox transaction is verified by the backend before status updates.
            </p>
          </div>
        </div>

        <div className="table-controls">
          <div className="filter-group">
            <label>Filter Status:</label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="filter-select"
            >
              <option value="all">All Transactions ({payments.length})</option>
              <option value="captured">Captured (Settled)</option>
              <option value="pending">Pending</option>
              <option value="cancelled">Cancelled</option>
              <option value="failed">Failed</option>
              <option value="needs_verification">Needs Verification</option>
            </select>
          </div>

          {onRefresh && (
            <button
              type="button"
              className="btn btn-sm btn-secondary"
              onClick={onRefresh}
              disabled={loading}
            >
              {loading ? 'Refreshing...' : '↻ Refresh'}
            </button>
          )}
        </div>
      </div>

      <div className="table-responsive">
        {filtered.length === 0 ? (
          <div className="empty-table-state">
            <p>No transactions match the selected filter.</p>
          </div>
        ) : (
          <table className="ledger-table">
            <thead>
              <tr>
                <th>Created (UTC)</th>
                <th>Product</th>
                <th>Merchant</th>
                <th>Amount</th>
                <th>PayPal Order</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((item) => (
                <tr key={item.id}>
                  <td className="timestamp-cell">{formatDateTime(item.created_at)}</td>
                  <td className="product-cell">
                    <strong>{item.product_name || item.proposal_id}</strong>
                  </td>
                  <td>{item.merchant_name || '—'}</td>
                  <td className="amount-cell">{formatCents(item.amount_cents)}</td>
                  <td className="code-cell">
                    {item.paypal_order_id ? (
                      <code>{item.paypal_order_id.slice(0, 16)}...</code>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                  <td>
                    <span className={`status-pill ${item.status}`}>
                      {item.status.toUpperCase()}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
