'use client'

import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { format, formatDistanceStrict } from 'date-fns'
import { es } from 'date-fns/locale'
import {
  X,
  CheckCircle,
  Clock,
  PlayCircle,
  User,
  Hash,
  Package,
  Calendar,
  AlertCircle,
  MapPin,
} from 'lucide-react'
import { type Order } from '@/lib/types'
import { updateOrderStatus, updateOrderProgress } from '@/lib/api'
import StatusBadge from './StatusBadge'
import LoadingSpinner from './LoadingSpinner'

interface OrderDetailModalProps {
  order: Order
  onClose: () => void
  onOrderUpdated: () => void
}

// ── Categorías ────────────────────────────────────────────────────────────────

type CategoryId = 'all' | 'leds' | 'perfiles' | 'fuentes' | 'cerebros' | 'otros'

const CATEGORIES: { id: CategoryId; label: string }[] = [
  { id: 'all',      label: 'Todos'    },
  { id: 'leds',     label: 'LEDs'     },
  { id: 'perfiles', label: 'Perfiles' },
  { id: 'fuentes',  label: 'Fuentes'  },
  { id: 'cerebros', label: 'Cerebros' },
  { id: 'otros',    label: 'Otros'    },
]

// El orden importa: Cerebros va ANTES de LEDs porque "Cerebro Secuencial" contiene "Secuencial"
const CAT_CHECKS: { id: Exclude<CategoryId, 'all' | 'otros'>; pattern: RegExp }[] = [
  { id: 'cerebros', pattern: /Cerebro/i },
  { id: 'leds',     pattern: /COB|Tira\s+Led|LED|RGB|Secuencial/i },
  { id: 'perfiles', pattern: /Perfil/i },
  { id: 'fuentes',  pattern: /Fuente/i },
]

function getCategory(description: string): CategoryId {
  const name = description.split('(')[0]
  for (const check of CAT_CHECKS) {
    if (check.pattern.test(name)) return check.id
  }
  return 'otros'
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function splitDescription(full: string): { name: string; detail: string | null } {
  const idx = full.indexOf('(')
  if (idx > 0) {
    const name = full.slice(0, idx).trim()
    const detail = full.slice(idx + 1).replace(/\)$/, '').trim()
    return { name, detail: detail || null }
  }
  return { name: full, detail: null }
}

function itemKey(orderId: string, zone: string, idx: number, id?: string): string {
  return id ? `${orderId}-${id}` : `${orderId}-${zone}-${idx}`
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function OrderDetailModal({
  order,
  onClose,
  onOrderUpdated,
}: OrderDetailModalProps) {
  const [isUpdating, setIsUpdating]       = useState(false)
  const [error, setError]                 = useState<string | null>(null)
  const [showCompleteForm, setShowCompleteForm] = useState(false)
  const [bodegueroName, setBodegueroName] = useState('')
  const [activeCategory, setActiveCategory] = useState<CategoryId>('all')

  // ── Progreso persistido en Supabase ──────────────────────────────────────
  const [checkedItems, setCheckedItems] = useState<Set<string>>(
    () => new Set(order.checked_items ?? [])
  )
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const persistChecked = useCallback((next: Set<string>) => {
    setCheckedItems(next)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      updateOrderProgress(order.id, Array.from(next)).catch(() => {})
    }, 600)
  }, [order.id])

  // ── Items agrupados por zona ──────────────────────────────────────────────
  const itemsByZone = useMemo(() => {
    const map = new Map<string, typeof order.items>()
    for (const item of order.items ?? []) {
      const zone = item.zone || 'GENERAL'
      if (!map.has(zone)) map.set(zone, [])
      map.get(zone)!.push(item)
    }
    return map
  }, [order.items])

  // ── Conteo por categoría (para mostrar en los botones) ───────────────────
  const categoryCounts = useMemo(() => {
    const counts: Record<CategoryId, number> = {
      all: 0, leds: 0, perfiles: 0, fuentes: 0, cerebros: 0, otros: 0,
    }
    for (const item of order.items ?? []) {
      const cat = getCategory(item.description)
      counts[cat]++
      counts.all++
    }
    return counts
  }, [order.items])

  // ── Zona completada = TODOS sus items marcados (sin importar filtro) ──────
  function isZoneDone(zone: string): boolean {
    const items = itemsByZone.get(zone) ?? []
    if (items.length === 0) return false
    return items.every((item, idx) => checkedItems.has(itemKey(order.id, zone, idx, item.id)))
  }

  // ── Toggle item individual ────────────────────────────────────────────────
  function toggleItem(key: string) {
    const next = new Set(checkedItems)
    if (next.has(key)) next.delete(key)
    else next.add(key)
    persistChecked(next)
  }

  // ── Toggle zona: marca/desmarca solo los items visibles con el filtro activo
  function toggleZoneFiltered(zone: string, visibleItems: typeof order.items) {
    const allChecked = visibleItems.every((item, idx) =>
      checkedItems.has(itemKey(order.id, zone, idx, item.id))
    )
    const next = new Set(checkedItems)
    visibleItems.forEach((item, idx) => {
      const key = itemKey(order.id, zone, idx, item.id)
      if (allChecked) next.delete(key)
      else next.add(key)
    })
    persistChecked(next)
  }

  const totalItems = order.items?.length ?? 0
  const doneItems  = checkedItems.size
  const zonesTotal = itemsByZone.size
  const zonesDone  = Array.from(itemsByZone.keys()).filter(isZoneDone).length

  const nameInputRef = useRef<HTMLInputElement>(null)
  const modalRef     = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handleKeyDown)
    document.body.style.overflow = 'hidden'
    return () => { document.removeEventListener('keydown', handleKeyDown); document.body.style.overflow = '' }
  }, [onClose])

  useEffect(() => {
    if (showCompleteForm && nameInputRef.current) nameInputRef.current.focus()
  }, [showCompleteForm])

  async function handleMarkInProgress() {
    setIsUpdating(true); setError(null)
    try { await updateOrderStatus(order.id, 'in_progress'); onOrderUpdated() }
    catch (err) { setError(err instanceof Error ? err.message : 'Error al actualizar'); setIsUpdating(false) }
  }

  async function handleMarkCompleted() {
    if (!bodegueroName.trim()) { nameInputRef.current?.focus(); return }
    setIsUpdating(true); setError(null)
    try { await updateOrderStatus(order.id, 'completed', bodegueroName.trim()); onOrderUpdated() }
    catch (err) { setError(err instanceof Error ? err.message : 'Error al completar'); setIsUpdating(false) }
  }

  function formatDate(dateStr: string) {
    try { return format(new Date(dateStr), "d 'de' MMMM yyyy, HH:mm", { locale: es }) }
    catch { return dateStr }
  }

  function getDuration(): string {
    if (!order.completed_at) return ''
    try { return formatDistanceStrict(new Date(order.completed_at), new Date(order.created_at), { locale: es }) }
    catch { return '' }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 modal-backdrop"
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.75)' }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
      role="dialog" aria-modal="true"
      aria-label={`Detalle del pedido ${order.proforma_number}`}
    >
      <div
        ref={modalRef}
        className="bg-slate-800 border border-slate-700 rounded-2xl w-full max-w-2xl max-h-[90vh] flex flex-col shadow-2xl animate-slide-up"
      >
        {/* Header */}
        <div className="flex items-start justify-between p-6 border-b border-slate-700">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 flex-wrap mb-2">
              <h2 className="text-white text-xl font-bold truncate">{order.client_name}</h2>
              <StatusBadge status={order.status} />
            </div>
            <div className="flex items-center gap-4 text-slate-400 text-sm flex-wrap">
              <span className="flex items-center gap-1.5">
                <Hash className="h-3.5 w-3.5" />
                <span className="font-mono">{order.proforma_number}</span>
              </span>
              <span className="flex items-center gap-1.5">
                <Calendar className="h-3.5 w-3.5" />
                <span>{formatDate(order.created_at)}</span>
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="ml-4 p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700 transition-colors flex-shrink-0"
            aria-label="Cerrar modal"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Items por zona */}
        <div className="flex-1 overflow-y-auto p-6">

          {/* Contadores */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Package className="h-4 w-4 text-indigo-400" />
              <h3 className="text-white font-semibold text-sm uppercase tracking-wide">
                Artículos ({totalItems})
              </h3>
            </div>
            {zonesTotal > 0 && (
              <div className="flex items-center gap-3 text-xs">
                <span className="text-slate-500">{doneItems}/{totalItems} artículos</span>
                <span className={`font-semibold ${zonesDone === zonesTotal ? 'text-emerald-400' : 'text-slate-400'}`}>
                  {zonesDone}/{zonesTotal} zonas listas
                </span>
              </div>
            )}
          </div>

          {/* Barra de progreso */}
          {totalItems > 0 && (
            <div className="w-full h-1.5 bg-slate-700 rounded-full mb-4 overflow-hidden">
              <div
                className="h-full bg-emerald-500 rounded-full transition-all duration-300"
                style={{ width: `${(doneItems / totalItems) * 100}%` }}
              />
            </div>
          )}

          {/* Filtros de categoría */}
          {totalItems > 0 && (
            <div className="flex gap-2 flex-wrap mb-4">
              {CATEGORIES.filter(cat => cat.id === 'all' || categoryCounts[cat.id] > 0).map(cat => {
                const active = activeCategory === cat.id
                return (
                  <button
                    key={cat.id}
                    onClick={() => setActiveCategory(cat.id)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                      active
                        ? 'bg-indigo-600 border-indigo-500 text-white'
                        : 'bg-slate-700/50 border-slate-600 text-slate-400 hover:border-slate-400 hover:text-slate-200'
                    }`}
                  >
                    {cat.label}
                    {cat.id !== 'all' && (
                      <span className={`ml-1.5 ${active ? 'text-indigo-200' : 'text-slate-500'}`}>
                        {categoryCounts[cat.id]}
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          )}

          {/* Zonas */}
          {itemsByZone.size > 0 ? (
            <div className="space-y-3">
              {Array.from(itemsByZone.entries()).map(([zone, allItems]) => {
                // Items visibles según filtro activo
                const visibleItems = activeCategory === 'all'
                  ? allItems
                  : allItems.filter(item => getCategory(item.description) === activeCategory)

                // Saltar zonas sin items visibles
                if (visibleItems.length === 0) return null

                // Zona done = TODOS los items (no solo los visibles)
                const zoneDone = isZoneDone(zone)

                // Todos los items VISIBLES marcados (pero zona puede no estar done)
                const allVisibleChecked = visibleItems.every((item, idx) =>
                  checkedItems.has(itemKey(order.id, zone, idx, item.id))
                )
                const someVisibleChecked = visibleItems.some((item, idx) =>
                  checkedItems.has(itemKey(order.id, zone, idx, item.id))
                )

                // Estado visual de la zona
                const zoneColor = zoneDone
                  ? 'border-emerald-500/30 bg-emerald-500/5'
                  : allVisibleChecked && activeCategory !== 'all'
                    ? 'border-amber-500/30 bg-amber-500/5'   // filtrado completo pero zona no lista
                    : someVisibleChecked
                      ? 'border-indigo-500/20 bg-slate-900/40'
                      : 'border-slate-700 bg-slate-900/40'

                return (
                  <div key={zone} className={`rounded-xl border transition-all ${zoneColor}`}>
                    {/* Cabecera de zona */}
                    <button
                      onClick={() => toggleZoneFiltered(zone, visibleItems)}
                      className="w-full flex items-center gap-3 px-4 py-3 text-left"
                    >
                      {/* Círculo de estado */}
                      <div className={`flex-shrink-0 w-5 h-5 rounded-full border-2 flex items-center justify-center transition-colors ${
                        zoneDone
                          ? 'border-emerald-500 bg-emerald-500'
                          : allVisibleChecked && activeCategory !== 'all'
                            ? 'border-amber-500 bg-amber-500/20'
                            : 'border-slate-500'
                      }`}>
                        {zoneDone
                          ? <CheckCircle className="h-3.5 w-3.5 text-white" />
                          : allVisibleChecked && activeCategory !== 'all'
                            ? <span className="w-2 h-2 rounded-full bg-amber-400 block" />
                            : null
                        }
                      </div>

                      <MapPin className={`h-3.5 w-3.5 flex-shrink-0 ${zoneDone ? 'text-emerald-400' : 'text-indigo-400'}`} />

                      <span className={`font-semibold text-sm flex-1 ${zoneDone ? 'text-emerald-400 line-through' : 'text-white'}`}>
                        {zone}
                      </span>

                      {/* Contador: visibles/total de zona */}
                      <span className={`text-xs tabular-nums ${zoneDone ? 'text-emerald-500' : 'text-slate-500'}`}>
                        {allItems.filter((item, idx) => checkedItems.has(itemKey(order.id, zone, idx, item.id))).length}/{allItems.length}
                        {activeCategory !== 'all' && (
                          <span className="text-slate-600"> ({visibleItems.length} vis.)</span>
                        )}
                      </span>
                    </button>

                    {/* Items visibles */}
                    <div className="px-4 pb-3 space-y-1">
                      {visibleItems.map((item) => {
                        // Buscar idx real del item en allItems para mantener la clave correcta
                        const realIdx = allItems.indexOf(item)
                        const key     = itemKey(order.id, zone, realIdx, item.id)
                        const checked = checkedItems.has(key)
                        const { name, detail } = splitDescription(item.description)
                        return (
                          <button
                            key={key}
                            onClick={(e) => { e.stopPropagation(); toggleItem(key) }}
                            className={`w-full flex items-start gap-3 py-2.5 px-1 border-t border-slate-700/40 text-left group transition-opacity ${
                              checked ? 'opacity-60' : 'opacity-100'
                            }`}
                          >
                            <div className={`flex-shrink-0 mt-0.5 w-4 h-4 rounded border-2 flex items-center justify-center transition-colors ${
                              checked ? 'border-emerald-500 bg-emerald-500' : 'border-slate-500 group-hover:border-slate-300'
                            }`}>
                              {checked && (
                                <svg className="w-2.5 h-2.5 text-white" viewBox="0 0 10 10" fill="none">
                                  <path d="M1.5 5l2.5 2.5 4.5-4.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                                </svg>
                              )}
                            </div>
                            <div className="flex-1 min-w-0">
                              <span className={`text-sm font-medium leading-snug ${checked ? 'line-through text-slate-500' : 'text-slate-200'}`}>
                                {name}
                              </span>
                              {detail && (
                                <span className={`block text-xs mt-0.5 ${checked ? 'text-slate-600' : 'text-slate-400'}`}>
                                  {detail}
                                </span>
                              )}
                            </div>
                            <span className={`text-sm font-bold flex-shrink-0 tabular-nums mt-0.5 ${checked ? 'text-slate-500' : 'text-white'}`}>
                              ×{item.quantity}
                            </span>
                          </button>
                        )
                      })}
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <div className="text-center py-8 text-slate-400">
              <Package className="h-10 w-10 mx-auto mb-2 opacity-40" />
              <p>Sin artículos en este pedido</p>
            </div>
          )}

          {/* Info completado */}
          {order.status === 'completed' && (
            <div className="mt-5 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
              <div className="flex items-center gap-2 mb-3">
                <CheckCircle className="h-4 w-4 text-emerald-400" />
                <span className="text-emerald-400 font-semibold text-sm">Pedido Completado</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
                <div>
                  <span className="text-slate-400 text-xs block mb-0.5">Completado por</span>
                  <div className="flex items-center gap-1.5 text-white">
                    <User className="h-3.5 w-3.5 text-emerald-400" />
                    <span className="font-medium">{order.completed_by || 'No especificado'}</span>
                  </div>
                </div>
                {order.completed_at && (
                  <>
                    <div>
                      <span className="text-slate-400 text-xs block mb-0.5">Fecha de completado</span>
                      <div className="flex items-center gap-1.5 text-white">
                        <Calendar className="h-3.5 w-3.5 text-emerald-400" />
                        <span className="font-medium">{formatDate(order.completed_at)}</span>
                      </div>
                    </div>
                    <div>
                      <span className="text-slate-400 text-xs block mb-0.5">Duración</span>
                      <div className="flex items-center gap-1.5 text-white">
                        <Clock className="h-3.5 w-3.5 text-emerald-400" />
                        <span className="font-medium">{getDuration()}</span>
                      </div>
                    </div>
                  </>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer actions */}
        {(order.status === 'pending' || order.status === 'in_progress') && (
          <div className="p-6 border-t border-slate-700">
            {error && (
              <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 flex items-center gap-2 text-red-400 text-sm">
                <AlertCircle className="h-4 w-4 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}
            {showCompleteForm ? (
              <div className="space-y-3">
                <label className="block">
                  <span className="text-slate-300 text-sm font-medium mb-1.5 block">
                    Nombre del bodeguero que completó el pedido
                  </span>
                  <input
                    ref={nameInputRef}
                    type="text"
                    value={bodegueroName}
                    onChange={(e) => setBodegueroName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleMarkCompleted()
                      if (e.key === 'Escape') { setShowCompleteForm(false); setBodegueroName('') }
                    }}
                    placeholder="Ej: Juan García"
                    className="w-full px-4 py-2.5 rounded-lg bg-slate-900 border border-slate-600 text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                  />
                </label>
                <div className="flex gap-3">
                  <button
                    onClick={() => { setShowCompleteForm(false); setBodegueroName('') }}
                    className="flex-1 px-4 py-2.5 rounded-lg bg-slate-700 text-slate-300 hover:bg-slate-600 font-medium text-sm transition-colors"
                  >
                    Cancelar
                  </button>
                  <button
                    onClick={handleMarkCompleted}
                    disabled={isUpdating || !bodegueroName.trim()}
                    className="flex-1 px-4 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold text-sm transition-colors flex items-center justify-center gap-2"
                  >
                    {isUpdating ? <LoadingSpinner size="sm" /> : <><CheckCircle className="h-4 w-4" />Confirmar Completado</>}
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex flex-wrap gap-3">
                {order.status === 'pending' && (
                  <button
                    onClick={handleMarkInProgress}
                    disabled={isUpdating}
                    className="flex-1 min-w-[160px] px-4 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold text-sm transition-colors flex items-center justify-center gap-2"
                  >
                    {isUpdating ? <LoadingSpinner size="sm" /> : <><PlayCircle className="h-4 w-4" />Marcar como En Proceso</>}
                  </button>
                )}
                <button
                  onClick={() => setShowCompleteForm(true)}
                  disabled={isUpdating}
                  className="flex-1 min-w-[160px] px-4 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold text-sm transition-colors flex items-center justify-center gap-2"
                >
                  <CheckCircle className="h-4 w-4" />
                  Marcar como Completado
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
