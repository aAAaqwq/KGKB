/**
 * Toast - Lightweight notification system
 *
 * Provides a ToastProvider context and useToast hook for showing
 * success, error, info, and warning toasts from anywhere in the app.
 * Toasts auto-dismiss after a configurable duration.
 */

import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  useRef,
} from 'react'

// ─── Types ───────────────────────────────────────────────────────────────────

export type ToastType = 'success' | 'error' | 'info' | 'warning'

export interface Toast {
  id: string
  type: ToastType
  message: string
  duration?: number // ms, default 4000
}

interface ToastContextValue {
  toasts: Toast[]
  addToast: (type: ToastType, message: string, duration?: number) => void
  removeToast: (id: string) => void
  success: (message: string) => void
  error: (message: string) => void
  info: (message: string) => void
  warning: (message: string) => void
}

// ─── Context ─────────────────────────────────────────────────────────────────

const ToastContext = createContext<ToastContextValue | null>(null)

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) {
    // Fallback for components outside the provider — no-op
    return {
      toasts: [],
      addToast: () => {},
      removeToast: () => {},
      success: () => {},
      error: () => {},
      info: () => {},
      warning: () => {},
    }
  }
  return ctx
}

// ─── Style maps ──────────────────────────────────────────────────────────────

const TOAST_STYLES: Record<ToastType, { bg: string; border: string; text: string; icon: string }> = {
  success: {
    bg: 'bg-green-900/80',
    border: 'border-green-700/50',
    text: 'text-green-300',
    icon: '✅',
  },
  error: {
    bg: 'bg-red-900/80',
    border: 'border-red-700/50',
    text: 'text-red-300',
    icon: '❌',
  },
  info: {
    bg: 'bg-blue-900/80',
    border: 'border-blue-700/50',
    text: 'text-blue-300',
    icon: 'ℹ️',
  },
  warning: {
    bg: 'bg-amber-900/80',
    border: 'border-amber-700/50',
    text: 'text-amber-300',
    icon: '⚠️',
  },
}

// ─── Individual Toast Item ───────────────────────────────────────────────────

function ToastItem({
  toast,
  onRemove,
}: {
  toast: Toast
  onRemove: (id: string) => void
}) {
  const style = TOAST_STYLES[toast.type]
  const [exiting, setExiting] = useState(false)

  useEffect(() => {
    const duration = toast.duration || 4000
    const fadeTimer = setTimeout(() => setExiting(true), duration - 300)
    const removeTimer = setTimeout(() => onRemove(toast.id), duration)
    return () => {
      clearTimeout(fadeTimer)
      clearTimeout(removeTimer)
    }
  }, [toast.id, toast.duration, onRemove])

  return (
    <div
      className={`flex items-center gap-2.5 px-4 py-3 rounded-lg text-sm shadow-lg
                  border backdrop-blur-sm max-w-sm w-full
                  transition-all duration-300
                  ${style.bg} ${style.border} ${style.text}
                  ${exiting ? 'opacity-0 translate-x-4' : 'opacity-100 translate-x-0'}
                  toast-enter`}
      role="alert"
    >
      <span className="flex-shrink-0 text-base">{style.icon}</span>
      <span className="flex-1 min-w-0 break-words">{toast.message}</span>
      <button
        onClick={() => onRemove(toast.id)}
        className="flex-shrink-0 opacity-60 hover:opacity-100 transition text-sm p-0.5"
        aria-label="Dismiss"
      >
        ✕
      </button>
    </div>
  )
}

// ─── Provider ────────────────────────────────────────────────────────────────

let toastCounter = 0

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const removeToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  const addToast = useCallback(
    (type: ToastType, message: string, duration?: number) => {
      const id = `toast-${++toastCounter}-${Date.now()}`
      setToasts(prev => [...prev.slice(-4), { id, type, message, duration }]) // max 5
    },
    []
  )

  const success = useCallback((msg: string) => addToast('success', msg), [addToast])
  const error = useCallback((msg: string) => addToast('error', msg), [addToast])
  const info = useCallback((msg: string) => addToast('info', msg), [addToast])
  const warning = useCallback((msg: string) => addToast('warning', msg), [addToast])

  const value: ToastContextValue = {
    toasts,
    addToast,
    removeToast,
    success,
    error,
    info,
    warning,
  }

  return (
    <ToastContext.Provider value={value}>
      {children}

      {/* Toast container — fixed top-right */}
      {toasts.length > 0 && (
        <div
          className="fixed top-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-auto"
          aria-live="polite"
        >
          {toasts.map(toast => (
            <ToastItem key={toast.id} toast={toast} onRemove={removeToast} />
          ))}
        </div>
      )}
    </ToastContext.Provider>
  )
}
