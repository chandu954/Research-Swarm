"use client";

import { ThemeProvider } from "next-themes";
import { useEffect, useState } from "react";
import { AuthProvider } from "@/lib/auth";
import { TenantProvider } from "@/lib/tenant";

export default function Providers({ children }: { children: React.ReactNode }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem={false}
      storageKey="research-swarm-theme"
      disableTransitionOnChange
    >
      <AuthProvider>
        <TenantProvider>
          {mounted ? children : <div style={{ visibility: "hidden" }}>{children}</div>}
        </TenantProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
