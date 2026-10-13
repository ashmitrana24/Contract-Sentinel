import Link from "next/link";
import { ArrowLeft, FileQuestion } from "lucide-react";

export default function NotFound() {
  return (
    <div className="mx-auto flex min-h-[60vh] max-w-md flex-col items-center justify-center px-4 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--bg-card-muted)] text-[var(--text-muted)] border border-[var(--border-subtle)] mb-4">
        <FileQuestion className="h-7 w-7" />
      </div>
      <h1 className="text-xl font-semibold text-[var(--text-primary)]">Page not found</h1>
      <p className="mt-2 text-xs text-[var(--text-secondary)] leading-relaxed">
        The contract or page you requested could not be located. It may have been removed or the URL
        is incorrect.
      </p>
      <div className="mt-6">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-4 py-2 text-xs font-medium text-white hover:opacity-90 transition-opacity"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Return to document list</span>
        </Link>
      </div>
    </div>
  );
}
