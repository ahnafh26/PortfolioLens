"use client";

import { useTheme } from "next-themes";

import { useHasMounted } from "@/hooks/use-has-mounted";

// defaults to light until next-themes hydrates, avoids a mismatch flash
export function useChartTheme(): "light" | "dark" {
  const { resolvedTheme } = useTheme();
  const mounted = useHasMounted();
  return mounted && resolvedTheme === "dark" ? "dark" : "light";
}
