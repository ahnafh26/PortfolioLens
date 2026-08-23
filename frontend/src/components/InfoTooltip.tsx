"use client";

import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

// CSS-only hover/focus, not JS pointer-event state: the browser tracks :hover and
// :focus-within itself, so this can never get stuck open the way a manually
// controlled Radix Popover could when a pointerleave was missed.
export function InfoTooltip({
  text,
  children,
  className,
}: {
  text: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span className="group/tooltip relative inline-flex">
      <button
        type="button"
        aria-label={text}
        className={cn(
          "inline-flex shrink-0 align-middle text-muted-foreground/70 transition-colors hover:text-muted-foreground",
          className,
        )}
        onKeyDown={(e) => {
          if (e.key === "Escape") e.currentTarget.blur();
        }}
      >
        {children}
      </button>
      <span
        aria-hidden="true"
        className="pointer-events-none absolute bottom-full left-1/2 z-50 mb-1.5 w-max max-w-56 -translate-x-1/2 scale-95 rounded-md border border-border bg-popover px-2.5 py-1.5 text-xs leading-snug text-popover-foreground opacity-0 shadow-md transition-[opacity,transform] duration-100 ease-out group-hover/tooltip:scale-100 group-hover/tooltip:opacity-100 group-focus-within/tooltip:scale-100 group-focus-within/tooltip:opacity-100"
      >
        {text}
      </span>
    </span>
  );
}
