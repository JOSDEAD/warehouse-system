'use client'

import { useState, useEffect, useCallback } from 'react'
import { Search, Plus, AlertTriangle, Package2, Pencil } from 'lucide-react'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import { clsx } from 'clsx'
import { type InventoryItem } from '@/lib/types'
import { getInventory } from '@/lib/api'
import EditInventoryModal from './EditInventoryModal'
import AddInventoryModal from './AddInventoryModal'
import LoadingSpinner from './LoadingSpinner'

export default function InventoryTab() {
  const [items, setItems] = useState<InventoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [showLowStockOnly, setShowLowStockOnly] = useState(false)
  const [editingItem, setEditingItem] = useState<InventoryItem | null>(null)
  const [showAddModal, setShowAddModal] = useState(false)

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 350)
    return () => clearTimeout(timer)
  }, [search])

  const fetchInventory = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getInventory(debouncedSearch || undefined)
      setItems(data)
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Error al cargar el inventario. Verifique la conexión.'
      )
    } finally {
      setLoading(false)
    }
  }, [debouncedSearch])

  useEffect(() => {
    fetchInventory()
  }, [fetchInventory])

  const displayedItems = showLowStockOnly
    ? items.filter((item) => item.quantity <= item.min_stock)
    : items

  const lowStockCount = items.filter((item) => item.quantity <= item.min_stock).length

  function formatUpdatedAt(dateStr: string) {
    try {
      return format(new Date(dateStr), "d MMM yyyy, HH:mm", { locale: es })
    } catch {
      return dateStr
    }
  }

  return (
    <div className="space-y-5">
      {/* Controls row */}
      <div className="flex flex-col sm:flex-row gap-3">
        {/* Search input */}
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500 pointer-events-none" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por SKU, nombre o variedad..."
            className="w-full pl-9 pr-4 py-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-200 placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-colors"
          />
        </div>

        {/* Low stock toggle */}
        <label className="flex items-center gap-2.5 cursor-pointer px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 hover:border-slate-600 transition-colors flex-shrink-0">
          <div className="relative">
            <input
              type="checkbox"
              checked={showLowStockOnly}
              onChange={(e) => setShowLowStockOnly(e.target.checked)}
              className="sr-only"
            />
            <div
              className={clsx(
                'w-9 h-5 rounded-full transition-colors',
                showLowStockOnly ? 'bg-amber-500' : 'bg-slate-600'
              )}
            />
            <div
              className={clsx(
                'absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform shadow',
                showLowStockOnly ? 'translate-x-4' : 'translate-x-0'
              )}
            />
          </div>
          <span className="text-sm text-slate-300 whitespace-nowrap flex items-center gap-1.5">
            <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
            Solo stock bajo
            {lowStockCount > 0 && (
              <span className="ml-1 inline-flex items-center justify-center px-1.5 py-0.5 rounded-full bg-amber-500/20 text-amber-400 text-xs font-bold">
                {lowStockCount}
              </span>
            )}
          </span>
        </label>

        {/* Add button */}
        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm transition-colors flex-shrink-0 whitespace-nowrap"
        >
          <Plus className="h-4 w-4" />
          Agregar Item
        </button>
      </div>

      {/* Table */}
      {loading ? (
        <div className="py-16">
          <LoadingSpinner size="lg" label="Cargando inventario..." />
        </div>
      ) : error ? (
        <div className="py-12 text-center">
          <div className="inline-flex flex-col items-center gap-3 p-6 rounded-xl bg-red-500/10 border border-red-500/20 max-w-sm mx-auto">
            <div className="text-red-400 text-3xl">⚠️</div>
            <p className="text-red-400 text-sm font-medium">{error}</p>
            <button
              onClick={fetchInventory}
              className="px-4 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm font-medium transition-colors"
            >
              Reintentar
            </button>
          </div>
        </div>
      ) : displayedItems.length === 0 ? (
        <div className="py-16 text-center">
          <Package2 className="h-12 w-12 text-slate-600 mx-auto mb-3" />
          <p className="text-slate-400 text-base font-medium">
            {showLowStockOnly
              ? 'No hay productos con stock bajo'
              : 'No hay productos en el inventario'}
          </p>
          <p className="text-slate-600 text-sm mt-1">
            {search
              ? 'Intenta ajustar los términos de búsqueda'
              : showLowStockOnly
              ? 'Todo el inventario tiene stock suficiente'
              : 'Agrega productos usando el botón "Agregar Item"'}
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-700">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-900/60 border-b border-slate-700">
                <th className="text-left px-4 py-3 text-slate-400 font-medium text-xs uppercase tracking-wide">
                  SKU
                </th>
                <th className="text-left px-4 py-3 text-slate-400 font-medium text-xs uppercase tracking-wide">
                  Producto
                </th>
                <th className="text-left px-4 py-3 text-slate-400 font-medium text-xs uppercase tracking-wide">
                  Variedad
                </th>
                <th className="text-right px-4 py-3 text-slate-400 font-medium text-xs uppercase tracking-wide">
                  Cantidad
                </th>
                <th className="text-left px-4 py-3 text-slate-400 font-medium text-xs uppercase tracking-wide">
                  Unidad
                </th>
                <th className="text-right px-4 py-3 text-slate-400 font-medium text-xs uppercase tracking-wide">
                  Stock Mín.
                </th>
                <th className="text-left px-4 py-3 text-slate-400 font-medium text-xs uppercase tracking-wide hidden lg:table-cell">
                  Actualizado
                </th>
                <th className="text-center px-4 py-3 text-slate-400 font-medium text-xs uppercase tracking-wide">
                  Acciones
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/50">
              {displayedItems.map((item) => {
                const isLowStock = item.quantity <= item.min_stock
                return (
                  <tr
                    key={item.id}
                    className={clsx(
                      'table-row-hover transition-colors',
                      isLowStock && 'bg-amber-500/5'
                    )}
                  >
                    <td className="px-4 py-3">
                      <span className="font-mono text-indigo-400 text-xs">
                        {item.sku}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        {isLowStock && (
                          <AlertTriangle
                            className="h-3.5 w-3.5 text-amber-400 flex-shrink-0"
                            aria-label="Stock bajo"
                          />
                        )}
                        <span
                          className={clsx(
                            'font-medium',
                            isLowStock ? 'text-amber-100' : 'text-slate-200'
                          )}
                        >
                          {item.name}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-slate-400">
                      {item.variety || (
                        <span className="text-slate-600 italic">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span
                        className={clsx(
                          'font-bold text-base',
                          isLowStock ? 'text-amber-400' : 'text-white'
                        )}
                      >
                        {item.quantity}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-400 text-xs">
                      {item.unit || '—'}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-500 text-xs">
                      {item.min_stock}
                    </td>
                    <td className="px-4 py-3 text-slate-500 text-xs hidden lg:table-cell whitespace-nowrap">
                      {formatUpdatedAt(item.updated_at)}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <button
                        onClick={() => setEditingItem(item)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-indigo-600 text-slate-300 hover:text-white text-xs font-medium transition-colors"
                        title="Editar item"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                        Editar
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>

          {/* Table footer with count */}
          <div className="px-4 py-3 border-t border-slate-700 bg-slate-900/40 flex items-center justify-between">
            <span className="text-slate-500 text-xs">
              {displayedItems.length}{' '}
              {displayedItems.length === 1 ? 'producto' : 'productos'}
              {showLowStockOnly && ' con stock bajo'}
            </span>
            {lowStockCount > 0 && !showLowStockOnly && (
              <button
                onClick={() => setShowLowStockOnly(true)}
                className="text-amber-400 text-xs hover:text-amber-300 flex items-center gap-1 transition-colors"
              >
                <AlertTriangle className="h-3 w-3" />
                {lowStockCount} con stock bajo
              </button>
            )}
          </div>
        </div>
      )}

      {/* Modals */}
      {editingItem && (
        <EditInventoryModal
          item={editingItem}
          onClose={() => setEditingItem(null)}
          onSaved={() => {
            setEditingItem(null)
            fetchInventory()
          }}
        />
      )}

      {showAddModal && (
        <AddInventoryModal
          onClose={() => setShowAddModal(false)}
          onSaved={() => {
            setShowAddModal(false)
            fetchInventory()
          }}
        />
      )}
    </div>
  )
}
