import type { UploadResponse, ReviewResponse, UpdateFindingPayload } from '../types'

const API_BASE = '/api'

export async function analyzeDocument(
  file: File,
  onStatusChange: (message: string) => void
): Promise<ReviewResponse> {
  onStatusChange('Uploading…')
  const uploadResult = await uploadFile(file)

  onStatusChange('Analysing clauses with Claude Opus — this takes 30–60 seconds…')
  const reviewResult = await reviewDocument(uploadResult.document_id)

  return reviewResult
}

export async function uploadFile(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE}/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Upload failed');
  }

  return response.json();
}

export async function reviewDocument(documentId: number): Promise<ReviewResponse> {
  const response = await fetch(`${API_BASE}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ document_id: documentId }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Review failed');
  }

  return response.json();
}

export async function updateFinding(
  findingId: number,
  payload: UpdateFindingPayload
): Promise<void> {
  const response = await fetch(`${API_BASE}/finding/${findingId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Update failed');
  }
}

export function getReportDownloadUrl(reviewId: number): string {
  return `${API_BASE}/download/${reviewId}/report`;
}

export function getNegotiationDownloadUrl(reviewId: number): string {
  return `${API_BASE}/download/${reviewId}/negotiation`;
}

export async function downloadCleanCopy(reviewId: number, filename: string): Promise<void> {
  const response = await fetch(`${API_BASE}/download/${reviewId}/clean`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Clean copy generation failed');
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;

  const contentDisposition = response.headers.get('Content-Disposition');
  const match = contentDisposition?.match(/filename="([^"]+)"/);
  a.download = match ? match[1] : `${filename}_clean.docx`;

  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
