import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { useQuery } from '@tanstack/react-query'
import api from '../api/client'
import {
  LayoutDashboard, Upload, BarChart3, Database,
  Settings, LogOut, Bell, AlertTriangle, Activity,
} from 'lucide-react'

const NAV = [
  { to: '/dashboard',    icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/requests/new', icon: Upload,           label: 'New Request' },
  { to: '/analytics',    icon: BarChart3,        label: 'Analytics' },
  { to: '/dumps',        icon: Database,         label: 'Dump Ingestion' },
  { to: '/settings',     icon: Settings,         label: 'Settings' },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const { data: summary } = useQuery({
    queryKey: ['dashboard-summary'],
    queryFn: () => api.get('/dashboard/summary').then(r => r.data),
    refetchInterval: 30000,
    staleTime: 20000,
  })

  const unread = summary?.unread_notifications ?? 0
  const unknowns = summary?.unknown_entries ?? 0

  return (
    <div className="flex h-screen overflow-hidden bg-gray-950">
      {/* ── Sidebar ──────────────────────────────────────────────────────── */}
      <aside className="w-60 bg-brand-900 flex flex-col shrink-0 border-r border-brand-800">
        {/* Logo */}
        <div className="px-5 py-5 border-b border-brand-800">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-sky-500 flex items-center justify-center">
              <Activity size={15} className="text-white" />
            </div>
            <div>
              <h1 className="text-sm font-bold text-white tracking-wide leading-none">ODD Automation</h1>
              <p className="text-[10px] text-brand-300 mt-0.5 leading-none">DRA Node Management</p>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-3 space-y-0.5">
          {NAV.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-brand-700/80 text-white shadow-sm'
                    : 'text-brand-200 hover:bg-brand-800 hover:text-white'
                }`
              }
            >
              <Icon size={17} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* User footer */}
        <div className="px-3 py-3 border-t border-brand-800">
          <div className="flex items-center gap-2.5 px-2">
            <div className="w-8 h-8 rounded-full bg-sky-600/30 border border-sky-600/40 flex items-center justify-center text-xs font-bold text-sky-300 uppercase">
              {user?.username?.[0]}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-white truncate">{user?.username}</p>
              <p className="text-[10px] text-brand-300 capitalize">{user?.role}</p>
            </div>
            <button
              onClick={() => { logout(); navigate('/login') }}
              className="p-1.5 rounded-lg hover:bg-brand-700 text-brand-300 hover:text-white transition-all"
              title="Logout"
            >
              <LogOut size={15} />
            </button>
          </div>
        </div>
      </aside>

      {/* ── Main ─────────────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Topbar */}
        <header className="bg-gray-900/80 border-b border-gray-800 px-6 py-3 flex items-center justify-between shrink-0 backdrop-blur">
          <div className="text-xs text-gray-500 font-mono">
            {new Date().toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata', weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' })}
            {' IST'}
          </div>
          <div className="flex items-center gap-3">
            {unknowns > 0 && (
              <button
                onClick={() => navigate('/dashboard')}
                className="flex items-center gap-1.5 text-amber-400 bg-amber-500/10 border border-amber-500/30 px-3 py-1 rounded-full text-xs font-medium hover:bg-amber-500/20 transition-all"
              >
                <AlertTriangle size={13} />
                {unknowns} unknown {unknowns === 1 ? 'entry' : 'entries'}
              </button>
            )}
            <button
              onClick={() => navigate('/dashboard')}
              className="relative p-2 rounded-lg hover:bg-gray-800 transition-all"
            >
              <Bell size={18} className="text-gray-400" />
              {unread > 0 && (
                <span className="absolute top-1 right-1 w-4 h-4 bg-red-500 rounded-full text-white text-[10px] flex items-center justify-center font-bold leading-none">
                  {unread > 9 ? '9+' : unread}
                </span>
              )}
            </button>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-6 bg-gray-950">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
