import { useEffect, useState } from 'react'
import { ClipboardList, Code2, Pencil, Trash2, Plus, X } from 'lucide-react'
import api, { fetchAll } from '../api'

const DEFAULT_FORM = {
  name: '',
  title: '',
  description: '',
  button_text: 'Suscribirse',
  success_message: '¡Gracias! Revisa tu email para confirmar tu suscripción.',
  redirect_url: '',
  primary_color: '#6366f1',
  collect_first_name: false,
  collect_last_name: false,
  target_list: '',
  is_active: true,
}

function FormModal({ initial, groups, onClose, onSaved }) {
  const isEdit = !!initial?.id
  const [form, setForm] = useState(
    isEdit
      ? {
          name: initial.name || '',
          title: initial.title || '',
          description: initial.description || '',
          button_text: initial.button_text || 'Suscribirse',
          success_message: initial.success_message || '',
          redirect_url: initial.redirect_url || '',
          primary_color: initial.primary_color || '#6366f1',
          collect_first_name: !!initial.collect_first_name,
          collect_last_name: !!initial.collect_last_name,
          target_list: initial.target_list || '',
          is_active: initial.is_active !== false,
        }
      : { ...DEFAULT_FORM }
  )
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  function set(k, v) {
    setForm((prev) => ({ ...prev, [k]: v }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const payload = { ...form, target_list: form.target_list ? Number(form.target_list) : null }
      if (isEdit) {
        await api.patch(`/forms/${initial.id}/`, payload)
      } else {
        await api.post('/forms/', payload)
      }
      onSaved()
    } catch (err) {
      setError(
        err.response?.data
          ? JSON.stringify(err.response.data)
          : 'Error al guardar el formulario'
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
        aria-labelledby="form-modal-title"
        onSubmit={handleSubmit}
        className="card w-full max-w-lg flex flex-col max-h-[90vh] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 dark:border-slate-700 flex-shrink-0">
          <h2 id="form-modal-title" className="text-lg font-semibold">
            {isEdit ? 'Editar formulario' : 'Nuevo formulario'}
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
            <label htmlFor="fm-name" className="label">Nombre interno *</label>
            <input
              id="fm-name"
              className="input"
              required
              value={form.name}
              onChange={(e) => set('name', e.target.value)}
            />
          </div>

          <div>
            <label htmlFor="fm-target-list" className="label">Grupo de destino</label>
            <select
              id="fm-target-list"
              className="input"
              value={form.target_list}
              onChange={(e) => set('target_list', e.target.value)}
            >
              <option value="">Grupo por defecto</option>
              {groups.map((g) => (
                <option key={g.id} value={g.id}>{g.name}</option>
              ))}
            </select>
            <p className="text-xs text-gray-500 dark:text-slate-400 mt-1">
              Los suscriptores que entren por este formulario se añadirán a este grupo.
            </p>
          </div>

          <div>
            <label htmlFor="fm-title" className="label">Título del formulario</label>
            <input
              id="fm-title"
              className="input"
              value={form.title}
              onChange={(e) => set('title', e.target.value)}
            />
          </div>

          <div>
            <label htmlFor="fm-description" className="label">Descripción</label>
            <textarea
              id="fm-description"
              className="input"
              rows={3}
              value={form.description}
              onChange={(e) => set('description', e.target.value)}
            />
          </div>

          <div>
            <label htmlFor="fm-button-text" className="label">Texto del botón</label>
            <input
              id="fm-button-text"
              className="input"
              value={form.button_text}
              onChange={(e) => set('button_text', e.target.value)}
            />
          </div>

          <div>
            <label htmlFor="fm-success-message" className="label">Mensaje de éxito</label>
            <textarea
              id="fm-success-message"
              className="input"
              rows={2}
              value={form.success_message}
              onChange={(e) => set('success_message', e.target.value)}
            />
          </div>

          <div>
            <label htmlFor="fm-redirect-url" className="label">URL de redirección tras confirmar (opcional)</label>
            <input
              id="fm-redirect-url"
              className="input"
              type="url"
              placeholder="https://tudominio.com/gracias"
              value={form.redirect_url}
              onChange={(e) => set('redirect_url', e.target.value)}
            />
          </div>

          <div>
            <label htmlFor="fm-color" className="label">Color del botón</label>
            <div className="flex items-center gap-3">
              <input
                id="fm-color"
                type="color"
                className="h-9 w-14 rounded border border-gray-300 dark:border-slate-600 cursor-pointer p-1"
                value={form.primary_color}
                onChange={(e) => set('primary_color', e.target.value)}
              />
              <span className="text-sm font-mono text-gray-600 dark:text-slate-300">{form.primary_color}</span>
            </div>
          </div>

          <div className="space-y-2">
            <label className="flex items-center gap-2 cursor-pointer text-sm">
              <input
                type="checkbox"
                className="rounded border-gray-300"
                checked={form.collect_first_name}
                onChange={(e) => set('collect_first_name', e.target.checked)}
              />
              Pedir nombre
            </label>
            <label className="flex items-center gap-2 cursor-pointer text-sm">
              <input
                type="checkbox"
                className="rounded border-gray-300"
                checked={form.collect_last_name}
                onChange={(e) => set('collect_last_name', e.target.checked)}
              />
              Pedir apellido
            </label>
            <label className="flex items-center gap-2 cursor-pointer text-sm">
              <input
                type="checkbox"
                className="rounded border-gray-300"
                checked={form.is_active}
                onChange={(e) => set('is_active', e.target.checked)}
              />
              Formulario activo
            </label>
          </div>
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

function EmbedModal({ form, onClose }) {
  const [embedCode, setEmbedCode] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    setLoading(true)
    setError(null)
    api
      .get(`/forms/${form.id}/embed/`)
      .then((r) => setEmbedCode(r.data.html || ''))
      .catch(() => setError('No se pudo cargar el código embed.'))
      .finally(() => setLoading(false))
  }, [form.id])

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(embedCode)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setError('No se pudo copiar al portapapeles.')
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
        aria-labelledby="embed-modal-title"
        className="card w-full max-w-2xl flex flex-col max-h-[90vh] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 dark:border-slate-700 flex-shrink-0">
          <h2 id="embed-modal-title" className="text-lg font-semibold">
            Código para incrustar en tu web
          </h2>
          <button
            type="button"
            aria-label="Cerrar modal de código embed"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 dark:text-slate-400 dark:hover:text-slate-200"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          <p className="text-sm text-gray-500 dark:text-slate-400">
            Copia este HTML y pégalo en cualquier página de tu sitio web.
          </p>

          {error && (
            <div role="alert" className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg p-3">
              {error}
            </div>
          )}

          {loading ? (
            <div role="status" aria-live="polite" className="py-8 text-center text-gray-500 dark:text-slate-400">
              Cargando…
            </div>
          ) : (
            <>
              <textarea
                readOnly
                rows={8}
                className="input font-mono text-xs"
                value={embedCode}
                aria-label="Código HTML para embeber el formulario"
              />
              <div className="flex justify-end">
                <button className="btn-primary" onClick={handleCopy}>
                  {copied ? '✓ Copiado' : 'Copiar código'}
                </button>
              </div>

              {embedCode && (
                <div>
                  <p className="text-xs text-gray-500 dark:text-slate-400 mb-2 font-medium">Vista previa</p>
                  <div className="border border-gray-200 dark:border-slate-700 rounded-lg overflow-hidden">
                    <iframe
                      title={`Vista previa del formulario ${form.name}`}
                      srcDoc={embedCode}
                      className="w-full"
                      style={{ height: '200px' }}
                      sandbox="allow-forms allow-scripts"
                    />
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        <div className="flex justify-end px-6 py-4 border-t border-gray-100 dark:border-slate-700 flex-shrink-0">
          <button className="btn-secondary" onClick={onClose}>
            Cerrar
          </button>
        </div>
      </div>
    </div>
  )
}

export default function Forms() {
  const [forms, setForms] = useState([])
  const [groups, setGroups] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showCreate, setShowCreate] = useState(false)
  const [editForm, setEditForm] = useState(null)
  const [embedForm, setEmbedForm] = useState(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      setForms(await fetchAll('/forms/'))
    } catch {
      setError('No se pudieron cargar los formularios.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])
  useEffect(() => {
    api.get('/subscribers/groups/').then((r) => setGroups(r.data || [])).catch(() => {})
  }, [])

  async function handleDelete(id) {
    if (!confirm('¿Eliminar este formulario? Esta acción no se puede deshacer.')) return
    try {
      await api.delete(`/forms/${id}/`)
      await load()
    } catch {
      setError('No se pudo eliminar el formulario.')
    }
  }

  function handleSaved() {
    setShowCreate(false)
    setEditForm(null)
    load()
  }

  return (
    <div className="space-y-6 max-w-6xl">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Formularios de suscripción</h1>
          <p className="text-sm text-gray-500 dark:text-slate-400">
            Crea formularios embebibles para tu web. Cada suscripción envía un email de verificación automáticamente.
          </p>
        </div>
        <button className="btn-primary" onClick={() => setShowCreate(true)}>
          <Plus className="h-4 w-4" /> Nuevo formulario
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
      ) : forms.length === 0 ? (
        <div className="card p-12 text-center">
          <ClipboardList className="mx-auto mb-3 h-12 w-12 text-gray-300 dark:text-slate-600" />
          <p className="text-gray-500 dark:text-slate-400 mb-4">Aún no tienes formularios</p>
          <button className="btn-primary" onClick={() => setShowCreate(true)}>
            <Plus className="h-4 w-4" /> Crear tu primer formulario
          </button>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {forms.map((form) => (
            <div key={form.id} className="card p-5 space-y-3">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-semibold">{form.name}</h3>
                  <p className="text-sm text-gray-500 dark:text-slate-400">{form.title}</p>
                </div>
                <span
                  className={`badge ${
                    form.is_active
                      ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                      : 'bg-gray-100 text-gray-500 dark:bg-slate-700 dark:text-slate-400'
                  }`}
                >
                  {form.is_active ? 'Activo' : 'Inactivo'}
                </span>
              </div>
              <p className="text-xs text-gray-500 dark:text-slate-400">
                Creado {new Date(form.created_at).toLocaleDateString()}
              </p>
              <div className="flex gap-2 pt-1">
                <button
                  aria-label="Ver código para incrustar"
                  onClick={() => setEmbedForm(form)}
                  className="btn-secondary text-xs py-1.5 flex items-center gap-1"
                >
                  <Code2 className="h-3.5 w-3.5" /> Código embed
                </button>
                <button
                  aria-label={`Editar formulario ${form.name}`}
                  onClick={() => setEditForm(form)}
                  className="btn-secondary text-xs py-1.5 flex items-center gap-1"
                >
                  <Pencil className="h-3.5 w-3.5" /> Editar
                </button>
                <button
                  aria-label={`Eliminar formulario ${form.name}`}
                  onClick={() => handleDelete(form.id)}
                  className="text-gray-400 hover:text-red-600 p-1.5"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showCreate && (
        <FormModal groups={groups} onClose={() => setShowCreate(false)} onSaved={handleSaved} />
      )}

      {editForm && (
        <FormModal
          initial={editForm}
          groups={groups}
          onClose={() => setEditForm(null)}
          onSaved={handleSaved}
        />
      )}

      {embedForm && (
        <EmbedModal form={embedForm} onClose={() => setEmbedForm(null)} />
      )}
    </div>
  )
}
