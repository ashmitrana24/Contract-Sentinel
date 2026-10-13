"use client";

import Link from "next/link";
import { ShieldAlert, Sun, Moon } from "lucide-react";
import { useTheme } from "./theme-provider";

export function Header() {
  const { theme, toggleTheme } = useTheme();

  return (
    <header className="sticky top-0 z-30 w-full border-b border-[var(--border-subtle)] bg-[var(--bg-card)]/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6">
        <Link
          href="/"
          className="flex items-center gap-2.5 text-base font-semibold tracking-tight text-[var(--text-primary)] hover:opacity-90 transition-opacity"
        >
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--accent)] text-white shadow-sm">
            <ShieldAlert className="h-4 w-4" />
          </div>
          <span>ClauseGuard</span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--bg-card-muted)] text-[var(--text-muted)] border border-[var(--border-subtle)] font-medium">
            Workbench
          </span>
        </Link>

        <div className="flex items-center gap-3">
          <button
            onClick={toggleTheme}
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-card)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card-muted)] transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent)]"
          >
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
        </div>
      </div>
    </header>
  );
}
