import { useEffect, useState } from 'react'
import { Save, Send, CheckCircle2, AlertCircle, Database, Key, Copy, Trash2 } from 'lucide-react'
import api from '../api'
import DnsSetupBlock from '../components/DnsSetupBlock.jsx'

export default function Settings() {
  const [me, setMe] = useState(null)
  const [providers, setProviders] = useState([])
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [savedMsg, setSavedMsg] = useState(null)
  const [testMsg, setTestMsg] = useState(null)
  const [testTo, setTestTo] = useState('')
  const [pwForm, setPwForm] = useState({ current_password: '', new_password: '' })
  const [pwMsg, setPwMsg] = useState(null)

  useEffect(() => {
    Promise.all([
      api.get('/auth/me/'),
      api.get('/auth/email-providers/'),
    ]).then(([meRes, provRes]) => {
      setMe(meRes.data)
      setProviders(provRes.data)
      setTestTo(meRes.data.email || '')
    })
  }, [])

  const currentProvider = providers.find((p) => p.key === me?.email_provider) || providers[0]

  function setMeField(k, v) {
    setMe((prev) => {
      const next = { ...prev, [k]: v }
      // Si el usuario rellena el SMTP user y from_email está vacío, autosincroniza.
      if (k === 'smtp_user' && v && !prev.from_email) {
        next.from_email = v
      }
      return next
    })
  }

  function pickProvider(key) {
    const p = providers.find((pp) => pp.key === key)
    if (!p) { setMeField('email_provider', key); return }
    const patch = { email_provider: key }
    if (p.kind === 'smtp') {
      patch.smtp_host = p.host || me.smtp_host || ''
      patch.smtp_port = p.port || 587
      patch.smtp_use_tls = !!p.tls
      patch.smtp_use_ssl = !!p.ssl
    }
    setMe({ ...me, ...patch })
  }

  async function save() {
    setSaving(true); setSavedMsg(null)
    try {
      const payload = { ...me }
      delete payload.id; delete payload.email; delete payload.smtp_password_set
      delete payload.brevo_api_key_set; delete payload.sendgrid_api_key_set
      // Las claves son write_only: si están en blanco no se reenvían (el backend
      // las mantiene). Así guardar ajustes no borra la API key ya configurada.
      if (!payload.smtp_password) delete payload.smtp_password
      if (!payload.brevo_api_key) delete payload.brevo_api_key
      if (!payload.sendgrid_api_key) delete payload.sendgrid_api_key
      const r = await api.patch('/auth/me/', payload)
      setMe(r.data)
      setSavedMsg({ ok: true, text: 'Ajustes guardados' })
    } catch (err) {
      setSavedMsg({ ok: false, text: err.response?.data ? JSON.stringify(err.response.data) : 'Error guardando' })
    } finally {
      setSaving(false)
      setTimeout(() => setSavedMsg(null), 4000)
    }
  }

  async function testEmail() {
    const to = (testTo || '').trim()
    if (!to) { setTestMsg({ ok: false, text: 'Indica un email de destino' }); return }
    setTesting(true); setTestMsg(null)
    try {
      const r = await api.post('/auth/test-email/', { to })
      setTestMsg({
        ok: true,
        text: r.data.detail || `Email enviado a ${to}`,
        warning: r.data.warning,
        meta: r.data.message_id ? `ID: ${r.data.message_id}` : null,
      })
    } catch (err) {
      const detail = err.response?.data?.detail
        || (typeof err.response?.data === 'object' ? JSON.stringify(err.response.data) : null)
        || err.message
        || 'Error al enviar'
      setTestMsg({ ok: false, text: detail })
    } finally {
      setTesting(false)
    }
  }

  async function changePassword(e) {
    e.preventDefault()
    setPwMsg(null)
    try {
      await api.post('/auth/change-password/', pwForm)
      setPwMsg({ ok: true, text: 'Contraseña actualizada' })
      setPwForm({ current_password: '', new_password: '' })
    } catch (err) {
      setPwMsg({ ok: false, text: err.response?.data?.detail || 'Error' })
    }
  }

  async function exportDb() {
    try {
      // Auth is via HttpOnly cookies (see CookieJWTAuthentication), so just
      // include credentials — there is no bearer token in localStorage.
      const res = await fetch('/api/auth/db-export/', { credentials: 'include' })
      if (!res.ok) { alert('No autorizado o error en la descarga'); return }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `mailerup-${new Date().toISOString().slice(0,10)}.sqlite3`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      alert('Error al descargar')
    }
  }

  if (!me) return <div role="status" aria-live="polite" className="text-gray-500 dark:text-slate-400">Cargando…</div>

  const isAdmin = !!me.is_admin
  const isSmtp = currentProvider?.kind === 'smtp'
  const isApi = currentProvider?.kind === 'api'

  return (
    <div className="max-w-3xl space-y-8">
      <h1 className="text-2xl font-semibold">Ajustes</h1>

      <section className="card p-6 space-y-4">
        <h2 className="font-semibold">Perfil</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="label">Email</label>
            <input className="input bg-gray-50 dark:bg-slate-800" value={me.email} disabled />
          </div>
          <div>
            <label className="label">Usuario</label>
            <input className="input" value={me.username || ''} onChange={(e) => setMeField('username', e.target.value)} />
          </div>
          <div>
            <label className="label">Empresa</label>
            <input className="input" value={me.company || ''} onChange={(e) => setMeField('company', e.target.value)} />
          </div>
          <div>
            <label className="label">Zona horaria</label>
            <input className="input" value={me.timezone || ''} onChange={(e) => setMeField('timezone', e.target.value)} />
          </div>
        </div>
      </section>

      <section className="card p-6 space-y-4">
        <h2 className="font-semibold">Remitente por defecto</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="label">Nombre del remitente</label>
            <input className="input" value={me.from_name || ''} onChange={(e) => setMeField('from_name', e.target.value)}
              placeholder="Ej: Mario de MailerUp" />
          </div>
          <div>
            <label className="label flex items-center justify-between">
              <span>Email del remitente</span>
              {me.smtp_user && me.from_email !== me.smtp_user && (
                <button
                  type="button"
                  onClick={() => setMeField('from_email', me.smtp_user)}
                  className="text-xs text-primary-600 hover:underline font-normal normal-case"
                >
                  Usar el del SMTP ({me.smtp_user})
                </button>
              )}
            </label>
            <input className="input" type="email" value={me.from_email || ''} onChange={(e) => setMeField('from_email', e.target.value)}
              placeholder={me.smtp_user || "hola@tudominio.com"} />
            <FromEmailWarning fromEmail={me.from_email} smtpUser={me.smtp_user} />
          </div>
        </div>
      </section>

      {isAdmin && (
      <section className="card p-6 space-y-4">
        <h2 className="font-semibold">Proveedor de email</h2>
        <p className="text-xs text-gray-500 dark:text-slate-400">
          Elige cómo se envían tus correos. Si tienes hosting con Raiola Networks, selecciona "Raiola Networks" y configura el SMTP que te dieron.
        </p>
        <div>
          <label className="label">Proveedor</label>
          <select className="input" value={me.email_provider} onChange={(e) => pickProvider(e.target.value)}>
            {providers.map((p) => (
              <option key={p.key} value={p.key}>{p.label}</option>
            ))}
          </select>
          {currentProvider?.hint && (
            <p className="text-xs text-gray-500 dark:text-slate-400 mt-1.5">💡 {currentProvider.hint}</p>
          )}
        </div>

        {isSmtp && (
          <div className="space-y-3 border-t border-gray-100 dark:border-slate-700 pt-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="sm:col-span-2">
                <label className="label">Servidor SMTP</label>
                <input className="input" value={me.smtp_host || ''}
                  onChange={(e) => setMeField('smtp_host', e.target.value)} placeholder="smtp.tudominio.com" />
              </div>
              <div>
                <label className="label">Puerto</label>
                <input className="input" type="number" value={me.smtp_port || 587}
                  onChange={(e) => setMeField('smtp_port', parseInt(e.target.value || '0', 10))} />
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="label">Usuario</label>
                <input className="input" value={me.smtp_user || ''}
                  onChange={(e) => setMeField('smtp_user', e.target.value)} placeholder="usuario@tudominio.com" />
              </div>
              <div>
                <label className="label">Contraseña</label>
                <input className="input" type="password"
                  value={me.smtp_password || ''}
                  onChange={(e) => setMeField('smtp_password', e.target.value)}
                  placeholder={me.smtp_password_set ? '••••••••  (guardada)' : ''} />
              </div>
            </div>
            <div className="flex items-center gap-6 pt-1">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={!!me.smtp_use_tls}
                  onChange={(e) => setMeField('smtp_use_tls', e.target.checked)} />
                STARTTLS (puerto 587)
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={!!me.smtp_use_ssl}
                  onChange={(e) => setMeField('smtp_use_ssl', e.target.checked)} />
                SSL directo (puerto 465)
              </label>
            </div>
          </div>
        )}

        {isApi && me.email_provider === 'brevo' && (
          <div className="border-t border-gray-100 dark:border-slate-700 pt-4">
            <label className="label">Brevo API key</label>
            <input className="input" type="password" value={me.brevo_api_key || ''}
              onChange={(e) => setMeField('brevo_api_key', e.target.value)}
              placeholder={me.brevo_api_key_set ? '••••••••  (guardada)' : 'xkeysib-...'} />
          </div>
        )}
        {isApi && me.email_provider === 'sendgrid' && (
          <div className="border-t border-gray-100 dark:border-slate-700 pt-4">
            <label className="label">SendGrid API key</label>
            <input className="input" type="password" value={me.sendgrid_api_key || ''}
              onChange={(e) => setMeField('sendgrid_api_key', e.target.value)}
              placeholder={me.sendgrid_api_key_set ? '••••••••  (guardada)' : 'SG...'} />
          </div>
        )}

        {currentProvider?.dns && (
          <DnsSetupBlock
            provider={currentProvider}
            fromEmail={me.from_email}
            smtpUser={me.smtp_user}
          />
        )}

        <div className="flex items-center gap-3 pt-2 border-t border-gray-100 dark:border-slate-700">
          <button className="btn-primary" onClick={save} disabled={saving}>
            <Save className="h-4 w-4" /> {saving ? 'Guardando…' : 'Guardar ajustes'}
          </button>
          {savedMsg && <Msg msg={savedMsg} />}
        </div>

        <div className="border-t border-gray-100 dark:border-slate-700 pt-4 space-y-2">
          <label className="label">Enviar email de prueba a</label>
          <div className="flex flex-wrap items-center gap-2">
            <input
              className="input flex-1 min-w-[260px]"
              type="email"
              value={testTo}
              onChange={(e) => setTestTo(e.target.value)}
              placeholder="destinatario@ejemplo.com"
              disabled={me.email_provider === 'local'}
            />
            <button
              className="btn-secondary"
              onClick={testEmail}
              disabled={testing || me.email_provider === 'local' || !testTo}
            >
              <Send className="h-4 w-4" /> {testing ? 'Enviando…' : 'Enviar prueba'}
            </button>
          </div>
          {me.email_provider === 'local' && (
            <p className="text-xs text-gray-400 dark:text-slate-500">
              En modo "Local" no se envían correos. Elige un proveedor SMTP/API para poder probar.
            </p>
          )}
          {testMsg && <Msg msg={testMsg} />}
        </div>
      </section>
      )}

      {isAdmin && (
      <section className="card p-6 space-y-4">
        <h2 className="font-semibold">Ritmo de envío</h2>
        <p className="text-xs text-gray-500 dark:text-slate-400">
          Las campañas se envían poco a poco para no saturar tu proveedor SMTP. Aquí defines
          cuántos correos como máximo se mandan <strong>por hora</strong>. El cambio se aplica al instante,
          sin reiniciar. Ajústalo por debajo del límite de tu hosting (consulta su tope por hora y por día).
        </p>
        <div className="max-w-xs">
          <label className="label">Correos por hora</label>
          <input
            className="input"
            type="number"
            min={1}
            max={100000}
            value={me.send_rate_per_hour ?? 300}
            onChange={(e) => setMeField('send_rate_per_hour', Math.max(1, parseInt(e.target.value || '1', 10)))}
          />
          <p className="text-xs text-gray-400 dark:text-slate-500 mt-1">
            {me.send_rate_per_hour
              ? `≈ ${Math.round(3600 / me.send_rate_per_hour)}s entre correos · ${me.send_rate_per_hour * 24} al día como máximo si envía 24h seguidas`
              : ''}
          </p>
        </div>
        <div className="flex items-center gap-3 pt-2 border-t border-gray-100 dark:border-slate-700">
          <button className="btn-primary" onClick={save} disabled={saving}>
            <Save className="h-4 w-4" /> {saving ? 'Guardando…' : 'Guardar ajustes'}
          </button>
        </div>
      </section>
      )}

      {isAdmin && (
      <section className="card p-6 space-y-4">
        <h2 className="font-semibold">Pie de correo</h2>
        <p className="text-xs text-gray-500 dark:text-slate-400">
          Estos datos se insertan en el bloque de baja al pulsar el botón <em>"Insertar pie con baja"</em> del editor de campañas.
          La ley (GDPR / CAN-SPAM) exige incluir dirección postal e identificación del remitente.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="label">Nombre de la empresa / remitente</label>
            <input className="input" value={me.footer_company || ''}
              onChange={(e) => setMeField('footer_company', e.target.value)}
              placeholder="Ej: MailerUp S.L." />
          </div>
          <div>
            <label className="label">Texto del enlace de baja</label>
            <input className="input" value={me.footer_button_label || ''}
              onChange={(e) => setMeField('footer_button_label', e.target.value)}
              placeholder="Darse de baja" />
          </div>
        </div>
        <div>
          <label className="label">Dirección postal</label>
          <input className="input" value={me.footer_address || ''}
            onChange={(e) => setMeField('footer_address', e.target.value)}
            placeholder="Calle Mayor 1, 28001 Madrid, España" />
        </div>
        <div>
          <label className="label">Texto de la baja</label>
          <textarea className="input" rows={2} value={me.footer_unsubscribe_text || ''}
            onChange={(e) => setMeField('footer_unsubscribe_text', e.target.value)}
            placeholder="Si ya no quieres recibir nuestros correos, puedes darte de baja en cualquier momento." />
        </div>

        <div>
          <label className="label">Línea "reenviar" (opcional)</label>
          <input className="input" value={me.footer_forward_text || ''}
            onChange={(e) => setMeField('footer_forward_text', e.target.value)}
            placeholder="Si te ha gustado este email, reenvíaselo a un compañero." />
        </div>
        <div>
          <label className="label">Línea "suscribirse" (opcional)</label>
          <input className="input" value={me.footer_subscribe_text || ''}
            onChange={(e) => setMeField('footer_subscribe_text', e.target.value)}
            placeholder="Si te han reenviado este email y quieres recibir más, ve a tu-dominio.com/newsletter" />
          <p className="text-xs text-gray-400 dark:text-slate-500 mt-1">Las URLs se convierten en enlaces automáticamente. Déjalo vacío para no mostrar esta línea.</p>
        </div>

        <div className="rounded-md border border-gray-200 dark:border-slate-700 bg-gray-50 dark:bg-slate-900 p-4">
          <div className="text-xs font-medium text-gray-500 dark:text-slate-400 mb-2">VISTA PREVIA</div>
          <FooterPreview footer={{
            company: me.footer_company,
            address: me.footer_address,
            unsubscribe_text: me.footer_unsubscribe_text,
            button_label: me.footer_button_label,
            forward_text: me.footer_forward_text,
            subscribe_text: me.footer_subscribe_text,
          }} />
        </div>

        <div className="flex items-center gap-3 pt-2 border-t border-gray-100 dark:border-slate-700">
          <button className="btn-primary" onClick={save} disabled={saving}>
            <Save className="h-4 w-4" /> {saving ? 'Guardando…' : 'Guardar ajustes'}
          </button>
        </div>
      </section>
      )}

      {isAdmin && <ApiKeysSection />}

      {isAdmin && (
      <section className="card p-6 space-y-3">
        <div className="flex items-center gap-3">
          <Database className="h-5 w-5 text-primary-600" />
          <h2 className="font-semibold">Copia de seguridad</h2>
        </div>
        <p className="text-sm text-gray-600 dark:text-slate-300">
          Descarga un volcado completo de la base de datos SQLite. Solo accesible para administradores.
        </p>
        <p className="text-xs text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-800 rounded px-2 py-1.5">
          ⚠ Contiene credenciales SMTP cifradas, emails de suscriptores y datos personales. Guárdalo en un sitio seguro.
        </p>
        <button className="btn-secondary" onClick={exportDb}>
          <Database className="h-4 w-4" /> Exportar DB
        </button>
      </section>
      )}

      <section className="card p-6 space-y-4">
        <h2 className="font-semibold">Cambiar contraseña</h2>
        <form onSubmit={changePassword} className="space-y-3 max-w-md">
          <div>
            <label className="label">Contraseña actual</label>
            <input className="input" type="password" required value={pwForm.current_password}
              onChange={(e) => setPwForm({ ...pwForm, current_password: e.target.value })} />
          </div>
          <div>
            <label className="label">Nueva contraseña</label>
            <input className="input" type="password" required minLength={8} value={pwForm.new_password}
              onChange={(e) => setPwForm({ ...pwForm, new_password: e.target.value })} />
          </div>
          <div className="flex items-center gap-3">
            <button className="btn-primary">Actualizar</button>
            {pwMsg && <Msg msg={pwMsg} />}
          </div>
        </form>
      </section>
    </div>
  )
}

function FromEmailWarning({ fromEmail, smtpUser }) {
  if (!fromEmail || !smtpUser || !fromEmail.includes('@') || !smtpUser.includes('@')) return null
  const fromDomain = fromEmail.split('@')[1].toLowerCase()
  const smtpDomain = smtpUser.split('@')[1].toLowerCase()
  if (fromDomain === smtpDomain) return null
  return (
    <p className="mt-1.5 text-xs text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-800 rounded px-2 py-1.5">
      ⚠ El dominio del remitente (<code>@{fromDomain}</code>) no coincide con el del SMTP
      (<code>@{smtpDomain}</code>). Gmail/Outlook descartarán tus correos por SPF. Usa un
      email <code>@{smtpDomain}</code>.
    </p>
  )
}

function FooterPreview({ footer }) {
  const company = footer.company || 'Tu empresa'
  const address = footer.address || 'Tu dirección postal'
  const text = footer.unsubscribe_text || 'Si ya no quieres recibir nuestros correos, puedes darte de baja en cualquier momento.'
  const label = footer.button_label || 'Darse de baja'
  const forward = footer.forward_text
  const subscribe = footer.subscribe_text
  return (
    <div style={{ textAlign: 'center', color: '#94a3b8', fontSize: 13, lineHeight: 1.6 }}>
      <div style={{ fontWeight: 600 }}>{company}</div>
      <div>{address}</div>
      {forward && <div style={{ marginTop: 10 }}>▸ {forward}</div>}
      {subscribe && <div style={{ marginTop: 4 }}>▸ {subscribe}</div>}
      {/* Línea de baja: más pequeña y separada → discreta. Enlace sin subrayar. */}
      <div style={{ marginTop: 18, fontSize: 11 }}>
        {text}{' '}
        <a
          href="#preview"
          onClick={(e) => e.preventDefault()}
          style={{ color: 'inherit', textDecoration: 'none' }}
        >
          {label}
        </a>.
      </div>
    </div>
  )
}

function ApiKeysSection() {
  const [keys, setKeys] = useState(null)
  const [name, setName] = useState('')
  const [creating, setCreating] = useState(false)
  const [newKey, setNewKey] = useState(null)   // { key, prefix } — mostrado una sola vez
  const [copied, setCopied] = useState(false)
  const [err, setErr] = useState(null)

  const endpoint = `${window.location.origin}/api/public/subscribers/`

  async function load() {
    try {
      const r = await api.get('/auth/api-keys/')
      setKeys(r.data.results || r.data)   // paginado o lista
    } catch {
      setErr('No se pudieron cargar las claves')
    }
  }
  useEffect(() => { load() }, [])

  async function create() {
    setCreating(true); setErr(null); setNewKey(null); setCopied(false)
    try {
      const r = await api.post('/auth/api-keys/', { name: name.trim() })
      setNewKey(r.data)   // incluye el campo `key` en claro (solo esta vez)
      setName('')
      load()
    } catch (e) {
      setErr(e.response?.data ? JSON.stringify(e.response.data) : 'Error creando la clave')
    } finally {
      setCreating(false)
    }
  }

  async function revoke(id) {
    if (!window.confirm('¿Revocar esta clave? Los sistemas que la usen dejarán de funcionar.')) return
    try {
      await api.delete(`/auth/api-keys/${id}/`)
      load()
    } catch {
      setErr('No se pudo revocar la clave')
    }
  }

  function copyKey() {
    if (!newKey?.key) return
    navigator.clipboard.writeText(newKey.key).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <section className="card p-6 space-y-4">
      <div className="flex items-center gap-3">
        <Key className="h-5 w-5 text-primary-600" />
        <h2 className="font-semibold">Claves API</h2>
      </div>
      <p className="text-sm text-gray-600 dark:text-slate-300">
        Genera claves para que un sistema externo (tu web, un CRM, Zapier…) dé de alta suscriptores
        mediante una petición <code>POST</code>. La clave se muestra <strong>una sola vez</strong>;
        guárdala en un sitio seguro. Si la pierdes, revócala y crea otra.
      </p>

      <div className="rounded-md border border-gray-200 dark:border-slate-700 bg-gray-50 dark:bg-slate-900 p-3 text-xs font-mono overflow-x-auto">
        <div className="text-gray-500 dark:text-slate-400 mb-1 font-sans">Uso:</div>
        curl -X POST {endpoint} \<br />
        &nbsp;&nbsp;-H "Authorization: Bearer &lt;TU_CLAVE&gt;" \<br />
        &nbsp;&nbsp;-H "Content-Type: application/json" \<br />
        &nbsp;&nbsp;-d '{'{'}"email":"nuevo@ejemplo.com","first_name":"Ana"{'}'}'
      </div>

      {/* Alta de clave */}
      <div className="flex flex-wrap items-end gap-2 border-t border-gray-100 dark:border-slate-700 pt-4">
        <div className="flex-1 min-w-[220px]">
          <label className="label">Nombre (para identificarla)</label>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)}
            placeholder="Ej: Landing de captación" maxLength={100} />
        </div>
        <button className="btn-primary" onClick={create} disabled={creating}>
          <Key className="h-4 w-4" /> {creating ? 'Creando…' : 'Crear clave'}
        </button>
      </div>

      {newKey?.key && (
        <div className="rounded-md border border-green-300 dark:border-green-700 bg-green-50 dark:bg-green-900/30 p-3 space-y-2">
          <div className="text-xs font-medium text-green-800 dark:text-green-300">
            ✓ Clave creada. Cópiala ahora — no volverá a mostrarse.
          </div>
          <div className="flex items-center gap-2">
            <code className="flex-1 text-xs font-mono break-all bg-white dark:bg-slate-800 rounded px-2 py-1.5 border border-green-200 dark:border-green-800">
              {newKey.key}
            </code>
            <button className="btn-secondary shrink-0" onClick={copyKey}>
              <Copy className="h-4 w-4" /> {copied ? 'Copiado' : 'Copiar'}
            </button>
          </div>
        </div>
      )}

      {err && <p className="text-sm text-red-600 dark:text-red-400">{err}</p>}

      {/* Listado */}
      <div className="border-t border-gray-100 dark:border-slate-700 pt-4">
        {keys === null ? (
          <p className="text-sm text-gray-400 dark:text-slate-500">Cargando…</p>
        ) : keys.length === 0 ? (
          <p className="text-sm text-gray-400 dark:text-slate-500">Aún no hay claves creadas.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 dark:text-slate-400 border-b border-gray-100 dark:border-slate-700">
                <th className="py-2">Nombre</th>
                <th className="py-2">Prefijo</th>
                <th className="py-2">Creada</th>
                <th className="py-2">Último uso</th>
                <th className="py-2"></th>
              </tr>
            </thead>
            <tbody>
              {keys.map((k) => (
                <tr key={k.id} className="border-b border-gray-50 dark:border-slate-800">
                  <td className="py-2">{k.name || <span className="text-gray-400">—</span>}</td>
                  <td className="py-2 font-mono text-xs">{k.prefix}…</td>
                  <td className="py-2 text-xs text-gray-500 dark:text-slate-400">
                    {k.created_at ? new Date(k.created_at).toLocaleDateString() : ''}
                  </td>
                  <td className="py-2 text-xs text-gray-500 dark:text-slate-400">
                    {k.last_used_at ? new Date(k.last_used_at).toLocaleString() : 'Nunca'}
                  </td>
                  <td className="py-2 text-right">
                    <button
                      className="text-red-600 hover:text-red-700 dark:text-red-400 inline-flex items-center gap-1 text-xs"
                      onClick={() => revoke(k.id)}
                    >
                      <Trash2 className="h-4 w-4" /> Revocar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  )
}

function Msg({ msg }) {
  return (
    <div className={`text-sm space-y-1 ${msg.ok ? 'text-green-700 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
      <div className="inline-flex items-start gap-1.5">
        {msg.ok ? <CheckCircle2 className="h-4 w-4 mt-0.5 flex-shrink-0" /> : <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />}
        <span>{msg.text}</span>
      </div>
      {msg.warning && (
        <div className="ml-5 text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-800 rounded px-2 py-1 text-xs">
          ⚠ {msg.warning}
        </div>
      )}
      {msg.meta && <div className="ml-5 text-xs text-gray-400 dark:text-slate-500 font-mono">{msg.meta}</div>}
    </div>
  )
}
