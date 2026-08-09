import type { SourceType } from "@/lib/trust-scores";
import { cn } from "@/lib/utils";

const SOURCE_TYPE_STYLES: Record<SourceType, string> = {
  Official: "border-emerald-400/25 bg-emerald-500/10 text-emerald-400",
  Docs: "border-cyan-400/25 bg-cyan-500/10 text-cyan-400",
  Paper: "border-violet-400/25 bg-violet-500/10 text-violet-300",
  Blog: "border-amber-400/25 bg-amber-500/10 text-amber-400",
  GitHub: "border-[var(--border-strong)] bg-white/[0.04] text-[var(--text-secondary)]",
  Web: "border-[var(--border)] bg-white/[0.03] text-[var(--text-tertiary)]",
};

export default function SourceTypeBadge({
  type,
  className,
}: {
  type: SourceType;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded-md border px-1.5 py-0.5 text-[9px] font-medium leading-none",
        SOURCE_TYPE_STYLES[type],
        className,
      )}
    >
      {type}
    </span>
  );
}