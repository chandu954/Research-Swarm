"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  BookOpen,
  ExternalLink,
  FileText,
  Globe2,
  Library,
} from "lucide-react";
import type { SourceCitation } from "@/lib/types";

interface SourcesProps {
  sources: SourceCitation[];
}

export default function Sources({ sources }: SourcesProps) {
  const webSources = sources.filter((source) => source.source_type === "web");
  const documentSources = sources.filter(
    (source) => source.source_type === "document",
  );

  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <BookOpen className="h-4 w-4 text-orange-400" />
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">
              Sources
            </h2>
          </div>
          <p className="mt-1 text-[10px] text-[var(--text-muted)]">
            Evidence attached to the answer
          </p>
        </div>
        {sources.length > 0 && (
          <span className="latency-badge">{sources.length} total</span>
        )}
      </div>

      {sources.length === 0 ? (
        <div className="flex items-center gap-2 rounded-xl border border-dashed border-[var(--border)] px-3 py-4">
          <Library className="h-4 w-4 text-[var(--text-muted)]" />
          <p className="text-[10px] text-[var(--text-muted)]">
            Citations will collect here as agents work.
          </p>
        </div>
      ) : (
        <div className="max-h-[320px] space-y-4 overflow-y-auto rounded-xl border border-[var(--border)] bg-white/[0.015] p-2">
          <AnimatePresence initial={false}>
            {webSources.map((source) => (
              <motion.a
                key={`web-${source.url || source.title}`}
                href={source.url}
                target="_blank"
                rel="noreferrer"
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                className="group flex items-start gap-2.5 rounded-lg p-2 transition-colors hover:bg-[var(--surface-hover)]"
              >
                <span className="mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg bg-cyan-500/10 text-cyan-400">
                  <Globe2 className="h-3.5 w-3.5" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[11px] text-[var(--text-secondary)] group-hover:text-[var(--text-primary)]">
                    {source.title}
                  </span>
                  <span className="mt-1 block truncate text-[9px] text-[var(--text-muted)]">
                    {source.url}
                  </span>
                </span>
                <ExternalLink className="mt-1 h-3 w-3 flex-shrink-0 text-[var(--text-muted)] opacity-0 transition-opacity group-hover:opacity-100" />
              </motion.a>
            ))}

            {documentSources.map((source) => (
              <motion.div
                key={`document-${source.title}-${source.relevance || ""}`}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                className="flex items-start gap-2.5 rounded-lg p-2"
              >
                <span className="mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-400">
                  <FileText className="h-3.5 w-3.5" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[11px] text-[var(--text-secondary)]">
                    {source.title}
                  </span>
                  {source.relevance && (
                    <span className="mt-1 block text-[9px] text-[var(--text-muted)]">
                      {source.relevance}
                    </span>
                  )}
                </span>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}
    </section>
  );
}
