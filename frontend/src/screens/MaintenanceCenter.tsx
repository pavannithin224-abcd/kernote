import { NotYet } from '../components/ui'

export default function MaintenanceCenter() {
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-lg font-semibold tracking-tight">Memory Intelligence Center</h1>
      </header>
      <NotYet stage="Stage 6" what="Memory Intelligence Center" gate="a file edit produces a finding naming the overlapping diff hunk, and two contradicting sources produce one finding holding both claims" />
    </div>
  )
}
