import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, Cell,
} from 'recharts'
import api from '../api/client'

const COLORS = ['#38bdf8', '#818cf8', '#34d399', '#fb923c', '#f472b6', '#a78bfa']

function Card({ title, children, className = '' }) {
  return (
    <div className={`rounded-xl border border-gray-700 bg-gray-800/40 overflow-hidden ${className}`}>
      <div className="px-5 py-3 border-b border-gray-700">
        <span className="text-sm font-semibold text-gray-200">{title}</span>
      </div>
      <div className="p-5">{children}</div>
    </div>
  )
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-xs">
      <p className="text-gray-400 mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }}>{p.name}: <strong>{p.value}</strong></p>
      ))}
    </div>
  )
}

export default function Analytics() {
  const [days, setDays] = useState(30)

  const { data, isLoading } = useQuery({
    queryKey: ['analytics', days],
    queryFn: () => api.get(`/dashboard/analytics?days=${days}`).then(r => r.data),
    staleTime: 300_000,
  })

  const timeData = data?.requests_over_time ?? []
  const implData = data?.avg_implementation_hours_by_site ?? []
  const pendingData = data?.pending_by_site ?? []
  const unknownData = data?.unknown_entries_by_instance ?? []

  return (
    <div className="space-y-6 pb-10">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Analytics</h1>
          <p className="text-sm text-gray-400 mt-1">Operational insights across all DRA nodes</p>
        </div>
        <div className="flex gap-2">
          {[7, 30, 90].map(d => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                days === d
                  ? 'bg-sky-600 border-sky-600 text-white'
                  : 'border-gray-600 text-gray-400 hover:border-gray-500'
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center h-48 text-gray-500 text-sm">Loading…</div>
      ) : (
        <div className="space-y-5">
          {/* Requests over time */}
          <Card title={`Requests Over Time — Last ${days} Days`}>
            {timeData.length === 0 ? (
              <p className="text-gray-500 text-sm text-center py-4">No data in this period.</p>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={timeData} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
                  <defs>
                    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#38bdf8" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="day" tick={{ fill: '#6b7280', fontSize: 10 }} tickLine={false} />
                  <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} tickLine={false} axisLine={false} />
                  <Tooltip content={<CustomTooltip />} />
                  <Area type="monotone" dataKey="count" stroke="#38bdf8" fill="url(#sky)" strokeWidth={2} name="Requests" />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </Card>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {/* Avg impl time by site */}
            <Card title="Avg Implementation Time by Site (hours)">
              {implData.length === 0 ? (
                <p className="text-gray-500 text-sm text-center py-4">No reconciled data yet.</p>
              ) : (
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={implData} layout="vertical" margin={{ left: 10, right: 16 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" horizontal={false} />
                    <XAxis type="number" tick={{ fill: '#6b7280', fontSize: 10 }} tickLine={false} axisLine={false} />
                    <YAxis type="category" dataKey="site" tick={{ fill: '#9ca3af', fontSize: 11, fontFamily: 'monospace' }} tickLine={false} width={40} />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="avg_hours" radius={[0, 4, 4, 0]} name="Avg Hours">
                      {implData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </Card>

            {/* Pending by site */}
            <Card title="Pending Implementation by Site">
              {pendingData.length === 0 ? (
                <p className="text-gray-500 text-sm text-center py-4">No pending entries.</p>
              ) : (
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={pendingData} layout="vertical" margin={{ left: 10, right: 16 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" horizontal={false} />
                    <XAxis type="number" tick={{ fill: '#6b7280', fontSize: 10 }} tickLine={false} axisLine={false} />
                    <YAxis type="category" dataKey="site" tick={{ fill: '#9ca3af', fontSize: 11, fontFamily: 'monospace' }} tickLine={false} width={40} />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="count" name="Pending" radius={[0, 4, 4, 0]}>
                      {pendingData.map((_, i) => <Cell key={i} fill="#fb923c" />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </Card>
          </div>

          {/* Unknown entries */}
          {unknownData.length > 0 && (
            <Card title="Unacknowledged Unknown Entries by Instance">
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-gray-700 text-gray-400">
                      {['DRA Type', 'Instance', 'Count'].map(h => (
                        <th key={h} className="px-4 py-2 text-left font-medium">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {unknownData.map((r, i) => (
                      <tr key={i} className="border-b border-gray-700/40 hover:bg-gray-700/20">
                        <td className="px-4 py-2 text-gray-300 font-mono">{r.dra_type}</td>
                        <td className="px-4 py-2 text-sky-300 font-mono">{r.instance_label}</td>
                        <td className="px-4 py-2 text-orange-400 font-bold font-mono">{r.count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}
