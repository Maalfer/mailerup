import { useEffect, useState } from 'react'
import { Plus, Trash2, Pencil, X } from 'lucide-react'
import api, { fetchAll } from '../api'
import { useAuth } from '../auth.jsx'

export default function Users() {
  const { user: me, setUser } = useAuth()
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [editTarget, setEditTarget] = useState(null)

  async function load() {
    setLoading(true)
    try {
      setUsers(await fetchAll('/auth/users/'))
    } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  async function handleDelete(u) {
    if (!confirm(`¿Eliminar ${u.email}?`)) return
    try {
      await api.delete(`/auth/users/${u.id}/`)
      await load()
    } catch (err) {
      alert(err.response?.data?.detail || 'Error')
    }
  }

  async function refreshSelfIfNeeded(updatedId) {
    if (updatedId === me.id) {
      const r = await api.get('/auth/me/')
      setUser(r.data)
    }
  }

  return (
    <div className="max-w-5xl space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Gestión de usuarios</h1>
          <p className="text-sm text-gray-500 dark:text-slate-400">Crea, edita y elimina cuentas. Puedes editarte a ti mismo.</p>
        </div>
        <button className="btn-primary" onClick={() => setShowAdd(true)}>
          <Plus className="h-4 w-4" /> Nuevo usuario
        </button>
      </div>

      <div className="card overflow-hidden">
        {loading ? (
          <div role="status" aria-live="polite" className="p-8 text-center text-gray-500 dark:text-slate-400">Cargando…</div>
        ) : (
          <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[600px]" aria-label="Lista de usuarios">
            <thead className="bg-gray-50 dark:bg-slate-700 text-gray-500 dark:text-slate-400 text-xs uppercase">
              <tr>
                <th scope="col" className="px-4 py-3 text-left">Email</th>
                <th scope="col" className="px-4 py-3 text-left">Usuario</th>
                <th scope="col" className="px-4 py-3 text-left">Empresa</th>
                <th scope="col" className="px-4 py-3 text-left">Rol</th>
                <th scope="col" className="px-4 py-3 text-left">Alta</th>
                <th scope="col" className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-slate-700">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-gray-50 dark:hover:bg-slate-700">
                  <td className="px-4 py-3 font-medium text-gray-900 dark:text-slate-100">
                    {u.email}
                    {u.id === me.id && (
                      <span className="ml-2 text-xs text-gray-400 dark:text-slate-500">(tú)</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-600 dark:text-slate-300">{u.username || '—'}</td>
                  <td className="px-4 py-3 text-gray-600 dark:text-slate-300">{u.company || '—'}</td>
                  <td className="px-4 py-3">
                    {u.is_admin
                      ? <span className="badge bg-primary-100 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300">admin</span>
                      : <span className="badge bg-gray-100 text-gray-600 dark:bg-slate-700 dark:text-slate-300">usuario</span>}
                  </td>
                  <td className="px-4 py-3 text-gray-500 dark:text-slate-400">{new Date(u.date_joined).toLocaleDateString()}</td>
                  <td className="px-4 py-3 text-right space-x-2">
                    <button
                      onClick={() => setEditTarget(u)}
                      aria-label={`Editar usuario ${u.email}`}
                      className="text-gray-400 hover:text-primary-600 dark:hover:text-primary-400"
                    >
                      <Pencil className="h-4 w-4 inline" />
                    </button>
                    <button
                      onClick={() => handleDelete(u)}
                      aria-label={`Eliminar usuario ${u.email}`}
                      className="text-gray-400 hover:text-red-600"
                    >
                      <Trash2 className="h-4 w-4 inline" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </div>

      {showAdd && (
        <UserModal
          mode="create"
          onClose={() => setShowAdd(false)}
          onSaved={async () => { setShowAdd(false); await load() }}
        />
      )}

      {editTarget && (
        <UserModal
          mode="edit"
          user={editTarget}
          isSelf={editTarget.id === me.id}
          onClose={() => setEditTarget(null)}
          onSaved={async () => {
            const id = editTarget.id
            setEditTarget(null)
            await load()
            await refreshSelfIfNeeded(id)
          }}
        />
      )}
    </div>
  )
}

function UserModal({ mode, user, isSelf, onClose, onSaved }) {
  const isCreate = mode === 'create'
  const [form, setForm] = useState({
    email: user?.email || '',
    username: user?.username || '',
    company: user?.company || '',
    is_admin: !!user?.is_admin,
    password: '',
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setBusy(true); setError(null)
    try {
      const payload = {
        email: form.email,
        username: form.username,
        company: form.company,
        is_admin: form.is_admin,
      }
      if (form.password) payload.password = form.password
      if (isCreate) {
        await api.post('/auth/users/', payload)
      } else {
        await api.patch(`/auth/users/${user.id}/`, payload)
      }
      await onSaved()
    } catch (err) {
      const d = err.response?.data
      setError(
        d?.detail
        || d?.email?.[0]
        || d?.username?.[0]
        || (typeof d === 'object' ? JSON.stringify(d) : 'Error')
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="user-modal-title"
        className="card w-full max-w-md flex flex-col max-h-[90vh] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 dark:border-slate-700 flex-shrink-0">
          <h2 id="user-modal-title" className="text-lg font-semibold">
            {isCreate ? 'Nuevo usuario' : `Editar ${user.email}`}
          </h2>
          <button
            aria-label="Cerrar modal"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-700 dark:text-slate-400 dark:hover:text-slate-200"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col flex-1 overflow-hidden">
          <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
            {isSelf && (
              <div className="text-xs text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-800 rounded px-2 py-1.5">
                ⚠ Estás editando tu propio usuario. Si cambias el email o la contraseña, úsalos para volver a entrar.
              </div>
            )}
            <div>
              <label htmlFor="user-email" className="label">Email *</label>
              <input
                id="user-email"
                autoFocus
                className="input"
                type="email"
                required
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
              />
            </div>
            <div>
              <label htmlFor="user-username" className="label">Usuario *</label>
              <input
                id="user-username"
                className="input"
                required
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
              />
            </div>
            <div>
              <label htmlFor="user-company" className="label">Empresa</label>
              <input
                id="user-company"
                className="input"
                value={form.company}
                onChange={(e) => setForm({ ...form, company: e.target.value })}
              />
            </div>
            <div>
              <label htmlFor="user-password" className="label">
                {isCreate ? 'Contraseña *' : 'Nueva contraseña (déjala vacía para no cambiarla)'}
              </label>
              <input
                id="user-password"
                className="input"
                type="text"
                minLength={isCreate ? 8 : 0}
                required={isCreate}
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                placeholder={isCreate ? 'Mínimo 8 caracteres' : ''}
              />
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={form.is_admin}
                onChange={(e) => setForm({ ...form, is_admin: e.target.checked })} />
              Rol de administrador
            </label>

            {error && <p role="alert" className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          </div>

          <div className="flex justify-end gap-2 px-6 py-4 border-t border-gray-100 dark:border-slate-700 flex-shrink-0">
            <button type="button" className="btn-secondary" onClick={onClose}>Cancelar</button>
            <button className="btn-primary" disabled={busy}>
              {busy ? 'Guardando…' : (isCreate ? 'Crear' : 'Guardar')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
