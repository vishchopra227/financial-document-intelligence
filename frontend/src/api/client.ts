/**
 * API client for FinSight Intelligence backend.
 */

export interface SystemHealth {
  status: string;
  version: string;
  environment: string;
  database: {
    status: string;
    type: string;
    target?: string;
    error?: string;
  };
  vector_store: {
    backend: string;
    status: string;
    storage_path: string;
  };
  ai_providers: {
    llm_provider: string;
    llm_model: string;
    llm_configured: boolean;
    embedding_provider: string;
    embedding_model: string;
    embedding_configured: boolean;
  };
}

export interface SystemSettings {
  project_name: string;
  environment: string;
  max_upload_size_mb: number;
  vector_store_backend: string;
  rag: {
    top_k: number;
    chunk_size: number;
    chunk_overlap: number;
    similarity_threshold: number;
    hybrid_search: boolean;
  };
  providers: {
    llm: {
      name: string;
      model: string;
      has_api_key: boolean;
    };
    embedding: {
      name: string;
      model: string;
      has_api_key: boolean;
    };
  };
  security_note: string;
}

export interface DocumentModel {
  id: string;
  original_filename: string;
  file_type: string;
  file_size_bytes: number;
  workspace_id: string;
  page_count: number;
  chunk_count: number;
  status: string;
  error_message?: string;
  document_summary?: string;
  reporting_period?: string;
  company_name?: string;
  created_at: string;
  updated_at: string;
}

export interface DocumentListResponse {
  documents: DocumentModel[];
  total_count: number;
  indexed_count: number;
}

export interface Citation {
  chunk_id: string;
  document_id: string;
  filename: string;
  page_number?: number;
  excerpt: string;
  similarity_score?: number;
}

export interface ChatResponse {
  answer: string;
  conversation_id: string;
  message_id: string;
  citations: Citation[];
  retrieved_chunk_count: number;
  has_sufficient_evidence: boolean;
  retrieval_latency_ms: number;
  generation_latency_ms: number;
  model_name: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  citations?: Citation[];
  created_at?: string;
  latency?: string;
}

export interface DocumentEvidenceSummary {
  document_id: string;
  filename: string;
  page_count: number;
  company_name?: string | null;
  reporting_period?: string | null;
  top_chunks: string[];
  pages_cited: number[];
}

export interface ComparisonResult {
  query: string;
  documents: DocumentEvidenceSummary[];
  analysis: string;
  citations: Citation[];
  has_sufficient_evidence: boolean;
  retrieval_latency_ms: number;
  generation_latency_ms: number;
  model_name: string;
}

export interface MetricComparisonValue {
  document_name: string;
  raw_value: string;
  numeric_value?: number | null;
  currency?: string | null;
  unit?: string | null;
  period?: string | null;
  page_number?: number | null;
  source_excerpt?: string | null;
  evidence: Array<{
    raw_value: string;
    numeric_value?: number | null;
    currency?: string | null;
    unit?: string | null;
    period?: string | null;
    page_number?: number | null;
    source_excerpt?: string | null;
    confidence?: number;
  }>;
}

export interface MetricComparisonRow {
  metric_name: string;
  reporting_period?: string | null;
  values: Record<string, MetricComparisonValue>;
}

export interface MetricComparisonTable {
  document_ids: string[];
  documents: Array<{ id: string; filename: string }>;
  metrics_table: MetricComparisonRow[];
}

export interface MetricItem {
  id: string;
  document_id: string;
  metric_name: string;
  raw_value: string;
  numeric_value?: number;
  unit?: string;
  currency?: string;
  reporting_period?: string;
  page_number?: number;
  source_excerpt?: string;
  confidence: number;
}

export interface DocumentMetricsResponse {
  document_id: string;
  document_name: string;
  metrics: MetricItem[];
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';

export async function checkHealth(): Promise<SystemHealth> {
  const response = await fetch(`${API_BASE}/health`);
  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`);
  }
  return response.json();
}

export async function getSettings(): Promise<SystemSettings> {
  const response = await fetch(`${API_BASE}/settings`);
  if (!response.ok) {
    throw new Error(`Failed to fetch settings: status ${response.status}`);
  }
  return response.json();
}

export async function uploadDocument(file: File, workspaceId: string = 'default'): Promise<DocumentModel> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('workspace_id', workspaceId);

  const response = await fetch(`${API_BASE}/documents/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Upload failed with status ${response.status}`);
  }
  return response.json();
}

export async function listDocuments(
  workspaceId: string = 'default',
  searchQuery?: string
): Promise<DocumentListResponse> {
  const params = new URLSearchParams({ workspace_id: workspaceId });
  if (searchQuery) {
    params.append('search', searchQuery);
  }

  const response = await fetch(`${API_BASE}/documents?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`Failed to list documents: status ${response.status}`);
  }
  return response.json();
}

export async function getDocumentPreview(documentId: string, pageNumber?: number): Promise<any> {
  const params = new URLSearchParams();
  if (pageNumber !== undefined) {
    params.append('page', pageNumber.toString());
  }

  const response = await fetch(`${API_BASE}/documents/${documentId}/preview?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch document preview: status ${response.status}`);
  }
  return response.json();
}

export async function deleteDocument(documentId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/documents/${documentId}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new Error(`Failed to delete document: status ${response.status}`);
  }
}

export async function askQuestion(
  query: string,
  documentIds?: string[],
  conversationId?: string,
  workspaceId: string = 'default',
  topK: number = 4
): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query,
      document_ids: documentIds && documentIds.length > 0 ? documentIds : null,
      conversation_id: conversationId,
      workspace_id: workspaceId,
      top_k: topK,
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Chat request failed: status ${response.status}`);
  }
  return response.json();
}

export async function compareDocuments(
  documentIds: string[],
  query: string,
  topKPerDoc: number = 3
): Promise<ComparisonResult> {
  const response = await fetch(`${API_BASE}/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      document_ids: documentIds,
      query,
      top_k_per_doc: topKPerDoc,
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Comparison failed: status ${response.status}`);
  }
  return response.json();
}

export async function compareMetricsTable(documentIds: string[]): Promise<MetricComparisonTable> {
  const params = new URLSearchParams({ document_ids: documentIds.join(',') });
  const response = await fetch(`${API_BASE}/compare/metrics?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch metrics table: status ${response.status}`);
  }
  return response.json();
}

export async function getDocumentMetrics(documentId: string): Promise<DocumentMetricsResponse> {
  const response = await fetch(`${API_BASE}/metrics/document/${documentId}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch metrics: status ${response.status}`);
  }
  return response.json();
}

export async function downloadComparisonExport(
  documentIds: string[],
  query: string,
  format: 'json' | 'csv',
  topKPerDoc: number = 3
): Promise<Blob> {
  const response = await fetch(`${API_BASE}/compare/export?format=${format}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ document_ids: documentIds, query, top_k_per_doc: topKPerDoc }),
  });
  if (!response.ok) {
    throw new Error(`Export failed: status ${response.status}`);
  }
  return response.blob();
}
