import type { HoldingStats } from "@/lib/api";
import { formatCompactWeight, formatPercent, formatRatio } from "@/lib/format";
import { cn } from "@/lib/utils";

export function HoldingsTable({ holdings }: { holdings: HoldingStats[] }) {
  const sorted = [...holdings].sort((a, b) => b.weight - a.weight);

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs text-muted-foreground">
            <th className="py-2 pr-4 font-medium">Holding</th>
            <th className="py-2 pr-4 font-medium">Weight</th>
            <th className="py-2 pr-4 font-medium">Return</th>
            <th className="py-2 pr-4 font-medium">Volatility</th>
            <th className="py-2 font-medium">Sharpe</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((h) => (
            <tr key={h.ticker} className="border-b border-border/60 last:border-0">
              <td className="py-2.5 pr-4 font-medium">{h.ticker}</td>
              <td className="py-2.5 pr-4 tabular-nums text-muted-foreground">
                {formatCompactWeight(h.weight)}
              </td>
              <td
                className={cn(
                  "py-2.5 pr-4 tabular-nums",
                  h.annual_return >= 0 ? "text-positive" : "text-negative",
                )}
              >
                {formatPercent(h.annual_return)}
              </td>
              <td className="py-2.5 pr-4 tabular-nums text-muted-foreground">
                {formatPercent(h.annual_volatility)}
              </td>
              <td className="py-2.5 tabular-nums text-muted-foreground">
                {formatRatio(h.sharpe_ratio)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
