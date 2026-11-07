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
  listMemories: (id: string, type?: string, status?: string) => {
    const q = new URLSearchParams()
    if (type) q.set('type', type)
    if (status) q.set('status', status)
    const qs = q.toString()
    return call<Memory[]>(`/projects/${id}/memories${qs ? `?${qs}` : ''}`)
  },
  getMemory: (id: string) => call<MemoryDetail>(`/memories/${id}`),
  archiveMemory: (id: string) =>
    call<{ archived: boolean }>(`/memories/${id}/archive`, { method: 'POST' }),
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
