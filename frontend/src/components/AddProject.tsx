import { useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, type Job } from '../lib/api'
import { nativeFolderPicker } from '../lib/useAddProject'
import { Button, ErrorNote } from './ui'

type Phase = 'idle' | 'registering' | 'scanning' | 'analyzing' | 'done'

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

/** The last path segment, which is what people would call the project. */
function folderName(path: string): string {
  const parts = path.trim().replace(/[\\/]+$/, '').split(/[\\/]/)
  return parts[parts.length - 1] ?? ''
}

/** The API's wording is for developers; the dialog's is for people. */
function friendly(error: unknown): Error {
  const message = error instanceof Error ? error.message : String(error)
  if (message.startsWith('already registered')) {
    return new Error('That folder is already a project. Pick it from the sidebar.')
  }
  if (message.startsWith('not a directory')) {
    return new Error('That path is not a folder on this machine. Check it and try again.')
  }
  return error instanceof Error ? error : new Error(message)
}

/** Poll a background job until it settles; a failed job throws its error. */
async function finish(job: Job): Promise<Job> {
  let current = job
  while (current.status === 'queued' || current.status === 'running') {
    await sleep(600)
    current = await api.job(current.id)
  }
  if (current.status === 'failed') throw new Error(current.error ?? `${current.kind} failed`)
  return current
}

const PHASE_TEXT: Record<Phase, string> = {
  idle: '',
  registering: 'Registering the folder…',
  scanning: 'Reading the project. Files are only read, never changed.',
  analyzing: 'Checking the new memories for drift, conflicts and duplicates…',
  done: 'Ready.',
}

/**
 * Add a local folder as a project and build its memory.
 *
 * Registering alone would leave the user on an empty screen, so this runs the
 * whole first-use path -- register, scan, analyze -- with the work done by the
 * background job runner and its real status shown, then lands on the project.
 * Scanning is read-only (the scanner refuses secrets, binaries and build
 * output), which the dialog says rather than leaving people to wonder.
 */
export function AddProject({
  onClose,
  onAdded,
}: {
  onClose: () => void
  onAdded: (projectId: string) => void
}) {
  const qc = useQueryClient()
  const pathRef = useRef<HTMLInputElement>(null)
  const picker = nativeFolderPicker()
  const [path, setPath] = useState('')
  const [name, setName] = useState('')
  const [nameEdited, setNameEdited] = useState(false)
  const [phase, setPhase] = useState<Phase>('idle')
  const [memories, setMemories] = useState<number | null>(null)
  const busy = phase !== 'idle' && phase !== 'done'

  useEffect(() => {
    pathRef.current?.focus()
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape' && !busy) onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose, busy])

  const choosePath = (value: string) => {
    setPath(value)
    if (!nameEdited) setName(folderName(value))
  }

  const browse = useMutation({
    mutationFn: async () => (picker ? picker() : null),
    onSuccess: (picked) => { if (picked) choosePath(picked) },
  })

  const add = useMutation({
    mutationFn: async () => {
      setPhase('registering')
      const project = await api.registerProject(name.trim() || folderName(path), path.trim())
      // From here the project exists, so a failure leaves a usable (if empty)
      // project rather than nothing: refresh the list either way.
      qc.invalidateQueries({ queryKey: ['projects'] })
      setPhase('scanning')
      const scan = await finish(await api.scanInBackground(project.id))
      setMemories(scan.result?.memories_created ?? 0)
      setPhase('analyzing')
      await finish(await api.analyzeInBackground(project.id))
      return project.id
    },
    onSuccess: (projectId) => {
      qc.invalidateQueries()
      setPhase('done')
      onAdded(projectId)
      setTimeout(onClose, 900)
    },
    onError: () => {
      setPhase('idle')
      qc.invalidateQueries({ queryKey: ['projects'] })
    },
  })

  const field = {
    borderColor: 'var(--border)', background: 'var(--bg)', color: 'var(--text)',
  } as const

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center p-4 sm:p-8 overflow-auto"
      style={{ background: 'color-mix(in srgb, var(--bg) 78%, transparent)' }}
      onMouseDown={(e) => { if (e.target === e.currentTarget && !busy) onClose() }}
    >
      <div
        role="dialog" aria-modal="true" aria-label="Add project"
        className="w-full max-w-lg rounded-md border mt-8"
        style={{ borderColor: 'var(--border)', background: 'var(--panel)' }}
      >
        <form
          className="p-4 space-y-3"
          onSubmit={(e) => { e.preventDefault(); if (!busy) add.mutate() }}
        >
          <div className="mono text-[11px] uppercase tracking-[0.14em]">Add project</div>

          <label className="block text-[12px]">
            Project folder
            <div className="mt-1 flex gap-2">
              <input
                ref={pathRef} value={path} onChange={(e) => choosePath(e.target.value)}
                required disabled={busy} spellCheck={false}
                placeholder={picker ? 'Choose a folder…' : 'C:\\Users\\you\\code\\my-project'}
                className="mono min-w-0 flex-1 rounded-md border px-2 py-1.5 text-[12px]"
                style={field}
              />
              {picker && (
                <Button type="button" disabled={busy || browse.isPending} onClick={() => browse.mutate()}>
                  Browse…
                </Button>
              )}
            </div>
          </label>

          <label className="block text-[12px]">
            Name
            <input
              value={name} disabled={busy} maxLength={120}
              onChange={(e) => { setName(e.target.value); setNameEdited(true) }}
              placeholder="Defaults to the folder name"
              className="mt-1 w-full rounded-md border px-2 py-1.5 text-[13px]"
              style={field}
            />
          </label>

          <p className="text-[11px]" style={{ color: 'var(--muted)' }}>
            Kernote reads documentation, source and configuration, honours
            <span className="mono"> .gitignore</span>, refuses secrets and binaries, and
            never writes into your repository. Everything stays on this machine.
          </p>

          {busy && (
            <div role="status" className="mono text-[12px]" style={{ color: 'var(--accent)' }}>
              {PHASE_TEXT[phase]}
            </div>
          )}
          {phase === 'done' && (
            <div role="status" className="mono text-[12px]" style={{ color: 'var(--ok)' }}>
              {memories} memories created. Opening the project…
            </div>
          )}
          {(add.isError || browse.isError) && <ErrorNote error={friendly(add.error ?? browse.error)} />}

          <div className="flex items-center justify-end gap-2 pt-1">
            <Button type="button" disabled={busy} onClick={onClose}>Cancel</Button>
            <Button primary type="submit" disabled={busy || phase === 'done' || !path.trim()}>
              {busy ? 'Working…' : 'Add and scan'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
