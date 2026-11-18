import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useProject } from '../lib/useProject'
import { Badge, Button, Citation, Empty, ErrorNote, Panel, ScreenHeader, Stat } from '../components/ui'

function bytes(n: number | undefined): string {
  if (n === undefined) return '—'
  if (n < 1024) return `${n} B`
  const units = ['KB', 'MB', 'GB']
  let v = n / 1024
  let i = 0
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i += 1
  }
  return `${v < 10 ? v.toFixed(1) : Math.round(v)} ${units[i]}`
}

/**
 * Where the data is, and what leaves the machine.
 *
 * Every line here reports something the system already knows — the database
 * path and size come from `/health`, the embedding state from the project's
 * own status. Nothing is asserted that is not checked, which is why there
 * is no "encrypted" badge and no "0 trackers" counter.
 */
function DataAndPrivacyPanel() {
  const { projectId } = useProject()
  const qc = useQueryClient()
  const health = useQuery({ queryKey: ['health'], queryFn: api.health })
  const emb = useQuery({
    queryKey: ['embeddings', projectId],
    queryFn: () => api.embeddingStatus(projectId!),
    enabled: !!projectId,
  })

  const [restorePath, setRestorePath] = useState('')
  const [confirming, setConfirming] = useState(false)

  const backup = useMutation({ mutationFn: () => api.takeBackup() })
  const inspect = useMutation({ mutationFn: (p: string) => api.inspectBackup(p) })
  const restore = useMutation({
    mutationFn: (p: string) => api.restoreBackup(p),
    onSuccess: () => {
      setConfirming(false)
      qc.invalidateQueries()
    },
  })

  const Row = ({ label, children }: { label: string; children: React.ReactNode }) => (
    <div className="flex items-baseline justify-between gap-3 py-1.5">
      <span className="mono text-[11px]" style={{ color: 'var(--muted)' }}>{label}</span>
      <span className="mono min-w-0 truncate text-right text-[11px]">{children}</span>
    </div>
  )

  return (
    <Panel title="Data & privacy">
      {health.isError ? (
        <ErrorNote error={health.error} />
      ) : (
        <>
          <Row label="database">
            {health.isLoading ? '…' : health.data?.db_path}
          </Row>
          <Row label="size on disk">
            {health.isLoading ? '…' : `${bytes(health.data?.db_bytes)} · includes the write-ahead log`}
          </Row>
          <Row label="network">
            <span style={{ color: 'var(--ok)' }}>offline · no outbound calls</span>
          </Row>
          <Row label="semantic index">
            {!projectId ? (
              <span style={{ color: 'var(--muted)' }}>no project selected</span>
            ) : emb.isLoading ? (
              '…'
            ) : emb.data?.usable ? (
              `${emb.data.model_id.split('/').pop()} · ${emb.data.dim}d · local`
            ) : (
              <span style={{ color: 'var(--muted)' }}>
                off · enabling downloads ~{emb.data?.download_mb ?? 90} MB once
              </span>
            )}
          </Row>
        </>
      )}

      <div className="mt-3 border-t pt-3" style={{ borderColor: 'var(--border)' }}>
        <div
          className="mono mb-2 text-[10px] uppercase tracking-[0.14em]"
          style={{ color: 'var(--muted)' }}
        >
          Backup
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={() => backup.mutate()} disabled={backup.isPending}>
            {backup.isPending ? 'copying…' : 'Take a backup'}
          </Button>
          <a
            href="/api/v1/backup/download"
            className="mono rounded border px-2 py-1 text-[11px]"
            style={{ borderColor: 'var(--border)', color: 'var(--text)' }}
          >
            Download a copy
          </a>
          {projectId && (
            <a
              href={`/api/v1/projects/${projectId}/export`}
              className="mono rounded border px-2 py-1 text-[11px]"
              style={{ borderColor: 'var(--border)', color: 'var(--text)' }}
            >
              Export as JSON
            </a>
          )}
        </div>

        {backup.isError && <div className="mt-2"><ErrorNote error={backup.error} /></div>}
        {backup.data && (
          <p className="mono mt-2 text-[11px]" style={{ color: 'var(--ok)' }}>
            {bytes(backup.data.bytes)} written to {backup.data.path}
          </p>
        )}
      </div>

      <div className="mt-3 border-t pt-3" style={{ borderColor: 'var(--border)' }}>
        <div
          className="mono mb-2 text-[10px] uppercase tracking-[0.14em]"
          style={{ color: 'var(--muted)' }}
        >
          Restore
        </div>
        <p className="mb-2 text-[12px]" style={{ color: 'var(--muted)' }}>
          Replaces every memory in this vault. The current one is snapshotted first,
          and you will be told where it went.
        </p>

        <div className="flex flex-wrap items-center gap-2">
          <input
            value={restorePath}
            onChange={(e) => {
              setRestorePath(e.target.value)
              setConfirming(false)
            }}
            placeholder="/path/to/kernote-backup.db"
            aria-label="Path to a backup file"
            className="mono min-w-0 flex-1 rounded border px-2 py-1 text-[11px]"
            style={{ borderColor: 'var(--border)', background: 'var(--bg)', color: 'var(--text)' }}
          />
          <button
            className="mono rounded border px-2 py-1 text-[11px]"
            style={{ borderColor: 'var(--border)', color: 'var(--text)' }}
            disabled={!restorePath.trim() || inspect.isPending}
            onClick={() => {
              setConfirming(false)
              inspect.mutate(restorePath.trim())
            }}
          >
            {inspect.isPending ? 'checking…' : 'Check this file'}
          </button>
        </div>

        {inspect.isError && <div className="mt-2"><ErrorNote error={inspect.error} /></div>}

        {inspect.data && (
          <div className="mt-2">
            <p className="mono text-[11px]" style={{ color: 'var(--text)' }}>
              {inspect.data.memories} memories · {inspect.data.projects} project
              {inspect.data.projects === 1 ? '' : 's'} · schema v{inspect.data.schema_version}
            </p>
            {!confirming ? (
              <button
                className="mono mt-2 rounded border px-2 py-1 text-[11px]"
                style={{ borderColor: 'var(--stale)', color: 'var(--stale)' }}
                onClick={() => setConfirming(true)}
              >
                Restore from this file…
              </button>
            ) : (
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <span className="mono text-[11px]" style={{ color: 'var(--stale)' }}>
                  This replaces the current vault. Sure?
                </span>
                <button
                  className="mono rounded border px-2 py-1 text-[11px]"
                  style={{ borderColor: 'var(--stale)', color: 'var(--stale)' }}
                  disabled={restore.isPending}
                  onClick={() => restore.mutate(inspect.data!.path)}
                >
                  {restore.isPending ? 'restoring…' : 'Yes, replace it'}
                </button>
                <button
                  className="mono rounded border px-2 py-1 text-[11px]"
                  style={{ borderColor: 'var(--border)', color: 'var(--muted)' }}
                  onClick={() => setConfirming(false)}
                >
                  Cancel
                </button>
              </div>
            )}
          </div>
        )}

        {restore.isError && <div className="mt-2"><ErrorNote error={restore.error} /></div>}
        {restore.data && (
          <p className="mono mt-2 text-[11px]" style={{ color: 'var(--ok)' }}>
            Restored {restore.data.memories} memories. The previous vault is at{' '}
            {restore.data.safety_backup}
          </p>
        )}
      </div>
    </Panel>
  )
}

function ScanConfigPanel() {
  const { projectId } = useProject()
  const queryClient = useQueryClient()
  const [include, setInclude] = useState('')
  const [exclude, setExclude] = useState('')
  const [dirty, setDirty] = useState(false)

  const config = useQuery({
    queryKey: ['scan-config', projectId],
    queryFn: () => api.scanConfig(projectId!),
    enabled: !!projectId,
  })

  useEffect(() => {
    if (config.data && !dirty) {
      setInclude(config.data.override.include.join('\n'))
      setExclude(config.data.override.exclude.join('\n'))
    }
  }, [config.data, dirty])

  const save = useMutation({
    mutationFn: () =>
      api.saveScanConfig(
        projectId!,
        include.split('\n').map((s) => s.trim()).filter(Boolean),
        exclude.split('\n').map((s) => s.trim()).filter(Boolean),
      ),
    onSuccess: () => {
      setDirty(false)
      queryClient.invalidateQueries({ queryKey: ['scan-config', projectId] })
    },
  })

  if (!projectId) {
    return (
      <Panel title="Scan configuration">
        <Empty title="Select a project first" />
      </Panel>
    )
  }

  const eff = config.data?.effective

  return (
    <Panel
      title="Scan configuration"
      right={
        <Button primary onClick={() => save.mutate()} disabled={!dirty || save.isPending}>
          {save.isPending ? 'Saving…' : 'Save override'}
        </Button>
      }
    >
      <p className="text-[12px] mb-2">
        Which files Kernote reads. Commit{' '}
        <Citation>{config.data?.config_filename ?? '.kernote.toml'}</Citation> to your
        repository to declare this for everyone; the override below is local to this
        machine, like <code>.git/info/exclude</code>. Kernote never writes into your
        repository.
      </p>

      {config.error && <ErrorNote error={config.error} />}
      {save.error && <ErrorNote error={save.error} />}

      {eff && (
        <>
          <div className="grid gap-2 sm:grid-cols-2 mb-2">
            <div>
              <div className="text-[11px] mb-1" style={{ color: 'var(--muted)' }}>
                Effective include ({eff.include.length})
              </div>
              <ul className="space-y-0.5">
                {eff.include.length === 0 && (
                  <li className="text-[12px]" style={{ color: 'var(--muted)' }}>
                    none — the built-in allowlist only
                  </li>
                )}
                {eff.include.map((p) => (
                  <li key={`i-${p}`} className="mono text-[11px]">{p}</li>
                ))}
              </ul>
            </div>
            <div>
              <div className="text-[11px] mb-1" style={{ color: 'var(--muted)' }}>
                Effective exclude ({eff.exclude.length})
              </div>
              <ul className="space-y-0.5">
                {eff.exclude.length === 0 && (
                  <li className="text-[12px]" style={{ color: 'var(--muted)' }}>none</li>
                )}
                {eff.exclude.map((p) => (
                  <li key={`e-${p}`} className="mono text-[11px]">{p}</li>
                ))}
              </ul>
            </div>
          </div>
          <p className="text-[12px] mb-2">
            Sources:{' '}
            {eff.sources.length ? (
              eff.sources.map((s) => <Badge key={s}>{s}</Badge>)
            ) : (
              <span style={{ color: 'var(--muted)' }}>built-in defaults only</span>
            )}
          </p>
          {eff.notes.map((n) => (
            <p key={n} className="text-[12px]" style={{ color: 'var(--warn)' }}>{n}</p>
          ))}
        </>
      )}

      <div className="grid gap-2 sm:grid-cols-2 mt-2">
        <label className="text-[12px]">
          Local include patterns (one per line)
          <textarea
            value={include}
            onChange={(e) => { setInclude(e.target.value); setDirty(true) }}
            rows={4}
            spellCheck={false}
            className="mono mt-1 w-full rounded border px-2 py-1 text-[11px]"
            style={{ borderColor: 'var(--border)', background: 'var(--bg)', color: 'var(--text)' }}
          />
        </label>
        <label className="text-[12px]">
          Local exclude patterns (one per line)
          <textarea
            value={exclude}
            onChange={(e) => { setExclude(e.target.value); setDirty(true) }}
            rows={4}
            spellCheck={false}
            className="mono mt-1 w-full rounded border px-2 py-1 text-[11px]"
            style={{ borderColor: 'var(--border)', background: 'var(--bg)', color: 'var(--text)' }}
          />
        </label>
      </div>

      <ul className="mt-2 space-y-0.5">
        {(config.data?.rules ?? []).map((r) => (
          <li key={r} className="text-[12px]" style={{ color: 'var(--muted)' }}>· {r}</li>
        ))}
      </ul>
    </Panel>
  )
}

function pct(value: number | null | undefined) {
  return value === null || value === undefined ? 'n/a' : `${(value * 100).toFixed(1)}%`
}
function num(value: number | null | undefined) {
  return value === null || value === undefined ? 'n/a' : value.toFixed(3)
}

const VERDICT_TONE: Record<string, 'ok' | 'warn' | 'neutral'> = {
  answered: 'ok',
  correctly_declined: 'ok',
  lead_only: 'warn',
  missed: 'warn',
  wrongly_asserted: 'warn',
}

export default function Settings() {
  const [allowDownload, setAllowDownload] = useState(false)
  const set = useQuery({ queryKey: ['eval-set'], queryFn: api.evalQuestionSet })
  const run = useMutation({ mutationFn: () => api.runEvaluation(allowDownload) })
  const report = run.data

  return (
    <div className="space-y-4">
      <ScreenHeader title="Settings & Evaluation">
        Where your data lives, what it is indexed with, and measured retrieval
        quality against a labelled question set.
      </ScreenHeader>

      <DataAndPrivacyPanel />

      <ScanConfigPanel />

      <Panel
        title="Retrieval evaluation"
        right={
          <Button onClick={() => run.mutate()} disabled={run.isPending}>
            {run.isPending ? 'Running…' : 'Run evaluation'}
          </Button>
        }
      >
        <p className="text-[12px] mb-2">
          This scores <strong>Kernote&apos;s own retrieval</strong> against{' '}
          {set.data ? `${set.data.questions} labelled questions` : 'a labelled question set'}{' '}
          over the fixture corpus{' '}
          <Citation>{set.data?.corpus ?? 'samples/eval-repo'}</Citation>. It does not
          measure your project: your repository has no relevance labels, so nothing
          here can be scored against it. The run uses a throwaway database and
          never writes to your vault.
        </p>
        <label className="flex items-start gap-2 text-[12px] my-2">
          <input
            type="checkbox"
            checked={allowDownload}
            onChange={(e) => setAllowDownload(e.target.checked)}
            className="mt-0.5"
          />
          <span>
            Include semantic retrieval, downloading the embedding model if it is
            not already cached (~90&nbsp;MB from Hugging Face). Off by default:
            an evaluation must not reach the network without being asked. With
            it off and no cached model, the run measures the keyword-only path
            and the result says so.
          </span>
        </label>
        {set.data && (
          <p className="text-[12px]" style={{ color: 'var(--muted)' }}>
            {set.data.answerable} answerable, {set.data.unanswerable} unanswerable.
            The unanswerable ones are the point: a system that always answers
            cannot be trusted when it does.
          </p>
        )}
        {set.error && <ErrorNote error={set.error} />}
        {run.error && <ErrorNote error={run.error} />}
      </Panel>

      {report && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <Stat
              label="Citation correctness"
              value={pct(report.citation_correctness)}
              hint={`${pct(report.citation_correctness_strict)} cited a document that answers it`}
            />
            <Stat
              label="Useful abstention"
              value={pct(report.useful_abstention_rate)}
              hint="declined when nothing supported it"
            />
            <Stat
              label="False abstention"
              value={pct(report.false_abstention_rate)}
              hint="declined when the answer was there"
            />
            <Stat
              label="Retrieved vs asserted"
              value={`${pct(report.retrieval_success_rate)} / ${pct(report.answer_rate)}`}
              hint="found the right document / called it an answer"
            />
          </div>

          <Panel title="Ranking">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <Stat label="Recall@1" value={num(report.recall_at_k['1'])} />
              <Stat label="Recall@5" value={num(report.recall_at_k['5'])} />
              <Stat label="MRR" value={num(report.mrr)} />
              <Stat label="nDCG" value={num(report.ndcg_at_10)} />
            </div>
            <p className="text-[12px] mt-2" style={{ color: 'var(--muted)' }}>
              {report.memories_scanned} memories ·{' '}
              {report.semantic ? 'hybrid keyword + semantic' : 'keyword only'} ·{' '}
              retrieval depth {report.retrieval_depth} · {report.elapsed_seconds}s. No
              cut-off deeper than that depth is reported. Recall and MRR are averaged over the
              answerable questions only — scoring an unanswerable question zero
              would make honest abstention look like failed retrieval.
            </p>
          </Panel>

          <Panel title={`Per question (${report.results.length})`}>
            <ul className="space-y-1">
              {report.results.map((r) => (
                <li key={r.id} className="flex flex-wrap items-center gap-1.5 text-[12px]">
                  <Badge tone={VERDICT_TONE[r.verdict] ?? 'neutral'}>{r.verdict}</Badge>
                  <span className="mono" style={{ color: 'var(--muted)' }}>{r.id}</span>
                  <span className="flex-1 min-w-0 truncate">{r.question}</span>
                  {r.retrieved[0] && <Citation>{r.retrieved[0]}</Citation>}
                </li>
              ))}
            </ul>
          </Panel>
        </>
      )}

      {!report && !run.isPending && (
        <Empty
          title="No evaluation has been run in this session"
          hint="The result is measured each time rather than stored, so it always describes the code running now."
        />
      )}
    </div>
  )
}
