"use client";

import {
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

import { scatterTriad, chartInk } from "@/lib/chart-colors";
import { useChartTheme } from "@/hooks/use-chart-theme";
import { formatPercent, formatRatio } from "@/lib/format";
import type { FrontierPoint, OptimalPortfolio } from "@/lib/api";

interface Props {
  points: FrontierPoint[];
  userPortfolio: FrontierPoint;
  maxSharpe: OptimalPortfolio;
  minVolatility: OptimalPortfolio;
}

interface TooltipRow {
  payload: { name: string; annual_return: number; annual_volatility: number; sharpe_ratio?: number };
}

function FrontierTooltip({ active, payload }: { active?: boolean; payload?: TooltipRow[] }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 shadow-lg shadow-black/10">
      <p className="text-xs text-muted-foreground">{p.name}</p>
      <p className="text-sm font-semibold tabular-nums">
        {formatPercent(p.annual_return)} return
      </p>
      <p className="text-xs tabular-nums text-muted-foreground">
        {formatPercent(p.annual_volatility)} volatility
        {p.sharpe_ratio !== undefined && ` · Sharpe ${formatRatio(p.sharpe_ratio)}`}
      </p>
    </div>
  );
}

export function EfficientFrontierChart({ points, userPortfolio, maxSharpe, minVolatility }: Props) {
  const mode = useChartTheme();
  const [userColor, sharpeColor, volColor] = scatterTriad[mode];
  const ink = chartInk.secondary[mode];
  const grid = chartInk.gridline[mode];

  // keep backend order (ascending return), sorting by volatility would fold the curve
  const curve = points.map((p) => ({ ...p, name: "Frontier" }));

  return (
    <div className="h-80 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid stroke={grid} strokeDasharray="0" vertical={false} />
          <XAxis
            type="number"
            dataKey="annual_volatility"
            name="Volatility"
            domain={[(min: number) => Math.max(0, min - 0.02), (max: number) => max + 0.02]}
            tickFormatter={(v) => formatPercent(v, 0)}
            stroke={ink}
            tick={{ fill: ink, fontSize: 12 }}
            axisLine={{ stroke: grid }}
            tickLine={false}
            label={{ value: "Volatility (annualized)", position: "insideBottom", offset: -4, fill: ink, fontSize: 12 }}
          />
          <YAxis
            type="number"
            dataKey="annual_return"
            name="Return"
            domain={[(min: number) => min - 0.02, (max: number) => max + 0.02]}
            tickFormatter={(v) => formatPercent(v, 0)}
            stroke={ink}
            tick={{ fill: ink, fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            width={48}
            label={{ value: "Return (annualized)", angle: -90, position: "insideLeft", fill: ink, fontSize: 12 }}
          />
          <ZAxis type="number" range={[140, 140]} />
          <Tooltip content={<FrontierTooltip />} cursor={{ stroke: grid }} />

          <Line
            data={curve}
            dataKey="annual_return"
            stroke={ink}
            strokeWidth={2}
            dot={false}
            isAnimationActive
            animationDuration={600}
            animationEasing="ease-out"
            name="Efficient frontier"
          />

          <Scatter
            data={[{ ...minVolatility, name: "Min. volatility" }]}
            fill={volColor}
            shape="diamond"
            isAnimationActive
            animationDuration={500}
          />
          <Scatter
            data={[{ ...maxSharpe, name: "Max Sharpe" }]}
            fill={sharpeColor}
            shape="star"
            isAnimationActive
            animationDuration={500}
          />
          <Scatter
            data={[{ ...userPortfolio, name: "Your portfolio" }]}
            fill={userColor}
            shape="circle"
            isAnimationActive
            animationDuration={500}
          />
        </ComposedChart>
      </ResponsiveContainer>

      <div className="mt-2 flex flex-wrap justify-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <LegendItem color={userColor} label="Your portfolio" />
        <LegendItem color={sharpeColor} label="Max Sharpe" />
        <LegendItem color={volColor} label="Min. volatility" />
        <LegendItem color={ink} label="Efficient frontier" line />
      </div>
    </div>
  );
}

function LegendItem({ color, label, line = false }: { color: string; label: string; line?: boolean }) {
  return (
    <span className="flex items-center gap-1.5">
      {line ? (
        <span className="h-0.5 w-3 rounded-full" style={{ backgroundColor: color }} />
      ) : (
        <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
      )}
      {label}
    </span>
  );
}
