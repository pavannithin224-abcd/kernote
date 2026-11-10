import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, type Finding } from '../lib/api'
import { useProject } from '../lib/useProject'
import { Badge, Button, Citation, Empty, ErrorNote, Panel, Stat } from '../components/ui'

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
    return <Empty title="No project selected" hint="Register one on the Dashboard first." />
  }

  const byKind = (findings.data ?? []).reduce<Record<string, Finding[]>>((acc, f) => {
    ;(acc[f.kind] ??= []).push(f)
    return acc
  }, {})
  const result = analyze.data

  return (
    <div className="space-y-4">
      <header className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Memory Intelligence</h1>
          <p className="text-[12px]" style={{ color: 'var(--muted)' }}>
            Every finding is a request for review, never a verdict. Nothing is merged or
            marked wrong without you.
          </p>
        </div>
        <Button
          primary
          onClick={() => analyze.mutate()}
          disabled={analyze.isPending}
          className="shrink-0"
        >
          {analyze.isPending ? 'Analysing…' : 'Run analysis'}
        </Button>
      </header>

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
    </div>
  )
}
