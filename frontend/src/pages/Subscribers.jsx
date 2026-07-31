import { useEffect, useRef, useState } from 'react'
import { Plus, Upload, Download, Trash2, X, Users, AlertTriangle, RefreshCw, ChevronLeft, ChevronRight, Search, Layers, Pencil } from 'lucide-react'
import api from '../api'

const STATUS_LABELS = {
  active: 'Activo',
  unsubscribed: 'Dado de baja',
  bounced: 'Rebotado',
  complained: 'Queja spam',
}

function GroupsModal({ groups, onClose, onChanged }) {
  const [newName, setNewName] = useState('')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState(null)

  async function handleCreate(e) {
    e.preventDefault()
    if (!newName.trim()) return
    setCreating(true)
    setError(null)
    try {
      await api.post('/subscribers/groups/', { name: newName.trim() })
      setNewName('')
      onChanged()
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al crear el grupo')
    } finally {
      setCreating(false)
    }
  }

  async function handleRename(g) {
    const name = prompt('Nuevo nombre del grupo:', g.name)
    if (name == null || !name.trim() || name.trim() === g.name) return
    try {
      await api.patch(`/subscribers/groups/${g.id}/`, { name: name.trim() })
      onChanged()
    } catch (err) {
      alert(err.response?.data?.detail || 'Error al renombrar el grupo')
    }
  }

  async function handleDelete(g) {
    if (!confirm(`¿Eliminar el grupo "${g.name}"? Se eliminarán también sus ${g.subscriber_count} suscriptores. Esta acción no se puede deshacer.`)) return
    try {
      await api.delete(`/subscribers/groups/${g.id}/`)
      onChanged()
    } catch (err) {
      alert(err.response?.data?.detail || 'Error al eliminar el grupo')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="groups-modal-title"
        className="card w-full max-w-md flex flex-col max-h-[90vh] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 dark:border-slate-700 flex-shrink-0">
          <h2 id="groups-modal-title" className="text-lg font-semibold">Grupos de suscriptores</h2>
          <button type="button" aria-label="Cerrar" onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:text-slate-400 dark:hover:text-slate-200">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {error && (
            <div role="alert" className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg p-3">
              {error}
            </div>
          )}
          <ul className="divide-y divide-gray-100 dark:divide-slate-700 border border-gray-100 dark:border-slate-700 rounded-lg">
            {groups.map((g) => (
              <li key={g.id} className="flex items-center justify-between px-3 py-2">
                <span className="text-sm">
                  <span className="font-medium text-gray-900 dark:text-slate-100">{g.name}</span>
                  <span className="text-gray-400 dark:text-slate-500"> · {g.subscriber_count}</span>
                </span>
                <span className="flex items-center gap-2">
                  <button aria-label={`Renombrar ${g.name}`} onClick={() => handleRename(g)} className="text-gray-400 hover:text-primary-600">
                    <Pencil className="h-4 w-4" />
                  </button>
                  <button aria-label={`Eliminar ${g.name}`} onClick={() => handleDelete(g)} className="text-gray-400 hover:text-red-600">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </span>
              </li>
            ))}
          </ul>
          <form onSubmit={handleCreate} className="flex items-center gap-2">
            <input
              className="input flex-1"
              placeholder="Nombre del nuevo grupo"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
            />
            <button className="btn-primary whitespace-nowrap" disabled={creating || !newName.trim()}>
              <Plus className="h-4 w-4" /> {creating ? 'Creando…' : 'Crear'}
            </button>
          </form>
        </div>
        <div className="flex justify-end px-6 py-4 border-t border-gray-100 dark:border-slate-700 flex-shrink-0">
          <button className="btn-secondary" onClick={onClose}>Cerrar</button>
        </div>
      </div>
    </div>
  )
}

function CleanupTab({ onDeleted }) {
  const [threshold, setThreshold] = useState(25)
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [analyzed, setAnalyzed] = useState(false)
  const [selected, setSelected] = useState(new Set())
  const [deleting, setDeleting] = useState(false)
  const [result, setResult] = useState(null)

  async function load() {
    setLoading(true)
    setAnalyzed(false)
    setSelected(new Set())
    setResult(null)
    try {
      const r = await api.get(`/subscribers/low-engagement/?threshold=${threshold}`)
      setItems(r.data)
      setAnalyzed(true)
    } catch (err) {
      alert(err.response?.data?.detail || 'Error al analizar suscriptores')
    } finally {
      setLoading(false)
    }
  }

  function toggleSelect(id) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  function toggleAll() {
    if (selected.size === items.length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(items.map((i) => i.id)))
    }
  }

  async function handleDelete() {
    if (selected.size === 0) return
    if (!confirm(`¿Eliminar ${selected.size} suscriptores? Esta acción no se puede deshacer.`)) return
    setDeleting(true)
    try {
      const r = await api.post('/subscribers/bulk-delete/', { ids: [...selected] })
      setResult(r.data.deleted)
      setSelected(new Set())
      await load()
      if (onDeleted) onDeleted()
    } catch (err) {
      alert(err.response?.data?.detail || 'Error al eliminar suscriptores')
    } finally {
      setDeleting(false)
    }
  }

  function getRateBadge(rate) {
    if (rate === 0) return <span className="badge bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">Nunca abrió</span>
    if (rate < 10) return <span className="badge bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300">{rate}%</span>
    return <span className="badge bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400">{rate}%</span>
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-base font-semibold text-gray-900 dark:text-slate-100">Suscriptores inactivos</h2>
        <p className="text-sm text-gray-500 dark:text-slate-400">
          Contactos con baja tasa de apertura que podrías eliminar para mantener tu lista limpia.
        </p>
      </div>

      <div className="flex items-center gap-3">
        <select
          className="input w-auto"
          value={threshold}
          onChange={(e) => setThreshold(Number(e.target.value))}
        >
          <option value={0}>Nunca han abierto (0%)</option>
          <option value={10}>Menos del 10%</option>
          <option value={25}>Menos del 25%</option>
          <option value={50}>Menos del 50%</option>
        </select>
        <button className="btn-primary" onClick={load} disabled={loading}>
          {loading ? (
            <><RefreshCw className="h-4 w-4 animate-spin" /> Analizando...</>
          ) : (
            <><AlertTriangle className="h-4 w-4" /> Analizar</>
          )}
        </button>
      </div>

      {result !== null && (
        <div role="status" aria-live="polite" className="card p-4 bg-green-50 border-green-200 dark:bg-green-900/30 dark:border-green-800 flex items-center justify-between">
          <span className="text-sm text-green-800 dark:text-green-400">
            Se han eliminado {result} suscriptores.
          </span>
          <button aria-label="Cerrar notificación" onClick={() => setResult(null)} className="text-green-700 dark:text-green-400">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {analyzed && !loading && (
        <div className="card overflow-hidden">
          {items.length === 0 ? (
            <div className="p-12 text-center">
              <p className="text-gray-500 dark:text-slate-400">
                No hay suscriptores por debajo del umbral seleccionado. ¡Tu lista está en buen estado! ✓
              </p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
              <table className="w-full text-sm min-w-[600px]" aria-label="Suscriptores inactivos">
                <thead className="bg-gray-50 dark:bg-slate-700 text-gray-500 dark:text-slate-400 text-xs uppercase">
                  <tr>
                    <th scope="col" className="px-4 py-3 text-left">
                      <input
                        type="checkbox"
                        aria-label="Seleccionar todos"
                        checked={items.length > 0 && selected.size === items.length}
                        onChange={toggleAll}
                        className="rounded border-gray-300"
                      />
                    </th>
                    <th scope="col" className="px-4 py-3 text-left">Email</th>
                    <th scope="col" className="px-4 py-3 text-left">Nombre</th>
                    <th scope="col" className="px-4 py-3 text-left">Enviados</th>
                    <th scope="col" className="px-4 py-3 text-left">Abiertos</th>
                    <th scope="col" className="px-4 py-3 text-left">Tasa apertura</th>
                    <th scope="col" className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-slate-700">
                  {items.map((s) => (
                    <tr key={s.id} className={selected.has(s.id) ? 'bg-red-50 dark:bg-red-900/20' : ''}>
                      <td className="px-4 py-3">
                        <input
                          type="checkbox"
                          checked={selected.has(s.id)}
                          onChange={() => toggleSelect(s.id)}
                          className="rounded border-gray-300"
                        />
                      </td>
                      <td className="px-4 py-3 font-medium text-gray-900 dark:text-slate-100">{s.email}</td>
                      <td className="px-4 py-3 text-gray-600 dark:text-slate-300">
                        {[s.first_name, s.last_name].filter(Boolean).join(' ') || '—'}
                      </td>
                      <td className="px-4 py-3 text-gray-600 dark:text-slate-300">{s.sends_count}</td>
                      <td className="px-4 py-3 text-gray-600 dark:text-slate-300">{s.opens_count}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className="w-20 bg-gray-200 dark:bg-slate-700 rounded-full h-1.5 flex-shrink-0">
                            <div
                              className="bg-red-500 h-1.5 rounded-full"
                              style={{ width: `${Math.min(s.open_rate, 100)}%` }}
                            />
                          </div>
                          {getRateBadge(s.open_rate)}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={async () => {
                            if (!confirm('¿Eliminar este suscriptor? Esta acción no se puede deshacer.')) return
                            setDeleting(true)
                            try {
                              const r = await api.post('/subscribers/bulk-delete/', { ids: [s.id] })
                              setResult(r.data.deleted)
                              setSelected((prev) => { const n = new Set(prev); n.delete(s.id); return n })
                              await load()
                              if (onDeleted) onDeleted()
                            } catch (err) {
                              alert(err.response?.data?.detail || 'Error al eliminar')
                            } finally {
                              setDeleting(false)
                            }
                          }}
                          aria-label={`Eliminar ${s.email}`}
                          className="text-gray-400 hover:text-red-600"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
              <div className="px-4 py-3 border-t border-gray-100 dark:border-slate-700 flex items-center justify-between bg-gray-50 dark:bg-slate-700">
                <span className="text-sm text-gray-500 dark:text-slate-400">
                  {selected.size} seleccionados de {items.length}
                </span>
                <button
                  className="btn-primary bg-red-600 hover:bg-red-700 disabled:opacity-50"
                  disabled={selected.size === 0 || deleting}
                  onClick={handleDelete}
                >
                  <Trash2 className="h-4 w-4" />
                  {deleting ? 'Eliminando…' : `Eliminar seleccionados (${selected.size})`}
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

const PAGE_SIZE_OPTIONS = [50, 100, 200]

export default function Subscribers() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [adding, setAdding] = useState(false)
  const [form, setForm] = useState({ email: '', first_name: '', last_name: '' })
  const [importResult, setImportResult] = useState(null)
  const [tab, setTab] = useState('list')
  const fileRef = useRef(null)

  // Grupos.
  const [groups, setGroups] = useState([])
  const [selectedGroup, setSelectedGroup] = useState('')  // ''=todos los grupos
  const [showGroups, setShowGroups] = useState(false)

  // Paginación + búsqueda (server-side).
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(50)
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(1)
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')

  async function loadGroups() {
    try {
      const r = await api.get('/subscribers/groups/')
      setGroups(r.data || [])
    } catch { /* noop */ }
  }

  useEffect(() => { loadGroups() }, [])

  async function load(opts = {}) {
    const p = opts.page ?? page
    const ps = opts.pageSize ?? pageSize
    const s = opts.search ?? search
    const g = opts.group ?? selectedGroup
    setLoading(true)
    try {
      const params = new URLSearchParams({ page: String(p), page_size: String(ps) })
      if (s) params.set('search', s)
      if (g) params.set('list', g)
      const r = await api.get(`/subscribers/all/?${params.toString()}`)
      setItems(r.data.results)
      setTotal(r.data.count ?? 0)
      setTotalPages(r.data.total_pages ?? r.data.num_pages ?? 1)
      // El backend puede clampar la página fuera de rango; reflejamos la real.
      if (r.data.page && r.data.page !== p) setPage(r.data.page)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load({ page, pageSize, search, group: selectedGroup }) }, [page, pageSize, search, selectedGroup])

  function goToPage(p) {
    const clamped = Math.max(1, Math.min(p, totalPages))
    setPage(clamped)
  }

  function handleSearchSubmit(e) {
    e.preventDefault()
    setPage(1)
    setSearch(searchInput.trim())
  }

  function changePageSize(e) {
    setPageSize(Number(e.target.value))
    setPage(1)
  }

  async function handleAdd(e) {
    e.preventDefault()
    setAdding(true)
    try {
      await api.post('/subscribers/add/', { ...form, list: selectedGroup || undefined })
      setForm({ email: '', first_name: '', last_name: '' })
      setShowAdd(false)
      await load()
      await loadGroups()
    } catch (err) {
      alert(err.response?.data?.detail || 'Error añadiendo suscriptor')
    } finally {
      setAdding(false)
    }
  }

  async function handleDelete(id) {
    if (!confirm('¿Eliminar suscriptor?')) return
    await api.delete(`/subscribers/${id}/`)
    await load()
    await loadGroups()
  }

  async function handleGroupsChanged() {
    await loadGroups()
    // Si el grupo filtrado ya no existe, vuelve a "todos".
    try {
      const r = await api.get('/subscribers/groups/')
      const ids = (r.data || []).map((g) => String(g.id))
      if (selectedGroup && !ids.includes(String(selectedGroup))) {
        setSelectedGroup('')
      } else {
        await load()
      }
    } catch { /* noop */ }
  }

  async function handleImport(e) {
    const file = e.target.files?.[0]
    if (!file) return
    const text = await file.text()
    try {
      const r = await api.post('/subscribers/import/', { csv_data: text, list: selectedGroup || undefined })
      setImportResult(r.data)
      await load()
      await loadGroups()
    } catch (err) {
      alert(err.response?.data?.detail || 'Error importando')
    } finally {
      e.target.value = ''
    }
  }

  function handleExport() {
    const qs = selectedGroup ? `?list=${selectedGroup}` : ''
    api.get(`/subscribers/export/${qs}`, { responseType: 'blob' })
      .then((r) => {
        const url = URL.createObjectURL(r.data)
        const a = document.createElement('a')
        a.href = url
        a.download = 'subscribers.csv'
        a.click()
        URL.revokeObjectURL(url)
      })
  }

  return (
    <div className="space-y-6 max-w-6xl">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Suscriptores</h1>
          <p className="text-sm text-gray-500 dark:text-slate-400">Miembros de tu newsletter ({total})</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn-secondary" onClick={() => setShowGroups(true)}>
            <Layers className="h-4 w-4" /> Grupos
          </button>
          <button className="btn-secondary" onClick={handleExport}>
            <Download className="h-4 w-4" /> Exportar CSV
          </button>
          <button className="btn-secondary" onClick={() => fileRef.current?.click()}>
            <Upload className="h-4 w-4" /> Importar CSV / TXT
          </button>
          <input type="file" accept=".csv,.txt,text/csv,text/plain" ref={fileRef} onChange={handleImport} className="hidden" />
          <button className="btn-primary" onClick={() => setShowAdd(true)}>
            <Plus className="h-4 w-4" /> Añadir
          </button>
        </div>
      </div>

      <div className="flex gap-1 border-b border-gray-200 dark:border-slate-700">
        <button
          onClick={() => setTab('list')}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
            tab === 'list'
              ? 'border-primary-600 dark:border-primary-400 text-primary-700 dark:text-white'
              : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-slate-400 dark:hover:text-slate-200'
          }`}
        >
          Lista
        </button>
        <button
          onClick={() => setTab('cleanup')}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
            tab === 'cleanup'
              ? 'border-primary-600 dark:border-primary-400 text-primary-700 dark:text-white'
              : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-slate-400 dark:hover:text-slate-200'
          }`}
        >
          Limpieza
        </button>
      </div>

      {importResult && (
        <div className="card p-4 bg-green-50 border-green-200 dark:bg-green-900/30 dark:border-green-800 flex items-center justify-between">
          <span className="text-sm text-green-800 dark:text-green-400">
            Importados: {importResult.imported} · Omitidos: {importResult.skipped}
          </span>
          <button aria-label="Cerrar notificación de importación" onClick={() => setImportResult(null)} className="text-green-700 dark:text-green-400">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {tab === 'list' && (
        <>
        <form onSubmit={handleSearchSubmit} className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 dark:text-slate-500" />
            <input
              type="search"
              className="input pl-9"
              placeholder="Buscar por email o nombre…"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
            />
          </div>
          <div className="flex items-center gap-2">
            <button type="submit" className="btn-secondary">Buscar</button>
            {search && (
              <button
                type="button"
                className="btn-secondary"
                onClick={() => { setSearchInput(''); setSearch(''); setPage(1) }}
              >
                Limpiar
              </button>
            )}
            <label htmlFor="group-filter" className="text-sm text-gray-500 dark:text-slate-400 ml-1">Grupo</label>
            <select
              id="group-filter"
              className="input w-auto"
              value={selectedGroup}
              onChange={(e) => { setSelectedGroup(e.target.value); setPage(1) }}
            >
              <option value="">Todos los grupos</option>
              {groups.map((g) => (
                <option key={g.id} value={g.id}>{g.name} ({g.subscriber_count})</option>
              ))}
            </select>
            <label htmlFor="page-size" className="text-sm text-gray-500 dark:text-slate-400 ml-1">Por página</label>
            <select id="page-size" className="input w-auto" value={pageSize} onChange={changePageSize}>
              {PAGE_SIZE_OPTIONS.map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </div>
        </form>
        <div className="card overflow-hidden">
          {loading ? (
            <div role="status" aria-live="polite" className="p-8 text-center text-gray-500 dark:text-slate-400">Cargando…</div>
          ) : items.length === 0 ? (
            <div className="p-12 text-center">
              <Users className="mx-auto mb-3 h-12 w-12 text-gray-300 dark:text-slate-600" />
              <p className="text-gray-500 dark:text-slate-400 mb-4">Aún no hay suscriptores.</p>
              <p className="text-xs text-gray-500 dark:text-slate-400">
                Sube un CSV o TXT con columnas <code>email,first_name,last_name</code> o añade uno a mano.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[500px]" aria-label="Lista de suscriptores">
              <thead className="bg-gray-50 dark:bg-slate-700 text-gray-500 dark:text-slate-400 text-xs uppercase">
                <tr>
                  <th scope="col" className="px-4 py-3 text-left">Email</th>
                  <th scope="col" className="px-4 py-3 text-left">Nombre</th>
                  <th scope="col" className="px-4 py-3 text-left">Estado</th>
                  <th scope="col" className="px-4 py-3 text-left">Alta</th>
                  <th scope="col" className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-slate-700">
                {items.map((s) => (
                  <tr key={s.id}>
                    <td className="px-4 py-3 font-medium text-gray-900 dark:text-slate-100">{s.email}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-slate-300">{[s.first_name, s.last_name].filter(Boolean).join(' ') || '—'}</td>
                    <td className="px-4 py-3">
                      <span className={`badge ${
                        s.status === 'active'
                          ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                          : s.status === 'bounced' || s.status === 'complained'
                            ? 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400'
                            : 'bg-gray-100 text-gray-600 dark:bg-slate-700 dark:text-slate-300'
                      }`}>
                        {STATUS_LABELS[s.status] || s.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500 dark:text-slate-400">{new Date(s.subscribed_at).toLocaleDateString()}</td>
                    <td className="px-4 py-3 text-right">
                      <button
                        aria-label={`Eliminar suscriptor ${s.email}`}
                        onClick={() => handleDelete(s.id)}
                        className="text-gray-400 hover:text-red-600"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          )}

          {!loading && items.length > 0 && (
            <div className="px-4 py-3 border-t border-gray-100 dark:border-slate-700 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between bg-gray-50 dark:bg-slate-700">
              <span className="text-sm text-gray-500 dark:text-slate-400">
                Página {page} de {totalPages} · {total} suscriptores
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  className="btn-secondary disabled:opacity-50"
                  disabled={page <= 1 || loading}
                  onClick={() => goToPage(page - 1)}
                >
                  <ChevronLeft className="h-4 w-4" /> Anterior
                </button>
                <button
                  type="button"
                  className="btn-secondary disabled:opacity-50"
                  disabled={page >= totalPages || loading}
                  onClick={() => goToPage(page + 1)}
                >
                  Siguiente <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}
        </div>
        </>
      )}

      {tab === 'cleanup' && <CleanupTab onDeleted={load} />}

      {showGroups && (
        <GroupsModal
          groups={groups}
          onClose={() => setShowGroups(false)}
          onChanged={handleGroupsChanged}
        />
      )}

      {showAdd && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => setShowAdd(false)}
        >
          <form
            role="dialog"
            aria-modal="true"
            aria-labelledby="add-subscriber-title"
            onSubmit={handleAdd}
            className="card w-full max-w-md flex flex-col max-h-[90vh] overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 dark:border-slate-700 flex-shrink-0">
              <h2 id="add-subscriber-title" className="text-lg font-semibold">Nuevo suscriptor</h2>
              <button type="button" aria-label="Cerrar" onClick={() => setShowAdd(false)} className="text-gray-400 hover:text-gray-600 dark:text-slate-400 dark:hover:text-slate-200">
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
              <div>
                <label htmlFor="sub-email" className="label">Email *</label>
                <input
                  id="sub-email"
                  autoFocus
                  className="input"
                  type="email"
                  required
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label htmlFor="sub-first-name" className="label">Nombre</label>
                  <input
                    id="sub-first-name"
                    className="input"
                    value={form.first_name}
                    onChange={(e) => setForm({ ...form, first_name: e.target.value })}
                  />
                </div>
                <div>
                  <label htmlFor="sub-last-name" className="label">Apellido</label>
                  <input
                    id="sub-last-name"
                    className="input"
                    value={form.last_name}
                    onChange={(e) => setForm({ ...form, last_name: e.target.value })}
                  />
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-2 px-6 py-4 border-t border-gray-100 dark:border-slate-700 flex-shrink-0">
              <button type="button" className="btn-secondary" onClick={() => setShowAdd(false)}>Cancelar</button>
              <button className="btn-primary" disabled={adding}>{adding ? 'Guardando…' : 'Guardar'}</button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
