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
  /** When it was approved or rejected; null while pending. */
  decided_at?: string | null
  preview: {
    before: ProposalSide[]
    after: { title: string; content: string; citations: string[] }
    guarantees: string[]
  }
}

export interface ContextBundle {
  markdown: string
  task: string | null
  token_budget: number
  tokens_used: number
  included: number
  dropped: { title: string; citation: string }[]
  not_considered: number
  excluded_total: number
  over_budget: boolean
  note: string | null
}

export interface ScanConfig {
  effective: { include: string[]; exclude: string[]; sources: string[]; notes: string[] }
  override: { include: string[]; exclude: string[] }
  config_filename: string
  ignore_filename: string
  rules: string[]
}

export interface EvalQuestionSet {
  version: number
  corpus: string
  about: string[]
  questions: number
  answerable: number
  unanswerable: number
  measures: string[]
}

export interface EvalResult {
  id: string
  question: string
  kind: string
  outcome: string
  verdict: string
  retrieved: string[]
  note: string | null
}

export interface EvalReport {
  corpus: string
  questions: number
  answerable: number
  unanswerable: number
  memories_scanned: number
  semantic: boolean
  elapsed_seconds: number
  retrieval_depth: number
  recall_at_k: Record<string, number | null>
  mrr: number | null
  ndcg_at_10: number | null
  precision_at_5: number | null
  citation_correctness: number | null
  citation_correctness_strict: number | null
  useful_abstention_rate: number | null
  false_abstention_rate: number | null
  retrieval_success_rate: number | null
  answer_rate: number | null
  outcomes: Record<string, number>
  verdicts: Record<string, number>
  results: EvalResult[]
  markdown: string
}

export interface McpInfo {
  server_name: string
  transport: string
  command: string
  env: Record<string, string>
  tools: { name: string; description: string }[]
  writable: boolean
  claude_code_snippet: string
  note: string
}

export interface AffectedMemory {
  memory_id: string
  title: string
  memory_type: string
  status: string
  citation: string
  rel_path: string
  overlap: 'direct' | 'same_file'
  changed_lines: number[][]
  reason: string
}

export interface ImpactReport {
  base: string
  head: string
  resolved: boolean
  changed_files: string[]
  files_with_memories: string[]
  affected: AffectedMemory[]
  note: string | null
  direct: number
}

export interface Commit {
  sha: string
  date: string
  subject: string
}

export interface ApprovalResult {
  proposal_id: string
  kept_id: string
  absorbed_id: string
  citations_before: number
  citations_after: number
  revisions_written: number
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
  related: EvidenceItem[]
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

export interface GraphNode {
  id: string
  title: string
  type: string
  status: string
  importance: number | null
  degree: number
  /** Named by a finding or an explicit link, not merely co-mentioned. */
  flagged: boolean
}

export interface GraphEdge {
  src: string
  dst: string
  /** `shares` is entity co-occurrence; the rest are recorded relationships. */
  kind: 'shares' | 'conflict' | 'duplicate' | string
  reason: string
  weight: number
  /** Where the edge came from: `suggested` is a heuristic nobody has agreed
   *  with, `user` a confirmed judgement, `merge` a consolidation's
   *  consequence, `finding` an open review item. */
  origin?: 'suggested' | 'user' | 'merge' | 'finding'
}

export interface LinkSuggestion {
  src_id: string
  dst_id: string
  src_title: string
  dst_title: string
  src_type: string
  dst_type: string
  /** Summed specificity of everything the pair shares: higher is stronger. */
  score: number
  shared: string[]
  /** Identical titles the duplicate detector did not flag — "related" is
   *  probably the wrong answer, and the UI says so rather than hiding it. */
  same_title: boolean
}

export interface MemoryGraph {
  nodes: GraphNode[]
  edges: GraphEdge[]
  totals: { memories: number; edges_considered: number; connected_memories: number }
  /** What the server left out, so the view can say so rather than look complete. */
  limits: {
    node_limit: number
    edge_limit: number
    entity_spread_max: number
    omitted_memories: number
    omitted_edges: number
    entities_too_common: number
  }
}

export interface Freshness {
  /** null until a freshness check has actually run. Render "never checked" —
   *  not 0%, and above all not 100%. */
  checked_at: string | null
  refs_checked: number
  /** Memories pinning a real file region. Memories citing nothing are in
   *  neither half of the fraction. */
  verifiable: number
  flagged: number
  verified: number
}

export interface ProjectDetail {
  project: Project
  counts: Record<string, number>
  freshness: Freshness
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
  health: () =>
    call<{
      status: string
      schema_version: string
      db_path: string
      db_bytes: number
    }>('/health'),
  listProjects: () => call<Project[]>('/projects'),
  getProject: (id: string) => call<ProjectDetail>(`/projects/${id}`),
  graph: (id: string) => call<MemoryGraph>(`/projects/${id}/graph`),

  /** Unanswered suggestions, strongest first. */
  linkSuggestions: (projectId: string, limit = 25) =>
    call<LinkSuggestion[]>(
      `/projects/${projectId}/links/suggestions?limit=${limit}`,
    ),
  /** Answer several at once. Each still goes through the same guards. */
  batchLinks: (
    projectId: string,
    decisions: { src_id: string; dst_id: string; verdict: 'confirm' | 'dismiss' }[],
  ) =>
    call<{ confirmed: number; dismissed: number; failed: { error: string }[] }>(
      `/projects/${projectId}/links/batch`,
      { method: 'POST', body: JSON.stringify({ decisions }) },
    ),

  // --- curated relationships (ADR-0045) ---------------------------------
  confirmLink: (projectId: string, memoryId: string, otherId: string, kind = 'relates_to') =>
    call<{ src_id: string; dst_id: string; kind: string; origin: string }>(
      `/memories/${memoryId}/links?project_id=${encodeURIComponent(projectId)}`,
      { method: 'POST', body: JSON.stringify({ other_id: otherId, kind }) },
    ),
  dismissLink: (projectId: string, memoryId: string, otherId: string) =>
    call<{ dismissed: string[] }>(
      `/memories/${memoryId}/links/dismiss?project_id=${encodeURIComponent(projectId)}`,
      { method: 'POST', body: JSON.stringify({ other_id: otherId }) },
    ),
  removeLink: (projectId: string, memoryId: string, otherId: string) =>
    call<{ removed: boolean }>(
      `/memories/${memoryId}/links?project_id=${encodeURIComponent(projectId)}` +
        `&other_id=${encodeURIComponent(otherId)}`,
      { method: 'DELETE' },
    ),

  // --- backup, restore, export (ADR-0043) -------------------------------
  takeBackup: (path?: string) =>
    call<{ path: string; bytes: number; schema_version: number; taken_at: string }>(
      '/backup',
      { method: 'POST', body: JSON.stringify({ path: path ?? null }) },
    ),
  /** What a file claims to be. Touches nothing. */
  inspectBackup: (path: string) =>
    call<{ path: string; schema_version: number; projects: number; memories: number }>(
      '/restore/inspect',
      { method: 'POST', body: JSON.stringify({ path }) },
    ),
  /** Replaces every memory in the vault. The server snapshots first and
   *  returns where it put the previous one. */
  restoreBackup: (path: string) =>
    call<{
      restored_from: string
      safety_backup: string
      schema_version: number
      projects: number
      memories: number
    }>('/restore', { method: 'POST', body: JSON.stringify({ path, confirm: true }) }),
  registerProject: (name: string, root_path: string) =>
    call<Project>('/projects', { method: 'POST', body: JSON.stringify({ name, root_path }) }),
  scan: (id: string) => call<ScanResult>(`/projects/${id}/scan`, { method: 'POST' }),
  skipped: (runId: string) =>
    call<{ total: number; by_reason: Record<string, string[]> }>(`/scans/${runId}/skipped`),
  // Superseded and archived records are hidden by default (MEMORY_MODEL.md):
  // serving a replaced claim next to its replacement is misleading. Pass
  // includeInactive to see them.
  /** Assert a memory by hand. Provenance is recorded as a user note, not a
   *  file and line range, because there is no source to cite. */
  createMemory: (
    projectId: string,
    body: { type: string; title: string; content: string; summary?: string | null },
  ) =>
    call<Memory>(`/projects/${projectId}/memories`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
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
  /** Recently closed findings, newest first — what the undo panel reads. */
  resolvedFindings: (id: string) =>
    call<Finding[]>(`/projects/${id}/findings?status=resolved`),
  /** Reopen a resolved finding, re-flagging only the memories the
   *  resolution actually changed. */
  undoFinding: (projectId: string, findingId: string, note?: string) =>
    call<{ finding_id: string; reflagged: string[] }>(
      `/findings/${findingId}/undo?project_id=${encodeURIComponent(projectId)}`,
      { method: 'POST', body: JSON.stringify({ note: note ?? null }) },
    ),
  proposals: (id: string, status: 'pending' | 'approved' | 'rejected' = 'pending') =>
    call<Proposal[]>(`/projects/${id}/proposals?status=${status}`),
  ask: (id: string, question: string, sessionId?: string | null) =>
    call<AnswerBundle>(`/projects/${id}/ask`, {
      method: 'POST',
      body: JSON.stringify({ question, session_id: sessionId ?? null }),
    }),
  approveProposal: (projectId: string, proposalId: string, note?: string) =>
    call<ApprovalResult>(
      `/proposals/${proposalId}/approve?project_id=${encodeURIComponent(projectId)}`,
      { method: 'POST', body: JSON.stringify({ note: note ?? null }) },
    ),
  /** Reverse an approved consolidation. The merge stays in the revision
   *  history and the original approval stays in the feedback log — an undo is
   *  recorded as having happened, not erased. */
  undoProposal: (projectId: string, proposalId: string, note?: string) =>
    call<{
      proposal_id: string
      kept_id: string
      restored_id: string
      citations_removed: number
      content_restored: boolean
    }>(`/proposals/${proposalId}/undo?project_id=${encodeURIComponent(projectId)}`, {
      method: 'POST',
      body: JSON.stringify({ note: note ?? null }),
    }),
  rejectProposal: (projectId: string, proposalId: string, note?: string) =>
    call<{ rejected: boolean; note: string }>(
      `/proposals/${proposalId}/reject?project_id=${encodeURIComponent(projectId)}`,
      { method: 'POST', body: JSON.stringify({ note: note ?? null }) },
    ),
  resolveFinding: (
    projectId: string,
    findingId: string,
    verdict: 'accepted' | 'rejected' | 'resolved',
    note?: string,
  ) =>
    call<{ verdict: string; memories_returned_to_active: string[] }>(
      `/findings/${findingId}/resolve?project_id=${encodeURIComponent(projectId)}`,
      { method: 'POST', body: JSON.stringify({ verdict, note: note ?? null }) },
    ),
  impact: (id: string, base: string, head = 'HEAD') =>
    call<ImpactReport>(
      `/projects/${id}/impact?base=${encodeURIComponent(base)}&head=${encodeURIComponent(head)}`,
    ),
  commits: (id: string) => call<Commit[]>(`/projects/${id}/commits`),
  buildBundle: (id: string, task: string | null, tokenBudget: number) =>
    call<ContextBundle>(`/projects/${id}/context`, {
      method: 'POST',
      body: JSON.stringify({ task, token_budget: tokenBudget }),
    }),
  mcpInfo: (id: string) => call<McpInfo>(`/projects/${id}/mcp`),
  scanConfig: (id: string) => call<ScanConfig>(`/projects/${id}/scan-config`),
  saveScanConfig: (id: string, include: string[], exclude: string[]) =>
    call<ScanConfig>(`/projects/${id}/scan-config`, {
      method: 'PUT',
      body: JSON.stringify({ include, exclude }),
    }),
  evalQuestionSet: () => call<EvalQuestionSet>('/evaluation/question-set'),
  runEvaluation: (allowDownload: boolean) =>
    call<EvalReport>('/evaluation/run', {
      method: 'POST',
      body: JSON.stringify({ limit: 10, allow_download: allowDownload }),
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
