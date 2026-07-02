import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import api from '../api/client'
import { CheckCircle2, Clock, XCircle, AlertTriangle, Plus, RefreshCw } from 'lucide-react'
import { defaultModule } from '../modules/registry'

const STATUS_COLORS = {
  COMPLETED:  'bg-green-500/20 text-green-300',
  FAILED:     'bg-red-500/20 text-red-300',
  PROCESSING: 'bg-blue-500/20 text-blue-300',
  QUEUED:     'bg-gray-700 text-gray-300',
  ROLLEDBACK: 'bg-orange-500/20 text-orange-300',
}

function StatCard({ label, value, color, icon: Icon, onClick }) {
  return (
    <button
      onClick={onClick}
      className="bg-gray-800/50 rounded-xl border border-gray-700 p-5 text-left hover:border-gray-600 transition-all"
    >
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-400 mb-1">{label}</p>
          <p className={`text-3xl font-bold font-mono ${color}`}>{value ?? '—'}</p>
        </div>
        <Icon size={24} className={color} />
      </div>
    </button>
  )
}

export default function Dashboard() {
  const navigate = useNavigate()
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['dashboard-summary'],
    queryFn: () => api.get('/dashboard/summary').then(r => r.data),
    refetchInterval: 15000,
  })

  const sc = data?.status_counts || {}

  return (
    <div className="space-y-6 pb-10">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Dashboard</h1>
          <p className="text-sm text-gray-400 mt-1">System overview and recent activity</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => refetch()} className="flex items-center gap-2 text-sm text-gray-300 px-3 py-2 rounded-lg border border-gray-700 hover:bg-gray-800">
            <RefreshCw size={15} /> Refresh
          </button>
          <button
            onClick={() => navigate(`/requests/new/${defaultModule().id.toLowerCase()}`)}
            className="flex items-center gap-2 bg-sky-600 hover:bg-sky-500 text-white px-4 py-2 rounded-lg text-sm font-semibold"
          >
            <Plus size={16} /> New Request
          </button>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total Requests" value={data?.total_requests} color="text-sky-400" icon={CheckCircle2} onClick={() => navigate('/requests')} />
        <StatCard label="Pending Implementation" value={data?.pending_implementation} color="text-yellow-400" icon={Clock} onClick={() => navigate('/requests')} />
        <StatCard label="Awaiting Implementation" value={data?.AWAITING_IMPLEMENTATION} color="text-red-400" icon={XCircle} onClick={() => navigate('/requests')} />
        <StatCard label="Unknown Entries" value={data?.unknown_entries} color="text-amber-400" icon={AlertTriangle} onClick={() => navigate('/unknown-entries')} />
      </div>

      {/* Status breakdown */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {Object.entries(sc).map(([s, v]) => (
          <div key={s} className="bg-gray-800/50 rounded-lg border border-gray-700 p-3 text-center">
            <p className={`inline-block px-2 py-0.5 rounded text-xs font-semibold mb-1 ${STATUS_COLORS[s] || 'bg-gray-700 text-gray-300'}`}>{s}</p>
            <p className="text-2xl font-bold font-mono text-gray-200">{v}</p>
          </div>
        ))}
      </div>

      {/* Recent requests */}
      <section className="rounded-xl border border-gray-700 bg-gray-800/40 overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-700 flex items-center justify-between">
          <span className="text-sm font-semibold text-gray-200">Recent Requests</span>
          <button onClick={() => navigate('/requests')} className="text-xs text-sky-400 hover:text-sky-300">
            View all →
          </button>
        </div>
        <div className="divide-y divide-gray-700/40">
          {isLoading && <div className="py-10 text-center text-gray-500 text-sm">Loading…</div>}
          {!isLoading && !data?.recent_requests?.length && (
            <div className="py-10 text-center text-gray-500 text-sm">
              No requests yet.{' '}
              <button className="text-sky-400 underline" onClick={() => navigate(`/requests/new/${defaultModule().id.toLowerCase()}`)}>
                Create one
              </button>
            </div>
          )}
          {data?.recent_requests?.map(r => (
            <div
              key={r.id}
              onClick={() => navigate(`/requests/${r.id}`)}
              className="flex items-center gap-4 px-5 py-3 hover:bg-gray-700/20 cursor-pointer transition-colors"
            >
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${STATUS_COLORS[r.status] || 'bg-gray-700 text-gray-300'}`}>
                {r.status}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-200 truncate">{r.uploaded_file_name || r.id}</p>
                <p className="text-xs text-gray-500">
                  {r.created_at ? new Date(r.created_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' }) : ''} IST
                </p>
              </div>
              <div className="text-xs text-gray-500 text-right font-mono">
                {r.processed_rows ?? 0} / {r.total_rows ?? 0} rows
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
