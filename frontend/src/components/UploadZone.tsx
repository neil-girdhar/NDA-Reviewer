import { useRef, useState } from 'react'
import './UploadZone.css'

interface UploadZoneProps {
  onFileSelect: (file: File) => void;
  selectedFile: File | null;
  disabled?: boolean;
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
    fileInputRef.current?.click();
  };

  const handleBrowseClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    fileInputRef.current?.click();
  };

  return (
    <div
      className={`upload-card ${isDragOver ? 'drag-over' : ''} ${disabled ? 'disabled' : ''}`}
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
      <div className="upload-icon-wrap">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
        </svg>
      </div>
      <div className="upload-title">
        {selectedFile ? selectedFile.name : 'Drop your NDA here'}
      </div>
      <p className="upload-sub">
        {selectedFile
          ? `${(selectedFile.size / 1024).toFixed(0)} KB`
          : <>or <span className="browse" onClick={handleBrowseClick}>browse to upload</span></>
        }
      </p>
      <span className="upload-meta">PDF · DOCX · max 20 MB</span>
    </div>
  );
}
