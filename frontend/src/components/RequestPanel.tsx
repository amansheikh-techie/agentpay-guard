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
    chip: 'Allowed',
    chipClass: 'chip-allowed',
    text: 'Find a wireless mouse for work, under $35, from an approved merchant.',
    hint: 'Meets cap ($29.99 < $40), merchant TechCore is approved.',
  },
  {
    chip: 'Blocked: Cap',
    chipClass: 'chip-blocked',
    text: 'I need a high-end mechanical keyboard for typing.',
    hint: 'Product costs $79.99, exceeds $40 per-order limit.',
  },
  {
    chip: 'Blocked: Merchant',
    chipClass: 'chip-merchant',
    text: 'Find a shadowtech gadget for my desk.',
    hint: 'Merchant ShadowTech is NOT in approved list.',
  },
];

export default function RequestPanel({ onProposalCreated }: Props) {
  const [requestText, setRequestText] = useState('');
  const [selectedScenarioIndex, setSelectedScenarioIndex] = useState<number | null>(null);
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

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem', width: '100%', minWidth: 0 }}>
        {error && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.625rem', background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 'var(--radius-md)', color: 'var(--danger)', fontSize: '0.8rem' }}>
            <AlertCircle size={15} />
            <span>{error}</span>
          </div>
        )}

        <div className="form-group" style={{ width: '100%', minWidth: 0 }}>
          <label className="form-label" htmlFor="shopping-request">
            Natural-Language Request
          </label>
          <textarea
            id="shopping-request"
            className="form-textarea"
            placeholder="e.g. Find a wireless mouse for work, under $35, from an approved merchant."
            value={requestText}
            onChange={e => {
              const val = e.target.value;
              setRequestText(val);
              if (selectedScenarioIndex !== null && val !== DEMO_SCENARIOS[selectedScenarioIndex]?.text) {
                setSelectedScenarioIndex(null);
              }
            }}
            rows={3}
            disabled={loading}
          />
        </div>

        {/* Demo Scenario Quick-Picks */}
        <div style={{ width: '100%', minWidth: 0 }}>
          <p style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Test Hackathon Demo Scenarios:
          </p>
          <div className="scenario-list">
            {DEMO_SCENARIOS.map((s, idx) => {
              const isSelected = selectedScenarioIndex === idx && requestText === s.text;
              return (
                <button
                  key={idx}
                  type="button"
                  className={`scenario-btn ${isSelected ? 'selected' : ''}`}
                  onClick={() => {
                    setRequestText(s.text);
                    setSelectedScenarioIndex(idx);
                  }}
                  disabled={loading}
                  aria-pressed={isSelected}
                >
                  <span className={`scenario-chip ${s.chipClass}`}>
                    {s.chip}
                  </span>
                  <div className="scenario-text">{s.text}</div>
                  <div className="scenario-hint">{s.hint}</div>
                </button>
              );
            })}
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
              <span>Checking policy...</span>
            </>
          ) : (
            <>
              <Send size={16} />
              <span>Propose Purchase</span>
            </>
          )}
        </button>

        <p style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', textAlign: 'center', lineHeight: 1.45, margin: 0 }}>
          🛡️ <strong>Trust Boundary</strong>: The AI model only selects a product ID. Product prices, merchant identity, and policy evaluation are authoritative on the server.
        </p>
      </form>
    </div>
  );
}
