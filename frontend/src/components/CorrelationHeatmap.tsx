"use client";

import { useState } from "react";
import { motion } from "framer-motion";

import { correlationColor } from "@/lib/chart-colors";
import { useChartTheme } from "@/hooks/use-chart-theme";
import { cn } from "@/lib/utils";

export interface CorrelationMatrixData {
  tickers: string[];
  matrix: number[][];
}

function textColorFor(value: number): string {
  return Math.abs(value) > 0.55 ? "#ffffff" : "currentColor";
}

export function CorrelationHeatmap({ tickers, matrix }: CorrelationMatrixData) {
  const mode = useChartTheme();
  const [hovered, setHovered] = useState<{ row: number; col: number } | null>(null);
  const showInlineValues = tickers.length <= 8;
  const cellSize = tickers.length > 14 ? 32 : tickers.length > 8 ? 40 : 52;

  return (
    <div className="overflow-x-auto">
      <table className="border-separate" style={{ borderSpacing: 3 }}>
        <caption className="sr-only">Correlation matrix between portfolio holdings</caption>
        <thead>
          <tr>
            <th scope="col" />
            {tickers.map((t) => (
              <th
                key={t}
                scope="col"
                className="px-1 pb-1 text-center text-xs font-medium text-muted-foreground"
                style={{ width: cellSize }}
              >
                {t}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {tickers.map((rowTicker, i) => (
            <tr key={rowTicker}>
              <th
                scope="row"
                className="pr-2 text-right text-xs font-medium text-muted-foreground"
              >
                {rowTicker}
              </th>
              {tickers.map((colTicker, j) => {
                const value = matrix[i][j];
                const isHovered = hovered?.row === i && hovered?.col === j;
                return (
                  <td key={colTicker} className="p-0">
                    <motion.div
                      role="gridcell"
                      tabIndex={0}
                      aria-label={`${rowTicker} vs ${colTicker}: correlation ${value.toFixed(2)}`}
                      onMouseEnter={() => setHovered({ row: i, col: j })}
                      onMouseLeave={() => setHovered(null)}
                      onFocus={() => setHovered({ row: i, col: j })}
                      onBlur={() => setHovered(null)}
                      initial={{ opacity: 0, scale: 0.8 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ duration: 0.2, delay: (i + j) * 0.008, ease: "easeOut" }}
                      className={cn(
                        "relative flex items-center justify-center rounded-md text-[11px] font-medium tabular-nums outline-none transition-transform",
                        isHovered && "z-10 scale-110 ring-2 ring-ring",
                      )}
                      style={{
                        width: cellSize,
                        height: cellSize,
                        backgroundColor: correlationColor(value, mode),
                        color: textColorFor(value),
                      }}
                    >
                      {showInlineValues && value.toFixed(2)}
                    </motion.div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>

      <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
        <span>-1.0</span>
        <div
          className="h-2 w-32 rounded-full"
          style={{
            background: `linear-gradient(to right, ${correlationColor(-1, mode)}, ${correlationColor(0, mode)}, ${correlationColor(1, mode)})`,
          }}
        />
        <span>+1.0</span>
      </div>
    </div>
  );
}
