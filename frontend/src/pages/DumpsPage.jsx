import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Upload, RefreshCw, Database, CheckCircle2, AlertCircle, FileText } from 'lucide-react'
import api from '../api/client'
import { useQuery as useInstancesQuery } from '@tanstack/react-query'

function useInstances() {
  return useQuery({
    queryKey: ['instances'],
    queryFn: () => api.get('/instances/').then(r => r.data),
    staleTime: 3600_000,
  })
}

export default function DumpsPage() {
  const qc = useQueryClient()
  const fileRef = useRef(null)
  const [file, setFile] = useState(null)
  const [draType, setDraType] = useState('')
  const [instLabel, setInstLabel] = useState('')
  const [reconStatus, setReconStatus] = useState(null)

  const { data: instances = [] } = useInstances()
  const { data: snaps = [], refetch: refetchSnaps } = useQuery({
    queryKey: ['snapshots'],
    queryFn: () => api.get('/dumps/snapshots').then(r => r.data),
    staleTime: 30_000,
  })

  const ingest = useMutation({
    mutationFn: () => {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('dra_type', draType)
      fd.append('instance_label', instLabel)
      return api.post('/dumps/ingest', fd)
    },
    onSuccess: () => {
      setFile(null)
      setDraType('')
      setInstLabel('')
      refetchSnaps()
    },
  })

  const reconcile = useMutation({
    mutationFn: (payload) => api.post('/dumps/reconcile', null, { params: payload }),
    onSuccess: (r) => {
      setReconStatus(r.data)
      qc.invalidateQueries(['dashboard'])
    },
  })

  const scan = useMutation({
    mutationFn: () => api.post('/dumps/scan'),
    onSuccess: () => setTimeout(() => refetchSnaps(), 2000),
  })

  const draTypes = [...new Set(instances.map(i => i.dra_type))].sort()
  const labelsForType = instances.filter(i => i.dra_type === draType).map(i => i.instance_label).sort()

  return (
    <div className="space-y-6 pb-10">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Dump Management</h1>
          <p className="text-sm text-gray-400 mt-1">Ingest DRA system dumps for reconciliation.</p>
        </div>
        <button
          onClick={() => scan.mutate()}
          disabled={scan.isPending}
          title="Scan the configured dump source folder on the VM for new files"
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-sky-600/50 bg-sky-600/10 hover:bg-sky-600/20 text-sky-300 text-sm font-medium disabled:opacity-40 transition-all"
        >
          <RefreshCw size={14} className={scan.isPending ? 'animate-spin' : ''} />
          {scan.isPending ? 'Scanning…' : 'Scan Dump Source'}
        </button>
      </div>
      {scan.isSuccess && (
        <p className="text-xs text-green-400">✓ Dump source scan queued — new files will appear under snapshots.</p>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Upload form */}
        <section className="rounded-xl border border-gray-700 bg-gray-800/40 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-700 flex items-center gap-2">
            <Upload size={15} className="text-sky-400" />
            <span className="text-sm font-semibold text-gray-200">Ingest Dump File</span>
          </div>
          <div className="p-5 space-y-4">
            {/* File picker */}
            <div>
              <label className="text-xs text-gray-400 mb-1.5 block">Dump CSV File</label>
              <div
                onClick={() => fileRef.current?.click()}
                className="cursor-pointer border border-dashed border-gray-600 hover:border-gray-500 rounded-lg px-4 py-3 flex items-center gap-3 transition-all"
              >
                <input
                  ref={fileRef}
                  type="file"
                  accept=".csv"
                  className="hidden"
                  onChange={e => setFile(e.target.files[0])}
                />
                <FileText size={18} className="text-gray-500" />
                <span className="text-sm text-gray-400">{file ? file.name : 'Click to select…'}</span>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                Filename pattern: …_Diameter_PeerRouteRule.csv or …_Rbar_AddressRange.csv
              </p>
            </div>

            {/* DRA Type */}
            <div>
              <label className="text-xs text-gray-400 mb-1.5 block">DRA Type</label>
              <select
                value={draType}
                onChange={e => { setDraType(e.target.value); setInstLabel('') }}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-sky-500"
              >
                <option value="">Select DRA type…</option>
                {draTypes.map(t => <option key={t}>{t}</option>)}
              </select>
            </div>

            {/* Instance */}
            <div>
              <label className="text-xs text-gray-400 mb-1.5 block">Instance</label>
              <select
                value={instLabel}
                onChange={e => setInstLabel(e.target.value)}
                disabled={!draType}
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-sky-500 disabled:opacity-40"
              >
                <option value="">Select instance…</option>
                {labelsForType.map(l => <option key={l}>{l}</option>)}
              </select>
            </div>

            <button
              disabled={!file || !draType || !instLabel || ingest.isPending}
              onClick={() => ingest.mutate()}
              className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-sky-600 hover:bg-sky-500 disabled:opacity-40 text-white font-semibold text-sm transition-all"
            >
              <Upload size={15} />
              {ingest.isPending ? 'Queuing…' : 'Ingest Dump'}
            </button>

            {ingest.isSuccess && (
              <div className="flex items-center gap-2 text-green-400 text-sm">
                <CheckCircle2 size={15} /> Dump queued for ingestion
              </div>
            )}
            {ingest.isError && (
              <div className="flex items-center gap-2 text-red-400 text-sm">
                <AlertCircle size={15} /> {ingest.error?.response?.data?.detail ?? 'Upload failed'}
              </div>
            )}
          </div>
        </section>

        {/* Reconcile trigger */}
        <section className="rounded-xl border border-gray-700 bg-gray-800/40 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-700 flex items-center gap-2">
            <RefreshCw size={15} className="text-purple-400" />
            <span className="text-sm font-semibold text-gray-200">Manual Reconciliation</span>
          </div>
          <div className="p-5 space-y-4">
            <p className="text-xs text-gray-400">
              Trigger reconciliation to compare PENDING entries against the latest dump snapshots
              and mark entries as IMPLEMENTED or AWAITING_IMPLEMENTATION.
            </p>
            <p className="text-xs text-gray-500">Leave fields empty to reconcile all instances.</p>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-400 mb-1.5 block">DRA Type (optional)</label>
                <select
                  id="rdt"
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-purple-500"
                  defaultValue=""
                >
                  <option value="">All</option>
                  {draTypes.map(t => <option key={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-400 mb-1.5 block">Instance (optional)</label>
                <input
                  id="ril"
                  placeholder="e.g. DEL-01"
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-200 font-mono focus:outline-none focus:border-purple-500"
                />
              </div>
            </div>

            <button
              disabled={reconcile.isPending}
              onClick={() => {
                const dt = document.getElementById('rdt').value || undefined
                const il = document.getElementById('ril').value.trim() || undefined
                reconcile.mutate({ dra_type: dt, instance_label: il })
              }}
              className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-purple-600 hover:bg-purple-500 disabled:opacity-40 text-white font-semibold text-sm transition-all"
            >
              <RefreshCw size={15} className={reconcile.isPending ? 'animate-spin' : ''} />
              {reconcile.isPending ? 'Running…' : 'Run Reconciliation'}
            </button>

            {reconStatus && (
              <div className="bg-gray-700/40 rounded-lg p-3 text-xs space-y-1">
                <p className="text-green-400">✓ Implemented: <strong>{reconStatus.implemented ?? '—'}</strong></p>
                <p className="text-yellow-400">⌛ Not Implemented: <strong>{reconStatus.AWAITING_IMPLEMENTATION ?? '—'}</strong></p>
                <p className="text-orange-400">⚠ Unknown Entries: <strong>{reconStatus.unknown_entries ?? '—'}</strong></p>
              </div>
            )}
          </div>
        </section>
      </div>

      {/* Snapshot list */}
      <section className="rounded-xl border border-gray-700 bg-gray-800/40 overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-700 flex items-center gap-2">
          <Database size={15} className="text-sky-400" />
          <span className="text-sm font-semibold text-gray-200">Recent Snapshots</span>
          <button onClick={() => refetchSnaps()} className="ml-auto text-xs text-gray-500 hover:text-gray-300 flex items-center gap-1">
            <RefreshCw size={12} /> Refresh
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-700 text-gray-400">
                {['DRA Type', 'Instance', 'Object Type', 'File Name', 'Source Time', 'Ingested At'].map(h => (
                  <th key={h} className="px-4 py-2.5 text-left font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {snaps.map((s) => (
                <tr key={s.id} className="border-b border-gray-700/40 hover:bg-gray-700/20">
                  <td className="px-4 py-2 font-mono text-sky-300">{s.dra_type}</td>
                  <td className="px-4 py-2 font-mono text-gray-300">{s.instance_label}</td>
                  <td className="px-4 py-2">
                    <span className={`font-mono text-xs px-1.5 py-0.5 rounded ${
                      s.object_type === 'PRR' ? 'bg-blue-500/15 text-blue-300' : 'bg-purple-500/15 text-purple-300'
                    }`}>{s.object_type}</span>
                  </td>
                  <td className="px-4 py-2 text-gray-400 max-w-xs truncate font-mono">{s.file_name}</td>
                  <td className="px-4 py-2 text-gray-400">
                    {s.source_timestamp ? new Date(s.source_timestamp).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' }) : '—'}
                  </td>
                  <td className="px-4 py-2 text-gray-500">
                    {s.created_at ? new Date(s.created_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' }) : '—'}
                  </td>
                </tr>
              ))}
              {snaps.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-6 text-center text-gray-500">No snapshots yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
