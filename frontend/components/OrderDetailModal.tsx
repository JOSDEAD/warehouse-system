'use client'

import { useState, useEffect, useRef, useMemo } from 'react'
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
import { updateOrderStatus } from '@/lib/api'
import StatusBadge from './StatusBadge'
import LoadingSpinner from './LoadingSpinner'

interface OrderDetailModalProps {
  order: Order
  onClose: () => void
  onOrderUpdated: () => void
}

export default function OrderDetailModal({
  order,
  onClose,
  onOrderUpdated,
}: OrderDetailModalProps) {
  const [isUpdating, setIsUpdating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showCompleteForm, setShowCompleteForm] = useState(false)
  const [bodegueroName, setBodegueroName] = useState('')
  const [completedZones, setCompletedZones] = useState<Set<string>>(new Set())

  // Agrupar items por zona
  const itemsByZone = useMemo(() => {
    const map = new Map<string, typeof order.items>()
    for (const item of order.items ?? []) {
      const zone = item.zone || 'GENERAL'
      if (!map.has(zone)) map.set(zone, [])
      map.get(zone)!.push(item)
    }
    return map
  }, [order.items])

  function toggleZone(zone: string) {
    setCompletedZones(prev => {
      const next = new Set(prev)
      if (next.has(zone)) next.delete(zone)
      else next.add(zone)
      return next
    })
  }
  const nameInputRef = useRef<HTMLInputElement>(null)
  const modalRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = ''
    }
  }, [onClose])

  useEffect(() => {
    if (showCompleteForm && nameInputRef.current) {
      nameInputRef.current.focus()
    }
  }, [showCompleteForm])

  async function handleMarkInProgress() {
    setIsUpdating(true)
    setError(null)
    try {
      await updateOrderStatus(order.id, 'in_progress')
      onOrderUpdated()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al actualizar el pedido')
      setIsUpdating(false)
    }
  }

  async function handleMarkCompleted() {
    if (!bodegueroName.trim()) {
      nameInputRef.current?.focus()
      return
    }
    setIsUpdating(true)
    setError(null)
    try {
      await updateOrderStatus(order.id, 'completed', bodegueroName.trim())
      onOrderUpdated()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al completar el pedido')
      setIsUpdating(false)
    }
  }

  function formatDate(dateStr: string) {
    try {
      return format(new Date(dateStr), "d 'de' MMMM yyyy, HH:mm", { locale: es })
    } catch {
      return dateStr
    }
  }

  function getDuration(): string {
    if (!order.completed_at) return ''
    try {
      return formatDistanceStrict(
        new Date(order.completed_at),
        new Date(order.created_at),
        { locale: es }
      )
    } catch {
      return ''
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 modal-backdrop"
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.75)' }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
      role="dialog"
      aria-modal="true"
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
              <h2 className="text-white text-xl font-bold truncate">
                {order.client_name}
              </h2>
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
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Package className="h-4 w-4 text-indigo-400" />
              <h3 className="text-white font-semibold text-sm uppercase tracking-wide">
                Artículos ({order.items?.length ?? 0})
              </h3>
            </div>
            {itemsByZone.size > 0 && (
              <span className="text-slate-500 text-xs">
                {completedZones.size}/{itemsByZone.size} zonas listas
              </span>
            )}
          </div>

          {itemsByZone.size > 0 ? (
            <div className="space-y-3">
              {Array.from(itemsByZone.entries()).map(([zone, items]) => {
                const done = completedZones.has(zone)
                return (
                  <div
                    key={zone}
                    className={`rounded-xl border transition-colors ${
                      done
                        ? 'border-emerald-500/30 bg-emerald-500/5'
                        : 'border-slate-700 bg-slate-900/40'
                    }`}
                  >
                    {/* Zona header con checkbox */}
                    <button
                      onClick={() => toggleZone(zone)}
                      className="w-full flex items-center gap-3 px-4 py-3 text-left"
                    >
                      {/* Checkbox visual */}
                      <div className={`flex-shrink-0 w-5 h-5 rounded-full border-2 flex items-center justify-center transition-colors ${
                        done
                          ? 'border-emerald-500 bg-emerald-500'
                          : 'border-slate-500'
                      }`}>
                        {done && <CheckCircle className="h-3.5 w-3.5 text-white" />}
                      </div>
                      <MapPin className={`h-3.5 w-3.5 flex-shrink-0 ${done ? 'text-emerald-400' : 'text-indigo-400'}`} />
                      <span className={`font-semibold text-sm flex-1 ${done ? 'text-emerald-400 line-through' : 'text-white'}`}>
                        {zone}
                      </span>
                      <span className={`text-xs ${done ? 'text-emerald-500' : 'text-slate-500'}`}>
                        {items.length} {items.length === 1 ? 'artículo' : 'artículos'}
                      </span>
                    </button>

                    {/* Lista de items */}
                    <div className="px-4 pb-3 space-y-2">
                      {items.map((item, idx) => (
                        <div
                          key={item.id || idx}
                          className={`flex items-start justify-between gap-3 py-2 border-t border-slate-700/40 ${done ? 'opacity-50' : ''}`}
                        >
                          <span className={`text-sm flex-1 ${done ? 'line-through text-slate-500' : 'text-slate-200'}`}>
                            {item.description}
                          </span>
                          <span className={`text-sm font-bold flex-shrink-0 tabular-nums ${done ? 'text-slate-500' : 'text-white'}`}>
                            ×{item.quantity}
                          </span>
                        </div>
                      ))}
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

          {/* Completion info for completed orders */}
          {order.status === 'completed' && (
            <div className="mt-5 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
              <div className="flex items-center gap-2 mb-3">
                <CheckCircle className="h-4 w-4 text-emerald-400" />
                <span className="text-emerald-400 font-semibold text-sm">
                  Pedido Completado
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
                <div>
                  <span className="text-slate-400 text-xs block mb-0.5">
                    Completado por
                  </span>
                  <div className="flex items-center gap-1.5 text-white">
                    <User className="h-3.5 w-3.5 text-emerald-400" />
                    <span className="font-medium">
                      {order.completed_by || 'No especificado'}
                    </span>
                  </div>
                </div>
                {order.completed_at && (
                  <>
                    <div>
                      <span className="text-slate-400 text-xs block mb-0.5">
                        Fecha de completado
                      </span>
                      <div className="flex items-center gap-1.5 text-white">
                        <Calendar className="h-3.5 w-3.5 text-emerald-400" />
                        <span className="font-medium">
                          {formatDate(order.completed_at)}
                        </span>
                      </div>
                    </div>
                    <div>
                      <span className="text-slate-400 text-xs block mb-0.5">
                        Duración
                      </span>
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
                      if (e.key === 'Escape') {
                        setShowCompleteForm(false)
                        setBodegueroName('')
                      }
                    }}
                    placeholder="Ej: Juan García"
                    className="w-full px-4 py-2.5 rounded-lg bg-slate-900 border border-slate-600 text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                  />
                </label>
                <div className="flex gap-3">
                  <button
                    onClick={() => {
                      setShowCompleteForm(false)
                      setBodegueroName('')
                    }}
                    className="flex-1 px-4 py-2.5 rounded-lg bg-slate-700 text-slate-300 hover:bg-slate-600 font-medium text-sm transition-colors"
                  >
                    Cancelar
                  </button>
                  <button
                    onClick={handleMarkCompleted}
                    disabled={isUpdating || !bodegueroName.trim()}
                    className="flex-1 px-4 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold text-sm transition-colors flex items-center justify-center gap-2"
                  >
                    {isUpdating ? (
                      <LoadingSpinner size="sm" />
                    ) : (
                      <>
                        <CheckCircle className="h-4 w-4" />
                        Confirmar Completado
                      </>
                    )}
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
                    {isUpdating ? (
                      <LoadingSpinner size="sm" />
                    ) : (
                      <>
                        <PlayCircle className="h-4 w-4" />
                        Marcar como En Proceso
                      </>
                    )}
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
