"use client";

import { useEffect, useRef, useState } from "react";
import { LineSeries, createChart, type UTCTimestamp } from "lightweight-charts";
import { Info } from "lucide-react";

import { Button } from "@/components/ui/button";
import { InfoTooltip } from "@/components/InfoTooltip";
import { Skeleton } from "@/components/ui/skeleton";
import {
  backtestPortfolio,
  type BacktestPeriod,
  type BacktestResponse,
  type HoldingInput,
} from "@/lib/api";
import { categorical, chartInk, chartSurface, chartFontFamily } from "@/lib/chart-colors";
import { useChartTheme } from "@/hooks/use-chart-theme";
import { formatPercent, formatRatio, formatSignedPercent } from "@/lib/format";

const PERIODS: { value: BacktestPeriod; label: string }[] = [
  { value: "gfc_2008", label: "2008 Financial Crisis" },
  { value: "covid_2020", label: "2020 COVID Crash" },
  { value: "rate_hikes_2022", label: "2022 Rate Hikes" },
];

function Stat({ label, value, sub, tooltip }: { label: string; value: string; sub?: string; tooltip?: string }) {
  return (
    <div>
      <p className="flex items-center gap-1 text-xs text-muted-foreground">
        {label}
        {tooltip && (
          <InfoTooltip text={tooltip}>
            <Info className="size-3" />
          </InfoTooltip>
        )}
      </p>
      <p className="text-base font-semibold tabular-nums">{value}</p>
      {sub && <p className="text-xs tabular-nums text-muted-foreground">{sub}</p>}
    </div>
  );
}

function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="h-0.5 w-3 rounded-full" style={{ backgroundColor: color }} />
      {label}
    </span>
  );
}

export function BacktestChart({ holdings }: { holdings: HoldingInput[] }) {
  const [period, setPeriod] = useState<BacktestPeriod>("covid_2020");
  const [result, setResult] = useState<BacktestResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const mode = useChartTheme();

  useEffect(() => {
    const controller = new AbortController();
    backtestPortfolio({ holdings, period }, { signal: controller.signal })
      .then(setResult)
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : "Backtest failed");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [period]);

  function selectPeriod(next: BacktestPeriod) {
    setLoading(true);
    setError(null);
    setPeriod(next);
  }

  useEffect(() => {
    const container = containerRef.current;
    if (!result || !container) return;

    const portfolioColor = categorical[mode][0];
    const benchmarkColor = categorical[mode][1];
    const ink = chartInk.secondary[mode];
    const grid = chartInk.gridline[mode];
    const surface = chartSurface[mode];

    const chart = createChart(container, {
      width: container.clientWidth,
      height: 320,
      layout: { background: { color: surface }, textColor: ink, fontFamily: chartFontFamily, attributionLogo: false },
      grid: { vertLines: { visible: false }, horzLines: { color: grid } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
      localization: { priceFormatter: (p: number) => `${((p - 1) * 100).toFixed(0)}%` },
    });

    const portfolioSeries = chart.addSeries(LineSeries, { color: portfolioColor, lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
    const benchmarkSeries = chart.addSeries(LineSeries, { color: benchmarkColor, lineWidth: 2, priceLineVisible: false, lastValueVisible: false });

    const times = result.dates.map((d) => Math.floor(new Date(d).getTime() / 1000) as UTCTimestamp);
    portfolioSeries.setData(times.map((time, i) => ({ time, value: result.portfolio_path[i] })));
    benchmarkSeries.setData(times.map((time, i) => ({ time, value: result.benchmark_path[i] })));

    chart.timeScale().fitContent();

    const resizeObserver = new ResizeObserver(() => {
      if (container.clientWidth > 0) chart.applyOptions({ width: container.clientWidth });
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
    };
  }, [result, mode]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {PERIODS.map((p) => (
          <Button
            key={p.value}
            size="sm"
            variant={period === p.value ? "default" : "outline"}
            onClick={() => selectPeriod(p.value)}
          >
            {p.label}
          </Button>
        ))}
      </div>

      {loading && <Skeleton className="h-80 w-full" />}
      {!loading && error && <p className="text-sm text-negative">{error}</p>}

      {!loading && result && (
        <>
          <div ref={containerRef} className="h-80 w-full overflow-hidden rounded-lg" />

          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <LegendItem color={categorical[mode][0]} label="Your portfolio" />
            <LegendItem color={categorical[mode][1]} label="S&P 500 (SPY)" />
          </div>

          <div className="grid grid-cols-2 gap-4 border-t border-border pt-4 sm:grid-cols-4">
            <Stat
              label="Total return"
              value={formatSignedPercent(result.portfolio_total_return)}
              sub={`SPY ${formatSignedPercent(result.benchmark_total_return)}`}
            />
            <Stat
              label="Alpha"
              value={formatSignedPercent(result.alpha)}
              sub="annualized"
              tooltip="Return the portfolio generated beyond what its market exposure (beta) alone would predict. Positive means it beat its benchmark-implied return."
            />
            <Stat
              label="Beta"
              value={formatRatio(result.beta)}
              sub="vs SPY"
              tooltip="How much the portfolio tends to move for every 1% move in the S&P 500. Above 1 means more volatile than the market, below 1 means less."
            />
            <Stat
              label="Max drawdown"
              value={`-${formatPercent(result.portfolio_max_drawdown, 0)}`}
              sub={`SPY -${formatPercent(result.benchmark_max_drawdown, 0)}`}
              tooltip="The largest peak-to-trough decline the portfolio experienced during this period, before it recovered."
            />
          </div>

          {result.skipped_tickers.length > 0 && (
            <p className="text-xs text-muted-foreground">
              No price data for {result.skipped_tickers.join(", ")} during this period, excluded and
              the rest reweighted to 100%.
            </p>
          )}
        </>
      )}
    </div>
  );
}
