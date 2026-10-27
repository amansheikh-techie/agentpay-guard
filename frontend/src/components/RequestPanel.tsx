// components/RequestPanel.tsx — Natural-language shopping request form wired to POST /api/agent/propose
import { useState } from 'react';
import { Send, Sparkles, AlertCircle } from 'lucide-react';
import { propose } from '../api/client';
import type { Proposal } from '../types';

interface Props {
  onProposalCreated: (proposal: Proposal) => void;
}

const DEMO_SCENARIOS = [
  {
    tag: 'Scenario A (Allowed)',
    text: 'Find a wireless mouse for work, under $35, from an approved merchant.',
    hint: 'Meets cap ($29.99 < $40), merchant TechCore is approved.',
  },
  {
    tag: 'Scenario B (Blocked: Cap)',
    text: 'I need a high-end mechanical keyboard for typing.',
    hint: 'Product costs $79.99, exceeds $40 per-order limit.',
  },
  {
    tag: 'Scenario C (Blocked: Merchant)',
    text: 'Find a shadowtech gadget for my desk.',
    hint: 'Merchant ShadowTech is NOT in approved list.',
  },
];

export default function RequestPanel({ onProposalCreated }: Props) {
  const [requestText, setRequestText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const clean = requestText.trim();
    if (!clean || loading) return;

    setLoading(true);
    setError(null);

    try {
      const proposal = await propose(clean);
      onProposalCreated(proposal);
    } catch (err) {
      setError((err as Error).message || 'Failed to submit shopping request.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-icon">
          <Sparkles size={18} />
        </div>
        <h2>AI Shopping Agent</h2>
      </div>

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {error && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.625rem', background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 'var(--radius-md)', color: 'var(--danger)', fontSize: '0.8rem' }}>
            <AlertCircle size={15} />
            <span>{error}</span>
          </div>
        )}

        <div className="form-group">
          <label className="form-label" htmlFor="shopping-request">
            Natural-Language Request
          </label>
          <textarea
            id="shopping-request"
            className="form-textarea"
            placeholder="e.g. Find a wireless mouse for work, under $35, from an approved merchant."
            value={requestText}
            onChange={e => setRequestText(e.target.value)}
            rows={3}
            disabled={loading}
          />
        </div>

        {/* Demo Scenario Quick-Picks */}
        <div>
          <p style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Test Hackathon Demo Scenarios:
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
            {DEMO_SCENARIOS.map((s, idx) => (
              <button
                key={idx}
                type="button"
                className="btn btn-ghost btn-sm"
                style={{
                  justifyContent: 'flex-start',
                  textAlign: 'left',
                  fontSize: '0.78rem',
                  padding: '0.45rem 0.625rem',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-md)',
                  background: 'var(--bg-input)',
                }}
                onClick={() => setRequestText(s.text)}
                disabled={loading}
              >
                <div>
                  <span style={{ fontWeight: 600, color: 'var(--primary)', marginRight: '0.4rem' }}>
                    {s.tag}:
                  </span>
                  <span style={{ color: 'var(--text-primary)' }}>{s.text}</span>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.1rem' }}>
                    {s.hint}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>

        <button
          id="submit-request-btn"
          type="submit"
          className="btn btn-primary btn-full btn-lg"
          disabled={!requestText.trim() || loading}
        >
          {loading ? (
            <>
              <span className="spinner" />
              Evaluating with AI &amp; Policy Engine…
            </>
          ) : (
            <>
              <Send size={16} />
              Propose Purchase
            </>
          )}
        </button>

        <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textAlign: 'center', lineHeight: 1.4 }}>
          🛡️ <strong>Trust Boundary</strong>: The AI model only selects a product ID. Product prices, merchant identity, and policy evaluation are authoritative on the server.
        </p>
      </form>
    </div>
  );
}
