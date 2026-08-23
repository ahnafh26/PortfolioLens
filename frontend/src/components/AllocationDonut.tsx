"use client";

import { useMemo } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import { categorical, chartInk } from "@/lib/chart-colors";
import { useChartTheme } from "@/hooks/use-chart-theme";
import { formatPercent } from "@/lib/format";

export interface AllocationSlice {
  ticker: string;
  weight: number; // 0-1 fraction
}

const MAX_SLICES = 8; // palette only has 8 colors

function withOtherBucket(slices: AllocationSlice[]): AllocationSlice[] {
  if (slices.length <= MAX_SLICES) return slices;
  const sorted = [...slices].sort((a, b) => b.weight - a.weight);
  const top = sorted.slice(0, MAX_SLICES - 1);
  const rest = sorted.slice(MAX_SLICES - 1);
  const otherWeight = rest.reduce((sum, s) => sum + s.weight, 0);
  return [...top, { ticker: "Other", weight: otherWeight }];
}

interface TooltipPayloadItem {
  payload: AllocationSlice & { color: string };
}

function DonutTooltip({ active, payload }: { active?: boolean; payload?: TooltipPayloadItem[] }) {
  if (!active || !payload?.length) return null;
  const slice = payload[0].payload;
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 shadow-lg shadow-black/10">
      <div className="flex items-center gap-2">
        <span
          className="h-2 w-2 rounded-full"
          style={{ backgroundColor: slice.color }}
          aria-hidden
        />
        <span className="text-xs text-muted-foreground">{slice.ticker}</span>
      </div>
      <p className="mt-0.5 text-sm font-semibold tabular-nums">{formatPercent(slice.weight)}</p>
    </div>
  );
}

export function AllocationDonut({ data }: { data: AllocationSlice[] }) {
  const mode = useChartTheme();
  const palette = categorical[mode];
  const ink = chartInk.secondary[mode];

  const slices = useMemo(() => withOtherBucket(data), [data]);
  const colored = slices.map((s, i) => ({ ...s, color: palette[i % palette.length] }));

  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
      <div className="h-48 w-48 shrink-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={colored}
              dataKey="weight"
              nameKey="ticker"
              innerRadius="65%"
              outerRadius="100%"
              paddingAngle={2}
              cornerRadius={3}
              strokeWidth={0}
              isAnimationActive
              animationDuration={500}
              animationEasing="ease-out"
            >
              {colored.map((s) => (
                <Cell key={s.ticker} fill={s.color} />
              ))}
            </Pie>
            <Tooltip content={<DonutTooltip />} />
          </PieChart>
        </ResponsiveContainer>
      </div>

      <ul className="grid flex-1 grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-1">
        {colored.map((s) => (
          <li key={s.ticker} className="flex items-center justify-between gap-2 text-sm">
            <span className="flex min-w-0 items-center gap-2">
              <span
                className="h-2.5 w-2.5 shrink-0 rounded-full"
                style={{ backgroundColor: s.color }}
                aria-hidden
              />
              <span className="truncate font-medium">{s.ticker}</span>
            </span>
            <span className="shrink-0 tabular-nums" style={{ color: ink }}>
              {formatPercent(s.weight)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
