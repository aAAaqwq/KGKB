/**
 * LinkModeDialog - Modal dialog for creating relations between two graph nodes
 *
 * Appears when the user is in Link Mode and has selected both a source and
 * target node. Allows picking a relation type (from presets or custom),
 * adjusting weight, and confirming the link creation.
 */

import React, { useState, useEffect, useRef } from 'react'

/** Common relation types offered as quick-select presets. */
const RELATION_PRESETS = [
  { value: 'relates_to', label: 'Relates to', icon: '🔗' },
  { value: 'contains', label: 'Contains', icon: '📦' },
  { value: 'depends_on', label: 'Depends on', icon: '⚙️' },
  { value: 'similar_to', label: 'Similar to', icon: '🔄' },
  { value: 'part_of', label: 'Part of', icon: '🧩' },
  { value: 'references', label: 'References', icon: '📝' },
  { value: 'derived_from', label: 'Derived from', icon: '🌱' },
  { value: 'contradicts', label: 'Contradicts', icon: '⚡' },
]

export interface LinkModeDialogProps {
  /** Source node label. */
  sourceLabel: string
  /** Target node label. */
  targetLabel: string
  /** Whether the dialog is currently submitting. */
  submitting: boolean
  /** Callback when user confirms the link. */
  onConfirm: (type: string, weight: number) => void
  /** Callback when user cancels. */
  onCancel: () => void
}

export function LinkModeDialog({
  sourceLabel,
  targetLabel,
  submitting,
  onConfirm,
  onCancel,
}: LinkModeDialogProps) {
  const [relationType, setRelationType] = useState('relates_to')
  const [customType, setCustomType] = useState('')
  const [isCustom, setIsCustom] = useState(false)
  const [weight, setWeight] = useState(1.0)
  const dialogRef = useRef<HTMLDivElement>(null)
  const customInputRef = useRef<HTMLInputElement>(null)

  // Focus trap: close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onCancel()
      }
      if (e.key === 'Enter' && !submitting) {
        e.preventDefault()
        handleConfirm()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onCancel, relationType, customType, isCustom, weight, submitting])

  // Auto-focus custom input when switching to custom mode
  useEffect(() => {
    if (isCustom && customInputRef.current) {
      customInputRef.current.focus()
    }
  }, [isCustom])

  const handleConfirm = () => {
    const type = isCustom ? customType.trim() || 'relates_to' : relationType
    onConfirm(type, weight)
  }

  const handlePresetClick = (value: string) => {
    setRelationType(value)
    setIsCustom(false)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onCancel}
      />

      {/* Dialog */}
      <div
        ref={dialogRef}
        className="relative bg-gray-800 rounded-xl border border-gray-600 shadow-2xl
                   w-[440px] max-w-[90vw] animate-scale-in"
        style={{ animation: 'scaleIn 0.2s ease-out' }}
      >
        {/* Header */}
        <div className="px-6 pt-5 pb-3">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            <span className="text-blue-400">🔗</span>
            Create Relation
          </h3>
          <p className="text-sm text-gray-400 mt-1">
            Link two knowledge nodes together
          </p>
        </div>

        {/* Node visualization */}
        <div className="px-6 py-3">
          <div className="flex items-center gap-3 bg-gray-900/60 rounded-lg p-3">
            <div className="flex-1 min-w-0">
              <div className="text-xs text-gray-500 mb-0.5">Source</div>
              <div className="text-sm font-medium text-blue-400 truncate" title={sourceLabel}>
                {sourceLabel}
              </div>
            </div>
            <div className="flex-shrink-0 text-gray-500 text-lg">→</div>
            <div className="flex-1 min-w-0">
              <div className="text-xs text-gray-500 mb-0.5">Target</div>
              <div className="text-sm font-medium text-green-400 truncate" title={targetLabel}>
                {targetLabel}
              </div>
            </div>
          </div>
        </div>

        {/* Relation type selector */}
        <div className="px-6 py-3">
          <label className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2 block">
            Relation Type
          </label>
          <div className="flex flex-wrap gap-2 mb-3">
            {RELATION_PRESETS.map(preset => (
              <button
                key={preset.value}
                onClick={() => handlePresetClick(preset.value)}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg
                           border transition-all duration-150
                           ${!isCustom && relationType === preset.value
                    ? 'bg-blue-600/20 border-blue-500/50 text-blue-300'
                    : 'bg-gray-900/40 border-gray-700 text-gray-400 hover:border-gray-500 hover:text-gray-300'
                  }`}
              >
                <span>{preset.icon}</span>
                {preset.label}
              </button>
            ))}
          </div>

          {/* Custom type */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsCustom(!isCustom)}
              className={`px-3 py-1.5 text-xs rounded-lg border transition-all duration-150
                         ${isCustom
                  ? 'bg-purple-600/20 border-purple-500/50 text-purple-300'
                  : 'bg-gray-900/40 border-gray-700 text-gray-400 hover:border-gray-500 hover:text-gray-300'
                }`}
            >
              ✨ Custom
            </button>
            {isCustom && (
              <input
                ref={customInputRef}
                type="text"
                value={customType}
                onChange={(e) => setCustomType(e.target.value)}
                placeholder="e.g. inspired_by"
                className="flex-1 px-3 py-1.5 text-sm bg-gray-900/60 border border-gray-700
                           rounded-lg text-gray-200 placeholder-gray-500
                           focus:outline-none focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/30
                           transition"
                maxLength={50}
              />
            )}
          </div>
        </div>

        {/* Weight slider */}
        <div className="px-6 py-3">
          <label className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2 block">
            Weight
            <span className="ml-2 text-gray-500 normal-case">
              ({weight.toFixed(1)})
            </span>
          </label>
          <input
            type="range"
            min="0.1"
            max="2.0"
            step="0.1"
            value={weight}
            onChange={(e) => setWeight(parseFloat(e.target.value))}
            className="w-full h-1.5 bg-gray-700 rounded-full appearance-none cursor-pointer
                       [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4
                       [&::-webkit-slider-thumb]:bg-blue-500 [&::-webkit-slider-thumb]:rounded-full
                       [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:cursor-grab"
          />
          <div className="flex justify-between text-[10px] text-gray-600 mt-1">
            <span>Weak (0.1)</span>
            <span>Strong (2.0)</span>
          </div>
        </div>

        {/* Actions */}
        <div className="px-6 py-4 border-t border-gray-700/50 flex items-center justify-end gap-3">
          <button
            onClick={onCancel}
            disabled={submitting}
            className="px-4 py-2 text-sm text-gray-400 hover:text-gray-200
                       rounded-lg border border-gray-700 hover:border-gray-500
                       transition disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={submitting}
            className="px-5 py-2 text-sm font-medium text-white
                       bg-blue-600 hover:bg-blue-500 rounded-lg
                       transition disabled:opacity-50 disabled:cursor-not-allowed
                       flex items-center gap-2"
          >
            {submitting ? (
              <>
                <span className="animate-spin">⏳</span>
                Creating…
              </>
            ) : (
              <>
                🔗 Create Link
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
