"use client";

// Premium skeleton panels shown while lazy-loaded visualizations mount.
// Sized to match the real component so nothing shifts when content arrives.

function ShimmerBar({ className }: { className: string }) {
  return <div className={`animate-pulse rounded bg-[var(--border)] ${className}`} />;
}

export function KnowledgeGraphSkeleton() {
  return (
    <section className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface)]">
      <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
        <div className="flex items-center gap-2">
          <ShimmerBar className="h-4 w-4 rounded-md" />
          <ShimmerBar className="h-3 w-28" />
        </div>
        <ShimmerBar className="h-3 w-16" />
      </div>
      <div className="flex items-center gap-2 border-b border-[var(--border)] px-3 py-2">
        <ShimmerBar className="h-4 w-4" />
        <ShimmerBar className="h-4 flex-1" />
        <ShimmerBar className="h-4 w-8" />
      </div>
      <div className="flex h-[350px] items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <ShimmerBar className="h-10 w-10 rounded-xl" />
          <ShimmerBar className="h-3 w-40" />
        </div>
      </div>
    </section>
  );
}

export function PanelSkeleton({ height = 240 }: { height?: number }) {
  return (
    <div
      className="w-full animate-pulse space-y-2 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4"
      style={{ height }}
      role="status"
      aria-label="Loading"
    >
      <ShimmerBar className="h-3 w-1/3" />
      <ShimmerBar className="h-3 w-2/3" />
      <ShimmerBar className="h-3 w-1/2" />
    </div>
  );
}

export function ReportSkeleton() {
  return (
    <div className="mx-auto max-w-3xl animate-pulse space-y-3 px-6 py-10" role="status" aria-label="Loading report">
      <ShimmerBar className="h-3 w-40" />
      <ShimmerBar className="h-8 w-3/4" />
      <ShimmerBar className="h-3 w-52" />
      <div className="space-y-2 pt-4">
        <ShimmerBar className="h-3 w-full" />
        <ShimmerBar className="h-3 w-11/12" />
        <ShimmerBar className="h-3 w-4/5" />
      </div>
    </div>
  );
}
