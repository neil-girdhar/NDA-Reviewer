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

  const groupedFindings = {
    Red: results.findings.filter(f => f.rag_rating === 'Red'),
    Amber: results.findings.filter(f => f.rag_rating === 'Amber'),
    Green: results.findings.filter(f => f.rag_rating === 'Green'),
  }

  const handleDownload = (type: 'report' | 'negotiation' | 'clean') => {
    window.location.href = `/api/download/${results.id}/${type}`
  }

  return (
    <div id="results">
      <div className="result-header">
        <div className="result-meta">
          <h2>Review complete</h2>
          <div className="filename mono">{results.filename}</div>
        </div>
        <div className={`overall-badge badge-${results.overall_risk}`}>
          <span className="ov-label">Overall Risk</span>
          <span className="ov-value">{results.overall_risk}</span>
        </div>
      </div>

      <div id="findings-list">
        {Object.entries(groupedFindings).map(([rating, findings]) =>
          findings.length > 0 && (
            <div key={rating}>
              <div className="group-heading">
                <span style={{ color: `var(--${rating.toLowerCase()}-bar)`, fontSize: '8px', lineHeight: '1' }}>●</span>
                {rating === 'Red' && ' Red — Must resolve'}
                {rating === 'Amber' && ' Amber — Push back if possible'}
                {rating === 'Green' && ' Green — Acceptable as written'}
              </div>
              {findings.map(finding => (
                <FindingCard
                  key={finding.id}
                  finding={finding}
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
          <button className="dl-card negotiation" onClick={() => handleDownload('negotiation')}>
            <div className="dl-icon icon-container">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
            </div>
            <span className="dl-name">Negotiation Pack</span>
            <span className="dl-desc">Redlines + talking points for BD and project managers</span>
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
  editingField: { id: number; field: string } | null
  editValue: string
  onStartEdit: (field: string) => void
  onCancelEdit: () => void
  onSaveEdit: () => void
  onEditValueChange: (value: string) => void
}

function FindingCard({ finding, editingField, editValue, onStartEdit, onCancelEdit, onSaveEdit, onEditValueChange }: FindingCardProps) {
  const [showTalkingPoints, setShowTalkingPoints] = useState(false)
  const isEditing = (field: string) => editingField?.id === finding.id && editingField?.field === field

  return (
    <div className={`finding ${finding.rag_rating}`}>
      <div className="finding-bar"></div>
      <div className="finding-body">
        <div className="finding-top">
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

        {finding.talking_points && finding.rag_rating !== 'Green' && (
          <>
            <button
              className="tp-toggle"
              onClick={() => setShowTalkingPoints(!showTalkingPoints)}
            >
              {showTalkingPoints ? (
                <>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '4px' }}>
                    <polyline points="18 15 12 9 6 15" />
                  </svg>
                  Hide talking points
                </>
              ) : (
                <>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ display: 'inline', verticalAlign: 'middle' }}>
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                  </svg>
                  {' '}Talking points
                </>
              )}
            </button>
            {showTalkingPoints && (
              <div className="tp-body">
                {isEditing('talking_points') ? (
                  <>
                    <textarea
                      className="inline-editor edit-tp"
                      value={editValue}
                      onChange={(e) => onEditValueChange(e.target.value)}
                      rows={Math.max(2, Math.ceil(editValue.length / 60) + 1)}
                    />
                    <div className="edit-actions">
                      <button className="btn-xs btn-xs-save" onClick={onSaveEdit}>✓ Save</button>
                      <button className="btn-xs btn-xs-cancel" onClick={onCancelEdit}>✕ Cancel</button>
                    </div>
                  </>
                ) : (
                  <>
                    {finding.talking_points}
                    <button className="edit-icon-btn" onClick={() => onStartEdit('talking_points')}>
                      ✎ Edit
                    </button>
                  </>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
