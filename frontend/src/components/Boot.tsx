/**
 * The startup reveal: a knowledge graph forming, resolving into the wordmark,
 * over status lines that are actually true.
 *
 * Three decisions from `design/STARTUP_ANIMATION_BRIEF.md`, settled here.
 *
 * **The status lines report what can be checked.** The brief asked for five
 * lines -- DATABASE, MEMORY ENGINE, RETRIEVAL INDEX, LOCAL SERVICES,
 * WORKSPACE READY -- and forbade showing OK before a service is ready. Three
 * of those five have nothing behind them: there is no memory-engine process
 * (it is library code in the same process), and "local services" *is* the API
 * that already answered. So the lines are the ones with a real signal, and a
 * line is free to say something other than OK. Semantic search being `off` is
 * a normal, correct state -- printing a green tick over it would be the exact
 * dishonesty the product exists to argue against.
 *
 * **It runs on load, never on navigation**, because this component sits above
 * the router in `main.tsx`. A route change cannot remount it, so no flag,
 * no sessionStorage, nothing to go stale. A full reload is a real reload and
 * shows it again, which is what the brief asked for.
 *
 * **The app mounts underneath it the whole time.** This is an overlay, not a
 * gate: the dashboard is loading and painting behind the curtain, so the
 * dismissal is a fade onto a screen that is already there rather than the
 * start of another wait.
 */
import { useEffect, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import { api } from '../lib/api'

/** Minimum time the curtain stays up when everything is instantly ready.
 *  Below about a second the reveal reads as a flicker; above two it is in the
 *  way. This is the only invented duration here -- every other timing is the
 *  animation's own, and nothing waits on a timer that could wait on a fact. */
const MIN_MS = 1250

/** How long a failure stays on screen before the curtain lifts anyway.
 *  A splash that never dismisses would hide the dashboard's own error states,
 *  which are the useful ones -- they name the failing call and offer a retry.
 *  So a failure is *shown*, not swallowed, and then handed over. */
const FAIL_MS = 2200

/** Deterministic. A seeded scatter would differ every boot for no gain, and
 *  the repo's taste runs to deterministic output. Twenty-two nodes and
 *  seventeen links: cheap enough to animate with transform and opacity only,
 *  which is the brief's node budget made concrete. */
const NODES: [number, number, 'n' | 'a' | 'r'][] = [
  [86, 40, 'n'], [150, 28, 'n'], [214, 46, 'a'], [262, 30, 'n'],
  [44, 78, 'a'], [112, 86, 'n'], [178, 72, 'r'], [240, 92, 'n'], [300, 70, 'a'],
  [28, 120, 'n'], [96, 132, 'r'], [160, 116, 'n'], [226, 138, 'a'], [292, 124, 'n'],
  [58, 166, 'n'], [124, 178, 'a'], [192, 162, 'n'], [258, 184, 'r'], [318, 170, 'n'],
  [90, 212, 'n'], [172, 220, 'n'], [248, 208, 'a'],
]

const LINKS: [number, number][] = [
  [0, 1], [1, 2], [2, 3], [0, 5], [1, 6], [4, 5], [5, 6], [6, 7], [7, 8],
  [4, 9], [5, 10], [6, 11], [7, 12], [9, 10], [10, 11], [11, 12], [12, 13],
]

const HUE = { n: 'var(--accent)', a: 'var(--ok)', r: 'var(--rel)' } as const

type Line = { key: string; label: string; state: 'pending' | 'ok' | 'off' | 'fail'; detail: string }

const PENDING: Line[] = [
  { key: 'db', label: 'DATABASE', state: 'pending', detail: '' },
  { key: 'sem', label: 'SEMANTIC INDEX', state: 'pending', detail: '' },
  { key: 'ws', label: 'WORKSPACE', state: 'pending', detail: '' },
]

const MARK = {
  ok: { text: '[ OK ]', tone: 'var(--ok)' },
  off: { text: '[ OFF ]', tone: 'var(--muted)' },
  fail: { text: '[FAIL]', tone: 'var(--stale)' },
  pending: { text: '[ .. ]', tone: 'var(--muted)' },
} as const

export default function Boot({ reducedMotion }: { reducedMotion: boolean }) {
  const [lines, setLines] = useState<Line[]>(PENDING)
  const [leaving, setLeaving] = useState(false)
  const [gone, setGone] = useState(false)
  const started = useRef(Date.now())

  useEffect(() => {
    let cancelled = false
    const set = (key: string, patch: Partial<Line>) =>
      !cancelled && setLines((prev) => prev.map((l) => (l.key === key ? { ...l, ...patch } : l)))

    ;(async () => {
      // Each line resolves when its own check returns. Nothing is staged on a
      // timer, so a slow or broken service genuinely holds its line at [ .. ].
      // Dismiss after the checks settle. A failure still dismisses, just
      // later, so the reason is readable before the app's own error UI takes
      // over.
      const dismiss = (failed: boolean) => {
        const waited = Date.now() - started.current
        const floor = failed ? FAIL_MS : reducedMotion ? 0 : MIN_MS
        window.setTimeout(
          () => {
            if (cancelled) return
            setLeaving(true)
            window.setTimeout(() => !cancelled && setGone(true), 320)
          },
          Math.max(0, floor - waited),
        )
      }

      try {
        const h = await api.health()
        // FTS5 is created by the migrations, so a health response that reports
        // a schema version is also proof the keyword index exists. It is
        // folded into this line rather than given its own, because a separate
        // line would imply a separate check that is not being made.
        set('db', { state: 'ok', detail: `schema v${h.schema_version} · fts5` })
      } catch {
        set('db', { state: 'fail', detail: 'not reachable' })
        set('sem', { state: 'fail', detail: 'unknown' })
        set('ws', { state: 'fail', detail: 'unknown' })
        dismiss(true)
        return
      }

      let projects: Awaited<ReturnType<typeof api.listProjects>> = []
      try {
        projects = await api.listProjects()
        set('ws', {
          state: projects.length ? 'ok' : 'off',
          detail: projects.length
            ? `${projects.length} project${projects.length === 1 ? '' : 's'}`
            : 'no projects yet',
        })
      } catch {
        set('ws', { state: 'fail', detail: 'unreadable' })
      }

      if (!projects.length) {
        set('sem', { state: 'off', detail: 'no project to index' })
      } else {
        try {
          const e = await api.embeddingStatus(projects[0].id)
          // `off` is not a failure. Semantic search is opt-in and being
          // switched off is the default, correct state.
          set(
            'sem',
            e.usable
              ? { state: 'ok', detail: `${e.model_id.split('/').pop()} · ${e.dim}d` }
              : { state: 'off', detail: 'opt-in, not enabled' },
          )
        } catch {
          set('sem', { state: 'fail', detail: 'unreadable' })
        }
      }

      dismiss(false)
    })()

    return () => {
      cancelled = true
    }
  }, [reducedMotion])

  if (gone) return null

  const failed = lines.some((l) => l.state === 'fail')
  const ready = !failed && lines.every((l) => l.state !== 'pending')

  return (
    <div
      className={`boot grid-bg${leaving ? ' boot-leaving' : ''}`}
      role="status"
      aria-live="polite"
      aria-label="Starting Kernote"
    >
      <div className="boot-stage">
        {!reducedMotion && (
          <svg
            className="boot-graph"
            viewBox="0 0 346 248"
            aria-hidden
            focusable="false"
          >
            {LINKS.map(([a, b], i) => (
              <line
                key={i}
                x1={NODES[a][0]} y1={NODES[a][1]}
                x2={NODES[b][0]} y2={NODES[b][1]}
                className="boot-link"
                pathLength={1}
                style={{ '--d': `${0.25 + i * 0.03}s` } as CSSProperties}
              />
            ))}
            {NODES.map(([x, y, kind], i) => (
              <circle
                key={i}
                cx={x} cy={y} r={kind === 'a' ? 2.6 : 2}
                className="boot-node"
                style={{ '--d': `${i * 0.028}s`, '--neon': HUE[kind] } as CSSProperties}
              />
            ))}
          </svg>
        )}

        <div className={reducedMotion ? 'boot-word' : 'boot-word boot-word-in'}>
          <span className="mono">ker</span>
          <span className="mono" style={{ color: 'var(--accent)' }}>note</span>
          <span className="mono cursor" style={{ color: 'var(--accent)' }}>_</span>
        </div>

        <ul className={reducedMotion ? 'boot-lines' : 'boot-lines boot-lines-in'}>
          {lines.map((l) => (
            <li key={l.key} className="mono boot-line">
              <span style={{ color: MARK[l.state].tone }}>{MARK[l.state].text}</span>{' '}
              <span style={{ color: 'var(--text)' }}>{l.label}</span>
              {l.detail && (
                <span style={{ color: 'var(--muted)' }}>{'  '}{l.detail}</span>
              )}
            </li>
          ))}
          <li className="mono boot-line" style={{ color: failed ? 'var(--stale)' : 'var(--muted)' }}>
            {failed
              ? 'STARTUP FAILED — the workspace could not be reached'
              : ready
                ? 'WORKSPACE READY'
                : 'CHECKING…'}
          </li>
        </ul>
      </div>
    </div>
  )
}
