// components/Header.tsx — Top navigation with branding, sandbox badge, health indicators
import { useEffect, useState } from 'react';
import { Shield, AlertTriangle, CheckCircle, XCircle, Zap } from 'lucide-react';
import { fetchHealth } from '../api/client';
import type { HealthStatus } from '../types';

export default function Header() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch(() => setError(true));
  }, []);

  const backendOk = !error && health?.status === 'ok';

  return (
    <header className="app-header">
      {/* Logo */}
      <div className="header-logo">
        <div className="header-logo-icon">
          <Shield size={18} color="#0b0f1a" strokeWidth={2.5} />
        </div>
        <span className="header-logo-name">
          AgentPay <span>Guard</span>
        </span>
      </div>

      <div className="header-spacer" />

      {/* Badges */}
      <div className="header-badges">
        {/* Sandbox warning — always visible */}
        <span className="badge badge-sandbox">
          <AlertTriangle size={11} />
          PayPal Sandbox — test only
        </span>

        {/* Backend health */}
        <span className={`badge ${backendOk ? 'badge-success' : error ? 'badge-danger' : 'badge-muted'}`}>
          {backendOk ? <CheckCircle size={11} /> : error ? <XCircle size={11} /> : null}
          {backendOk ? 'API Online' : error ? 'API Offline' : 'Connecting…'}
        </span>

        {/* AI mode */}
        {health && (
          <span className={`badge ${health.ai_configured ? 'badge-success' : 'badge-warning'}`}>
            <Zap size={11} />
            {health.ai_configured ? `AI: ${health.ai_provider}` : 'Demo Fallback Mode'}
          </span>
        )}
      </div>
    </header>
  );
}
