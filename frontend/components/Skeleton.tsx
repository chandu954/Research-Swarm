import { cn } from "@/lib/utils";

interface SkeletonProps {
  className?: string;
  variant?: "text" | "card" | "circle" | "rect";
}

export default function Skeleton({ className, variant = "text" }: SkeletonProps) {
  return (
    <div
      className={cn(
        "animate-pulse rounded-md bg-white/[0.05]",
        variant === "text" && "h-4 w-full",
        variant === "card" && "h-24 w-full rounded-xl",
        variant === "circle" && "h-10 w-10 rounded-full",
        variant === "rect" && "h-32 w-full rounded-xl",
        className,
      )}
    />
  );
}

export function CardSkeleton() {
  return (
    <div className="space-y-3 rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
      <Skeleton variant="circle" className="h-8 w-8" />
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="h-3 w-1/2" />
    </div>
  );
}

export function ListSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="flex items-center gap-3">
          <Skeleton variant="circle" className="h-7 w-7" />
          <div className="flex-1 space-y-1.5">
            <Skeleton className="h-3 w-3/4" />
            <Skeleton className="h-2 w-1/2" />
          </div>
        </div>
      ))}
    </div>
  );
}
