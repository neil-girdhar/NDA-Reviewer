export type RagRating = 'Red' | 'Amber' | 'Green';

export interface Finding {
  id: number;
  clause_type: string;
  plain_english_summary: string;
  risk_reason: string;
  rag_rating: RagRating;
  suggested_redline: string | null;
  replacement_language: string | null;
  talking_points: string | null;
}

export interface Review {
  id: number;
  filename: string;
  overall_risk: RagRating;
  findings: Finding[];
}

export interface UploadResponse {
  document_id: number;
  filename: string;
}

export interface ReviewResponse {
  id: number;
  filename: string;
  overall_risk: RagRating;
  findings: Finding[];
}

export type ReviewResult = ReviewResponse;

export interface UpdateFindingPayload {
  replacement_language?: string;
  talking_points?: string;
}
