// Thin fetch wrapper for the operator console. Session cookies are sent
// automatically; there is no token to attach (ADR-0004).

const BASE = '/api'

export async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { credentials: 'same-origin' })
  if (res.status === 401) {
    window.location.href = '/login'
    throw new Error('session expired')
  }
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export interface Order {
  id: string
  status: 'draft' | 'submitted' | 'picked' | 'shipped' | 'delivered' | 'cancelled'
  customerId: string
}
