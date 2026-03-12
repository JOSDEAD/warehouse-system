'use client'

import { useState, useEffect, useCallback } from 'react'
import { Search, PackageOpen } from 'lucide-react'
import { clsx } from 'clsx'
import { type Order, type FilterStatus } from '@/lib/types'
import { getOrders } from '@/lib/api'
import OrderCard from './OrderCard'
import LoadingSpinner from './LoadingSpinner'

const filterOptions: { value: FilterStatus; label: string }[] = [
  { value: 'all', label: 'Todos' },
  { value: 'pending', label: 'Pendientes' },
  { value: 'in_progress', label: 'En Proceso' },
  { value: 'completed', label: 'Completados' },
]

export default function OrdersTab() {
  const [orders, setOrders] = useState<Order[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeFilter, setActiveFilter] = useState<FilterStatus>('all')
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search)
    }, 350)
    return () => clearTimeout(timer)
  }, [search])

  const fetchOrders = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getOrders(
        activeFilter !== 'all' ? activeFilter : undefined,
        debouncedSearch || undefined
      )
      setOrders(data)
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Error al cargar los pedidos. Verifique la conexión con el servidor.'
      )
    } finally {
      setLoading(false)
    }
  }, [activeFilter, debouncedSearch])

  useEffect(() => {
    fetchOrders()
  }, [fetchOrders])

  const filterColorMap: Record<FilterStatus, string> = {
    all: 'bg-indigo-600 text-white border-indigo-600',
    pending: 'bg-amber-500/20 text-amber-400 border-amber-500/40',
    in_progress: 'bg-blue-500/20 text-blue-400 border-blue-500/40',
    completed: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40',
  }

  return (
    <div className="space-y-5">
      {/* Filters and search row */}
      <div className="flex flex-col sm:flex-row gap-3">
        {/* Filter pills */}
        <div className="flex items-center gap-2 flex-wrap">
          {filterOptions.map((option) => (
            <button
              key={option.value}
              onClick={() => setActiveFilter(option.value)}
              className={clsx(
                'px-4 py-2 rounded-full text-sm font-medium border transition-all whitespace-nowrap',
                activeFilter === option.value
                  ? filterColorMap[option.value]
                  : 'bg-slate-800 text-slate-400 border-slate-700 hover:border-slate-500 hover:text-slate-200'
              )}
            >
              {option.label}
            </button>
          ))}
        </div>

        {/* Search input */}
        <div className="relative flex-1 sm:max-w-xs ml-auto">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500 pointer-events-none" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por proforma o cliente..."
            className="w-full pl-9 pr-4 py-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-200 placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-colors"
          />
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="py-16">
          <LoadingSpinner size="lg" label="Cargando pedidos..." />
        </div>
      ) : error ? (
        <div className="py-12 text-center">
          <div className="inline-flex flex-col items-center gap-3 p-6 rounded-xl bg-red-500/10 border border-red-500/20 max-w-sm mx-auto">
            <div className="text-red-400 text-3xl">⚠️</div>
            <p className="text-red-400 text-sm font-medium">{error}</p>
            <button
              onClick={fetchOrders}
              className="px-4 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm font-medium transition-colors"
            >
              Reintentar
            </button>
          </div>
        </div>
      ) : orders.length === 0 ? (
        <div className="py-16 text-center">
          <PackageOpen className="h-12 w-12 text-slate-600 mx-auto mb-3" />
          <p className="text-slate-400 text-base font-medium">
            No hay pedidos que mostrar
          </p>
          <p className="text-slate-600 text-sm mt-1">
            {search || activeFilter !== 'all'
              ? 'Intenta ajustar los filtros de búsqueda'
              : 'Los pedidos aparecerán aquí cuando se reciban'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {orders.map((order) => (
            <OrderCard
              key={order.id}
              order={order}
              onOrderUpdated={fetchOrders}
            />
          ))}
        </div>
      )}
    </div>
  )
}
