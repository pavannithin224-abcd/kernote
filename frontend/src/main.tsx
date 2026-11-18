import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './app/App'
import Boot from './components/Boot'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, staleTime: 5_000 } },
})

// Read once, at load. The reveal is a one-shot that lasts about a second; a
// listener for changes mid-animation would be answering a question nobody is
// asking.
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      {/* Above the router on purpose: a route change cannot remount this, so
          the reveal runs on load and reload and never on navigation, with no
          flag to go stale. The app mounts underneath it and is painting
          behind the curtain the whole time. */}
      <Boot reducedMotion={reducedMotion} />
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
