import { useEffect, useRef, useState } from 'react'
import { HardDrive, Paperclip, Trash2, Link2, Check, Loader2, Upload } from 'lucide-react'
import api, { fetchAll as fetchAllPages } from '../api'
import Pager from '../components/Pager'

const PAGE_SIZE = 12

function fmt(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  if (bytes < 1024 * 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + ' MB'
  return (bytes / 1024 / 1024 / 1024).toFixed(2) + ' GB'
}

function fmtDate(iso) {
  return new Date(iso).toLocaleString('es-ES', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function DiskBar({ label, used, total, color }) {
  const pct = total > 0 ? Math.min(100, (used / total) * 100) : 0
  const warn = pct > 85
  const barColor = warn ? 'bg-red-500' : color
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="font-medium text-gray-700 dark:text-slate-300">{label}</span>
        <span className="text-gray-500 dark:text-slate-400">{fmt(used)} / {fmt(total)}</span>
      </div>
      <div className="h-2 w-full rounded-full bg-gray-200 dark:bg-slate-700 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColor}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="flex justify-between text-xs mt-1">
        <span className={warn ? 'text-red-500 font-medium' : 'text-gray-400 dark:text-slate-500'}>
          {pct.toFixed(1)}% usado
        </span>
        <span className="text-gray-400 dark:text-slate-500">{fmt(total - used)} libres</span>
      </div>
    </div>
  )
}

export default function Storage() {
  const [resources, setResources] = useState([])
  const [disk, setDisk] = useState(null)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [copiedId, setCopiedId] = useState(null)
  const [error, setError] = useState('')
  const [page, setPage] = useState(1)
  const fileInputRef = useRef()

  useEffect(() => { fetchAll() }, [])

  async function fetchAll() {
    setLoading(true)
    try {
      // fetchAllPages recorre TODAS las páginas DRF (antes ?page_size=200 se
      // ignoraba y solo se veían 25 de hasta 200 recursos).
      const [diskRes, allResources] = await Promise.all([
        api.get('/campaigns/resources/disk-usage/'),
        fetchAllPages('/campaigns/resources/'),
      ])
      setDisk(diskRes.data)
      setResources(allResources)
    } catch {
      setError('No se pudieron cargar los datos.')
    } finally {
      setLoading(false)
    }
  }

  async function handleUpload(e) {
    const files = Array.from(e.target.files || [])
    if (!files.length) return
    setError('')
    setUploading(true)
    try {
      const uploaded = []
      for (const file of files) {
        const fd = new FormData()
        fd.append('file', file)
        const r = await api.post('/campaigns/resources/', fd)
        uploaded.push(r.data)
      }
      setResources(prev => [...uploaded, ...prev])
      setPage(1) // los recién subidos van al principio
      // Refresh disk stats
      api.get('/campaigns/resources/disk-usage/').then(r => setDisk(r.data))
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al subir el archivo.')
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  async function deleteResource(resource) {
    if (!confirm(`¿Eliminar "${resource.original_name}"? Esta acción no se puede deshacer.`)) return
    try {
      await api.delete(`/campaigns/resources/${resource.id}/`)
      setResources(prev => prev.filter(r => r.id !== resource.id))
      api.get('/campaigns/resources/disk-usage/').then(r => setDisk(r.data))
    } catch {
      alert('No se pudo eliminar el recurso.')
    }
  }

  function copyLink(resource) {
    const fullUrl = window.location.origin + resource.url
    navigator.clipboard.writeText(fullUrl).then(() => {
      setCopiedId(resource.id)
      setTimeout(() => setCopiedId(null), 2000)
    })
  }

  const totalResourcesSize = resources.reduce((s, r) => s + (r.file_size || 0), 0)
  const totalPages = Math.max(1, Math.ceil(resources.length / PAGE_SIZE))
  const safePage = Math.min(page, totalPages)
  const pageItems = resources.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE)

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <HardDrive className="h-6 w-6 text-primary-600 dark:text-primary-400" />
            Almacenamiento
          </h1>
          {!loading && (
            <p className="mt-1 text-sm text-gray-500 dark:text-slate-400">
              {resources.length} {resources.length === 1 ? 'archivo' : 'archivos'} · {fmt(totalResourcesSize)} en recursos
            </p>
          )}
        </div>
        <div>
          <input ref={fileInputRef} type="file" multiple className="hidden" onChange={handleUpload} />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-60 dark:bg-primary-500 dark:hover:bg-primary-600"
          >
            {uploading
              ? <><Loader2 className="h-4 w-4 animate-spin" /> Subiendo…</>
              : <><Upload className="h-4 w-4" /> Subir archivo</>}
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Disk usage cards */}
      {disk && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="rounded-xl border border-gray-200 bg-white dark:border-slate-700 dark:bg-slate-800 p-5 space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 dark:text-slate-500">
              Disco del servidor (VPS)
            </p>
            <DiskBar
              label="Espacio total"
              used={disk.used}
              total={disk.total}
              color="bg-primary-500"
            />
            <div className="grid grid-cols-3 gap-2 pt-1">
              <div className="text-center">
                <p className="text-lg font-bold text-gray-900 dark:text-white">{fmt(disk.total)}</p>
                <p className="text-xs text-gray-400 dark:text-slate-500">Total</p>
              </div>
              <div className="text-center">
                <p className="text-lg font-bold text-gray-900 dark:text-white">{fmt(disk.used)}</p>
                <p className="text-xs text-gray-400 dark:text-slate-500">Usado</p>
              </div>
              <div className="text-center">
                <p className="text-lg font-bold text-green-600 dark:text-green-400">{fmt(disk.free)}</p>
                <p className="text-xs text-gray-400 dark:text-slate-500">Libre</p>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-gray-200 bg-white dark:border-slate-700 dark:bg-slate-800 p-5 space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 dark:text-slate-500">
              Recursos adjuntos (newsletter)
            </p>
            <DiskBar
              label="Espacio en recursos"
              used={disk.resources_bytes}
              total={disk.total}
              color="bg-amber-500"
            />
            <div className="grid grid-cols-3 gap-2 pt-1">
              <div className="text-center">
                <p className="text-lg font-bold text-gray-900 dark:text-white">{resources.length}</p>
                <p className="text-xs text-gray-400 dark:text-slate-500">Archivos</p>
              </div>
              <div className="text-center">
                <p className="text-lg font-bold text-gray-900 dark:text-white">{fmt(disk.resources_bytes)}</p>
                <p className="text-xs text-gray-400 dark:text-slate-500">Ocupado</p>
              </div>
              <div className="text-center">
                <p className="text-lg font-bold text-gray-900 dark:text-white">
                  {disk.total > 0 ? ((disk.resources_bytes / disk.total) * 100).toFixed(2) + '%' : '—'}
                </p>
                <p className="text-xs text-gray-400 dark:text-slate-500">Del VPS</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* File list */}
      <div className="rounded-xl border border-gray-200 bg-white dark:border-slate-700 dark:bg-slate-800 overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-16 text-gray-400 dark:text-slate-500 gap-2">
            <Loader2 className="h-5 w-5 animate-spin" />
            <span className="text-sm">Cargando archivos…</span>
          </div>
        ) : resources.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <Paperclip className="h-10 w-10 text-gray-300 dark:text-slate-600 mb-3" />
            <p className="text-sm font-medium text-gray-500 dark:text-slate-400">No hay archivos subidos</p>
            <p className="text-xs text-gray-400 dark:text-slate-500 mt-1">
              Sube archivos desde aquí o desde el editor de campañas
            </p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 dark:border-slate-700 bg-gray-50 dark:bg-slate-900/40">
                <th className="px-4 py-3 text-left font-medium text-gray-500 dark:text-slate-400">Nombre</th>
                <th className="px-4 py-3 text-left font-medium text-gray-500 dark:text-slate-400 hidden sm:table-cell">Tamaño</th>
                <th className="px-4 py-3 text-left font-medium text-gray-500 dark:text-slate-400 hidden md:table-cell">Subido</th>
                <th className="px-4 py-3 text-right font-medium text-gray-500 dark:text-slate-400">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-slate-700">
              {pageItems.map(r => (
                <tr key={r.id} className="hover:bg-gray-50 dark:hover:bg-slate-700/40 transition-colors">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2 min-w-0">
                      <Paperclip className="h-4 w-4 flex-shrink-0 text-gray-400 dark:text-slate-500" />
                      <div className="min-w-0">
                        <p className="font-medium text-gray-900 dark:text-white truncate max-w-xs">
                          {r.original_name}
                        </p>
                        <p className="text-xs text-gray-400 dark:text-slate-500 font-mono truncate max-w-xs">
                          {window.location.origin}{r.url}
                        </p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-500 dark:text-slate-400 hidden sm:table-cell whitespace-nowrap">
                    {fmt(r.file_size)}
                  </td>
                  <td className="px-4 py-3 text-gray-500 dark:text-slate-400 hidden md:table-cell whitespace-nowrap">
                    {fmtDate(r.uploaded_at)}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => copyLink(r)}
                        title="Copiar enlace"
                        className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
                          copiedId === r.id
                            ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                            : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-slate-600'
                        }`}
                      >
                        {copiedId === r.id
                          ? <><Check className="h-3.5 w-3.5" /> Copiado</>
                          : <><Link2 className="h-3.5 w-3.5" /> Copiar enlace</>}
                      </button>
                      <button
                        onClick={() => deleteResource(r)}
                        title="Eliminar"
                        className="inline-flex items-center rounded-md p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-600 dark:text-slate-500 dark:hover:bg-red-900/20 dark:hover:text-red-400 transition-colors"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <Pager page={safePage} totalPages={totalPages} total={resources.length} unit="archivos" onPage={setPage} className="px-4 pb-3" />
      </div>
    </div>
  )
}
