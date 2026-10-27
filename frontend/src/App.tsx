// App.tsx — Root layout and dashboard coordinator
import './index.css';
import Header from './components/Header';
import PolicyOverview from './components/PolicyOverview';
import RequestPanel from './components/RequestPanel';
import DecisionCard from './components/DecisionCard';
import AuditLog from './components/AuditLog';

export default function App() {
  return (
    <div className="app-wrapper">
      <Header />

      <main className="main-content">
        {/* Left column: policy summary + request form */}
        <div className="col-left">
          <PolicyOverview />
          <RequestPanel />
        </div>

        {/* Right column: decision card + audit log */}
        <div className="col-right">
          <DecisionCard />
          <AuditLog />
        </div>
      </main>

      <footer style={{
        textAlign: 'center',
        padding: '1rem',
        borderTop: '1px solid var(--border-subtle)',
        fontSize: '0.75rem',
        color: 'var(--text-muted)',
      }}>
        AgentPay Guard — Hackathon Prototype &nbsp;|&nbsp;
        PayPal Sandbox — No real money &nbsp;|&nbsp;
        <a href="https://github.com/amansheikh-techie/agentpay-guard" target="_blank" rel="noopener noreferrer">
          GitHub
        </a>
      </footer>
    </div>
  );
}
