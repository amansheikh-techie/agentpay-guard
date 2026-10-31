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
            <span style={{ fontSize: '0.72rem', padding: '0.15rem 0.45rem', borderRadius: '4px', background: 'rgba(52,211,153,0.15)', color: 'var(--success)', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '0.25rem', border: '1px solid rgba(52,211,153,0.3)' }}>
              <CheckCircle2 size={12} />
              PROPOSAL ALLOWED
            </span>
          );
        }
        return (
          <span style={{ fontSize: '0.72rem', padding: '0.15rem 0.45rem', borderRadius: '4px', background: 'rgba(239,68,68,0.15)', color: 'var(--danger)', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '0.25rem', border: '1px solid rgba(239,68,68,0.3)' }}>
            <XCircle size={12} />
            PROPOSAL BLOCKED
          </span>
        );
      case 'POLICY_UPDATED':
        return (
          <span style={{ fontSize: '0.72rem', padding: '0.15rem 0.45rem', borderRadius: '4px', background: 'rgba(245,158,11,0.15)', color: '#fbbf24', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '0.25rem', border: '1px solid rgba(245,158,11,0.3)' }}>
            <Settings size={12} />
            POLICY UPDATED
          </span>
        );
      case 'PAYMENT_CREATED':
        return (
          <span style={{ fontSize: '0.72rem', padding: '0.15rem 0.45rem', borderRadius: '4px', background: 'rgba(96,165,250,0.15)', color: 'var(--info)', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '0.25rem', border: '1px solid rgba(96,165,250,0.3)' }}>
            <CheckCircle2 size={12} />
            ORDER CREATED
          </span>
        );
      case 'PAYMENT_CAPTURED':
        return (
          <span style={{ fontSize: '0.72rem', padding: '0.15rem 0.45rem', borderRadius: '4px', background: 'rgba(52,211,153,0.2)', color: 'var(--success)', fontWeight: 700, border: '1px solid rgba(52,211,153,0.35)' }}>
            PAYMENT CAPTURED
          </span>
        );
      case 'PAYMENT_CANCELLED':
        return (
          <span style={{ fontSize: '0.72rem', padding: '0.15rem 0.45rem', borderRadius: '4px', background: 'rgba(239,68,68,0.15)', color: 'var(--danger)', fontWeight: 600, border: '1px solid rgba(239,68,68,0.3)' }}>
            PAYMENT CANCELLED
          </span>
        );
      default:
        return (
          <span style={{ fontSize: '0.72rem', padding: '0.15rem 0.45rem', borderRadius: '4px', background: 'var(--bg-input)', color: 'var(--text-secondary)', fontWeight: 600, border: '1px solid var(--border-subtle)' }}>
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
          style={{ fontSize: '0.75rem', gap: '0.35rem', padding: '0.35rem 0.55rem' }}
          title="Refresh audit events"
        >
          <RotateCw size={13} className={loading ? 'spin-anim' : ''} />
          Refresh
        </button>
      </div>

      {events.length === 0 ? (
        <div className="audit-empty" style={{ padding: '2.5rem 1rem', textAlign: 'center' }}>
          <div style={{ fontSize: '2rem', marginBottom: '0.5rem', opacity: 0.85 }}>📋</div>
          <p style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.25rem' }}>
            No Audit Events Recorded Yet
          </p>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', maxWidth: '320px', margin: '0 auto', lineHeight: 1.45 }}>
            Submit a shopping request or update policy limits to see immutable audit trail events appear in real time.
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '340px', overflowY: 'auto', width: '100%', minWidth: 0 }}>
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
                  width: '100%',
                  minWidth: 0,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem', flexWrap: 'wrap', gap: '0.35rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexWrap: 'wrap' }}>
                    {getEventBadge(ev.event_type, details)}
                    {ev.proposal_id && (
                      <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', fontFamily: 'monospace' }}>
                        {ev.proposal_id}
                      </span>
                    )}
                  </div>
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                    {formatTime(ev.created_at)}
                  </span>
                </div>

                {ev.event_type === 'PROPOSAL_CREATED' && (
                  <div style={{ color: 'var(--text-secondary)', marginTop: '0.25rem', overflowWrap: 'anywhere', wordBreak: 'normal' }}>
                    <div>
                      &ldquo;{String(details.user_request || '')}&rdquo;
                    </div>
                    {Boolean(details.product_name) && (
                      <div style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
                        Product: <strong style={{ color: 'var(--text-primary)' }}>{String(details.product_name)}</strong>
                        {details.price_cents ? ` ($${(Number(details.price_cents) / 100).toFixed(2)})` : ''}
                      </div>
                    )}
                    {Array.isArray(details.reasons) && details.reasons.length > 0 && (
                      <div style={{ fontSize: '0.72rem', color: 'var(--danger)', marginTop: '0.25rem', display: 'flex', alignItems: 'center', gap: '0.25rem', flexWrap: 'wrap' }}>
                        <ShieldAlert size={12} style={{ flexShrink: 0 }} />
                        <span>Reasons: {details.reasons.map(r => String(r)).join(', ')}</span>
                      </div>
                    )}
                  </div>
                )}

                {ev.event_type === 'POLICY_UPDATED' && (
                  <div style={{ color: 'var(--text-secondary)', fontSize: '0.74rem', marginTop: '0.2rem' }}>
                    Budget: ${((Number(details.new_budget_cents) || 0) / 100).toFixed(2)} |
                    Cap: ${((Number(details.new_cap_cents) || 0) / 100).toFixed(2)}
                  </div>
                )}

                {(ev.event_type === 'PAYMENT_CAPTURED' || ev.event_type === 'PAYMENT_CREATED') && (
                  <div style={{ color: 'var(--text-secondary)', fontSize: '0.74rem', marginTop: '0.2rem', display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center' }}>
                    <span>
                      Amount: <strong style={{ color: 'var(--accent)' }}>${details.amount_cents ? (Number(details.amount_cents) / 100).toFixed(2) : '—'} {String(details.currency || 'USD')}</strong>
                    </span>
                    {Boolean(details.product_name) && (
                      <span style={{ color: 'var(--text-secondary)' }}>
                        ({String(details.product_name)})
                      </span>
                    )}
                    {Boolean(details.paypal_order_id) && (
                      <span style={{ color: 'var(--text-muted)', fontFamily: 'monospace', fontSize: '0.7rem' }}>
                        Order: {String(details.paypal_order_id)}
                      </span>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      <div style={{
        marginTop: '0.75rem',
        padding: '0.6rem 0.75rem',
        background: 'var(--bg-surface)',
        borderRadius: 'var(--radius-sm)',
        border: '1px dashed var(--border-subtle)',
        fontSize: '0.74rem',
        color: 'var(--text-secondary)',
        lineHeight: 1.45,
        whiteSpace: 'normal',
        overflowWrap: 'anywhere',
        wordBreak: 'normal',
        minWidth: 0,
        width: '100%',
      }}>
        🔒 Every policy decision and payment action is logged server-side. No API keys or sensitive secrets are ever logged.
      </div>
    </div>
  );
}
