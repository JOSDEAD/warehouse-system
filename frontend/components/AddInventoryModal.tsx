'use client'

import { useState, useEffect, useRef } from 'react'
import { X, PlusCircle, AlertCircle } from 'lucide-react'
import { type NewInventoryItem } from '@/lib/types'
import { createInventoryItem } from '@/lib/api'
import LoadingSpinner from './LoadingSpinner'

interface AddInventoryModalProps {
  onClose: () => void
  onSaved: () => void
}

const emptyForm: NewInventoryItem = {
  sku: '',
  name: '',
  variety: '',
  quantity: 0,
  unit: '',
  min_stock: 0,
}

export default function AddInventoryModal({
  onClose,
  onSaved,
}: AddInventoryModalProps) {
  const [formData, setFormData] = useState<NewInventoryItem>(emptyForm)
  const [rawQuantity, setRawQuantity] = useState('0')
  const [rawMinStock, setRawMinStock] = useState('0')
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
    if (name === 'quantity') {
      setRawQuantity(value)
      setFormData((prev) => ({ ...prev, quantity: Number(value) || 0 }))
    } else if (name === 'min_stock') {
      setRawMinStock(value)
      setFormData((prev) => ({ ...prev, min_stock: Number(value) || 0 }))
    } else {
      setFormData((prev) => ({ ...prev, [name]: value }))
    }
    if (error) setError(null)
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()

    if (!formData.sku.trim()) {
      setError('El SKU es requerido')
      return
    }
    if (!formData.name.trim()) {
      setError('El nombre del producto es requerido')
      return
    }
    if (isNaN(formData.quantity) || formData.quantity < 0) {
      setError('La cantidad debe ser un número válido mayor o igual a 0')
      return
    }
    if (isNaN(formData.min_stock) || formData.min_stock < 0) {
      setError('El stock mínimo debe ser un número válido mayor o igual a 0')
      return
    }

    setIsSubmitting(true)
    setError(null)
    try {
      await createInventoryItem({
        sku: formData.sku.trim().toUpperCase(),
        name: formData.name.trim(),
        variety: formData.variety.trim(),
        quantity: formData.quantity,
        unit: formData.unit.trim(),
        min_stock: formData.min_stock,
      })
      onSaved()
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Error al crear el item de inventario'
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
      aria-label="Agregar nuevo item de inventario"
    >
      <div className="bg-slate-800 border border-slate-700 rounded-2xl w-full max-w-md shadow-2xl animate-slide-up">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-700">
          <div>
            <h2 className="text-white font-bold text-lg">Agregar Item</h2>
            <p className="text-slate-400 text-sm mt-0.5">
              Nuevo producto al inventario
            </p>
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

          {/* SKU */}
          <div>
            <label
              htmlFor="add-sku"
              className="block text-slate-300 text-xs font-medium mb-1.5 uppercase tracking-wide"
            >
              SKU <span className="text-red-400">*</span>
            </label>
            <input
              ref={firstInputRef}
              id="add-sku"
              type="text"
              name="sku"
              value={formData.sku}
              onChange={handleChange}
              required
              placeholder="Ej: PROD-001"
              className="w-full px-4 py-2.5 rounded-lg bg-slate-900 border border-slate-600 text-white placeholder-slate-500 font-mono text-sm focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          {/* Nombre */}
          <div>
            <label
              htmlFor="add-name"
              className="block text-slate-300 text-xs font-medium mb-1.5 uppercase tracking-wide"
            >
              Nombre <span className="text-red-400">*</span>
            </label>
            <input
              id="add-name"
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
              htmlFor="add-variety"
              className="block text-slate-300 text-xs font-medium mb-1.5 uppercase tracking-wide"
            >
              Variedad
            </label>
            <input
              id="add-variety"
              type="text"
              name="variety"
              value={formData.variety}
              onChange={handleChange}
              placeholder="Ej: Orgánico, Premium, Estándar"
              className="w-full px-4 py-2.5 rounded-lg bg-slate-900 border border-slate-600 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          {/* Cantidad inicial y Unidad */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label
                htmlFor="add-quantity"
                className="block text-slate-300 text-xs font-medium mb-1.5 uppercase tracking-wide"
              >
                Cantidad inicial
              </label>
              <input
                id="add-quantity"
                type="number"
                name="quantity"
                value={rawQuantity}
                onChange={handleChange}
                min="0"
                step="0.01"
                className="w-full px-4 py-2.5 rounded-lg bg-slate-900 border border-slate-600 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label
                htmlFor="add-unit"
                className="block text-slate-300 text-xs font-medium mb-1.5 uppercase tracking-wide"
              >
                Unidad
              </label>
              <input
                id="add-unit"
                type="text"
                name="unit"
                value={formData.unit}
                onChange={handleChange}
                placeholder="kg, cajas, unidades"
                className="w-full px-4 py-2.5 rounded-lg bg-slate-900 border border-slate-600 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          </div>

          {/* Stock mínimo */}
          <div>
            <label
              htmlFor="add-min-stock"
              className="block text-slate-300 text-xs font-medium mb-1.5 uppercase tracking-wide"
            >
              Stock Mínimo
            </label>
            <input
              id="add-min-stock"
              type="number"
              name="min_stock"
              value={rawMinStock}
              onChange={handleChange}
              min="0"
              step="0.01"
              className="w-full px-4 py-2.5 rounded-lg bg-slate-900 border border-slate-600 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
            />
            <p className="text-slate-500 text-xs mt-1">
              Recibirás alertas cuando el stock baje de este nivel
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
                  <PlusCircle className="h-4 w-4" />
                  Agregar Item
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
