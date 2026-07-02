"use client";

import { useEffect, useRef, useState } from "react";

/** Animate a number from 0 to `value` on mount / whenever value changes. */
export function useCountUp(value: number, durationMs = 900): number {
  const [display, setDisplay] = useState(0);
  const frame = useRef<number | null>(null);
  const fromRef = useRef(0);

  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const duration = reduce ? 0 : durationMs;

    const from = fromRef.current;
    const start = performance.now();
    const tick = (now: number) => {
      const t = duration <= 0 ? 1 : Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      const current = Math.round(from + (value - from) * eased);
      setDisplay(current);
      if (t < 1) {
        frame.current = requestAnimationFrame(tick);
      } else {
        fromRef.current = value;
      }
    };
    frame.current = requestAnimationFrame(tick);
    return () => {
      if (frame.current) cancelAnimationFrame(frame.current);
    };
  }, [value, durationMs]);

  return display;
}
