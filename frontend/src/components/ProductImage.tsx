// components/ProductImage.tsx — Visual product iconography
import React from 'react';

interface ProductImageProps {
  productId?: string;
  name?: string;
  category?: string;
  size?: 'sm' | 'md' | 'lg';
}

export const ProductImage: React.FC<ProductImageProps> = ({
  productId = '',
  name = '',
  category = '',
  size = 'md',
}) => {
  const dim = size === 'sm' ? 32 : size === 'lg' ? 64 : 48;
  const lower = `${productId} ${name} ${category}`.toLowerCase();

  const getIcon = () => {
    if (lower.includes('mouse')) {
      return (
        <svg width={dim} height={dim} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="6" y="3" width="12" height="18" rx="6" />
          <path d="M12 7v4" />
        </svg>
      );
    }
    if (lower.includes('keyboard')) {
      return (
        <svg width={dim} height={dim} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="2" y="5" width="20" height="14" rx="2" />
          <path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M6 14h.01M18 14h.01M10 14h4" />
        </svg>
      );
    }
    if (lower.includes('headset') || lower.includes('audio')) {
      return (
        <svg width={dim} height={dim} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M3 18v-6a9 9 0 0 1 18 0v6" />
          <path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z" />
        </svg>
      );
    }
    if (lower.includes('hub') || lower.includes('usb')) {
      return (
        <svg width={dim} height={dim} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="4" y="8" width="16" height="8" rx="2" />
          <path d="M8 12h.01M12 12h.01M16 12h.01M12 4v4M12 16v4" />
        </svg>
      );
    }
    if (lower.includes('webcam') || lower.includes('camera')) {
      return (
        <svg width={dim} height={dim} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="10" r="7" />
          <circle cx="12" cy="10" r="3" />
          <path d="M7 21h10M12 17v4" />
        </svg>
      );
    }
    if (lower.includes('lamp') || lower.includes('light')) {
      return (
        <svg width={dim} height={dim} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M9 21h6M12 3a6 6 0 0 0-6 6c0 2.22 1.2 4.16 3 5.2V17a1 1 0 0 0 1 1h4a1 1 0 0 0 1-1v-2.8c1.8-1.04 3-2.98 3-5.2a6 6 0 0 0-6-6z" />
        </svg>
      );
    }
    if (lower.includes('notebook') || lower.includes('pen')) {
      return (
        <svg width={dim} height={dim} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
          <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
        </svg>
      );
    }
    // Default package / shopping item
    return (
      <svg width={dim} height={dim} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
        <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
        <line x1="12" y1="22.08" x2="12" y2="12" />
      </svg>
    );
  };

  return (
    <div
      style={{
        width: dim,
        height: dim,
        borderRadius: 8,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(56, 189, 248, 0.08)',
        border: '1px solid rgba(56, 189, 248, 0.25)',
        color: '#38bdf8',
        flexShrink: 0,
      }}
    >
      {getIcon()}
    </div>
  );
};
