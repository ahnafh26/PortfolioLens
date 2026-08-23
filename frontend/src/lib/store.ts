import { create } from "zustand";

import type { TickerSearchResult } from "@/lib/api";

export interface BuilderHolding {
  ticker: string;
  name: string;
  exchange: string;
  weightPct: number; // 0-100, not a fraction
}

interface PortfolioBuilderState {
  holdings: BuilderHolding[];
  lookbackYears: number;
  addHolding: (result: TickerSearchResult) => void;
  removeHolding: (ticker: string) => void;
  setWeightPct: (ticker: string, weightPct: number) => void;
  setLookbackYears: (years: number) => void;
  applyWeights: (weights: Record<string, number>) => void;
  reset: () => void;
}

// splits 100% evenly, remainder cents go to the first holding
function evenSplit(n: number): number[] {
  if (n === 0) return [];
  const base = Math.floor((100 / n) * 100) / 100;
  const shares = Array(n).fill(base);
  const remainder = Math.round((100 - base * n) * 100) / 100;
  shares[0] = Math.round((shares[0] + remainder) * 100) / 100;
  return shares;
}

export const usePortfolioBuilder = create<PortfolioBuilderState>((set) => ({
  holdings: [],
  lookbackYears: 5,

  addHolding: (result) =>
    set((state) => {
      if (state.holdings.some((h) => h.ticker === result.symbol)) return state;
      const holdings = [
        ...state.holdings,
        { ticker: result.symbol, name: result.name, exchange: result.exchange, weightPct: 0 },
      ];
      const splits = evenSplit(holdings.length);
      return { holdings: holdings.map((h, i) => ({ ...h, weightPct: splits[i] })) };
    }),

  removeHolding: (ticker) =>
    set((state) => {
      const holdings = state.holdings.filter((h) => h.ticker !== ticker);
      const splits = evenSplit(holdings.length);
      return { holdings: holdings.map((h, i) => ({ ...h, weightPct: splits[i] })) };
    }),

  setWeightPct: (ticker, weightPct) =>
    set((state) => ({
      holdings: state.holdings.map((h) =>
        h.ticker === ticker ? { ...h, weightPct: Math.max(0, weightPct) } : h,
      ),
    })),

  setLookbackYears: (years) => set({ lookbackYears: years }),

  applyWeights: (weights) =>
    set((state) => ({
      holdings: state.holdings.map((h) =>
        h.ticker in weights
          ? { ...h, weightPct: Math.round(weights[h.ticker] * 100 * 100) / 100 }
          : h,
      ),
    })),

  reset: () => set({ holdings: [], lookbackYears: 5 }),
}));

export function totalAllocatedPct(holdings: BuilderHolding[]): number {
  return Math.round(holdings.reduce((sum, h) => sum + h.weightPct, 0) * 100) / 100;
}
