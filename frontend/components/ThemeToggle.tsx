"use client";

import { Moon } from "lucide-react";

// Light mode is disabled until the hardcoded white-alpha surfaces scattered
// across components are migrated to theme tokens. Forcing dark mode here keeps
// users from landing in a half-broken light theme.
export default function ThemeToggle() {
  return (
    <span
      className="icon-button h-8 w-8 cursor-default opacity-60"
      title="Dark mode only — light theme coming soon"
      aria-label="Dark mode only"
    >
      <Moon className="h-4 w-4" />
    </span>
  );
}
