import type { ConfidenceLabel } from "@/lib/trust-scores";

// Shared confidence-pill styling used by report sources, citation chips, and
// the executive summary. Kept in one place so trust visuals stay consistent.
export const CONFIDENCE_PILL: Record<ConfidenceLabel, string> = {
  High: "border-emerald-400/25 bg-emerald-500/10 text-emerald-400",
  Medium: "border-amber-400/25 bg-amber-500/10 text-amber-400",
  Low: "border-rose-400/25 bg-rose-500/10 text-rose-400",
};
