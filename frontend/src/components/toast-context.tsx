"use client";

import React, { createContext, useContext, useState, useCallback } from "react";
import { CheckCircle2, X } from "lucide-react";

interface Toast {
  id: string;
  message: string;
  onUndo?: () => void;
}

interface ToastContextType {
  showToast: (message: string, onUndo?: () => void) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((message: string, onUndo?: () => void) => {
    const id = Math.random().toString(36).substring(2, 9);
    const toast: Toast = { id, message, onUndo };
    setToasts((prev) => [...prev, toast]);

    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4500);
  }, []);

  const dismissToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div
        className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none"
        aria-live="polite"
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            role="status"
            className="pointer-events-auto flex items-center gap-3 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] px-4 py-3 text-xs text-[var(--text-primary)] shadow-lg animate-in fade-in slide-in-from-bottom-2 duration-150"
          >
            <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
            <span className="font-medium">{toast.message}</span>
            {toast.onUndo && (
              <button
                onClick={() => {
                  toast.onUndo?.();
                  dismissToast(toast.id);
                }}
                className="ml-2 font-semibold text-[var(--accent)] hover:underline focus:outline-none"
              >
                Undo
              </button>
            )}
            <button
              onClick={() => dismissToast(toast.id)}
              className="text-[var(--text-muted)] hover:text-[var(--text-primary)] p-0.5"
              aria-label="Dismiss notification"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within ToastProvider");
  }
  return ctx;
}
