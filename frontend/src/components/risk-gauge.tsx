"use client";

import React, { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

interface RiskGaugeProps {
  score: number;
  size?: number;
  className?: string;
}

export function RiskGauge({ score, size = 120, className }: RiskGaugeProps) {
  const [animatedScore, setAnimatedScore] = useState(score);

  useEffect(() => {
    // Check if user prefers reduced motion
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReducedMotion) {
      const id = requestAnimationFrame(() => setAnimatedScore(score));
      return () => cancelAnimationFrame(id);
    }

    const timer = setTimeout(() => {
      setAnimatedScore(score);
    }, 100);
    return () => clearTimeout(timer);
  }, [score]);

  // Semicircle gauge geometry
  const strokeWidth = 10;
  const radius = (size - strokeWidth) / 2;
  const center = size / 2;
  // Circumference of semicircle = Math.PI * radius
  const arcLength = Math.PI * radius;
  // Clamped ratio
  const ratio = Math.max(0, Math.min(100, animatedScore)) / 100;
  const strokeDashoffset = arcLength * (1 - ratio);

  let strokeColor = "#10b981"; // emerald-500
  if (score >= 60) {
    strokeColor = "#ef4444"; // red-500
  } else if (score >= 20) {
    strokeColor = "#f59e0b"; // amber-500
  }

  return (
    <div
      className={cn("relative flex flex-col items-center justify-center select-none", className)}
      style={{ width: size, height: size * 0.65 }}
      data-testid="risk-gauge"
    >
      <svg
        width={size}
        height={size / 2 + strokeWidth}
        viewBox={`0 0 ${size} ${size / 2 + strokeWidth}`}
        className="overflow-visible"
        aria-hidden="true"
      >
        {/* Background track arc */}
        <path
          d={`M ${strokeWidth / 2} ${center} A ${radius} ${radius} 0 0 1 ${size - strokeWidth / 2} ${center}`}
          fill="none"
          stroke="currentColor"
          className="text-zinc-200 dark:text-zinc-800"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
        />
        {/* Animated fill arc */}
        <path
          d={`M ${strokeWidth / 2} ${center} A ${radius} ${radius} 0 0 1 ${size - strokeWidth / 2} ${center}`}
          fill="none"
          stroke={strokeColor}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={arcLength}
          strokeDashoffset={strokeDashoffset}
          style={{
            transition: "stroke-dashoffset 800ms cubic-bezier(0.16, 1, 0.3, 1)",
          }}
        />
      </svg>
      {/* Central score readout */}
      <div className="absolute bottom-0 flex flex-col items-center text-center">
        <span className="text-2xl font-bold tracking-tight text-[var(--text-primary)] tabular-nums leading-none">
          {Math.round(animatedScore)}
        </span>
        <span className="text-[10px] uppercase tracking-wider text-[var(--text-muted)] font-medium mt-1">
          Score
        </span>
      </div>
    </div>
  );
}
