import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { App } from '@/app/App'
import { Toaster } from '@/components/ui/sonner'
import { TooltipProvider } from '@/components/ui/tooltip'
import { ApiError } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'
import { watchSystemTheme } from '@/lib/theme'

import './index.css'

const queryClient: QueryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 2,
    },
    mutations: {
      onError: (err) => {
        // An expired session anywhere sends the owner back to the login screen.
        if (err instanceof ApiError && err.status === 401)
          void queryClient.invalidateQueries({ queryKey: queryKeys.me })
      },
    },
  },
})

const root = document.getElementById('root')
if (!root) throw new Error('index.html is missing #root')

watchSystemTheme()

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <App />
        <Toaster position="bottom-right" />
      </TooltipProvider>
    </QueryClientProvider>
  </StrictMode>,
)
