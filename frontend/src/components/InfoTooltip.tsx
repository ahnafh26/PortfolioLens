"use client";

import * as React from "react";
import * as PopoverPrimitive from "@radix-ui/react-popover";
import { motion } from "framer-motion";

import { cn } from "@/lib/utils";

export function InfoTooltip({
  text,
  children,
  className,
}: {
  text: string;
  children: React.ReactNode;
  className?: string;
}) {
  const [open, setOpen] = React.useState(false);

  return (
    <PopoverPrimitive.Root open={open} onOpenChange={setOpen}>
      <PopoverPrimitive.Trigger asChild>
        <button
          type="button"
          aria-label={text}
          className={cn("inline-flex shrink-0 align-middle text-muted-foreground/70 transition-colors hover:text-muted-foreground", className)}
          // don't add onClick, Radix already toggles it and doubling up breaks tap-to-open on mobile
          onMouseEnter={() => setOpen(true)}
          onMouseLeave={() => setOpen(false)}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
        >
          {children}
        </button>
      </PopoverPrimitive.Trigger>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content side="top" align="center" sideOffset={6} asChild onOpenAutoFocus={(e) => e.preventDefault()}>
          <motion.div
            initial={{ opacity: 0, scale: 0.97, y: 2 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ duration: 0.12, ease: "easeOut" }}
            className="z-50 max-w-56 rounded-md border border-border bg-popover px-2.5 py-1.5 text-xs leading-snug text-popover-foreground shadow-md outline-none"
          >
            {text}
          </motion.div>
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  );
}
