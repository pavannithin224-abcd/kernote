/**
 * ⌘K / Ctrl+K opens the command palette.
 *
 * Lives beside `useProject` rather than in the component file: exporting a
 * hook next to a component breaks React Fast Refresh, which eslint flags.
 *
 * Not ⌘1-⌘9 — in a browser tab those switch tabs, and stealing them would
 * be hostile in the arrangement most people run today.
 */
import { useEffect, useState } from 'react'

export function useCommandPalette() {
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setOpen((v) => !v)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return { open, setOpen }
}
