export const TRADING_DAYS_PER_YEAR = 252; // mirrors backend's analysis.TRADING_DAYS_PER_YEAR

export function formatPercent(fraction: number, decimals = 1): string {
  return `${(fraction * 100).toFixed(decimals)}%`;
}

export function formatSignedPercent(fraction: number, decimals = 1): string {
  const pct = fraction * 100;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(decimals)}%`;
}

export function formatRatio(value: number, decimals = 2): string {
  return value.toFixed(decimals);
}

// past +/-900% switch to "Nx" notation, otherwise huge tail percentiles look like a bug
export function formatGrowthMultiple(p: number): string {
  const pct = (p - 1) * 100;
  if (Math.abs(pct) < 900) {
    return `${pct > 0 ? "+" : ""}${pct.toFixed(0)}%`;
  }
  return `${new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(p)}x`;
}
