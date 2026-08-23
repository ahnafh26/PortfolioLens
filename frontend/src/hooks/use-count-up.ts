import { useEffect, useRef, useState } from "react";
import { useReducedMotion } from "framer-motion";

export function useCountUp(target: number, durationMs = 900): number {
  const [value, setValue] = useState(target);
  const prefersReducedMotion = useReducedMotion();
  const fromRef = useRef(0);

  useEffect(() => {
    if (prefersReducedMotion) return;

    const from = fromRef.current;
    const delta = target - from;
    const start = performance.now();
    let frame: number;

    const tick = (now: number) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / durationMs, 1);
      const eased = 1 - Math.pow(1 - progress, 3); // cubic easeOut
      setValue(from + delta * eased);
      if (progress < 1) {
        frame = requestAnimationFrame(tick);
      } else {
        fromRef.current = target;
      }
    };

    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, durationMs, prefersReducedMotion]);

  return prefersReducedMotion ? target : value;
}
