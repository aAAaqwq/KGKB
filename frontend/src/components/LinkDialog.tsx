/**
 * LinkDialog - Modal dialog for creating a relation between two graph nodes
 *
 * Shown when user selects two nodes in Link Mode.
 * Allows choosing relation type (from presets or custom) and confirming.
 * Calls API to create the relation, then reports success/failure.
 */

import React, { useState, useEffect, useRef } from 'react'

/** Common relation types offered as quick-pick buttons. */
const RELATION_PRESETS = [
  { type: 'relates_to', label: 'Relates to', emoji: '🔗' },
  { type: 'contains', label: 'Contains', emoji: '📦' },
  { type: 'depends_on', label: 'Depends on', emoji: '⚙️' },
  { type: 'similar_to', label: 'Similar to', emoji: '🔄' },
  { type: 'part_of', label: 'Part of', emoji: '🧩' },
  { type: 'derived_from', label: 'Derived from', emoji: '🌿' },
  { type: 'contradicts', label: 'Contradicts', emoji: '⚡' },
  { type: 'supports', label: 'Supports', emoji: '🤝' },
]

export interface LinkDialogProps {
  /** Source node label. */
  sourceLabel: string
  /** Source node ID. */
  sourceId: string
  /** Target node label. */
  targetLabel: string
  /** Target node ID. */
  targetId: string
  /** Whether the API call is in progress. */
  loading: boolean
  /** Error message from API call, if any. */
  error: string | null
  /** Called when user confirms the link with the selected type. */
  onConfirm: (type: string) => void
  /** Called when user cancels the dialog. */
  onCancel: () => void
}

export function LinkDialog({
  sourceLabel,
  sourceId,
  targetLabel,
  targetId,
  loading,
  error,
  onConfirm,
  onCancel,
}: LinkDialogProps) {
  const [selectedType, setSelectedType] = useState('relates_to')
  const [customType, setCustomType] = useState('')
  const [useCustom, setUseCustom] = useState(false)
  const customInputRef = useRef<HTMLInputElement>(null)

  // Focus custom input when switching to custom mode
  useEffect(() => {
    if (useCustom && customInputRef.current) {
      customInputRef.current.focus()
    }
  }, [useCustom])

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !loading) onCancel()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onCancel, loading])

  const effectiveType = useCustom ? customType.trim() : selectedType
  const canSubmit = effectiveType.length > 0 && !loading

  const handleSubmit = () => {
    if (canSubmit) onConfirm(effectiveType)
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={(e) => {
        // Close on backdrop click (not when clicking dialog content)
        if (e.target === e.currentTarget && !loading) onCancel()
      }}
    >
      <div
        className="bg-gray-800 border border-gray-600 rounded-xl shadow-2xl w-[440px] max-w-[95vw]
                   animate-fade-in-up"
        style={{ animation: 'fadeInUp 0.2s ease-out' }}
      >
        {/* Header */}
        <div className="px-5 pt-5 pb-3">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            🔗 Create Relation
          </h3>
          <p className="text-sm text-gray-400 mt-1">
            Link two knowledge nodes with a typed relationship.
          </p>
        </div>

        {/* Node pair display */}
        <div className="px-5 pb-3">
          <div className="flex items-center gap-3 bg-gray-900/60 rounded-lg p-3">
            {/* Source */}
            <div className="flex-1 min-w-0">
              <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-0.5">
                Source
              </div>
              <div className="text-sm text-blue-400 font-medium truncate" title={sourceLabel}>
                {sourceLabel}
              </div>
            </div>

            {/* Arrow */}
            <div className="flex-shrink-0 text-gray-500 text-lg">→</div>

            {/* Target */}
            <div className="flex-1 min-w-0">
              <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-0.5">
                Target
              </div>
              <div className="text-sm text-green-400 font-medium truncate" title={targetLabel}>
                {targetLabel}
              </div>
            </div>
          </div>
        </div>

        {/* Relation type selection */}
        <div className="px-5 pb-3">
          <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
            Relation Type
          </div>

          {/* Preset buttons */}
          <div className="flex flex-wrap gap-1.5 mb-3">
            {RELATION_PRESETS.map(preset => (
              <button
                key={preset.type}
                onClick={() => {
                  setSelectedType(preset.type)
                  setUseCustom(false)
                }}
                disabled={loading}
                className={`inline-flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-lg
                           border transition-all duration-150
                           ${!useCustom && selectedType === preset.type
                    ? 'bg-blue-600/25 border-blue-500/50 text-blue-300 shadow-sm'
                    : 'bg-gray-900/40 border-gray-700 text-gray-400 hover:border-gray-500 hover:text-gray-300'
                  }
                           disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                <span>{preset.emoji}</span>
                {preset.label}
              </button>
            ))}
          </div>

          {/* Custom type toggle + input */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setUseCustom(!useCustom)}
              disabled={loading}
              className={`text-xs px-2 py-1 rounded border transition
                ${useCustom
                  ? 'bg-purple-600/20 border-purple-500/50 text-purple-300'
                  : 'bg-transparent border-gray-700 text-gray-500 hover:text-gray-300'
                }
                disabled:opacity-50`}
            >
              ✨ Custom
            </button>

            {useCustom && (
              <input
                ref={customInputRef}
                type="text"
                value={customType}
                onChange={(e) => setCustomType(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleSubmit()
                }}
                placeholder="e.g. inspired_by"
                disabled={loading}
                className="flex-1 px-3 py-1.5 text-sm bg-gray-900/60 border border-gray-700
                           rounded-md text-gray-200 placeholder-gray-600
                           focus:outline-none focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/30
                           transition disabled:opacity-50"
              />
            )}
          </div>
        </div>

        {/* Error display */}
        {error && (
          <div className="px-5 pb-2">
            <div className="text-xs text-red-400 bg-red-500/10 rounded-md px-3 py-2 border border-red-500/20">
              ❌ {error}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-gray-700/50">
          <button
            onClick={onCancel}
            disabled={loading}
            className="px-4 py-2 text-sm text-gray-400 hover:text-gray-200
                       bg-gray-700/50 hover:bg-gray-700 rounded-lg transition
                       disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="px-4 py-2 text-sm text-white font-medium
                       bg-blue-600 hover:bg-blue-500 rounded-lg transition
                       disabled:opacity-50 disabled:cursor-not-allowed
                       flex items-center gap-2"
          >
            {loading ? (
              <>
                <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Creating…
              </>
            ) : (
              <>🔗 Create Link</>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
