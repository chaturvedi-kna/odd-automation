import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Table2, Download, ChevronLeft, ChevronRight, ArrowUpDown, ArrowUp, ArrowDown, Search } from 'lucide-react'
import api from '../api/client'
import { downloadFile } from '../api/download'

const SOURCE_BADGE = {
  DUMP:           'bg-gray-600/30 text-gray-300 border-gray-600',
  PENDING_ADD:    'bg-green-500/15 text-green-300 border-green-500/30',
  PENDING_DELETE: 'bg-yellow-500/15 text-yellow-300 border-yellow-500/30',
}

const PRR_COLS = [
  { key: 'name', label: 'Rule Name' },
  { key: 'realm', label: 'Realm' },
  { key: 'route_list_name', label: 'Route List' },
  { key: 'peer_route_table', label: 'Peer Route Table' },
  { key: 'source', label: 'Source' },
]
const RBAR_COLS = [
  { key: 'table_name', label: 'Table' },
  { key: 'start_addr', label: 'Start Addr' },
  { key: 'end_addr', label: 'End Addr' },
  { key: 'destination', label: 'Destination' },
  { key: 'source', label: 'Source' },
]

const selCls =
  'bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-sky-500'

export default function MasterOdd() {
  const [draType, setDraType] = useState('')
  const [instLabel, setInstLabel] = useState('')
  const [objectType, setObjectType] = useState('PRR')
  const [source, setSource] = useState('')
  const [search, setSearch] = useState('')
  const [sortBy, setSortBy] = useState('')
  const [sortDir, setSortDir] = useState('asc')
  const [page, setPage] = useState(1)
  const pageSize = 50

  const { data: instances = [] } = useQuery({
    queryKey: ['instances'],
    queryFn: () => api.get('/instances/').then(r => r.data),
    staleTime: 3600_000,
  })

  const ready = draType && instLabel
  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['master-odd', draType, instLabel, objectType, source, search, sortBy, sortDir, page],
    queryFn: () => api.get('/master-odd/', {
      params: {
        dra_type: draType, instance_label: instLabel, object_type: objectType,
        source: source || undefined, search: search || undefined,
        sort_by: sortBy || undefined, sort_dir: sortDir,
        page, page_size: pageSize,
      },
    }).then(r => r.data),
    enabled: !!ready,
    keepPreviousData: true,
  })

  const draTypes = [...new Set(instances.map(i => i.dra_type))].sort()
  const labels = instances.filter(i => i.dra_type === draType).map(i => i.instance_label).sort()
  const cols = objectType === 'PRR' ? PRR_COLS : RBAR_COLS
  const items = data?.items ?? []
  const total = data?.total ?? 0
  const pages = Math.max(1, Math.ceil(total / pageSize))

  const resetPage = (fn) => (v) => { fn(v); setPage(1) }

  function toggleSort(key) {
    if (sortBy !== key) { setSortBy(key); setSortDir('asc') }
    else if (sortDir === 'asc') setSortDir('desc')
    else { setSortBy(''); setSortDir('asc') }
    setPage(1)
  }

  return (
    <div className="space-y-5 pb-10">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Table2 size={20} className="text-sky-400" /> Master ODD Viewer
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            Latest dump snapshot merged with pending changes, per DRA instance.
          </p>
        </div>
        {ready && (
          <button
            onClick={() => downloadFile(
              `/exports/master/download?dra_type=${draType}&instance_label=${instLabel}`,
              `ODD_master_${draType}_${instLabel}.xlsx`,
            )}
            className="flex items-center gap-2 px-4 py-2 rounded-lg border border-sky-600/50 bg-sky-600/10 hover:bg-sky-600/20 text-sky-300 text-sm font-medium transition-all"
          >
            <Download size={14} /> Download Excel
          </button>
        )}
      </div>

      {/* ── Filters ──────────────────────────────────────────────────────── */}
      <section className="rounded-xl border border-gray-700 bg-gray-800/40 p-4 flex flex-wrap gap-3 items-center">
        <select className={selCls} value={draType} onChange={e => { setDraType(e.target.value); setInstLabel(''); setPage(1) }}>
          <option value="">DRA type…</option>
          {draTypes.map(t => <option key={t}>{t}</option>)}
        </select>
        <select className={selCls} value={instLabel} onChange={e => resetPage(setInstLabel)(e.target.value)} disabled={!draType}>
          <option value="">Instance…</option>
          {labels.map(l => <option key={l}>{l}</option>)}
        </select>

        {/* PRR / RBAR tabs */}
        <div className="flex rounded-lg border border-gray-700 overflow-hidden">
          {['PRR', 'RBAR'].map(t => (
            <button key={t}
              onClick={() => { setObjectType(t); setSortBy(''); setPage(1) }}
              className={`px-4 py-2 text-sm font-semibold transition-all ${
                objectType === t ? 'bg-sky-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-gray-200'
              }`}
            >{t}</button>
          ))}
        </div>

        <select className={selCls} value={source} onChange={e => resetPage(setSource)(e.target.value)}>
          <option value="">All sources</option>
          <option value="DUMP">Dump only</option>
          <option value="PENDING_ADD">Pending ADD</option>
          <option value="PENDING_DELETE">Pending DELETE</option>
        </select>

        <div className="relative flex-1 min-w-48">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            className={`${selCls} w-full pl-8`}
            placeholder="Search realm, rule, destination, range…"
            value={search}
            onChange={e => resetPage(setSearch)(e.target.value)}
          />
        </div>
      </section>

      {/* ── Table ────────────────────────────────────────────────────────── */}
      {!ready ? (
        <div className="rounded-xl border border-dashed border-gray-700 py-16 text-center text-gray-500 text-sm">
          Select a DRA type and instance to view its Master ODD.
        </div>
      ) : (
        <section className="rounded-xl border border-gray-700 bg-gray-800/40 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-700 flex items-center gap-3 text-xs text-gray-400">
            <span className="font-mono text-sky-300">{draType} / {instLabel}</span>
            <span>{total} rows{isFetching ? ' · refreshing…' : ''}</span>
            {data?.snapshot ? (
              <span className="ml-auto">
                Snapshot: <span className="font-mono">{data.snapshot.file_name}</span>
                {data.snapshot.source_timestamp &&
                  ` · ${new Date(data.snapshot.source_timestamp).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })} IST`}
              </span>
            ) : (
              <span className="ml-auto text-yellow-400">No dump snapshot ingested yet — showing pending changes only.</span>
            )}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-700 text-gray-400">
                  {cols.map(c => (
                    <th key={c.key} className="px-4 py-2.5 text-left font-medium whitespace-nowrap">
                      <button onClick={() => toggleSort(c.key)} className="flex items-center gap-1 hover:text-gray-200">
                        {c.label}
                        {sortBy === c.key
                          ? (sortDir === 'asc' ? <ArrowUp size={12} /> : <ArrowDown size={12} />)
                          : <ArrowUpDown size={12} className="opacity-40" />}
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {isLoading && <tr><td colSpan={cols.length} className="px-4 py-8 text-center text-gray-500">Loading…</td></tr>}
                {!isLoading && items.length === 0 && (
                  <tr><td colSpan={cols.length} className="px-4 py-8 text-center text-gray-500">No rows match.</td></tr>
                )}
                {items.map((r, i) => (
                  <tr key={i} className="border-b border-gray-700/40 hover:bg-gray-700/20">
                    {cols.map(c => (
                      <td key={c.key} className="px-4 py-2 font-mono text-gray-300 max-w-sm truncate">
                        {c.key === 'source' ? (
                          <span className={`px-1.5 py-0.5 rounded border ${SOURCE_BADGE[r.source]}`}>{r.source}</span>
                        ) : (r[c.key] ?? '—')}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="px-4 py-2.5 border-t border-gray-700 flex items-center justify-between text-xs text-gray-400">
            <span>Page {page} / {pages}</span>
            <div className="flex gap-1">
              <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}
                className="p-1.5 rounded hover:bg-gray-700 disabled:opacity-30"><ChevronLeft size={14} /></button>
              <button disabled={page >= pages} onClick={() => setPage(p => p + 1)}
                className="p-1.5 rounded hover:bg-gray-700 disabled:opacity-30"><ChevronRight size={14} /></button>
            </div>
          </div>
        </section>
      )}
    </div>
  )
}
