import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Download, RefreshCw, ChevronDown, ChevronRight,
  CheckCircle2, Clock, XCircle, RotateCcw, AlertTriangle,
} from 'lucide-react'
import api from '../api/client'
import { downloadFile } from '../api/download'
import { useAuth } from '../contexts/AuthContext'

const DECISION_STYLES = {
  ADD:                'bg-green-500/15 text-green-300 border-green-500/30',
  DELETE:             'bg-red-500/15 text-red-300 border-red-500/30',
  DEPENDENCY_ADD:     'bg-blue-500/15 text-blue-300 border-blue-500/30',
  DEPENDENCY_DELETE:  'bg-orange-500/15 text-orange-300 border-orange-500/30',
  SUPERSEDE:          'bg-purple-500/15 text-purple-300 border-purple-500/30',
  SUPERSEDE_PENDING:  'bg-purple-500/10 text-purple-300/80 border-purple-500/20',
  SKIPPED:            'bg-gray-700/40 text-gray-400 border-gray-600',
}

const IMPL_STYLES = {
  'PENDING FOR RECONCILIATION': 'text-yellow-400',
  'IMPLEMENTED':               'text-green-400',
  'AWAITING_IMPLEMENTATION':           'text-red-400',
}

const STATUS_BADGE = {
  COMPLETED:  'bg-green-500/20 text-green-300',
  FAILED:     'bg-red-500/20 text-red-300',
  PROCESSING: 'bg-blue-500/20 text-blue-300 animate-pulse',
  QUEUED:     'bg-gray-700 text-gray-300',
  ROLLEDBACK: 'bg-orange-500/20 text-orange-300',
}

function Badge({ cls, children }) {
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-mono border ${cls}`}>
      {children}
    </span>
  )
}

export default function RequestDetail() {
  const { id } = useParams()
  const nav = useNavigate()
  const qc = useQueryClient()
  const { user } = useAuth()
  const [auditOpen, setAuditOpen] = useState(false)
  const [filterInst, setFilterInst] = useState('')
  const [filterDecision, setFilterDecision] = useState('')

  const { data: req, isLoading, refetch } = useQuery({
    queryKey: ['request', id],
    queryFn: () => api.get(`/requests/${id}`).then(r => r.data),
    refetchInterval: (d) => {
      const s = d?.status
      return s === 'PROCESSING' || s === 'QUEUED' ? 3000 : false
    },
  })

  const rollback = useMutation({
    mutationFn: () => api.post(`/requests/${id}/rollback`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['request', id] })
      refetch()
    },
  })

  if (isLoading) return (
    <div className="flex items-center justify-center h-48 text-gray-500 text-sm">Loading…</div>
  )
  if (!req) return <div className="text-red-400 text-sm">Request not found.</div>

  const statuses = req.instance_statuses ?? []
  const filtered = statuses.filter(s => {
    if (filterInst && !`${s.dra_type} ${s.instance_label}`.toLowerCase().includes(filterInst.toLowerCase())) return false
    if (filterDecision && s.decision !== filterDecision) return false
    return true
  })

  const uniqueInstances = [...new Set(statuses.map(s => s.instance_label))].sort()
  const uniqueDecisions = [...new Set(statuses.map(s => s.decision))]

  // Rollback = cancel entries still awaiting implementation on the DRA.
  // Admin-only action (backend enforces via require_admin as well).
  const canRollback = req.status !== 'ROLLEDBACK' && user?.role === 'admin'

  return (
    <div className="space-y-6 pb-10">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold text-white font-mono">{id.slice(0, 8)}…</h1>
            <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${STATUS_BADGE[req.status]}`}>
              {req.status}
            </span>
          </div>
          <p className="text-sm text-gray-400 mt-1">
            {req.uploaded_file_name}
            {req.azure_request_id && (
              <span className="ml-3 font-mono text-xs text-amber-300 bg-amber-500/10 border border-amber-500/30 px-2 py-0.5 rounded">
                Azure: {req.azure_request_id}
              </span>
            )}
          </p>
          <p className="text-xs text-gray-500 mt-0.5">
            Created {req.created_at ? new Date(req.created_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' }) : '—'}
            {req.completed_at && ` · Completed ${new Date(req.completed_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })}`}
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => refetch()} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-600 hover:bg-gray-700 text-gray-300 text-sm">
            <RefreshCw size={13} /> Refresh
          </button>
          <button
            onClick={() => downloadFile(`/exports/${id}/delta`, `delta_${id.slice(0, 8)}.xlsx`)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-sky-600/50 bg-sky-600/10 hover:bg-sky-600/20 text-sky-300 text-sm">
            <Download size={13} /> Delta Excel
          </button>
          {canRollback && (
            <button
              onClick={() => { if (confirm('Cancel all entries of this request that are still pending / awaiting implementation?')) rollback.mutate() }}
              disabled={rollback.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-orange-600/50 bg-orange-600/10 hover:bg-orange-600/20 text-orange-300 text-sm disabled:opacity-40"
            >
              <RotateCcw size={13} /> {rollback.isPending ? 'Rolling back…' : 'Rollback'}
            </button>
          )}
        </div>
      </div>

      {rollback.isError && (
        <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-2">
          {rollback.error?.response?.data?.detail ?? 'Rollback failed'}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: 'Total Rows', val: req.total_rows, color: 'text-gray-300' },
          { label: 'Processed', val: req.processed_rows, color: 'text-green-400' },
          { label: 'Skipped', val: req.skipped_rows, color: 'text-gray-400' },
          { label: 'Failed', val: req.failed_rows, color: 'text-red-400' },
        ].map(({ label, val, color }) => (
          <div key={label} className="bg-gray-800/50 border border-gray-700 rounded-xl p-4 text-center">
            <p className={`text-2xl font-bold font-mono ${color}`}>{val ?? 0}</p>
            <p className="text-xs text-gray-500 mt-0.5">{label}</p>
          </div>
        ))}
      </div>

      {/* Instance Statuses */}
      <section className="rounded-xl border border-gray-700 bg-gray-800/40 overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-700 flex items-center gap-3 flex-wrap">
          <span className="text-sm font-semibold text-gray-200">Entry Statuses</span>
          <span className="text-xs text-gray-500">{filtered.length}/{statuses.length}</span>
          <div className="ml-auto flex gap-2">
            <select
              value={filterInst}
              onChange={e => setFilterInst(e.target.value)}
              className="text-xs bg-gray-700 border border-gray-600 rounded px-2 py-1 text-gray-300 focus:outline-none"
            >
              <option value="">All Instances</option>
              {uniqueInstances.map(i => <option key={i} value={i}>{i}</option>)}
            </select>
            <select
              value={filterDecision}
              onChange={e => setFilterDecision(e.target.value)}
              className="text-xs bg-gray-700 border border-gray-600 rounded px-2 py-1 text-gray-300 focus:outline-none"
            >
              <option value="">All Decisions</option>
              {uniqueDecisions.map(d => <option key={d} value={d}>{d}</option>)}
            </select>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-700 text-gray-400">
                {['Instance', 'Type', 'Decision', 'Realm / Range', 'Final Rule', 'Impl Status', 'Note'].map(h => (
                  <th key={h} className="px-4 py-2.5 text-left font-medium whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((s, i) => (
                <tr key={i} className="border-b border-gray-700/50 hover:bg-gray-700/20 transition-colors">
                  <td className="px-4 py-2 font-mono text-sky-300">{s.dra_type} / {s.instance_label}</td>
                  <td className="px-4 py-2 text-gray-300">{s.entry_type}</td>
                  <td className="px-4 py-2">
                    <Badge cls={DECISION_STYLES[s.decision] ?? 'text-gray-400'}>
                      {s.decision}
                    </Badge>
                  </td>
                  <td className="px-4 py-2 font-mono text-gray-300 max-w-xs truncate">
                    {s.realm ?? (s.start_addr ? `${s.start_addr}–${s.end_addr}` : '—')}
                  </td>
                  <td className="px-4 py-2 font-mono text-gray-400 max-w-xs truncate">{s.final_prt_rule ?? '—'}</td>
                  <td className="px-4 py-2">
                    <span className={`font-mono ${IMPL_STYLES[s.impl_status] ?? 'text-gray-500'}`}>
                      {s.impl_status ?? 'N/A'}
                    </span>
                  </td>
                  {/* Note must never truncate — wrap long dependency notes/reasons */}
                  <td className="px-4 py-2 text-gray-500 max-w-md whitespace-normal break-words leading-relaxed">
                    {s.dependency_note ?? s.reason ?? ''}
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-6 text-center text-gray-500">No entries match filters.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Per-instance Master ODD downloads */}
      {req.selected_instances?.length > 0 && (
        <section className="rounded-xl border border-gray-700 bg-gray-800/40 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-700">
            <span className="text-sm font-semibold text-gray-200">Master ODD Downloads</span>
          </div>
          <div className="p-4 flex flex-wrap gap-2">
            {req.selected_instances.map(inst => (
              <button
                key={`${inst.dra_type}|${inst.instance_label}`}
                onClick={() => downloadFile(
                  `/exports/${id}/master?dra_type=${inst.dra_type}&instance_label=${inst.instance_label}`,
                  `ODD_master_${inst.dra_type}_${inst.instance_label}.xlsx`,
                )}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-600 bg-gray-700/30 hover:bg-gray-700 text-gray-300 text-xs font-mono"
              >
                <Download size={12} /> {inst.instance_label}
              </button>
            ))}
          </div>
        </section>
      )}

      {/* Audit Log */}
      <section className="rounded-xl border border-gray-700 bg-gray-800/40 overflow-hidden">
        <button
          onClick={() => setAuditOpen(o => !o)}
          className="w-full px-5 py-3 border-b border-gray-700 flex items-center gap-2 text-sm font-semibold text-gray-200 hover:bg-gray-700/30 transition-colors"
        >
          {auditOpen ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
          Audit Log
          <span className="ml-2 text-xs text-gray-500">{req.audit_logs?.length ?? 0} entries</span>
        </button>
        {auditOpen && (
          <div className="overflow-x-auto max-h-80 overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-gray-800">
                <tr className="border-b border-gray-700 text-gray-400">
                  {['Time (IST)', 'Level', 'Type', 'Instance', 'Message'].map(h => (
                    <th key={h} className="px-4 py-2 text-left font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(req.audit_logs ?? []).map((a) => (
                  <tr key={a.id} className="border-b border-gray-700/40 hover:bg-gray-700/20">
                    <td className="px-4 py-1.5 font-mono text-gray-500 whitespace-nowrap">
                      {a.created_at ? new Date(a.created_at).toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour12: false }) : '—'}
                    </td>
                    <td className={`px-4 py-1.5 font-mono font-bold ${
                      a.level === 'ERROR' ? 'text-red-400' :
                      a.level === 'WARNING' ? 'text-yellow-400' : 'text-gray-400'
                    }`}>{a.level}</td>
                    <td className="px-4 py-1.5 text-gray-500">{a.entry_type ?? '—'}</td>
                    <td className="px-4 py-1.5 font-mono text-sky-400">{a.instance_label ?? '—'}</td>
                    <td className="px-4 py-1.5 text-gray-300 max-w-lg">{a.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
