"use client";

import { Info, type LucideIcon } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { InfoTooltip } from "@/components/InfoTooltip";
import { Reveal } from "@/components/Reveal";
import { useCountUp } from "@/hooks/use-count-up";
import { cn } from "@/lib/utils";

type Tone = "auto" | "neutral" | "negative";

export interface StatCardProps {
  label: string;
  value: number; // fraction or ratio depending on format
  format: "percent" | "ratio";
  icon: LucideIcon;
  tone?: Tone;
  hint?: string;
  tooltip?: string;
}

function toneClass(tone: Tone, value: number): string {
  if (tone === "neutral") return "text-foreground";
  if (tone === "negative") return "text-negative";
  return value >= 0 ? "text-positive" : "text-negative";
}

export function StatCard({ label, value, format, icon: Icon, tone = "auto", hint, tooltip }: StatCardProps) {
  const animated = useCountUp(value);
  const display =
    format === "percent"
      ? tone === "negative"
        ? `-${Math.abs(animated * 100).toFixed(1)}%`
        : tone === "auto"
          ? `${animated > 0 ? "+" : ""}${(animated * 100).toFixed(1)}%`
          : `${(animated * 100).toFixed(1)}%`
      : animated.toFixed(2);

  return (
    <Reveal className="min-w-0">
      <Card>
        <CardContent className="p-5">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1 text-sm text-muted-foreground">
              {label}
              {tooltip && (
                <InfoTooltip text={tooltip}>
                  <Info className="size-3.5" />
                </InfoTooltip>
              )}
            </span>
            <Icon className="size-4 text-muted-foreground" />
          </div>
          <p className={cn("mt-2 text-2xl font-semibold tabular-nums", toneClass(tone, value))}>
            {display}
          </p>
          {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
        </CardContent>
      </Card>
    </Reveal>
  );
}

export function StatCardSkeleton() {
  return (
    <Card>
      <CardContent className="space-y-3 p-5">
        <div className="flex items-center justify-between">
          <Skeleton className="h-4 w-20" />
          <Skeleton className="size-4 rounded" />
        </div>
        <Skeleton className="h-7 w-24" />
      </CardContent>
    </Card>
  );
}
