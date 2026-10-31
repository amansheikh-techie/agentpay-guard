// components/TabNav.tsx — Navigation tabs for AgentPay Guard 2.0
import React from 'react';

export type TabKey = 'overview' | 'shopping' | 'permissions' | 'approvals' | 'transactions' | 'audit';

interface TabNavProps {
  activeTab: TabKey;
  onTabChange: (tab: TabKey) => void;
  pendingCount?: number;
}

export const TabNav: React.FC<TabNavProps> = ({ activeTab, onTabChange, pendingCount = 0 }) => {
  const tabs: { key: TabKey; label: string; badge?: number }[] = [
    { key: 'overview', label: 'Overview' },
    { key: 'shopping', label: 'AI Shopping' },
    { key: 'permissions', label: 'Permissions' },
    { key: 'approvals', label: 'Approvals', badge: pendingCount > 0 ? pendingCount : undefined },
    { key: 'transactions', label: 'Transactions' },
    { key: 'audit', label: 'Audit Log' },
  ];

  return (
    <nav className="tab-navigation" aria-label="Main Navigation">
      <div className="tab-bar">
        {tabs.map((tab) => {
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              className={`tab-btn ${isActive ? 'active' : ''}`}
              onClick={() => onTabChange(tab.key)}
              aria-selected={isActive}
              role="tab"
            >
              <span>{tab.label}</span>
              {tab.badge !== undefined && (
                <span className="tab-badge">{tab.badge}</span>
              )}
            </button>
          );
        })}
      </div>
    </nav>
  );
};
