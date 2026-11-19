import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, type Finding } from '../lib/api'
import { useProject } from '../lib/useProject'
import { Badge, Button, Citation, Empty, ErrorNote, Panel, ScreenHeader, Stat, NoProject } from '../components/ui'

const KIND_LABEL: Record<Finding['kind'], string> = {
  stale_risk: 'May be stale',
  conflict: 'Contradiction',
  duplicate: 'Possible duplicate',
  broken_link: 'Broken source',
  missing_doc: 'Missing doc',
}

function severityTone(severity: Finding['severity']) {
  return severity === 'high' ? 'warn' : severity === 'medium' ? 'info' : 'neutral'
}

/** Diff-style before/after, with the decision that applies it. */
function ProposalPreview({
  proposal,
  projectId,
  onDecided,
}: {
  proposal: import('../lib/api').Proposal
  projectId: string
  onDecided: () => void
}) {
  const { before, after, guarantees } = proposal.preview
  const approve = useMutation({
    mutationFn: () => api.approveProposal(projectId, proposal.id, 'approved in review'),
    onSuccess: onDecided,
  })
  const reject = useMutation({
    mutationFn: () => api.rejectProposal(projectId, proposal.id, 'not a duplicate'),
    onSuccess: onDecided,
  })
  return (
    <div className="space-y-3">
      <div className="grid md:grid-cols-2 gap-2">
        {before.map((side) => (
          <div
            key={side.memory_id}
            className="rounded-md border p-2.5"
            style={{
              borderColor: side.role === 'keep' ? 'var(--ok)' : 'var(--border)',
              background: side.role === 'keep' ? 'var(--ok-soft)' : 'transparent',
            }}
          >
            <div className="flex items-center justify-between gap-2 mb-1">
              <span className="text-[12px] font-medium">{side.title}</span>
              <Badge tone={side.role === 'keep' ? 'ok' : 'neutral'}>
                {side.role === 'keep' ? 'kept' : 'absorbed'}
              </Badge>
            </div>
            <div className="flex flex-wrap gap-1 mb-1.5">
              {side.citations.map((c) => (
                <Citation key={c}>{c}</Citation>
              ))}
            </div>
            <pre
              className="mono whitespace-pre-wrap text-[11px] max-h-24 overflow-auto"
              style={{ color: 'var(--muted)' }}
            >
              {side.content.slice(0, 400)}
            </pre>
          </div>
        ))}
      </div>

      <div
        className="rounded-md border p-2.5"
        style={{ borderColor: 'var(--border)', background: 'var(--chip)' }}
      >
        <div className="text-[12px] font-medium mb-1">After approval</div>
        <div className="flex flex-wrap gap-1 mb-1.5">
          {after.citations.map((c) => (
            <Citation key={c}>{c}</Citation>
          ))}
        </div>
        <pre className="mono whitespace-pre-wrap text-[11px] max-h-24 overflow-auto">
          {after.content.slice(0, 400)}
        </pre>
      </div>

      <ul className="text-[11px] space-y-0.5" style={{ color: 'var(--muted)' }}>
        {guarantees.map((g) => (
          <li key={g}>· {g}</li>
        ))}
      </ul>

      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={() => approve.mutate()}
          disabled={approve.isPending || reject.isPending}
          className="rounded-md px-2.5 py-1 text-[12px] font-medium text-white disabled:opacity-50"
          style={{ background: 'var(--ok)' }}
        >
          {approve.isPending ? 'Merging…' : 'Approve merge'}
        </button>
        <button
          onClick={() => reject.mutate()}
          disabled={approve.isPending || reject.isPending}
          className="rounded-md border px-2.5 py-1 text-[12px] font-medium disabled:opacity-50"
          style={{ borderColor: 'var(--border)' }}
        >
          {reject.isPending ? 'Dismissing…' : 'Not a duplicate'}
        </button>
        <span className="text-[11px]" style={{ color: 'var(--muted)' }}>
          Approving supersedes the absorbed record; it is never deleted.
        </span>
      </div>

      {approve.isError && <ErrorNote error={approve.error} />}
      {reject.isError && <ErrorNote error={reject.error} />}
      {approve.data && (
        <div
          className="rounded-md px-2.5 py-2 text-[12px]"
          style={{ background: 'var(--ok-soft)', color: 'var(--ok)' }}
        >
          Merged. Citations {approve.data.citations_before} →{' '}
          {approve.data.citations_after}, {approve.data.revisions_written} revisions
          written, absorbed record kept as history.
        </div>
      )}
    </div>
  )
}

/** Closing a finding is a recorded decision, not a dismissal (ADR-0007). */
function FindingActions({
  finding,
  projectId,
  onDecided,
}: {
  finding: Finding
  projectId: string
  onDecided: () => void
}) {
  const act = useMutation({
    mutationFn: (verdict: 'accepted' | 'rejected') =>
      api.resolveFinding(
        projectId,
        finding.id,
        verdict,
        verdict === 'rejected' ? 'false positive' : 'needs attention',
      ),
    onSuccess: onDecided,
  })
  return (
    <div className="flex flex-wrap items-center gap-2 pl-1">
      <button
        onClick={() => act.mutate('accepted')}
        disabled={act.isPending}
        className="rounded border px-2 py-0.5 text-[11px] disabled:opacity-50"
        style={{ borderColor: 'var(--border)' }}
      >
        Needs attention
      </button>
      <button
        onClick={() => act.mutate('rejected')}
        disabled={act.isPending}
        className="rounded border px-2 py-0.5 text-[11px] disabled:opacity-50"
        style={{ borderColor: 'var(--border)' }}
      >
        False positive
      </button>
      {act.isError && <ErrorNote error={act.error} />}
    </div>
  )
}

/**
 * What has already been applied, and the way back.
 *
 * A consolidation that leaves no trace in the UI cannot be undone, however
 * reversible it is underneath — which is why the approval flow had no undo
 * for so long despite the lineage being fully preserved.
 */
function AppliedConsolidations({ projectId }: { projectId: string }) {
  const qc = useQueryClient()
  const approved = useQuery({
    queryKey: ['proposals', projectId, 'approved'],
    queryFn: () => api.proposals(projectId, 'approved'),
  })
  const [undoing, setUndoing] = useState<string | null>(null)

  const undo = useMutation({
    mutationFn: (id: string) => api.undoProposal(projectId, id, 'undone from review'),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['proposals', projectId] })
      qc.invalidateQueries({ queryKey: ['proposals', projectId, 'approved'] })
      qc.invalidateQueries({ queryKey: ['findings', projectId] })
      qc.invalidateQueries({ queryKey: ['memories'] })
      qc.invalidateQueries({ queryKey: ['graph', projectId] })
      setUndoing(null)
    },
    onError: () => setUndoing(null),
  })

  const rows = approved.data ?? []
  if (approved.isLoading || rows.length === 0) return null

  return (
    <Panel title={`Applied consolidations (${rows.length})`}>
      {undo.isError && <ErrorNote error={undo.error} />}
      <ul className="space-y-2">
        {rows.map((p) => (
          <li
            key={p.id}
            className="flex items-start gap-3 border-t pt-2 first:border-0 first:pt-0"
            style={{ borderColor: 'var(--border)' }}
          >
            <div className="min-w-0 flex-1">
              <div className="text-[13px]" style={{ color: 'var(--text)' }}>
                {p.preview.after.title}
              </div>
              <div className="mono mt-0.5 text-[11px]" style={{ color: 'var(--muted)' }}>
                merged {p.input_ids.length} records · {p.preview.after.citations.length} citations
                {p.decided_at && ` · ${new Date(p.decided_at).toLocaleString()}`}
              </div>
            </div>
            <button
              className="mono shrink-0 rounded border px-2 py-1 text-[11px]"
              style={{ borderColor: 'var(--border)', color: 'var(--text)' }}
              disabled={undo.isPending}
              onClick={() => {
                setUndoing(p.id)
                undo.mutate(p.id)
              }}
            >
              {undoing === p.id && undo.isPending ? 'undoing…' : 'Undo'}
            </button>
          </li>
        ))}
      </ul>
      <p className="mono mt-2 text-[11px]" style={{ color: 'var(--muted)' }}>
        Undo restores the absorbed record and the keeper's previous wording. The merge
        stays in the revision history; nothing is erased.
      </p>
    </Panel>
  )
}

/** Decisions already taken on findings, and the way back. */
function ResolvedFindings({ projectId }: { projectId: string }) {
  const qc = useQueryClient()
  const resolved = useQuery({
    queryKey: ['findings', projectId, 'resolved'],
    queryFn: () => api.resolvedFindings(projectId),
  })
  // A finding closed by approving a consolidation cannot be reopened here --
  // `undo_resolution` refuses it, because undoing the merge is what actually
  // reverses that decision. Offering the button anyway is a guaranteed 409,
  // so these rows point at the panel above instead.
  const applied = useQuery({
    queryKey: ['proposals', projectId, 'approved'],
    queryFn: () => api.proposals(projectId, 'approved'),
  })
  const closedByMerge = new Set(
    (applied.data ?? []).flatMap((p) => (p.finding_id ? [p.finding_id] : [])),
  )
  // Until that list arrives the set is empty, so every row would briefly
  // offer Reopen -- including the ones the backend must refuse. Hold the
  // buttons rather than show one that cannot work.
  const knowWhichAreMergeClosed = !applied.isLoading
  const [undoing, setUndoing] = useState<string | null>(null)

  const undo = useMutation({
    mutationFn: (id: string) => api.undoFinding(projectId, id, 'reopened from review'),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['findings', projectId] })
      qc.invalidateQueries({ queryKey: ['findings', projectId, 'resolved'] })
      qc.invalidateQueries({ queryKey: ['memories'] })
      qc.invalidateQueries({ queryKey: ['graph', projectId] })
      setUndoing(null)
    },
    onError: () => setUndoing(null),
  })

  const rows = resolved.data ?? []
  if (resolved.isLoading || rows.length === 0) return null

  return (
    <Panel title={`Recently decided (${rows.length})`}>
      {undo.isError && <ErrorNote error={undo.error} />}
      <ul className="space-y-2">
        {rows.map((f) => (
          <li
            key={f.id}
            className="flex items-start gap-3 border-t pt-2 first:border-0 first:pt-0"
            style={{ borderColor: 'var(--border)' }}
          >
            <Badge tone={f.status === 'rejected' ? 'neutral' : 'ok'}>{f.status}</Badge>
            <div className="min-w-0 flex-1">
              <div className="text-[13px]" style={{ color: 'var(--text)' }}>
                {KIND_LABEL[f.kind] ?? f.kind}
              </div>
              <div className="mono mt-0.5 truncate text-[11px]" style={{ color: 'var(--muted)' }}>
                {f.explanation}
              </div>
            </div>
            {closedByMerge.has(f.id) ? (
              <span
                className="mono shrink-0 text-[11px]"
                style={{ color: 'var(--muted)' }}
                title="Undo the consolidation above to reverse this."
              >
                closed by a merge
              </span>
            ) : (
              <button
                className="mono shrink-0 rounded border px-2 py-1 text-[11px]"
                style={{ borderColor: 'var(--border)', color: 'var(--text)' }}
                disabled={undo.isPending || !knowWhichAreMergeClosed}
                onClick={() => {
                  setUndoing(f.id)
                  undo.mutate(f.id)
                }}
              >
                {undoing === f.id && undo.isPending ? 'reopening…' : 'Reopen'}
              </button>
            )}
          </li>
        ))}
      </ul>
      <p className="mono mt-2 text-[11px]" style={{ color: 'var(--muted)' }}>
        Reopening re-flags only the memories the decision changed. Both decisions stay in
        the record.
      </p>
    </Panel>
  )
}

/**
 * Relationship suggestions, ranked, for triage.
 *
 * There is deliberately **no "confirm all"**. Agreeing to several hundred
 * relationships in one click would record a judgement nobody made, which is
 * the thing this product spends its effort not doing. Selection is explicit;
 * the batch button only applies what you ticked.
 */
function SuggestedRelationships({ projectId }: { projectId: string }) {
  const qc = useQueryClient()
  const [picked, setPicked] = useState<Set<string>>(new Set())

  const suggestions = useQuery({
    queryKey: ['link-suggestions', projectId],
    queryFn: () => api.linkSuggestions(projectId, 25),
  })

  const decide = useMutation({
    mutationFn: (decisions: { src_id: string; dst_id: string; verdict: 'confirm' | 'dismiss' }[]) =>
      api.batchLinks(projectId, decisions),
    onSuccess: () => {
      setPicked(new Set())
      qc.invalidateQueries({ queryKey: ['link-suggestions', projectId] })
      qc.invalidateQueries({ queryKey: ['graph', projectId] })
    },
  })

  const rows = suggestions.data ?? []
  const key = (s: { src_id: string; dst_id: string }) => `${s.src_id}:${s.dst_id}`
  const chosen = rows.filter((s) => picked.has(key(s)))

  const apply = (verdict: 'confirm' | 'dismiss') =>
    decide.mutate(chosen.map((s) => ({ src_id: s.src_id, dst_id: s.dst_id, verdict })))

  if (suggestions.isError) {
    return (
      <Panel title="Suggested relationships">
        <ErrorNote error={suggestions.error} />
      </Panel>
    )
  }
  if (suggestions.isLoading) {
    return (
      <Panel title="Suggested relationships">
        <div className="h-16 animate-pulse rounded" style={{ background: 'var(--chip)' }} aria-busy />
      </Panel>
    )
  }
  if (rows.length === 0) return null

  return (
    <Panel
      title={`Suggested relationships (${rows.length})`}
      right={
        <span className="mono text-[11px]" style={{ color: 'var(--muted)' }}>
          strongest first
        </span>
      }
    >
      <p className="mb-2 text-[12px]" style={{ color: 'var(--muted)' }}>
        Pairs that keep appearing together. Ranked by how specific the overlap is —
        three rare files in common says more than one vague one. Nothing is recorded
        until you say so.
      </p>

      {decide.isError && <ErrorNote error={decide.error} />}
      {decide.data && decide.data.failed.length > 0 && (
        <p className="mono mb-2 text-[11px]" style={{ color: 'var(--warn)' }}>
          {decide.data.failed.length} could not be applied: {decide.data.failed[0].error}
        </p>
      )}

      <ul className="space-y-1">
        {rows.map((s) => {
          const id = key(s)
          const on = picked.has(id)
          return (
            <li
              key={id}
              className="flex items-start gap-2 border-t py-1.5 first:border-0"
              style={{ borderColor: 'var(--border)' }}
            >
              <input
                type="checkbox"
                checked={on}
                aria-label={`Select ${s.src_title} and ${s.dst_title}`}
                onChange={() =>
                  setPicked((prev) => {
                    const next = new Set(prev)
                    if (next.has(id)) next.delete(id)
                    else next.add(id)
                    return next
                  })
                }
                className="mt-1 shrink-0"
              />
              <div className="min-w-0 flex-1">
                <div className="truncate text-[12px]" style={{ color: 'var(--text)' }}>
                  {s.src_title}
                  <span style={{ color: 'var(--rel)' }}> ⇄ </span>
                  {s.dst_title}
                </div>
                <div className="mono mt-0.5 truncate text-[10px]" style={{ color: 'var(--muted)' }}>
                  {s.shared.join(' · ')}
                </div>
              </div>
              {s.same_title && (
                <Badge tone="warn">same title — check for duplicate</Badge>
              )}
              <span className="mono shrink-0 text-[10px] tabular-nums" style={{ color: 'var(--muted)' }}>
                {s.score.toFixed(1)}
              </span>
            </li>
          )
        })}
      </ul>

      <div className="mt-2 flex items-center gap-2">
        <button
          className="mono rounded border px-2 py-1 text-[11px]"
          style={{ borderColor: 'var(--rel)', color: 'var(--rel)' }}
          disabled={chosen.length === 0 || decide.isPending}
          onClick={() => apply('confirm')}
        >
          Confirm {chosen.length || ''}
        </button>
        <button
          className="mono rounded border px-2 py-1 text-[11px]"
          style={{ borderColor: 'var(--border)', color: 'var(--muted)' }}
          disabled={chosen.length === 0 || decide.isPending}
          onClick={() => apply('dismiss')}
        >
          Dismiss {chosen.length || ''}
        </button>
        <span className="mono text-[10px]" style={{ color: 'var(--muted)' }}>
          {chosen.length === 0 ? 'select pairs to act on them' : `${chosen.length} selected`}
        </span>
      </div>
    </Panel>
  )
}

export default function MaintenanceCenter() {
  const qc = useQueryClient()
  const { projectId } = useProject()

  const findings = useQuery({
    queryKey: ['findings', projectId],
    queryFn: () => api.findings(projectId!),
    enabled: !!projectId,
  })
  const proposals = useQuery({
    queryKey: ['proposals', projectId],
    queryFn: () => api.proposals(projectId!),
    enabled: !!projectId,
  })
  const analyze = useMutation({
    mutationFn: () => api.analyze(projectId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['findings', projectId] })
      qc.invalidateQueries({ queryKey: ['proposals', projectId] })
      qc.invalidateQueries({ queryKey: ['memories'] })
    },
  })

  if (!projectId) {
    return <NoProject />
  }

  const byKind = (findings.data ?? []).reduce<Record<string, Finding[]>>((acc, f) => {
    ;(acc[f.kind] ??= []).push(f)
    return acc
  }, {})
  const result = analyze.data

  return (
    <div className="space-y-4">
      <ScreenHeader
        title="Intelligence"
        right={
          <Button
            primary
            onClick={() => analyze.mutate()}
            disabled={analyze.isPending}
            className="shrink-0"
          >
            {analyze.isPending ? 'Analysing…' : 'Run analysis'}
          </Button>
        }
      >
        Every finding is a request for review, never a verdict. Nothing is merged or
        marked wrong without you.
      </ScreenHeader>

      {analyze.isError && <ErrorNote error={analyze.error} />}
      {findings.isError && <ErrorNote error={findings.error} />}

      {result && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          <Stat
            label="Stale risk"
            value={result.drift_high + result.drift_medium}
            hint={`${result.drift_high} high · ${result.drift_medium} formatting only`}
          />
          <Stat
            label="Contradictions"
            value={result.conflicts_procedure + result.conflicts_decision}
            hint="both claims kept"
          />
          <Stat label="Duplicates" value={result.duplicate_candidates} hint="proposed" />
          <Stat label="Refs checked" value={result.refs_checked} />
        </div>
      )}

      {(proposals.data ?? []).length > 0 && (
        <Panel title={`Consolidation proposals (${proposals.data!.length})`}>
          <div className="space-y-5">
            {proposals.data!.map((p) => (
              <ProposalPreview
                key={p.id}
                proposal={p}
                projectId={projectId}
                onDecided={() => {
                  qc.invalidateQueries({ queryKey: ['proposals', projectId] })
                  qc.invalidateQueries({ queryKey: ['findings', projectId] })
                  qc.invalidateQueries({ queryKey: ['memories'] })
                }}
              />
            ))}
          </div>
        </Panel>
      )}

      {Object.keys(byKind).length === 0 ? (
        <Panel title="Review queue">
          <Empty
            title="Nothing to review"
            hint="Run analysis to check source freshness, contradictions and duplicates."
          />
        </Panel>
      ) : (
        Object.entries(byKind).map(([kind, items]) => (
          <Panel
            key={kind}
            title={`${KIND_LABEL[kind as Finding['kind']] ?? kind} (${items.length})`}
          >
            <ul className="space-y-2.5">
              {items.map((f) => {
                const hunks = (f.evidence.overlapping_hunks as number[][]) ?? []
                const cited = f.evidence.cited_lines as number[] | undefined
                return (
                  <li key={f.id} className="space-y-1">
                    <div className="flex items-start gap-2">
                      <Badge tone={severityTone(f.severity)}>{f.severity}</Badge>
                      <span className="text-[12px]">{f.explanation}</span>
                    </div>
                    <div className="flex flex-wrap items-center gap-1.5 pl-1">
                      {f.evidence.rel_path ? (
                        <Citation>
                          {String(f.evidence.rel_path)}
                          {cited ? `:${cited[0]}-${cited[1]}` : ''}
                        </Citation>
                      ) : null}
                      {hunks.length > 0 && (
                        <span className="mono text-[11px]" style={{ color: 'var(--muted)' }}>
                          changed lines {hunks.map((h) => `${h[0]}-${h[1]}`).join(', ')}
                        </span>
                      )}
                      <span className="mono text-[11px]" style={{ color: 'var(--muted)' }}>
                        {f.detector}
                      </span>
                    </div>
                    <FindingActions
                      finding={f}
                      projectId={projectId}
                      onDecided={() => {
                        qc.invalidateQueries({ queryKey: ['findings', projectId] })
                        qc.invalidateQueries({ queryKey: ['memories'] })
                      }}
                    />
                  </li>
                )
              })}
            </ul>
          </Panel>
        ))
      )}

      {/* Below the queue on purpose: the nav badge counts findings, so arriving
          here has to show them, not 25 optional suggestions above them. */}
      {projectId && <SuggestedRelationships projectId={projectId} />}
      {projectId && <AppliedConsolidations projectId={projectId} />}
      {projectId && <ResolvedFindings projectId={projectId} />}
    </div>
  )
}
