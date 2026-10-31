// App.tsx — Root layout, tab coordinator, and mission control for AgentPay Guard 2.0
import { useState, useEffect, useCallback } from 'react';
import './index.css';
import Header from './components/Header';
import PolicyOverview from './components/PolicyOverview';
import RequestPanel from './components/RequestPanel';
import DecisionCard from './components/DecisionCard';
import AuditLog from './components/AuditLog';
import { TabNav, type TabKey } from './components/TabNav';
import { OverviewTab } from './components/OverviewTab';
import { PermissionCenter } from './components/PermissionCenter';
import { ApprovalQueue } from './components/ApprovalQueue';
import { TransactionsTable } from './components/TransactionsTable';
import { ShoppingResults } from './components/ShoppingResults';
import { ApprovalConfirm } from './components/ApprovalConfirm';
import {
  fetchPolicy,
  fetchAudit,
  fetchSummary,
  fetchPaymentsList,
  fetchProducts,
  createOrder,
  captureOrder,
  cancelOrder,
} from './api/client';
import type { Policy, Proposal, AuditEvent, SummaryResponse, PaymentListItem, Product } from './types';

export default function App() {
  const [activeTab, setActiveTab] = useState<TabKey>(() => {
    const params = new URLSearchParams(window.location.search);
    const t = params.get('tab') as TabKey;
    if (['overview', 'shopping', 'permissions', 'approvals', 'transactions', 'audit'].includes(t)) {
      return t;
    }
    return 'overview';
  });

  // Core Data
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [policyLoading, setPolicyLoading] = useState(true);

  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [paymentsList, setPaymentsList] = useState<PaymentListItem[]>([]);

  const [activeProposal, setActiveProposal] = useState<Proposal | null>(null);

  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditFilter, setAuditFilter] = useState<string>('ALL');

  // Modals & In-flight actions
  const [showApprovalConfirm, setShowApprovalConfirm] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  // Load summary metrics
  const loadSummary = useCallback(async () => {
    try {
      const data = await fetchSummary();
      setSummary(data);
    } catch (err) {
      console.error('Failed to load summary metrics:', err);
    }
  }, []);

  // Load payments list
  const loadPayments = useCallback(async () => {
    try {
      const data = await fetchPaymentsList();
      setPaymentsList(data);
    } catch (err) {
      console.error('Failed to load payments ledger:', err);
    }
  }, []);

  // Load catalogue products
  const loadProducts = useCallback(async () => {
    try {
      const data = await fetchProducts();
      setProducts(data);
    } catch (err) {
      console.error('Failed to load products:', err);
    }
  }, []);

  // Load spending policy
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

  // Load audit trail with optional event type filter
  const loadAudit = useCallback(async (filter = auditFilter) => {
    setAuditLoading(true);
    try {
      const data = await fetchAudit(50, filter);
      setAuditEvents(data);
    } catch (err) {
      console.error('Failed to load audit events:', err);
    } finally {
      setAuditLoading(false);
    }
  }, [auditFilter]);

  // Initial load
  useEffect(() => {
    loadPolicy();
    loadSummary();
    loadPayments();
    loadProducts();
    loadAudit();
  }, [loadPolicy, loadSummary, loadPayments, loadProducts, loadAudit]);

  const handleTabChange = (tab: TabKey) => {
    setActiveTab(tab);
    const url = new URL(window.location.href);
    url.searchParams.set('tab', tab);
    window.history.replaceState({}, '', url.toString());
  };

  // Handle audit filter change
  const handleAuditFilterChange = (filter: string) => {
    setAuditFilter(filter);
    loadAudit(filter);
  };

  // Handler when a new shopping proposal is created
  const handleProposalCreated = (proposal: Proposal) => {
    setActiveProposal(proposal);
    setActiveTab('shopping');
    loadAudit();
    loadPolicy();
    loadSummary();
    loadPayments();
  };

  // Handler when policy is modified via PolicyOverview editor or PermissionCenter
  const handlePolicyUpdated = (updated: Policy) => {
    setPolicy(updated);
    loadSummary();
    loadAudit();
  };

  // Handler when payment capture succeeds
  const handlePaymentSuccess = () => {
    loadPolicy();
    loadSummary();
    loadPayments();
    loadAudit();
  };

  // Approval modal confirm handler
  const handleConfirmAuthorize = async () => {
    if (!activeProposal || !activeProposal.product) return;
    setActionLoading(true);
    try {
      const binding = {
        product_id: activeProposal.product.id,
        price_cents: activeProposal.product.price_cents,
        merchant_id: activeProposal.product.merchant_id,
        policy_version: policy?.policy_version || 1,
      };
      const res = await createOrder(activeProposal.id, binding);
      setShowApprovalConfirm(false);
      loadSummary();
      loadPayments();
      loadAudit();
      if (res.approve_url) {
        window.open(res.approve_url, '_blank');
      }
    } catch (err) {
      console.error('Order creation failed:', err);
      alert((err as Error).message || 'Failed to create order');
    } finally {
      setActionLoading(false);
    }
  };

  // Quick capture action from Approvals Queue
  const handleCaptureDirect = async (paypalOrderId: string) => {
    setActionLoading(true);
    try {
      await captureOrder(paypalOrderId);
      handlePaymentSuccess();
    } catch (err) {
      alert((err as Error).message || 'Failed to capture payment');
    } finally {
      setActionLoading(false);
    }
  };

  // Quick cancel action from Approvals Queue
  const handleCancelDirect = async (paypalOrderId: string) => {
    setActionLoading(true);
    try {
      await cancelOrder(paypalOrderId);
      loadSummary();
      loadPayments();
      loadAudit();
    } catch (err) {
      alert((err as Error).message || 'Failed to cancel order');
    } finally {
      setActionLoading(false);
    }
  };

  const pendingPayments = paymentsList.filter((p) =>
    ['pending', 'approved', 'capturing', 'needs_verification'].includes(p.status)
  );

  const pendingApprovalsCount =
    (activeProposal && activeProposal.policy_decision === 'ALLOWED' && activeProposal.status === 'pending' ? 1 : 0) +
    pendingPayments.length;

  return (
    <div className="app-wrapper">
      <Header />

      <TabNav
        activeTab={activeTab}
        onTabChange={handleTabChange}
        pendingCount={pendingApprovalsCount}
      />

      <main className="main-content">
        {/* Tab 1: Overview Mission Control */}
        {activeTab === 'overview' && (
          <OverviewTab
            policy={policy}
            summary={summary}
            onNavigateToShopping={() => setActiveTab('shopping')}
            onNavigateToPermissions={() => setActiveTab('permissions')}
          />
        )}

        {/* Tab 2: AI Shopping & Decision Flow */}
        {activeTab === 'shopping' && (
          <div className="shopping-tab-layout">
            <div className="col-left">
              <PolicyOverview
                policy={policy}
                loading={policyLoading}
                onPolicyUpdated={handlePolicyUpdated}
              />
              <RequestPanel onProposalCreated={handleProposalCreated} />
            </div>

            <div className="col-right">
              {activeProposal && (
                <ShoppingResults
                  proposal={activeProposal}
                  onSelectAlternative={setActiveProposal}
                  activeProposalId={activeProposal.id}
                />
              )}
              <DecisionCard
                proposal={activeProposal}
                onPaymentSuccess={handlePaymentSuccess}
                onSelectAlternative={setActiveProposal}
              />
            </div>
          </div>
        )}

        {/* Tab 3: Agent Permissions & Spending Limits */}
        {activeTab === 'permissions' && (
          <PermissionCenter
            policy={policy}
            products={products}
            onPolicyUpdated={handlePolicyUpdated}
          />
        )}

        {/* Tab 4: Approvals Queue */}
        {activeTab === 'approvals' && (
          <ApprovalQueue
            currentProposal={activeProposal}
            pendingPayments={pendingPayments}
            onOpenApproval={() => setShowApprovalConfirm(true)}
            onCaptureOrder={handleCaptureDirect}
            onCancelOrder={handleCancelDirect}
            loading={actionLoading}
          />
        )}

        {/* Tab 5: Payment Ledger & Transactions */}
        {activeTab === 'transactions' && (
          <TransactionsTable
            payments={paymentsList}
            onRefresh={loadPayments}
            loading={actionLoading}
          />
        )}

        {/* Tab 6: Immutable Audit Trail */}
        {activeTab === 'audit' && (
          <div className="audit-tab-wrapper">
            <AuditLog
              events={auditEvents}
              loading={auditLoading}
              onRefresh={() => loadAudit(auditFilter)}
              selectedFilter={auditFilter}
              onFilterChange={handleAuditFilterChange}
            />
          </div>
        )}
      </main>

      {/* Explicit Human Approval Confirmation Modal */}
      {activeProposal && showApprovalConfirm && (
        <ApprovalConfirm
          proposal={activeProposal}
          isOpen={showApprovalConfirm}
          onConfirm={handleConfirmAuthorize}
          onCancel={() => setShowApprovalConfirm(false)}
          loading={actionLoading}
        />
      )}

      <footer
        style={{
          textAlign: 'center',
          padding: '1.25rem 1rem',
          borderTop: '1px solid var(--border-subtle)',
          fontSize: '0.78rem',
          color: 'var(--text-secondary)',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          gap: '0.75rem',
          flexWrap: 'wrap',
          minWidth: 0,
          width: '100%',
        }}
      >
        <span>AgentPay Guard 2.0 — PayPal AI Hackathon 2026 Prototype</span>
        <span>•</span>
        <span style={{ color: 'var(--accent)' }}>PayPal Sandbox — No real money</span>
        <span>•</span>
        <a
          href="https://github.com/amansheikh-techie/agentpay-guard"
          target="_blank"
          rel="noopener noreferrer"
          style={{ color: 'var(--text-secondary)', textDecoration: 'underline' }}
        >
          GitHub Repository
        </a>
      </footer>
    </div>
  );
}
