"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";

import { cn } from "@/lib/utils";

export default function SectionCard({
  level,
  heading,
  number,
  index,
  defaultOpen = true,
  children,
}: {
  level: number;
  heading: string | null;
  number?: string;
  index: number;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  if (!heading) {
    return <div className="scroll-mt-28">{children}</div>;
  }
  const HeadingTag = (level === 1 ? "h2" : level === 2 ? "h3" : "h4") as "h2" | "h3" | "h4";

  return (
    <section
      id={`section-${index}`}
      data-section-index={index}
      className="group/section scroll-mt-28 rounded-xl border border-transparent transition-colors hover:border-[var(--border)]"
    >
      <HeadingTag
        className="cursor-pointer select-none px-1 pt-1"
        onClick={() => setOpen((prev) => !prev)}
      >
        <span className="flex items-center gap-2.5">
          {number && (
            <span className="font-mono text-[10px] font-medium tracking-wide text-[var(--accent-violet)]">
              {number}
            </span>
          )}
          <ChevronDown
            className={cn(
              "h-4 w-4 shrink-0 text-[var(--text-tertiary)] transition-transform duration-200",
              !open && "-rotate-90",
            )}
          />
          {heading}
        </span>
      </HeadingTag>
      {open && <div className="px-1 pb-1">{children}</div>}
    </section>
  );
}
