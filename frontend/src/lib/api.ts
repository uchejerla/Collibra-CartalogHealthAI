/**
 * src/lib/api.ts — Typed API client for Catalog Health AI backend.
 *
 * All functions throw on non-2xx responses.
 * Base URL is read from NEXT_PUBLIC_API_URL env var (falls back to localhost:8000).
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

// ─────────────────────────────────────────────────────────────────────────────
// Response types (mirror Pydantic models in backend/app/main.py)
// ─────────────────────────────────────────────────────────────────────────────

export interface HealthScore {
  scan_id:        string | null
  health_score:   number
  audit_score:    number | null
  high_count:     number
  medium_count:   number
  low_count:      number
  total_findings: number
  total_assets:   number
  scanned_at:     string | null
  breakdown:      Record<string, Record<string, number>>
}

export interface Finding {
  id:          string
  asset_name:  string | null
  agent:       string
  rule_id:     string
  issue_type:  string
  severity:    "High" | "Medium" | "Low"
  message:     string
  status:      string
  created_at:  string
}

export interface IssuesResponse {
  scan_id:     string | null
  total:       number
  page:        number
  page_size:   number
  findings:    Finding[]
}

export interface Summary {
  scan_id:      string | null
  executive:    string | null
  steward:      string | null
  trend:        string | null
  generated_at: string | null
  from_cache:   boolean
}

export interface ScanRun {
  scan_id:        string
  status:         string
  health_score:   number | null
  audit_score:    number | null
  total_assets:   number
  total_findings: number
  started_at:     string
  completed_at:   string | null
}

export interface IngestResponse {
  scan_id:            string
  records_processed:  number
  message:            string
}

// ─────────────────────────────────────────────────────────────────────────────
// Fetch helper
// ─────────────────────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const body = await res.text().catch(() => "")
    throw new Error(`API ${res.status} at ${path}: ${body}`)
  }
  return res.json() as Promise<T>
}

// ─────────────────────────────────────────────────────────────────────────────
// API client
// ─────────────────────────────────────────────────────────────────────────────

export const api = {
  /** GET /health-score — governance health score from latest scan */
  getHealthScore(): Promise<HealthScore> {
    return apiFetch<HealthScore>("/health-score")
  },

  /** GET /issues — paginated filtered findings list */
  getIssues(params?: {
    severity?: string
    agent?: string
    issue_type?: string
    status?: string
    page?: number
    page_size?: number
  }): Promise<IssuesResponse> {
    const qs = new URLSearchParams()
    if (params?.severity)   qs.set("severity",   params.severity)
    if (params?.agent)      qs.set("agent",       params.agent)
    if (params?.issue_type) qs.set("issue_type",  params.issue_type)
    if (params?.status)     qs.set("status",      params.status)
    if (params?.page)       qs.set("page",        String(params.page))
    if (params?.page_size)  qs.set("page_size",   String(params.page_size))
    const query = qs.toString() ? `?${qs}` : ""
    return apiFetch<IssuesResponse>(`/issues${query}`)
  },

  /** GET /summary — AI-generated executive and steward summaries */
  getSummary(forceRefresh = false): Promise<Summary> {
    return apiFetch<Summary>(`/summary${forceRefresh ? "?force_refresh=true" : ""}`)
  },

  /** POST /run-scan — trigger the 4-agent pipeline for a given scan */
  runScan(scanId: string): Promise<ScanRun> {
    return apiFetch<ScanRun>(`/run-scan?scan_id=${scanId}`, { method: "POST" })
  },

  /** POST /upload-assets — ingest a Collibra asset export CSV */
  uploadAssets(file: File): Promise<IngestResponse> {
    const form = new FormData()
    form.append("file", file)
    return apiFetch<IngestResponse>("/upload-assets", {
      method: "POST",
      body: form,
      headers: {},   // Let browser set multipart boundary
    })
  },

  /** POST /upload-lineage — ingest a Collibra lineage export CSV */
  uploadLineage(file: File, scanId: string): Promise<IngestResponse> {
    const form = new FormData()
    form.append("file", file)
    return apiFetch<IngestResponse>(`/upload-lineage?scan_id=${scanId}`, {
      method: "POST",
      body: form,
      headers: {},
    })
  },

  /** GET /healthz — service liveness check */
  healthz(): Promise<{ status: string; version: string; env: string }> {
    return apiFetch("/healthz")
  },
}
