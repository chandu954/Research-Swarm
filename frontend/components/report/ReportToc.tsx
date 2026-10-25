"use client";

import { ListOrdered } from "lucide-react";

import { cn } from "@/lib/utils";

export default function ReportToc({
  toc,
  active,
}: {
  toc: { index: number; heading: string }[];
  active: number;
}) {
  if (toc.length === 0) return null;

  const scrollTo = (index: number) => {
    document
      .getElementById(`section-${index}`)
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <nav
      aria-label="Report sections"
      className="sticky top-0 z-30 -mx-4 mb-8 border-b border-[var(--border)] bg-[color-mix(in_srgb,var(--bg)_90%,transparent)] px-4 py-2.5 backdrop-blur-xl sm:-mx-6 sm:px-6"
    >
      <div className="flex items-center gap-2 overflow-x-auto pb-0.5">
        <ListOrdered className="h-3.5 w-3.5 shrink-0 text-[var(--text-muted)]" />
        {toc.map(({ index, heading }) => (
          <button
            key={index}
            type="button"
            onClick={() => scrollTo(index)}
            className={cn(
              "shrink-0 rounded-full border px-2.5 py-1 text-[10px] font-medium transition-colors",
              active === index
                ? "border-[var(--accent-violet)]/40 bg-[var(--accent-violet)]/10 text-[var(--accent-violet)]"
                : "border-transparent text-[var(--text-muted)] hover:border-[var(--border)] hover:text-[var(--text-secondary)]",
            )}
          >
            {heading}
          </button>
        ))}
      </div>
    </nav>
  );
}
