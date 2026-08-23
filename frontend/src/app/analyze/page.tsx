"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  Download,
  FileText,
  Gauge,
  Info,
  Loader2,
  ShieldAlert,
  TrendingUp,
  Wallet,
  Waves,
} from "lucide-react";

import { SiteHeader } from "@/components/SiteHeader";
import { AIAssistantSidebar, AIAssistantTrigger } from "@/components/AIAssistantSidebar";
import { BacktestChart } from "@/components/BacktestChart";
import { ContagionGraph } from "@/components/ContagionGraph";
import { SectorBreakdown } from "@/components/SectorBreakdown";
import { RebalanceCalculator } from "@/components/RebalanceCalculator";
import { StatCard, StatCardSkeleton } from "@/components/StatCard";
import { InfoTooltip } from "@/components/InfoTooltip";
import { CorrelationHeatmap } from "@/components/CorrelationHeatmap";
import { EfficientFrontierChart } from "@/components/EfficientFrontierChart";
import { MonteCarloChart } from "@/components/MonteCarloChart";
import { AllocationDonut } from "@/components/AllocationDonut";
import { HoldingsTable } from "@/components/HoldingsTable";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { usePortfolioBuilder } from "@/lib/store";
import { analyzePortfolio, ApiError, exportCsv, exportPdf, type AnalyzeResponse } from "@/lib/api";

function ChartCardSkeleton({ title }: { title: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <Skeleton className="h-80 w-full" />
      </CardContent>
    </Card>
  );
}

const sectionMotion = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.3, ease: "easeOut" as const },
};

export default function AnalyzePage() {
  const holdings = usePortfolioBuilder((s) => s.holdings);
  const lookbackYears = usePortfolioBuilder((s) => s.lookbackYears);

  const [data, setData] = useState<AnalyzeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [aiSidebarOpen, setAiSidebarOpen] = useState(false);
  const [aiInsights, setAiInsights] = useState<string[] | null>(null);
  const [exporting, setExporting] = useState<"csv" | "pdf" | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const fetchAnalysis = useCallback((hs: typeof holdings, years: number) => {
    return analyzePortfolio({
      holdings: hs.map((h) => ({ ticker: h.ticker, weight: h.weightPct / 100 })),
      lookback_years: years,
    })
      .then(setData)
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (holdings.length === 0) return;
    fetchAnalysis(holdings, lookbackYears);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchAnalysis]);

  const retry = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchAnalysis(holdings, lookbackYears);
  }, [fetchAnalysis, holdings, lookbackYears]);

  async function handleExport(format: "csv" | "pdf") {
    if (!data) return;
    setExporting(format);
    setExportError(null);
    try {
      const fn = format === "csv" ? exportCsv : exportPdf;
      await fn({ analysis: data, ai_insights: aiInsights });
    } catch (err) {
      setExportError(err instanceof Error ? err.message : "Export failed. Please try again.");
    } finally {
      setExporting(null);
    }
  }

  if (holdings.length === 0) {
    return (
      <div className="flex flex-1 flex-col">
        <SiteHeader />
        <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center px-4 py-16 sm:px-6">
          <EmptyState
            icon={Wallet}
            title="No portfolio to analyze yet"
            description="Head back to the builder to add a few holdings first."
            action={
              <Button asChild>
                <Link href="/">
                  <ArrowLeft className="size-4" />
                  Back to builder
                </Link>
              </Button>
            }
          />
        </main>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col">
      <SiteHeader />
      <main className="mx-auto w-full max-w-6xl flex-1 space-y-6 px-4 py-8 sm:px-6">
        <div className="flex items-center justify-between">
          <Button variant="ghost" size="sm" asChild>
            <Link href="/">
              <ArrowLeft className="size-4" />
              Edit portfolio
            </Link>
          </Button>
          <div className="flex items-center gap-3">
            <span className="hidden text-sm text-muted-foreground sm:inline">
              {lookbackYears}-year lookback · {holdings.length}{" "}
              {holdings.length === 1 ? "holding" : "holdings"}
            </span>
            {!loading && data && (
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="icon"
                  disabled={exporting !== null}
                  onClick={() => handleExport("csv")}
                  aria-label="Export CSV"
                  title="Export CSV"
                >
                  {exporting === "csv" ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <Download className="size-4" />
                  )}
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  disabled={exporting !== null}
                  onClick={() => handleExport("pdf")}
                  aria-label="Export PDF"
                  title="Export PDF"
                >
                  {exporting === "pdf" ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <FileText className="size-4" />
                  )}
                </Button>
                <AIAssistantTrigger onClick={() => setAiSidebarOpen(true)} />
              </div>
            )}
          </div>
        </div>

        {exportError && <p className="text-right text-xs text-negative">{exportError}</p>}

        {data && (
          <AIAssistantSidebar
            open={aiSidebarOpen}
            onOpenChange={setAiSidebarOpen}
            analysis={data}
            onInsightsLoaded={setAiInsights}
          />
        )}

        {error && <ErrorState message={error} onRetry={retry} />}

        {!error && data?.skipped_tickers && data.skipped_tickers.length > 0 && (
          <div className="flex items-center gap-2 rounded-lg border border-border bg-muted px-4 py-3 text-sm text-muted-foreground">
            <Info className="size-4 shrink-0" />
            Couldn&apos;t find enough price history for{" "}
            <span className="font-medium text-foreground">{data.skipped_tickers.join(", ")}</span>
            {" "}, the rest of the portfolio was re-weighted to 100% without{" "}
            {data.skipped_tickers.length === 1 ? "it" : "them"}.
          </div>
        )}

        {!error && (
          <>
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              {loading || !data ? (
                <>
                  <StatCardSkeleton />
                  <StatCardSkeleton />
                  <StatCardSkeleton />
                  <StatCardSkeleton />
                </>
              ) : (
                <>
                  <StatCard
                    label="Annual return"
                    value={data.portfolio.annual_return}
                    format="percent"
                    icon={TrendingUp}
                    tone="auto"
                  />
                  <StatCard
                    label="Annual volatility"
                    tooltip="How much the portfolio's returns have swung around their average over the past year, annualized. Higher means a bumpier ride."
                    value={data.portfolio.annual_volatility}
                    format="percent"
                    icon={Waves}
                    tone="neutral"
                  />
                  <StatCard
                    label="Sharpe ratio"
                    tooltip="Return earned per unit of risk taken, relative to a risk-free rate. Higher means better risk-adjusted performance."
                    value={data.portfolio.sharpe_ratio}
                    format="ratio"
                    icon={Gauge}
                    tone="auto"
                  />
                  <StatCard
                    label="1yr 95% VaR"
                    tooltip="The worst loss you'd statistically expect in the bottom 5% of simulated years, a one-in-20 bad year, not a worst case."
                    value={data.portfolio.value_at_risk_95}
                    format="percent"
                    icon={ShieldAlert}
                    tone="negative"
                    hint="Worst 5% of simulated years"
                  />
                </>
              )}
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              {loading || !data ? (
                <ChartCardSkeleton title="Efficient frontier" />
              ) : (
                <motion.div {...sectionMotion} className="min-w-0">
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-1">
                        Efficient frontier
                        <InfoTooltip text="The set of portfolios giving the highest expected return for each level of risk. Points below the curve are leaving return on the table.">
                          <Info className="size-3.5" />
                        </InfoTooltip>
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <EfficientFrontierChart
                        points={data.efficient_frontier.points}
                        userPortfolio={data.efficient_frontier.user_portfolio}
                        maxSharpe={data.efficient_frontier.max_sharpe}
                        minVolatility={data.efficient_frontier.min_volatility}
                      />
                    </CardContent>
                  </Card>
                </motion.div>
              )}

              {loading || !data ? (
                <ChartCardSkeleton title="10-year simulation" />
              ) : (
                <motion.div
                  {...sectionMotion}
                  transition={{ ...sectionMotion.transition, delay: 0.05 }}
                  className="min-w-0"
                >
                  <Card>
                    <CardHeader>
                      <CardTitle>10-year Monte Carlo simulation</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <MonteCarloChart result={data.monte_carlo} />
                    </CardContent>
                  </Card>
                </motion.div>
              )}
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              {loading || !data ? (
                <ChartCardSkeleton title="Correlation" />
              ) : (
                <motion.div
                  {...sectionMotion}
                  transition={{ ...sectionMotion.transition, delay: 0.1 }}
                  className="min-w-0"
                >
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-1">
                        Correlation between holdings
                        <InfoTooltip text="How closely two holdings' daily returns move together, from -1 (opposite) to +1 (in lockstep). Near 0 means they move independently.">
                          <Info className="size-3.5" />
                        </InfoTooltip>
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <CorrelationHeatmap
                        tickers={data.correlation.tickers}
                        matrix={data.correlation.matrix}
                      />
                    </CardContent>
                  </Card>
                </motion.div>
              )}

              {loading || !data ? (
                <ChartCardSkeleton title="Holdings" />
              ) : (
                <motion.div
                  {...sectionMotion}
                  transition={{ ...sectionMotion.transition, delay: 0.15 }}
                  className="min-w-0"
                >
                  <Card>
                    <CardHeader>
                      <CardTitle>Holdings breakdown</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      <AllocationDonut
                        data={data.holdings.map((h) => ({ ticker: h.ticker, weight: h.weight }))}
                      />
                      <HoldingsTable holdings={data.holdings} />
                    </CardContent>
                  </Card>
                </motion.div>
              )}
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              {loading || !data ? (
                <ChartCardSkeleton title="Factor breakdown" />
              ) : (
                <motion.div
                  {...sectionMotion}
                  transition={{ ...sectionMotion.transition, delay: 0.2 }}
                  className="min-w-0"
                >
                  <Card>
                    <CardHeader>
                      <CardTitle>Sector &amp; market cap exposure</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <SectorBreakdown breakdown={data.factor_breakdown} />
                    </CardContent>
                  </Card>
                </motion.div>
              )}

              {loading || !data ? (
                <ChartCardSkeleton title="Rebalance calculator" />
              ) : (
                <motion.div
                  {...sectionMotion}
                  transition={{ ...sectionMotion.transition, delay: 0.25 }}
                  className="min-w-0"
                >
                  <Card>
                    <CardHeader>
                      <CardTitle>Rebalance calculator</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <RebalanceCalculator
                        holdings={data.holdings.map((h) => ({ ticker: h.ticker, weight: h.weight }))}
                      />
                    </CardContent>
                  </Card>
                </motion.div>
              )}
            </div>

            {!loading && data && (
              <motion.div {...sectionMotion} transition={{ ...sectionMotion.transition, delay: 0.3 }}>
                <Card>
                  <CardHeader>
                    <CardTitle>Historical stress test</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <BacktestChart
                      holdings={data.holdings.map((h) => ({ ticker: h.ticker, weight: h.weight }))}
                    />
                  </CardContent>
                </Card>
              </motion.div>
            )}

            {!loading && data && (
              <motion.div {...sectionMotion} transition={{ ...sectionMotion.transition, delay: 0.35 }}>
                <ContagionGraph
                  holdings={data.holdings.map((h) => ({ ticker: h.ticker, weight: h.weight }))}
                  lookbackYears={Math.min(lookbackYears, 5)}
                />
              </motion.div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
