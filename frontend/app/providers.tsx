"use client";

import { ThemeProvider } from "next-themes";
import { useEffect, useState } from "react";
import { AuthProvider } from "@/lib/auth";
import { TenantProvider } from "@/lib/tenant";
import { ConfirmProvider } from "@/lib/confirm-context";

export default function Providers({ children }: { children: React.ReactNode }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="dark"
      forcedTheme="dark"
      enableSystem={false}
      disableTransitionOnChange
    >
      <AuthProvider>
        <TenantProvider>
          <ConfirmProvider>
            {mounted ? children : <div style={{ visibility: "hidden" }}>{children}</div>}
          </ConfirmProvider>
        </TenantProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
