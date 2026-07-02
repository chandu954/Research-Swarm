import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDuration(seconds: number): string {
  if (seconds < 0) return "-";
  if (seconds === 0) return "0s";
  if (seconds < 0.001) return `${Math.round(seconds * 1000)}ms`;
  if (seconds < 1) return `${(seconds * 1000).toFixed(0)}ms`;
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}m ${s}s`;
}

export function formatMs(milliseconds: number): string {
  return formatDuration(milliseconds / 1000);
}

export function formatExecutionTime(seconds?: number): string {
  if (!seconds && seconds !== 0) return "-";
  return formatDuration(seconds);
}
