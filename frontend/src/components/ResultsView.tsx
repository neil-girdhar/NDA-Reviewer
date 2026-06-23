import { useState } from 'react'
import './ResultsView.css'
import type { ReviewResult, Finding } from '../types'

interface ResultsViewProps {
  results: ReviewResult
  onReset: () => void
}

export default function ResultsView({ results, onReset }: ResultsViewProps) {
  const [editingField, setEditingField] = useState<{ id: number; field: string } | null>(null)
  const [editValue, setEditValue] = useState('')
  const [findings, setFindings] = useState(results.findings)

  // Track which findings are selected for clean copy (default: all Red/Amber checked)
  const [selectedFindings, setSelectedFindings] = useState<Set<number>>(() => {
    const redAndAmber = results.findings.filter(f => f.rag_rating === 'Red' || f.rag_rating === 'Amber')
    return new Set(redAndAmber.map(f => f.id))
  })

  const groupedFindings = {
    Red: findings.filter(f => f.rag_rating === 'Red'),
    Amber: findings.filter(f => f.rag_rating === 'Amber'),
    Green: findings.filter(f => f.rag_rating === 'Green'),
  }

  const toggleFinding = (id: number) => {
    setSelectedFindings(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const handleDownload = async (type: 'report' | 'clean') => {
    const selectedIds = Array.from(selectedFindings).join(',')
    const url = `/api/download/${results.id}/${type}?findings=${selectedIds}`
    try {
      const response = await fetch(url, { cache: 'no-store' })
      if (!response.ok) throw new Error(`Server error ${response.status}`)
      const blob = await response.blob()
      const dlUrl = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = dlUrl
      const cd = response.headers.get('Content-Disposition')
      const match = cd?.match(/filename="([^"]+)"/)
      a.download = match ? match[1] : `review_${type}.docx`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(dlUrl)
    } catch (err) {
      alert(`Download failed: ${err}`)
    }
  }

  return (
    <div id="results">
      <div className="result-header">
        <div className="result-meta">
          <h2>Review complete</h2>
          <div className="filename mono">{results.filename}</div>
        </div>
        <div className="rag-key">
          <div className="rag-key-row">
            <span className="rag-dot rag-dot-red" />
            <span className="rag-key-label"><strong>Red</strong> — Must resolve</span>
          </div>
          <div className="rag-key-row">
            <span className="rag-dot rag-dot-amber" />
            <span className="rag-key-label"><strong>Amber</strong> — Change at discretion</span>
          </div>
          <div className="rag-key-row">
            <span className="rag-dot rag-dot-green" />
            <span className="rag-key-label"><strong>Green</strong> — Acceptable as written</span>
          </div>
        </div>
      </div>

      <div id="findings-list">
        {Object.entries(groupedFindings).map(([rating, findings]) =>
          findings.length > 0 && (
            <div key={rating}>
              <div className="group-heading">
                <span style={{ color: `var(--${rating.toLowerCase()}-bar)`, fontSize: '8px', lineHeight: '1' }}>●</span>
                {rating === 'Red' && ' Red — Must resolve'}
                {rating === 'Amber' && ' Amber — Change at discretion'}
                {rating === 'Green' && ' Green — Acceptable as written'}
              </div>
              {findings.map(finding => (
                <FindingCard
                  key={finding.id}
                  finding={finding}
                  isSelected={selectedFindings.has(finding.id)}
                  onToggleSelect={() => toggleFinding(finding.id)}
                  editingField={editingField}
                  editValue={editValue}
                  onStartEdit={(field) => {
                    setEditingField({ id: finding.id, field })
                    setEditValue(finding[field as keyof Finding] as string)
                  }}
                  onCancelEdit={() => setEditingField(null)}
                  onSaveEdit={async () => {
                    try {
                      const response = await fetch(`/api/finding/${finding.id}`, {
                        method: 'PATCH',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ [editingField!.field]: editValue }),
                      })
                      if (!response.ok) throw new Error('Save failed')

                      // Update local state to reflect the saved changes
                      setFindings(prevFindings =>
                        prevFindings.map(f =>
                          f.id === finding.id
                            ? { ...f, [editingField!.field]: editValue }
                            : f
                        )
                      )
                      setEditingField(null)
                    } catch (error) {
                      alert(`Save failed: ${error}`)
                    }
                  }}
                  onEditValueChange={setEditValue}
                />
              ))}
            </div>
          )
        )}
      </div>

      <div className="actions">
        <div className="actions-label">Download reports</div>
        <div className="dl-grid">
          <button className="dl-card report" onClick={() => handleDownload('report')}>
            <div className="dl-icon icon-container">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
                <rect x="8" y="2" width="8" height="4" rx="1" ry="1" />
              </svg>
            </div>
            <span className="dl-name">Issues Report</span>
            <span className="dl-desc">Red &amp; amber findings with redlines, sorted by contract position</span>
            <div className="dl-action">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
              {' '}Download DOCX
            </div>
          </button>
          <button className="dl-card clean" onClick={() => handleDownload('clean')}>
            <div className="dl-icon icon-container">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </div>
            <span className="dl-name">Clean Copy</span>
            <span className="dl-desc">Full NDA with all Ascential changes applied, ready to send</span>
            <div className="dl-action">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
              {' '}Download DOCX
            </div>
          </button>
        </div>
        <button className="btn-secondary" onClick={onReset}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
          Review another NDA
        </button>
      </div>
    </div>
  )
}

interface FindingCardProps {
  finding: Finding
  isSelected: boolean
  onToggleSelect: () => void
  editingField: { id: number; field: string } | null
  editValue: string
  onStartEdit: (field: string) => void
  onCancelEdit: () => void
  onSaveEdit: () => void
  onEditValueChange: (value: string) => void
}

function FindingCard({ finding, isSelected, onToggleSelect, editingField, editValue, onStartEdit, onCancelEdit, onSaveEdit, onEditValueChange }: FindingCardProps) {
  const isEditing = (field: string) => editingField?.id === finding.id && editingField?.field === field
  const showCheckbox = finding.rag_rating === 'Red' || finding.rag_rating === 'Amber'

  return (
    <div className={`finding ${finding.rag_rating}`}>
      <div className="finding-bar"></div>
      <div className="finding-body">
        <div className="finding-top">
          {showCheckbox && (
            <label className="finding-checkbox" title="Include in clean copy">
              <input
                type="checkbox"
                checked={isSelected}
                onChange={onToggleSelect}
              />
              <span className="checkbox-label">Apply</span>
            </label>
          )}
          <span className={`rag-pill ${finding.rag_rating}`}>{finding.rag_rating}</span>
          <span className="finding-title">{finding.clause_type}</span>
        </div>
        <div className="finding-summary">{finding.plain_english_summary}</div>
        <div className="finding-risk">{finding.risk_reason}</div>

        {finding.suggested_redline && (
          <div className="redline-block">
            <span className="label">Remove</span>
            <span className="original">{finding.suggested_redline}</span>
            <span className="label">Replace with</span>
            {isEditing('replacement_language') ? (
              <>
                <textarea
                  className="inline-editor edit-replacement"
                  value={editValue}
                  onChange={(e) => onEditValueChange(e.target.value)}
                  rows={Math.max(2, Math.ceil(editValue.length / 60) + 1)}
                />
                <div className="edit-actions">
                  <button className="btn-xs btn-xs-save" onClick={onSaveEdit}>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '4px', verticalAlign: 'middle' }}>
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                    Save
                  </button>
                  <button className="btn-xs btn-xs-cancel" onClick={onCancelEdit}>
                    <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" style={{ marginRight: '4px', verticalAlign: 'middle' }}>
                      <path d="M4 4l8 8M12 4l-8 8" />
                    </svg>
                    Cancel
                  </button>
                </div>
              </>
            ) : (
              <>
                <span className="replacement">{finding.replacement_language}</span>
                <button className="edit-icon-btn" onClick={() => onStartEdit('replacement_language')}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '3px', verticalAlign: 'middle' }}>
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                  </svg>
                  Edit
                </button>
              </>
            )}
          </div>
        )}

      </div>
    </div>
  )
}
