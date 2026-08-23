"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Loader2, Plus, Search, TrendingUp } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Badge } from "@/components/ui/badge";
import { searchTickers, type TickerSearchResult } from "@/lib/api";
import { usePortfolioBuilder } from "@/lib/store";
import { useDebounce } from "@/hooks/use-debounce";
import { cn } from "@/lib/utils";

const ROW_HEIGHT = 52;
const LIST_MAX_HEIGHT = 320;

// splits text around the first match of query so we can bold it
function splitOnMatch(text: string, query: string): { chunk: string; matched: boolean }[] {
  if (!query) return [{ chunk: text, matched: false }];
  const idx = text.toLowerCase().indexOf(query.toLowerCase());
  if (idx === -1) return [{ chunk: text, matched: false }];
  return [
    { chunk: text.slice(0, idx), matched: false },
    { chunk: text.slice(idx, idx + query.length), matched: true },
    { chunk: text.slice(idx + query.length), matched: false },
  ].filter((s) => s.chunk.length > 0);
}

function Highlighted({ text, query }: { text: string; query: string }) {
  return (
    <>
      {splitOnMatch(text, query).map((s, i) =>
        s.matched ? (
          <mark key={i} className="rounded-sm bg-accent/20 text-accent">
            {s.chunk}
          </mark>
        ) : (
          <span key={i}>{s.chunk}</span>
        ),
      )}
    </>
  );
}

export function TickerSearch() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<TickerSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [highlightedIndex, setHighlightedIndex] = useState(0);

  const inputRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const holdings = usePortfolioBuilder((s) => s.holdings);
  const addHolding = usePortfolioBuilder((s) => s.addHolding);
  const heldTickers = useMemo(() => new Set(holdings.map((h) => h.ticker)), [holdings]);

  const debouncedQuery = useDebounce(query, 150);

  // aborts stale requests so a slow "A" response can't clobber "AAPL"'s
  useEffect(() => {
    if (!debouncedQuery.trim()) {
      setResults([]);
      setError(null);
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    searchTickers(debouncedQuery, { signal: controller.signal })
      .then((r) => {
        setResults(r);
        setHighlightedIndex(0);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : "Search failed");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [debouncedQuery]);

  const selectableResults = useMemo(
    () => results.filter((r) => !heldTickers.has(r.symbol)),
    [results, heldTickers],
  );

  // overscan = full cap so every row is mounted, keyboard nav can reach any of them
  const virtualizer = useVirtualizer({
    count: selectableResults.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 50,
  });

  function select(result: TickerSearchResult) {
    addHolding(result);
    setQuery("");
    setResults([]);
    setOpen(false);
    requestAnimationFrame(() => inputRef.current?.blur());
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!selectableResults.length) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlightedIndex((i) => {
        const next = (i + 1) % selectableResults.length;
        virtualizer.scrollToIndex(next, { align: "auto" });
        return next;
      });
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightedIndex((i) => {
        const next = (i - 1 + selectableResults.length) % selectableResults.length;
        virtualizer.scrollToIndex(next, { align: "auto" });
        return next;
      });
    } else if (e.key === "Enter") {
      e.preventDefault();
      const target = selectableResults[highlightedIndex];
      if (target) select(target);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) requestAnimationFrame(() => inputRef.current?.focus());
      }}
    >
      <PopoverTrigger asChild>
        <Button variant="outline" size="lg" className="border-dashed">
          <Plus className="size-4" />
          Add holding
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[340px] p-0" align="start">
        <div className="flex items-center gap-2 border-b border-border px-3">
          <Search className="size-4 shrink-0 text-muted-foreground" />
          <input
            ref={inputRef}
            role="combobox"
            aria-expanded={open}
            aria-controls="ticker-search-listbox"
            aria-activedescendant={
              selectableResults[highlightedIndex]
                ? `ticker-option-${selectableResults[highlightedIndex].symbol}`
                : undefined
            }
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Search symbol or company..."
            className="h-11 w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
          {loading && <Loader2 className="size-4 shrink-0 animate-spin text-muted-foreground" />}
        </div>

        {error && (
          <p className="px-3 py-4 text-sm text-negative">{error}</p>
        )}

        {!error && !loading && debouncedQuery && selectableResults.length === 0 && (
          <p className="px-3 py-6 text-center text-sm text-muted-foreground">
            No matches for &ldquo;{debouncedQuery}&rdquo;
          </p>
        )}

        {!error && !debouncedQuery && (
          <div className="flex flex-col items-center gap-2 px-3 py-8 text-center">
            <TrendingUp className="size-5 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              Search 11,000+ US-listed stocks &amp; ETFs
            </p>
          </div>
        )}

        {selectableResults.length > 0 && (
          <div
            ref={scrollRef}
            id="ticker-search-listbox"
            role="listbox"
            className="overflow-y-auto p-1"
            style={{ maxHeight: LIST_MAX_HEIGHT }}
          >
            <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
              {virtualizer.getVirtualItems().map((row) => {
                const result = selectableResults[row.index];
                const isHighlighted = row.index === highlightedIndex;
                return (
                  <button
                    key={result.symbol}
                    id={`ticker-option-${result.symbol}`}
                    role="option"
                    aria-selected={isHighlighted}
                    type="button"
                    onMouseEnter={() => setHighlightedIndex(row.index)}
                    onClick={() => select(result)}
                    style={{
                      position: "absolute",
                      top: 0,
                      left: 0,
                      width: "100%",
                      height: row.size,
                      transform: `translateY(${row.start}px)`,
                    }}
                    className={cn(
                      "flex flex-col justify-center rounded-lg px-2.5 text-left transition-colors",
                      isHighlighted && "bg-muted",
                    )}
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold tabular-nums">
                        <Highlighted text={result.symbol} query={debouncedQuery} />
                      </span>
                      <Badge variant="outline" className="px-1.5 py-0 text-[10px] font-normal">
                        {result.exchange}
                      </Badge>
                    </div>
                    <span className="truncate text-xs text-muted-foreground">
                      <Highlighted text={result.name} query={debouncedQuery} />
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
