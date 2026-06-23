import { useRef, useState } from 'react'
import './UploadZone.css'

interface UploadZoneProps {
  onFileSelect: (file: File) => void;
  selectedFile: File | null;
  disabled?: boolean;
}

function WordIcon() {
  return (
    <svg
      width="44" height="44"
      viewBox="0 0 100 100"
      xmlns="http://www.w3.org/2000/svg"
      style={{ flexShrink: 0, display: 'block' }}
    >
      <defs>
        <clipPath id="word-bg-clip">
          <rect x="28" y="5" width="67" height="63" rx="8" ry="8" />
        </clipPath>
      </defs>
      {/* Background page: 5 horizontal bands, light→dark blue */}
      <rect x="28" y="5"  width="67" height="63" rx="8" ry="8" fill="#41A5EE" />
      <rect x="28" y="18" width="67" height="13" fill="#2B9EDE" clipPath="url(#word-bg-clip)" />
      <rect x="28" y="31" width="67" height="13" fill="#1B8ACC" clipPath="url(#word-bg-clip)" />
      <rect x="28" y="44" width="67" height="13" fill="#185ABD" clipPath="url(#word-bg-clip)" />
      <rect x="28" y="57" width="67" height="11" fill="#103F91" clipPath="url(#word-bg-clip)" />
      {/* Foreground W card */}
      <rect x="5" y="27" width="56" height="68" rx="9" ry="9" fill="#185ABD" />
      {/* W letter */}
      <text
        x="33" y="79"
        textAnchor="middle"
        fill="white"
        fontFamily="'Segoe UI', Arial, sans-serif"
        fontSize="52"
        fontWeight="900"
      >W</text>
    </svg>
  )
}

function PdfIcon() {
  return (
    <div style={{
      width: 44, height: 44, borderRadius: 8, flexShrink: 0,
      background: '#CC0000',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      color: '#fff',
      fontFamily: "'Helvetica Neue', Arial, sans-serif",
      fontSize: 14, fontWeight: 800, letterSpacing: 1, userSelect: 'none',
    }}>PDF</div>
  )
}

export default function UploadZone({ onFileSelect, selectedFile, disabled }: UploadZoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) onFileSelect(file);
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onFileSelect(file);
  };

  const handleClick = () => {
    if (!disabled) fileInputRef.current?.click();
  };

  const handleBrowseClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    fileInputRef.current?.click();
  };

  const ext = selectedFile?.name.split('.').pop()?.toLowerCase();
  const isWord = ext === 'docx';

  return (
    <div
      className={`upload-card ${selectedFile ? 'has-file' : ''} ${isDragOver ? 'drag-over' : ''} ${disabled ? 'disabled' : ''}`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={handleClick}
    >
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx"
        onChange={handleFileInputChange}
        style={{ display: 'none' }}
      />

      {selectedFile ? (
        <div className="upload-selected">
          <div className="file-type-icon">
            {isWord ? <WordIcon /> : <PdfIcon />}
          </div>
          <div className="file-info">
            <div className="file-name">{selectedFile.name}</div>
            <div className="file-size">{(selectedFile.size / 1024).toFixed(0)} KB — click to change</div>
          </div>
        </div>
      ) : (
        <>
          <div className="upload-icon-wrap">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
          </div>
          <div className="upload-title">Drop your NDA here</div>
          <p className="upload-sub">
            or <span className="browse" onClick={handleBrowseClick}>browse to upload</span>
          </p>
          <span className="upload-meta">PDF · DOCX · max 20 MB</span>
        </>
      )}
    </div>
  );
}
