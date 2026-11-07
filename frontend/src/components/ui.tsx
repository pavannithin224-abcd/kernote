import type { ReactNode } from 'react'

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
  children: ReactNode; tone?: 'neutral' | 'accent' | 'warn' | 'ok'
}) {
  const map = {
    neutral: { bg: 'transparent', fg: 'var(--muted)', bd: 'var(--border)' },
    accent: { bg: 'var(--accent-soft)', fg: 'var(--accent)', bd: 'transparent' },
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

/** A citation is a first-class UI element: evidence must always be visible. */
export function Citation({ children }: { children: ReactNode }) {
  return (
    <span
      className="mono inline-flex items-center rounded px-1.5 py-0.5 text-[11px]"
      style={{ background: 'var(--accent-soft)', color: 'var(--accent)' }}
    >
      {children}
    </span>
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
