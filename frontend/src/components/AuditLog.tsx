// components/AuditLog.tsx — Timeline of policy decisions and payment events
// Phase 2 will populate from GET /api/audit
import { Activity } from 'lucide-react';

export default function AuditLog() {
  // Phase 2: fetch from /api/audit
  const events: null[] = [];

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-icon">
          <Activity size={18} />
        </div>
        <h2>Audit Timeline</h2>
      </div>

      {events.length === 0 ? (
        <div className="audit-empty">
          <p>No events yet. Events are recorded after proposals and payments.</p>
        </div>
      ) : (
        <div className="audit-list">
          {/* Phase 2: events.map(e => <AuditItem key={e.id} event={e} />) */}
        </div>
      )}

      <div style={{ marginTop: '0.75rem', padding: '0.625rem', background: 'var(--bg-input)', borderRadius: 'var(--radius-md)', border: '1px dashed var(--border-subtle)' }}>
        <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          Every proposal, policy decision, user approval, and payment outcome is recorded here with a timestamp.
          Budget is only updated after a verified successful PayPal capture.
        </p>
      </div>
    </div>
  );
}
