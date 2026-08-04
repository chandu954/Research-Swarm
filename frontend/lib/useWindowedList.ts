"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface WindowedListResult<T> {
  containerRef: React.RefObject<HTMLDivElement | null>;
  virtualize: boolean;
  start: number;
  end: number;
  topPad: number;
  bottomPad: number;
  onScroll: () => void;
}

// Fixed-row-height windowing for long lists. Lists under `threshold` items
// render in full; larger lists render only the visible window plus overscan
// so the DOM never grows unbounded (sources, activity logs).
export function useWindowedList<T>(
  items: readonly T[],
  rowHeight: number,
  threshold = 60,
  overscan = 6,
): WindowedListResult<T> {
  const containerRef = useRef<HTMLDivElement>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const virtualize = items.length > threshold;

  const onScroll = useCallback(() => {
    setScrollTop(containerRef.current?.scrollTop ?? 0);
  }, []);

  useEffect(() => {
    if (!virtualize) {
      setScrollTop(0);
      return;
    }
    const el = containerRef.current;
    if (!el) return;
    setScrollTop(el.scrollTop);
  }, [virtualize, items.length]);

  if (!virtualize) {
    return {
      containerRef,
      virtualize: false,
      start: 0,
      end: items.length,
      topPad: 0,
      bottomPad: 0,
      onScroll,
    };
  }

  const height = containerRef.current?.clientHeight ?? 400;
  const start = Math.max(0, Math.floor(scrollTop / rowHeight) - overscan);
  const end = Math.min(
    items.length,
    Math.ceil((scrollTop + height) / rowHeight) + overscan,
  );

  return {
    containerRef,
    virtualize: true,
    start,
    end,
    topPad: start * rowHeight,
    bottomPad: (items.length - end) * rowHeight,
    onScroll,
  };
}
