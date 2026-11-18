import { useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import { Button, ErrorNote } from './ui'

const TYPES = [
  'project_fact', 'architecture', 'decision',
  'procedure', 'convention', 'gotcha', 'current_state',
] as const

/**
 * Assert a memory by hand.
 *
 * A captured memory has no file and line range to cite, so the API records its
 * provenance as a user note and its extraction method as `manual`. That
 * distinction is the point: a hand-written claim is evidence of what someone
 * said, not of what the repository contains, and the vault keeps the two
 * apart.
 */
export function CaptureMemory({ projectId, onClose }: { projectId: string; onClose: () => void }) {
  const qc = useQueryClient()
  const first = useRef<HTMLInputElement>(null)
  const [type, setType] = useState<string>('project_fact')
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')

  useEffect(() => {
    first.current?.focus()
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const save = useMutation({
    mutationFn: () => api.createMemory(projectId, { type, title: title.trim(), content: content.trim() }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['memories', projectId] })
      qc.invalidateQueries({ queryKey: ['project', projectId] })
      onClose()
    },
  })

  const field = {
    borderColor: 'var(--border)', background: 'var(--bg)', color: 'var(--text)',
  } as const

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center p-4 sm:p-8 overflow-auto"
      style={{ background: 'color-mix(in srgb, var(--bg) 78%, transparent)' }}
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        role="dialog" aria-modal="true" aria-label="Capture memory"
        className="w-full max-w-lg rounded-md border mt-8"
        style={{ borderColor: 'var(--border)', background: 'var(--panel)' }}
      >
        <form
          className="p-4 space-y-3"
          onSubmit={(e) => { e.preventDefault(); save.mutate() }}
        >
          <div className="mono text-[11px] uppercase tracking-[0.14em]">Capture memory</div>

          <label className="block text-[12px]">
            Type
            <select
              value={type} onChange={(e) => setType(e.target.value)}
              className="mono mt-1 w-full rounded-md border px-2 py-1.5 text-[12px]"
              style={field}
            >
              {TYPES.map((t) => <option key={t} value={t}>{t.replace('_', ' ')}</option>)}
            </select>
          </label>

          <label className="block text-[12px]">
            Title
            <input
              ref={first} value={title} onChange={(e) => setTitle(e.target.value)}
              required maxLength={200} placeholder="What is true?"
              className="mt-1 w-full rounded-md border px-2 py-1.5 text-[13px]"
              style={field}
            />
          </label>

          <label className="block text-[12px]">
            Content
            <textarea
              value={content} onChange={(e) => setContent(e.target.value)}
              required rows={5} placeholder="The claim, in full. This is stored as asserted by you, not extracted from a file."
              className="mt-1 w-full rounded-md border px-2 py-1.5 text-[13px]"
              style={field}
            />
          </label>

          <p className="text-[11px]" style={{ color: 'var(--muted)' }}>
            Recorded as a manual assertion with no source citation. It will be
            marked as such wherever it is used as evidence.
          </p>

          {save.isError && <ErrorNote error={save.error} />}

          <div className="flex items-center justify-end gap-2 pt-1">
            <Button type="button" onClick={onClose}>Cancel</Button>
            <Button primary type="submit" disabled={save.isPending || !title.trim() || !content.trim()}>
              {save.isPending ? 'Saving…' : 'Capture'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
