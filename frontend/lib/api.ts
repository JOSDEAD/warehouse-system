import { type Order, type InventoryItem, type NewInventoryItem } from './types'

// Elimina trailing slash y agrega /api prefix
const BASE_URL = `${(process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '')}/api`

async function fetchJSON<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${path}`
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  })

  if (!response.ok) {
    const errorText = await response.text().catch(() => 'Unknown error')
    throw new Error(`API error ${response.status}: ${errorText}`)
  }

  return response.json() as Promise<T>
}

export async function getOrders(
  status?: string,
  search?: string
): Promise<Order[]> {
  const params = new URLSearchParams()
  if (status && status !== 'all') params.set('status', status)
  if (search && search.trim()) params.set('search', search.trim())
  const query = params.toString() ? `?${params.toString()}` : ''
  return fetchJSON<Order[]>(`/orders${query}`)
}

export async function getOrder(id: string): Promise<Order> {
  return fetchJSON<Order>(`/orders/${id}`)
}

export async function updateOrderStatus(
  id: string,
  status: string,
  completedBy?: string
): Promise<void> {
  const body: Record<string, string> = { status }
  if (completedBy) body.completed_by = completedBy
  await fetchJSON<void>(`/orders/${id}/status`, {
    method: 'PUT',
    body: JSON.stringify(body),
  })
}

export async function getInventory(search?: string): Promise<InventoryItem[]> {
  const params = new URLSearchParams()
  if (search && search.trim()) params.set('search', search.trim())
  const query = params.toString() ? `?${params.toString()}` : ''
  return fetchJSON<InventoryItem[]>(`/inventory${query}`)
}

export async function updateInventory(
  id: string,
  data: Partial<InventoryItem>
): Promise<void> {
  await fetchJSON<void>(`/inventory/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function createInventoryItem(
  data: NewInventoryItem
): Promise<InventoryItem> {
  return fetchJSON<InventoryItem>('/inventory', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateOrderProgress(
  id: string,
  checkedItems: string[]
): Promise<void> {
  await fetchJSON<void>(`/orders/${id}/progress`, {
    method: 'PATCH',
    body: JSON.stringify({ checked_items: checkedItems }),
  })
}

export async function getPendingCount(): Promise<number> {
  const orders = await fetchJSON<Order[]>('/orders?status=pending')
  return orders.length
}
