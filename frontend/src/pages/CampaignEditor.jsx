import { useEffect, useState } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { ArrowLeft, ArrowRight, Save, Send, Copy, FileText, CalendarClock, FlaskConical, Eye, X, UserX, Upload, Type, Code2 } from 'lucide-react'
import api from '../api'
import RichTextEditor from '../components/RichTextEditor.jsx'
import { wrapEmailHtml } from '../emailPreview.js'

const BLANK_CONTENT = '<p>Escribe el contenido de tu correo aquí…</p>'

// Plantilla de arranque para el modo HTML: email responsive basado en tablas
// (el formato robusto que entienden todos los clientes de correo), con tarjeta
// de 600px, barra de acento, cabecera, título, cuerpo, botón CTA y pie con el
// enlace de baja real ({{unsubscribe_url}}). Pensada para que el usuario parta
// de una base sólida y solo cambie textos/colores, en lugar de una caja vacía.
const HTML_STARTER_TEMPLATE = `<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{first_name}}, tenemos algo para ti</title>
</head>
<body style="margin:0; padding:0; background-color:#f4f5fb;">

  <!-- Preheader oculto (texto de vista previa en la bandeja) -->
  <div style="display:none; max-height:0; overflow:hidden; opacity:0; color:#f4f5fb; font-size:1px; line-height:1px;">
    Resume aquí en una línea de qué va el correo.
  </div>

  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f4f5fb;">
    <tr>
      <td align="center" style="padding:24px 12px;">

        <!-- Tarjeta 600px -->
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:600px; max-width:600px; background-color:#ffffff; border-radius:14px; overflow:hidden; border:1px solid #e6e7f0;">

          <!-- Barra de acento -->
          <tr>
            <td style="height:6px; line-height:6px; font-size:6px; background:#4f46e5;">&nbsp;</td>
          </tr>

          <!-- Cabecera -->
          <tr>
            <td style="padding:28px 32px 8px 32px; font-family:Arial,Helvetica,sans-serif; font-size:22px; font-weight:800; color:#1f2433;">
              Tu Marca
            </td>
          </tr>

          <!-- Título -->
          <tr>
            <td style="padding:8px 32px 0 32px; font-family:Arial,Helvetica,sans-serif;">
              <h1 style="margin:0; font-size:24px; line-height:1.3; font-weight:800; color:#1f2433;">
                Hola {{first_name}}, este es tu titular
              </h1>
            </td>
          </tr>

          <!-- Cuerpo -->
          <tr>
            <td style="padding:18px 32px 8px 32px; font-family:Arial,Helvetica,sans-serif; font-size:16px; line-height:1.65; color:#1f2433;">
              <p style="margin:0 0 16px 0;">Escribe aquí tu mensaje. Puedes usar <strong>negrita</strong>, <em>cursiva</em> y enlaces.</p>
              <p style="margin:0 0 16px 0;">Personaliza con variables como {{first_name}}, {{last_name}} o {{email}}.</p>
            </td>
          </tr>

          <!-- Botón CTA -->
          <tr>
            <td align="center" style="padding:8px 32px 28px 32px;">
              <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td align="center" bgcolor="#4f46e5" style="border-radius:10px;">
                    <a href="https://tu-enlace.com" target="_blank"
                       style="display:inline-block; padding:14px 32px; font-family:Arial,Helvetica,sans-serif; font-size:16px; font-weight:700; color:#ffffff; text-decoration:none; border-radius:10px;">
                      Llamada a la acción
                    </a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Pie -->
          <tr>
            <td style="padding:0 32px 28px 32px; font-family:Arial,Helvetica,sans-serif; font-size:12px; line-height:1.6; color:#8a92a6;">
              <div style="border-top:1px solid #e6e7f0; padding-top:16px;">
                Recibes este correo porque te suscribiste.<br>
                <a href="{{unsubscribe_url}}" style="color:#8a92a6; text-decoration:underline;">Darse de baja</a>
              </div>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>

</body>
</html>`

// Valores de ejemplo para previsualizar las variables tal como se rellenan en el
// envío real (ver apps/campaigns/tasks.py -> _personalize y automations/tasks.py).
const PREVIEW_SAMPLE = {
  first_name: 'María',
  last_name: 'García',
  email: 'maria.garcia@ejemplo.com',
  unsubscribe_url: '#',
}

function fillPreviewPlaceholders(html) {
  return (html || '')
    // Mismo formato EXACTO que el backend (str.replace de "{{first_name}}" sin
    // espacios) para que la vista previa no mienta: `{{ first_name }}` con
    // espacios NO se sustituye, igual que en el envío real.
    .replace(/\{\{first_name\}\}/g, PREVIEW_SAMPLE.first_name)
    .replace(/\{\{last_name\}\}/g, PREVIEW_SAMPLE.last_name)
    .replace(/\{\{email\}\}/g, PREVIEW_SAMPLE.email)
    .replace(/\{\{unsubscribe_url\}\}/g, PREVIEW_SAMPLE.unsubscribe_url)
}

// Construye un documento HTML aislado que reproduce cómo llega el correo al
// destinatario. La maqueta (ancho ~600px centrado, fondo claro) vive en
// emailPreview.js y la comparte con la vista previa de Entregabilidad, así
// ambas son fieles entre sí.
function buildPreviewSrcDoc(rawHtml) {
  return wrapEmailHtml(fillPreviewPlaceholders(rawHtml))
}

function defaultScheduleValue() {
  // Una hora en el futuro, formato compatible con input datetime-local.
  const d = new Date(Date.now() + 60 * 60 * 1000)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export default function CampaignEditor() {
  const { id } = useParams()
  const isEdit = !!id
  const nav = useNavigate()
  const [step, setStep] = useState(1)
  const [saving, setSaving] = useState(false)
  const [sending, setSending] = useState(false)
  const [subsCount, setSubsCount] = useState(0)
  const [sendableCount, setSendableCount] = useState(0)   // activos NO en automatización activa
  const [showRecent, setShowRecent] = useState(!isEdit)
  const [recent, setRecent] = useState([])
  const [groups, setGroups] = useState([])
  const [form, setForm] = useState({
    name: '',
    subject: '',
    preview_text: '',
    from_name: '',
    from_email: '',
    html_content: BLANK_CONTENT,
    ab_enabled: false,
    subject_b: '',
    ab_split_percent: 50,
    subscriber_list: null,
    send_to_all: true,
  })
  const [campaignId, setCampaignId] = useState(id || null)
  const [me, setMe] = useState(null)
  const [scheduleMode, setScheduleMode] = useState('now') // 'now' | 'later'
  const [scheduledAt, setScheduledAt] = useState(defaultScheduleValue())
  const [showPreview, setShowPreview] = useState(false)
  const [editorMode, setEditorMode] = useState('visual') // 'visual' | 'html'
  const [testEmail, setTestEmail] = useState('')
  const [testSending, setTestSending] = useState(false)
  const [testResult, setTestResult] = useState(null)
  const [exclusionCount, setExclusionCount] = useState(0)
  const [exclusionUploading, setExclusionUploading] = useState(false)
  const [exclusionResult, setExclusionResult] = useState(null)

  useEffect(() => {
    api.get('/subscribers/groups/').then((r) => setGroups(r.data || [])).catch(() => {})
    api.get('/auth/me/').then((r) => {
      setMe(r.data)
      if (!isEdit) {
        const fallbackFromEmail = r.data.from_email || r.data.smtp_user || r.data.email || ''
        setForm((f) => ({
          ...f,
          from_name: f.from_name || r.data.from_name || r.data.username || '',
          from_email: f.from_email || fallbackFromEmail,
        }))
      }
    })
    if (isEdit) {
      api.get(`/campaigns/${id}/`).then((r) => {
        setForm({
          name: r.data.name || '',
          subject: r.data.subject || '',
          preview_text: r.data.preview_text || '',
          from_name: r.data.from_name || '',
          from_email: r.data.from_email || '',
          html_content: r.data.html_content || '',
          ab_enabled: r.data.ab_enabled || false,
          subject_b: r.data.subject_b || '',
          ab_split_percent: r.data.ab_split_percent ?? 50,
          subscriber_list: r.data.subscriber_list ?? null,
          send_to_all: r.data.send_to_all ?? false,
        })
        if (r.data.status === 'scheduled' && r.data.scheduled_at) {
          const d = new Date(r.data.scheduled_at)
          const pad = (n) => String(n).padStart(2, '0')
          setScheduledAt(`${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`)
          setScheduleMode('later')
        }
        if (r.data.excluded_emails) {
          const lines = r.data.excluded_emails.split('\n').filter(Boolean)
          setExclusionCount(lines.length)
        }
      })
    } else {
      api.get('/campaigns/').then((r) => {
        const all = r.data.results || r.data
        setRecent(all.slice(0, 6))
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  // Recalcula el número de destinatarios según el ámbito elegido (un grupo o
  // todos). El backend devuelve sendable_count para el ámbito de ?list=.
  useEffect(() => {
    const qs = (!form.send_to_all && form.subscriber_list)
      ? `?list=${form.subscriber_list}`
      : ''
    api.get(`/subscribers/all/${qs}`).then((r) => {
      setSubsCount(r.data.count || 0)
      setSendableCount(r.data.sendable_count ?? r.data.count ?? 0)
    }).catch(() => {})
  }, [form.send_to_all, form.subscriber_list])

  async function applyTemplate(c) {
    try {
      const r = await api.get(`/campaigns/${c.id}/`)
      setForm({
        name: '',
        subject: r.data.subject || '',
        preview_text: r.data.preview_text || '',
        from_name: form.from_name || r.data.from_name || '',
        from_email: form.from_email || r.data.from_email || '',
        html_content: r.data.html_content || BLANK_CONTENT,
        ab_enabled: false,
        subject_b: '',
        ab_split_percent: 50,
        subscriber_list: form.subscriber_list ?? null,
        send_to_all: form.send_to_all ?? true,
      })
      setShowRecent(false)
    } catch {
      alert('No se pudo cargar la plantilla')
    }
  }

  function startBlank() {
    setShowRecent(false)
  }

  async function persist() {
    const payload = { ...form }
    if (campaignId) {
      const r = await api.patch(`/campaigns/${campaignId}/`, payload)
      return r.data
    }
    const r = await api.post('/campaigns/', payload)
    setCampaignId(r.data.id)
    return r.data
  }

  async function handleSaveDraft() {
    if (!form.name || !form.subject) { alert('Nombre y asunto son obligatorios'); return }
    setSaving(true)
    try {
      await persist()
      nav('/campaigns')
    } catch (err) {
      alert(err.response?.data ? JSON.stringify(err.response.data) : 'Error guardando')
    } finally {
      setSaving(false)
    }
  }

  async function handleNext() {
    if (!form.name || !form.subject) { alert('Nombre y asunto son obligatorios'); return }
    setSaving(true)
    try {
      await persist()
      setStep(2)
    } catch (err) {
      alert(err.response?.data ? JSON.stringify(err.response.data) : 'Error guardando')
    } finally {
      setSaving(false)
    }
  }

  async function handleSend() {
    if (!campaignId) return
    if (sendableCount === 0) {
      const msg = subsCount === 0
        ? 'No tienes suscriptores. ¿Marcar como enviada igualmente?'
        : 'Todos tus suscriptores activos están dentro de una automatización, así que no se enviará a nadie. ¿Marcar como enviada igualmente?'
      if (!confirm(msg)) return
    }
    setSending(true)
    try {
      await api.post(`/campaigns/${campaignId}/send/`)
      nav('/campaigns')
    } catch (err) {
      alert(err.response?.data?.detail || 'Error al enviar')
    } finally {
      setSending(false)
    }
  }

  async function handleSchedule() {
    if (!campaignId) return
    if (!scheduledAt) { alert('Indica fecha y hora.'); return }
    const iso = new Date(scheduledAt).toISOString()
    if (new Date(iso) <= new Date()) {
      alert('La fecha debe estar en el futuro.'); return
    }
    setSending(true)
    try {
      await api.post(`/campaigns/${campaignId}/schedule/`, { scheduled_at: iso })
      nav('/campaigns')
    } catch (err) {
      alert(err.response?.data?.detail || 'Error al programar')
    } finally {
      setSending(false)
    }
  }

  async function handleSendTest() {
    if (!campaignId) { alert('Guarda la campaña primero.'); return }
    if (!testEmail) { alert('Introduce un email de prueba.'); return }
    setTestSending(true)
    setTestResult(null)
    try {
      const r = await api.post(`/campaigns/${campaignId}/send_test/`, { email: testEmail })
      setTestResult({ ok: true, msg: r.data.detail || `Enviado a ${testEmail}` })
    } catch (err) {
      setTestResult({ ok: false, msg: err.response?.data?.detail || 'Error al enviar el test' })
    } finally {
      setTestSending(false)
    }
  }

  async function handleExclusionUpload(e) {
    const file = e.target.files?.[0]
    if (!file || !campaignId) return
    setExclusionUploading(true)
    setExclusionResult(null)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const r = await api.post(`/campaigns/${campaignId}/exclude/`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      setExclusionCount(r.data.total_excluded)
      setExclusionResult({ added: r.data.detail, total: r.data.total_excluded })
    } catch (err) {
      setExclusionResult({ error: err.response?.data?.detail || 'Error al subir el fichero' })
    } finally {
      setExclusionUploading(false)
      e.target.value = ''
    }
  }

  async function handleClearExclusion() {
    if (!campaignId) return
    if (!confirm('¿Eliminar la lista de exclusión de esta campaña?')) return
    try {
      await api.delete(`/campaigns/${campaignId}/exclude/`)
      setExclusionCount(0)
      setExclusionResult(null)
    } catch {
      alert('No se pudo eliminar la lista de exclusión. Inténtalo de nuevo.')
    }
  }

  if (showRecent) {
    return (
      <div className="max-w-5xl space-y-6">
        <div>
          <Link to="/campaigns" className="inline-flex items-center text-sm text-gray-400 hover:text-gray-600 dark:hover:text-slate-200">
            <ArrowLeft className="h-4 w-4 mr-1" /> Campañas
          </Link>
          <h1 className="text-2xl font-semibold mt-1">Nueva campaña</h1>
          <p className="text-sm text-gray-500 dark:text-slate-400 mt-1">Empieza desde cero o reutiliza un correo anterior como plantilla.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <button
            onClick={startBlank}
            className="card p-6 text-left hover:border-primary-500 hover:shadow-md transition-all flex flex-col items-start gap-3 border-2 border-dashed"
          >
            <div className="h-12 w-12 rounded-lg bg-primary-50 dark:bg-primary-900/30 text-primary-600 dark:text-primary-400 flex items-center justify-center">
              <FileText className="h-6 w-6" />
            </div>
            <div>
              <div className="font-semibold text-gray-900 dark:text-slate-100">Email en blanco</div>
              <div className="text-xs text-gray-500 dark:text-slate-400 mt-1">Empieza con un editor vacío.</div>
            </div>
          </button>

          {recent.map((c) => (
            <button
              key={c.id}
              onClick={() => applyTemplate(c)}
              className="card p-6 text-left hover:border-primary-500 hover:shadow-md transition-all flex flex-col items-start gap-3"
            >
              <div className="h-12 w-12 rounded-lg bg-gray-100 dark:bg-slate-700 text-gray-500 dark:text-slate-400 flex items-center justify-center">
                <Copy className="h-6 w-6" />
              </div>
              <div className="w-full min-w-0">
                <div className="font-semibold text-gray-900 dark:text-slate-100 truncate">{c.name}</div>
                <div className="text-xs text-gray-500 dark:text-slate-400 mt-1 truncate">{c.subject || '(sin asunto)'}</div>
                <div className="text-xs text-gray-500 dark:text-slate-400 mt-2">
                  {c.status === 'sent' ? 'Enviada' : c.status === 'draft' ? 'Borrador' : c.status}
                  {c.created_at && ` · ${new Date(c.created_at).toLocaleDateString()}`}
                </div>
              </div>
            </button>
          ))}
        </div>

        {recent.length === 0 && (
          <p className="text-sm text-gray-400 dark:text-slate-500">
            Cuando tengas campañas anteriores aparecerán aquí para usarlas como plantilla.
          </p>
        )}
      </div>
    )
  }

  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <Link to="/campaigns" className="inline-flex items-center text-sm text-gray-400 hover:text-gray-600 dark:hover:text-slate-200">
            <ArrowLeft className="h-4 w-4 mr-1" /> Campañas
          </Link>
          <h1 className="text-2xl font-semibold mt-1">{isEdit ? 'Editar campaña' : 'Nueva campaña'}</h1>
        </div>
        <Steps step={step} />
      </div>

      {step === 1 && (
        <div className="space-y-6">
          <div className="card p-5 space-y-4">
            <h2 className="font-semibold">Información básica</h2>
            <div>
              <label className="label">Nombre interno *</label>
              <input className="input" required value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div>
              <label className="label">{form.ab_enabled ? 'Asunto variante A *' : 'Asunto *'}</label>
              <input className="input" required value={form.subject}
                onChange={(e) => setForm({ ...form, subject: e.target.value })} />
            </div>
            <div>
              <label className="label">Texto preview</label>
              <input className="input" value={form.preview_text}
                onChange={(e) => setForm({ ...form, preview_text: e.target.value })} />
            </div>
            <div>
              <label className="label">Enviar a</label>
              <select
                className="input"
                value={form.send_to_all ? 'all' : String(form.subscriber_list ?? '')}
                onChange={(e) => {
                  const v = e.target.value
                  if (v === 'all') {
                    setForm({ ...form, send_to_all: true, subscriber_list: null })
                  } else {
                    setForm({ ...form, send_to_all: false, subscriber_list: Number(v) })
                  }
                }}
              >
                <option value="all">Todos los grupos</option>
                {groups.map((g) => (
                  <option key={g.id} value={g.id}>{g.name} ({g.subscriber_count})</option>
                ))}
              </select>
              <p className="text-xs text-gray-500 dark:text-slate-400 mt-1">
                Elige un grupo concreto o envía a todos los suscriptores de todos los grupos.
              </p>
            </div>
          </div>

          {/* A/B Testing */}
          <div className="card p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FlaskConical className="h-4 w-4 text-indigo-500" />
                <h2 className="font-semibold">Test A/B</h2>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={form.ab_enabled}
                aria-label="Activar test A/B"
                onClick={() => setForm({ ...form, ab_enabled: !form.ab_enabled })}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${
                  form.ab_enabled ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-slate-600'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                    form.ab_enabled ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>
            {form.ab_enabled && (
              <div className="space-y-4">
                <div>
                  <label className="label">Asunto variante B *</label>
                  <input
                    className="input"
                    value={form.subject_b}
                    onChange={(e) => setForm({ ...form, subject_b: e.target.value })}
                    placeholder="Escribe el asunto alternativo…"
                  />
                </div>
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="label mb-0">Distribución</label>
                    <span className="text-sm text-gray-600 dark:text-slate-300">
                      Variante A: <strong>{form.ab_split_percent}%</strong>
                      {' · '}
                      Variante B: <strong>{100 - form.ab_split_percent}%</strong>
                    </span>
                  </div>
                  <input
                    type="range"
                    id="ab-split"
                    min={0}
                    max={100}
                    step={5}
                    value={form.ab_split_percent}
                    onChange={(e) => setForm({ ...form, ab_split_percent: Number(e.target.value) })}
                    className="w-full accent-indigo-600"
                    aria-label="Porcentaje de distribución para la variante A"
                  />
                  <div className="flex justify-between text-xs text-gray-500 dark:text-slate-400 mt-1">
                    <span>0%</span>
                    <span>50%</span>
                    <span>100%</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="card p-5 space-y-4">
            <h2 className="font-semibold">Remitente</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="label">Nombre</label>
                <input className="input" value={form.from_name}
                  onChange={(e) => setForm({ ...form, from_name: e.target.value })} />
              </div>
              <div>
                <label className="label">Email</label>
                <input className="input" type="email" value={form.from_email}
                  onChange={(e) => setForm({ ...form, from_email: e.target.value })} />
              </div>
            </div>
          </div>

          <div className="card p-5 space-y-3">
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <h2 className="font-semibold">Contenido</h2>
              {/* Selector de modo: editor visual (Tiptap) o HTML en crudo */}
              <div className="inline-flex rounded-md border border-gray-300 dark:border-slate-600 overflow-hidden text-sm">
                <button
                  type="button"
                  onClick={() => setEditorMode('visual')}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 ${
                    editorMode === 'visual'
                      ? 'bg-primary-600 text-white'
                      : 'bg-white dark:bg-slate-900 text-gray-600 dark:text-slate-300 hover:bg-gray-50 dark:hover:bg-slate-800'
                  }`}
                  aria-pressed={editorMode === 'visual'}
                >
                  <Type className="h-4 w-4" /> Visual
                </button>
                <button
                  type="button"
                  onClick={() => setEditorMode('html')}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 border-l border-gray-300 dark:border-slate-600 ${
                    editorMode === 'html'
                      ? 'bg-primary-600 text-white'
                      : 'bg-white dark:bg-slate-900 text-gray-600 dark:text-slate-300 hover:bg-gray-50 dark:hover:bg-slate-800'
                  }`}
                  aria-pressed={editorMode === 'html'}
                >
                  <Code2 className="h-4 w-4" /> HTML
                </button>
              </div>
            </div>

            {editorMode === 'visual' ? (
              <RichTextEditor
                value={form.html_content}
                onChange={(html) => setForm({ ...form, html_content: html })}
                footer={me}
              />
            ) : (
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <p className="text-xs text-gray-500 dark:text-slate-400">
                    Pega o escribe un correo HTML completo (tablas + estilos en línea).
                  </p>
                  <button
                    type="button"
                    onClick={() => {
                      const empty = !form.html_content || form.html_content.trim() === '' || form.html_content === BLANK_CONTENT
                      if (!empty && !confirm('Esto reemplazará el contenido actual por la plantilla de ejemplo. ¿Continuar?')) return
                      setForm({ ...form, html_content: HTML_STARTER_TEMPLATE })
                    }}
                    className="inline-flex items-center gap-1.5 rounded-md border border-primary-200 dark:border-primary-700 bg-primary-50 dark:bg-primary-900/30 px-2.5 py-1 text-xs font-medium text-primary-700 dark:text-primary-400 hover:bg-primary-100 dark:hover:bg-primary-900/50"
                  >
                    <Code2 className="h-3.5 w-3.5" /> Insertar plantilla de ejemplo
                  </button>
                </div>
                <textarea
                  className="input font-mono text-sm leading-relaxed min-h-[420px] whitespace-pre"
                  spellCheck={false}
                  value={form.html_content}
                  onChange={(e) => setForm({ ...form, html_content: e.target.value })}
                  placeholder={'<!doctype html>\n<html>\n  <body style="margin:0;background:#f4f4f7;">\n    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">\n      <!-- Escribe tu correo HTML completo con estilos en línea -->\n    </table>\n  </body>\n</html>'}
                />
                <p className="text-xs text-amber-600 dark:text-amber-400">
                  Modo HTML: escribe el correo completo con tus propios estilos (recomendado en línea, <code>style="…"</code>).
                  Incluye <code>{'{{unsubscribe_url}}'}</code> en tu pie para respetar tu maquetación; si no lo pones, MailerUp añadirá un pie de baja al enviar.
                  Al volver al modo <strong>Visual</strong>, el editor puede simplificar etiquetas o estilos que no reconoce.
                  Usa <strong>Vista previa</strong> para comprobar el resultado final.
                </p>
              </div>
            )}

            <p className="text-xs text-gray-500 dark:text-slate-400">
              Puedes usar <code>{'{{first_name}}'}</code>, <code>{'{{last_name}}'}</code>, <code>{'{{email}}'}</code> como variables.
            </p>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <button className="btn-secondary" onClick={handleSaveDraft} disabled={saving}>
                <Save className="h-4 w-4" /> Guardar borrador
              </button>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setShowPreview(true)}
              >
                <Eye className="h-4 w-4" /> Vista previa
              </button>
            </div>
            <button className="btn-primary" onClick={handleNext} disabled={saving}>
              Siguiente <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* Preview Modal */}
      {showPreview && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={() => setShowPreview(false)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="preview-modal-title"
            className="bg-gray-50 dark:bg-slate-900 rounded-xl shadow-2xl ring-1 ring-black/5 dark:ring-white/10 w-full max-w-3xl flex flex-col max-h-[88vh] overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800">
              <h2 id="preview-modal-title" className="font-semibold text-gray-900 dark:text-slate-100">Vista previa del correo</h2>
              <button
                type="button"
                aria-label="Cerrar vista previa"
                onClick={() => setShowPreview(false)}
                className="text-gray-400 hover:text-gray-700 dark:hover:text-slate-200"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Cabecera realista del mensaje, tal como la vería el destinatario */}
            <div className="px-5 py-3 border-b border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 space-y-1 text-sm">
              <div className="flex gap-2">
                <span className="w-16 shrink-0 text-gray-400 dark:text-slate-500">De:</span>
                <span className="font-medium text-gray-900 dark:text-slate-100 truncate">
                  {form.from_name || '(sin nombre)'}{' '}
                  <span className="font-normal text-gray-500 dark:text-slate-400">
                    &lt;{form.from_email || 'sin-email@ejemplo.com'}&gt;
                  </span>
                </span>
              </div>
              <div className="flex gap-2">
                <span className="w-16 shrink-0 text-gray-400 dark:text-slate-500">Para:</span>
                <span className="text-gray-700 dark:text-slate-300 truncate">
                  {PREVIEW_SAMPLE.first_name} {PREVIEW_SAMPLE.last_name} &lt;{PREVIEW_SAMPLE.email}&gt;
                </span>
              </div>
              <div className="flex gap-2">
                <span className="w-16 shrink-0 text-gray-400 dark:text-slate-500">Asunto:</span>
                <span className="font-semibold text-gray-900 dark:text-slate-100 truncate">
                  {fillPreviewPlaceholders(form.subject) || '(sin asunto)'}
                </span>
              </div>
              {form.preview_text && (
                <div className="flex gap-2">
                  <span className="w-16 shrink-0 text-gray-400 dark:text-slate-500">Preview:</span>
                  <span className="text-gray-500 dark:text-slate-400 italic truncate">
                    {fillPreviewPlaceholders(form.preview_text)}
                  </span>
                </div>
              )}
            </div>

            {/* Cuerpo del email aislado en un iframe (sin scripts), sobre fondo claro realista */}
            <div className="flex-1 overflow-auto bg-gray-100 dark:bg-slate-950/40">
              <iframe
                sandbox=""
                className="w-full h-full min-h-[60vh] border-0 bg-transparent"
                srcDoc={buildPreviewSrcDoc(form.html_content)}
                title="Vista previa del correo"
              />
            </div>

            <div className="px-5 py-2 border-t border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs text-gray-400 dark:text-slate-500">
              Las variables como <code>{'{{first_name}}'}</code> se muestran con datos de ejemplo.
            </div>
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="space-y-6">
          <div className="card p-6 space-y-4">
            <h2 className="font-semibold text-lg">¿A quién enviar?</h2>
            <label className="flex items-start gap-3 rounded-lg border-2 border-primary-600 bg-primary-50 dark:bg-primary-900/30 p-4 cursor-pointer">
              <input type="radio" checked readOnly className="mt-1" />
              <div>
                <div className="font-medium">
                  {form.send_to_all
                    ? 'Todos los grupos'
                    : (groups.find((g) => g.id === form.subscriber_list)?.name || 'Grupo seleccionado')}
                </div>
                <div className="text-sm text-gray-600 dark:text-slate-300">
                  Se enviará a {sendableCount} suscriptores activos.
                  {subsCount > sendableCount && (
                    <span className="block text-xs text-gray-400 dark:text-slate-500 mt-0.5">
                      ({subsCount - sendableCount} excluidos por estar en una automatización)
                    </span>
                  )}
                </div>
              </div>
            </label>
          </div>

          <div className="card p-6 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="font-semibold text-lg">Exclusiones</h2>
                <p className="text-sm text-gray-500 dark:text-slate-400">Emails que NO recibirán esta campaña aunque estén en tu lista.</p>
              </div>
              {exclusionCount > 0 && (
                <span className="inline-flex items-center rounded-full bg-orange-100 dark:bg-orange-900/30 px-2.5 py-0.5 text-xs font-medium text-orange-700 dark:text-orange-300">{exclusionCount} excluidos</span>
              )}
            </div>

            {exclusionCount > 0 ? (
              <div className="flex items-center gap-3 rounded-lg bg-orange-50 dark:bg-orange-900/30 border border-orange-200 dark:border-orange-800 p-3">
                <UserX className="h-5 w-5 text-orange-600 dark:text-orange-400 flex-shrink-0" />
                <span className="text-sm text-orange-800 dark:text-orange-300 flex-1">
                  <strong>{exclusionCount} emails</strong> serán excluidos del envío.
                </span>
                <button onClick={handleClearExclusion} className="text-xs text-orange-600 dark:text-orange-400 hover:text-orange-800 underline">
                  Eliminar
                </button>
              </div>
            ) : null}

            <div>
              <label className="flex items-center gap-2 cursor-pointer w-fit">
                <input
                  type="file"
                  accept=".csv,.txt,text/csv,text/plain"
                  className="hidden"
                  onChange={handleExclusionUpload}
                  disabled={!campaignId || exclusionUploading}
                  aria-label="Subir CSV o TXT con emails a excluir"
                />
                <span className={`btn-secondary text-sm inline-flex items-center gap-2 ${(!campaignId || exclusionUploading) ? 'opacity-50 cursor-not-allowed' : ''}`}>
                  <Upload className="h-4 w-4" />
                  {exclusionUploading ? 'Subiendo…' : 'Subir CSV / TXT de exclusión'}
                </span>
              </label>
              {!campaignId && (
                <p className="text-xs text-gray-500 dark:text-slate-400 mt-1">Guarda la campaña primero para poder añadir exclusiones.</p>
              )}
              <p className="text-xs text-gray-500 dark:text-slate-400 mt-1">
                Acepta CSV con columna <code>email</code> o un TXT con un email por línea.
              </p>
            </div>

            {exclusionResult && (
              <p role="alert" className={`text-sm ${exclusionResult.error ? 'text-red-600 dark:text-red-400' : 'text-green-700 dark:text-green-400'}`}>
                {exclusionResult.error || `✓ ${exclusionResult.added} · Total excluidos: ${exclusionResult.total}`}
              </p>
            )}
          </div>

          <div className="card p-6 space-y-3">
            <h2 className="font-semibold text-lg">¿Cuándo enviar?</h2>
            <label className={`flex items-start gap-3 rounded-lg border-2 p-4 cursor-pointer ${
              scheduleMode === 'now' ? 'border-primary-600 bg-primary-50 dark:bg-primary-900/30' : 'border-gray-200 dark:border-slate-600'
            }`}>
              <input type="radio" name="when" checked={scheduleMode === 'now'}
                onChange={() => setScheduleMode('now')} className="mt-1" />
              <div>
                <div className="font-medium flex items-center gap-2"><Send className="h-4 w-4" /> Enviar ahora</div>
                <div className="text-sm text-gray-600 dark:text-slate-300">El correo sale en cuanto pulses el botón.</div>
              </div>
            </label>
            <label className={`flex items-start gap-3 rounded-lg border-2 p-4 cursor-pointer ${
              scheduleMode === 'later' ? 'border-primary-600 bg-primary-50 dark:bg-primary-900/30' : 'border-gray-200 dark:border-slate-600'
            }`}>
              <input type="radio" name="when" checked={scheduleMode === 'later'}
                onChange={() => setScheduleMode('later')} className="mt-1" />
              <div className="flex-1">
                <div className="font-medium flex items-center gap-2"><CalendarClock className="h-4 w-4" /> Programar envío</div>
                <div className="text-sm text-gray-600 dark:text-slate-300 mb-2">
                  MailerUp lo enviará automáticamente a la fecha y hora que elijas.
                </div>
                {scheduleMode === 'later' && (
                  <input
                    type="datetime-local"
                    className="input max-w-xs"
                    value={scheduledAt}
                    min={defaultScheduleValue().replace(/T.*/, 'T00:00')}
                    onChange={(e) => setScheduledAt(e.target.value)}
                  />
                )}
              </div>
            </label>
          </div>

          {/* Send Test Email */}
          <div className="card p-6 space-y-3">
            <div>
              <h2 className="font-semibold text-lg">Prueba tu campaña</h2>
              <p className="text-sm text-gray-500 dark:text-slate-400">Envía un correo de prueba para verificar cómo se ve antes del envío definitivo.</p>
            </div>
            <div className="flex items-center gap-2">
              <label htmlFor="test-email" className="sr-only">Email de prueba</label>
              <input
                id="test-email"
                type="email"
                className="input flex-1"
                placeholder="correo@ejemplo.com"
                value={testEmail}
                onChange={(e) => { setTestEmail(e.target.value); setTestResult(null) }}
              />
              <button
                type="button"
                className="btn-secondary whitespace-nowrap"
                onClick={handleSendTest}
                disabled={testSending}
              >
                <Send className="h-4 w-4" />
                {testSending ? 'Enviando…' : 'Enviar test'}
              </button>
            </div>
            {testResult && (
              <div
                role="alert"
                className={`text-sm flex items-center gap-1.5 ${testResult.ok ? 'text-green-700 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}
              >
                <span aria-hidden="true">{testResult.ok ? '✓' : '✗'}</span>
                <span>{testResult.msg}</span>
              </div>
            )}
          </div>

          <div className="card p-6">
            <h3 className="font-semibold mb-2">Resumen</h3>
            <dl className="text-sm space-y-1.5">
              <Row k="Nombre" v={form.name} />
              <Row k="Asunto" v={form.subject} />
              <Row k="Remitente" v={`${form.from_name || '(sin nombre)'} <${form.from_email || '(sin email)'}>`} />
              <Row k="Destinatarios" v={`${sendableCount} suscriptores`} />
              {exclusionCount > 0 && <Row k="Excluidos" v={`${exclusionCount} emails no recibirán el correo`} />}
              <Row k="Envío" v={
                scheduleMode === 'now'
                  ? 'Inmediato'
                  : (scheduledAt ? new Date(scheduledAt).toLocaleString() : '(sin fecha)')
              } />
            </dl>
          </div>

          <div className="flex items-center justify-between">
            <button className="btn-secondary" onClick={() => setStep(1)}>
              <ArrowLeft className="h-4 w-4" /> Atrás
            </button>
            {scheduleMode === 'now' ? (
              <button className="btn-primary" onClick={handleSend} disabled={sending}>
                <Send className="h-4 w-4" /> {sending ? 'Enviando…' : 'Enviar ahora'}
              </button>
            ) : (
              <button className="btn-primary" onClick={handleSchedule} disabled={sending}>
                <CalendarClock className="h-4 w-4" /> {sending ? 'Programando…' : 'Programar'}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function Steps({ step }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className={`flex items-center gap-2 ${step === 1 ? 'text-primary-700 dark:text-white font-medium' : 'text-gray-400 dark:text-slate-500'}`}>
        <span className={`h-6 w-6 rounded-full flex items-center justify-center text-xs ${step === 1 ? 'bg-primary-600 text-white' : 'bg-gray-200 dark:bg-slate-700'}`}>1</span>
        Contenido
      </span>
      <span className="text-gray-300 dark:text-slate-600">›</span>
      <span className={`flex items-center gap-2 ${step === 2 ? 'text-primary-700 dark:text-white font-medium' : 'text-gray-400 dark:text-slate-500'}`}>
        <span className={`h-6 w-6 rounded-full flex items-center justify-center text-xs ${step === 2 ? 'bg-primary-600 text-white' : 'bg-gray-200 dark:bg-slate-700'}`}>2</span>
        Destinatarios
      </span>
    </div>
  )
}

function Row({ k, v }) {
  return (
    <div className="flex justify-between gap-4 border-b border-gray-100 dark:border-slate-700 py-1.5 last:border-0">
      <dt className="text-gray-500 dark:text-slate-400">{k}</dt>
      <dd className="text-gray-900 dark:text-slate-100 font-medium text-right">{v}</dd>
    </div>
  )
}
