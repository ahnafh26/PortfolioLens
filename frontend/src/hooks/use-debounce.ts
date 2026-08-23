import { useEffect, useState } from "react";

/** Delays reflecting `value` until it's stopped changing for `delayMs`.
 * Used to keep the ticker search from firing a network request on every
 * keystroke. */
export function useDebounce<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return debounced;
}
