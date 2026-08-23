"use client";

import { motion } from "framer-motion";
import { AlertTriangle } from "lucide-react";

import { categorical, status as statusColors } from "@/lib/chart-colors";
import { useChartTheme } from "@/hooks/use-chart-theme";
import { formatPercent } from "@/lib/format";
import type { BreakdownSlice, FactorBreakdown } from "@/lib/api";

function BreakdownBars({ items }: { items: BreakdownSlice[] }) {
  const mode = useChartTheme();
  const palette = categorical[mode];
  const sorted = [...items].sort((a, b) => b.weight - a.weight);

  return (
    <ul className="space-y-2.5">
      {sorted.map((s, i) => (
        <li key={s.label} className="space-y-1">
          <div className="flex items-center justify-between text-xs">
            <span className="font-medium">{s.label}</span>
            <span className="tabular-nums text-muted-foreground">{formatPercent(s.weight, 0)}</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-muted">
            <motion.div
              className="h-full rounded-full"
              style={{ backgroundColor: palette[i % palette.length] }}
              initial={{ width: 0 }}
              animate={{ width: `${s.weight * 100}%` }}
              transition={{ duration: 0.4, ease: "easeOut", delay: i * 0.05 }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}

export function SectorBreakdown({ breakdown }: { breakdown: FactorBreakdown }) {
  const mode = useChartTheme();

  return (
    <div className="space-y-6">
      {breakdown.concentration_warnings.length > 0 && (
        <div className="flex items-start gap-2 rounded-lg border border-border bg-muted px-3 py-2.5">
          <AlertTriangle
            className="mt-0.5 size-3.5 shrink-0"
            style={{ color: statusColors.warning[mode] }}
          />
          <p className="text-xs text-muted-foreground">
            <span className="font-medium text-foreground">Concentration risk: </span>
            {breakdown.concentration_warnings
              .map((w) => `${w.label} (${formatPercent(w.weight, 0)})`)
              .join(", ")}{" "}
            {breakdown.concentration_warnings.length === 1 ? "makes" : "make"} up an outsized share
            of the portfolio.
          </p>
        </div>
      )}

      <div className="grid gap-6 sm:grid-cols-2">
        <div>
          <h4 className="mb-3 text-xs font-medium text-muted-foreground">By sector</h4>
          <BreakdownBars items={breakdown.sector} />
        </div>
        <div>
          <h4 className="mb-3 text-xs font-medium text-muted-foreground">By market cap</h4>
          <BreakdownBars items={breakdown.market_cap} />
        </div>
      </div>
    </div>
  );
}
