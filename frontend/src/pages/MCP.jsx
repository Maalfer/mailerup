import { useState } from 'react'
import { Bot, Copy, Check, Terminal, Sparkles, ExternalLink, Download, Plug, ShieldCheck } from 'lucide-react'
import { useAuth } from '../auth.jsx'

const REPO_URL = 'https://github.com/Maalfer/mailerup'

// Bloque de código con botón de copiar.
function CodeBlock({ code }) {
  const [copied, setCopied] = useState(false)
  const copy = () =>
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  return (
    <div className="relative">
      <pre className="text-xs font-mono bg-gray-900 text-gray-100 dark:bg-slate-950 rounded-lg p-3 pr-12 overflow-x-auto whitespace-pre">{code}</pre>
      <button
        type="button"
        onClick={copy}
        aria-label="Copiar"
        title="Copiar al portapapeles"
        className="absolute top-2 right-2 p-1.5 rounded-md bg-gray-700/70 hover:bg-gray-600 text-gray-100 transition-colors"
      >
        {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
      </button>
    </div>
  )
}

// Campo de conexión (valor auto-rellenado) con botón de copiar.
function Field({ label, value, mono = true }) {
  const [copied, setCopied] = useState(false)
  const copy = () =>
    navigator.clipboard.writeText(value).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  return (
    <div>
      <div className="text-xs font-medium text-gray-500 dark:text-slate-400 mb-1">{label}</div>
      <div className="flex items-center gap-2">
        <code className={`flex-1 ${mono ? 'font-mono' : ''} text-sm break-all bg-gray-50 dark:bg-slate-800 rounded-lg px-3 py-2 border border-gray-200 dark:border-slate-700`}>
          {value}
        </code>
        <button
          type="button"
          onClick={copy}
          aria-label={`Copiar ${label}`}
          className="btn-secondary text-xs py-2 px-2.5 flex items-center gap-1 flex-shrink-0"
        >
          {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
        </button>
      </div>
    </div>
  )
}

export default function MCP() {
  const { user } = useAuth()
  const baseUrl = window.location.origin
  const email = user?.email || 'tu-email@ejemplo.com'
  const isAdmin = !!user?.is_admin

  const setupCmd = `git clone ${REPO_URL}.git
cd mailerup/mcp
bash setup.sh`

  const claudeCodeCmd = `claude mcp add mailerup \\
  -e MAILERUP_BASE_URL=${baseUrl} \\
  -e MAILERUP_EMAIL=${email} \\
  -e MAILERUP_PASSWORD='TU_CONTRASEÑA' \\
  -- "$(pwd)/.venv/bin/python" -m mailerup_mcp`

  const desktopJson = `{
  "mcpServers": {
    "mailerup": {
      "command": "/ruta/a/mailerup/mcp/.venv/bin/python",
      "args": ["-m", "mailerup_mcp"],
      "env": {
        "MAILERUP_BASE_URL": "${baseUrl}",
        "MAILERUP_EMAIL": "${email}",
        "MAILERUP_PASSWORD": "TU_CONTRASEÑA"
      }
    }
  }
}`

  const examples = [
    '«Crea un grupo "Clientes 2026" e impórtale estos emails.»',
    '«Redacta una campaña de bienvenida en HTML y prográmala para el lunes a las 9:00.»',
    '«¿Qué campaña tuvo mejor tasa de apertura este mes? Enséñame los enlaces más clicados.»',
    '«Monta una automatización de 3 pasos enganchada al formulario de la landing.»',
    '«Haz un backup completo de la newsletter antes de tocar nada.»',
  ]

  const capabilities = [
    ['Campañas', 'Crear, editar, enviar, programar, pausar/reanudar, duplicar, prueba y vista previa.'],
    ['Suscriptores y grupos', 'Alta, edición, import/export CSV, mover, borrado masivo, baja engagement.'],
    ['Automatizaciones', 'Secuencias y pasos con retrasos, vinculadas a formularios.'],
    ['Formularios', 'Crear y editar formularios de suscripción y su código embed.'],
    ['Analíticas', 'KPIs, ranking de campañas por métrica, entregabilidad y series temporales.'],
    ['Cuenta y ajustes', 'Remitente, proveedor SMTP, pie de correo, email de prueba.'],
    ['Administración', 'Usuarios y Claves API (solo admin).'],
    ['Backups', 'Copia lógica completa (suscriptores, campañas, automatizaciones…).'],
  ]

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold flex items-center gap-2">
          <Bot className="h-6 w-6 text-primary-600 dark:text-primary-400" /> Asistente IA (MCP)
        </h1>
        <p className="text-sm text-gray-500 dark:text-slate-400 mt-1">
          Administra MailerUp desde <strong>Claude</strong> (u otros modelos compatibles con el
          Model Context Protocol) hablando en lenguaje natural: crea y programa campañas, gestiona
          suscriptores, consulta estadísticas o haz backups sin entrar al panel.
        </p>
      </div>

      {/* Qué es / diferencia con Claves API */}
      <div className="card p-5 border-l-4 border-primary-500">
        <p className="text-sm text-gray-700 dark:text-slate-300">
          El <strong>Asistente IA (MCP)</strong> es un pequeño programa que se ejecuta en{' '}
          <strong>tu ordenador</strong> (donde uses Claude) y se conecta a esta instancia con tus
          credenciales del panel. No lo confundas con <strong>Claves API</strong> (en Ajustes): esas
          son para que un sistema externo dé de alta suscriptores; el MCP eres tú administrando
          <em> todo</em> con IA.
        </p>
      </div>

      {/* Datos de conexión */}
      <div className="card p-5 space-y-4">
        <h2 className="font-semibold flex items-center gap-2">
          <Plug className="h-4 w-4 text-primary-600 dark:text-primary-400" /> Datos de conexión
        </h2>
        <p className="text-sm text-gray-500 dark:text-slate-400">
          El MCP se configura con estas tres variables. La URL y tu email ya vienen rellenados con
          los de esta instancia; la contraseña es la misma con la que entras al panel.
        </p>
        <div className="grid gap-3">
          <Field label="MAILERUP_BASE_URL" value={baseUrl} />
          <Field label="MAILERUP_EMAIL" value={email} />
          <div>
            <div className="text-xs font-medium text-gray-500 dark:text-slate-400 mb-1">MAILERUP_PASSWORD</div>
            <code className="block text-sm bg-gray-50 dark:bg-slate-800 rounded-lg px-3 py-2 border border-gray-200 dark:border-slate-700 text-gray-500 dark:text-slate-400">
              Tu contraseña del panel (no se muestra por seguridad)
            </code>
          </div>
        </div>
        {!isAdmin && (
          <p className="text-xs text-amber-600 dark:text-amber-400 flex items-start gap-1.5">
            <ShieldCheck className="h-4 w-4 flex-shrink-0 mt-px" />
            Tu cuenta no es de administrador: el MCP funcionará, pero algunas acciones (gestión de
            usuarios, Claves API y backup completo) requieren una cuenta admin.
          </p>
        )}
      </div>

      {/* Instalación */}
      <div className="card p-5 space-y-5">
        <h2 className="font-semibold flex items-center gap-2">
          <Download className="h-4 w-4 text-primary-600 dark:text-primary-400" /> Instalación (una vez)
        </h2>
        <div className="space-y-2">
          <p className="text-sm text-gray-700 dark:text-slate-300">
            <span className="inline-flex items-center justify-center h-5 w-5 rounded-full bg-primary-100 dark:bg-primary-900/40 text-primary-700 dark:text-primary-300 text-xs font-semibold mr-1.5">1</span>
            Descarga el MCP y crea su entorno (necesitas <strong>Python 3.10+</strong>):
          </p>
          <CodeBlock code={setupCmd} />
        </div>
      </div>

      {/* Registro en el cliente */}
      <div className="card p-5 space-y-5">
        <h2 className="font-semibold flex items-center gap-2">
          <Terminal className="h-4 w-4 text-primary-600 dark:text-primary-400" /> Conéctalo a tu cliente de IA
        </h2>

        <div className="space-y-2">
          <p className="text-sm font-medium text-gray-800 dark:text-slate-200">
            <span className="inline-flex items-center justify-center h-5 w-5 rounded-full bg-primary-100 dark:bg-primary-900/40 text-primary-700 dark:text-primary-300 text-xs font-semibold mr-1.5">2</span>
            Claude Code (terminal) — desde la carpeta <code className="text-xs">mcp/</code>:
          </p>
          <CodeBlock code={claudeCodeCmd} />
          <p className="text-xs text-gray-500 dark:text-slate-400">
            Sustituye <code>TU_CONTRASEÑA</code> por la de tu cuenta. Comprueba con <code>claude mcp list</code>.
          </p>
        </div>

        <div className="space-y-2">
          <p className="text-sm font-medium text-gray-800 dark:text-slate-200">
            Claude Desktop — añade esto a <code className="text-xs">claude_desktop_config.json</code> y reinicia:
          </p>
          <CodeBlock code={desktopJson} />
        </div>
      </div>

      {/* Qué puedes hacer */}
      <div className="card p-5 space-y-4">
        <h2 className="font-semibold flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-primary-600 dark:text-primary-400" /> Qué puedes pedirle
        </h2>
        <ul className="space-y-1.5">
          {examples.map((ex, i) => (
            <li key={i} className="text-sm text-gray-700 dark:text-slate-300 flex gap-2">
              <span className="text-primary-500">›</span>
              <span>{ex}</span>
            </li>
          ))}
        </ul>
        <div className="grid sm:grid-cols-2 gap-x-6 gap-y-2 pt-2 border-t border-gray-100 dark:border-slate-700">
          {capabilities.map(([title, desc]) => (
            <div key={title} className="text-sm">
              <span className="font-medium text-gray-800 dark:text-slate-200">{title}: </span>
              <span className="text-gray-500 dark:text-slate-400">{desc}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <a href={`${REPO_URL}/blob/main/mcp/README.md`} target="_blank" rel="noopener noreferrer" className="btn-secondary text-sm inline-flex items-center gap-1.5">
          <ExternalLink className="h-4 w-4" /> Documentación completa del MCP
        </a>
        <span className="text-xs text-gray-400 dark:text-slate-500">
          Trata tu contraseña como un secreto: pásala solo por la configuración del cliente de IA.
        </span>
      </div>
    </div>
  )
}
