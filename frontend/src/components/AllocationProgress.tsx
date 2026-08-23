"use client";

import { motion } from "framer-motion";
import { Check } from "lucide-react";

import { cn } from "@/lib/utils";

// only turns green at exactly 100%, over/under both stay neutral
export function AllocationProgress({ totalPct }: { totalPct: number }) {
  const isComplete = Math.abs(totalPct - 100) < 0.005;
  const isOver = totalPct > 100;

  return (
    <div className="flex items-center gap-3">
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
        <motion.div
          className={cn("h-full rounded-full", isComplete ? "bg-positive" : "bg-foreground/40")}
          initial={false}
          animate={{ width: `${Math.min(totalPct, 100)}%` }}
          transition={{ duration: 0.25, ease: "easeOut" }}
        />
      </div>
      <span
        className={cn(
          "flex shrink-0 items-center gap-1 text-sm font-medium tabular-nums",
          isComplete ? "text-positive" : "text-muted-foreground",
        )}
      >
        {isComplete && <Check className="size-3.5" />}
        {totalPct.toFixed(totalPct % 1 === 0 ? 0 : 1)}% allocated
        {isOver && !isComplete && " (over 100%)"}
      </span>
    </div>
  );
}
