import { useEffect, useState, useCallback } from 'react'
import { Activity, CheckCircle2, XCircle, Send, RefreshCw, Clock, Pause, Play, Users, Search, X, Mail, MailWarning, Eye, ChevronLeft, ChevronRight, BadgeCheck } from 'lucide-react'
import api from '../api'
import { wrapEmailHtml } from '../emailPreview.js'

const fmtDateTime = (s) =>
  s ? new Date(s).toLocaleString('es-ES', { dateStyle: 'short', timeStyle: 'short' }) : '—'

// Números grandes con separador de miles (695854 → "695.854").
const fmtNum = (n) => (typeof n === 'number' ? n.toLocaleString('es-ES') : n ?? 0)

function RecipientBadge({ status }) {
  if (status === 'ok')
    return <span className="badge bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">Entregado</span>
  if (status === 'error')
    return <span className="badge bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400">Error</span>
  return <span className="badge bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">Pendiente</span>
}

// Modal con buscador y pestañas para ver a quién le ha llegado un correo
// (recibidos / pendientes / con error) de una campaña concreta.
function RecipientsModal({ campaign, onClose }) {
  const [filter, setFilter] = useState('received')
  const [q, setQ] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    const t = setTimeout(() => {
      api
        .get(`/analytics/deliverability/campaign/${campaign.id}/recipients/`, { params: { q, filter } })
        .then((r) => { if (!cancelled) setData(r.data) })
        .catch(() => { if (!cancelled) setData(null) })
        .finally(() => { if (!cancelled) setLoading(false) })
    }, q ? 300 : 0) // pequeño debounce al teclear
    return () => { cancelled = true; clearTimeout(t) }
  }, [campaign.id, q, filter])

  const counts = data?.counts || { received: 0, error: 0, pending: 0 }
  const tabs = [
    { key: 'received', label: 'Recibidos', count: counts.received, always: true },
    { key: 'pending', label: 'Pendientes', count: counts.pending },
    { key: 'error', label: 'Con error', count: counts.error },
  ].filter((t) => t.always || t.count > 0 || t.key === filter)

  const results = data?.results || []

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="recipients-title"
        className="card w-full max-w-2xl flex flex-col max-h-[90vh] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 dark:border-slate-700 flex-shrink-0">
          <div className="min-w-0">
            <h2 id="recipients-title" className="text-lg font-semibold truncate flex items-center gap-2">
              <Users className="h-5 w-5 text-primary-600 dark:text-primary-400 flex-shrink-0" />
              <span className="truncate">{campaign.name}</span>
            </h2>
            <p className="text-xs text-gray-500 dark:text-slate-400 truncate">Destinatarios de este correo</p>
          </div>
          <button type="button" aria-label="Cerrar" onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:text-slate-400 dark:hover:text-slate-200 flex-shrink-0">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="px-6 pt-4 flex-shrink-0 space-y-3">
          <div className="flex flex-wrap gap-2" role="tablist">
            {tabs.map((t) => (
              <button
                key={t.key}
                role="tab"
                aria-selected={filter === t.key}
                onClick={() => setFilter(t.key)}
                className={`text-sm px-3 py-1.5 rounded-lg border transition-colors ${
                  filter === t.key
                    ? 'bg-primary-600 text-white border-primary-600 dark:text-white'
                    : 'border-gray-200 dark:border-slate-700 text-gray-600 dark:text-slate-300 hover:bg-gray-50 dark:hover:bg-slate-800'
                }`}
              >
                {t.label} ({t.count})
              </button>
            ))}
          </div>
          <div className="relative">
            <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-slate-500" />
            <input
              autoFocus
              className="input pl-9"
              type="search"
              placeholder="Buscar por email o nombre…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              aria-label="Buscar destinatario"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          {loading ? (
            <p className="text-sm text-gray-500 dark:text-slate-400" role="status">Cargando…</p>
          ) : results.length === 0 ? (
            <p className="text-sm text-gray-500 dark:text-slate-400">
              {q ? 'Ningún destinatario coincide con la búsqueda.' : 'No hay destinatarios en esta categoría.'}
            </p>
          ) : (
            <ul className="divide-y divide-gray-100 dark:divide-slate-700">
              {results.map((r, i) => (
                <li key={`${r.email}-${i}`} className="py-2.5 flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 text-sm font-medium text-gray-800 dark:text-slate-200">
                      <Mail className="h-3.5 w-3.5 text-gray-400 dark:text-slate-500 flex-shrink-0" />
                      <span className="truncate">{r.email}</span>
                    </div>
                    {r.name && <div className="text-xs text-gray-500 dark:text-slate-400 ml-5">{r.name}</div>}
                    {r.status === 'error' && r.error_reason && (
                      <div className="text-xs text-rose-600 dark:text-rose-400 mt-0.5 break-words">{r.error_reason}</div>
                    )}
                    {r.status === 'ok' && r.sent_at && (
                      <div className="text-xs text-gray-400 dark:text-slate-500 mt-0.5">Enviado {fmtDateTime(r.sent_at)}</div>
                    )}
                  </div>
                  <RecipientBadge status={r.status} />
                </li>
              ))}
            </ul>
          )}
          {data?.truncated && (
            <p className="text-xs text-gray-400 dark:text-slate-500 mt-3">
              Mostrando los primeros {data.limit}. Afina la búsqueda para encontrar destinatarios concretos.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

// Modal con la vista previa del correo TAL CUAL lo reciben los suscriptores
// (HTML personalizado + pie de baja), renderizado en un iframe aislado.
function PreviewModal({ campaign, onClose }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true); setError(false)
    api
      .get(`/campaigns/${campaign.id}/preview/`)
      .then((r) => { if (!cancelled) setData(r.data) })
      .catch(() => { if (!cancelled) setError(true) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [campaign.id])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-2 sm:p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="preview-title"
        className="card w-full max-w-3xl flex flex-col max-h-[92vh] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-3 px-4 sm:px-6 py-3 sm:py-4 border-b border-gray-100 dark:border-slate-700 flex-shrink-0">
          <div className="min-w-0">
            <h2 id="preview-title" className="text-base sm:text-lg font-semibold truncate flex items-center gap-2">
              <Eye className="h-5 w-5 text-primary-600 dark:text-primary-400 flex-shrink-0" />
              <span className="truncate">{data?.subject || campaign.name}</span>
            </h2>
            <p className="text-xs text-gray-500 dark:text-slate-400 truncate">
              {data?.from_name ? `${data.from_name} · ` : ''}
              {data?.from_email || 'Vista previa del correo'}
            </p>
          </div>
          <button type="button" aria-label="Cerrar" onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:text-slate-400 dark:hover:text-slate-200 flex-shrink-0">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="flex-1 overflow-hidden bg-white">
          {loading ? (
            <p className="p-6 text-sm text-gray-500" role="status">Cargando vista previa…</p>
          ) : error ? (
            <p className="p-6 text-sm text-red-600" role="alert">No se pudo cargar la vista previa del correo.</p>
          ) : (
            <iframe
              title="Vista previa del correo"
              srcDoc={wrapEmailHtml(data.html)}
              sandbox=""
              className="w-full h-full min-h-[55vh] sm:min-h-[60vh] border-0 bg-white"
            />
          )}
        </div>
      </div>
    </div>
  )
}

function Kpi({ icon: Icon, label, value, sub, tone }) {
  const toneCls = tone === 'ok'
    ? 'text-emerald-600 dark:text-emerald-400'
    : tone === 'err'
      ? 'text-rose-600 dark:text-rose-400'
      : 'text-primary-600 dark:text-primary-400'
  return (
    <div className="card p-5">
      <div className="flex items-center gap-2 text-gray-500 dark:text-slate-400 text-sm">
        {Icon && <Icon className={`h-4 w-4 ${toneCls}`} />} {label}
      </div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
      {sub && <div className="text-xs text-gray-400 dark:text-slate-500 mt-0.5">{sub}</div>}
    </div>
  )
}

export default function Deliverability() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [retrying, setRetrying] = useState(false)
  const [msg, setMsg] = useState(null)
  const [openCampaign, setOpenCampaign] = useState(null) // campaña cuyos destinatarios se ven
  const [previewCampaign, setPreviewCampaign] = useState(null) // campaña cuyo correo se previsualiza
  const [sentPage, setSentPage] = useState(1) // paginación de "Correos enviados"

  const load = useCallback(() => {
    api.get('/analytics/deliverability/', { params: { sent_page: sentPage, sent_page_size: 10 } })
      .then((r) => setData(r.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [sentPage])

  useEffect(() => {
    load()
    const id = setInterval(load, 15000) // refresco en vivo del progreso
    return () => clearInterval(id)
  }, [load])

  async function pauseResume(id, action) {
    try {
      await api.post(`/campaigns/${id}/${action}/`)
      load()
    } catch (err) {
      setMsg(err.response?.data?.detail || 'No se pudo cambiar el estado del envío.')
    }
  }

  async function retry() {
    if (!confirm('¿Reintentar todos los envíos fallidos? Se reencolarán y se enviarán poco a poco al ritmo configurado.')) return
    setRetrying(true)
    setMsg(null)
    try {
      const r = await api.post('/analytics/retry-failed/')
      setMsg(`Reencolados ${r.data.requeued} envío(s) en ${r.data.campaigns} campaña(s). Se reenviarán al ritmo configurado.`)
      load()
    } catch {
      setMsg('No se pudieron reencolar los envíos. Inténtalo de nuevo.')
    } finally {
      setRetrying(false)
    }
  }

  if (loading) return <div role="status" className="text-gray-500 dark:text-slate-400">Cargando…</div>
  if (!data) return <div role="alert" className="text-red-600">Error al cargar.</div>

  const fmtEta = (h) =>
    !h || h <= 0 ? '—' : h < 1 ? `${Math.round(h * 60)} min` : h < 48 ? `${h} h` : `${Math.round(h / 24)} días`

  return (
    <div className="max-w-5xl space-y-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Entregabilidad</h1>
          <p className="text-sm text-gray-500 dark:text-slate-400">
            Éxito de los envíos, errores y progreso del envío en tiempo real.
          </p>
        </div>
        <button onClick={load} className="btn-secondary text-sm flex items-center gap-1">
          <RefreshCw className="h-4 w-4" /> Actualizar
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Kpi icon={CheckCircle2} tone="ok" label="Aceptados por el servidor" value={`${data.success_rate}%`} sub={`${fmtNum(data.ok)} aceptados`} />
        <Kpi icon={XCircle} tone="err" label="Errores de envío" value={`${data.error_rate}%`} sub={`${fmtNum(data.errored)} con error`} />
        <Kpi icon={MailWarning} tone="err" label="Tasa de rebote" value={`${data.bounce_rate ?? 0}%`} sub={`${fmtNum(data.total_bounces ?? 0)} rebotes (${fmtNum(data.hard_bounces ?? 0)} duros)`} />
        <Kpi icon={BadgeCheck} tone="ok" label="Entrega neta" value={`${data.net_delivery_rate ?? 0}%`} sub={`${fmtNum(data.net_delivered ?? 0)} sin error ni rebote duro`} />
        <Kpi icon={Send} label="Total enviados" value={fmtNum(data.total_sends)} />
        <Kpi icon={Activity} label="Ritmo actual" value={`${fmtNum(data.rate_per_hour)}/h`} sub="configurable en Ajustes" />
      </div>
      <p className="text-xs text-gray-400 dark:text-slate-500 -mt-3">
        <strong>"Aceptados por el servidor"</strong> = correos que tu servidor SMTP admitió para envío sin error;
        no garantiza que lleguen a la bandeja de entrada (por eso puede rozar el 100 %). <strong>"Entrega
        neta"</strong> resta los rebotes duros (fallo permanente) de esa cifra — los blandos no restan, suelen
        ser temporales. La entregabilidad real la reflejan sobre todo los <strong>rebotes</strong> y las
        <strong> aperturas</strong> de cada campaña.
      </p>

      <div className="card p-5">
        <h2 className="font-semibold mb-3 flex items-center gap-2">
          <Send className="h-4 w-4 text-primary-600 dark:text-primary-400" /> Envíos en curso
        </h2>
        {data.sending.length === 0 ? (
          <p className="text-sm text-gray-500 dark:text-slate-400">No hay campañas enviándose ni pausadas ahora mismo.</p>
        ) : (
          <div className="space-y-4">
            {data.sending.map((c) => (
              <div key={c.id}>
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1.5 sm:gap-2 text-sm mb-1">
                  <span className="font-medium text-gray-800 dark:text-slate-200 truncate flex items-center gap-2 min-w-0">
                    {c.name}
                    {c.status === 'paused' && (
                      <span className="badge bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">Pausada</span>
                    )}
                  </span>
                  <div className="flex items-center flex-wrap gap-2 sm:flex-shrink-0">
                    <span className="text-gray-500 dark:text-slate-400">{c.sent}/{c.total} · {c.progress}%</span>
                    <button onClick={() => setPreviewCampaign({ id: c.id, name: c.name })} aria-label="Ver correo" title="Ver cómo se recibe el correo" className="btn-secondary text-xs py-1 px-2 flex items-center gap-1">
                      <Eye className="h-3.5 w-3.5" /> Ver
                    </button>
                    <button onClick={() => setOpenCampaign({ id: c.id, name: c.name })} className="btn-secondary text-xs py-1 px-2 flex items-center gap-1">
                      <Users className="h-3.5 w-3.5" /> Destinatarios
                    </button>
                    {c.status === 'sending' ? (
                      <button onClick={() => pauseResume(c.id, 'pause')} className="btn-secondary text-xs py-1 px-2 flex items-center gap-1">
                        <Pause className="h-3.5 w-3.5" /> Pausar
                      </button>
                    ) : (
                      <button onClick={() => pauseResume(c.id, 'resume')} className="btn-primary text-xs py-1 px-2 flex items-center gap-1">
                        <Play className="h-3.5 w-3.5" /> Reanudar
                      </button>
                    )}
                  </div>
                </div>
                <div className="h-2.5 rounded-full bg-gray-100 dark:bg-slate-700 overflow-hidden">
                  <div className={`h-full transition-all ${c.status === 'paused' ? 'bg-amber-400' : 'bg-emerald-500'}`} style={{ width: `${Math.min(c.progress, 100)}%` }} />
                </div>
                <div className="text-xs text-gray-400 dark:text-slate-500 mt-1">{c.pending} pendientes</div>
              </div>
            ))}
            <div className="text-xs text-gray-500 dark:text-slate-400 flex items-center gap-1.5 flex-wrap pt-2 border-t border-gray-100 dark:border-slate-700">
              <Clock className="h-3.5 w-3.5" />
              {data.total_pending} pendientes en total · ritmo {data.rate_per_hour}/h · tiempo estimado restante:&nbsp;
              <strong>{fmtEta(data.eta_hours)}</strong>
            </div>
          </div>
        )}
      </div>

      <div className="card p-5">
        <h2 className="font-semibold mb-3 flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 text-emerald-500" /> Correos enviados
        </h2>
        {!data.sent || data.sent.length === 0 ? (
          <p className="text-sm text-gray-500 dark:text-slate-400">Todavía no has enviado ningún correo.</p>
        ) : (
          <>
            <ul className="divide-y divide-gray-100 dark:divide-slate-700">
              {data.sent.map((c) => (
                <li key={c.id} className="py-3 flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="font-medium text-gray-800 dark:text-slate-200 truncate">{c.name}</div>
                    <div className="text-xs text-gray-500 dark:text-slate-400 truncate">
                      {c.sends} destinatario{c.sends === 1 ? '' : 's'} · {fmtDateTime(c.sent_at)}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <button
                      onClick={() => setPreviewCampaign({ id: c.id, name: c.name })}
                      aria-label="Ver correo"
                      title="Ver cómo se recibe el correo"
                      className="btn-secondary text-xs py-1 px-2 flex items-center gap-1"
                    >
                      <Eye className="h-3.5 w-3.5" /> <span className="hidden sm:inline">Ver</span>
                    </button>
                    <button
                      onClick={() => setOpenCampaign({ id: c.id, name: c.name })}
                      aria-label="Destinatarios"
                      title="Ver destinatarios"
                      className="btn-secondary text-xs py-1 px-2 flex items-center gap-1"
                    >
                      <Users className="h-3.5 w-3.5" /> <span className="hidden sm:inline">Destinatarios</span>
                    </button>
                  </div>
                </li>
              ))}
            </ul>
            {data.sent_pages > 1 && (
              <div className="flex items-center justify-between gap-2 pt-3 mt-1 border-t border-gray-100 dark:border-slate-700">
                <span className="text-xs text-gray-500 dark:text-slate-400">
                  {data.sent_total} correos · pág. {data.sent_page}/{data.sent_pages}
                </span>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setSentPage((p) => Math.max(1, p - 1))}
                    disabled={data.sent_page <= 1}
                    aria-label="Página anterior"
                    className="btn-secondary text-xs py-1 px-2 flex items-center gap-1 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <ChevronLeft className="h-3.5 w-3.5" /> <span className="hidden sm:inline">Anterior</span>
                  </button>
                  <button
                    onClick={() => setSentPage((p) => Math.min(data.sent_pages, p + 1))}
                    disabled={data.sent_page >= data.sent_pages}
                    aria-label="Página siguiente"
                    className="btn-secondary text-xs py-1 px-2 flex items-center gap-1 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <span className="hidden sm:inline">Siguiente</span> <ChevronRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      <div className="card p-5">
        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
          <h2 className="font-semibold flex items-center gap-2">
            <XCircle className="h-4 w-4 text-rose-500" /> Envíos fallidos
          </h2>
          {data.errored > 0 && (
            <button onClick={retry} disabled={retrying} className="btn-primary text-sm flex items-center gap-1">
              <RefreshCw className={`h-4 w-4 ${retrying ? 'animate-spin' : ''}`} />
              {retrying ? 'Reencolando…' : `Reintentar fallidos (${data.errored})`}
            </button>
          )}
        </div>
        {msg && (
          <div className="text-sm mb-3 text-primary-700 dark:text-primary-300 bg-primary-50 dark:bg-primary-900/30 border border-primary-200 dark:border-primary-800 rounded-lg p-3">
            {msg}
          </div>
        )}
        {data.errored === 0 ? (
          <p className="text-sm text-gray-500 dark:text-slate-400">No hay envíos fallidos. 🎉</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" aria-label="Motivos de error">
              <thead className="text-gray-500 dark:text-slate-400 text-xs uppercase">
                <tr>
                  <th scope="col" className="text-left py-2">Motivo del error</th>
                  <th scope="col" className="text-right py-2">Nº</th>
                  <th scope="col" className="text-right py-2">%</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-slate-700">
                {data.top_errors.map((e, i) => (
                  <tr key={i}>
                    <td className="py-2 pr-3 text-gray-700 dark:text-slate-300 break-words">{e.reason}</td>
                    <td className="py-2 text-right text-gray-700 dark:text-slate-300">{e.count}</td>
                    <td className="py-2 text-right text-gray-500 dark:text-slate-400">{e.rate}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-xs text-gray-400 dark:text-slate-500 mt-3">
              Al reintentar, los fallidos vuelven a la cola y se reenvían poco a poco al ritmo configurado. Los que sí
              llegaron no se reenvían.
            </p>
          </div>
        )}
      </div>

      <div className="card p-5">
        <h2 className="font-semibold mb-3 flex items-center gap-2">
          <MailWarning className="h-4 w-4 text-rose-500" /> Rebotes (rechazados tras la entrega)
        </h2>
        <p className="text-xs text-gray-400 dark:text-slate-500 mb-3">
          A diferencia de "Envíos fallidos" (el propio servidor rechazó el correo al enviarlo), esto son
          rebotes reales devueltos por el proveedor destino (buzón lleno, dirección inexistente, bloqueo
          antispam…). Los duros dan de baja automáticamente al suscriptor para no seguir enviándole.
        </p>
        {!data.total_bounces ? (
          <p className="text-sm text-gray-500 dark:text-slate-400">No hay rebotes registrados.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" aria-label="Motivos de rebote">
              <thead className="text-gray-500 dark:text-slate-400 text-xs uppercase">
                <tr>
                  <th scope="col" className="text-left py-2">Motivo del rebote</th>
                  <th scope="col" className="text-right py-2">Nº</th>
                  <th scope="col" className="text-right py-2">%</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-slate-700">
                {(data.top_bounce_reasons || []).map((e, i) => (
                  <tr key={i}>
                    <td className="py-2 pr-3 text-gray-700 dark:text-slate-300 break-words">{e.reason}</td>
                    <td className="py-2 text-right text-gray-700 dark:text-slate-300">{e.count}</td>
                    <td className="py-2 text-right text-gray-500 dark:text-slate-400">{e.rate}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-xs text-gray-400 dark:text-slate-500 mt-3">
              {data.hard_bounces} duros · {data.soft_bounces} blandos
            </p>
          </div>
        )}
      </div>

      {openCampaign && (
        <RecipientsModal campaign={openCampaign} onClose={() => setOpenCampaign(null)} />
      )}
      {previewCampaign && (
        <PreviewModal campaign={previewCampaign} onClose={() => setPreviewCampaign(null)} />
      )}
    </div>
  )
}
