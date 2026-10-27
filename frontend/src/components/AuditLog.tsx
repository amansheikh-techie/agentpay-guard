// components/AuditLog.tsx — Immutable audit log of policy decisions and payment events
import { Activity, RotateCw, CheckCircle2, XCircle, Settings, ShieldAlert } from 'lucide-react';
import type { AuditEvent } from '../types';

interface Props {
  events: AuditEvent[];
  loading: boolean;
  onRefresh: () => void;
}

export default function AuditLog({ events, loading, onRefresh }: Props) {
  const getEventBadge = (type: string, details: Record<string, unknown>) => {
    switch (type) {
      case 'PROPOSAL_CREATED':
        if (details.policy_decision === 'ALLOWED') {
          return (
            <span style={{ fontSize: '0.72rem', padding: '0.15rem 0.4rem', borderRadius: '4px', background: 'rgba(52,211,153,0.15)', color: 'var(--success)', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
              <CheckCircle2 size={12} />
              PROPOSAL ALLOWED
            </span>
          );
        }
        return (
          <span style={{ fontSize: '0.72rem', padding: '0.15rem 0.4rem', borderRadius: '4px', background: 'rgba(239,68,68,0.15)', color: 'var(--danger)', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
            <XCircle size={12} />
            PROPOSAL BLOCKED
          </span>
        );
      case 'POLICY_UPDATED':
        return (
          <span style={{ fontSize: '0.72rem', padding: '0.15rem 0.4rem', borderRadius: '4px', background: 'rgba(245,158,11,0.15)', color: '#f59e0b', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
            <Settings size={12} />
            POLICY UPDATED
          </span>
        );
      case 'PAYMENT_CAPTURED':
        return (
          <span style={{ fontSize: '0.72rem', padding: '0.15rem 0.4rem', borderRadius: '4px', background: 'rgba(52,211,153,0.2)', color: 'var(--success)', fontWeight: 700 }}>
            PAYMENT CAPTURED
          </span>
        );
      default:
        return (
          <span style={{ fontSize: '0.72rem', padding: '0.15rem 0.4rem', borderRadius: '4px', background: 'var(--bg-input)', color: 'var(--text-muted)', fontWeight: 600 }}>
            {type}
          </span>
        );
    }
  };

  const formatTime = (iso: string) => {
    try {
      const d = new Date(iso);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return iso;
    }
  };

  return (
    <div className="card">
      <div className="card-header" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
          <div className="card-icon">
            <Activity size={18} />
          </div>
          <h2>Immutable Audit Trail</h2>
        </div>
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={onRefresh}
          disabled={loading}
          style={{ fontSize: '0.75rem', gap: '0.35rem', padding: '0.35rem 0.5rem' }}
          title="Refresh audit events"
        >
          <RotateCw size={13} className={loading ? 'spinner' : ''} />
          Refresh
        </button>
      </div>

      {events.length === 0 ? (
        <div className="audit-empty">
          <p>No audit events recorded yet. Submit a shopping request to see events appear.</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '340px', overflowY: 'auto' }}>
          {events.map(ev => {
            const details = (ev.details || {}) as Record<string, unknown>;
            return (
              <div
                key={ev.id}
                style={{
                  padding: '0.625rem 0.75rem',
                  borderRadius: 'var(--radius-md)',
                  background: 'var(--bg-input)',
                  border: '1px solid var(--border-subtle)',
                  fontSize: '0.78rem',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    {getEventBadge(ev.event_type, details)}
                    {ev.proposal_id && (
                      <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                        {ev.proposal_id}
                      </span>
                    )}
                  </div>
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                    {formatTime(ev.created_at)}
                  </span>
                </div>

                {ev.event_type === 'PROPOSAL_CREATED' && (
                  <div style={{ color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                    <div>
                      &ldquo;{String(details.user_request || '')}&rdquo;
                    </div>
                    {Boolean(details.product_name) && (
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>
                        Product: <strong>{String(details.product_name)}</strong>
                        {details.price_cents ? ` ($${(Number(details.price_cents) / 100).toFixed(2)})` : ''}
                      </div>
                    )}
                    {Array.isArray(details.reasons) && details.reasons.length > 0 && (
                      <div style={{ fontSize: '0.7rem', color: 'var(--danger)', marginTop: '0.2rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                        <ShieldAlert size={12} />
                        Reasons: {details.reasons.map(r => String(r)).join(', ')}
                      </div>
                    )}
                  </div>
                )}

                {ev.event_type === 'POLICY_UPDATED' && (
                  <div style={{ color: 'var(--text-secondary)', fontSize: '0.72rem', marginTop: '0.2rem' }}>
                    Budget: ${((Number(details.new_budget_cents) || 0) / 100).toFixed(2)} |
                    Cap: ${((Number(details.new_cap_cents) || 0) / 100).toFixed(2)}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      <div style={{ marginTop: '0.75rem', padding: '0.5rem 0.65rem', background: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)', border: '1px dashed var(--border-subtle)', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
        🔒 Every policy decision and payment action is logged server-side. No API keys or sensitive secrets are ever logged.
      </div>
    </div>
  );
}
