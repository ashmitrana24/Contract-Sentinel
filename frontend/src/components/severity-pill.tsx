import React from "react";
import { ShieldAlert, AlertTriangle, AlertCircle, Info } from "lucide-react";
import { cn } from "@/lib/utils";

interface SeverityPillProps {
  severity: string;
  className?: string;
  size?: "sm" | "md";
}

export function SeverityPill({ severity, className, size = "md" }: SeverityPillProps) {
  const sev = (severity || "low").toLowerCase();

  let icon = <Info className={size === "sm" ? "h-3 w-3" : "h-3.5 w-3.5"} />;
  let label = "Low";
  let bgClass = "bg-[var(--sev-low-bg)] text-[var(--sev-low-text)] border-[var(--sev-low-border)]";

  if (sev === "critical") {
    icon = <ShieldAlert className={size === "sm" ? "h-3 w-3 text-[var(--sev-critical)]" : "h-3.5 w-3.5 text-[var(--sev-critical)]"} />;
    label = "Critical";
    bgClass = "bg-[var(--sev-critical-bg)] text-[var(--sev-critical-text)] border-[var(--sev-critical-border)]";
  } else if (sev === "high") {
    icon = <AlertTriangle className={size === "sm" ? "h-3 w-3 text-[var(--sev-high)]" : "h-3.5 w-3.5 text-[var(--sev-high)]"} />;
    label = "High";
    bgClass = "bg-[var(--sev-high-bg)] text-[var(--sev-high-text)] border-[var(--sev-high-border)]";
  } else if (sev === "medium") {
    icon = <AlertCircle className={size === "sm" ? "h-3 w-3 text-[var(--sev-medium)]" : "h-3.5 w-3.5 text-[var(--sev-medium)]"} />;
    label = "Medium";
    bgClass = "bg-[var(--sev-medium-bg)] text-[var(--sev-medium-text)] border-[var(--sev-medium-border)]";
  }

  const sizeClasses = size === "sm" ? "text-[11px] px-2 py-0.5 gap-1" : "text-xs px-2.5 py-1 gap-1.5";

  return (
    <span
      className={cn(
        "inline-flex items-center font-medium rounded-full border tracking-normal select-none",
        bgClass,
        sizeClasses,
        className
      )}
    >
      {icon}
      <span>{label}</span>
    </span>
  );
}
