import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, FileText, Send, Trash2, Copy, CalendarClock, Pause, Play } from 'lucide-react'
import api, { fetchAll } from '../api'
import Pager from '../components/Pager'

const PAGE_SIZE = 20

const TABS = [
  { key: 'drafts',    label: 'Borradores',         statuses: ['draft'],                       icon: FileText },
  { key: 'outbox',    label: 'Bandeja de salida',  statuses: ['sending', 'paused', 'sent', 'failed'], icon: Send },
  { key: 'scheduled', label: 'Programados',        statuses: ['scheduled'],                   icon: CalendarClock },
]

export default function Campaigns() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('drafts')
  const [page, setPage] = useState(1)
  const nav = useNavigate()

  async function load() {
    setLoading(true)
    try {
      // El endpoint pagina (DRF). fetchAll recorre todas las páginas para que los
      // contadores de las pestañas reflejen el total real; la lista se pagina
      // luego en cliente por pestaña (PAGE_SIZE) para no mostrar cientos de filas.
      setItems(await fetchAll('/campaigns/'))
    } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const current = TABS.find((t) => t.key === tab)
  const filtered = items.filter((c) => current.statuses.includes(c.status))
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const safePage = Math.min(page, totalPages)
  const pageItems = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE)

  async function handleDelete(id) {
    if (!confirm('¿Eliminar campaña?')) return
    await api.delete(`/campaigns/${id}/`)
    await load()
  }
  async function handleDuplicate(id) {
    await api.post(`/campaigns/${id}/duplicate/`)
    await load()
  }
  async function handlePause(id) {
    try {
      await api.post(`/campaigns/${id}/pause/`)
      await load()
    } catch (err) {
      alert(err.response?.data?.detail || 'Error al pausar')
    }
  }
  async function handleResume(id) {
    try {
      await api.post(`/campaigns/${id}/resume/`)
      await load()
    } catch (err) {
      alert(err.response?.data?.detail || 'Error al reanudar')
    }
  }

  function statusBadge(s) {
    const map = {
      draft:     ['bg-gray-100 text-gray-700 dark:bg-slate-700 dark:text-slate-300', 'Borrador'],
      scheduled: ['bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400', 'Programada'],
      sending:   ['bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400', 'Enviando'],
      sent:      ['bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400', 'Enviada'],
      failed:    ['bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400', 'Fallida'],
      paused:    ['bg-gray-200 text-gray-700 dark:bg-slate-700 dark:text-slate-300', 'Pausada'],
    }
    const [cls, label] = map[s] || ['bg-gray-100 text-gray-700 dark:bg-slate-700 dark:text-slate-300', s]
    return <span className={`badge ${cls}`}>{label}</span>
  }

  return (
    <div className="space-y-6 max-w-6xl">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Campañas</h1>
          <p className="text-sm text-gray-500 dark:text-slate-400">Crea y envía correos a tu newsletter</p>
        </div>
        <button className="btn-primary" onClick={() => nav('/campaigns/new')}>
          <Plus className="h-4 w-4" /> Nueva campaña
        </button>
      </div>

      <div className="flex gap-1 border-b border-gray-200 dark:border-slate-700">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => { setTab(t.key); setPage(1) }}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
              tab === t.key
                ? 'border-primary-600 dark:border-primary-400 text-primary-700 dark:text-white'
                : 'border-transparent text-gray-500 hover:text-gray-800 dark:text-slate-400 dark:hover:text-slate-200'
            }`}
          >
            <t.icon className="h-4 w-4" /> {t.label}
            <span className="ml-1 text-xs text-gray-400 dark:text-slate-500">
              ({items.filter((c) => t.statuses.includes(c.status)).length})
            </span>
          </button>
        ))}
      </div>

      <div className="card overflow-hidden">
        {loading ? (
          <div role="status" aria-live="polite" className="p-8 text-center text-gray-500 dark:text-slate-400">Cargando…</div>
        ) : filtered.length === 0 ? (
          <div className="p-12 text-center text-gray-500 dark:text-slate-400">
            {tab === 'drafts'
              ? 'No tienes borradores.'
              : tab === 'scheduled'
              ? 'No hay correos programados.'
              : 'No hay correos enviados todavía.'}
          </div>
        ) : (
          <>
          <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[600px]" aria-label="Lista de campañas">
            <thead className="bg-gray-50 dark:bg-slate-700 text-gray-500 dark:text-slate-400 text-xs uppercase">
              <tr>
                <th scope="col" className="px-4 py-3 text-left">Nombre</th>
                <th scope="col" className="px-4 py-3 text-left">Asunto</th>
                <th scope="col" className="px-4 py-3 text-left">Estado</th>
                <th scope="col" className="px-4 py-3 text-left">
                  {tab === 'drafts' ? 'Creada' : tab === 'scheduled' ? 'Programada para' : 'Enviada'}
                </th>
                <th scope="col" className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-slate-700">
              {pageItems.map((c) => (
                <tr key={c.id} className="hover:bg-gray-50 dark:hover:bg-slate-700">
                  <td className="px-4 py-3 font-medium text-gray-900 dark:text-slate-100">
                    <button
                      onClick={() => nav(
                        c.status === 'sent'
                          ? `/analytics?campaign=${c.id}`
                          : `/campaigns/${c.id}/edit`
                      )}
                      className="hover:underline"
                    >
                      {c.name}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-gray-600 dark:text-slate-300">{c.subject}</td>
                  <td className="px-4 py-3">{statusBadge(c.status)}</td>
                  <td className="px-4 py-3 text-gray-500 dark:text-slate-400">
                    {tab === 'scheduled' && c.scheduled_at
                      ? new Date(c.scheduled_at).toLocaleString()
                      : (c.sent_at || c.created_at) && new Date(c.sent_at || c.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right space-x-2">
                    {c.status === 'sending' && (
                      <button
                        aria-label={`Pausar campaña ${c.name}`}
                        onClick={() => handlePause(c.id)}
                        className="text-gray-400 hover:text-yellow-600 dark:hover:text-yellow-400"
                        title="Pausar envío"
                      >
                        <Pause className="h-4 w-4 inline" />
                      </button>
                    )}
                    {c.status === 'paused' && (
                      <button
                        aria-label={`Reanudar campaña ${c.name}`}
                        onClick={() => handleResume(c.id)}
                        className="text-gray-400 hover:text-green-600 dark:hover:text-green-400"
                        title="Reanudar envío"
                      >
                        <Play className="h-4 w-4 inline" />
                      </button>
                    )}
                    <button
                      aria-label={`Duplicar campaña ${c.name}`}
                      onClick={() => handleDuplicate(c.id)}
                      className="text-gray-400 hover:text-primary-600 dark:hover:text-primary-400"
                    >
                      <Copy className="h-4 w-4 inline" />
                    </button>
                    <button
                      aria-label={`Eliminar campaña ${c.name}`}
                      onClick={() => handleDelete(c.id)}
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
          <Pager page={safePage} totalPages={totalPages} total={filtered.length} unit="campañas" onPage={setPage} className="px-4 pb-3" />
          </>
        )}
      </div>
    </div>
  )
}
