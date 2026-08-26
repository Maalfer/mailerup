import { useEffect, useRef, useState, Fragment } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Users, Mail, MailOpen, MousePointerClick, UserMinus, UserPlus,
  TrendingUp, BarChart3, ArrowLeft, ExternalLink, Zap, ChevronDown, ChevronRight, MailWarning,
} from 'lucide-react'
import api from '../api'
import Pager from '../components/Pager'

const CAMP_PAGE_SIZE = 15

export default function Analytics() {
  const [searchParams, setSearchParams] = useSearchParams()
  const queryCampaign = searchParams.get('campaign')
  const _tab = searchParams.get('tab')
  const queryTab = _tab === 'automations' ? 'automations' : _tab === 'subscriptions' ? 'subscriptions' : 'campaigns'
  const [data, setData] = useState(null)
  const [autoData, setAutoData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [campPage, setCampPage] = useState(1)
  const tab = queryTab
  const [selected, setSelected] = useState(queryCampaign || null)
  const [detail, setDetail] = useState(null)

  useEffect(() => {
    Promise.all([
      api.get('/analytics/overview/').then((r) => setData(r.data)),
      api.get('/analytics/automations/overview/').then((r) => setAutoData(r.data)).catch(() => setAutoData({ automations: [] })),
    ]).finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    setSelected(queryCampaign || null)
  }, [queryCampaign])

  useEffect(() => {
    if (!selected) { setDetail(null); return }
    setDetail(null)
    api.get(`/analytics/campaign/${selected}/`).then((r) => setDetail(r.data))
  }, [selected])

  function back() {
    setSearchParams({})
    setSelected(null)
  }

  if (loading) return <div role="status" aria-live="polite" className="text-gray-500 dark:text-slate-400">Cargando…</div>
  if (!data) return <div role="alert" className="text-red-600">Error al cargar.</div>

  if (selected) {
    return <CampaignDetail data={detail} onBack={back} />
  }

  function switchTab(t) {
    if (t === 'campaigns') setSearchParams({})
    else setSearchParams({ tab: t })
  }

  return (
    <div className="max-w-6xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Analíticas</h1>
        <p className="text-sm text-gray-500 dark:text-slate-400">Aperturas, clics y comportamiento de tus suscriptores.</p>
      </div>

      <div className="flex gap-1 border-b border-gray-200 dark:border-slate-700" role="tablist">
        {[
          { id: 'campaigns', label: 'Campañas', icon: BarChart3 },
          { id: 'automations', label: 'Automatizaciones', icon: Zap },
          { id: 'subscriptions', label: 'Inscripciones', icon: UserPlus },
        ].map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            role="tab"
            aria-selected={tab === id}
            onClick={() => switchTab(id)}
            className={`inline-flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === id
                ? 'border-primary-600 text-primary-700 dark:border-primary-400 dark:text-white'
                : 'border-transparent text-gray-500 hover:text-gray-800 dark:text-slate-400 dark:hover:text-slate-200'
            }`}
          >
            <Icon className="h-4 w-4" /> {label}
          </button>
        ))}
      </div>

      {tab === 'automations' ? (
        <AutomationsPanel data={autoData} />
      ) : tab === 'subscriptions' ? (
        <SubscriptionsPanel />
      ) : (
      <>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Kpi icon={Users}            label="Suscriptores activos" value={data.total_subscribers} />
        <Kpi icon={Mail}             label="Correos enviados"     value={data.total_sends} />
        <Kpi icon={MailOpen}         label="Apertura media"       value={`${data.avg_open_rate}%`}    sub={`${data.total_opens} aperturas únicas`} />
        <Kpi icon={MousePointerClick} label="Clic medio"           value={`${data.avg_click_rate}%`}   sub={`${data.total_clicks} clics únicos`} />
        <Kpi icon={BarChart3}        label="Campañas enviadas"    value={data.sent_campaigns} sub={`${data.total_campaigns} totales`} />
        <Kpi icon={UserMinus}        label="Bajas totales"        value={data.total_unsubscribes} sub={`${data.total_unsubscribed} en la lista`} />
        <Kpi icon={MailWarning}      label="Rebotes totales"      value={data.total_bounces} sub={`${data.total_bounced} suscriptores rebotados`} />
        <Kpi icon={TrendingUp}       label="Aperturas totales"    value={data.total_opens} />
        <Kpi icon={MousePointerClick} label="Clics totales"        value={data.total_clicks} />
      </div>

      <div className="card overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-200 dark:border-slate-700 flex items-center justify-between">
          <h2 className="font-semibold">Rendimiento por campaña</h2>
          <span className="text-xs text-gray-500 dark:text-slate-400">Haz clic en una campaña para ver el detalle</span>
        </div>
        {data.campaigns.length === 0 ? (
          <div className="p-12 text-center text-gray-500 dark:text-slate-400">
            Aún no hay campañas enviadas. Envía una para ver métricas aquí.
          </div>
        ) : (() => {
          const totalPages = Math.max(1, Math.ceil(data.campaigns.length / CAMP_PAGE_SIZE))
          const safePage = Math.min(campPage, totalPages)
          const pageItems = data.campaigns.slice((safePage - 1) * CAMP_PAGE_SIZE, safePage * CAMP_PAGE_SIZE)
          return (
          <>
          <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[700px]" aria-label="Rendimiento por campaña">
            <thead className="bg-gray-50 dark:bg-slate-700 text-gray-500 dark:text-slate-400 text-xs uppercase">
              <tr>
                <th scope="col" className="px-4 py-3 text-left">Campaña</th>
                <th scope="col" className="px-4 py-3 text-right">Enviados</th>
                <th scope="col" className="px-4 py-3 text-right">Aperturas</th>
                <th scope="col" className="px-4 py-3 text-right">Clics</th>
                <th scope="col" className="px-4 py-3 text-right">Bajas</th>
                <th scope="col" className="px-4 py-3 text-right">Tasa apertura</th>
                <th scope="col" className="px-4 py-3 text-right">Tasa clics</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-slate-700">
              {pageItems.map((c) => (
                <tr key={c.id} className="hover:bg-gray-50 dark:hover:bg-slate-700 cursor-pointer"
                    onClick={() => setSearchParams({ campaign: c.id })}>
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900 dark:text-slate-100">{c.name}</div>
                    <div className="text-xs text-gray-500 dark:text-slate-400">{c.subject}</div>
                  </td>
                  <td className="px-4 py-3 text-right text-gray-700 dark:text-slate-300">{c.sends}</td>
                  <td className="px-4 py-3 text-right text-gray-700 dark:text-slate-300">{c.opens}</td>
                  <td className="px-4 py-3 text-right text-gray-700 dark:text-slate-300">{c.clicks}</td>
                  <td className="px-4 py-3 text-right text-gray-700 dark:text-slate-300">{c.unsubscribes}</td>
                  <td className="px-4 py-3 text-right">
                    <RateBar value={c.open_rate} color="emerald" />
                  </td>
                  <td className="px-4 py-3 text-right">
                    <RateBar value={c.click_rate} color="indigo" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
          <Pager page={safePage} totalPages={totalPages} total={data.campaigns.length} unit="campañas" onPage={setCampPage} className="px-5 pb-3" />
          </>
          )
        })()}
      </div>
      </>
      )}
    </div>
  )
}

function AutomationsPanel({ data }) {
  const [open, setOpen] = useState(null)
  const [detail, setDetail] = useState(null)

  useEffect(() => {
    if (!open) { setDetail(null); return }
    setDetail(null)
    api.get(`/analytics/automation/${open}/`).then((r) => setDetail(r.data))
  }, [open])

  if (!data) return <div role="status" aria-live="polite" className="text-gray-500 dark:text-slate-400">Cargando…</div>

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Kpi icon={Zap}              label="Automatizaciones"   value={data.total_automations} sub={`${data.active_automations} activas`} />
        <Kpi icon={Mail}             label="Correos enviados"   value={data.total_sends} />
        <Kpi icon={MailOpen}         label="Apertura media"     value={`${data.avg_open_rate}%`}  sub={`${data.total_opens} aperturas únicas`} />
        <Kpi icon={MousePointerClick} label="Clic medio"         value={`${data.avg_click_rate}%`} sub={`${data.total_clicks} clics únicos`} />
      </div>

      <div className="card overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-200 dark:border-slate-700 flex items-center justify-between">
          <h2 className="font-semibold">Rendimiento por automatización</h2>
          <span className="text-xs text-gray-500 dark:text-slate-400">Haz clic para ver el desglose por paso</span>
        </div>
        {data.automations.length === 0 ? (
          <div className="p-12 text-center text-gray-500 dark:text-slate-400">
            Aún no hay automatizaciones con envíos. Las métricas aparecerán aquí cuando se envíen correos.
          </div>
        ) : (
          <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[760px]" aria-label="Rendimiento por automatización">
            <thead className="bg-gray-50 dark:bg-slate-700 text-gray-500 dark:text-slate-400 text-xs uppercase">
              <tr>
                <th scope="col" className="px-4 py-3 text-left">Automatización</th>
                <th scope="col" className="px-4 py-3 text-right">Enrolados</th>
                <th scope="col" className="px-4 py-3 text-right">Enviados</th>
                <th scope="col" className="px-4 py-3 text-right">Aperturas</th>
                <th scope="col" className="px-4 py-3 text-right">Clics</th>
                <th scope="col" className="px-4 py-3 text-right">Bajas</th>
                <th scope="col" className="px-4 py-3 text-right">Tasa apertura</th>
                <th scope="col" className="px-4 py-3 text-right">Tasa clics</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-slate-700">
              {data.automations.map((a) => {
                const isOpen = open === a.id
                return (
                  <Fragment key={a.id}>
                    <tr className="hover:bg-gray-50 dark:hover:bg-slate-700 cursor-pointer"
                        onClick={() => setOpen(isOpen ? null : a.id)}>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1.5">
                          {isOpen ? <ChevronDown className="h-4 w-4 text-gray-400" /> : <ChevronRight className="h-4 w-4 text-gray-400" />}
                          <div>
                            <div className="font-medium text-gray-900 dark:text-slate-100 flex items-center gap-2">
                              {a.name}
                              {!a.is_active && <span className="badge bg-gray-100 text-gray-500 dark:bg-slate-700 dark:text-slate-400 text-xs">inactiva</span>}
                            </div>
                            <div className="text-xs text-gray-500 dark:text-slate-400">{a.steps_count} paso{a.steps_count === 1 ? '' : 's'}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right text-gray-700 dark:text-slate-300">{a.enrolled}</td>
                      <td className="px-4 py-3 text-right text-gray-700 dark:text-slate-300">{a.sends}</td>
                      <td className="px-4 py-3 text-right text-gray-700 dark:text-slate-300">{a.opens}</td>
                      <td className="px-4 py-3 text-right text-gray-700 dark:text-slate-300">{a.clicks}</td>
                      <td className="px-4 py-3 text-right text-gray-700 dark:text-slate-300">{a.unsubscribes}</td>
                      <td className="px-4 py-3 text-right"><RateBar value={a.open_rate} color="emerald" /></td>
                      <td className="px-4 py-3 text-right"><RateBar value={a.click_rate} color="indigo" /></td>
                    </tr>
                    {isOpen && (
                      <tr>
                        <td colSpan={8} className="bg-gray-50/60 dark:bg-slate-800/40 px-4 py-4">
                          <AutomationSteps detail={detail} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
          </div>
        )}
      </div>
    </div>
  )
}

function AutomationSteps({ detail }) {
  if (!detail) return <div role="status" aria-live="polite" className="text-sm text-gray-500 dark:text-slate-400 px-2">Cargando desglose…</div>
  if (!detail.steps || detail.steps.length === 0) {
    return <div className="text-sm text-gray-500 dark:text-slate-400 px-2">Esta automatización no tiene pasos.</div>
  }
  return (
    <div className="rounded-lg border border-gray-200 dark:border-slate-700 overflow-hidden">
      <table className="w-full text-sm" aria-label="Desglose por paso">
        <thead className="bg-gray-100 dark:bg-slate-700 text-gray-500 dark:text-slate-400 text-xs uppercase">
          <tr>
            <th scope="col" className="px-4 py-2 text-left">Paso</th>
            <th scope="col" className="px-4 py-2 text-right">Enviados</th>
            <th scope="col" className="px-4 py-2 text-right">Aperturas</th>
            <th scope="col" className="px-4 py-2 text-right">Clics</th>
            <th scope="col" className="px-4 py-2 text-right">Tasa apertura</th>
            <th scope="col" className="px-4 py-2 text-right">Tasa clics</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 dark:divide-slate-700 bg-white dark:bg-slate-800">
          {detail.steps.map((s) => (
            <tr key={s.id}>
              <td className="px-4 py-2.5">
                <div className="font-medium text-gray-900 dark:text-slate-100">Paso {s.order + 1}</div>
                <div className="text-xs text-gray-500 dark:text-slate-400 truncate max-w-xs">{s.subject}</div>
              </td>
              <td className="px-4 py-2.5 text-right text-gray-700 dark:text-slate-300">{s.sends}</td>
              <td className="px-4 py-2.5 text-right text-gray-700 dark:text-slate-300">{s.opens}</td>
              <td className="px-4 py-2.5 text-right text-gray-700 dark:text-slate-300">{s.clicks}</td>
              <td className="px-4 py-2.5 text-right"><RateBar value={s.open_rate} color="emerald" /></td>
              <td className="px-4 py-2.5 text-right"><RateBar value={s.click_rate} color="indigo" /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function AbComparison({ ab_stats }) {
  if (!ab_stats) {
    return (
      <div className="card p-6 text-center text-gray-400 dark:text-slate-500 text-sm">
        Aún no hay datos de envío para el test A/B.
      </div>
    )
  }

  const a = ab_stats.A
  const b = ab_stats.B
  const aWinsOpen = a.open_rate > b.open_rate
  const bWinsOpen = b.open_rate > a.open_rate
  const aWinsClick = a.click_rate > b.click_rate
  const bWinsClick = b.click_rate > a.click_rate

  return (
    <div className="card overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-200 dark:border-slate-700 flex items-center gap-2">
        <span className="text-base font-semibold">Comparación A/B</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-gray-100 dark:divide-slate-700">
        {[
          { label: 'Variante A', stats: a, winsOpen: aWinsOpen, winsClick: aWinsClick },
          { label: 'Variante B', stats: b, winsOpen: bWinsOpen, winsClick: bWinsClick },
        ].map(({ label, stats, winsOpen, winsClick }) => (
          <div key={label} className="p-5 space-y-3">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-gray-700 dark:text-slate-200">{label}</span>
              {(winsOpen || winsClick) && (
                <span className="badge bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 text-xs">Ganador</span>
              )}
            </div>
            <p className="text-sm text-gray-500 dark:text-slate-400 italic truncate">&ldquo;{stats.subject}&rdquo;</p>
            <dl className="text-sm space-y-1.5">
              <div className="flex justify-between border-b border-gray-100 dark:border-slate-700 py-1">
                <dt className="text-gray-500 dark:text-slate-400">Enviados</dt>
                <dd className="font-medium text-gray-900 dark:text-slate-100">{stats.sends}</dd>
              </div>
              <div className="flex justify-between border-b border-gray-100 dark:border-slate-700 py-1 items-center">
                <dt className="text-gray-500 dark:text-slate-400">Aperturas</dt>
                <dd className="flex items-center gap-1.5 font-medium text-gray-900 dark:text-slate-100">
                  {stats.opens}
                  {winsOpen && <span className="text-xs text-green-600 dark:text-green-400 font-semibold">{stats.open_rate}%</span>}
                  {!winsOpen && <span className="text-xs text-gray-400 dark:text-slate-500">{stats.open_rate}%</span>}
                </dd>
              </div>
              <div className="flex justify-between border-b border-gray-100 dark:border-slate-700 py-1 items-center">
                <dt className="text-gray-500 dark:text-slate-400">Tasa apertura</dt>
                <dd className={`font-semibold ${winsOpen ? 'text-green-700 dark:text-green-400' : 'text-gray-700 dark:text-slate-300'}`}>{stats.open_rate}%</dd>
              </div>
              <div className="flex justify-between border-b border-gray-100 dark:border-slate-700 py-1">
                <dt className="text-gray-500 dark:text-slate-400">Clics</dt>
                <dd className="font-medium text-gray-900 dark:text-slate-100">{stats.clicks}</dd>
              </div>
              <div className="flex justify-between py-1 items-center">
                <dt className="text-gray-500 dark:text-slate-400">Tasa clic</dt>
                <dd className={`font-semibold ${winsClick ? 'text-green-700 dark:text-green-400' : 'text-gray-700 dark:text-slate-300'}`}>{stats.click_rate}%</dd>
              </div>
            </dl>
          </div>
        ))}
      </div>
    </div>
  )
}

function CampaignDetail({ data, onBack }) {
  if (!data) return <div role="status" aria-live="polite" className="text-gray-500 dark:text-slate-400">Cargando…</div>
  return (
    <div className="max-w-6xl space-y-6">
      <button onClick={onBack} className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-900 dark:text-slate-400 dark:hover:text-slate-100">
        <ArrowLeft className="h-4 w-4" /> Todas las campañas
      </button>
      <div>
        <h1 className="text-2xl font-semibold">{data.name}</h1>
        <p className="text-sm text-gray-500 dark:text-slate-400">{data.subject}</p>
      </div>

      {data.ab_enabled && (
        <AbComparison ab_stats={data.ab_stats} />
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Kpi icon={Mail}              label="Enviados"           value={data.sends} sub={data.errored ? `${data.delivered} entregados · ${data.errored} con error` : undefined} />
        <Kpi icon={MailOpen}          label="Tasa de apertura"   value={`${data.open_rate}%`} sub={`${data.opens} de ${data.delivered}`} />
        <Kpi icon={MousePointerClick} label="Tasa de clic"       value={`${data.click_rate}%`} sub={`${data.clicks} de ${data.delivered}`} />
        <Kpi icon={UserMinus}         label="Bajas"              value={`${data.unsubscribe_rate}%`} sub={`${data.unsubscribes} de ${data.delivered}`} />
        <Kpi icon={MailWarning}       label="Rebotes"            value={`${data.bounce_rate ?? 0}%`} sub={`${data.hard_bounces ?? 0} duros · ${data.soft_bounces ?? 0} blandos`} />
        <Kpi icon={Users}             label="Sin abrir"          value={data.not_opened} />
        <Kpi icon={Users}             label="Sin hacer clic"     value={data.not_clicked} />
        <Kpi icon={TrendingUp}        label="CTR de aperturas"   value={`${data.click_through_open_rate}%`}
             sub="Clics / aperturas" />
        <Kpi icon={BarChart3}         label="Aperturas únicas"   value={data.opens} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-200 dark:border-slate-700">
            <h2 className="font-semibold">Enlaces más clicados</h2>
          </div>
          {data.top_links.length === 0 ? (
            <div className="p-8 text-center text-gray-500 dark:text-slate-400">Sin clics todavía.</div>
          ) : (
            <ul className="divide-y divide-gray-100 dark:divide-slate-700">
              {data.top_links.map((l, i) => (
                <li key={i} className="px-5 py-3 flex items-center justify-between gap-3">
                  <a href={l.url} target="_blank" rel="noreferrer"
                     className="text-sm text-primary-700 dark:text-primary-400 hover:underline truncate flex items-center gap-1">
                    <ExternalLink className="h-3.5 w-3.5 flex-shrink-0" />
                    <span className="truncate">{l.url}</span>
                  </a>
                  <span className="text-sm font-semibold text-gray-700 dark:text-slate-300">{l.clicks} clic{l.clicks === 1 ? '' : 's'}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="card overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-200 dark:border-slate-700">
            <h2 className="font-semibold">Destinatarios ({data.recipients.length})</h2>
          </div>
          <div className="max-h-96 overflow-y-auto">
            <table className="w-full text-sm" aria-label="Destinatarios de la campaña">
              <thead className="bg-gray-50 dark:bg-slate-700 text-gray-500 dark:text-slate-400 text-xs uppercase sticky top-0">
                <tr>
                  <th scope="col" className="px-4 py-2 text-left">Email</th>
                  <th scope="col" className="px-4 py-2 text-center">Abierto</th>
                  <th scope="col" className="px-4 py-2 text-center">Clic</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-slate-700">
                {data.recipients.map((r, i) => (
                  <tr key={i}>
                    <td className="px-4 py-2 truncate">{r.email}</td>
                    <td className="px-4 py-2 text-center">{r.opened ? '✅' : '—'}</td>
                    <td className="px-4 py-2 text-center">{r.clicked ? '✅' : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}

function Kpi({ icon: Icon, label, value, sub }) {
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between">
        <span className="text-xs uppercase font-medium text-gray-500 dark:text-slate-400">{label}</span>
        <Icon className="h-4 w-4 text-gray-400 dark:text-slate-500" />
      </div>
      <div className="mt-2 text-2xl font-semibold text-gray-900 dark:text-slate-100">{value}</div>
      {sub && <div className="mt-1 text-xs text-gray-500 dark:text-slate-400">{sub}</div>}
    </div>
  )
}

function RateBar({ value, color }) {
  const colors = {
    emerald: 'bg-emerald-500',
    indigo: 'bg-indigo-500',
  }
  const safe = Number(value) || 0   // evita NaN%/undefined% si la API no manda número
  return (
    <div className="flex items-center justify-end gap-2 min-w-[100px]">
      <div className="flex-1 max-w-[80px] bg-gray-100 dark:bg-slate-700 rounded-full h-1.5 overflow-hidden">
        <div className={`h-full ${colors[color]}`} style={{ width: `${Math.min(safe, 100)}%` }} />
      </div>
      <span className="text-sm font-semibold text-gray-700 dark:text-slate-300 w-12 text-right">{safe}%</span>
    </div>
  )
}

// ─── Pestaña "Inscripciones": altas y bajas en el tiempo ──────────────────────
function SubscriptionsPanel() {
  const [period, setPeriod] = useState('day')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.get(`/analytics/subscriptions/timeseries/?period=${period}`)
      .then((r) => setData(r.data))
      .catch(() => setData({ buckets: [], total_altas: 0, total_bajas: 0 }))
      .finally(() => setLoading(false))
  }, [period])

  const buckets = data?.buckets || []
  const net = (data?.total_altas || 0) - (data?.total_bajas || 0)
  const periodLabel = period === 'day' ? 'día' : period === 'week' ? 'semana' : 'mes'

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-sm text-gray-500 dark:text-slate-400">Agrupar por:</span>
        {[['day', 'Día'], ['week', 'Semana'], ['month', 'Mes']].map(([k, label]) => (
          <button
            key={k}
            onClick={() => setPeriod(k)}
            aria-pressed={period === k}
            className={`px-3 py-1.5 text-sm rounded-md border transition-colors ${
              period === k
                ? 'bg-primary-600 text-white border-primary-600'
                : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50 dark:bg-slate-700 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-600'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Kpi icon={UserPlus} label="Altas (total)" value={data?.total_altas ?? 0} />
        <Kpi icon={UserMinus} label="Bajas (total)" value={data?.total_bajas ?? 0} />
        <Kpi icon={TrendingUp} label="Crecimiento neto" value={net} sub="altas − bajas" />
      </div>

      <div className="card p-5">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
          <h3 className="font-semibold text-sm">Altas y bajas por {periodLabel}</h3>
          <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-slate-400">
            <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-emerald-500" /> Altas</span>
            <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-rose-500" /> Bajas</span>
          </div>
        </div>
        {loading ? (
          <div role="status" className="p-8 text-center text-gray-500 dark:text-slate-400">Cargando…</div>
        ) : buckets.length === 0 ? (
          <div className="p-8 text-center text-gray-500 dark:text-slate-400">Aún no hay datos de altas/bajas en este periodo.</div>
        ) : (
          <SubsChart buckets={buckets} />
        )}
      </div>
    </div>
  )
}

function SubsChart({ buckets }) {
  const data = buckets.slice(-24)   // últimos 24 periodos para legibilidad
  const max = Math.max(1, ...data.map((b) => Math.max(b.altas, b.bajas)))
  const H = 180, barW = 8, gap = 4, groupW = barW * 2 + gap, step = groupW + 16
  const W = Math.max(data.length * step + 30, 280)
  const yOf = (v) => H - (v / max) * H
  const fmt = (d) => (d || '').slice(5).replace('-', '/') || d

  const containerRef = useRef(null)
  // { index, x, y, width } en coordenadas del contenedor (no del SVG), para que
  // el tooltip HTML se posicione bien aunque el gráfico esté scrolleado
  // horizontalmente (overflow-x-auto). El <title> nativo de SVG que había antes
  // depende del navegador/SO, tarda en aparecer o directamente no sale con barras
  // finas de pocos px: por eso aquí se dibuja el tooltip a mano.
  const [hover, setHover] = useState(null)

  const updateHover = (index, evt) => {
    const rect = containerRef.current?.getBoundingClientRect()
    if (!rect) return
    setHover({ index, x: evt.clientX - rect.left, y: evt.clientY - rect.top, width: rect.width })
  }
  const clearHover = (index) => setHover((h) => (h?.index === index ? null : h))

  const hoveredBucket = hover ? data[hover.index] : null
  const tooltipLeft = hover ? Math.min(Math.max(hover.x, 64), Math.max(hover.width - 64, 64)) : 0

  return (
    <div ref={containerRef} className="relative overflow-x-auto">
      <svg width={W} height={H + 46} role="img" aria-label="Gráfico de altas y bajas por periodo">
        <line x1="0" y1={H} x2={W} y2={H} className="stroke-gray-200 dark:stroke-slate-700" strokeWidth="1" />
        {data.map((b, i) => {
          const x = 16 + i * step
          const isHover = hover?.index === i
          return (
            <g key={b.date}>
              <rect x={x} y={yOf(b.altas)} width={barW} height={H - yOf(b.altas)} rx="1.5"
                    className={isHover ? 'fill-emerald-400' : 'fill-emerald-500'} pointerEvents="none" />
              <rect x={x + barW + gap} y={yOf(b.bajas)} width={barW} height={H - yOf(b.bajas)} rx="1.5"
                    className={isHover ? 'fill-rose-400' : 'fill-rose-500'} pointerEvents="none" />
              {/* Zona de hover ancha e invisible: cubre todo el alto del grupo,
                  no solo la barra, para que sea fácil apuntar incluso cuando
                  altas o bajas valen 0 (barra de 0px de alto). */}
              <rect
                x={x - gap} y={0} width={groupW + gap * 2} height={H}
                fill="transparent"
                onMouseEnter={(e) => updateHover(i, e)}
                onMouseMove={(e) => updateHover(i, e)}
                onMouseLeave={() => clearHover(i)}
                style={{ cursor: 'crosshair' }}
              />
              {isHover && (
                <line x1={x + groupW / 2} y1="0" x2={x + groupW / 2} y2={H}
                      className="stroke-gray-300 dark:stroke-slate-600" strokeWidth="1" strokeDasharray="3 3" pointerEvents="none" />
              )}
              <text
                x={x + groupW / 2}
                y={H + 16}
                textAnchor="end"
                transform={`rotate(-45 ${x + groupW / 2} ${H + 16})`}
                className={isHover ? 'fill-gray-600 dark:fill-slate-300' : 'fill-gray-400 dark:fill-slate-500'}
                style={{ fontSize: 9 }}
              >
                {fmt(b.date)}
              </text>
            </g>
          )
        })}
      </svg>
      {hoveredBucket && (
        <div
          className="pointer-events-none absolute z-10 -translate-x-1/2 whitespace-nowrap rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs shadow-lg dark:border-slate-600 dark:bg-slate-800"
          style={{ left: tooltipLeft, top: Math.max(hover.y - 64, 0) }}
        >
          <div className="mb-1 font-semibold text-gray-700 dark:text-slate-200">{hoveredBucket.date}</div>
          <div className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400">
            <span className="h-2 w-2 rounded-sm bg-emerald-500" /> {hoveredBucket.altas} {hoveredBucket.altas === 1 ? 'alta' : 'altas'}
          </div>
          <div className="flex items-center gap-1.5 text-rose-600 dark:text-rose-400">
            <span className="h-2 w-2 rounded-sm bg-rose-500" /> {hoveredBucket.bajas} {hoveredBucket.bajas === 1 ? 'baja' : 'bajas'}
          </div>
        </div>
      )}
    </div>
  )
}
