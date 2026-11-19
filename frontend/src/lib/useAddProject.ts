import { createContext, useContext } from 'react'

/**
 * Lets any screen open the "Add project" dialog, which lives at the app root.
 *
 * Several empty states tell a first-time user to register a project, so the
 * action has to be reachable from where they are standing rather than from a
 * screen they have to guess at. Kept in `lib/` with no JSX so Fast Refresh
 * keeps working on the components that consume it.
 */
export const AddProjectContext = createContext<() => void>(() => {})

export function useAddProject() {
  return useContext(AddProjectContext)
}

/** The native folder picker, present only inside the desktop window. */
export function nativeFolderPicker(): (() => Promise<string | null>) | null {
  const bridge = (window as unknown as {
    pywebview?: { api?: { pick_folder?: () => Promise<string | null> } }
  }).pywebview
  const pick = bridge?.api?.pick_folder
  return typeof pick === 'function' ? () => pick() : null
}
