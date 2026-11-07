import { NotYet } from '../components/ui'

export default function Settings() {
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-lg font-semibold tracking-tight">Settings & Evaluation</h1>
      </header>
      <NotYet stage="Stage 8" what="Settings & Evaluation" gate="benchmarks recorded on the target machine and reported on the four MemoryAgentBench axes" />
    </div>
  )
}
