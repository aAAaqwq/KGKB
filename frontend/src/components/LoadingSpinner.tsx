/**
 * LoadingSpinner - Reusable loading indicator
 *
 * Supports multiple sizes and an optional label.
 * Used across all views for consistent loading feedback.
 */

import React from 'react'

export interface LoadingSpinnerProps {
  /** Size variant: sm (16px), md (32px), lg (48px) */
  size?: 'sm' | 'md' | 'lg'
  /** Optional label shown below the spinner */
  label?: string
  /** Fill parent container height? */
  fullHeight?: boolean
  /** Additional CSS class */
  className?: string
}

const SIZE_MAP = {
  sm: 'w-4 h-4 border-2',
  md: 'w-8 h-8 border-2',
  lg: 'w-12 h-12 border-[3px]',
}

export function LoadingSpinner({
  size = 'md',
  label,
  fullHeight = false,
  className = '',
}: LoadingSpinnerProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center gap-3
                  ${fullHeight ? 'min-h-[400px]' : 'py-16'}
                  ${className}`}
    >
      <div className="relative">
        {/* Faint track circle */}
        {size === 'lg' && (
          <div className="absolute inset-0 w-12 h-12 border-[3px] border-blue-500/20 rounded-full" />
        )}
        {/* Spinning arc */}
        <div
          className={`rounded-full animate-spin border-blue-500 border-t-transparent
                      ${SIZE_MAP[size]}`}
        />
      </div>
      {label && (
        <span className="text-sm text-gray-400 animate-pulse">{label}</span>
      )}
    </div>
  )
}

/**
 * SkeletonLine - Animated placeholder for text content
 */
export function SkeletonLine({
  width = '100%',
  height = '1rem',
  className = '',
}: {
  width?: string
  height?: string
  className?: string
}) {
  return (
    <div
      className={`bg-gray-700/50 rounded animate-pulse ${className}`}
      style={{ width, height }}
    />
  )
}

/**
 * SkeletonCard - Animated placeholder card for list loading states
 */
export function SkeletonCard({ className = '' }: { className?: string }) {
  return (
    <div className={`bg-gray-800 rounded-lg border border-gray-700 p-4 space-y-3 ${className}`}>
      <div className="flex items-start justify-between">
        <div className="flex-1 space-y-2">
          <SkeletonLine width="60%" height="1.25rem" />
          <SkeletonLine width="90%" />
          <SkeletonLine width="75%" />
        </div>
        <SkeletonLine width="4rem" height="1rem" className="flex-shrink-0 ml-4" />
      </div>
      <div className="flex gap-2 pt-1">
        <SkeletonLine width="3.5rem" height="1.5rem" className="rounded-full" />
        <SkeletonLine width="4.5rem" height="1.5rem" className="rounded-full" />
        <SkeletonLine width="3rem" height="1.5rem" className="rounded-full" />
      </div>
    </div>
  )
}
