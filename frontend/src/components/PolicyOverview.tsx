// components/PolicyOverview.tsx — Spending policy dashboard and live rule editor
import { useState } from 'react';
import { ShieldCheck, Edit3, Check, X, AlertCircle } from 'lucide-react';
import type { Policy } from '../types';
import { updatePolicy } from '../api/client';

interface Props {
  policy: Policy | null;
  loading: boolean;
  onPolicyUpdated: (updated: Policy) => void;
}

const ALL_MERCHANTS = [
  { id: 'techcore', name: 'TechCore Electronics' },
  { id: 'homeplus', name: 'HomePlus Supplies' },
  { id: 'officemate', name: 'OfficeMate Pro' },
  { id: 'shadowtech', name: 'ShadowTech (Demo unapproved)' },
];

export default function PolicyOverview({ policy, loading, onPolicyUpdated }: Props) {
  const [editing, setEditing] = useState(false);
  const [budgetDollars, setBudgetDollars] = useState('100.00');
  const [capDollars, setCapDollars] = useState('40.00');
  const [selectedMerchants, setSelectedMerchants] = useState<string[]>(['techcore', 'homeplus']);
  const [saving, setSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  const startEdit = () => {
    if (!policy) return;
    setBudgetDollars((policy.total_budget_cents / 100).toFixed(2));
    setCapDollars((policy.max_per_order_cents / 100).toFixed(2));
    setSelectedMerchants([...policy.approved_merchant_ids]);
    setEditError(null);
    setEditing(true);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setEditError(null);

    const b = Math.round(parseFloat(budgetDollars) * 100);
    const c = Math.round(parseFloat(capDollars) * 100);

    if (isNaN(b) || b <= 0) {
      setEditError('Total budget must be a positive amount.');
      return;
    }
    if (isNaN(c) || c <= 0) {
      setEditError('Per-order cap must be a positive amount.');
      return;
    }
    if (c > b) {
      setEditError('Per-order cap cannot exceed total budget.');
      return;
    }
    if (selectedMerchants.length === 0) {
      setEditError('At least one merchant must be approved.');
      return;
    }

    setSaving(true);
    try {
      const updated = await updatePolicy({
        total_budget_cents: b,
        max_per_order_cents: c,
        approved_merchant_ids: selectedMerchants,
        require_approval: true,
      });
      onPolicyUpdated(updated);
      setEditing(false);
    } catch (err) {
      setEditError((err as Error).message || 'Failed to update policy.');
    } finally {
      setSaving(false);
    }
  };

  const toggleMerchant = (id: string) => {
    setSelectedMerchants(prev =>
      prev.includes(id) ? prev.filter(m => m !== id) : [...prev, id]
    );
  };

  if (loading || !policy) {
    return (
      <div className="card">
        <div className="card-header">
          <div className="card-icon"><ShieldCheck size={18} /></div>
          <h2>Spending Policy</h2>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {[1, 2, 3].map(i => (
            <div key={i} className="skeleton" style={{ height: '48px', borderRadius: '8px' }} />
          ))}
        </div>
      </div>
    );
  }

  const spent = policy.successful_spend_cents / 100;
  const total = policy.total_budget_cents / 100;
  const remaining = (policy.remaining_budget_cents ?? (policy.total_budget_cents - policy.successful_spend_cents)) / 100;
  const cap = policy.max_per_order_cents / 100;
  const pct = Math.min(100, Math.round((policy.successful_spend_cents / policy.total_budget_cents) * 100)) || 0;

  return (
    <div className="card">
      <div className="card-header" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
          <div className="card-icon"><ShieldCheck size={18} /></div>
          <h2>Deterministic Spending Policy</h2>
        </div>
        {!editing ? (
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={startEdit}
            style={{ fontSize: '0.78rem', gap: '0.35rem' }}
          >
            <Edit3 size={14} />
            Edit Rules
          </button>
        ) : (
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => setEditing(false)}
            style={{ fontSize: '0.78rem', gap: '0.35rem' }}
          >
            <X size={14} />
            Cancel
          </button>
        )}
      </div>

      {!editing ? (
        <>
          <div className="policy-grid">
            <div className="policy-stat">
              <div className="policy-stat-label">Total Budget</div>
              <div className="policy-stat-value accent">${total.toFixed(2)}</div>
            </div>
            <div className="policy-stat">
              <div className="policy-stat-label">Spent (Captured)</div>
              <div className="policy-stat-value">${spent.toFixed(2)}</div>
            </div>
            <div className="policy-stat">
              <div className="policy-stat-label">Remaining</div>
              <div className="policy-stat-value" style={{ color: remaining > 0 ? 'var(--success)' : 'var(--danger)' }}>
                ${remaining.toFixed(2)}
              </div>
            </div>
            <div className="policy-stat">
              <div className="policy-stat-label">Per-Order Cap</div>
              <div className="policy-stat-value">${cap.toFixed(2)}</div>
            </div>
          </div>

          {/* Utilization bar */}
          <div className="budget-bar-wrap">
            <div className="budget-bar-label">
              <span>Budget Utilisation</span>
              <span>{pct}%</span>
            </div>
            <div className="budget-bar-track">
              <div className="budget-bar-fill" style={{ width: `${pct}%` }} />
            </div>
          </div>

          {/* Approved merchants */}
          <div style={{ marginTop: '1rem' }}>
            <p style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.5rem' }}>
              Approved Merchant Allowlist
            </p>
            <div className="merchant-chips">
              {policy.approved_merchant_ids.map(id => {
                const found = ALL_MERCHANTS.find(m => m.id === id);
                return (
                  <span key={id} className="merchant-chip" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                    <Check size={12} color="var(--primary)" />
                    {found ? found.name : id}
                  </span>
                );
              })}
            </div>
          </div>

          <div style={{ marginTop: '0.875rem', padding: '0.625rem 0.75rem', background: 'var(--bg-input)', borderRadius: 'var(--radius-md)', fontSize: '0.72rem', color: 'var(--text-muted)' }}>
            🔒 <strong>Human Approval Required</strong>: The AI cannot autonomously spend. Every purchase requires explicit user confirmation.
          </div>
        </>
      ) : (
        <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
          {editError && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.625rem', background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 'var(--radius-md)', color: 'var(--danger)', fontSize: '0.8rem' }}>
              <AlertCircle size={15} />
              <span>{editError}</span>
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
            <div className="form-group">
              <label className="form-label" htmlFor="edit-budget">Total Budget ($ USD)</label>
              <input
                id="edit-budget"
                type="number"
                step="0.01"
                min="1"
                className="form-input"
                value={budgetDollars}
                onChange={e => setBudgetDollars(e.target.value)}
                disabled={saving}
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="edit-cap">Per-Order Cap ($ USD)</label>
              <input
                id="edit-cap"
                type="number"
                step="0.01"
                min="1"
                className="form-input"
                value={capDollars}
                onChange={e => setCapDollars(e.target.value)}
                disabled={saving}
              />
            </div>
          </div>

          <div>
            <label className="form-label">Merchant Allowlist</label>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', marginTop: '0.35rem' }}>
              {ALL_MERCHANTS.map(m => {
                const checked = selectedMerchants.includes(m.id);
                return (
                  <label
                    key={m.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                      fontSize: '0.82rem',
                      padding: '0.4rem 0.6rem',
                      background: checked ? 'rgba(14,165,233,0.1)' : 'var(--bg-input)',
                      border: `1px solid ${checked ? 'rgba(14,165,233,0.3)' : 'var(--border-subtle)'}`,
                      borderRadius: 'var(--radius-md)',
                      cursor: 'pointer',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleMerchant(m.id)}
                      disabled={saving}
                    />
                    <span>{m.name}</span>
                  </label>
                );
              })}
            </div>
          </div>

          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
            <button
              type="submit"
              className="btn btn-primary btn-sm"
              disabled={saving}
              style={{ flex: 1 }}
            >
              {saving ? 'Saving…' : 'Save Policy Changes'}
            </button>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => setEditing(false)}
              disabled={saving}
            >
              Cancel
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
