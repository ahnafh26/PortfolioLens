"use client";

import { useState } from "react";
import { ArrowDownRight, ArrowUpRight, Calculator, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { rebalancePortfolio, type HoldingInput, type RebalanceResponse } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Props {
  holdings: HoldingInput[];
}

export function RebalanceCalculator({ holdings }: Props) {
  const [totalValue, setTotalValue] = useState("10000");
  const [currentValues, setCurrentValues] = useState<Record<string, string>>({});
  const [result, setResult] = useState<RebalanceResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const parsedTotal = Number(totalValue);
  const canCalculate = Number.isFinite(parsedTotal) && parsedTotal > 0;

  function calculate() {
    if (!canCalculate) return;
    setLoading(true);
    setError(null);
    rebalancePortfolio({
      holdings: holdings.map((h) => ({
        ticker: h.ticker,
        weight: h.weight,
        current_value: Number(currentValues[h.ticker]) || 0,
      })),
      total_value: parsedTotal,
    })
      .then(setResult)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Couldn't calculate trades"))
      .finally(() => setLoading(false));
  }

  return (
    <div className="space-y-5">
      <div className="space-y-1.5">
        <Label htmlFor="rebalance-total">Total portfolio value</Label>
        <div className="relative">
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">
            $
          </span>
          <Input
            id="rebalance-total"
            type="number"
            inputMode="decimal"
            min={0}
            value={totalValue}
            onChange={(e) => setTotalValue(e.target.value)}
            className="pl-6 tabular-nums"
          />
        </div>
      </div>

      <details className="group">
        <summary className="cursor-pointer text-xs text-muted-foreground select-none">
          I already own some of these holdings (optional)
        </summary>
        <div className="mt-3 space-y-2">
          {holdings.map((h) => (
            <div key={h.ticker} className="flex items-center gap-2">
              <span className="w-16 shrink-0 text-xs font-medium">{h.ticker}</span>
              <div className="relative flex-1">
                <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">
                  $
                </span>
                <Input
                  type="number"
                  inputMode="decimal"
                  min={0}
                  placeholder="0"
                  value={currentValues[h.ticker] ?? ""}
                  onChange={(e) => setCurrentValues((prev) => ({ ...prev, [h.ticker]: e.target.value }))}
                  className="h-8 pl-6 text-xs tabular-nums"
                />
              </div>
            </div>
          ))}
        </div>
      </details>

      <Button size="sm" disabled={!canCalculate || loading} onClick={calculate} className="w-full sm:w-auto">
        {loading ? <Loader2 className="size-3.5 animate-spin" /> : <Calculator className="size-3.5" />}
        Calculate trades
      </Button>

      {error && <p className="text-sm text-negative">{error}</p>}

      {result && (
        <div className="animate-in space-y-3 fade-in-0 slide-in-from-top-1 duration-200 ease-out">
          {result.orders.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Already at target weights, no trades needed.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-muted-foreground">
                    <th className="py-2 pr-4 font-medium">Action</th>
                    <th className="py-2 pr-4 font-medium">Shares</th>
                    <th className="py-2 font-medium">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {result.orders.map((o) => (
                    <tr key={o.ticker} className="border-b border-border/60 last:border-0">
                      <td className="py-2.5 pr-4">
                        <span
                          className={cn(
                            "inline-flex items-center gap-1 font-medium",
                            o.action === "buy" ? "text-positive" : "text-negative",
                          )}
                        >
                          {o.action === "buy" ? (
                            <ArrowUpRight className="size-3.5" />
                          ) : (
                            <ArrowDownRight className="size-3.5" />
                          )}
                          {o.action === "buy" ? "Buy" : "Sell"} {o.ticker}
                        </span>
                      </td>
                      <td className="py-2.5 pr-4 tabular-nums text-muted-foreground">
                        {o.shares % 1 === 0 ? o.shares : o.shares.toFixed(2)}
                      </td>
                      <td className="py-2.5 tabular-nums">
                        ${o.dollar_amount.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {Math.abs(result.leftover_cash) >= 1 && (
            <p className="text-xs text-muted-foreground">
              {result.leftover_cash > 0
                ? `$${result.leftover_cash.toFixed(2)} left over after rounding to whole shares.`
                : `$${Math.abs(result.leftover_cash).toFixed(2)} more than the target value needed to round up to whole shares.`}
            </p>
          )}

          {result.skipped_tickers.length > 0 && (
            <p className="text-xs text-muted-foreground">
              Couldn&apos;t fetch a current price for {result.skipped_tickers.join(", ")}, excluded.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
