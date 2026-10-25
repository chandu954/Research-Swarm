"use client";

import Image from "next/image";
import { ExternalLink, ShieldCheck } from "lucide-react";

import { CONFIDENCE_PILL } from "@/lib/confidence-pill";
import {
  authorityStars,
  classifySourceType,
  confidenceLabel,
  faviconUrl,
  getConfidence,
  getTrustScore,
} from "@/lib/trust-scores";
import { cn } from "@/lib/utils";
import type { SourceCitation } from "@/lib/types";
import SourceTypeBadge from "../SourceTypeBadge";

export default function ReferenceCard({
  entry,
  source,
  usedIn,
}: {
  entry: { index: number; title: string; url?: string; description?: string };
  source?: SourceCitation;
  usedIn: string[];
}) {
  const trust = getTrustScore(source?.url ?? entry.url, source?.title ?? entry.title);
  const confidence = getConfidence(trust.authority, trust.relevance);
  const label = confidenceLabel(confidence);
  const url = source?.url ?? entry.url;
  const iconSrc = faviconUrl(url);
  const type = classifySourceType({ url, provider: source?.provider });

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="group flex items-start gap-3 rounded-xl border border-[var(--border)] bg-[color-mix(in_srgb,var(--surface-hover)_20%,transparent)] p-3.5 transition-all hover:-translate-y-px hover:border-[var(--accent-violet)]/40 hover:bg-[var(--accent-violet)]/5"
    >
      <span className="flex h-10 w-10 flex-shrink-0 items-center justify-center overflow-hidden rounded-lg border border-[var(--border)] bg-white/[0.04]">
        {iconSrc ? (
          <Image
            src={iconSrc}
            alt=""
            width={20}
            height={20}
            unoptimized
            className="h-5 w-5 object-contain"
          />
        ) : (
          <span className="text-[10px] font-bold text-cyan-300">
            {(entry.title.trim().charAt(0) || "?").toUpperCase()}
          </span>
        )}
      </span>

      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="font-mono text-[9px] font-medium text-[var(--text-tertiary)]">
            #{String(entry.index).padStart(2, "0")}
          </span>
          <span className="min-w-0 truncate text-[13px] font-semibold text-[var(--text-primary)] transition-colors group-hover:text-[var(--accent-violet)]">
            {entry.title}
          </span>
          <SourceTypeBadge type={type} />
          <span
            className={cn(
              "ml-auto inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[9px] font-medium",
              CONFIDENCE_PILL[label],
            )}
          >
            <ShieldCheck className="h-2.5 w-2.5" />
            {confidence}% · {label}
          </span>
        </span>
        <span className="mt-1 flex items-center gap-1.5 text-[10px] text-[var(--text-tertiary)]">
          <span className="truncate">{url?.replace(/^https?:\/\/(www\.)?/, "") ?? trust.domain}</span>
          <span aria-hidden>·</span>
          <span className="text-yellow-500/60">{authorityStars(trust.authority)}</span>
        </span>
        {entry.description && (
          <span className="mt-1.5 block line-clamp-2 text-[10px] leading-relaxed text-[var(--text-secondary)]">
            {entry.description}
          </span>
        )}
        {usedIn.length > 0 && (
          <span className="mt-2 flex flex-wrap items-center gap-1.5">
            <span className="text-[8px] uppercase tracking-wider text-[var(--text-tertiary)]">
              Used in
            </span>
            {usedIn.slice(0, 3).map((heading) => (
              <span
                key={heading}
                className="rounded-sm border border-[var(--border)] bg-white/[0.03] px-1.5 py-0.5 text-[9px] text-[var(--text-secondary)]"
              >
                {heading}
              </span>
            ))}
            {usedIn.length > 3 && (
              <span className="text-[9px] text-[var(--text-tertiary)]">+{usedIn.length - 3}</span>
            )}
          </span>
        )}
      </span>
      <ExternalLink className="mt-1 h-3.5 w-3.5 flex-shrink-0 text-[var(--text-muted)] transition-colors group-hover:text-[var(--accent-violet)]" />
    </a>
  );
}
