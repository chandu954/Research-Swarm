"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { motion } from "framer-motion";

export default function ThemeToggle() {
  const [dark, setDark] = useState(true);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const savedTheme = window.localStorage.getItem("research-swarm-theme");
    if (savedTheme === "light") setDark(false);
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    const root = document.documentElement;
    if (dark) {
      root.classList.add("dark");
      root.classList.remove("light");
    } else {
      root.classList.add("light");
      root.classList.remove("dark");
    }
    window.localStorage.setItem("research-swarm-theme", dark ? "dark" : "light");
  }, [dark, hydrated]);

  return (
    <button
      onClick={() => setDark(!dark)}
      className="relative w-9 h-9 rounded-xl flex items-center justify-center
                 text-text-muted hover:text-text-primary hover:bg-surface-hover
                 transition-all duration-200"
      aria-label="Toggle theme"
      aria-pressed={!dark}
    >
      <motion.div
        key={dark ? "moon" : "sun"}
        initial={{ rotate: -90, opacity: 0 }}
        animate={{ rotate: 0, opacity: 1 }}
        exit={{ rotate: 90, opacity: 0 }}
        transition={{ duration: 0.2 }}
      >
        {dark ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
      </motion.div>
    </button>
  );
}
