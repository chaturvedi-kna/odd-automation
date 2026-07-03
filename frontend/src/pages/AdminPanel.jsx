import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { UserPlus, Trash2, Shield, KeyRound, Check, X, AlertCircle } from 'lucide-react'
import api from '../api/client'
import { useAuth } from '../contexts/AuthContext'

const ROLES = ['admin', 'operator', 'viewer']
const ROLE_BADGE = {
  admin:    'bg-red-500/15 text-red-300 border-red-500/30',
  operator: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
  viewer:   'bg-gray-600/30 text-gray-300 border-gray-600',
}

const inputCls =
  'w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-sky-500'

export default function AdminPanel() {
  const qc = useQueryClient()
  const { user: me } = useAuth()
  const [form, setForm] = useState({ username: '', password: '', email: '', role: 'operator' })
  const [error, setError] = useState('')
  const [pwdFor, setPwdFor] = useState(null)   // user id whose password is being reset
  const [newPwd, setNewPwd] = useState('')

  const { data: users = [], isLoading } = useQuery({
    queryKey: ['users'],
    queryFn: () => api.get('/users/').then(r => r.data),
  })

  const invalidate = () => qc.invalidateQueries({ queryKey: ['users'] })
  const onErr = (e) => setError(e?.response?.data?.detail ?? 'Operation failed')

  const createUser = useMutation({
    mutationFn: () => api.post('/users/', form),
    onSuccess: () => { setForm({ username: '', password: '', email: '', role: 'operator' }); setError(''); invalidate() },
    onError: onErr,
  })
  const updateUser = useMutation({
    mutationFn: ({ id, ...payload }) => api.patch(`/users/${id}`, payload),
    onSuccess: () => { setError(''); setPwdFor(null); setNewPwd(''); invalidate() },
    onError: onErr,
  })
  const deleteUser = useMutation({
    mutationFn: (id) => api.delete(`/users/${id}`),
    onSuccess: () => { setError(''); invalidate() },
    onError: onErr,
  })

  return (
    <div className="space-y-6 pb-10">
      <div>
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <Shield size={20} className="text-red-400" /> Admin Panel
        </h1>
        <p className="text-sm text-gray-400 mt-1">Create, update and remove users and their roles.</p>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-red-400 text-sm bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-2">
          <AlertCircle size={15} /> {error}
          <button onClick={() => setError('')} className="ml-auto text-gray-500 hover:text-gray-300"><X size={14} /></button>
        </div>
      )}

      {/* ── Create user ──────────────────────────────────────────────────── */}
      <section className="rounded-xl border border-gray-700 bg-gray-800/40 overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-700 flex items-center gap-2">
          <UserPlus size={15} className="text-sky-400" />
          <span className="text-sm font-semibold text-gray-200">Create User</span>
        </div>
        <div className="p-5 grid grid-cols-1 md:grid-cols-5 gap-3 items-end">
          <div>
            <label className="text-xs text-gray-400 mb-1.5 block">Username</label>
            <input className={inputCls} value={form.username}
              onChange={e => setForm(f => ({ ...f, username: e.target.value }))} />
          </div>
          <div>
            <label className="text-xs text-gray-400 mb-1.5 block">Password</label>
            <input type="password" className={inputCls} value={form.password}
              onChange={e => setForm(f => ({ ...f, password: e.target.value }))} />
          </div>
          <div>
            <label className="text-xs text-gray-400 mb-1.5 block">Email (optional)</label>
            <input className={inputCls} value={form.email}
              onChange={e => setForm(f => ({ ...f, email: e.target.value }))} />
          </div>
          <div>
            <label className="text-xs text-gray-400 mb-1.5 block">Role</label>
            <select className={inputCls} value={form.role}
              onChange={e => setForm(f => ({ ...f, role: e.target.value }))}>
              {ROLES.map(r => <option key={r}>{r}</option>)}
            </select>
          </div>
          <button
            disabled={!form.username || form.password.length < 6 || createUser.isPending}
            onClick={() => createUser.mutate()}
            className="flex items-center justify-center gap-2 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 disabled:opacity-40 text-white font-semibold text-sm transition-all"
          >
            <UserPlus size={14} /> {createUser.isPending ? 'Creating…' : 'Create'}
          </button>
        </div>
        <p className="px-5 pb-4 text-xs text-gray-500">Password must be at least 6 characters.</p>
      </section>

      {/* ── Users table ──────────────────────────────────────────────────── */}
      <section className="rounded-xl border border-gray-700 bg-gray-800/40 overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-700">
          <span className="text-sm font-semibold text-gray-200">Users</span>
          <span className="ml-2 text-xs text-gray-500">{users.length}</span>
        </div>
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-gray-700 text-gray-400">
              {['Username', 'Email', 'Role', 'Status', 'Created (IST)', 'Actions'].map(h => (
                <th key={h} className="px-4 py-2.5 text-left font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-500">Loading…</td></tr>}
            {users.map(u => (
              <tr key={u.id} className="border-b border-gray-700/40 hover:bg-gray-700/20">
                <td className="px-4 py-2.5 font-mono text-gray-200">
                  {u.username}
                  {u.id === me?.id && <span className="ml-2 text-[10px] text-sky-400">(you)</span>}
                </td>
                <td className="px-4 py-2.5 text-gray-400">{u.email ?? '—'}</td>
                <td className="px-4 py-2.5">
                  <select
                    value={u.role}
                    disabled={u.id === me?.id}
                    onChange={e => updateUser.mutate({ id: u.id, role: e.target.value })}
                    className={`border rounded px-1.5 py-0.5 bg-transparent font-mono text-xs ${ROLE_BADGE[u.role]} disabled:opacity-60`}
                  >
                    {ROLES.map(r => <option key={r} className="bg-gray-800 text-gray-200">{r}</option>)}
                  </select>
                </td>
                <td className="px-4 py-2.5">
                  <button
                    disabled={u.id === me?.id}
                    onClick={() => updateUser.mutate({ id: u.id, is_active: !u.is_active })}
                    className={`px-2 py-0.5 rounded-full text-xs font-semibold border transition-all disabled:opacity-60 ${
                      u.is_active
                        ? 'bg-green-500/15 text-green-300 border-green-500/30'
                        : 'bg-gray-700 text-gray-400 border-gray-600'
                    }`}
                  >
                    {u.is_active ? 'active' : 'inactive'}
                  </button>
                </td>
                <td className="px-4 py-2.5 text-gray-500 whitespace-nowrap">
                  {u.created_at ? new Date(u.created_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' }) : '—'}
                </td>
                <td className="px-4 py-2.5">
                  <div className="flex items-center gap-2">
                    {pwdFor === u.id ? (
                      <>
                        <input
                          type="password" placeholder="New password" value={newPwd} autoFocus
                          onChange={e => setNewPwd(e.target.value)}
                          className="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 w-32 focus:outline-none focus:border-sky-500"
                        />
                        <button
                          disabled={newPwd.length < 6}
                          onClick={() => updateUser.mutate({ id: u.id, password: newPwd })}
                          className="p-1 rounded text-green-400 hover:bg-gray-700 disabled:opacity-30" title="Save password"
                        ><Check size={14} /></button>
                        <button onClick={() => { setPwdFor(null); setNewPwd('') }}
                          className="p-1 rounded text-gray-500 hover:bg-gray-700" title="Cancel"
                        ><X size={14} /></button>
                      </>
                    ) : (
                      <button onClick={() => { setPwdFor(u.id); setNewPwd('') }}
                        className="p-1.5 rounded text-gray-400 hover:bg-gray-700 hover:text-sky-300" title="Reset password"
                      ><KeyRound size={14} /></button>
                    )}
                    <button
                      disabled={u.id === me?.id || deleteUser.isPending}
                      onClick={() => { if (confirm(`Delete user '${u.username}'?`)) deleteUser.mutate(u.id) }}
                      className="p-1.5 rounded text-gray-400 hover:bg-gray-700 hover:text-red-400 disabled:opacity-30"
                      title="Delete user"
                    ><Trash2 size={14} /></button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  )
}
