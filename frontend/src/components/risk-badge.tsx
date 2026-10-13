import React from "react";
import { CheckCircle2, AlertTriangle, AlertOctagon } from "lucide-react";
import { cn } from "@/lib/utils";

interface RiskBadgeProps {
  band: "low" | "medium" | "high" | string;
  score?: number;
  hasWarning?: boolean;
  size?: "sm" | "md" | "lg";
  showLabelText?: boolean;
  className?: string;
}

export function getRiskBandLabel(band: string): string {
  const b = band?.toLowerCase();
  if (b === "high") return "Needs careful review";
  if (b === "medium") return "Review recommended";
  return "No significant issues found";
}

export function RiskBadge({
  band,
  score,
  hasWarning = false,
  size = "md",
  showLabelText = false,
  className,
}: RiskBadgeProps) {
  const b = (band || "low").toLowerCase();
  const label = getRiskBandLabel(b);

  let icon = <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />;
  let colorClasses =
    "bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800/60";

  if (b === "high") {
    icon = <AlertOctagon className="h-3.5 w-3.5 text-red-600 dark:text-red-400" />;
    colorClasses =
      "bg-red-50 text-red-800 border-red-200 dark:bg-red-950/40 dark:text-red-300 dark:border-red-800/60";
  } else if (b === "medium") {
    icon = <AlertTriangle className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400" />;
    colorClasses =
      "bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800/60";
  }

  const bandName = b.toUpperCase();

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 font-medium rounded-full border select-none",
        colorClasses,
        size === "sm" && "text-xs px-2 py-0.5",
        size === "md" && "text-xs px-2.5 py-1",
        size === "lg" && "text-sm px-3.5 py-1.5",
        className
      )}
      data-testid="risk-badge"
    >
      {icon}
      <span>{bandName}</span>
      {score !== undefined && (
        <span className="font-semibold tabular-nums opacity-85">({score})</span>
      )}
      {hasWarning && (
        <span
          className="font-bold text-amber-600 dark:text-amber-400 ml-0.5 cursor-help"
          title="Analysis was run with coverage caveats. Review warnings."
        >
          *
        </span>
      )}
      {showLabelText && (
        <span className="opacity-90 pl-1 border-l border-current/20 text-[11px] sm:text-xs">
          {label}
        </span>
      )}
    </span>
  );
}
