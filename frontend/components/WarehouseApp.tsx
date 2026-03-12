'use client'

import { useState, useEffect, useCallback } from 'react'
import { Package, Boxes, Clock, Wifi, WifiOff } from 'lucide-react'
import { clsx } from 'clsx'
import { supabase } from '@/lib/supabase'
import { getPendingCount } from '@/lib/api'
import OrdersTab from './OrdersTab'
import InventoryTab from './InventoryTab'

type Tab = 'orders' | 'inventory'

function useCurrentTime() {
  const [time, setTime] = useState<string>('')

  useEffect(() => {
    function tick() {
      const now = new Date()
      const hours = now.getHours().toString().padStart(2, '0')
      const minutes = now.getMinutes().toString().padStart(2, '0')
      const seconds = now.getSeconds().toString().padStart(2, '0')
      setTime(`${hours}:${minutes}:${seconds}`)
    }
    tick()
    const interval = setInterval(tick, 1000)
    return () => clearInterval(interval)
  }, [])

  return time
}

export default function WarehouseApp() {
  const [activeTab, setActiveTab] = useState<Tab>('orders')
  const [pendingCount, setPendingCount] = useState<number>(0)
  const [isConnected, setIsConnected] = useState<boolean | null>(null)
  const [orderTabKey, setOrderTabKey] = useState(0)
  const currentTime = useCurrentTime()

  const refreshPendingCount = useCallback(async () => {
    try {
      const count = await getPendingCount()
      setPendingCount(count)
      setIsConnected(true)
    } catch {
      setIsConnected(false)
    }
  }, [])

  useEffect(() => {
    refreshPendingCount()
  }, [refreshPendingCount])

  useEffect(() => {
    let channel: ReturnType<typeof supabase.channel> | null = null

    try {
      channel = supabase
        .channel('warehouse-orders-changes')
        .on(
          'postgres_changes',
          {
            event: '*',
            schema: 'public',
            table: 'orders',
          },
          () => {
            refreshPendingCount()
            setOrderTabKey((k) => k + 1)
          }
        )
        .subscribe((status) => {
          if (status === 'SUBSCRIBED') {
            setIsConnected(true)
          } else if (status === 'CHANNEL_ERROR' || status === 'TIMED_OUT') {
            setIsConnected(false)
          }
        })
    } catch {
      setIsConnected(false)
    }

    return () => {
      if (channel) {
        supabase.removeChannel(channel)
      }
    }
  }, [refreshPendingCount])

  // Refresh pending count when switching to orders tab
  useEffect(() => {
    if (activeTab === 'orders') {
      refreshPendingCount()
    }
  }, [activeTab, refreshPendingCount])

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col">
      {/* Top header */}
      <header className="bg-slate-800 border-b border-slate-700 sticky top-0 z-40">
        <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
          {/* Logo and title */}
          <div className="flex items-center gap-3 flex-shrink-0">
            <div className="w-9 h-9 rounded-xl bg-indigo-600 flex items-center justify-center text-xl leading-none shadow-lg shadow-indigo-500/20">
              🏭
            </div>
            <div>
              <h1 className="text-white font-bold text-lg leading-tight tracking-tight">
                Sistema de Bodega
              </h1>
              <p className="text-slate-500 text-xs leading-none hidden sm:block">
                Warehouse Management
              </p>
            </div>
          </div>

          {/* Right side: status and time */}
          <div className="flex items-center gap-4">
            {/* Connection status */}
            <div
              className={clsx(
                'hidden sm:flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full',
                isConnected === null
                  ? 'text-slate-500 bg-slate-700/50'
                  : isConnected
                  ? 'text-emerald-400 bg-emerald-500/10'
                  : 'text-red-400 bg-red-500/10'
              )}
            >
              {isConnected === null ? (
                <>
                  <div className="w-1.5 h-1.5 rounded-full bg-slate-500" />
                  <span>Conectando...</span>
                </>
              ) : isConnected ? (
                <>
                  <Wifi className="h-3 w-3" />
                  <span>En línea</span>
                </>
              ) : (
                <>
                  <WifiOff className="h-3 w-3" />
                  <span>Sin conexión</span>
                </>
              )}
            </div>

            {/* Clock */}
            {currentTime && (
              <div className="flex items-center gap-1.5 text-slate-400 text-sm">
                <Clock className="h-3.5 w-3.5" />
                <span className="font-mono tabular-nums">{currentTime}</span>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Tab navigation */}
      <nav className="bg-slate-800 border-b border-slate-700">
        <div className="max-w-screen-2xl mx-auto px-4 sm:px-6">
          <div className="flex gap-1">
            <button
              onClick={() => setActiveTab('orders')}
              className={clsx(
                'flex items-center gap-2 px-5 py-4 text-sm font-medium border-b-2 transition-all relative',
                activeTab === 'orders'
                  ? 'border-indigo-500 text-indigo-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-600'
              )}
            >
              <Package className="h-4 w-4" />
              <span>Pedidos</span>
              {pendingCount > 0 && (
                <span
                  className="ml-1 inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full bg-amber-500 text-white text-xs font-bold badge-pulse"
                  title={`${pendingCount} pedidos pendientes`}
                >
                  {pendingCount > 99 ? '99+' : pendingCount}
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab('inventory')}
              className={clsx(
                'flex items-center gap-2 px-5 py-4 text-sm font-medium border-b-2 transition-all',
                activeTab === 'inventory'
                  ? 'border-indigo-500 text-indigo-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-600'
              )}
            >
              <Boxes className="h-4 w-4" />
              <span>Inventario</span>
            </button>
          </div>
        </div>
      </nav>

      {/* Main content */}
      <main className="flex-1 max-w-screen-2xl mx-auto w-full px-4 sm:px-6 py-6">
        {activeTab === 'orders' && <OrdersTab key={orderTabKey} />}
        {activeTab === 'inventory' && <InventoryTab />}
      </main>

      {/* Footer */}
      <footer className="bg-slate-800/50 border-t border-slate-700/50 py-3 mt-auto">
        <div className="max-w-screen-2xl mx-auto px-4 sm:px-6">
          <p className="text-slate-600 text-xs text-center">
            Sistema de Bodega &copy; {new Date().getFullYear()} &mdash; Agentes Luxury
          </p>
        </div>
      </footer>
    </div>
  )
}
