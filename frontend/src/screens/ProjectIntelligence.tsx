import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, type AnswerBundle } from '../lib/api'
import { useProject } from '../lib/useProject'
import { Badge, Button, Citation, Empty, ErrorNote, Panel, ScreenHeader, NoProject } from '../components/ui'

const OUTCOME: Record<AnswerBundle['outcome'], { label: string; tone: 'ok' | 'warn' | 'neutral' }> = {
  evidence_found: { label: 'Evidence found', tone: 'ok' },
  weak_evidence: { label: 'No direct evidence', tone: 'warn' },
  not_found: { label: 'Evidence not found', tone: 'warn' },
}

export default function ProjectIntelligence() {
  const qc = useQueryClient()
  const { projectId } = useProject()
  const [params, setParams] = useSearchParams()
  const [question, setQuestion] = useState(() => params.get('q') ?? '')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [history, setHistory] = useState<AnswerBundle[]>([])

  const embeddings = useQuery({
    queryKey: ['embeddings', projectId],
    queryFn: () => api.embeddingStatus(projectId!),
    enabled: !!projectId,
  })

  // The header's search box navigates here with ?q=. Run it once on arrival
  // and clear the parameter, so a refresh does not silently re-ask and the URL
  // stops claiming a question that has already been answered.
  const askedFor = useRef<string | null>(null)

  const ask = useMutation({
    mutationFn: (q: string) => api.ask(projectId!, q, sessionId),
    onSuccess: (bundle) => {
      setSessionId(bundle.session_id)
      setHistory((prev) => [bundle, ...prev])
      setQuestion('')
    },
  })

  useEffect(() => {
    const q = params.get('q')?.trim()
    if (!q || !projectId || askedFor.current === q) return
    askedFor.current = q
    setQuestion(q)
    ask.mutate(q)
    params.delete('q')
    setParams(params, { replace: true })
  }, [params, projectId, ask, setParams])

  const build = useMutation({
    mutationFn: (allowDownload: boolean) => api.buildEmbeddings(projectId!, allowDownload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['embeddings', projectId] }),
  })

  if (!projectId) {
    return <NoProject />
  }

  const emb = embeddings.data

  return (
    <div className="space-y-4">
      <ScreenHeader title="Query Console">
        Kernote returns the evidence that bears on a question, with citations. It does
        not write an answer — there is no language model in the loop.
      </ScreenHeader>

      {/* Semantic search is opt-in: the weights are a one-time download. */}
      {emb && !emb.usable && (
        <Panel title="Semantic search is off">
          <p className="text-[12px]">
            Search is keyword-only right now, which is a working mode, not a broken one.
            Adding meaning-based recall needs a one-time{' '}
            <strong>{emb.download_mb} MB</strong> model download
            (<span className="mono">{emb.model_id}</span>) into{' '}
            <span className="mono">{emb.cache_path}</span>. Model weights only — no
            telemetry, and nothing about your code leaves the machine.
          </p>
          <Button
            onClick={() => build.mutate(true)}
            disabled={build.isPending}
            className="mt-2"
          >
            {build.isPending ? 'Downloading and indexing…' : `Download ${emb.download_mb} MB and index`}
          </Button>
          {build.isError && <div className="mt-2"><ErrorNote error={build.error} /></div>}
        </Panel>
      )}

      {emb?.usable && (
        <div className="flex flex-wrap items-center gap-2 text-[12px]" style={{ color: 'var(--muted)' }}>
          <Badge tone="ok">semantic on</Badge>
          <span className="mono">{emb.model_id}</span>
          <span>{emb.indexed_memories} memories · {emb.indexed_chunks} chunks indexed</span>
          <button
            onClick={() => build.mutate(false)}
            disabled={build.isPending}
            className="underline disabled:opacity-50"
          >
            {build.isPending ? 'indexing…' : 'index new records'}
          </button>
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault()
          if (question.trim()) ask.mutate(question.trim())
        }}
        className="flex gap-2"
      >
        <input
          aria-label="Ask a question about this project"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Why did we choose SQLite? How do I run the tests?"
          className="flex-1 rounded-md border px-2.5 py-1.5 text-[13px]"
          style={{ borderColor: 'var(--border)', background: 'var(--panel)', color: 'var(--text)' }}
        />
        <Button primary type="submit" disabled={ask.isPending || !question.trim()}>
          {ask.isPending ? 'Searching…' : 'Ask'}
        </Button>
      </form>

      {ask.isError && <ErrorNote error={ask.error} />}

      {history.length === 0 && !ask.isPending && (
        <Panel title="Nothing asked yet">
          <Empty
            title="Ask something about this project"
            hint="Every claim is labelled as quoted evidence or as an interpretation, and cited."
          />
        </Panel>
      )}

      {history.map((bundle, index) => (
        <Panel
          key={bundle.turn_id ?? index}
          title={bundle.question}
          right={<Badge tone={OUTCOME[bundle.outcome].tone}>{OUTCOME[bundle.outcome].label}</Badge>}
        >
          <p className="text-[13px] mb-3">{bundle.statement}</p>

          {bundle.evidence.length > 0 && (
            <ol className="space-y-2.5">
              {bundle.evidence.map((item) => (
                <li key={`${item.source}-${item.target_id}`} className="space-y-1">
                  <div className="flex flex-wrap items-center gap-1.5">
                    {/* When the outcome is weak, these rows are the search's closest
                        guesses, not answers. Stamping them "quoted from source" with a
                        confidence figure made an irrelevant record read as evidence,
                        which is the one thing this screen must never do. */}
                    {bundle.outcome === 'weak_evidence' ? (
                      <Badge tone="warn">lead · not an answer</Badge>
                    ) : (
                      <Badge tone={item.kind === 'evidence' ? 'ok' : 'warn'}>
                        {item.kind === 'evidence' ? 'quoted from source' : 'interpretation'}
                      </Badge>
                    )}
                    <Citation>{item.citation}</Citation>
                    {item.confidence !== null && bundle.outcome !== 'weak_evidence' && (
                      <span
                        className="mono text-[11px]"
                        style={{ color: 'var(--muted)' }}
                        title="How reliably this record was extracted from its source, not how well it answers the question"
                      >
                        extraction confidence {item.confidence.toFixed(2)}
                      </span>
                    )}
                  </div>
                  <div className="text-[13px] font-medium">{item.title}</div>
                  <pre
                    className="mono whitespace-pre-wrap text-[11px] max-h-28 overflow-auto"
                    style={{ color: 'var(--muted)' }}
                  >
                    {item.excerpt}
                  </pre>
                  <div className="text-[11px]" style={{ color: 'var(--muted)' }}>
                    matched {item.matched_terms.join(', ') || '—'} · {item.why_ranked}
                  </div>
                </li>
              ))}
            </ol>
          )}

          {bundle.related?.length > 0 && (
            <div className="mt-4 pt-3" style={{ borderTop: '1px solid var(--border)' }}>
              <div className="text-[12px] mb-1">
                <strong>Also retrieved, not verified ({bundle.related.length})</strong>
              </div>
              <p className="text-[12px] mb-2" style={{ color: 'var(--muted)' }}>
                These came back from the search but do not mention what you asked
                about, so Kernote will not offer them as evidence. They are shown
                because withholding them would hide the search's own best guesses.
              </p>
              <ul className="space-y-1">
                {bundle.related.map((item) => (
                  <li
                    key={`rel-${item.source}-${item.target_id}`}
                    className="flex flex-wrap items-center gap-1.5 text-[12px]"
                  >
                    <Citation>{item.citation}</Citation>
                    <span className="flex-1 min-w-0 truncate">{item.title}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {bundle.unknowns.length > 0 && (
            <div
              className="mt-3 rounded-md px-2.5 py-2 text-[12px]"
              style={{ background: 'var(--warn-soft)', color: 'var(--warn)' }}
            >
              <strong>Not supported by any source: </strong>
              {bundle.unknowns.join('; ')}
            </div>
          )}

          {bundle.note && (
            <p className="mt-2 text-[11px]" style={{ color: 'var(--muted)' }}>
              {bundle.note}
            </p>
          )}
        </Panel>
      ))}
    </div>
  )
}
