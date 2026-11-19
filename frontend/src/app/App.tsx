import { useState } from 'react'
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { useProject } from '../lib/useProject'
import Dashboard from '../screens/Dashboard'
import MemoryExplorer from '../screens/MemoryExplorer'
import ProjectIntelligence from '../screens/ProjectIntelligence'
import MaintenanceCenter from '../screens/MaintenanceCenter'
import ChangeImpact from '../screens/ChangeImpact'
import KnowledgeGraph from '../screens/KnowledgeGraph'
import AgentIntegrations from '../screens/AgentIntegrations'
import SettingsScreen from '../screens/Settings'
import { CaptureMemory } from '../components/CaptureMemory'
import { AddProject } from '../components/AddProject'
import { AddProjectContext } from '../lib/useAddProject'
import CommandPalette from '../components/CommandPalette'
import { useCommandPalette } from '../lib/useCommandPalette'
import { Button, Dot } from '../components/ui'

/** The mock's three groups, pointed only at screens that exist. */
const WORKBENCH = [
  { to: '/dashboard', label: 'Overview' },
  { to: '/explorer', label: 'Memory Ledger' },
  { to: '/graph', label: 'Knowledge Graph' },
  { to: '/maintenance', label: 'Intelligence', badge: 'findings' as const },
  { to: '/intelligence', label: 'Query Console' },
  { to: '/impact', label: 'Change Impact' },
]
const SYSTEM = [
  { to: '/agents', label: 'Agent Integrations' },
  { to: '/settings', label: 'Settings' },
]

const TITLE: Record<string, string> = {
  '/dashboard': 'overview',
  '/explorer': 'memory ledger',
  '/graph': 'knowledge graph',
  '/maintenance': 'intelligence',
  '/intelligence': 'query console',
  '/impact': 'change impact',
  '/agents': 'agents',
  '/settings': 'settings',
}

function NavGroup({ label }: { label: string }) {
  return (
    <div
      className="mono px-2.5 pt-4 pb-1.5 text-[10px] uppercase tracking-[0.16em]"
      style={{ color: 'var(--muted)' }}
    >
      {label}
    </div>
  )
}

function NavRow({ to, label, count }: {
  to: string; label: string; count?: number
}) {
  return (
    <NavLink
      to={to}
      className="flex items-center justify-between rounded px-2.5 py-1.5 text-[13px] mb-0.5"
      style={({ isActive }) => ({
        background: isActive ? 'var(--accent-soft)' : 'transparent',
        color: 'var(--text)',
        boxShadow: isActive ? 'inset 2px 0 0 var(--accent)' : undefined,
      })}
    >
      <span className="truncate">{label}</span>
      {count !== undefined && count > 0 ? (
        <span className="mono text-[11px] tabular-nums" style={{ color: 'var(--warn)' }}>{count}</span>
      ) : null}
    </NavLink>
  )
}

function ProjectRow({ id, name, selected, onSelect }: {
  id: string; name: string; selected: boolean; onSelect: () => void
}) {
  const detail = useQuery({ queryKey: ['project', id], queryFn: () => api.getProject(id) })
  return (
    <button
      onClick={onSelect}
      className="flex w-full items-center justify-between rounded px-2.5 py-1.5 text-[13px] mb-0.5 text-left"
      style={{
        background: selected ? 'var(--accent-soft)' : 'transparent',
        color: 'var(--text)',
        boxShadow: selected ? 'inset 2px 0 0 var(--accent)' : undefined,
      }}
    >
      <span className="mono truncate">{name}</span>
      <span className="mono text-[11px] tabular-nums" style={{ color: 'var(--muted)' }}>
        {detail.data?.counts.memories ?? ''}
      </span>
    </button>
  )
}

export default function App() {
  const health = useQuery({ queryKey: ['health'], queryFn: api.health, retry: false })
  const { projects, projectId, select } = useProject()
  const findings = useQuery({
    queryKey: ['findings', projectId],
    queryFn: () => api.findings(projectId!),
    enabled: !!projectId,
  })
  const location = useLocation()
  const navigate = useNavigate()
  const [capturing, setCapturing] = useState(false)
  const [adding, setAdding] = useState(false)
  const [query, setQuery] = useState('')
  const palette = useCommandPalette()

  const current = projects.data?.find((p) => p.id === projectId)
  const screen = TITLE[location.pathname] ?? ''

  return (
    <AddProjectContext.Provider value={() => setAdding(true)}>
    <div className="flex min-h-screen" style={{ background: 'var(--bg)' }}>
      {/* The sidebar is ~20 tab stops. Without this, every keyboard visit to
          a screen begins by traversing all of them. */}
      <a href="#main" className="skip-link">
        Skip to content
      </a>

      <aside
        className="hidden md:flex w-56 lg:w-60 shrink-0 flex-col border-r"
        style={{ borderColor: 'var(--border)', background: 'var(--panel)' }}
      >
        <div className="px-3.5 pt-4 pb-1">
          <div className="mono text-[17px] font-semibold tracking-tight">
            ker<span style={{ color: 'var(--accent)' }}>note</span>
            <span className="cursor" style={{ color: 'var(--accent)' }}>_</span>
          </div>
          <div className="mono text-[10px] mt-0.5" style={{ color: 'var(--muted)' }}>
            {health.data ? `schema v${health.data.schema_version} · local-first` : 'local-first'}
          </div>
        </div>

        <nav aria-label="Main" className="flex-1 overflow-y-auto px-2 pb-2">
          <NavGroup label="Workbench" />
          {WORKBENCH.map((n) => (
            <NavRow
              key={n.to} to={n.to} label={n.label}
              count={n.badge === 'findings' ? findings.data?.length : undefined}
            />
          ))}

          <NavGroup label="Projects" />
          {projects.isLoading && (
            <div className="px-2.5 py-1.5 text-[12px]" style={{ color: 'var(--muted)' }}>loading…</div>
          )}
          {projects.data?.length === 0 && (
            <div className="px-2.5 py-1.5 text-[12px]" style={{ color: 'var(--muted)' }}>none yet</div>
          )}
          {projects.data?.map((p) => (
            <ProjectRow
              key={p.id} id={p.id} name={p.name}
              selected={p.id === projectId} onSelect={() => select(p.id)}
            />
          ))}

          <button
            onClick={() => setAdding(true)}
            className="mono flex w-full items-center rounded px-2.5 py-1.5 text-[12px] mb-0.5 text-left"
            style={{ color: 'var(--accent)' }}
          >
            + Add project
          </button>

          <NavGroup label="System" />
          {SYSTEM.map((n) => <NavRow key={n.to} to={n.to} label={n.label} />)}
        </nav>

        <div
          className="mono px-3.5 py-2.5 text-[10px] border-t flex items-center gap-2"
          style={{ borderColor: 'var(--border)', color: 'var(--muted)' }}
        >
          {health.isError ? (
            <><Dot tone="stale" /><span style={{ color: 'var(--stale)' }}>backend unreachable</span></>
          ) : health.isLoading ? (
            <><Dot tone="muted" /> connecting…</>
          ) : (
            <><Dot tone="ok" /> offline · no outbound calls</>
          )}
        </div>
      </aside>

      <main id="main" className="grid-bg flex-1 min-w-0 flex flex-col">
        <header
          className="sticky top-0 z-10 flex items-center gap-3 border-b px-4 lg:px-6 py-2.5"
          style={{ borderColor: 'var(--border)', background: 'var(--panel)' }}
        >
          <div className="mono hidden sm:block text-[12px] min-w-0 truncate" style={{ color: 'var(--muted)' }}>
            workspace
            {current && <> / <span style={{ color: 'var(--text)' }}>{current.name}</span></>}
            {screen && <> / {screen}</>}
          </div>

          <form
            className="ml-auto min-w-0 flex-1 sm:max-w-md"
            onSubmit={(e) => {
              e.preventDefault()
              const q = query.trim()
              if (q) navigate(`/intelligence?q=${encodeURIComponent(q)}`)
            }}
          >
            <div className="relative">
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search memories, symbols, decisions…"
                aria-label="Search memories"
                className="mono w-full rounded border px-2.5 py-1.5 pr-12 text-[12px]"
                style={{ borderColor: 'var(--border)', background: 'var(--bg)', color: 'var(--text)' }}
              />
              {/* A hint for a key that works. The sidebar used to show ⌘1,
                  which nothing handled. */}
              <button
                type="button"
                onClick={() => palette.setOpen(true)}
                aria-label="Open the command palette"
                className="mono absolute right-1.5 top-1/2 -translate-y-1/2 rounded border px-1.5 py-0.5 text-[10px]"
                style={{ borderColor: 'var(--border)', color: 'var(--muted)' }}
              >
                ⌘K
              </button>
            </div>
          </form>

          <Button
            primary
            className="shrink-0"
            disabled={!projectId}
            onClick={() => setCapturing(true)}
          >
            + Capture Memory
          </Button>
        </header>

        <div className="flex-1 px-4 lg:px-6 py-4">
          <div className="mx-auto w-full max-w-[1500px]">
            <Routes>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/explorer" element={<MemoryExplorer />} />
              <Route path="/intelligence" element={<ProjectIntelligence />} />
              <Route path="/maintenance" element={<MaintenanceCenter />} />
              <Route path="/impact" element={<ChangeImpact />} />
              <Route path="/graph" element={<KnowledgeGraph />} />
              <Route path="/agents" element={<AgentIntegrations />} />
              <Route path="/settings" element={<SettingsScreen />} />
            </Routes>
          </div>
        </div>
      </main>

      {adding && (
        <AddProject
          onClose={() => setAdding(false)}
          onAdded={(id) => { select(id); navigate('/dashboard') }}
        />
      )}

      {capturing && projectId && (
        <CaptureMemory projectId={projectId} onClose={() => setCapturing(false)} />
      )}

      {palette.open && (
        <CommandPalette
          projectId={projectId}
          onClose={() => palette.setOpen(false)}
          onCapture={() => setCapturing(true)}
        />
      )}
    </div>
    </AddProjectContext.Provider>
  )
}
