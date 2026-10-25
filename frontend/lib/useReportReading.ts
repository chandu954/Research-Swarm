"use client";

import { useEffect, useState } from "react";

// Reading progress and section tracking live in their own hooks so scroll
// updates never re-render the report body.
export function useReadingProgress(): number {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const onScroll = () => {
      const doc = document.documentElement;
      const max = doc.scrollHeight - window.innerHeight;
      setProgress(max > 0 ? Math.min(1, Math.max(0, window.scrollY / max)) : 0);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, []);

  return progress;
}

export function useActiveSection(sectionCount: number): number {
  const [active, setActive] = useState(-1);

  useEffect(() => {
    if (sectionCount === 0) return;
    const elements = document.querySelectorAll<HTMLElement>("[data-section-index]");
    if (elements.length === 0) return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            const index = Number((entry.target as HTMLElement).dataset.sectionIndex);
            if (Number.isFinite(index)) setActive(index);
          }
        }
      },
      { rootMargin: "-12% 0px -72% 0px", threshold: 0 },
    );
    elements.forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, [sectionCount]);

  return active;
}
