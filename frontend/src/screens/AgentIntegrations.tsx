import { NotYet } from '../components/ui'

export default function AgentIntegrations() {
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-lg font-semibold tracking-tight">Agent Integrations</h1>
      </header>
      <NotYet stage="Stage 7" what="Agent Integrations" gate="a live coding-agent session pulls project context over MCP with no hand-written instruction file" />
    </div>
  )
}
