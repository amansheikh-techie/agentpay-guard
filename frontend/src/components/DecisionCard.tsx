// components/DecisionCard.tsx — Shows AI recommendation and ALLOWED/BLOCKED verdict
// Phase 3 will populate this with real proposal data
import { ClipboardList, ShieldX, ShieldCheck } from 'lucide-react';

export default function DecisionCard() {
  // Phase 3: receives Proposal from parent state
  const proposal = null;

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-icon">
          <ClipboardList size={18} />
        </div>
        <h2>Policy Decision</h2>
      </div>

      {proposal === null ? (
        <div className="decision-empty">
          <div className="decision-empty-icon">🛡️</div>
          <p style={{ fontWeight: 500, color: 'var(--text-secondary)' }}>
            No active proposal
          </p>
          <p style={{ fontSize: '0.82rem' }}>
            Submit a shopping request above to see the AI recommendation and policy decision here.
          </p>
        </div>
      ) : null}

      {/* ── Blocked example layout (rendered when proposal.policy_decision === 'BLOCKED') ── */}
      {false && (
        <div style={{ border: '1px solid rgba(248,113,113,0.3)', borderRadius: 'var(--radius-md)', padding: '1.25rem', background: 'var(--danger-bg)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <ShieldX size={20} color="var(--danger)" />
            <span style={{ fontWeight: 700, color: 'var(--danger)', fontSize: '1rem' }}>BLOCKED</span>
          </div>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            This purchase was blocked by the policy engine.
          </p>
          {/* Reason codes rendered here in Phase 3 */}
        </div>
      )}

      {/* ── Allowed example layout ── */}
      {false && (
        <div style={{ border: '1px solid rgba(52,211,153,0.3)', borderRadius: 'var(--radius-md)', padding: '1.25rem', background: 'var(--success-bg)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <ShieldCheck size={20} color="var(--success)" />
            <span style={{ fontWeight: 700, color: 'var(--success)', fontSize: '1rem' }}>ALLOWED</span>
          </div>
          {/* Approve button shown ONLY here for allowed proposals — Phase 4 */}
        </div>
      )}
    </div>
  );
}
