"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  Check,
  ChevronDown,
  Info,
  Sparkles,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  getAIInsights,
  getSuggestedAllocation,
  getTickerResearch,
  type AnalyzeResponse,
  type RiskProfile,
  type SuggestedAllocationResponse,
  type TickerResearchResponse,
} from "@/lib/api";
import { usePortfolioBuilder } from "@/lib/store";
import { formatPercent } from "@/lib/format";
import { cn } from "@/lib/utils";

const RISK_PROFILES: { value: RiskProfile; label: string }[] = [
  { value: "conservative", label: "Conservative" },
  { value: "balanced", label: "Balanced" },
  { value: "growth", label: "Growth" },
  { value: "aggressive", label: "Aggressive" },
];

function SourceBadge({ source }: { source: "llm" | "rule_based" }) {
  return (
    <Badge variant={source === "llm" ? "accent" : "outline"} className="text-[10px]">
      {source === "llm" ? "AI-generated" : "Rule-based"}
    </Badge>
  );
}

function InsightsSection({
  analysis,
  onInsightsLoaded,
}: {
  analysis: AnalyzeResponse;
  onInsightsLoaded?: (insights: string[]) => void;
}) {
  const [insights, setInsights] = useState<string[] | null>(null);
  const [source, setSource] = useState<"llm" | "rule_based">("rule_based");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getAIInsights(
      {
        holdings: analysis.holdings.map((h) => ({ ticker: h.ticker, weight: h.weight })),
        annual_return: analysis.portfolio.annual_return,
        annual_volatility: analysis.portfolio.annual_volatility,
        sharpe_ratio: analysis.portfolio.sharpe_ratio,
        sector_breakdown: analysis.factor_breakdown.sector,
        correlation: analysis.correlation,
      },
      { signal: controller.signal },
    )
      .then((r) => {
        setInsights(r.insights);
        setSource(r.source);
        onInsightsLoaded?.(r.insights);
      })
      .catch(() => {
        if (controller.signal.aborted) return;
        setError("Couldn't load insights right now.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analysis]);

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Risk insights</h3>
        {!loading && insights && <SourceBadge source={source} />}
      </div>

      {loading && (
        <div className="space-y-2">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-5/6" />
          <Skeleton className="h-4 w-3/4" />
        </div>
      )}

      {!loading && error && <p className="text-sm text-negative">{error}</p>}

      {!loading && insights && (
        <ul className="space-y-2">
          {insights.map((line, i) => (
            <motion.li
              key={i}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2, delay: i * 0.04 }}
              className="flex gap-2 text-sm leading-relaxed text-muted-foreground"
            >
              <Info className="mt-0.5 size-3.5 shrink-0 text-accent" />
              <span>{line}</span>
            </motion.li>
          ))}
        </ul>
      )}
    </section>
  );
}

function SuggestedAllocationSection({ analysis }: { analysis: AnalyzeResponse }) {
  const [profile, setProfile] = useState<RiskProfile | null>(null);
  const [result, setResult] = useState<SuggestedAllocationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [applied, setApplied] = useState(false);
  const applyWeights = usePortfolioBuilder((s) => s.applyWeights);

  function selectProfile(next: RiskProfile) {
    setProfile(next);
    setResult(null);
    setApplied(false);
    setLoading(true);
    getSuggestedAllocation({
      holdings: analysis.holdings.map((h) => ({
        ticker: h.ticker,
        annual_return: h.annual_return,
        annual_volatility: h.annual_volatility,
      })),
      risk_profile: next,
    })
      .then(setResult)
      .finally(() => setLoading(false));
  }

  return (
    <section className="space-y-3">
      <h3 className="text-sm font-semibold">Suggested allocation</h3>
      <p className="text-xs text-muted-foreground">
        Pick a risk profile to see how it would reweight your current holdings.
      </p>

      <div className="grid grid-cols-2 gap-2">
        {RISK_PROFILES.map((p) => (
          <Button
            key={p.value}
            size="sm"
            variant={profile === p.value ? "default" : "outline"}
            onClick={() => selectProfile(p.value)}
          >
            {p.label}
          </Button>
        ))}
      </div>

      {loading && (
        <div className="space-y-2 pt-1">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-2/3" />
        </div>
      )}

      <AnimatePresence>
        {!loading && result && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="space-y-3 overflow-hidden rounded-lg border border-border bg-muted/50 p-3"
          >
            <p className="text-xs text-muted-foreground">{result.rationale}</p>
            <ul className="space-y-1.5">
              {Object.entries(result.weights)
                .sort((a, b) => b[1] - a[1])
                .map(([ticker, weight]) => (
                  <li key={ticker} className="flex items-center justify-between text-sm">
                    <span className="font-medium">{ticker}</span>
                    <span className="tabular-nums text-muted-foreground">{formatPercent(weight, 0)}</span>
                  </li>
                ))}
            </ul>
            <Button
              size="sm"
              className="w-full"
              disabled={applied}
              onClick={() => {
                applyWeights(result.weights);
                setApplied(true);
              }}
            >
              {applied ? (
                <>
                  <Check className="size-3.5" />
                  Applied to builder
                </>
              ) : (
                "Apply to portfolio"
              )}
            </Button>
            {applied && (
              <p className="text-center text-xs text-muted-foreground">
                Head back to the builder and re-analyze to see the effect.
              </p>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}

function ResearchRow({ ticker }: { ticker: string }) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<TickerResearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggle() {
    const next = !open;
    setOpen(next);
    if (next && !data && !loading) {
      setLoading(true);
      setError(null);
      getTickerResearch(ticker)
        .then(setData)
        .catch(() => setError("Couldn't load research for this ticker."))
        .finally(() => setLoading(false));
    }
  }

  return (
    <div className="rounded-lg border border-border">
      <button
        type="button"
        onClick={toggle}
        className="flex w-full items-center justify-between px-3 py-2.5 text-left text-sm font-medium"
      >
        {ticker}
        <ChevronDown className={cn("size-4 text-muted-foreground transition-transform", open && "rotate-180")} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="overflow-hidden"
          >
            <div className="space-y-2 border-t border-border px-3 py-3">
              {loading && (
                <div className="space-y-2">
                  <Skeleton className="h-3.5 w-full" />
                  <Skeleton className="h-3.5 w-5/6" />
                </div>
              )}
              {!loading && error && <p className="text-xs text-negative">{error}</p>}
              {!loading && data && (
                <>
                  <div className="flex flex-wrap items-center gap-1.5">
                    <Badge variant="outline" className="text-[10px]">{data.sector}</Badge>
                    {data.trailing_pe && (
                      <Badge variant="outline" className="text-[10px]">P/E {data.trailing_pe.toFixed(1)}</Badge>
                    )}
                    <SourceBadge source={data.source} />
                  </div>
                  <p className="text-xs leading-relaxed text-muted-foreground">{data.summary}</p>
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function ResearchSection({ tickers }: { tickers: string[] }) {
  return (
    <section className="space-y-3">
      <h3 className="text-sm font-semibold">Holding research</h3>
      <div className="space-y-2">
        {tickers.map((t) => (
          <ResearchRow key={t} ticker={t} />
        ))}
      </div>
    </section>
  );
}

export function AIAssistantTrigger({ onClick }: { onClick: () => void }) {
  return (
    <Button variant="outline" onClick={onClick}>
      <Sparkles className="size-4 text-accent" />
      AI Assistant
    </Button>
  );
}

export function AIAssistantSidebar({
  open,
  onOpenChange,
  analysis,
  onInsightsLoaded,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  analysis: AnalyzeResponse;
  onInsightsLoaded?: (insights: string[]) => void;
}) {
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[2px]"
            onClick={() => onOpenChange(false)}
          />
          <motion.aside
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ duration: 0.25, ease: "easeOut" }}
            className="fixed inset-y-0 right-0 z-50 flex w-full max-w-sm flex-col border-l border-border bg-card shadow-2xl"
          >
            <div className="flex items-center justify-between border-b border-border px-4 py-4">
              <div className="flex items-center gap-2">
                <Sparkles className="size-4 text-accent" />
                <h2 className="text-sm font-semibold">AI Portfolio Assistant</h2>
              </div>
              <Button variant="ghost" size="icon" onClick={() => onOpenChange(false)} aria-label="Close">
                <X className="size-4" />
              </Button>
            </div>

            <div className="flex-1 space-y-8 overflow-y-auto px-4 py-5">
              <InsightsSection analysis={analysis} onInsightsLoaded={onInsightsLoaded} />
              <div className="border-t border-border pt-6">
                <SuggestedAllocationSection analysis={analysis} />
              </div>
              <div className="border-t border-border pt-6">
                <ResearchSection tickers={analysis.holdings.map((h) => h.ticker)} />
              </div>
            </div>

            <div className="flex items-start gap-2 border-t border-border px-4 py-3 text-[11px] text-muted-foreground">
              <AlertTriangle className="mt-0.5 size-3 shrink-0" />
              General analytics, not personalized financial advice.
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
