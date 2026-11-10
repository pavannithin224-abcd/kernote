import type { ButtonHTMLAttributes, ReactNode } from 'react'

export function Panel({ title, children, right }: {
  title?: string; children: ReactNode; right?: ReactNode
}) {
  return (
    <section
      className="rounded-lg border overflow-hidden"
      style={{ borderColor: 'var(--border)', background: 'var(--panel)' }}
    >
      {title && (
        <header
          className="flex items-center justify-between gap-3 px-4 py-2.5 border-b"
          style={{ borderColor: 'var(--border)' }}
        >
          <h2 className="text-[13px] font-semibold tracking-tight">{title}</h2>
          {right}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  )
}

export function Badge({ children, tone = 'neutral' }: {
  children: ReactNode; tone?: 'neutral' | 'info' | 'warn' | 'ok'
}) {
  const map = {
    neutral: { bg: 'transparent', fg: 'var(--muted)', bd: 'var(--border)' },
    // `info` labels a category -- a memory's type, say. It used to be called
    // `accent` and used the accent colour, which made a label look like a
    // control. Reference material gets the neutral chip.
    info: { bg: 'var(--chip)', fg: 'var(--chip-text)', bd: 'transparent' },
    warn: { bg: 'var(--warn-soft)', fg: 'var(--warn)', bd: 'transparent' },
    ok: { bg: 'var(--ok-soft)', fg: 'var(--ok)', bd: 'transparent' },
  }[tone]
  return (
    <span
      className="inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-medium border whitespace-nowrap"
      style={{ background: map.bg, color: map.fg, borderColor: map.bd }}
    >
      {children}
    </span>
  )
}

/**
 * A citation is a first-class UI element: evidence must always be visible.
 *
 * It wears the neutral chip, not the accent. A citation is something you read
 * and go and check, never something you press, and there are up to three of
 * them on a screen -- so painting them the action colour left nothing on the
 * page saying which control actually does something.
 */
export function Citation({ children }: { children: ReactNode }) {
  return (
    <span
      className="mono inline-flex items-center rounded px-1.5 py-0.5 text-[11px]"
      style={{ background: 'var(--chip)', color: 'var(--chip-text)' }}
    >
      {children}
    </span>
  )
}

/**
 * A button. `primary` is the one action a screen is for, and it is the only
 * thing on that screen allowed to carry `--accent`.
 *
 * The rule lives here rather than in a style guide because it was broken
 * everywhere when it was only a convention: the accent was the nav state, six
 * buttons, every citation, a panel border and a type badge at once. One
 * component makes the rule checkable -- grep for `--accent` and you should
 * find this file, and the active nav item, and nothing else.
 */
export function Button({
  children,
  primary,
  ...rest
}: { children: ReactNode; primary?: boolean } & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...rest}
      className={
        'rounded-md px-2.5 py-1 text-[12px] font-medium disabled:opacity-50 ' +
        (rest.className ?? '')
      }
      style={
        primary
          ? { background: 'var(--accent)', color: 'var(--accent-contrast)', border: '1px solid transparent' }
          : { background: 'transparent', color: 'var(--text)', border: '1px solid var(--border)' }
      }
    >
      {children}
    </button>
  )
}

export function ErrorNote({ error }: { error: unknown }) {
  const msg = error instanceof Error ? error.message : String(error)
  return (
    <div
      className="rounded-md border px-3 py-2 text-[13px]"
      style={{ borderColor: 'var(--warn)', background: 'var(--warn-soft)', color: 'var(--warn)' }}
    >
      <strong className="font-semibold">Something failed. </strong>{msg}
    </div>
  )
}

export function Empty({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="py-10 text-center">
      <p className="text-[13px] font-medium">{title}</p>
      {hint && <p className="mt-1 text-[12px]" style={{ color: 'var(--muted)' }}>{hint}</p>}
    </div>
  )
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="rounded-md border px-3 py-2.5" style={{ borderColor: 'var(--border)' }}>
      <div className="text-[11px] uppercase tracking-wide" style={{ color: 'var(--muted)' }}>
        {label}
      </div>
      <div className="mt-0.5 text-xl font-semibold tabular-nums">{value}</div>
      {hint && <div className="text-[11px]" style={{ color: 'var(--muted)' }}>{hint}</div>}
    </div>
  )
}

/** Stage placeholder. Says plainly what is not built yet rather than faking it. */
export function NotYet({ stage, what, gate }: { stage: string; what: string; gate: string }) {
  return (
    <Panel title={what}>
      <p className="text-[13px]">
        Not built yet — scheduled for <strong>{stage}</strong>.
      </p>
      <p className="mt-2 text-[12px]" style={{ color: 'var(--muted)' }}>
        This screen is intentionally empty rather than showing mock data. Its gate:{' '}
        {gate}
      </p>
    </Panel>
  )
}
