"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Wifi, WifiOff, KeyRound } from "lucide-react";

type HealthStatus = "checking" | "connected" | "disconnected" | "no_key";

interface ProviderHealthProps {
  provider: "ollama" | "openrouter";
  openrouterKey: string;
}

export default function ProviderHealth({ provider, openrouterKey }: ProviderHealthProps) {
  const [status, setStatus] = useState<HealthStatus>("checking");
  const [label, setLabel] = useState("Checking...");

  useEffect(() => {
    if (provider === "openrouter" && !openrouterKey) {
      setStatus("no_key");
      setLabel("API key missing");
      return;
    }

    setStatus("checking");
    const controller = new AbortController();

    if (provider === "ollama") {
      fetch("http://localhost:11434/api/tags", { signal: controller.signal })
        .then((r) => {
          if (r.ok) {
            setStatus("connected");
            setLabel("Ollama connected");
          } else {
            setStatus("disconnected");
            setLabel("Ollama unavailable");
          }
        })
        .catch(() => {
          setStatus("disconnected");
          setLabel("Ollama unavailable");
        });
    } else {
      setStatus("connected");
      setLabel("OpenRouter ready");
    }

    return () => controller.abort();
  }, [provider, openrouterKey]);

  const colorMap: Record<HealthStatus, string> = {
    checking: "text-amber-400",
    connected: "text-emerald-400",
    disconnected: "text-rose-400",
    no_key: "text-amber-400",
  };

  const iconMap: Record<HealthStatus, React.ReactNode> = {
    checking: <motion.span animate={{ opacity: [0.4, 1, 0.4] }} transition={{ repeat: Infinity, duration: 1.5 }} className="h-1.5 w-1.5 rounded-full bg-amber-400" />,
    connected: <Wifi className="h-3 w-3" />,
    disconnected: <WifiOff className="h-3 w-3" />,
    no_key: <KeyRound className="h-3 w-3" />,
  };

  return (
    <span className={`tech-badge gap-1.5 ${colorMap[status]}`}>
      {iconMap[status]}
      <span className="text-[10px]">{label}</span>
    </span>
  );
}
