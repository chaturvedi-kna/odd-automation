import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { RefreshCw, ChevronLeft, ChevronRight } from 'lucide-react'
import api from '../api/client'

const STATUS_BADGE = {
  COMPLETED:  'bg-green-500/20 text-green-300',
  FAILED:     'bg-red-500/20 text-red-300',
  PROCESSING: 'bg-blue-500/20 text-blue-300 animate-pulse',
  QUEUED:     'bg-gray-700 text-gray-300',
  ROLLEDBACK: 'bg-orange-500/20 text-orange-300',
}
const STATUSES = ['', 'QUEUED', 'PROCESSING', 'COMPLETED', 'FAILED', 'ROLLEDBACK']

export default function RequestsList() {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState('')
  const pageSize = 20

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['requests', page, status],
    queryFn: () =>
      api.get('/requests/', { params: { page, page_size: pageSize, status: status || undefined } })
        .then(r => r.data),
    refetchInterval: 15000,
  })

  const items = data?.items ?? []
  const total = data?.total ?? 0
  const pages = Math.max(1, Math.ceil(total / pageSize))

  return (
    <div className="space-y-5 pb-10">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Change Requests</h1>
          <p className="text-sm text-gray-400 mt-1">{total} total</p>
        </div>
        <div className="flex gap-2">
          <select
            value={status}
            onChange={e => { setStatus(e.target.value); setPage(1) }}
            className="text-xs bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-300 focus:outline-none"
          >
            {STATUSES.map(s => <option key={s} value={s}>{s || 'All statuses'}</option>)}
          </select>
          <button onClick={() => refetch()} className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-700 hover:bg-gray-800 text-gray-300 text-xs">
            <RefreshCw size={13} /> Refresh
          </button>
        </div>
      </div>

      <section className="rounded-xl border border-gray-700 bg-gray-800/40 overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-gray-700 text-gray-400">
              {['Request ID', 'Azure Req ID', 'Status', 'Module', 'File', 'Rows (ok/skip/fail)', 'Instances', 'Created (IST)', 'Completed (IST)'].map(h => (
                <th key={h} className="px-4 py-2.5 text-left font-medium whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={9} className="px-4 py-8 text-center text-gray-500">Loading…</td></tr>
            )}
            {!isLoading && items.length === 0 && (
              <tr><td colSpan={9} className="px-4 py-8 text-center text-gray-500">No requests found.</td></tr>
            )}
            {items.map(r => (
              <tr
                key={r.id}
                onClick={() => navigate(`/requests/${r.id}`)}
                className="border-b border-gray-700/40 hover:bg-gray-700/20 cursor-pointer transition-colors"
              >
                <td className="px-4 py-2.5 font-mono text-gray-300" title={r.id}>{r.id.slice(0, 8)}</td>
                <td className="px-4 py-2.5 font-mono text-amber-300">{r.azure_request_id ?? '—'}</td>
                <td className="px-4 py-2.5">
                  <span className={`px-2 py-0.5 rounded-full font-bold ${STATUS_BADGE[r.status] ?? 'bg-gray-700 text-gray-300'}`}>
                    {r.status}
                  </span>
                </td>
                <td className="px-4 py-2.5 font-mono text-sky-300">{r.module}</td>
                <td className="px-4 py-2.5 text-gray-300 max-w-xs truncate">{r.uploaded_file_name ?? r.id.slice(0, 8)}</td>
                <td className="px-4 py-2.5 font-mono text-gray-400">
                  <span className="text-green-400">{r.processed_rows}</span>/
                  <span className="text-gray-400">{r.skipped_rows}</span>/
                  <span className="text-red-400">{r.failed_rows}</span>
                  <span className="text-gray-600"> of {r.total_rows}</span>
                </td>
                <td className="px-4 py-2.5 text-gray-400">{r.selected_instances?.length ?? 0}</td>
                <td className="px-4 py-2.5 text-gray-500 whitespace-nowrap">
                  {r.created_at ? new Date(r.created_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' }) : '—'}
                </td>
                <td className="px-4 py-2.5 text-gray-500 whitespace-nowrap">
                  {r.completed_at ? new Date(r.completed_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' }) : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {/* Pagination */}
        <div className="px-4 py-2.5 border-t border-gray-700 flex items-center justify-between text-xs text-gray-400">
          <span>Page {page} / {pages}</span>
          <div className="flex gap-1">
            <button
              disabled={page <= 1}
              onClick={() => setPage(p => p - 1)}
              className="p-1.5 rounded hover:bg-gray-700 disabled:opacity-30"
            >
              <ChevronLeft size={14} />
            </button>
            <button
              disabled={page >= pages}
              onClick={() => setPage(p => p + 1)}
              className="p-1.5 rounded hover:bg-gray-700 disabled:opacity-30"
            >
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      </section>
    </div>
  )
}
