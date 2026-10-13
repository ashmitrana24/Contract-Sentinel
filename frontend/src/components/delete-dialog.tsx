"use client";

import React from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { AlertTriangle, Trash2, X } from "lucide-react";

interface DeleteDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  documentTitle?: string;
  isDeleting?: boolean;
}

export function DeleteDialog({
  open,
  onOpenChange,
  onConfirm,
  documentTitle,
  isDeleting = false,
}: DeleteDialogProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm transition-opacity" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] p-6 shadow-xl focus:outline-none">
          <div className="flex items-start gap-4">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-red-100 text-red-600 dark:bg-red-950 dark:text-red-400">
              <AlertTriangle className="h-5 w-5" />
            </div>
            <div className="flex-1">
              <Dialog.Title className="text-base font-semibold text-[var(--text-primary)]">
                Delete document
              </Dialog.Title>
              <Dialog.Description className="mt-2 text-sm text-[var(--text-secondary)] leading-relaxed">
                Are you sure you want to delete{" "}
                <strong className="text-[var(--text-primary)] font-medium">
                  {documentTitle || "this document"}
                </strong>
                ? All analysis results, findings, and the stored file will be permanently removed.
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <button
                className="rounded-lg p-1 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent)]"
                aria-label="Close"
              >
                <X className="h-4 w-4" />
              </button>
            </Dialog.Close>
          </div>

          <div className="mt-6 flex justify-end gap-3">
            <Dialog.Close asChild>
              <button
                type="button"
                disabled={isDeleting}
                className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-card)] px-4 py-2 text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-card-muted)] hover:text-[var(--text-primary)] transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent)]"
              >
                Cancel
              </button>
            </Dialog.Close>
            <button
              type="button"
              data-testid="confirm-delete-btn"
              onClick={onConfirm}
              disabled={isDeleting}
              className="inline-flex items-center gap-1.5 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 transition-colors disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-red-600"
            >
              <Trash2 className="h-4 w-4" />
              <span>{isDeleting ? "Deleting..." : "Delete"}</span>
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
