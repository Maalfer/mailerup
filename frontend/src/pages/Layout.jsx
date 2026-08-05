import { useState, useEffect } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { Users, Megaphone, BarChart3, Activity, Settings as SettingsIcon, ShieldUser, LogOut, ClipboardList, Zap, Menu, X, Sun, Moon, HardDrive, Bot } from 'lucide-react'
import { useAuth } from '../auth.jsx'
import { REPO_URL } from '../repo.js'
import GithubMark from '../components/GithubMark.jsx'

const baseItems = [
  { to: '/subscribers', label: 'Suscriptores', icon: Users },
  { to: '/campaigns',   label: 'Campañas',     icon: Megaphone },
  { to: '/analytics',   label: 'Analíticas',     icon: BarChart3 },
  { to: '/deliverability', label: 'Entregabilidad', icon: Activity },
  { to: '/forms',       label: 'Formularios',    icon: ClipboardList },
  { to: '/automations', label: 'Automatizaciones', icon: Zap },
]
const adminItems = [
  { to: '/users',       label: 'Gestión usuarios', icon: ShieldUser },
]
const storageItem  = { to: '/storage',  label: 'Almacenamiento', icon: HardDrive }
const mcpItem      = { to: '/mcp',      label: 'Asistente IA (MCP)', icon: Bot }
const settingsItem = { to: '/settings', label: 'Ajustes', icon: SettingsIcon }

export default function Layout() {
  const { user, logout } = useAuth()
  const nav = useNavigate()
  const items = [...baseItems, ...(user?.is_admin ? adminItems : []), storageItem, mcpItem, settingsItem]
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [isDark, setIsDark] = useState(() => {
    if (typeof localStorage !== 'undefined') {
      const saved = localStorage.getItem('mailerup-theme')
      if (saved) return saved === 'dark'
    }
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  })

  useEffect(() => {
    document.documentElement.classList.toggle('dark', isDark)
    localStorage.setItem('mailerup-theme', isDark ? 'dark' : 'light')
  }, [isDark])

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-slate-900">
      {/* Overlay para móvil cuando sidebar está abierto */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed inset-y-0 left-0 z-30 flex h-full w-64 flex-col border-r border-gray-200 bg-white
        dark:bg-slate-900 dark:border-slate-700
        transform transition-transform duration-200 ease-in-out
        lg:relative lg:translate-x-0
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        <div className="flex h-16 items-center gap-3 border-b border-gray-200 dark:border-slate-700 px-5">
          <img src="/logo.png?v=3" alt="MailerUp" className="h-9 w-9 object-contain rounded-lg dark:bg-white dark:p-[3px] dark:shadow-sm" />
          <span className="text-lg font-semibold">MailerUp</span>
          <span className="text-[10px] font-medium leading-none text-gray-400 dark:text-slate-500 self-end mb-1.5">v{__APP_VERSION__}</span>
          {/* Botón cerrar en móvil */}
          <button
            className="ml-auto lg:hidden text-gray-400 hover:text-gray-600 dark:text-slate-400 dark:hover:text-slate-200"
            aria-label="Cerrar menú"
            onClick={() => setSidebarOpen(false)}
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <nav aria-label="Navegación principal" className="flex-1 overflow-y-auto p-3 space-y-1">
          {items.map((it) => (
            <NavLink
              key={it.to}
              to={it.to}
              onClick={() => setSidebarOpen(false)}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-primary-50 text-primary-700 dark:bg-slate-800 dark:text-white'
                    : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200'
                }`
              }
            >
              <it.icon className="h-5 w-5" />
              {it.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-gray-200 dark:border-slate-700 p-3">
          <div className="px-3 py-2 text-xs text-gray-500 dark:text-slate-400 truncate flex items-center gap-2">
            <span className="truncate">{user?.email}</span>
            {user?.is_admin && (
              <span className="badge bg-primary-100 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300">admin</span>
            )}
          </div>
          <button
            aria-label={isDark ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'}
            onClick={() => setIsDark(!isDark)}
            className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-gray-600 hover:bg-gray-100 dark:text-slate-400 dark:hover:bg-slate-800 w-full"
          >
            {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            {isDark ? 'Modo claro' : 'Modo oscuro'}
          </button>
          <button
            aria-label="Cerrar sesión"
            onClick={() => { logout(); nav('/login') }}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-gray-600 hover:bg-gray-100 dark:text-slate-400 dark:hover:bg-slate-800"
          >
            <LogOut className="h-4 w-4" /> Cerrar sesión
          </button>
          <a
            href={REPO_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="group mt-1 flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-gray-500 hover:bg-gray-100 hover:text-gray-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200"
          >
            <GithubMark className="h-4 w-4 transition-transform group-hover:scale-110" />
            <span>Ver en GitHub</span>
          </a>
        </div>
      </aside>

      {/* Área principal */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Topbar en móvil con botón hamburguesa */}
        <header className="flex h-14 items-center gap-3 border-b border-gray-200 bg-white dark:bg-slate-900 dark:border-slate-700 px-4 lg:hidden flex-shrink-0">
          <button
            aria-label="Abrir menú"
            onClick={() => setSidebarOpen(true)}
            className="text-gray-500 hover:text-gray-900 dark:text-slate-400 dark:hover:text-slate-200"
          >
            <Menu className="h-6 w-6" />
          </button>
          <img src="/logo.png?v=3" alt="MailerUp" className="h-7 w-7 object-contain rounded-md dark:bg-white dark:p-[3px] dark:shadow-sm" />
          <span className="font-semibold text-sm">MailerUp</span>
          <button
            aria-label={isDark ? 'Modo claro' : 'Modo oscuro'}
            onClick={() => setIsDark(!isDark)}
            className="ml-auto p-2 rounded-lg text-gray-500 hover:bg-gray-100 dark:text-slate-400 dark:hover:bg-slate-800"
          >
            {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </button>
        </header>

        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 dark:bg-slate-900">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
