import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { defaultModule } from './modules/registry'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import NewRequest from './pages/NewRequest'
import RequestsList from './pages/RequestsList'
import RequestDetail from './pages/RequestDetail'
import UnknownEntries from './pages/UnknownEntries'
import Analytics from './pages/Analytics'
import Settings from './pages/Settings'
import DumpsPage from './pages/DumpsPage'
import AdminPanel from './pages/AdminPanel'
import MasterOdd from './pages/MasterOdd'

const qc = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 30000 } } })

function PrivateRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="flex items-center justify-center h-screen text-gray-500">Loading…</div>
  return user ? children : <Navigate to="/login" replace />
}

export default function App() {
  const defaultNewRequest = `/requests/new/${defaultModule().id.toLowerCase()}`
  return (
    <QueryClientProvider client={qc}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/" element={<PrivateRoute><Layout /></PrivateRoute>}>
              <Route index element={<Navigate to="/dashboard" replace />} />
              <Route path="dashboard" element={<Dashboard />} />
              <Route path="requests" element={<RequestsList />} />
              {/* Module-slot: each registered module gets its own wizard URL */}
              <Route path="requests/new" element={<Navigate to={defaultNewRequest} replace />} />
              <Route path="requests/new/:moduleId" element={<NewRequest />} />
              <Route path="requests/:id" element={<RequestDetail />} />
              <Route path="unknown-entries" element={<UnknownEntries />} />
              <Route path="master-odd" element={<MasterOdd />} />
              <Route path="admin" element={<AdminPanel />} />
              <Route path="analytics" element={<Analytics />} />
              <Route path="dumps" element={<DumpsPage />} />
              <Route path="settings" element={<Settings />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}
