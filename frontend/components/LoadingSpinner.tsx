'use client'

import { clsx } from 'clsx'

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  className?: string
  label?: string
}

export default function LoadingSpinner({
  size = 'md',
  className,
  label = 'Cargando...',
}: LoadingSpinnerProps) {
  const sizeClasses = {
    sm: 'h-4 w-4 border-2',
    md: 'h-8 w-8 border-2',
    lg: 'h-12 w-12 border-3',
  }

  return (
    <div
      className={clsx('flex flex-col items-center justify-center gap-3', className)}
      role="status"
      aria-label={label}
    >
      <div
        className={clsx(
          'rounded-full border-slate-700 border-t-indigo-500 animate-spin',
          sizeClasses[size]
        )}
        style={{ borderTopColor: '#6366f1', borderColor: '#334155' }}
      />
      {size !== 'sm' && (
        <span className="text-slate-400 text-sm">{label}</span>
      )}
    </div>
  )
}
