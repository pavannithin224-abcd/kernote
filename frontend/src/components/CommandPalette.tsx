/**
 * The command palette — ⌘K / Ctrl+K.
 *
 * **Every entry does something.** The sidebar used to render a `⌘1` hint
 * that nothing handled, which is the decorative-functionality problem the
 * product spends so much effort avoiding everywhere else; that hint is gone
 * and this replaces it with keys that work.
 *
 * `⌘K` rather than `⌘1`-`⌘9` on purpose: in a browser tab those switch
 * tabs, and stealing them would be hostile in the arrangement most people
 * run today. `⌘K` collides with nothing.
 *
 * Actions that change data are *not* performed here. Scan and Analyze are
 * long, and Capture needs a form, so the palette navigates to the screen
 * that owns the operation and lets the user start it there, with its own
 * confirmation and progress. A palette that silently kicks off a
 * minutes-long scan from a fuzzy match would be worse than no palette.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

export interface Command {
  id: string
  label: string
  hint?: string
  group: string
  run: () => void
}

/** Subsequence match: "kg" finds "Knowledge Graph". */
function matches(query: string, label: string): boolean {
  if (!query) return true
  const haystack = label.toLowerCase()
  const needle = query.toLowerCase()
  if (haystack.includes(needle)) return true
  let i = 0
  for (const ch of haystack) {
    if (ch === needle[i]) i += 1
    if (i === needle.length) return true
  }
  return false
}

export default function CommandPalette({
  onClose,
  onCapture,
  projectId,
}: {
  onClose: () => void
  onCapture: () => void
  projectId: string | null
}) {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLUListElement>(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const commands = useMemo<Command[]>(() => {
    const go = (to: string) => () => {
      navigate(to)
      onClose()
    }
    const list: Command[] = [
      { id: 'overview', label: 'Overview', group: 'Go to', run: go('/dashboard') },
      { id: 'ledger', label: 'Memory Ledger', group: 'Go to', run: go('/explorer') },
      { id: 'graph', label: 'Knowledge Graph', group: 'Go to', run: go('/graph') },
      { id: 'intel', label: 'Intelligence · review queue', group: 'Go to', run: go('/maintenance') },
      { id: 'ask', label: 'Query Console', group: 'Go to', run: go('/intelligence') },
      { id: 'impact', label: 'Change Impact', group: 'Go to', run: go('/impact') },
      { id: 'agents', label: 'Agent Integrations', group: 'Go to', run: go('/agents') },
      { id: 'settings', label: 'Settings · data & privacy', group: 'Go to', run: go('/settings') },
    ]
    if (projectId) {
      list.unshift({
        id: 'capture',
        label: 'Capture a memory',
        hint: 'manual note',
        group: 'Do',
        run: () => {
          onClose()
          onCapture()
        },
      })
    }
    // A free-text query is a real action: it runs on the Query Console.
    if (query.trim()) {
      list.unshift({
        id: 'search',
        label: `Ask: “${query.trim()}”`,
        hint: 'query console',
        group: 'Do',
        run: () => {
          navigate(`/intelligence?q=${encodeURIComponent(query.trim())}`)
          onClose()
        },
      })
    }
    return list
  }, [navigate, onClose, onCapture, projectId, query])

  const shown = useMemo(
    () => commands.filter((c) => c.id === 'search' || matches(query, c.label)),
    [commands, query],
  )

  useEffect(() => {
    setActive(0)
  }, [query])

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.preventDefault()
      onClose()
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive((i) => Math.min(i + 1, shown.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      shown[active]?.run()
    }
  }

  useEffect(() => {
    const el = listRef.current?.querySelector<HTMLElement>('[data-active="true"]')
    el?.scrollIntoView({ block: 'nearest' })
  }, [active])

  let lastGroup = ''

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center px-4 pt-[12vh]"
      style={{ background: 'color-mix(in srgb, var(--bg) 72%, transparent)' }}
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        className="w-full max-w-lg overflow-hidden rounded border"
        style={{ background: 'var(--panel)', borderColor: 'var(--border)' }}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={onKeyDown}
      >
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Go to a screen, or ask a question…"
          aria-label="Command or question"
          aria-controls="palette-list"
          aria-activedescendant={shown[active] ? `cmd-${shown[active].id}` : undefined}
          className="mono w-full border-b bg-transparent px-3.5 py-3 text-[13px] outline-none"
          style={{ borderColor: 'var(--border)', color: 'var(--text)' }}
        />

        <ul id="palette-list" ref={listRef} role="listbox" className="max-h-[46vh] overflow-y-auto py-1">
          {shown.length === 0 && (
            <li className="mono px-3.5 py-3 text-[12px]" style={{ color: 'var(--muted)' }}>
              Nothing matches. Press Escape to close.
            </li>
          )}
          {shown.map((c, i) => {
            const header = c.group !== lastGroup ? c.group : null
            lastGroup = c.group
            const isActive = i === active
            return (
              <li key={c.id}>
                {header && (
                  <div
                    className="mono px-3.5 pt-2 pb-1 text-[10px] uppercase tracking-[0.14em]"
                    style={{ color: 'var(--muted)' }}
                  >
                    {header}
                  </div>
                )}
                <button
                  id={`cmd-${c.id}`}
                  role="option"
                  aria-selected={isActive}
                  data-active={isActive}
                  onMouseEnter={() => setActive(i)}
                  onClick={c.run}
                  className="flex w-full items-baseline justify-between px-3.5 py-1.5 text-left text-[13px]"
                  style={{
                    background: isActive ? 'var(--accent-soft)' : 'transparent',
                    color: 'var(--text)',
                    boxShadow: isActive ? 'inset 2px 0 0 var(--accent)' : undefined,
                  }}
                >
                  <span className="truncate">{c.label}</span>
                  {c.hint && (
                    <span className="mono shrink-0 text-[10px]" style={{ color: 'var(--muted)' }}>
                      {c.hint}
                    </span>
                  )}
                </button>
              </li>
            )
          })}
        </ul>

        <div
          className="mono flex gap-3 border-t px-3.5 py-1.5 text-[10px]"
          style={{ borderColor: 'var(--border)', color: 'var(--muted)' }}
        >
          <span>↑↓ move</span>
          <span>⏎ run</span>
          <span>esc close</span>
        </div>
      </div>
    </div>
  )
}
