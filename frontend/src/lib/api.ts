// Hand-written client for Stage 2. It is replaced by an openapi-typescript
// generated client in Stage 4, once the endpoint surface stops moving --
// generating against a schema that changes daily buys nothing yet.

export type MemoryType =
  | 'project_fact' | 'architecture' | 'decision' | 'procedure'
  | 'convention' | 'gotcha' | 'current_state'

export type MemoryStatus = 'active' | 'needs_review' | 'superseded' | 'archived'

export interface SourceRef {
  rel_path: string | null
  line_start: number | null
  line_end: number | null
  content_hash: string | null
  git_blob_hash: string | null
  git_commit: string | null
  url: string | null
  user_note: string | null
}

export interface Finding {
  id: string
  kind: 'stale_risk' | 'conflict' | 'duplicate' | 'broken_link' | 'missing_doc'
  severity: 'low' | 'medium' | 'high'
  status: string
  detector: string
  explanation: string
  memory_id: string | null
  other_id: string | null
  evidence: Record<string, unknown>
  created_at: string
}

export interface ProposalSide {
  memory_id: string
  title: string
  content: string
  citations: string[]
  importance: number
  role: 'keep' | 'absorb'
}

export interface Proposal {
  id: string
  finding_id: string | null
  input_ids: string[]
  created_at: string
  preview: {
    before: ProposalSide[]
    after: { title: string; content: string; citations: string[] }
    guarantees: string[]
  }
}

export interface EvidenceItem {
  kind: 'evidence' | 'inference'
  source: 'memory' | 'chunk'
  target_id: string
  title: string
  excerpt: string
  citation: string
  confidence: number | null
  matched_terms: string[]
  why_ranked: string
}

export interface AnswerBundle {
  question: string
  outcome: 'evidence_found' | 'weak_evidence' | 'not_found'
  statement: string
  evidence: EvidenceItem[]
  unknowns: string[]
  semantic_available: boolean
  note: string | null
  session_id: string | null
  turn_id: string | null
}

export interface EmbeddingStatus {
  model_id: string
  dim: number
  cached: boolean
  enabled: boolean
  usable: boolean
  cache_path: string
  download_mb: number
  indexed_memories: number
  indexed_chunks: number
}

export interface AnalysisResult {
  drift_high: number
  drift_medium: number
  drift_low: number
  refs_checked: number
  conflicts_procedure: number
  conflicts_decision: number
  duplicate_candidates: number
  proposals_created: number
  importance_adjusted: number
  open_findings: number
}

export interface Memory {
  id: string
  project_id: string
  type: MemoryType
  title: string
  content: string
  summary: string | null
  status: MemoryStatus
  claim_kind: 'source_fact' | 'interpretation'
  importance: number
  importance_reason: string
  confidence: number
  confidence_reason: string
  extraction_method: string
  created_at: string
  updated_at: string
  // Temporal validity: when the claim was true of the project, which is not
  // when the row was written.
  valid_from: string | null
  valid_until: string | null
  superseded_by: string | null
  supersedes: string | null
  decision: {
    status?: string
    chosen?: string
    alternatives?: string[]
    decided_on?: string
  } | null
  source_refs: SourceRef[]
}

export interface Project {
  id: string
  name: string
  root_path: string
  is_git_repo: boolean
  created_at: string
}

export interface ProjectDetail {
  project: Project
  counts: Record<string, number>
}

export interface Revision {
  id: string
  parent_id: string | null
  title: string
  change_reason: string
  actor: string
  created_at: string
}

export interface MemoryDetail {
  memory: Memory
  citations: string[]
  revisions: Revision[]
}

export interface ScanResult {
  scan_run_id: string
  files_seen: number
  files_new: number
  files_skipped: number
  captures_created: number
  memories_created: number
  git_commit: string | null
  skipped: { rel_path: string; reason: string }[]
}

const BASE = '/api/v1'

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path.startsWith('/health') ? path : BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    // Surface the server's message. Never swallow an error into a blank screen.
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body?.detail) detail = typeof body.detail === 'string'
        ? body.detail : JSON.stringify(body.detail)
    } catch { /* keep the status line */ }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => call<{ status: string; schema_version: string; db_path: string }>('/health'),
  listProjects: () => call<Project[]>('/projects'),
  getProject: (id: string) => call<ProjectDetail>(`/projects/${id}`),
  registerProject: (name: string, root_path: string) =>
    call<Project>('/projects', { method: 'POST', body: JSON.stringify({ name, root_path }) }),
  scan: (id: string) => call<ScanResult>(`/projects/${id}/scan`, { method: 'POST' }),
  skipped: (runId: string) =>
    call<{ total: number; by_reason: Record<string, string[]> }>(`/scans/${runId}/skipped`),
  // Superseded and archived records are hidden by default (MEMORY_MODEL.md):
  // serving a replaced claim next to its replacement is misleading. Pass
  // includeInactive to see them.
  listMemories: (
    id: string,
    type?: string,
    status?: string,
    includeInactive?: boolean,
  ) => {
    const q = new URLSearchParams()
    if (type) q.set('type', type)
    if (status) q.set('status', status)
    if (includeInactive) q.set('include_inactive', 'true')
    const qs = q.toString()
    return call<Memory[]>(`/projects/${id}/memories${qs ? `?${qs}` : ''}`)
  },
  getMemory: (id: string) => call<MemoryDetail>(`/memories/${id}`),
  archiveMemory: (id: string) =>
    call<{ archived: boolean }>(`/memories/${id}/archive`, { method: 'POST' }),
  analyze: (id: string) =>
    call<AnalysisResult>(`/projects/${id}/analyze`, { method: 'POST' }),
  findings: (id: string, kind?: string) =>
    call<Finding[]>(`/projects/${id}/findings${kind ? `?kind=${kind}` : ''}`),
  proposals: (id: string) => call<Proposal[]>(`/projects/${id}/proposals`),
  ask: (id: string, question: string, sessionId?: string | null) =>
    call<AnswerBundle>(`/projects/${id}/ask`, {
      method: 'POST',
      body: JSON.stringify({ question, session_id: sessionId ?? null }),
    }),
  embeddingStatus: (id: string) =>
    call<EmbeddingStatus>(`/projects/${id}/embeddings`),
  buildEmbeddings: (id: string, allowDownload: boolean) =>
    call<{ embedded_memories: number; embedded_chunks: number; skipped: string | null }>(
      `/projects/${id}/embeddings/build`,
      { method: 'POST', body: JSON.stringify({ allow_download: allowDownload }) },
    ),
}

/** Date-only display for an ISO timestamp the backend normalised. */
export function shortDate(iso: string | null): string {
  return iso ? iso.slice(0, 10) : ''
}

export const TYPE_LABEL: Record<MemoryType, string> = {
  project_fact: 'Fact',
  architecture: 'Architecture',
  decision: 'Decision',
  procedure: 'Procedure',
  convention: 'Convention',
  gotcha: 'Gotcha',
  current_state: 'Current state',
}

export function citationOf(ref: SourceRef): string {
  if (ref.rel_path && ref.line_start)
    return `${ref.rel_path}:${ref.line_start}-${ref.line_end ?? ref.line_start}`
  return ref.rel_path ?? ref.url ?? ref.user_note ?? 'unknown'
}
