"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { token, isLoading: authLoading } = useAuth();
  const router = useRouter();
  const [checkingOrg, setCheckingOrg] = useState(true);

  useEffect(() => {
    if (authLoading) return;
    if (!token) {
      router.replace("/login");
      return;
    }
    async function checkOrg() {
      try {
        const res = await fetch(`${API_URL}/auth/org-status`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          if (!data.has_organization) {
            router.replace("/onboarding");
            return;
          }
        }
      } catch {}
      setCheckingOrg(false);
    }
    checkOrg();
  }, [token, authLoading, router]);

  if (authLoading || checkingOrg) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#0a0a0f]">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-violet-500 border-t-transparent" />
      </div>
    );
  }

  return <>{children}</>;
}
