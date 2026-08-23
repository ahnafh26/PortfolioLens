"use client";

import * as React from "react";
import * as PopoverPrimitive from "@radix-ui/react-popover";

import { cn } from "@/lib/utils";

const Popover = PopoverPrimitive.Root;
const PopoverTrigger = PopoverPrimitive.Trigger;
const PopoverAnchor = PopoverPrimitive.Anchor;

// Radix handles mount/unmount and exposes it via data-state, so the entrance
// animation is driven off that (same pattern as ui/select.tsx)
function PopoverContent({
  className,
  align = "start",
  sideOffset = 6,
  children,
  ...props
}: React.ComponentProps<typeof PopoverPrimitive.Content>) {
  return (
    <PopoverPrimitive.Portal>
      <PopoverPrimitive.Content
        align={align}
        sideOffset={sideOffset}
        className={cn(
          "z-50 w-72 animate-in rounded-xl border border-border bg-popover text-popover-foreground shadow-lg shadow-black/10 outline-none fade-in-0 zoom-in-95 slide-in-from-top-1 duration-150 ease-out",
          className,
        )}
        {...props}
      >
        {children}
      </PopoverPrimitive.Content>
    </PopoverPrimitive.Portal>
  );
}

export { Popover, PopoverTrigger, PopoverAnchor, PopoverContent };
