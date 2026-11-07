import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from './api'

const KEY = 'kernote.selectedProject'

function read(): string | null {
  // localStorage can throw in a private window or with site data blocked.
  try { return window.localStorage.getItem(KEY) } catch { return null }
}
function write(id: string | null) {
  try {
    if (id) window.localStorage.setItem(KEY, id)
    else window.localStorage.removeItem(KEY)
  } catch { /* a remembered selection is a convenience, not state we rely on */ }
}

/** The selected project. Remembered per browser; never authoritative. */
export function useProject() {
  const projects = useQuery({ queryKey: ['projects'], queryFn: api.listProjects })
  const [selected, setSelected] = useState<string | null>(read)

  useEffect(() => {
    if (!projects.data) return
    const stillExists = selected && projects.data.some((p) => p.id === selected)
    if (!stillExists) {
      const next = projects.data[0]?.id ?? null
      setSelected(next)
      write(next)
    }
  }, [projects.data, selected])

  return {
    projects,
    projectId: selected,
    select: (id: string | null) => { setSelected(id); write(id) },
  }
}
