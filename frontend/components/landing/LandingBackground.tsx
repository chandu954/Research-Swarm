"use client";

import { useEffect, useRef } from "react";

const SECTION_GLOWS = [
  { top: "6%", left: "38%", size: 600, color: "#7c3aed", opacity: 0.13 },
  { top: "26%", left: "-8%", size: 520, color: "#2563eb", opacity: 0.1 },
  { top: "46%", left: "55%", size: 480, color: "#06b6d4", opacity: 0.08 },
  { top: "64%", left: "-6%", size: 460, color: "rgb(255 255 255)", opacity: 0.045 },
  { top: "78%", left: "52%", size: 500, color: "#fb923c", opacity: 0.07 },
  { top: "92%", left: "-8%", size: 520, color: "#10b981", opacity: 0.09 },
  { top: "106%", left: "30%", size: 560, color: "#7c3aed", opacity: 0.11 },
];

export default function LandingBackground() {
  const gridRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<HTMLDivElement>(null);
  const glowRefs = useRef<(HTMLDivElement | null)[]>([]);

  useEffect(() => {
    let raf = 0;
    const onScroll = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const y = window.scrollY;
        if (gridRef.current) {
          gridRef.current.style.transform = `translate3d(0, ${y * 0.045}px, 0)`;
        }
        if (mapRef.current) {
          mapRef.current.style.transform = `translate3d(0, ${y * 0.06}px, 0)`;
        }
        glowRefs.current.forEach((el, i) => {
          if (el) {
            const factor = 0.05 + (i % 3) * 0.025;
            el.style.transform = `translate3d(0, ${y * factor}px, 0)`;
          }
        });
      });
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => {
      window.removeEventListener("scroll", onScroll);
      cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <div className="landing-bg" aria-hidden="true">
      <div ref={gridRef} className="landing-grid" />
      <div ref={mapRef} className="landing-map" />
      {SECTION_GLOWS.map((glow, i) => (
        <div
          key={i}
          ref={(el) => {
            glowRefs.current[i] = el;
          }}
          className="section-glow"
          style={
            {
              top: glow.top,
              left: glow.left,
              width: glow.size,
              height: glow.size,
              background: glow.color,
              opacity: glow.opacity,
            } as React.CSSProperties
          }
        />
      ))}
    </div>
  );
}
