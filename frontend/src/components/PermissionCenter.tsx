// components/PermissionCenter.tsx — Complete Agent Spending Governance Tab
import React, { useState, useEffect } from 'react';
import type { Policy, Product } from '../types';
import { formatCents } from '../lib/format';
import { updatePolicy, resetPolicy } from '../api/client';

interface PermissionCenterProps {
  policy: Policy | null;
  products: Product[];
  onPolicyUpdated: (p: Policy) => void;
}

export const PermissionCenter: React.FC<PermissionCenterProps> = ({
  policy,
  products,
  onPolicyUpdated,
}) => {
  // Form fields
  const [totalBudgetCents, setTotalBudgetCents] = useState<number>(10000);
  const [maxPerOrderCents, setMaxPerOrderCents] = useState<number>(4000);
  const [dailyLimitCents, setDailyLimitCents] = useState<number>(0);
  const [monthlyLimitCents, setMonthlyLimitCents] = useState<number>(0);
  const [approvedMerchants, setApprovedMerchants] = useState<string[]>([]);
  const [blockedCategories, setBlockedCategories] = useState<string[]>([]);
  const [requireApproval, setRequireApproval] = useState<boolean>(true);
  const [agentEnabled, setAgentEnabled] = useState<boolean>(true);

  // Status & modal states
  const [saving, setSaving] = useState<boolean>(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [adminToken, setAdminToken] = useState<string>('');
  const [showAdminTokenModal, setShowAdminTokenModal] = useState<boolean>(false);
  const [showResetConfirm, setShowResetConfirm] = useState<boolean>(false);

  // Sync state from policy prop
  useEffect(() => {
    if (policy) {
      setTotalBudgetCents(policy.total_budget_cents);
      setMaxPerOrderCents(policy.max_per_order_cents);
      setDailyLimitCents(policy.daily_limit_cents || 0);
      setMonthlyLimitCents(policy.monthly_limit_cents || 0);
      setApprovedMerchants(policy.approved_merchant_ids || []);
      setBlockedCategories(policy.blocked_categories || []);
      setRequireApproval(policy.require_approval);
      setAgentEnabled(policy.agent_enabled !== false);
    }
  }, [policy]);

  // Derived merchant & category options from catalogue
  const allMerchants = React.useMemo(() => {
    const map = new Map<string, string>();
    products.forEach((p) => map.set(p.merchant_id, p.merchant_name));
    return Array.from(map.entries()).map(([id, name]) => ({ id, name }));
  }, [products]);

  const allCategories = ['peripherals', 'office', 'audio', 'gadgets'];

  const handleSave = async (tokenToUse = adminToken) => {
    setSaving(true);
    setMessage(null);
    try {
      const updated = await updatePolicy(
        {
          total_budget_cents: totalBudgetCents,
          max_per_order_cents: maxPerOrderCents,
          daily_limit_cents: dailyLimitCents,
          monthly_limit_cents: monthlyLimitCents,
          approved_merchant_ids: approvedMerchants,
          blocked_categories: blockedCategories,
          require_approval: requireApproval,
          agent_enabled: agentEnabled,
        },
        tokenToUse
      );
      onPolicyUpdated(updated);
      setMessage({ type: 'success', text: 'Policy successfully updated and active.' });
      setShowAdminTokenModal(false);
    } catch (err: unknown) {
      const error = err as Error & { status?: number };
      if (error?.status === 401 || error?.message?.includes('401') || error?.message?.includes('admin')) {
        setShowAdminTokenModal(true);
      } else {
        setMessage({ type: 'error', text: error.message || 'Failed to update policy' });
      }
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async (tokenToUse = adminToken) => {
    setSaving(true);
    setMessage(null);
    try {
      const reset = await resetPolicy(tokenToUse);
      onPolicyUpdated(reset);
      setMessage({ type: 'success', text: 'Policy reset to pristine demo defaults.' });
      setShowResetConfirm(false);
      setShowAdminTokenModal(false);
    } catch (err: unknown) {
      const error = err as Error & { status?: number };
      if (error?.status === 401 || error?.message?.includes('401')) {
        setShowAdminTokenModal(true);
      } else {
        setMessage({ type: 'error', text: error.message || 'Failed to reset policy' });
      }
    } finally {
      setSaving(false);
    }
  };

  const toggleMerchant = (id: string) => {
    setApprovedMerchants((prev) =>
      prev.includes(id) ? prev.filter((m) => m !== id) : [...prev, id]
    );
  };

  const toggleCategory = (cat: string) => {
    setBlockedCategories((prev) =>
      prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat]
    );
  };

  return (
    <div className="permission-center">
      <div className="card-header">
        <div className="header-title">
          <span className="card-icon">⚙️</span>
          <div>
            <h3>Agent Permission Center</h3>
            <p className="card-subtitle">
              Configure deterministic guardrails. Changes are audited and enforced server-side.
            </p>
          </div>
        </div>
        <div className="policy-badge">
          Version: <strong>v{policy?.policy_version || 1}</strong>
        </div>
      </div>

      {message && (
        <div className={`alert-banner ${message.type}`}>
          <span>{message.type === 'success' ? '✓' : '⚠️'}</span>
          <span>{message.text}</span>
        </div>
      )}

      {/* Master Agent Kill Switch */}
      <div className={`agent-master-switch ${agentEnabled ? 'enabled' : 'disabled'}`}>
        <div className="switch-info">
          <h4>AI Agent Purchase Authority</h4>
          <p>
            {agentEnabled
              ? 'Agent is currently enabled to propose purchases within policy rules.'
              : 'Agent is DISABLED. Any purchase proposal will be instantly BLOCKED.'}
          </p>
        </div>
        <label className="toggle-switch">
          <input
            type="checkbox"
            checked={agentEnabled}
            onChange={(e) => setAgentEnabled(e.target.checked)}
          />
          <span className="toggle-slider" />
        </label>
      </div>

      <div className="permissions-grid">
        {/* Spending Limits Card */}
        <div className="setting-card">
          <h4>Spending Limits</h4>
          <div className="form-group">
            <label>Total Workspace Budget (USD)</label>
            <div className="input-prefix">
              <span>$</span>
              <input
                type="number"
                min="1"
                step="1"
                value={(totalBudgetCents / 100).toFixed(0)}
                onChange={(e) => setTotalBudgetCents(Math.max(1, Number(e.target.value)) * 100)}
              />
            </div>
            <span className="field-hint">Current: {formatCents(totalBudgetCents)}</span>
          </div>

          <div className="form-group">
            <label>Per-Order Spending Cap (USD)</label>
            <div className="input-prefix">
              <span>$</span>
              <input
                type="number"
                min="1"
                step="1"
                value={(maxPerOrderCents / 100).toFixed(0)}
                onChange={(e) => setMaxPerOrderCents(Math.max(1, Number(e.target.value)) * 100)}
              />
            </div>
            <span className="field-hint">Maximum allowable per single checkout</span>
          </div>

          <div className="form-group">
            <label>Daily Spending Limit (USD, 0 = unlimited)</label>
            <div className="input-prefix">
              <span>$</span>
              <input
                type="number"
                min="0"
                step="1"
                value={(dailyLimitCents / 100).toFixed(0)}
                onChange={(e) => setDailyLimitCents(Math.max(0, Number(e.target.value)) * 100)}
              />
            </div>
            <span className="field-hint">
              {dailyLimitCents === 0 ? 'No daily cap enforced' : `${formatCents(dailyLimitCents)} max per UTC day`}
            </span>
          </div>

          <div className="form-group">
            <label>Monthly Spending Limit (USD, 0 = unlimited)</label>
            <div className="input-prefix">
              <span>$</span>
              <input
                type="number"
                min="0"
                step="1"
                value={(monthlyLimitCents / 100).toFixed(0)}
                onChange={(e) => setMonthlyLimitCents(Math.max(0, Number(e.target.value)) * 100)}
              />
            </div>
            <span className="field-hint">
              {monthlyLimitCents === 0 ? 'No monthly cap enforced' : `${formatCents(monthlyLimitCents)} max per month`}
            </span>
          </div>
        </div>

        {/* Allowlist & Restrictions Card */}
        <div className="setting-card">
          <h4>Approved Merchants & Blocked Categories</h4>

          <div className="form-group">
            <label>Approved Merchant Allowlist</label>
            <p className="field-hint">The AI agent can only propose items from selected merchants.</p>
            <div className="checkbox-list">
              {allMerchants.map((m) => (
                <label key={m.id} className="checkbox-item">
                  <input
                    type="checkbox"
                    checked={approvedMerchants.includes(m.id)}
                    onChange={() => toggleMerchant(m.id)}
                  />
                  <span>
                    <strong>{m.name}</strong> ({m.id})
                  </span>
                </label>
              ))}
            </div>
          </div>

          <div className="form-group">
            <label>Blocked Categories</label>
            <p className="field-hint">Categories strictly forbidden for autonomous purchase.</p>
            <div className="category-chips-list">
              {allCategories.map((cat) => {
                const isBlocked = blockedCategories.includes(cat);
                return (
                  <button
                    key={cat}
                    type="button"
                    className={`category-toggle-chip ${isBlocked ? 'blocked' : 'allowed'}`}
                    onClick={() => toggleCategory(cat)}
                  >
                    <span>{isBlocked ? '🚫 Blocked:' : '✓ Allowed:'}</span>
                    <strong>{cat}</strong>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="form-group human-approval-box">
            <label className="checkbox-item">
              <input
                type="checkbox"
                checked={requireApproval}
                onChange={(e) => setRequireApproval(e.target.checked)}
              />
              <span>
                <strong>Require Explicit Human Approval</strong>
                <span className="block-note">Must click "Approve" before PayPal checkout order is generated</span>
              </span>
            </label>
          </div>
        </div>
      </div>

      {/* Action Footer */}
      <div className="permission-actions">
        <button
          type="button"
          className="btn btn-secondary danger-text"
          onClick={() => setShowResetConfirm(true)}
          disabled={saving}
        >
          Reset to Demo Defaults
        </button>

        <button
          type="button"
          className="btn btn-primary save-btn"
          onClick={() => handleSave()}
          disabled={saving}
        >
          {saving ? (
            <>
              <span className="spinner" />
              <span>Saving Policy...</span>
            </>
          ) : (
            'Save Guardrails'
          )}
        </button>
      </div>

      {/* Admin Token Modal */}
      {showAdminTokenModal && (
        <div className="modal-backdrop">
          <div className="modal-dialog">
            <div className="modal-header">
              <h3>Admin Token Required</h3>
              <button className="modal-close-btn" onClick={() => setShowAdminTokenModal(false)}>✕</button>
            </div>
            <div className="modal-body">
              <p>Outside of development mode, policy modifications require an administrator secret token.</p>
              <div className="form-group">
                <label>Admin Token (X-Admin-Token)</label>
                <input
                  type="password"
                  placeholder="Enter ADMIN_TOKEN..."
                  value={adminToken}
                  onChange={(e) => setAdminToken(e.target.value)}
                />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowAdminTokenModal(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={() => handleSave(adminToken)}>Authenticate & Apply</button>
            </div>
          </div>
        </div>
      )}

      {/* Reset Confirmation Modal */}
      {showResetConfirm && (
        <div className="modal-backdrop">
          <div className="modal-dialog">
            <div className="modal-header">
              <h3>Confirm Reset to Defaults</h3>
              <button className="modal-close-btn" onClick={() => setShowResetConfirm(false)}>✕</button>
            </div>
            <div className="modal-body">
              <p>
                This will reset the total budget to $100.00, per-order cap to $40.00, clear category blocks,
                re-enable the agent, and reset recorded spend to $0.00.
              </p>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowResetConfirm(false)}>Cancel</button>
              <button className="btn btn-primary btn-danger" onClick={() => handleReset()}>Confirm Reset</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

