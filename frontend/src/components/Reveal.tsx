import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

// Plain CSS mount animation via tailwindcss-animate, no JS animation library involved.
export function Reveal({
  children,
  delayMs = 0,
  className,
}: {
  children: ReactNode;
  delayMs?: number;
  className?: string;
}) {
  return (
    <div
      className={cn("animate-in fade-in-0 slide-in-from-bottom-2 duration-300 ease-out", className)}
      style={delayMs ? { animationDelay: `${delayMs}ms` } : undefined}
    >
      {children}
    </div>
  );
}
