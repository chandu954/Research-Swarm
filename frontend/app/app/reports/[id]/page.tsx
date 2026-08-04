"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, FileQuestion } from "lucide-react";
import { getReportById, type ReportDetail } from "@/lib/supabase/query";
import ReportViewer from "@/components/ReportViewer";
import { ReportSkeleton } from "@/components/Skeletons";
import "../print.css";

export default function ReportPage() {
  const params = useParams<{ id: string }>();
  const [report, setReport] = useState<ReportDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [missing, setMissing] = useState(false);
  const reportId = params?.id;

  useEffect(() => {
    let cancelled = false;
    if (!reportId) {
      setLoading(false);
      setMissing(true);
      return;
    }
    getReportById(reportId).then((result) => {
      if (cancelled) return;
      if (!result || result.status !== "ready") {
        setMissing(true);
      } else {
        setReport(result);
      }
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [reportId]);

  return (
    <main
      className="min-h-screen"
      style={{
        backgroundColor: "var(--bg)",
        color: "var(--text-primary)",
      }}
    >
      {loading ? (
        <ReportSkeleton />
      ) : missing || !report ? (
        <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 px-6 text-center">
          <FileQuestion className="h-10 w-10 text-[var(--text-tertiary)]" />
          <div>
            <h1 className="text-lg font-semibold text-[var(--text-primary)]">
              Report not found
            </h1>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">
              It may have been deleted, or you don&apos;t have access to it.
            </p>
          </div>
          <Link
            href="/app"
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to workspace
          </Link>
        </div>
      ) : (
        <ReportViewer report={report} />
      )}
    </main>
  );
}
