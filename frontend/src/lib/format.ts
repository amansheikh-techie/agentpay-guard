// lib/format.ts — safe money & datetime formatting

export function formatCents(cents: number | undefined | null): string {
  if (cents === undefined || cents === null || isNaN(cents)) {
    return '$0.00';
  }
  return `$${(cents / 100).toFixed(2)}`;
}

export function formatDate(isoStr: string | undefined | null): string {
  if (!isoStr) return '';
  try {
    const d = new Date(isoStr);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return isoStr;
  }
}

export function formatDateTime(isoStr: string | undefined | null): string {
  if (!isoStr) return '';
  try {
    const d = new Date(isoStr);
    return `${d.toLocaleDateString()} ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
  } catch {
    return isoStr;
  }
}

