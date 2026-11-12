/**
 * India-specific formatting helpers: IST timestamps and INR Lakh/Crore currency.
 */

export function formatIstTime(input?: string | Date | null): string {
  if (!input) return '--:--:-- IST';
  const dt = typeof input === 'string' ? new Date(input) : input;
  if (Number.isNaN(dt.getTime())) return String(input);
  const formatted = new Intl.DateTimeFormat('en-IN', {
    timeZone: 'Asia/Kolkata',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(dt);
  return `${formatted} IST`;
}

export function formatIstDateTime(input?: string | Date | null): string {
  if (!input) return '-- IST';
  const dt = typeof input === 'string' ? new Date(input) : input;
  if (Number.isNaN(dt.getTime())) return String(input);
  const formatted = new Intl.DateTimeFormat('en-IN', {
    timeZone: 'Asia/Kolkata',
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(dt);
  return `${formatted} IST`;
}

export function formatInrLakhCrore(amountInr: number): string {
  if (!Number.isFinite(amountInr) || amountInr <= 0) return '₹0';
  if (amountInr >= 10_000_000) {
    return `₹${(amountInr / 10_000_000).toFixed(2)} Cr`;
  }
  if (amountInr >= 100_000) {
    return `₹${(amountInr / 100_000).toFixed(2)} Lakh`;
  }
  return `₹${Math.round(amountInr).toLocaleString('en-IN')}`;
}

