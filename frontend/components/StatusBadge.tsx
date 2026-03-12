'use client'

import { clsx } from 'clsx'
import { type OrderStatus } from '@/lib/types'

interface StatusBadgeProps {
  status: OrderStatus
  className?: string
}

const statusConfig: Record<
  OrderStatus,
  { label: string; emoji: string; classes: string }
> = {
  pending: {
    label: 'Pendiente',
    emoji: '🟡',
    classes: 'bg-amber-500/10 text-amber-400 border border-amber-500/30',
  },
  in_progress: {
    label: 'En Proceso',
    emoji: '🔵',
    classes: 'bg-blue-500/10 text-blue-400 border border-blue-500/30',
  },
  completed: {
    label: 'Completado',
    emoji: '✅',
    classes: 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30',
  },
}

export default function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = statusConfig[status]

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium whitespace-nowrap',
        config.classes,
        className
      )}
    >
      <span>{config.emoji}</span>
      <span>{config.label}</span>
    </span>
  )
}
