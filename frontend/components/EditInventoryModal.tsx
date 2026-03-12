'use client'

import { useState, useEffect, useRef } from 'react'
import { X, Save, AlertCircle } from 'lucide-react'
import { type InventoryItem } from '@/lib/types'
import { updateInventory } from '@/lib/api'
import LoadingSpinner from './LoadingSpinner'

interface EditInventoryModalProps {
  item: InventoryItem
  onClose: () => void
  onSaved: () => void
}

export default function EditInventoryModal({
  item,
  onClose,
  onSaved,
}: EditInventoryModalProps) {
  const [formData, setFormData] = useState({
    name: item.name,
    variety: item.variety,
    quantity: String(item.quantity),
    unit: item.unit,
    min_stock: String(item.min_stock),
  })
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const firstInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    document.body.style.overflow = 'hidden'
    firstInputRef.current?.focus()
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = ''
    }
  }, [onClose])

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const { name, value } = e.target
    setFormData((prev) => ({ ...prev, [name]: value }))
    if (error) setError(null)
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()

    const quantity = Number(formData.quantity)
    const min_stock = Number(formData.min_stock)

    if (!formData.name.trim()) {
      setError('El nombre del producto es requerido')
      return
    }
    if (isNaN(quantity) || quantity < 0) {
      setError('La cantidad debe ser un número válido mayor o igual a 0')
      return
    }
    if (isNaN(min_stock) || min_stock < 0) {
      setError('El stock mínimo debe ser un número válido mayor o igual a 0')
      return
    }

    setIsSubmitting(true)
    setError(null)
    try {
      await updateInventory(item.id, {
        name: formData.name.trim(),
        variety: formData.variety.trim(),
        quantity,
        unit: formData.unit.trim(),
        min_stock,
      })
      onSaved()
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Error al actualizar el inventario'
      )
      setIsSubmitting(false)
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
      aria-label={`Editar item ${item.sku}`}
    >
      <div className="bg-slate-800 border border-slate-700 rounded-2xl w-full max-w-md shadow-2xl animate-slide-up">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-700">
          <div>
            <h2 className="text-white font-bold text-lg">Editar Inventario</h2>
            <p className="text-slate-400 text-sm mt-0.5 font-mono">{item.sku}</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
            aria-label="Cerrar"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 flex items-center gap-2 text-red-400 text-sm">
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* SKU (readonly) */}
          <div>
            <label className="block text-slate-400 text-xs font-medium mb-1.5 uppercase tracking-wide">
              SKU (Solo lectura)
            </label>
            <input
              type="text"
              value={item.sku}
              readOnly
              className="w-full px-4 py-2.5 rounded-lg bg-slate-900/60 border border-slate-700 text-slate-500 font-mono text-sm cursor-not-allowed"
            />
          </div>

          {/* Nombre */}
          <div>
            <label
              htmlFor="edit-name"
              className="block text-slate-300 text-xs font-medium mb-1.5 uppercase tracking-wide"
            >
              Nombre <span className="text-red-400">*</span>
            </label>
            <input
              ref={firstInputRef}
              id="edit-name"
              type="text"
              name="name"
              value={formData.name}
              onChange={handleChange}
              required
              placeholder="Nombre del producto"
              className="w-full px-4 py-2.5 rounded-lg bg-slate-900 border border-slate-600 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          {/* Variedad */}
          <div>
            <label
              htmlFor="edit-variety"
              className="block text-slate-300 text-xs font-medium mb-1.5 uppercase tracking-wide"
            >
              Variedad
            </label>
            <input
              id="edit-variety"
              type="text"
              name="variety"
              value={formData.variety}
              onChange={handleChange}
              placeholder="Ej: Orgánico, Premium, etc."
              className="w-full px-4 py-2.5 rounded-lg bg-slate-900 border border-slate-600 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          {/* Cantidad y Unidad */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label
                htmlFor="edit-quantity"
                className="block text-slate-300 text-xs font-medium mb-1.5 uppercase tracking-wide"
              >
                Cantidad <span className="text-red-400">*</span>
              </label>
              <input
                id="edit-quantity"
                type="number"
                name="quantity"
                value={formData.quantity}
                onChange={handleChange}
                min="0"
                step="0.01"
                required
                className="w-full px-4 py-2.5 rounded-lg bg-slate-900 border border-slate-600 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label
                htmlFor="edit-unit"
                className="block text-slate-300 text-xs font-medium mb-1.5 uppercase tracking-wide"
              >
                Unidad
              </label>
              <input
                id="edit-unit"
                type="text"
                name="unit"
                value={formData.unit}
                onChange={handleChange}
                placeholder="Ej: kg, cajas, unidades"
                className="w-full px-4 py-2.5 rounded-lg bg-slate-900 border border-slate-600 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          </div>

          {/* Stock mínimo */}
          <div>
            <label
              htmlFor="edit-min-stock"
              className="block text-slate-300 text-xs font-medium mb-1.5 uppercase tracking-wide"
            >
              Stock Mínimo <span className="text-red-400">*</span>
            </label>
            <input
              id="edit-min-stock"
              type="number"
              name="min_stock"
              value={formData.min_stock}
              onChange={handleChange}
              min="0"
              step="0.01"
              required
              className="w-full px-4 py-2.5 rounded-lg bg-slate-900 border border-slate-600 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
            />
            <p className="text-slate-500 text-xs mt-1">
              Se mostrará una advertencia cuando el stock esté por debajo de este valor
            </p>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2.5 rounded-lg bg-slate-700 text-slate-300 hover:bg-slate-600 font-medium text-sm transition-colors"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex-1 px-4 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold text-sm transition-colors flex items-center justify-center gap-2"
            >
              {isSubmitting ? (
                <LoadingSpinner size="sm" />
              ) : (
                <>
                  <Save className="h-4 w-4" />
                  Guardar Cambios
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
