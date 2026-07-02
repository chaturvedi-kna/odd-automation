import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Check, RefreshCw } from 'lucide-react'
import api from '../api/client'

export default function UnknownEntries() {
  const qc = useQueryClient()
  const [showAcked, setShowAcked] = useState(false)
  const [page, setPage] = useState(1)

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['unknown-entries', showAcked, page],
    queryFn: () =>
      api.get('/dashboard/unknown-entries', { params: { acknowledged: showAcked, page, page_size: 50 } })
        .then(r => r.data),
    refetchInterval: 30000,
  })

  const ack = useMutation({
    mutationFn: (id) => api.patch(`/dashboard/unknown-entries/${id}/acknowledge`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['unknown-entries'] })
      qc.invalidateQueries({ queryKey: ['dashboard-summary'] })
    },
  })

  const items = data?.items ?? []

  return (
    <div className="space-y-5 pb-10">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <AlertTriangle size={20} className="text-amber-400" />
            Unknown Entries
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            In-scope configuration found on DRA instances that was not requested through this system.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => { setShowAcked(v => !v); setPage(1) }}
            className={`text-xs px-3 py-2 rounded-lg border transition-all ${
              showAcked
                ? 'border-amber-500/50 bg-amber-500/10 text-amber-300'
                : 'border-gray-700 text-gray-400 hover:bg-gray-800'
            }`}
          >
            {showAcked ? 'Showing acknowledged' : 'Showing open'}
          </button>
          <button onClick={() => refetch()} className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-700 hover:bg-gray-800 text-gray-300 text-xs">
            <RefreshCw size={13} /> Refresh
          </button>
        </div>
      </div>

      <section className="rounded-xl border border-gray-700 bg-gray-800/40 overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-gray-700 text-gray-400">
              {['DRA Type', 'Instance', 'Entry Type', 'Identifier', 'First Seen (IST)', ''].map((h, i) => (
                <th key={i} className="px-4 py-2.5 text-left font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-500">Loading…</td></tr>}
            {!isLoading && items.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                {showAcked ? 'No acknowledged entries.' : 'No unknown entries — all clear.'}
              </td></tr>
            )}
            {items.map(e => (
              <tr key={e.id} className="border-b border-gray-700/40 hover:bg-gray-700/20">
                <td className="px-4 py-2.5 font-mono text-sky-300">{e.dra_type}</td>
                <td className="px-4 py-2.5 font-mono text-gray-300">{e.instance_label}</td>
                <td className="px-4 py-2.5">
                  <span className={`font-mono px-1.5 py-0.5 rounded ${
                    e.entry_type === 'PRR' ? 'bg-blue-500/15 text-blue-300' : 'bg-purple-500/15 text-purple-300'
                  }`}>{e.entry_type}</span>
                </td>
                <td className="px-4 py-2.5 font-mono text-gray-300 max-w-md truncate">{e.identifier}</td>
                <td className="px-4 py-2.5 text-gray-500 whitespace-nowrap">
                  {e.created_at ? new Date(e.created_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' }) : '—'}
                </td>
                <td className="px-4 py-2.5 text-right">
                  {!showAcked && (
                    <button
                      onClick={() => ack.mutate(e.id)}
                      disabled={ack.isPending}
                      className="flex items-center gap-1 px-2.5 py-1 rounded-lg border border-green-600/40 bg-green-600/10 hover:bg-green-600/20 text-green-300 disabled:opacity-40 ml-auto"
                    >
                      <Check size={12} /> Acknowledge
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  )
}
