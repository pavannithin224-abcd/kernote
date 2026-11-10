import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import Dashboard from '../screens/Dashboard'
import MemoryExplorer from '../screens/MemoryExplorer'
import ProjectIntelligence from '../screens/ProjectIntelligence'
import MaintenanceCenter from '../screens/MaintenanceCenter'
import ChangeImpact from '../screens/ChangeImpact'
import AgentIntegrations from '../screens/AgentIntegrations'
import SettingsScreen from '../screens/Settings'
import { Mark } from '../components/Mark'

const NAV = [
  { to: '/dashboard', label: 'Dashboard', stage: 2 },
  { to: '/explorer', label: 'Memory Explorer', stage: 2 },
  { to: '/intelligence', label: 'Project Intelligence', stage: 2 },
  { to: '/maintenance', label: 'Memory Intelligence', stage: 2 },
  { to: '/impact', label: 'Change Impact', stage: 2 },
  { to: '/agents', label: 'Agent Integrations', stage: 2 },
  { to: '/settings', label: 'Settings & Evaluation', stage: 8 },
]

export default function App() {
  const health = useQuery({ queryKey: ['health'], queryFn: api.health, retry: false })

  return (
    <div className="flex min-h-screen">
      <aside
        className="hidden sm:flex w-60 shrink-0 flex-col border-r"
        style={{ borderColor: 'var(--border)', background: 'var(--panel)' }}
      >
        <div className="px-4 py-4">
          <div className="flex items-center gap-2">
            <Mark size={26} />
            <div className="text-[15px] font-semibold tracking-tight">Kernote</div>
          </div>
          <div className="text-[11px] mt-0.5" style={{ color: 'var(--muted)' }}>
            Reviewable project memory
          </div>
        </div>
        <nav className="flex-1 px-2">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              className="flex items-center justify-between rounded-md px-2.5 py-1.5 text-[13px] mb-0.5"
              style={({ isActive }) => ({
                background: isActive ? 'var(--accent-soft)' : 'transparent',
                color: isActive ? 'var(--accent)' : 'var(--text)',
                fontWeight: isActive ? 600 : 400,
              })}
            >
              <span>{n.label}</span>
              {n.stage > 2 && (
                <span className="text-[10px]" style={{ color: 'var(--muted)' }}>
                  S{n.stage}
                </span>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="px-4 py-3 text-[11px] border-t" style={{ borderColor: 'var(--border)', color: 'var(--muted)' }}>
          {health.isError ? (
            <span style={{ color: 'var(--warn)' }}>backend unreachable</span>
          ) : health.data ? (
            <>schema v{health.data.schema_version} · local only</>
          ) : (
            'connecting…'
          )}
        </div>
      </aside>

      <main className="flex-1 min-w-0 px-4 sm:px-6 py-5">
        <div className="mx-auto max-w-5xl">
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/explorer" element={<MemoryExplorer />} />
            <Route path="/intelligence" element={<ProjectIntelligence />} />
            <Route path="/maintenance" element={<MaintenanceCenter />} />
            <Route path="/impact" element={<ChangeImpact />} />
            <Route path="/agents" element={<AgentIntegrations />} />
            <Route path="/settings" element={<SettingsScreen />} />
          </Routes>
        </div>
      </main>
    </div>
  )
}
