/**
 * ConfirmDialog - Reusable modal confirmation dialog
 *
 * Features:
 * - Backdrop blur overlay
 * - Escape key to cancel
 * - Click backdrop to cancel
 * - Customizable title, message, and button labels
 * - Danger variant for destructive actions
 * - Loading state for async confirmation
 */

import React, { useEffect, useRef } from 'react'

export interface ConfirmDialogProps {
  /** Whether the dialog is visible */
  open: boolean
  /** Dialog title */
  title: string
  /** Dialog message/description (can be string or ReactNode) */
  message: React.ReactNode
  /** Confirm button label */
  confirmLabel?: string
  /** Cancel button label */
  cancelLabel?: string
  /** Use danger styling (red confirm button) */
  danger?: boolean
  /** Whether confirm action is in progress */
  loading?: boolean
  /** Called when user confirms */
  onConfirm: () => void
  /** Called when user cancels */
  onCancel: () => void
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  danger = false,
  loading = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null)

  // Handle keyboard: Escape to cancel, Enter to confirm
  useEffect(() => {
    if (!open) return

    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !loading) {
        e.preventDefault()
        onCancel()
      }
      // Enter only when not loading and not focused on a button (to avoid double-fire)
      if (e.key === 'Enter' && !loading) {
        const active = document.activeElement
        if (active?.tagName !== 'BUTTON') {
          e.preventDefault()
          onConfirm()
        }
      }
    }

    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, loading, onCancel, onConfirm])

  // Focus trap on mount
  useEffect(() => {
    if (open && dialogRef.current) {
      dialogRef.current.focus()
    }
  }, [open])

  if (!open) return null

  const confirmBtnClasses = danger
    ? 'bg-red-600 hover:bg-red-700 text-white'
    : 'bg-blue-600 hover:bg-blue-700 text-white'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={loading ? undefined : onCancel}
      />

      {/* Dialog */}
      <div
        ref={dialogRef}
        tabIndex={-1}
        className="relative bg-gray-800 rounded-xl border border-gray-700 p-6
                   max-w-md w-full mx-4 shadow-2xl animate-scale-in
                   focus:outline-none"
      >
        <h3 className="text-lg font-semibold text-gray-100 mb-2">
          {title}
        </h3>

        <div className="text-gray-400 text-sm mb-6 leading-relaxed">
          {message}
        </div>

        <div className="flex items-center justify-end gap-3">
          <button
            onClick={onCancel}
            disabled={loading}
            className="px-4 py-2 text-sm text-gray-400 border border-gray-700
                       hover:text-gray-200 hover:border-gray-500 rounded-lg transition
                       disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className={`px-5 py-2 text-sm font-medium rounded-lg transition
                        disabled:opacity-50 disabled:cursor-not-allowed
                        inline-flex items-center gap-1.5 ${confirmBtnClasses}`}
          >
            {loading ? (
              <>
                <svg
                  className="animate-spin h-4 w-4"
                  viewBox="0 0 24 24"
                  fill="none"
                >
                  <circle
                    className="opacity-25"
                    cx="12" cy="12" r="10"
                    stroke="currentColor" strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                  />
                </svg>
                Processing…
              </>
            ) : (
              confirmLabel
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
