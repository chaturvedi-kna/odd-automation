import { useState, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { Upload, Play, Download, CheckCircle2, AlertCircle, FileText, X } from 'lucide-react'
import api from '../api/client'
import InstanceSelector from '../components/InstanceSelector'
import ProgressBar from '../components/ProgressBar'

const STATUS_LABELS = {
  DONE: { label: 'Completed', cls: 'text-green-400' },
  DONE_PARTIAL: { label: 'Partial', cls: 'text-yellow-400' },
  FAILED: { label: 'Failed', cls: 'text-red-400' },
}

export default function NewRequest() {
  const nav = useNavigate()
  const fileRef = useRef(null)
  const dropRef = useRef(null)

  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [instances, setInstances] = useState([])
  const [requestId, setRequestId] = useState(null)
  const [summary, setSummary] = useState(null)

  // ── Drag & drop ──────────────────────────────────────────────────────────
  const onDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f?.name.endsWith('.csv')) setFile(f)
  }, [])

  // ── Submit mutation ──────────────────────────────────────────────────────
  const submit = useMutation({
    mutationFn: async () => {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('module', 'ILD')
      fd.append('selected_instances', JSON.stringify(instances))
      const r = await api.post('/requests/', fd)
      return r.data
    },
    onSuccess: (data) => setRequestId(data.id),
  })

  const handleRun = () => {
    if (!file) return
    if (instances.length === 0) return
    submit.mutate()
  }

  const handleDone = (payload) => {
    setSummary(payload)
  }

  const canRun = file && instances.length > 0 && !submit.isSuccess

  return (
    <div className="max-w-4xl mx-auto space-y-6 pb-10">
      <div>
        <h1 className="text-xl font-bold text-white">New Change Request</h1>
        <p className="text-sm text-gray-400 mt-1">Upload a CSV, select DRA instances, then run.</p>
      </div>

      {/* ── File Drop Zone ─────────────────────────────────────────────── */}
      <section className="rounded-xl border border-gray-700 bg-gray-800/40 overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-700 flex items-center gap-2">
          <FileText size={16} className="text-sky-400" />
          <span className="text-sm font-semibold text-gray-200">Input CSV</span>
        </div>
        <div
          ref={dropRef}
          onDragOver={e => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => !file && fileRef.current?.click()}
          className={`m-4 rounded-lg border-2 border-dashed transition-all cursor-pointer flex flex-col items-center justify-center py-10 gap-3 ${
            dragging ? 'border-sky-400 bg-sky-500/10' : 'border-gray-600 hover:border-gray-500'
          }`}
        >
          <input ref={fileRef} type="file" accept=".csv" className="hidden" onChange={e => setFile(e.target.files[0])} />
          {file ? (
            <div className="flex items-center gap-3">
              <FileText size={22} className="text-sky-400" />
              <div>
                <p className="text-sm font-medium text-white">{file.name}</p>
                <p className="text-xs text-gray-400">{(file.size / 1024).toFixed(1)} KB</p>
              </div>
              <button onClick={e => { e.stopPropagation(); setFile(null) }} className="ml-2 text-gray-500 hover:text-gray-300">
                <X size={16} />
              </button>
            </div>
          ) : (
            <>
              <Upload size={28} className="text-gray-500" />
              <div className="text-center">
                <p className="text-sm text-gray-300">Drop CSV here or <span className="text-sky-400">browse</span></p>
                <p className="text-xs text-gray-500 mt-1">Columns: Country, Operator, MCC, MNC, Realm, PRT Rule, Range, ACTION</p>
              </div>
            </>
          )}
        </div>
      </section>

      {/* ── Instance Selector ──────────────────────────────────────────── */}
      <section className="rounded-xl border border-gray-700 bg-gray-800/40 overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-700 flex items-center justify-between">
          <span className="text-sm font-semibold text-gray-200">DRA Instances</span>
          {instances.length > 0 && (
            <span className="text-xs font-mono bg-sky-500/20 text-sky-300 px-2 py-0.5 rounded">
              {instances.length} selected
            </span>
          )}
        </div>
        <div className="p-4">
          <InstanceSelector value={instances} onChange={setInstances} />
        </div>
      </section>

      {/* ── Run / Progress ─────────────────────────────────────────────── */}
      <section className="rounded-xl border border-gray-700 bg-gray-800/40 overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-700">
          <span className="text-sm font-semibold text-gray-200">Run</span>
        </div>
        <div className="p-5 space-y-4">
          {!requestId && (
            <button
              disabled={!canRun || submit.isPending}
              onClick={handleRun}
              className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-sky-600 hover:bg-sky-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold transition-all"
            >
              <Play size={16} />
              {submit.isPending ? 'Submitting…' : 'Run Processing Job'}
            </button>
          )}

          {submit.isError && (
            <div className="flex items-center gap-2 text-red-400 text-sm bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-2">
              <AlertCircle size={16} />
              {submit.error?.response?.data?.detail ?? 'Submission failed'}
            </div>
          )}

          {requestId && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-xs text-gray-400">
                <span className="font-mono text-gray-500">Request</span>
                <span className="font-mono text-sky-300">{requestId.slice(0, 8)}…</span>
              </div>
              <ProgressBar requestId={requestId} onDone={handleDone} />
            </div>
          )}
        </div>
      </section>

      {/* ── Summary (after done) ───────────────────────────────────────── */}
      {summary && requestId && (
        <section className="rounded-xl border border-gray-700 bg-gray-800/40 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-700 flex items-center gap-2">
            <CheckCircle2 size={16} className="text-green-400" />
            <span className="text-sm font-semibold text-gray-200">Result Summary</span>
            <span className={`ml-auto text-xs font-mono font-bold ${STATUS_LABELS[summary.status]?.cls}`}>
              {STATUS_LABELS[summary.status]?.label ?? summary.status}
            </span>
          </div>
          <div className="p-5 grid grid-cols-3 gap-4">
            {[
              { label: 'Processed', val: summary.processed, color: 'text-green-400' },
              { label: 'Skipped', val: summary.skipped, color: 'text-gray-400' },
              { label: 'Failed', val: summary.failed, color: 'text-red-400' },
            ].map(({ label, val, color }) => (
              <div key={label} className="text-center bg-gray-700/30 rounded-lg py-3">
                <p className={`text-2xl font-bold font-mono ${color}`}>{val ?? 0}</p>
                <p className="text-xs text-gray-500 mt-0.5">{label}</p>
              </div>
            ))}
          </div>

          {/* Download buttons */}
          <div className="px-5 pb-5 flex gap-3">
            <a
              href={`/api/exports/${requestId}/delta`}
              className="flex items-center gap-2 px-4 py-2 rounded-lg border border-sky-600/50 bg-sky-600/10 hover:bg-sky-600/20 text-sky-300 text-sm font-medium transition-all"
            >
              <Download size={14} />
              Delta Excel
            </a>
            <button
              onClick={() => nav(`/requests/${requestId}`)}
              className="flex items-center gap-2 px-4 py-2 rounded-lg border border-gray-600 bg-gray-700/30 hover:bg-gray-700 text-gray-300 text-sm font-medium transition-all"
            >
              View Full Detail
            </button>
          </div>
        </section>
      )}
    </div>
  )
}
