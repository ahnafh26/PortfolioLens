import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge conditional class names, letting later Tailwind classes win over
 * earlier conflicting ones (e.g. a caller's `className="p-4"` overriding a
 * component's default `p-2`). */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
