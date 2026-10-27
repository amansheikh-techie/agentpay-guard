// components/RequestPanel.tsx — Natural-language shopping request form
// Phase 3 will wire submit to POST /api/agent/propose
import { useState } from 'react';
import { Send, Sparkles } from 'lucide-react';

const EXAMPLE_PROMPTS = [
  'Find a wireless mouse for work, under $35, from an approved merchant.',
  'I need a USB-C hub with at least 4 ports, budget $50.',
  'Recommend a noise-cancelling headset for video calls.',
];

export default function RequestPanel() {
  const [request, setRequest] = useState('');
  const [loading] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!request.trim() || loading) return;
    // Phase 3: call POST /api/agent/propose
    alert('AI proposal endpoint arrives in Phase 3!');
  };

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-icon">
          <Sparkles size={18} />
        </div>
        <h2>Shopping Request</h2>
      </div>

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div className="form-group">
          <label className="form-label" htmlFor="shopping-request">
            Describe what you need
          </label>
          <textarea
            id="shopping-request"
            className="form-textarea"
            placeholder="e.g. Find a wireless mouse for work, under $35, from an approved merchant."
            value={request}
            onChange={e => setRequest(e.target.value)}
            rows={3}
            disabled={loading}
          />
        </div>

        {/* Example prompts */}
        <div>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
            Try an example:
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
            {EXAMPLE_PROMPTS.map((p, i) => (
              <button
                key={i}
                type="button"
                className="btn btn-ghost btn-sm"
                style={{ justifyContent: 'flex-start', textAlign: 'left', fontSize: '0.78rem' }}
                onClick={() => setRequest(p)}
                disabled={loading}
              >
                {p}
              </button>
            ))}
          </div>
        </div>

        <button
          id="submit-request-btn"
          type="submit"
          className="btn btn-primary btn-full btn-lg"
          disabled={!request.trim() || loading}
        >
          {loading ? (
            <>
              <span className="spinner" />
              Analysing with AI…
            </>
          ) : (
            <>
              <Send size={16} />
              Submit to AI Agent
            </>
          )}
        </button>

        <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textAlign: 'center' }}>
          The AI may only select products from the backend catalogue. Price and merchant are always verified server-side.
        </p>
      </form>
    </div>
  );
}
