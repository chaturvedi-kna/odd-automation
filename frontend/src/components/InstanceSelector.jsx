import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronDown, ChevronRight, CheckSquare, Square, MinusSquare } from 'lucide-react'
import api from '../api/client'

function useInstanceTree() {
  return useQuery({
    queryKey: ['instances', 'tree'],
    queryFn: () => api.get('/instances/tree').then(r => r.data),
    staleTime: 3600_000,
  })
}

function triState(items, selected) {
  const total = items.length
  const sel = items.filter(x => selected.has(x)).length
  if (sel === 0) return 'none'
  if (sel === total) return 'all'
  return 'partial'
}

export default function InstanceSelector({ value = [], onChange }) {
  const { data: tree = {}, isLoading } = useInstanceTree()
  const [openSites, setOpenSites] = useState({})
  const [openTypes, setOpenTypes] = useState({})

  // value is array of {dra_type, instance_label}
  const selected = new Set(value.map(v => `${v.dra_type}|${v.instance_label}`))

  function toggle(dra_type, instance_label) {
    const key = `${dra_type}|${instance_label}`
    const next = new Set(selected)
    if (next.has(key)) next.delete(key)
    else next.add(key)
    emit(next)
  }

  function toggleType(site, dra_type) {
    const items = tree[site]?.[dra_type] ?? []
    const keys = items.map(i => `${dra_type}|${i.instance_label}`)
    const state = triState(keys, selected)
    const next = new Set(selected)
    if (state === 'all') keys.forEach(k => next.delete(k))
    else keys.forEach(k => next.add(k))
    emit(next)
  }

  function toggleSite(site) {
    const keys = []
    Object.entries(tree[site] ?? {}).forEach(([dra_type, insts]) =>
      insts.forEach(i => keys.push(`${dra_type}|${i.instance_label}`))
    )
    const state = triState(keys, selected)
    const next = new Set(selected)
    if (state === 'all') keys.forEach(k => next.delete(k))
    else keys.forEach(k => next.add(k))
    emit(next)
  }

  function toggleAll() {
    const all = []
    Object.entries(tree).forEach(([site, types]) =>
      Object.entries(types).forEach(([dra_type, insts]) =>
        insts.forEach(i => all.push(`${dra_type}|${i.instance_label}`))
      )
    )
    const state = triState(all, selected)
    const next = new Set(selected)
    if (state === 'all') all.forEach(k => next.delete(k))
    else all.forEach(k => next.add(k))
    emit(next)
  }

  function emit(keySet) {
    const result = []
    Object.entries(tree).forEach(([site, types]) =>
      Object.entries(types).forEach(([dra_type, insts]) =>
        insts.forEach(i => {
          if (keySet.has(`${dra_type}|${i.instance_label}`))
            result.push({ dra_type, instance_label: i.instance_label })
        })
      )
    )
    onChange(result)
  }

  function Checkbox({ state }) {
    if (state === 'all') return <CheckSquare size={15} className="text-sky-400 shrink-0" />
    if (state === 'partial') return <MinusSquare size={15} className="text-sky-400/60 shrink-0" />
    return <Square size={15} className="text-gray-500 shrink-0" />
  }

  if (isLoading) return <p className="text-xs text-gray-500 py-2">Loading instances…</p>

  const allKeys = []
  Object.entries(tree).forEach(([site, types]) =>
    Object.entries(types).forEach(([dra_type, insts]) =>
      insts.forEach(i => allKeys.push(`${dra_type}|${i.instance_label}`))
    )
  )
  const allState = triState(allKeys, selected)

  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800/50 overflow-hidden text-sm select-none">
      {/* Select all */}
      <button
        onClick={toggleAll}
        className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-700/50 border-b border-gray-700 text-gray-300 font-medium"
      >
        <Checkbox state={allState} />
        <span>Select All Instances</span>
        <span className="ml-auto text-xs text-gray-500">{selected.size}/{allKeys.length}</span>
      </button>

      {/* Sites */}
      {Object.entries(tree).sort(([a], [b]) => a.localeCompare(b)).map(([site, types]) => {
        const siteKeys = []
        Object.entries(types).forEach(([dt, insts]) =>
          insts.forEach(i => siteKeys.push(`${dt}|${i.instance_label}`))
        )
        const siteState = triState(siteKeys, selected)
        const siteOpen = openSites[site] !== false  // open by default

        return (
          <div key={site} className="border-b border-gray-700 last:border-0">
            <div className="flex items-center">
              <button
                onClick={() => toggleSite(site)}
                className="flex items-center gap-2 px-3 py-2 flex-1 hover:bg-gray-700/50 text-gray-200 font-semibold"
              >
                <Checkbox state={siteState} />
                <span className="font-mono text-sky-300">{site}</span>
                <span className="text-xs text-gray-500 font-normal">({siteKeys.length})</span>
              </button>
              <button
                onClick={() => setOpenSites(p => ({ ...p, [site]: !siteOpen }))}
                className="px-3 py-2 hover:bg-gray-700/50 text-gray-400"
              >
                {siteOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              </button>
            </div>

            {siteOpen && Object.entries(types).map(([dra_type, insts]) => {
              const typeKeys = insts.map(i => `${dra_type}|${i.instance_label}`)
              const typeState = triState(typeKeys, selected)
              const typeOpen = openTypes[`${site}|${dra_type}`] !== false

              return (
                <div key={dra_type} className="border-t border-gray-700/50">
                  <div className="flex items-center pl-5">
                    <button
                      onClick={() => toggleType(site, dra_type)}
                      className="flex items-center gap-2 px-3 py-1.5 flex-1 hover:bg-gray-700/40 text-gray-300"
                    >
                      <Checkbox state={typeState} />
                      <span className="text-xs font-semibold uppercase tracking-wider">{dra_type}</span>
                    </button>
                    <button
                      onClick={() => setOpenTypes(p => ({ ...p, [`${site}|${dra_type}`]: !typeOpen }))}
                      className="px-3 py-1.5 hover:bg-gray-700/40 text-gray-500"
                    >
                      {typeOpen ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                    </button>
                  </div>

                  {typeOpen && (
                    <div className="pl-14 pb-1.5 flex flex-wrap gap-1.5 pr-3">
                      {insts.map(inst => {
                        const key = `${dra_type}|${inst.instance_label}`
                        const on = selected.has(key)
                        return (
                          <button
                            key={key}
                            onClick={() => toggle(dra_type, inst.instance_label)}
                            className={`px-2 py-0.5 rounded text-xs font-mono border transition-all ${
                              on
                                ? 'bg-sky-500/20 border-sky-500/60 text-sky-300'
                                : 'bg-gray-700/40 border-gray-600 text-gray-400 hover:border-gray-500'
                            }`}
                          >
                            {inst.instance_label}
                          </button>
                        )
                      })}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )
      })}
    </div>
  )
}
