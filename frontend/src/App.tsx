import { useState } from 'react'
import './App.css'
import UploadZone from './components/UploadZone'
import ResultsView from './components/ResultsView'
import { analyzeDocument } from './api/client'
import type { ReviewResult } from './types'

export default function App() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [statusMessage, setStatusMessage] = useState('')
  const [results, setResults] = useState<ReviewResult | null>(null)

  const handleFileSelect = (file: File) => {
    setSelectedFile(file)
    setStatusMessage('')
    setResults(null)
  }

  const handleAnalyze = async () => {
    if (!selectedFile) return

    setIsAnalyzing(true)
    setResults(null)
    setStatusMessage('Uploading…')

    try {
      const result = await analyzeDocument(selectedFile, (msg) => setStatusMessage(msg))
      setResults(result)
      setStatusMessage('')
    } catch (error) {
      setStatusMessage(`Error: ${error instanceof Error ? error.message : 'Analysis failed'}`)
    } finally {
      setIsAnalyzing(false)
    }
  }

  const handleReset = () => {
    setSelectedFile(null)
    setResults(null)
    setStatusMessage('')
    setIsAnalyzing(false)
  }

  return (
    <div className="app-content">
      <main>
        <UploadZone
          onFileSelect={handleFileSelect}
          selectedFile={selectedFile}
          disabled={isAnalyzing}
        />

        <div className="options-row">
          <button
            className="btn-primary"
            onClick={handleAnalyze}
            disabled={!selectedFile || isAnalyzing}
          >
            Analyze NDA
          </button>
        </div>

        {statusMessage && (
          <div className="status-message">
            {isAnalyzing && <span className="spinner" />}
            {statusMessage}
          </div>
        )}

        {results && (
          <ResultsView
            results={results}
            onReset={handleReset}
          />
        )}
      </main>
    </div>
  )
}
