import { useEffect, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Zap, Plus, Pencil, Trash2, ChevronLeft, ChevronUp, ChevronDown, X, Send } from 'lucide-react'
import api, { fetchAll } from '../api'

function formatDelay(amount, unit) {
  if (!amount || amount === 0) return 'Inmediato'
  if (unit === 'minutes') return amount === 1 ? '1 minuto después' : `${amount} minutos después`
  if (unit === 'hours') return amount === 1 ? '1 hora después' : `${amount} horas después`
  if (unit === 'days') return amount === 1 ? '1 día después' : `${amount} días después`
  return `${amount} ${unit} después`
}

// ─── Modal: crear/editar automatización ──────────────────────────────────────
function AutomationModal({ initial, forms, onClose, onSaved }) {
  const isEdit = !!initial?.id
  const [form, setForm] = useState({
    name: initial?.name || '',
    form: initial?.form || '',
    is_active: initial?.is_active !== false,
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  function set(k, v) {
    setForm((prev) => ({ ...prev, [k]: v }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    const payload = { ...form, form: form.form || null }
    try {
      if (isEdit) {
        await api.patch(`/automations/${initial.id}/`, payload)
      } else {
        await api.post('/automations/', payload)
      }
      onSaved()
    } catch (err) {
      setError(
        err.response?.data
          ? JSON.stringify(err.response.data)
          : 'Error al guardar la automatización'
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <form
        role="dialog"
        aria-modal="true"
        aria-labelledby="auto-modal-title"
        onSubmit={handleSubmit}
        className="card w-full max-w-md flex flex-col max-h-[90vh] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 dark:border-slate-700 flex-shrink-0">
          <h2 id="auto-modal-title" className="text-lg font-semibold">
            {isEdit ? 'Editar automatización' : 'Nueva automatización'}
          </h2>
          <button
            type="button"
            aria-label="Cerrar modal"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 dark:text-slate-400 dark:hover:text-slate-200"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {error && (
            <div role="alert" className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg p-3">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="auto-name" className="label">Nombre de la automatización *</label>
            <input
              id="auto-name"
              className="input"
              required
              value={form.name}
              onChange={(e) => set('name', e.target.value)}
            />
          </div>

          <div>
            <label htmlFor="auto-form" className="label">Formulario de entrada</label>
            <select
              id="auto-form"
              className="input"
              value={form.form}
              onChange={(e) => set('form', e.target.value)}
            >
              <option value="">Sin formulario (manual)</option>
              {forms.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name}
                </option>
              ))}
            </select>
          </div>

          <label className="flex items-center gap-2 cursor-pointer text-sm">
            <input
              type="checkbox"
              className="rounded border-gray-300"
              checked={form.is_active}
              onChange={(e) => set('is_active', e.target.checked)}
            />
            Automatización activa
          </label>
        </div>

        <div className="flex justify-end gap-2 px-6 py-4 border-t border-gray-100 dark:border-slate-700 flex-shrink-0">
          <button type="button" className="btn-secondary" onClick={onClose}>
            Cancelar
          </button>
          <button className="btn-primary" disabled={saving}>
            {saving ? 'Guardando…' : 'Guardar'}
          </button>
        </div>
      </form>
    </div>
  )
}

// ─── Vista de pasos ───────────────────────────────────────────────────────────
function StepsView({ automation, onBack }) {
  const nav = useNavigate()
  const [steps, setSteps] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  async function loadSteps() {
    setLoading(true)
    setError(null)
    try {
      const r = await api.get(`/automations/${automation.id}/steps/`)
      const data = r.data.results || r.data
      setSteps([...data].sort((a, b) => a.order - b.order))
    } catch {
      setError('No se pudieron cargar los pasos.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadSteps() }, [automation.id])

  async function handleDeleteStep(stepId) {
    if (!confirm('¿Eliminar este paso?')) return
    try {
      await api.delete(`/automations/${automation.id}/steps/${stepId}/`)
      await loadSteps()
    } catch {
      setError('No se pudo eliminar el paso.')
    }
  }

  async function handleReorder(step, direction) {
    const sorted = [...steps].sort((a, b) => a.order - b.order)
    const idx = sorted.findIndex((s) => s.id === step.id)
    const targetIdx = direction === 'up' ? idx - 1 : idx + 1
    if (targetIdx < 0 || targetIdx >= sorted.length) return

    const target = sorted[targetIdx]
    const orderA = step.order
    const orderB = target.order
    try {
      await Promise.all([
        api.patch(`/automations/${automation.id}/steps/${step.id}/`, { order: orderB }),
        api.patch(`/automations/${automation.id}/steps/${target.id}/`, { order: orderA }),
      ])
      await loadSteps()
    } catch {
      setError('No se pudo reordenar el paso.')
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            aria-label="Volver a la lista de automatizaciones"
            onClick={onBack}
            className="btn-secondary flex items-center gap-1"
          >
            <ChevronLeft className="h-4 w-4" /> Volver
          </button>
          <h2 className="text-lg font-semibold">
            Pasos de: <span className="text-primary-700 dark:text-primary-300">{automation.name}</span>
          </h2>
        </div>
        <button
          className="btn-primary"
          onClick={() => nav(`/automations/${automation.id}/steps/new`)}
        >
          <Plus className="h-4 w-4" /> Añadir paso
        </button>
      </div>

      {error && (
        <div role="alert" className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg p-3 flex items-center justify-between">
          {error}
          <button aria-label="Cerrar error" onClick={() => setError(null)} className="text-red-400 hover:text-red-600 ml-3">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {loading ? (
        <div role="status" aria-live="polite" className="p-8 text-center text-gray-500 dark:text-slate-400">
          Cargando pasos…
        </div>
      ) : steps.length === 0 ? (
        <div className="card p-10 text-center">
          <p className="text-gray-500 dark:text-slate-400 mb-3">Esta automatización no tiene pasos todavía.</p>
          <button
            className="btn-primary"
            onClick={() => nav(`/automations/${automation.id}/steps/new`)}
          >
            <Plus className="h-4 w-4" /> Añadir primer paso
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {steps.map((step, idx) => (
            <div key={step.id} className="card p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-1 flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold text-gray-800 dark:text-slate-200">
                      Paso {idx + 1}
                    </span>
                    <span className="text-gray-400 dark:text-slate-500 text-xs">·</span>
                    <span className="text-xs text-gray-500 dark:text-slate-400">
                      {formatDelay(step.delay_amount, step.delay_unit)}
                      {step.delay_hours_total !== undefined && step.delay_amount > 0 && step.delay_unit !== 'minutes' && (
                        <span className="ml-1 text-gray-400 dark:text-slate-500">({step.delay_hours_total}h total)</span>
                      )}
                    </span>
                    <span className="text-gray-400 dark:text-slate-500 text-xs">·</span>
                    <span
                      title="Personas a las que ya se les ha enviado el correo de este paso"
                      className="badge bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300 gap-1"
                    >
                      <Send className="h-3 w-3" />
                      {step.sent_count ?? 0} {(step.sent_count ?? 0) === 1 ? 'enviado' : 'enviados'}
                    </span>
                  </div>
                  <p className="text-sm font-medium text-gray-900 dark:text-slate-100 truncate">
                    Asunto: &quot;{step.subject}&quot;
                  </p>
                  {(step.from_name || step.from_email) && (
                    <p className="text-xs text-gray-500 dark:text-slate-400">
                      Remitente:{' '}
                      {step.from_name && <span>{step.from_name}</span>}
                      {step.from_name && step.from_email && ' '}
                      {step.from_email && <span>&lt;{step.from_email}&gt;</span>}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-1 flex-shrink-0">
                  <button
                    aria-label="Mover paso arriba"
                    onClick={() => handleReorder(step, 'up')}
                    disabled={idx === 0}
                    className="p-1.5 text-gray-400 hover:text-gray-700 disabled:opacity-30"
                  >
                    <ChevronUp className="h-4 w-4" />
                  </button>
                  <button
                    aria-label="Mover paso abajo"
                    onClick={() => handleReorder(step, 'down')}
                    disabled={idx === steps.length - 1}
                    className="p-1.5 text-gray-400 hover:text-gray-700 disabled:opacity-30"
                  >
                    <ChevronDown className="h-4 w-4" />
                  </button>
                  <button
                    aria-label={`Editar paso ${idx + 1}`}
                    onClick={() => nav(`/automations/${automation.id}/steps/${step.id}/edit`)}
                    className="btn-secondary text-xs py-1 px-2 flex items-center gap-1"
                  >
                    <Pencil className="h-3.5 w-3.5" /> Editar
                  </button>
                  <button
                    aria-label={`Eliminar paso ${idx + 1}`}
                    onClick={() => handleDeleteStep(step.id)}
                    className="text-gray-400 hover:text-red-600 p-1.5"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Página principal ─────────────────────────────────────────────────────────
export default function Automations() {
  const location = useLocation()
  const [automations, setAutomations] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [forms, setForms] = useState([])
  const [selected, setSelected] = useState(null)
  const [showCreate, setShowCreate] = useState(false)
  const [editAuto, setEditAuto] = useState(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const [autos, formsAll] = await Promise.all([
        fetchAll('/automations/'),
        fetchAll('/forms/'),
      ])
      setAutomations(autos)
      setForms(formsAll)
    } catch {
      setError('No se pudieron cargar las automatizaciones.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  // Cuando se vuelve del editor con openAutomation en el state, expandir esa automatización
  useEffect(() => {
    if (location.state?.openAutomation && automations.length > 0) {
      const auto = automations.find((a) => String(a.id) === String(location.state.openAutomation))
      if (auto) setSelected(auto)
    }
  }, [automations])

  async function handleDelete(id) {
    if (!confirm('¿Eliminar esta automatización y todos sus pasos?')) return
    try {
      await api.delete(`/automations/${id}/`)
      if (selected?.id === id) setSelected(null)
      await load()
    } catch {
      setError('No se pudo eliminar la automatización.')
    }
  }

  function handleSaved() {
    setShowCreate(false)
    setEditAuto(null)
    load()
  }

  function getFormName(formId) {
    if (!formId) return null
    const f = forms.find((f) => f.id === formId)
    return f?.name || null
  }

  if (selected) {
    return (
      <div className="space-y-6 max-w-4xl">
        <StepsView
          automation={selected}
          onBack={() => setSelected(null)}
        />
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Automatizaciones</h1>
          <p className="text-sm text-gray-500 dark:text-slate-400">
            Secuencias de correos automáticos que se envían a cada nuevo suscriptor según el formulario por el que entraron.
          </p>
        </div>
        <button className="btn-primary" onClick={() => setShowCreate(true)}>
          <Plus className="h-4 w-4" /> Nueva automatización
        </button>
      </div>

      {error && (
        <div role="alert" className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg p-3 flex items-center justify-between">
          {error}
          <button aria-label="Cerrar error" onClick={() => setError(null)} className="text-red-400 hover:text-red-600 ml-3">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {loading ? (
        <div role="status" aria-live="polite" className="p-8 text-center text-gray-500 dark:text-slate-400">
          Cargando…
        </div>
      ) : automations.length === 0 ? (
        <div className="card p-12 text-center">
          <Zap className="mx-auto mb-3 h-12 w-12 text-gray-300 dark:text-slate-600" />
          <p className="text-gray-500 dark:text-slate-400 mb-4">Aún no tienes automatizaciones</p>
          <button className="btn-primary" onClick={() => setShowCreate(true)}>
            <Plus className="h-4 w-4" /> Crear primera automatización
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {automations.map((auto) => {
            const formName = getFormName(auto.form)
            return (
              <div key={auto.id} className="card p-5">
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-1 flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-semibold">{auto.name}</h3>
                      <span
                        className={`badge ${
                          auto.is_active
                            ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                            : 'bg-gray-100 text-gray-500 dark:bg-slate-700 dark:text-slate-400'
                        }`}
                      >
                        {auto.is_active ? 'Activa' : 'Inactiva'}
                      </span>
                    </div>
                    <p className="text-sm text-gray-500 dark:text-slate-400">
                      {formName ? (
                        <>Formulario: <span className="font-medium text-gray-700 dark:text-slate-300">{formName}</span></>
                      ) : (
                        <span className="text-gray-400 dark:text-slate-500">Sin formulario vinculado</span>
                      )}
                    </p>
                    <p className="text-xs text-gray-400 dark:text-slate-500">
                      {auto.enrolled_count ?? 0} activos · {auto.completed_count ?? 0} completados
                    </p>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <button
                      aria-label={`Ver pasos de ${auto.name}`}
                      onClick={() => setSelected(auto)}
                      className="btn-secondary text-xs py-1.5 flex items-center gap-1"
                    >
                      Ver pasos
                    </button>
                    <button
                      aria-label={`Editar automatización ${auto.name}`}
                      onClick={() => setEditAuto(auto)}
                      className="btn-secondary text-xs py-1.5 flex items-center gap-1"
                    >
                      <Pencil className="h-3.5 w-3.5" /> Editar
                    </button>
                    <button
                      aria-label={`Eliminar automatización ${auto.name}`}
                      onClick={() => handleDelete(auto.id)}
                      className="text-gray-400 hover:text-red-600 p-1.5"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {showCreate && (
        <AutomationModal
          forms={forms}
          onClose={() => setShowCreate(false)}
          onSaved={handleSaved}
        />
      )}
      {editAuto && (
        <AutomationModal
          initial={editAuto}
          forms={forms}
          onClose={() => setEditAuto(null)}
          onSaved={handleSaved}
        />
      )}
    </div>
  )
}
