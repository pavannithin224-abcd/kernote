import { NotYet } from '../components/ui'

export default function ChangeImpact() {
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-lg font-semibold tracking-tight">Change Impact</h1>
      </header>
      <NotYet stage="Stage 6" what="Change Impact" gate="a commit range lists the memories it may have invalidated, each with its triggering hunk" />
    </div>
  )
}
