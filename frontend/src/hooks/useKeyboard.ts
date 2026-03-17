/**
 * useKeyboard - Global keyboard shortcuts for the app
 *
 * Provides:
 * - Ctrl+K / Cmd+K: focus search (navigate to /search)
 * - Ctrl+N / Cmd+N: navigate to /add (new knowledge)
 *
 * Respects text input focus — shortcuts are disabled when user
 * is typing in an input, textarea, or select.
 */

import { useEffect, useCallback } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'

/** Check if the active element is a text input. */
function isTextInput(el: Element | null): boolean {
  if (!el) return false
  const tag = el.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true
  if ((el as HTMLElement).isContentEditable) return true
  return false
}

export function useKeyboardShortcuts() {
  const navigate = useNavigate()
  const location = useLocation()

  const handler = useCallback(
    (e: KeyboardEvent) => {
      const mod = e.ctrlKey || e.metaKey

      // Skip if user is typing
      if (isTextInput(document.activeElement)) {
        // Exception: Ctrl+K should still work from any input
        if (!(mod && e.key === 'k')) return
      }

      // Ctrl+K / Cmd+K → Search
      if (mod && e.key === 'k') {
        e.preventDefault()
        if (location.pathname !== '/search') {
          navigate('/search')
        }
        // Focus the search input after navigation
        requestAnimationFrame(() => {
          const searchInput = document.querySelector<HTMLInputElement>(
            'input[placeholder*="Search"]'
          )
          searchInput?.focus()
          searchInput?.select()
        })
        return
      }

      // Ctrl+N / Cmd+N → Add new
      if (mod && e.key === 'n') {
        e.preventDefault()
        navigate('/add')
        return
      }
    },
    [navigate, location.pathname]
  )

  useEffect(() => {
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [handler])
}
