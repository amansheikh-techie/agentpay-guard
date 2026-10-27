// App.tsx — Root layout and dashboard coordinator for AgentPay Guard
import { useState, useEffect, useCallback } from 'react';
import './index.css';
import Header from './components/Header';
import PolicyOverview from './components/PolicyOverview';
import RequestPanel from './components/RequestPanel';
import DecisionCard from './components/DecisionCard';
import AuditLog from './components/AuditLog';
import { fetchPolicy, fetchAudit } from './api/client';
import type { Policy, Proposal, AuditEvent } from './types';

export default function App() {
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [policyLoading, setPolicyLoading] = useState(true);

  const [activeProposal, setActiveProposal] = useState<Proposal | null>(null);

  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);

  // Load policy from backend
  const loadPolicy = useCallback(async () => {
    try {
      const data = await fetchPolicy();
      setPolicy(data);
    } catch (err) {
      console.error('Failed to load spending policy:', err);
    } finally {
      setPolicyLoading(false);
    }
  }, []);

  // Load audit trail from backend
  const loadAudit = useCallback(async () => {
    setAuditLoading(true);
    try {
      const data = await fetchAudit(25);
      setAuditEvents(data);
    } catch (err) {
      console.error('Failed to load audit events:', err);
    } finally {
      setAuditLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPolicy();
    loadAudit();
  }, [loadPolicy, loadAudit]);

  // Handler when a new shopping proposal is created
  const handleProposalCreated = (proposal: Proposal) => {
    setActiveProposal(proposal);
    loadAudit();
    loadPolicy();
  };

  // Handler when policy is modified via PolicyOverview editor
  const handlePolicyUpdated = (updated: Policy) => {
    setPolicy(updated);
    loadAudit();
  };

  return (
    <div className="app-wrapper">
      <Header />

      <main className="main-content">
        {/* Left column: policy summary/editor + natural-language request form */}
        <div className="col-left">
          <PolicyOverview
            policy={policy}
            loading={policyLoading}
            onPolicyUpdated={handlePolicyUpdated}
          />
          <RequestPanel onProposalCreated={handleProposalCreated} />
        </div>

        {/* Right column: active proposal / policy decision card + immutable audit log */}
        <div className="col-right">
          <DecisionCard proposal={activeProposal} />
          <AuditLog
            events={auditEvents}
            loading={auditLoading}
            onRefresh={loadAudit}
          />
        </div>
      </main>

      <footer
        style={{
          textAlign: 'center',
          padding: '1.25rem',
          borderTop: '1px solid var(--border-subtle)',
          fontSize: '0.75rem',
          color: 'var(--text-muted)',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          gap: '1rem',
          flexWrap: 'wrap',
        }}
      >
        <span>AgentPay Guard — PayPal AI Hackathon 2026 Prototype</span>
        <span>•</span>
        <span style={{ color: 'var(--accent)' }}>PayPal Sandbox — No real money</span>
        <span>•</span>
        <a
          href="https://github.com/amansheikh-techie/agentpay-guard"
          target="_blank"
          rel="noopener noreferrer"
          style={{ color: 'var(--text-secondary)', textDecoration: 'none' }}
        >
          GitHub Repository
        </a>
      </footer>
    </div>
  );
}
