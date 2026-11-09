import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useProject } from '../lib/useProject'
import { Badge, Citation, Empty, ErrorNote, Panel, Stat } from '../components/ui'

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
        <button
          onClick={() => save.mutate()}
          disabled={!dirty || save.isPending}
          className="rounded border px-2 py-0.5 text-[11px]"
          style={{ borderColor: 'var(--border)' }}
        >
          {save.isPending ? 'Saving…' : 'Save override'}
        </button>
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
      <header>
        <h1 className="text-lg font-semibold tracking-tight">Settings &amp; Evaluation</h1>
        <p className="text-[12px]" style={{ color: 'var(--muted)' }}>
          Measured retrieval quality against a labelled question set.
        </p>
      </header>

      <ScanConfigPanel />

      <Panel
        title="Retrieval evaluation"
        right={
          <button
            onClick={() => run.mutate()}
            disabled={run.isPending}
            className="rounded border px-2 py-0.5 text-[11px]"
            style={{ borderColor: 'var(--border)' }}
          >
            {run.isPending ? 'Running…' : 'Run evaluation'}
          </button>
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
