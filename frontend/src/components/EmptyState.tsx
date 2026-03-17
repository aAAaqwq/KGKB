/**
 * EmptyState - Consistent empty/no-data states across all views
 *
 * Provides predefined empty state variants with emoji illustrations,
 * messages, and optional action buttons.
 */

import React from 'react'
import { Link } from 'react-router-dom'

export interface EmptyStateProps {
  /** Predefined variant or custom */
  variant?: 'no-data' | 'no-results' | 'no-relations' | 'error' | 'custom'
  /** Emoji icon (overrides variant default) */
  icon?: string
  /** Main title */
  title?: string
  /** Description text */
  description?: string
  /** Action button label */
  actionLabel?: string
  /** Action callback (button click) */
  onAction?: () => void
  /** Action link (renders as Link instead of button) */
  actionLink?: string
  /** Additional CSS class */
  className?: string
  /** Children for custom content below description */
  children?: React.ReactNode
}

/** Default content per variant */
const VARIANTS = {
  'no-data': {
    icon: '📭',
    title: 'No knowledge entries yet',
    description: 'Start building your knowledge graph by adding your first entry.',
  },
  'no-results': {
    icon: '🔍',
    title: 'No results found',
    description: 'Try different keywords or adjust your search filters.',
  },
  'no-relations': {
    icon: '🔗',
    title: 'No relations yet',
    description: 'Use the graph view to link knowledge entries together.',
  },
  'error': {
    icon: '😕',
    title: 'Something went wrong',
    description: 'An error occurred while loading data. Please try again.',
  },
  'custom': {
    icon: '📋',
    title: '',
    description: '',
  },
}

export function EmptyState({
  variant = 'no-data',
  icon,
  title,
  description,
  actionLabel,
  onAction,
  actionLink,
  className = '',
  children,
}: EmptyStateProps) {
  const defaults = VARIANTS[variant]
  const displayIcon = icon || defaults.icon
  const displayTitle = title || defaults.title
  const displayDesc = description || defaults.description

  return (
    <div className={`text-center py-16 px-4 animate-fade-in ${className}`}>
      <p className="text-5xl mb-4" role="img" aria-hidden="true">
        {displayIcon}
      </p>
      {displayTitle && (
        <p className="text-gray-300 text-lg font-medium mb-2">
          {displayTitle}
        </p>
      )}
      {displayDesc && (
        <p className="text-gray-500 text-sm mb-6 max-w-md mx-auto leading-relaxed">
          {displayDesc}
        </p>
      )}
      {children}
      {actionLink ? (
        <Link
          to={actionLink}
          className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-medium
                     bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition
                     shadow-lg shadow-blue-600/20"
        >
          {actionLabel || 'Get started'}
        </Link>
      ) : onAction && actionLabel ? (
        <button
          onClick={onAction}
          className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-medium
                     bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition
                     shadow-lg shadow-blue-600/20"
        >
          {actionLabel}
        </button>
      ) : null}
    </div>
  )
}
