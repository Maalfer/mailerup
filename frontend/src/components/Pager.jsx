import { ChevronLeft, ChevronRight } from 'lucide-react'

// Paginador reutilizable: "N elementos · pág. X/Y" + Anterior/Siguiente.
// Se oculta solo cuando hay una única página. Responsive (texto oculto en móvil).
export default function Pager({ page, totalPages, total, onPage, unit = 'elementos', className = '' }) {
  if (!totalPages || totalPages <= 1) return null
  return (
    <div className={`flex items-center justify-between gap-2 pt-3 mt-1 border-t border-gray-100 dark:border-slate-700 ${className}`}>
      <span className="text-xs text-gray-500 dark:text-slate-400">
        {typeof total === 'number' ? `${total.toLocaleString('es-ES')} ${unit} · ` : ''}pág. {page}/{totalPages}
      </span>
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => onPage(Math.max(1, page - 1))}
          disabled={page <= 1}
          aria-label="Página anterior"
          className="btn-secondary text-xs py-1 px-2 flex items-center gap-1 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <ChevronLeft className="h-3.5 w-3.5" /> <span className="hidden sm:inline">Anterior</span>
        </button>
        <button
          type="button"
          onClick={() => onPage(Math.min(totalPages, page + 1))}
          disabled={page >= totalPages}
          aria-label="Página siguiente"
          className="btn-secondary text-xs py-1 px-2 flex items-center gap-1 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <span className="hidden sm:inline">Siguiente</span> <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}
