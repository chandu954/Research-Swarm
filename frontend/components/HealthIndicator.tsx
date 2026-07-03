"use client";

import { useState, useEffect, useCallback } from "react";
import { Wifi, WifiOff, Loader2 } from "lucide-react";
import { checkHealth } from "@/lib/api-client";

export function HealthIndicator() {
  const [status, setStatus] = useState<"checking" | "ok" | "degraded" | "offline">("checking");
  const [detail, setDetail] = useState<string>("");

  const check = useCallback(async () => {
    setStatus("checking");
    const result = await checkHealth();
    if (result.ok) {
      setStatus("ok");
    } else if (result.detail) {
      setStatus("degraded");
      setDetail(result.detail);
    } else {
      setStatus("offline");
    }
  }, []);

  useEffect(() => {
    check();
    const interval = setInterval(check, 30_000);
    return () => clearInterval(interval);
  }, [check]);

  const config = {
    checking: { icon: Loader2, text: "Checking...", color: "text-gray-500" },
    ok: { icon: Wifi, text: "Connected", color: "text-emerald-400" },
    degraded: { icon: Wifi, text: "Degraded", color: "text-amber-400" },
    offline: { icon: WifiOff, text: "Offline", color: "text-rose-400" },
  }[status];

  const Icon = config.icon;

  return (
    <button
      onClick={check}
      className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-[10px] transition-colors hover:bg-white/[0.04]"
      title={detail || `Backend status: ${status}`}
    >
      <Icon className={`h-3 w-3 ${config.color} ${status === "checking" ? "animate-spin" : ""}`} />
      <span className="text-gray-500">{config.text}</span>
    </button>
  );
}
