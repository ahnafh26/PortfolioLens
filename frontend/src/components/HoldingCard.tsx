"use client";

import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { IconClose } from "@/components/icons";
import type { BuilderHolding } from "@/lib/store";
import { usePortfolioBuilder } from "@/lib/store";

export function HoldingCard({ holding }: { holding: BuilderHolding }) {
  const setWeightPct = usePortfolioBuilder((s) => s.setWeightPct);
  const removeHolding = usePortfolioBuilder((s) => s.removeHolding);

  return (
    <div className="flex items-center gap-3 rounded border border-border bg-card p-3 pl-4">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-semibold tabular-nums">{holding.ticker}</span>
          <Badge variant="outline" className="px-1.5 py-0 text-[10px] font-normal">
            {holding.exchange}
          </Badge>
        </div>
        <p className="truncate text-xs text-muted-foreground">{holding.name}</p>
      </div>

      <div className="relative w-24 shrink-0">
        <Input
          type="number"
          inputMode="decimal"
          min={0}
          max={100}
          step={0.1}
          value={holding.weightPct}
          onChange={(e) => setWeightPct(holding.ticker, Number(e.target.value))}
          aria-label={`Weight for ${holding.ticker}`}
          className="pr-6 text-right font-mono tabular-nums"
        />
        <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 font-mono text-sm text-muted-foreground">
          %
        </span>
      </div>

      <Button
        variant="ghost"
        size="icon"
        className="shrink-0 text-muted-foreground hover:text-negative"
        onClick={() => removeHolding(holding.ticker)}
        aria-label={`Remove ${holding.ticker}`}
      >
        <IconClose className="size-4" />
      </Button>
    </div>
  );
}
