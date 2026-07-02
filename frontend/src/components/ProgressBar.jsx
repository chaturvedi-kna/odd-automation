import { useEffect, useState, useRef } from 'react'

const BASE = import.meta.env.VITE_API_BASE ?? ''

export default function ProgressBar({ requestId, onDone }) {
  const [state, setState] = useState({ total: 0, processed: 0, ok: 0, skipped: 0, failed: 0, done: false, status: null })
  const esRef = useRef(null)

  useEffect(() => {
    if (!requestId) return
    const token = localStorage.getItem('token')
    const url = `${BASE}/api/sse/${requestId}${token ? `?token=${token}` : ''}`
    const es = new EventSource(url)
    esRef.current = es

    es.onmessage = (e) => {
      try {
        const payload = JSON.parse(e.data)
        if (payload.type === 'connected') return
        if (payload.type === 'progress') {
          setState(p => ({
            ...p,
            total: payload.total ?? p.total,
            processed: payload.processed ?? p.processed,
            ok: payload.processed_ok ?? p.ok,
            skipped: payload.skipped ?? p.skipped,
            failed: payload.failed ?? p.failed,
          }))
        }
        if (payload.type === 'done') {
          setState(p => ({ ...p, done: true, status: payload.status }))
          es.close()
          onDone?.(payload)
        }
      } catch {}
    }
    es.onerror = () => es.close()
    return () => es.close()
  }, [requestId])

  if (!requestId) return null

  const pct = state.total > 0 ? Math.round((state.processed / state.total) * 100) : 0
  const done = state.done
  const statusColor = state.status === 'COMPLETED' ? 'text-green-400' : state.status === 'FAILED' ? 'text-red-400' : 'text-sky-400'

  return (
    <div className="space-y-3">
      {/* Bar */}
      <div className="relative h-2.5 bg-gray-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-300 ${done ? (state.failed ? 'bg-yellow-500' : 'bg-green-500') : 'bg-sky-500'}`}
          style={{ width: `${pct}%` }}
        />
        {!done && (
          <div
            className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent animate-pulse"
          />
        )}
      </div>

      {/* Stats row */}
      <div className="flex items-center justify-between text-xs">
        <div className="flex gap-4">
          <span className="text-gray-400">
            <span className="font-mono text-white">{state.processed}</span>
            <span className="text-gray-500">/{state.total}</span>
          </span>
          {state.ok > 0 && <span className="text-green-400 font-mono">✓ {state.ok}</span>}
          {state.skipped > 0 && <span className="text-gray-400 font-mono">↷ {state.skipped}</span>}
          {state.failed > 0 && <span className="text-red-400 font-mono">✗ {state.failed}</span>}
        </div>
        <span className={`font-mono font-bold ${done ? statusColor : 'text-sky-400'}`}>
          {done ? state.status : `${pct}%`}
        </span>
      </div>
    </div>
  )
}
