// components/PolicyOverview.tsx — Read-only summary of current spending policy
// Placeholder for Phase 2; shows skeleton loaders until data is available.
import { ShieldCheck, DollarSign } from 'lucide-react';

export default function PolicyOverview() {
  // Phase 2 will connect this to GET /api/policy
  const isLoading = false; // will become real in Phase 2

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-icon">
          <ShieldCheck size={18} />
        </div>
        <h2>Spending Policy</h2>
      </div>

      {isLoading ? (
        <PolicySkeleton />
      ) : (
        <>
          <div className="policy-grid">
            <div className="policy-stat">
              <div className="policy-stat-label">Total Budget</div>
              <div className="policy-stat-value accent">—</div>
            </div>
            <div className="policy-stat">
              <div className="policy-stat-label">Remaining</div>
              <div className="policy-stat-value">—</div>
            </div>
            <div className="policy-stat">
              <div className="policy-stat-label">Per-Order Cap</div>
              <div className="policy-stat-value">—</div>
            </div>
            <div className="policy-stat">
              <div className="policy-stat-label">Approval</div>
              <div className="policy-stat-value">Required</div>
            </div>
          </div>

          {/* Budget progress bar */}
          <div className="budget-bar-wrap">
            <div className="budget-bar-label">
              <span>Budget utilisation</span>
              <span>—%</span>
            </div>
            <div className="budget-bar-track">
              <div className="budget-bar-fill" style={{ width: '0%' }} />
            </div>
          </div>

          {/* Approved merchants */}
          <div style={{ marginTop: '1rem' }}>
            <p style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.5rem' }}>
              Approved Merchants
            </p>
            <div className="merchant-chips">
              <span className="merchant-chip" style={{ opacity: 0.5 }}>Loading in Phase 2…</span>
            </div>
          </div>

          <div style={{ marginTop: '1rem', padding: '0.75rem', background: 'var(--bg-input)', borderRadius: 'var(--radius-md)', border: '1px dashed var(--border-subtle)' }}>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <DollarSign size={13} />
              Policy data loads in Phase 2 — catalogue, persistence &amp; policy engine.
            </p>
          </div>
        </>
      )}
    </div>
  );
}

function PolicySkeleton() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      {[1, 2, 3].map(i => (
        <div key={i} className="skeleton" style={{ height: '48px', borderRadius: '8px' }} />
      ))}
    </div>
  );
}
