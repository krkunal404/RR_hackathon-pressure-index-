import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import Layout from '@/components/Layout'
import { Skeleton } from '@/components/ui/primitives'
import Overview from '@/pages/Overview'

const Rankings = lazy(() => import('@/pages/Rankings'))
const PlayerDetail = lazy(() => import('@/pages/PlayerDetail'))
const Explorer = lazy(() => import('@/pages/Explorer'))
const PressureLab = lazy(() => import('@/pages/PressureLab'))
const Competitions = lazy(() => import('@/pages/Competitions'))
const Methodology = lazy(() => import('@/pages/Methodology'))
const Validation = lazy(() => import('@/pages/Validation'))

export const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 5 * 60_000, refetchOnWindowFocus: false, retry: 1 } },
})

function Fallback() {
  return <div className="space-y-4"><Skeleton className="h-10 w-72" /><Skeleton className="h-64" /><Skeleton className="h-64" /></div>
}

export function AppRoutes() {
  return (
    <Suspense fallback={<Fallback />}>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Overview />} />
          <Route path="rankings/:role" element={<Rankings />} />
          <Route path="players/:role/:id" element={<PlayerDetail />} />
          <Route path="explorer" element={<Explorer />} />
          <Route path="pressure" element={<PressureLab />} />
          <Route path="competitions" element={<Competitions />} />
          <Route path="methodology" element={<Methodology />} />
          <Route path="validation" element={<Validation />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </Suspense>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </QueryClientProvider>
  )
}
