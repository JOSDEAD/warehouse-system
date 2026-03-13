'use client'

import { useState } from 'react'
import { formatDistanceToNow } from 'date-fns'
import { es } from 'date-fns/locale'
import { Package, ChevronRight, User, Hash } from 'lucide-react'
import { type Order } from '@/lib/types'
import StatusBadge from './StatusBadge'
import OrderDetailModal from './OrderDetailModal'

interface OrderCardProps {
  order: Order
  onOrderUpdated: () => void
}

function timeAgo(dateStr: string): string {
  try {
    const date = new Date(dateStr)
    const distance = formatDistanceToNow(date, { locale: es, addSuffix: false })
    return `hace ${distance}`
  } catch {
    return 'fecha desconocida'
  }
}

export default function OrderCard({ order, onOrderUpdated }: OrderCardProps) {
  const [isModalOpen, setIsModalOpen] = useState(false)

  const borderColorMap: Record<string, string> = {
    draft: 'border-l-zinc-500',
    pending: 'border-l-amber-500',
    in_progress: 'border-l-blue-500',
    completed: 'border-l-emerald-500',
  }

  return (
    <>
      <button
        onClick={() => setIsModalOpen(true)}
        className={`
          w-full text-left bg-slate-800 rounded-xl border border-slate-700
          border-l-4 ${borderColorMap[order.status]}
          p-5 card-hover cursor-pointer
          focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500
          group
        `}
      >
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <User className="h-3.5 w-3.5 text-slate-400 flex-shrink-0" />
              <h3 className="text-white font-semibold text-base truncate leading-tight">
                {order.client_name}
              </h3>
            </div>
            <div className="flex items-center gap-2">
              <Hash className="h-3.5 w-3.5 text-slate-400 flex-shrink-0" />
              <span className="text-slate-400 text-sm font-mono">
                {order.proforma_number}
              </span>
            </div>
          </div>
          <div className="flex-shrink-0 flex items-center gap-2">
            <StatusBadge status={order.status} />
            <ChevronRight className="h-4 w-4 text-slate-600 group-hover:text-indigo-400 transition-colors flex-shrink-0" />
          </div>
        </div>

        <div className="flex items-center justify-between pt-3 border-t border-slate-700/60">
          <div className="flex items-center gap-2 text-slate-400 text-sm">
            <Package className="h-3.5 w-3.5" />
            <span>
              {order.items?.length ?? 0}{' '}
              {(order.items?.length ?? 0) === 1 ? 'artículo' : 'artículos'}
            </span>
          </div>
          <span className="text-slate-500 text-xs">{timeAgo(order.created_at)}</span>
        </div>
      </button>

      {isModalOpen && (
        <OrderDetailModal
          order={order}
          onClose={() => setIsModalOpen(false)}
          onOrderUpdated={() => {
            setIsModalOpen(false)
            onOrderUpdated()
          }}
        />
      )}
    </>
  )
}
