import type { ButtonHTMLAttributes, CSSProperties, ReactNode } from 'react'
import { useAddProject } from '../lib/useAddProject'
import { Link } from 'react-router-dom'

export function Panel({ title, children, right }: {
  title?: string; children: ReactNode; right?: ReactNode
}) {
  // The heading is in the same terminal register as `PanelTitle`: mono,
  // small, upper case, tracked. This component is what the six pre-redesign
  // screens render through, so changing it here brings them into the
  // workbench language without restructuring any of them -- which is the
  // brief's own instruction, not to rewrite working screens for style.
  return (
    <section
      className="rounded border overflow-hidden"
      style={{ borderColor: 'var(--border)', background: 'var(--panel)' }}
    >
      {title && (
        <header
          className="flex items-center justify-between gap-3 px-3.5 py-2 border-b"
          style={{ borderColor: 'var(--border)' }}
        >
          <h2
            className="mono text-[11px] uppercase tracking-[0.14em]"
            style={{ color: 'var(--text)' }}
          >
            {title}
          </h2>
          {right}
        </header>
      )}
      <div className="p-3.5">{children}</div>
    </section>
  )
}

/**
 * The top of a screen: its name and one line saying what it is for.
 *
 * The six older screens each hand-rolled this as an 18px semibold sans
 * heading, which reads as a web page; the redesigned screens put their name
 * in the workbench register instead. One component so they agree, and so
 * the `<h1>` every screen needs lives in exactly one place.
 */
export function ScreenHeader({ title, children, right }: {
  title: string; children?: ReactNode; right?: ReactNode
}) {
  return (
    <header className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <h1
          className="mono text-[12px] uppercase tracking-[0.16em]"
          style={{ color: 'var(--text)' }}
        >
          {title}
        </h1>
        {children && (
          <p className="mt-1 max-w-3xl text-[12px]" style={{ color: 'var(--muted)' }}>
            {children}
          </p>
        )}
      </div>
      {right && <div className="shrink-0">{right}</div>}
    </header>
  )
}

export function Badge({ children, tone = 'neutral' }: {
  children: ReactNode; tone?: 'neutral' | 'info' | 'warn' | 'ok' | 'rel' | 'stale'
}) {
  // One hue, one meaning. `rel` is a relationship between records -- a
  // conflict or a duplicate -- and `stale` is a claim the code has moved out
  // from under. Neither is the accent, which marks the one action a screen is
  // for.
  // The three semantic tones are *outlined and lit* rather than filled, which
  // is how the reference mock distinguishes a record needing attention from a
  // label describing one. Filled chips at this size read as buttons; an
  // outline reads as a state. `neutral` and `info` stay flat on purpose --
  // they label things, they do not ask for anything.
  if (tone === 'warn' || tone === 'ok' || tone === 'rel' || tone === 'stale') {
    return (
      <span
        className="neon-outline mono inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-[0.1em] whitespace-nowrap"
        style={{ '--neon': `var(--${tone})` } as CSSProperties}
      >
        {children}
      </span>
    )
  }

  const map = {
    neutral: { bg: 'transparent', fg: 'var(--muted)', bd: 'var(--border)' },
    // `info` labels a category -- a memory's type, say. It used to be called
    // `accent` and used the accent colour, which made a label look like a
    // control. Reference material gets the neutral chip.
    info: { bg: 'var(--chip)', fg: 'var(--chip-text)', bd: 'transparent' },
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
      // `alert` announces without waiting for a pause, which is right: these
      // appear in response to something the user just did and they report
      // that it did not happen. Fixing it here covers every screen at once,
      // including the ones with no other aria markup.
      role="alert"
      className="rounded-md border px-3 py-2 text-[13px]"
      style={{ borderColor: 'var(--warn)', background: 'var(--warn-soft)', color: 'var(--warn)' }}
    >
      <strong className="font-semibold">Something failed. </strong>{msg}
    </div>
  )
}

/** The shared dead end for "no project yet", with the way out attached. */
export function NoProject() {
  const addProject = useAddProject()
  return (
    <Empty
      title="No project selected"
      hint="Add a local folder and Kernote builds its memory."
      action={<Button primary onClick={addProject}>+ Add project</Button>}
    />
  )
}

export function Empty({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="py-10 text-center">
      <p className="text-[13px] font-medium">{title}</p>
      {hint && <p className="mt-1 text-[12px]" style={{ color: 'var(--muted)' }}>{hint}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  )
}

/**
 * A number worth leading with.
 *
 * `to` makes the whole tile a link: a figure that tells you something needs
 * attention without saying where is half a feature. `tone="warn"` colours the
 * figure when it is a number you would rather were zero -- that is the warn
 * colour, which carries its own meaning, never the accent, which marks the one
 * action a screen is for.
 */
export function Stat({
  label,
  value,
  hint,
  to,
  tone = 'neutral',
}: {
  label: string
  value: ReactNode
  hint?: string
  to?: string
  tone?: 'neutral' | 'warn'
}) {
  const body = (
    <>
      <div className="text-[11px] uppercase tracking-wide" style={{ color: 'var(--muted)' }}>
        {label}
      </div>
      <div
        className="mt-0.5 text-xl font-semibold tabular-nums"
        style={tone === 'warn' ? { color: 'var(--warn)' } : undefined}
      >
        {value}
      </div>
      {hint && <div className="text-[11px]" style={{ color: 'var(--muted)' }}>{hint}</div>}
    </>
  )
  const className = 'block rounded-md border px-3 py-2.5'
  if (!to) {
    return (
      <div className={className} style={{ borderColor: 'var(--border)' }}>
        {body}
      </div>
    )
  }
  return (
    <Link
      to={to}
      className={className + ' transition-colors hover:border-current'}
      style={{ borderColor: 'var(--border)', color: 'inherit' }}
    >
      {body}
    </Link>
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


/** Inline emphasis in a metadata line: the value the finding is about. */
export function Neon({ tone, children }: {
  tone: 'ok' | 'warn' | 'rel' | 'stale' | 'accent'; children: ReactNode
}) {
  return (
    <span className="neon-text mono" style={{ '--neon': `var(--${tone})` } as CSSProperties}>
      {children}
    </span>
  )
}

/** A lit proportion bar. `pct` is 0-100; the track stays unlit. */
export function Bar({ pct, tone }: { pct: number; tone: 'ok' | 'warn' | 'rel' | 'stale' }) {
  return (
    <span
      aria-hidden
      className="inline-block h-[5px] w-[72px] shrink-0 overflow-hidden rounded-full align-middle"
      style={{ background: 'var(--chip)' }}
    >
      <span
        className="neon-bar block h-full rounded-full"
        style={{ width: `${Math.max(0, Math.min(100, pct))}%`, '--neon': `var(--${tone})` } as CSSProperties}
      />
    </span>
  )
}

/**
 * A status dot: the tone's colour, and the shared glow. Like every other
 * lit element it reads `--glow-blur` / `--glow-alpha` through `.neon-bar`,
 * so it lights up in the dark and goes flat in daylight.
 */
export function Dot({ tone = 'ok' }: { tone?: 'ok' | 'warn' | 'rel' | 'stale' | 'muted' }) {
  const colour = tone === 'muted' ? 'var(--muted)' : `var(--${tone})`
  return (
    <span
      aria-hidden
      className="neon-bar inline-block size-[6px] rounded-full align-middle"
      style={{ '--neon': colour } as CSSProperties}
    />
  )
}

/** A section heading in the terminal register: small, spaced, upper case. */
export function PanelTitle({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 mb-2.5">
      <h2 className="mono text-[11px] uppercase tracking-[0.14em]" style={{ color: 'var(--text)' }}>
        {children}
      </h2>
      {right && (
        <div className="mono text-[11px]" style={{ color: 'var(--muted)' }}>
          {right}
        </div>
      )}
    </div>
  )
}
