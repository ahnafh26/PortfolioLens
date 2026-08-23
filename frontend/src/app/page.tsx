"use client";

import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Wallet } from "lucide-react";

import { SiteHeader } from "@/components/SiteHeader";
import { TickerSearch } from "@/components/TickerSearch";
import { HoldingCard } from "@/components/HoldingCard";
import { AllocationProgress } from "@/components/AllocationProgress";
import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { usePortfolioBuilder, totalAllocatedPct } from "@/lib/store";

const LOOKBACK_OPTIONS = [1, 2, 3, 5, 7, 10, 15, 20];

export default function BuilderPage() {
  const router = useRouter();
  const holdings = usePortfolioBuilder((s) => s.holdings);
  const lookbackYears = usePortfolioBuilder((s) => s.lookbackYears);
  const setLookbackYears = usePortfolioBuilder((s) => s.setLookbackYears);

  const totalPct = totalAllocatedPct(holdings);
  const canAnalyze = holdings.length > 0 && Math.abs(totalPct - 100) < 0.005;

  return (
    <div className="flex flex-1 flex-col">
      <SiteHeader />

      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-8 px-4 py-12 sm:px-6 sm:py-20">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease: "easeOut" }}
          className="space-y-3 text-center"
        >
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            Build a portfolio. See its risk.
          </h1>
          <p className="mx-auto max-w-lg text-balance text-muted-foreground">
            Add a few holdings and PortfolioLens runs the numbers real quant desks
            use: volatility, Sharpe ratio, correlation, the efficient frontier, and
            a Monte Carlo simulation of where it could go.
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: "easeOut", delay: 0.08 }}
        >
          <Card>
            <CardHeader className="flex-row items-center justify-between gap-4 space-y-0 pb-4">
              <div className="flex items-center gap-2">
                <Wallet className="size-4 text-muted-foreground" />
                <span className="text-sm font-medium text-foreground">Your holdings</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="hidden text-sm text-muted-foreground sm:inline">
                  Lookback
                </span>
                <Select
                  value={String(lookbackYears)}
                  onValueChange={(v) => setLookbackYears(Number(v))}
                >
                  <SelectTrigger className="w-28">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {LOOKBACK_OPTIONS.map((y) => (
                      <SelectItem key={y} value={String(y)}>
                        {y} {y === 1 ? "year" : "years"}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </CardHeader>

            <CardContent className="space-y-5">
              {holdings.length === 0 ? (
                <EmptyState
                  icon={Wallet}
                  title="No holdings yet"
                  description="Search for a stock or ETF to start building your portfolio."
                  action={<TickerSearch />}
                />
              ) : (
                <>
                  <ul className="flex flex-col gap-2">
                    <AnimatePresence initial={false}>
                      {holdings.map((holding, i) => (
                        <motion.li
                          key={holding.ticker}
                          layout
                          initial={{ opacity: 0, y: -8, scale: 0.98 }}
                          animate={{ opacity: 1, y: 0, scale: 1 }}
                          exit={{ opacity: 0, scale: 0.96 }}
                          transition={{ duration: 0.2, ease: "easeOut", delay: i * 0.03 }}
                        >
                          <HoldingCard holding={holding} />
                        </motion.li>
                      ))}
                    </AnimatePresence>
                  </ul>

                  <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                    <TickerSearch />
                    <div className="sm:w-64">
                      <AllocationProgress totalPct={totalPct} />
                    </div>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </motion.div>

        <div className="flex justify-center">
          <Button
            size="lg"
            disabled={!canAnalyze}
            onClick={() => router.push("/analyze")}
            className="w-full sm:w-auto"
          >
            Analyze portfolio
            <ArrowRight className="size-4" />
          </Button>
        </div>
      </main>
    </div>
  );
}
