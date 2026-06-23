import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import api from '../api/client'
import { CheckCircle2, Clock, XCircle, AlertTriangle, Plus, RefreshCw } from 'lucide-react'

const STATUS_COLORS = {
  DONE: 'bg-green-100 text-green-700',
  DONE_PARTIAL: 'bg-yellow-100 text-yellow-700',
  FAILED: 'bg-red-100 text-red-700',
  PROCESSING: 'bg-blue-100 text-blue-700',
  QUEUED: 'bg-gray-100 text-gray-700',
}

function StatCard({ label, value, color, icon: Icon }) {
  return (
    <div className={`bg-white rounded-xl border border-gray-100 p-5 shadow-sm`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500 mb-1">{label}</p>
          <p className={`text-3xl font-bold ${color}`}>{value ?? '—'}</p>
        </div>
        <div className={`p-3 rounded-xl ${color.replace('text-', 'bg-').replace('-600', '-100').replace('-700', '-100')}`}>
          <Icon size={24} className={color} />
        </div>
      </div>
    </div>
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
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900">Dashboard</h2>
          <p className="text-sm text-gray-500">System overview and recent activity</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => refetch()} className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 px-3 py-2 rounded-lg border border-gray-200 hover:bg-gray-50">
            <RefreshCw size={16} /> Refresh
          </button>
          <button
            onClick={() => navigate('/requests/new')}
            className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
          >
            <Plus size={16} /> New Request
          </button>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total Requests" value={data?.total_requests} color="text-brand-600" icon={CheckCircle2} />
        <StatCard label="Pending Implementation" value={data?.pending_implementation} color="text-yellow-600" icon={Clock} />
        <StatCard label="Not Implemented" value={data?.AWAITING_IMPLEMENTATION} color="text-red-600" icon={XCircle} />
        <StatCard label="Unknown Entries" value={data?.unknown_entries} color="text-amber-600" icon={AlertTriangle} />
      </div>

      {/* Status breakdown */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {Object.entries(sc).map(([s, v]) => (
          <div key={s} className="bg-white rounded-lg border border-gray-100 p-3 text-center shadow-sm">
            <p className={`inline-block px-2 py-0.5 rounded text-xs font-semibold mb-1 ${STATUS_COLORS[s] || 'bg-gray-100 text-gray-600'}`}>{s}</p>
            <p className="text-2xl font-bold text-gray-800">{v}</p>
          </div>
        ))}
      </div>

      {/* Recent requests */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <h3 className="font-semibold text-gray-800">Recent Requests</h3>
        </div>
        <div className="divide-y divide-gray-50">
          {isLoading && (
            <div className="py-10 text-center text-gray-400 text-sm">Loading…</div>
          )}
          {!isLoading && (!data?.recent_requests?.length) && (
            <div className="py-10 text-center text-gray-400 text-sm">No requests yet. <button className="text-brand-600 underline" onClick={() => navigate('/requests/new')}>Create one</button></div>
          )}
          {data?.recent_requests?.map(r => (
            <div
              key={r.id}
              onClick={() => navigate(`/requests/${r.id}`)}
              className="flex items-center gap-4 px-5 py-3 hover:bg-gray-50 cursor-pointer transition-colors"
            >
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${STATUS_COLORS[r.status] || 'bg-gray-100'}`}>
                {r.status}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800 truncate">{r.uploaded_file_name || r.id}</p>
                <p className="text-xs text-gray-400">{r.created_at ? new Date(r.created_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' }) : ''} IST</p>
              </div>
              <div className="text-xs text-gray-500 text-right">
                <p>{r.processed_rows ?? 0} / {r.total_rows ?? 0} rows</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
